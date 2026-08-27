"""Izgara (0.25 derece) bazlı öznitelik üretimi.

Her (hücre, referans tarihi) çifti için geçmişe bakan öznitelikler ve ileriye bakan
hedef etiketler üretir. Referans tarihleri: aylık kaydırmalı pencere.

Sızıntı (leakage) kuralı: bir referans tarihindeki öznitelikler YALNIZCA t < ref
olaylarını kullanır; hedefler yalnızca [ref, ref+w) penceresini. Bu ayrım
`np.searchsorted` ile indeks düzeyinde uygulanır.

Tamlık: kesme büyüklüğü data/processed/mc_by_period.csv'den okunur (model dönemindeki
en yüksek Mc). Sabit bir Mc varsayımı b-değerini sistematik olarak yanlış verir.

Çıktı: data/processed/grid_features.parquet
Kolonlar:
  cell_id, ref_date, lat_c, lon_c,
  n30, n90, n365, n3650          : son N günde Mw>=Mc olay sayısı
  bval, bval_trend               : b-değeri (MLE, son 10 yıl) ve 5 yıllık fark
  quiescence_z                   : sismik sessizlik Z-skoru (son 90g vs 10 yıl ortalama)
  tmax_since_m5                  : son Mw>=5'ten geçen yıl
  moment_rate                    : son 10 yıl kümülatif moment / yıl (log10)
  target_{w}d_m{X}               : ileriye w gün içinde hücrede Mw>=X ANA ŞOK var mı (0/1)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import epoch_seconds, read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

LAT0, LAT1, LON0, LON1, STEP = 35.0, 43.0, 25.0, 45.0, 0.25
WINDOWS = [1, 7, 30, 90]
# 4.5 eklendi: M>=5.0 hedefinde test setinde yalnızca 66 pozitif var ve
# jeofizik katman ablasyonunun güven aralıkları bu yüzden sıfırı içeriyor.
# Mc = 3.3 olduğundan 4.5 tamlık açısından güvenli (1.2 birim üstünde).
TARGET_MAGS = [4.5, 5.0, 5.5]
FEATURE_START = "1995-01-01"
BIN = 0.1
DAY = 86400.0
YEAR = 365.25 * DAY
MC_FALLBACK = 3.7


def load_mc(default: float = MC_FALLBACK) -> float:
    """Model dönemindeki en yüksek Mc — declustering ile aynı kesim kullanılır."""
    path = PROC / "mc_by_period.csv"
    if not path.exists():
        print(f"! {path} yok — Mc={default} varsayılıyor.")
        return default
    mc_df = pd.read_csv(path)
    mc_df = mc_df[mc_df["period"].str.slice(0, 4).astype(int) >= 1990].dropna(subset=["mc"])
    return float(mc_df["mc"].max()) if not mc_df.empty else default


def bvalue_from_sums(count: np.ndarray, mag_sum: np.ndarray, mc: float) -> np.ndarray:
    """Aki-Utsu MLE b-değeri, kümülatif toplamlardan vektörel olarak.

    b = log10(e) / (ortalama_M - (Mc - binGenisligi/2)); n < 30 ise güvenilmez -> NaN.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        mean_m = np.where(count > 0, mag_sum / np.maximum(count, 1), np.nan)
        denom = mean_m - (mc - BIN / 2)
        b = np.where((count >= 30) & (denom > 0), np.log10(np.e) / denom, np.nan)
    return b


