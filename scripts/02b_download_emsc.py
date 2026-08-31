"""EMSC (seismicportal.eu) FDSN'den Türkiye bbox kataloğunu indirir.

AFAD apiv2 erişilemediğinde (TR dışı IP engeli / WAF) **birincil Türkiye-bölgesi
beslemesi** olarak bu kullanılır; erişilebildiğinde AFAD'ın ikincil doğrulayıcısıdır.
EMSC kapsamı pratikte ~1998 sonrası anlamlıdır; öncesi için USGS'e güvenilir.

Kullanım:
    python scripts/02b_download_emsc.py --start 1998 --end 2027 --minmag 3.0
"""
import argparse
import io
import time
from pathlib import Path

import pandas as pd
import requests

from src.ingest.ham_yaz import guvenli_yaz

BASE = "https://www.seismicportal.eu/fdsnws/event/1/query"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
BBOX = dict(minlatitude=35.0, maxlatitude=43.0, minlongitude=25.0, maxlongitude=45.0)
LIMIT = 20000


def fetch_range(start: str, end: str, minmag: float, retries: int = 3) -> pd.DataFrame:
    params = dict(format="text", starttime=start, endtime=end,
                  minmagnitude=minmag, limit=LIMIT, **BBOX)
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=120,
                             headers={"User-Agent": "deprem-tahmin-research/0.1"})
            if r.status_code == 204 or not r.text.strip():
                return pd.DataFrame()
            r.raise_for_status()
            return pd.read_csv(io.StringIO(r.text), sep="|")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {start[:7]} deneme {attempt+1}/{retries}: {e}")
            time.sleep(5 * (attempt + 1))
    return pd.DataFrame()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1998)
    ap.add_argument("--end", type=int, default=2027)
    ap.add_argument("--minmag", type=float, default=3.0)
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    frames = []
    for year in range(args.start, args.end):
        df = fetch_range(f"{year}-01-01T00:00:00", f"{year+1}-01-01T00:00:00", args.minmag)
        print(f"{year}: {len(df)} olay")
        if len(df) >= LIMIT:
            print(f"  ! {year} limite ({LIMIT}) takıldı — bu yılı aylık dilimleyin.")
        if len(df):
            frames.append(df)
        time.sleep(1.0)

    if not frames:
        print("Hiç veri alınamadı.")
        return

    df = pd.concat(frames, ignore_index=True)
    # FDSN text kolonları '#EventID|Time|Latitude|...' şeklinde gelir
    df.columns = [c.lstrip("#").strip() for c in df.columns]
    df = df.rename(columns={"EventID": "event_id", "Time": "time", "Latitude": "lat",
                            "Longitude": "lon", "Depth/km": "depth_km",
                            "MagType": "mag_type", "Magnitude": "mag",
                            "EventLocationName": "place"})
    keep = [c for c in ("event_id", "time", "lat", "lon", "depth_km",
                        "mag", "mag_type", "place") if c in df.columns]
    df = df[keep]
    df["source"] = "EMSC"
    out = RAW / "emsc_catalog.csv"
    guvenli_yaz(df, out, ad="emsc_catalog.csv")
    print(f"Toplam {len(df)} olay -> {out}")


if __name__ == "__main__":
    main()
