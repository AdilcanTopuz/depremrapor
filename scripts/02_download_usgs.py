"""USGS FDSN'den Türkiye bounding box (25-45E, 35-43N) kataloğunu indirir (1900+).

Kullanım:
    python scripts/02_download_usgs.py --start 1900 --end 2026 --minmag 3.0
Not: 1900-1970 arası sadece büyük depremler kayıtlıdır (Mc yüksek) — bu beklenen durumdur.
"""
import argparse
import io
import time
from pathlib import Path

import pandas as pd
import requests

from src.ingest.ham_yaz import guvenli_yaz

BASE = "https://earthquake.usgs.gov/fdsnws/event/1/query"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
BBOX = dict(minlatitude=35.0, maxlatitude=43.0, minlongitude=25.0, maxlongitude=45.0)


def fetch_range(y0: int, y1: int, minmag: float) -> pd.DataFrame:
    params = dict(format="csv", starttime=f"{y0}-01-01", endtime=f"{y1}-01-01",
                  minmagnitude=minmag, orderby="time-asc", **BBOX)
    r = requests.get(BASE, params=params, timeout=120)
    r.raise_for_status()
    if not r.text.strip():
        return pd.DataFrame()
    return pd.read_csv(io.StringIO(r.text))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1900)
    ap.add_argument("--end", type=int, default=2026)
    ap.add_argument("--minmag", type=float, default=3.0)
    ap.add_argument("--chunk", type=int, default=5, help="yıl dilimi (20k limit aşımına karşı)")
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    y = args.start
    while y < args.end:
        y1 = min(y + args.chunk, args.end)
        try:
            df = fetch_range(y, y1, args.minmag)
            print(f"{y}-{y1}: {len(df)} olay")
            if len(df) >= 20000:
                print("  ! 20k limitine takılmış olabilir — --chunk değerini düşürün.")
            frames.append(df)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {y}-{y1} hata: {e}")
        time.sleep(1.0)
        y = y1

    df = pd.concat(frames, ignore_index=True)
    df = df.rename(columns={"time": "time", "latitude": "lat", "longitude": "lon",
                            "depth": "depth_km", "mag": "mag", "magType": "mag_type",
                            "id": "event_id"})
    df["source"] = "USGS"
    out = RAW / "usgs_catalog.csv"
    guvenli_yaz(df, out, ad="usgs_catalog.csv")
    print(f"Toplam {len(df)} olay -> {out}")


if __name__ == "__main__":
    main()