def cell_features(t: np.ndarray, mw: np.ndarray, is_main: np.ndarray,
                  refs: np.ndarray, mc: float) -> dict:
    """Tek bir hücrenin tüm referans tarihleri için öznitelik ve hedefleri üretir.

    t sıralı (saniye). Tüm pencereler `searchsorted` ile indekslendiği için maliyet
    O((olay + referans) log olay) — satır satır pandas filtrelemesinin yerini alır.
    """
    # GEÇMİŞE BAKIŞ YAPI GEREĞİ SINIRLI. Öznitelikler artık `CellHistory`
    # üzerinden hesaplanır: görünürlük tavanı (t < ref) kuruluşta sabitlenir ve
    # açık API'de ileri bakışı ifade edecek hiçbir parametre yoktur -- `days`
    # pozitif olmak zorundadır.
    #
    # Önceki hâlde bu garanti, `searchsorted(..., side="left")` satırının doğru
    # yazılmış OLMASINA dayanıyordu. Beyan vardı, mekanizma yoktu (V15).
    from src.features.history_view import CellHistory

    hist = CellHistory(t, mw, refs)

    out: dict[str, np.ndarray] = {}
    for nd in (30, 90, 365, 3650):
        out[f"n{nd}"] = hist.count_within(nd)

    c10 = out["n3650"]
    c5 = hist.count_within(1825)
    b10 = bvalue_from_sums(c10, hist.sum_magnitude_within(3650), mc)
    b5 = bvalue_from_sums(c5, hist.sum_magnitude_within(1825), mc)
    out["bval"] = b10
    out["bval_trend"] = b5 - b10

    mean_90 = out["n3650"] / (3650 / 90)
    out["quiescence_z"] = (out["n90"] - mean_90) / np.maximum(np.sqrt(mean_90), 1e-6)

    sec = hist.seconds_since_last(5.0)
    with np.errstate(invalid="ignore"):
        out["tmax_since_m5"] = np.where(np.isfinite(sec), sec / YEAR, np.nan)

    mom10 = hist.moment_sum_within(3650)
    with np.errstate(divide="ignore", invalid="ignore"):
        out["moment_rate"] = np.where(mom10 > 0, np.log10(mom10 / 10.0), np.nan)

    # hedefler için ref sınırı (bunlar İLERİYE bakar; tanım gereği)
    hi = np.searchsorted(t, refs, side="left")

    # Hedefler, yalnızca [ref, ref+w) penceresinden. İki tanım birden üretilir:
    #   target_..._m50      : yalnızca ANA ŞOKLAR (README'nin tanımı; "yeni bir
    #                         bağımsız deprem mi oldu?" sorusu)
    #   target_..._m50_all  : ARTÇILAR DAHİL tüm olaylar
    # İkincisi ETAS ile adil kıyas için zorunludur: ETAS bir dallanma süreci olarak
    # artçıları da üretir, dolayısıyla ayrıştırılmış bir hedefe karşı ölçmek modeli
    # hiç üretmediği bir şeyle sınamak olur.
    for tm in TARGET_MAGS:
        tag = str(tm).replace(".", "")
        for suffix, t_tgt in (("", t[is_main & (mw >= tm)]), ("_all", t[mw >= tm])):
            for w in WINDOWS:
                lo = np.searchsorted(t_tgt, refs, side="left")
                hi_w = np.searchsorted(t_tgt, refs + w * DAY, side="left")
                out[f"target_{w}d_m{tag}{suffix}"] = (hi_w > lo).astype(np.int8)
                # SAYIM hedefi de üretilir. İkili hedef "en az bir olay var mı"
                # sorusunu sorar; oran (intensity) modelleri ise beklenen SAYIYI
                # tahmin eder ve değerlendirmede kullandığımız bilgi kazancı
                # metriği de sayıma dayanır. İkili hedefle eğitilen bir model,
                # ölçüldüğü amaçtan farklı bir amaç için eniyilenmiş olur.
                out[f"count_{w}d_m{tag}{suffix}"] = (hi_w - lo).astype(np.int16)
    return out


