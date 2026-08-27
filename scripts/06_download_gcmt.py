"""Global CMT kataloğundan odak mekanizmalarını indirir (NDK biçimi).

NEDEN GEREKLİ: Coulomb gerilim değişimi hesabı, kaynak fayın geometrisini
(doğrultu/eğim/kayma açısı) ve sismik momenti gerektirir. Kullandığımız katalog
kaynaklarının hiçbiri (AFAD, KOERI, EMSC, USGS-FDSN) odak mekanizması vermez.
Global CMT bunu verir ve 1976'dan bugüne kesintisizdir.

Coulomb, projenin açık kalan araştırma bahsidir. Fay ve gerinim katmanları
ablasyonda katkı vermedi çünkü ikisi de ZAMANDAN BAĞIMSIZ — yalnızca hücreleri
ayırabiliyorlar, zamanları değil, ve o işi yumuşatılmış sismisite zaten yapıyor.
Coulomb ise yapısal olarak farklıdır: her büyük depremden sonra çevre fayların
nasıl yüklendiğini söyler, yani ZAMANLA DEĞİŞİR.

NDK biçimi: olay başına 5 satır, sabit sütun genişlikleri. Doğrudan iki düğüm
düzleminin doğrultu/eğim/kayma açısını içerir — CMTSOLUTION biçimi yalnızca
moment tensörü verir ve düzlemlere çevrilmesi gerekir.
Biçim tanımı: https://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog/allorder.ndk_explained

Çıktı: data/raw/gcmt/turkey_gcmt.csv

Kullanım:
    python scripts/06_download_gcmt.py --start 1976 --end 2027
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import requests

BASE = "https://www.ldeo.columbia.edu/~gcmt/projects/CMT/catalog"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "gcmt"
LAT0, LAT1, LON0, LON1 = 35.0, 43.0, 25.0, 45.0
MONTHS = ["jan", "feb", "mar", "apr", "may", "jun",
          "jul", "aug", "sep", "oct", "nov", "dec"]
HEADERS = {"User-Agent": "deprem-tahmin-research/0.1"}


def fetch(url: str, cache: Path) -> str:
    if cache.exists() and cache.stat().st_size > 0:
        return cache.read_text(encoding="ascii", errors="ignore")
    try:
        r = requests.get(url, timeout=300, headers=HEADERS)
        if r.status_code != 200 or not r.text.strip():
            return ""
        cache.write_text(r.text, encoding="ascii", errors="ignore")
        time.sleep(0.5)
        return r.text
    except Exception as e:  # noqa: BLE001
        print(f"  ! {url.split('/')[-1]}: {e}")
        return ""


def parse_ndk(text: str) -> list[dict]:
    """NDK metnini ayrıştırır. Her olay tam 5 satırdır.

    Sütun konumları biçim tanımından alınmıştır; NDK sabit genişlikli olduğu için
    boşlukla bölmek güvenilir DEĞİLDİR (alanlar bitişebilir).
    """
    lines = [ln.rstrip("\n") for ln in text.splitlines() if ln.strip()]
    out = []
    for i in range(0, len(lines) - 4, 5):
        h, l2, l3, l4, l5 = lines[i:i + 5]
        try:
            # 1. satır: referans katalog, tarih, saat, konum, derinlik, mb, MS
            date, clock = h[5:15].strip(), h[16:26].strip()
            lat, lon = float(h[27:33]), float(h[34:41])
            depth = float(h[42:47])
            region = h[56:].strip()
            # 4. satır: sonda üstel + iki düğüm düzlemi (doğrultu/eğim/kayma)
            exponent = int(l4[0:2])
            parts = l5.split()
            # 5. satır sonu: strike1 dip1 rake1 strike2 dip2 rake2
            s1, d1, r1, s2, d2, r2 = (float(x) for x in parts[-6:])
            # skaler moment: 5. satırın ortasındaki değer x 10^exponent (dyn-cm)
            m0 = float(parts[-7]) * (10.0 ** exponent)
            ts = pd.to_datetime(f"{date} {clock}", format="%Y/%m/%d %H:%M:%S.%f",
                                errors="coerce", utc=True)
            if pd.isna(ts):
                continue
        except (ValueError, IndexError):
            continue
        out.append({"time": ts, "lat": lat, "lon": lon, "depth_km": depth,
                    "m0_dyncm": m0, "strike1": s1, "dip1": d1, "rake1": r1,
                    "strike2": s2, "dip2": d2, "rake2": r2, "region": region})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1976)
    ap.add_argument("--end", type=int, default=2027)
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)

    events: list[dict] = []
    print("tarihsel katalog (1976-2020)...")
    text = fetch(f"{BASE}/jan76_dec20.ndk", RAW / "jan76_dec20.ndk")
    events += parse_ndk(text)
    print(f"  {len(events)} olay")

    print("aylık güncellemeler (2021+)...")
    for year in range(max(2021, args.start), args.end):
        got = 0
        for mi, mon in enumerate(MONTHS, 1):
            tag = f"{mon}{year % 100:02d}"
            t = fetch(f"{BASE}/NEW_MONTHLY/{year}/{tag}.ndk", RAW / f"{tag}.ndk")
            if t:
                n = len(parse_ndk(t))
                events += parse_ndk(t)
                got += n
        print(f"  {year}: {got} olay")

    df = pd.DataFrame(events)
    if df.empty:
        raise SystemExit("! hiç olay ayrıştırılamadı — NDK biçimini kontrol edin.")
    import numpy as np
    df["mw"] = (2.0 / 3.0) * (np.log10(df["m0_dyncm"]) - 16.1)
    df = df.drop_duplicates(subset=["time", "lat", "lon"])

    tr = df[df.lat.between(LAT0, LAT1) & df.lon.between(LON0, LON1)].copy()
    tr = tr.sort_values("time").reset_index(drop=True)
    dst = RAW / "turkey_gcmt.csv"
    tr.to_csv(dst, index=False)
    print(f"\nküresel {len(df)} olay -> Türkiye kutusunda {len(tr)} -> {dst}")
    print(f"tarih aralığı: {tr.time.min():%Y-%m-%d} - {tr.time.max():%Y-%m-%d}")
    print(f"Mw>=6.0: {int((tr.mw >= 6.0).sum())}, Mw>=6.5: {int((tr.mw >= 6.5).sum())}")
    print("\nen büyük 5 olay:")
    print(tr.nlargest(5, "mw")[["time", "lat", "lon", "mw", "strike1", "dip1",
                                "rake1", "region"]].to_string(index=False))


if __name__ == "__main__":
    main()
