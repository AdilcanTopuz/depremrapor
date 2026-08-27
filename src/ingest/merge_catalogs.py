"""AFAD + KOERI + EMSC + USGS kataloglarını birleştirir, tekilleştirir, Mw'ye normalize eder.

Çıktı: data/processed/catalog_merged.csv

Tekilleştirme kuralı: iki olay |Δt| <= 16 sn VE mesafe <= 100 km VE |Δmw| <= 1 ise
aynı deprem kabul edilir; çakışmada SOURCE_PRIORITY sırasına göre daha yetkili kaynak
tutulur (AFAD > KOERI > EMSC > USGS).

Mw dönüşümü: varsayılan olarak data/processed/mw_conversion.json okunur — bu dosya
src.ingest.mw_calibration tarafından Kandilli'nin çoklu büyüklük kayıtlarından
regresyonla üretilir. Dosya yoksa aşağıdaki literatür ortalamalarına dönülür, ama
bu tercih edilmez: Türkiye verisiyle ölçüldüğünde literatürün ML bağıntısı
büyüklükleri M4 civarında ~0.2 birim şişiriyor.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import epoch_seconds

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"

# Düşük = tercih edilir. Ulusal ağlar (AFAD, Kandilli) bölgeye yakın olayları
# daha iyi konumlandırır; EMSC bölgesel, USGS globaldir.
SOURCE_PRIORITY = {"AFAD": 0, "KOERI": 1, "EMSC": 2, "USGS": 3}
CATALOG_FILES = ("afad_catalog.csv", "koeri_catalog.csv",
                 "emsc_catalog.csv", "usgs_catalog.csv")

CONV = {
    "ml": (0.953, 0.422),
    "md": (1.011, 0.038),
    "mb": (1.048, -0.142),
    "mw": (1.0, 0.0), "mww": (1.0, 0.0), "mwc": (1.0, 0.0),
    "mwb": (1.0, 0.0), "mwr": (1.0, 0.0), "mwp": (1.0, 0.0),
    # Ms 1:1 DEĞİLDİR; Türkiye verisi Mw = 0.781*Ms + 1.254 veriyor.
    "ms": (0.781, 1.254),
}


def load_conversions() -> dict:
    """Mw dönüşüm katsayıları: varsa Türkiye verisiyle kalibre edilmiş olanlar.

    src.ingest.mw_calibration, Kandilli'nin çoklu büyüklük kayıtlarından bu
    bağıntıları regresyonla kestirir. Dosya yoksa literatür ortalamalarına dönülür
    ama bu tercih edilmez: ML için literatür bağıntısı Türkiye verisinde
    büyüklükleri M4 civarında ~0.2 birim şişiriyor.
    """
    path = OUT / "mw_conversion.json"
    conv = dict(CONV)
    if not path.exists():
        print("! mw_conversion.json yok — literatür değerleri kullanılıyor "
              "(src.ingest.mw_calibration ile kalibre edin).")
        return conv
    data = json.loads(path.read_text())
    for src, rel in data.get("relations", {}).items():
        conv[src] = (rel["slope"], rel["intercept"])
    names = ", ".join(sorted(data.get("relations", {})))
    print(f"Mw dönüşümü: {data.get('source', '?')} verisiyle kalibre ({names})")
    return conv


def to_mw(mag: float, mag_type: str, conv: dict | None = None) -> float:
    if pd.isna(mag):
        return np.nan
    table = CONV if conv is None else conv
    a, b = table.get(str(mag_type).strip().lower(), (1.0, 0.0))
    return a * mag + b


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


COLUMNS = ["event_id", "time", "lat", "lon", "depth_km", "mag", "mag_type", "mw", "source"]


def load(path: Path, conv: dict | None = None) -> pd.DataFrame:
    df = pd.read_csv(path, low_memory=False)
    df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True, format="mixed")
    df = df.dropna(subset=["time", "lat", "lon", "mag"])
    if "mag_type" not in df.columns:
        df["mag_type"] = ""
    # Dönüşüm sonrası 0.1'lik büyüklük ızgarasına geri yuvarlanır. Eğimi 1 olmayan
    # bir bağıntı (Mw = 1.039*ML - 0.138 gibi) raporlanan 0.1 adımlarını düzensiz
    # aralıklara dağıtır; histogramda sahte tepe ve boşluklar oluşur, bu da hem
    # MAXC'yi hem b-değeri kestirimini bozar. Büyüklükler zaten 0.1'den daha
    # hassas raporlanmıyor, dolayısıyla bilgi kaybı yok.
    df["mw"] = np.round([to_mw(m, t, conv) for m, t in zip(df["mag"], df["mag_type"])], 1)
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = np.nan
    return df[COLUMNS]


def dedup(df: pd.DataFrame, dt_s: float = 16.0, dist_km: float = 100.0,
          dmag: float = 1.0) -> pd.DataFrame:
    """Kataloglar arası tekilleştirme — kaynak önceliği sırasıyla, birebir eşleme.

    Üç kural bu adımı yoğun artçı dizilerinde güvenli kılar:

    1. **Sadece kataloglar arası.** Bir katalog kendi içinde aynı olayı iki kez
       listelemez; aynı kaynaktan 20 saniye arayla gelen iki olay iki AYRI artçıdır.
       Bu yüzden her kaynak, yalnızca daha önce kabul edilmiş *diğer* kaynakların
       olaylarına karşı eşleştirilir (kaynak kendi bloğunu bitirince master'a eklenir).
    2. **Birebir eşleme.** Kabul edilmiş her olay en fazla bir kopyayı "tüketir".
       Aksi halde 6 Şubat 2023 gibi dizilerde tek bir ana şok, onu izleyen onlarca
       gerçek artçıyı kopya diye yutar.
    3. **Büyüklük tutarlılığı.** |Δmw| <= dmag; M7.5 ile M3.4 aynı olay değildir.

    Tolerans (16 sn / 100 km) ISC'nin kataloglar arası eşleme pratiğine yakındır:
    bölgesel ve global ağlar aynı olayın merkez üssünü onlarca km farkla verebilir.
    """
    df = df.assign(_prio=df["source"].map(SOURCE_PRIORITY).fillna(99))
    kept_frames: list[pd.DataFrame] = []
    m_t = np.empty(0)          # master zaman (saniye, sıralı)
    m_lat = np.empty(0)
    m_lon = np.empty(0)
    m_mw = np.empty(0)
    consumed = np.empty(0, dtype=bool)
    n_dropped = 0

    for _, block in df.sort_values(["_prio", "time"]).groupby("_prio", sort=True):
        block = block.sort_values("time")
        # "Tüketildi" bayrağı HER KAYNAK İÇİN sıfırlanır. Birebir eşleme kısıtı
        # yalnızca tek bir kaynak içinde geçerlidir (bir katalog aynı olayı iki kez
        # listelemez); kaynaklar arasında değil — bir gerçek olayın dört katalogda
        # dört kaydı olabilir. Bayrak bloklar arası taşınırsa şu zincir oluşur:
        # KOERI kaydı kabul edilir, EMSC kopyası onu tüketir, USGS kopyası artık
        # eşleşemez ve katalogda KOPYA olarak kalır.
        consumed[:] = False
        b_t = epoch_seconds(block["time"])
        b_lat, b_lon = block["lat"].to_numpy(), block["lon"].to_numpy()
        b_mw = block["mw"].to_numpy()
        keep = np.ones(len(block), dtype=bool)

        for i in range(len(block)):
            lo = np.searchsorted(m_t, b_t[i] - dt_s, side="left")
            hi = np.searchsorted(m_t, b_t[i] + dt_s, side="right")
            if hi <= lo:
                continue
            idx = np.arange(lo, hi)
            idx = idx[~consumed[idx]]
            if not len(idx):
                continue
            ok = haversine_km(m_lat[idx], m_lon[idx], b_lat[i], b_lon[i]) <= dist_km
            if not np.isnan(b_mw[i]):
                ok &= np.isnan(m_mw[idx]) | (np.abs(m_mw[idx] - b_mw[i]) <= dmag)
            cand = idx[ok]
            if not len(cand):
                continue
            best = cand[np.argmin(np.abs(m_t[cand] - b_t[i]))]  # zamanca en yakın eşleşme
            consumed[best] = True
            keep[i] = False
            n_dropped += 1

        block = block[keep]
        kept_frames.append(block)
        # bloğu master'a ekle (zaman sırasını koruyarak birleştir)
        add_t = epoch_seconds(block["time"])
        m_t = np.concatenate([m_t, add_t])
        m_lat = np.concatenate([m_lat, block["lat"].to_numpy()])
        m_lon = np.concatenate([m_lon, block["lon"].to_numpy()])
        m_mw = np.concatenate([m_mw, block["mw"].to_numpy()])
        consumed = np.concatenate([consumed, np.zeros(len(block), dtype=bool)])
        order = np.argsort(m_t, kind="stable")
        m_t, m_lat, m_lon, m_mw, consumed = (m_t[order], m_lat[order], m_lon[order],
                                             m_mw[order], consumed[order])

    out = pd.concat(kept_frames, ignore_index=True).drop(columns="_prio")
    out = out.sort_values("time").reset_index(drop=True)
    print(f"Tekilleştirme: {n_dropped} kopya düşürüldü "
          f"({100 * n_dropped / max(len(df), 1):.1f}%)")
    return out


def main() -> None:
    conv = load_conversions()
    frames = []
    for name in CATALOG_FILES:
        p = RAW / name
        if p.exists():
            frames.append(load(p, conv))
            print(f"{name}: {len(frames[-1])} olay")
        else:
            print(f"! {name} yok — önce indirme scriptlerini çalıştırın.")
    if not frames:
        return
    df = pd.concat(frames, ignore_index=True)
    df = dedup(df)
    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "catalog_merged.csv"
    df.to_csv(out, index=False)
    print(f"Birleşik katalog: {len(df)} olay -> {out}")


if __name__ == "__main__":
    main()