def main(freq: str = "MS", start: str | None = None, end: str | None = None,
         out_name: str = "grid_features.parquet",
         all_refs: bool = False, cells_from_baseline: bool = False) -> None:
    """Öznitelik tablosu üretir.

    `all_refs` ve `cells_from_baseline`, DEĞERLENDİRME tablosu için vardır.

    Varsayılan davranış (eğitim için doğru): bir hücrede ilk olaydan önceki
    referanslar atlanır -- o satırlar bilgisizdir ve milyonlarca boş satır
    üretmenin anlamı yoktur.

    Ama DEĞERLENDİRMEDE bu bir ASİMETRİ yaratır: ETAS her hücreyi puanlar
    (arka plan oranı her yerde vardır), ML ise yalnızca geçmişi olan hücrelerde
    puanlanır. Ölçüldü (V19): ETAS'ın değerlendirdiği 252 pozitiften 4'ü,
    Mc üstü İLK olayı hedef penceresinde olan hücrelerdeydi ve öznitelik
    tablosunda karşılığı yoktu. ML o dört zor pozitifte hiç sınanmayacaktı.

    "Geçmişi yok" bir bilgidir, bilginin yokluğu değildir.
    """
    mc = load_mc()
    df = read_catalog(PROC / "catalog_declustered.csv")
    df = df[(df.lat.between(LAT0, LAT1)) & (df.lon.between(LON0, LON1))]
    df = df[df.mw >= mc].sort_values("time").reset_index(drop=True)
    print(f"Mc={mc:.2f} kesimiyle {len(df)} olay")

    # KANONİK fonksiyon kullanılır. Elle kopyalanan formül üst sınırı kapatmaz;
    # tam 43,0000 K / 45,0000 D'deki olay ızgara dışına düşer (bkz.
    # config.cell_id ve docs/CELLID_BEKLENEN_ETKI.md).
    from src.config import cell_id as _cell_id

    df["cell_id"] = _cell_id(df.lat, df.lon)
    df["cell_lat"] = df.cell_id // 1000
    df["cell_lon"] = df.cell_id % 1000

    # Referans takvimi: varsayılan aylık. Günlük değerlendirme için ayrı bir
    # takvim verilebilir — öznitelikler aynı fonksiyonlarla, yalnızca farklı
    # referans anlarında hesaplanır, dolayısıyla dağılımları aynıdır ve aylık
    # veriyle eğitilen bir model günlük referanslarda tahmin yapabilir.
    ref_dates = pd.date_range(
        pd.Timestamp(start or FEATURE_START, tz="UTC"),
        pd.Timestamp(end, tz="UTC") if end else df.time.max(), freq=freq)
    refs = epoch_seconds(ref_dates)
    print(f"{df.cell_id.nunique()} aktif hücre, {len(ref_dates)} referans tarihi")

    # Değerlendirme kipinde hücre kümesi baseline_poisson'dan alınır -- ETAS'ın
    # puanladığı ızgaranın AYNISI olsun diye.
    zorunlu = set()
    if cells_from_baseline:
        bp = pd.read_csv(PROC / "baseline_poisson.csv")
        zorunlu = set(int(c) for c in bp.cell_id.unique())

    frames = []
    for cid, g in df.groupby("cell_id", sort=False):
        t = epoch_seconds(g["time"])
        # hücrede ilk olaydan önceki referanslar bilgisizdir — atlanır
        if all_refs:
            first = 0
        else:
            first = np.searchsorted(refs, t[0], side="right")
            if first >= len(refs):
                continue
        r = refs[first:]
        feats = cell_features(t, g["mw"].to_numpy(),
                              g["is_mainshock"].to_numpy(dtype=bool), r, mc)
        block = pd.DataFrame(feats)
        block.insert(0, "cell_id", cid)
        block.insert(1, "ref_date", ref_dates[first:])
        block.insert(2, "lat_c", LAT0 + (cid // 1000) * STEP + STEP / 2)
        block.insert(3, "lon_c", LON0 + (cid % 1000) * STEP + STEP / 2)
        frames.append(block)

    # Katalogda hiç olayı olmayan ama değerlendirme ızgarasında bulunan
    # hücreler: öznitelikleri sıfır/NaN, ama SATIRLARI VAR. Aksi hâlde ML o
    # hücrelerde puanlanmaz, ETAS puanlanır.
    gorulen = set(int(c) for c in df.cell_id.unique())
    for cid in sorted(zorunlu - gorulen):
        bos = cell_features(np.array([]), np.array([]),
                            np.array([], dtype=bool), refs, mc)
        block = pd.DataFrame(bos)
        block.insert(0, "cell_id", cid)
        block.insert(1, "ref_date", ref_dates)
        block.insert(2, "lat_c", LAT0 + (cid // 1000) * STEP + STEP / 2)
        block.insert(3, "lon_c", LON0 + (cid % 1000) * STEP + STEP / 2)
        frames.append(block)
    if zorunlu:
        print(f"değerlendirme ızgarası: {len(zorunlu)} hücre; "
              f"katalogda olayı olmayan {len(zorunlu - gorulen)} hücre için "
              "boş satırlar eklendi")

    feat = pd.concat(frames, ignore_index=True)
    out = PROC / out_name
    feat.to_parquet(out, index=False)
    print(f"{len(feat)} satır -> {out}")
    for col in [c for c in feat.columns if c.startswith("target_")]:
        print(f"  {col}: {int(feat[col].sum())} pozitif ({100*feat[col].mean():.3f}%)")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--freq", default="MS", help="MS=aylık, D=günlük")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--out", default="grid_features.parquet")
    ap.add_argument("--all-refs", action="store_true",
                    help="hücrenin ilk olayından önceki referansları da üret "
                         "(DEĞERLENDİRME için zorunlu)")
    ap.add_argument("--cells-from-baseline", action="store_true",
                    help="hücre kümesini baseline_poisson'dan al (ETAS ızgarası)")
    a = ap.parse_args()
    main(a.freq, a.start, a.end, a.out, a.all_refs, a.cells_from_baseline)
