"""Kandilli Rasathanesi (KOERI/BDTİM) deprem veritabanından katalog indirir.

AFAD apiv2 erişilemediğinde **Türkiye ulusal ağ verisinin birincil kaynağı** budur.
Kandilli'nin sorgulama sistemi (udim.koeri.boun.edu.tr/zeqdb) resmî bir REST API
sunmaz; form tabanlı bir ASP arayüzüdür. Akış iki adımlıdır:

    1. submitRecSearchT.asp?...&ofName=X.txt   -> sorguyu çalıştırır, X.txt üretir
    2. download.php?download_file=X.txt        -> sekmeyle ayrılmış sonucu verir

Bu kaynağın EMSC/USGS'e göre iki üstünlüğü var:
  * Olay başına BİRDEN FAZLA büyüklük tipi (MD, ML, Mw, Ms, Mb) verir. Aynı olay
    için hem ML hem Mw raporlanan kayıtlar, Mw dönüşüm bağıntılarını Türkiye
    verisiyle yeniden regresyonlamayı mümkün kılar (Faz 1 açık maddesi).
  * Ulusal ağ olduğu için küçük büyüklüklerde kapsamı daha yoğundur.

**Patlatma filtresi:** "Tip" kolonu Ke (kesin deprem) veya Sm değerini alır.
Sm kayıtlarının ortalama derinliği 0,0 km ve %90'ı mesai saatlerinde (08-18)
gerçekleşir — bunlar taş ocağı patlatmalarıdır, deprem değil. Karşılaştırma:
Ke kayıtları ortalama 10,3 km derinlikte ve %40'ı mesai saatlerinde (24 saate
düzgün dağılımın beklentisi ~%42). Varsayılan olarak Sm dışlanır.

Kullanım:
    python scripts/02c_download_koeri.py --start 1990 --end 2027 --minmag 3.0
"""
import argparse
import time
from pathlib import Path

import pandas as pd
import requests

# BETİK OLARAK ÇALIŞTIRILDIĞINDA DEPO KÖKÜ sys.path'TE DEĞİLDİR.
# Hat bu dosyaları `python scripts/xx.py` diye çağırır (`-m` ile değil --
# modül adı rakamla başladığı için mümkün de değil), o zaman sys.path[0]
# `scripts/` olur ve `src` paketi görünmez. Kök elle eklenir.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from src.ingest.ham_yaz import guvenli_yaz  # noqa: E402

BASE = "http://udim.koeri.boun.edu.tr/zeqdb"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw"
CACHE = RAW / "koeri"

LAT0, LAT1, LON0, LON1 = 35.0, 43.0, 25.0, 45.0
ENCODING = "windows-1254"

# Büyüklük tercihi: Mw doğrudan momentten gelir ve dönüşüm gerektirmez; sonra
# yüzey/cisim dalgası, en son yerel ve süre büyüklükleri.
MAG_PREFERENCE = [("Mw", "mw"), ("Ms", "ms"), ("Mb", "mb"), ("ML", "ml"), ("MD", "md")]


def fetch_year(year: int, minmag: float, retries: int = 3) -> str:
    """Bir yılın kataloğunu sekmeyle ayrılmış metin olarak döndürür (önbellekli)."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"koeri_{year}_m{minmag}.txt"
    if cached.exists() and cached.stat().st_size > 0:
        return cached.read_text(encoding="utf-8")

    name = f"dt_{year}_{int(minmag * 10)}.txt"
    query = {
        "bYear": year, "bMont": "01", "bDay": "01",
        "eYear": year, "eMont": "12", "eDay": "31",
        "EnMin": f"{LAT0:.2f}", "EnMax": f"{LAT1:.2f}",
        "BoyMin": f"{LON0:.2f}", "BoyMax": f"{LON1:.2f}",
        "MAGMin": f"{minmag:.1f}", "MAGMax": "9.0",
        "DerMin": "0", "DerMax": "500", "Tip": "0", "ofName": name,
    }
    headers = {"User-Agent": "deprem-tahmin-research/0.1", "Referer": f"{BASE}/"}
    for attempt in range(retries):
        try:
            # 1) sorguyu çalıştır (yanıt HTML; asıl veri sunucuda dosyaya yazılır)
            requests.get(f"{BASE}/submitRecSearchT.asp", params=query,
                         headers=headers, timeout=180).raise_for_status()
            # 2) üretilen dosyayı indir
            r = requests.get(f"{BASE}/download.php", params={"download_file": name},
                             headers=headers, timeout=120)
            r.raise_for_status()
            text = r.content.decode(ENCODING, errors="replace")
            if "Enlem" not in text:
                raise ValueError("beklenen başlık satırı yok")
            cached.write_text(text, encoding="utf-8")
            return text
        except Exception as e:  # noqa: BLE001
            print(f"  ! {year} deneme {attempt+1}/{retries}: {e}")
            time.sleep(5 * (attempt + 1))
    return ""


def parse(text: str) -> pd.DataFrame:
    """Sekmeyle ayrılmış KOERI çıktısını DataFrame'e çevirir."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if len(lines) < 2:
        return pd.DataFrame()
    header = [h.strip() for h in lines[0].split("\t")]
    rows = [ln.split("\t") for ln in lines[1:]]
    rows = [r for r in rows if len(r) == len(header)]
    df = pd.DataFrame(rows, columns=header)
    return df.rename(columns=lambda c: c.strip())


def normalize(df: pd.DataFrame, keep_blasts: bool = False) -> pd.DataFrame:
    """KOERI şemasını boru hattının ortak şemasına çevirir."""
    if df.empty:
        return df
    df = df.copy()
    df.columns = [c.strip() for c in df.columns]
    tip_col = next((c for c in df.columns if c.lower().startswith("tip")), None)
    if tip_col and not keep_blasts:
        before = len(df)
        df = df[df[tip_col].str.strip() == "Ke"]
        print(f"  patlatma/şüpheli filtresi: {before - len(df)} kayıt çıkarıldı")

    date_col = next(c for c in df.columns if "tarih" in c.lower())
    time_col = next(c for c in df.columns if "zaman" in c.lower())
    lat_col = next(c for c in df.columns if c.lower().startswith("enlem"))
    lon_col = next(c for c in df.columns if c.lower().startswith("boylam"))
    dep_col = next(c for c in df.columns if c.lower().startswith("der"))
    id_col = next((c for c in df.columns if "kod" in c.lower()), None)

    out = pd.DataFrame()
    out["event_id"] = ("KOERI_" + df[id_col].str.strip()) if id_col else None
    out["time"] = pd.to_datetime(
        df[date_col].str.strip().str.replace(".", "-", regex=False) + " "
        + df[time_col].str.strip(), errors="coerce", utc=True)
    out["lat"] = pd.to_numeric(df[lat_col], errors="coerce")
    out["lon"] = pd.to_numeric(df[lon_col], errors="coerce")
    out["depth_km"] = pd.to_numeric(df[dep_col], errors="coerce")

    # Tüm büyüklük tipleri korunur: Mw yeniden kalibrasyonu bunlara dayanacak.
    for col, _ in MAG_PREFERENCE:
        if col in df.columns:
            out[f"mag_{col.lower()}"] = pd.to_numeric(df[col], errors="coerce")

    # Tercih sırasına göre ilk sıfırdan farklı büyüklük seçilir (KOERI eksik
    # değerleri 0.0 olarak yazar, NaN olarak değil).
    out["mag"] = pd.NA
    out["mag_type"] = pd.NA
    for col, kind in MAG_PREFERENCE:
        key = f"mag_{col.lower()}"
        if key not in out.columns:
            continue
        usable = out["mag"].isna() & out[key].notna() & (out[key] > 0)
        out.loc[usable, "mag"] = out.loc[usable, key]
        out.loc[usable, "mag_type"] = kind
    out["mag"] = pd.to_numeric(out["mag"], errors="coerce")

    place_col = next((c for c in df.columns if c.lower().startswith("yer")), None)
    if place_col:
        out["place"] = df[place_col].str.strip()
    out["source"] = "KOERI"
    return out.dropna(subset=["time", "lat", "lon", "mag"])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1990)
    ap.add_argument("--end", type=int, default=2027)
    ap.add_argument("--minmag", type=float, default=3.0)
    ap.add_argument("--keep-blasts", action="store_true",
                    help="taş ocağı patlatmalarını (Tip=Sm) da tut")
    args = ap.parse_args()

    frames = []
    alinamayan = []
    for year in range(args.start, args.end):
        text = fetch_year(year, args.minmag)
        if not text:
            print(f"{year}: alınamadı")
            alinamayan.append(year)
            continue
        df = normalize(parse(text), args.keep_blasts)
        print(f"{year}: {len(df)} olay")
        if len(df):
            frames.append(df)
        time.sleep(1.0)

    # KISMİ İNDİRME BAŞARI SAYILMAZ.
    #
    # Eskiden alınamayan yıl `continue` ile atlanıyor, elde kalan neyse
    # yazılıp 0 ile çıkılıyordu. 28 Ağustos 2026'da KOERI sunucusu yılların
    # çoğuna yanıt vermedi; betik 19.339 satırı 72.473 satırlık dosyanın
    # üzerine yazdı ve BAŞARILI göründü. Kırpılmayı ancak hattaki monotonluk
    # koruması yakaladı -- yani ham dosya çoktan gitmişti.
    #
    # AMA DURMAK DA TEK BAŞINA DOĞRU DEĞİL. İlk düzeltmede burada koşulsuz
    # `SystemExit` vardı; o, kırpılmış yazma sorununu çözerken yenisini
    # yarattı: tek bir yıl bile alınamadığında hiç dosya yazılmıyor, var
    # olan dosya da (önbellek onu kapsamadığı için) bulunmuyordu -> 0 satır
    # -> hattaki monotonluk koruması reddediyor -> HİÇBİR ZAMAN YAYIN YOK.
    # "Sessizce kırpılmış" yerine "hiç yayımlamayan" bir sistem geçmişti.
    #
    # Korunması gereken şey DOSYADIR, durmanın kendisi değil. Dosya varsa
    # kırpılmış sonuç atılır ve hat eldeki (biraz eski) katalogla devam
    # eder. Dosya yoksa düşülecek bir yer yoktur; ancak o zaman durulur.
    if alinamayan:
        mevcut = RAW / "koeri_catalog.csv"
        ozet = f"! KOERI: {len(alinamayan)} yıl alınamadı: {alinamayan}"
        if mevcut.exists():
            print(ozet)
            print(f"  Kırpılmış sonuç YAZILMADI; {mevcut.name} olduğu gibi kaldı.")
            print("  Hat eldeki katalogla devam eder; eksik yıllar bir sonraki")
            print("  koşuda önbellekten tamamlanır.")
            return
        raise SystemExit(
            ozet + "\n  Düşülecek mevcut bir katalog da yok; durduruldu."
        )

    if not frames:
        print("Hiç veri alınamadı.")
        return
    out = pd.concat(frames, ignore_index=True)
    dst = RAW / "koeri_catalog.csv"
    guvenli_yaz(out, dst, ad="koeri_catalog.csv")
    print(f"Toplam {len(out)} olay -> {dst}")
    both = out[out["mag_ml"].notna() & (out["mag_ml"] > 0)
               & out["mag_mw"].notna() & (out["mag_mw"] > 0)] \
        if {"mag_ml", "mag_mw"} <= set(out.columns) else pd.DataFrame()
    print(f"Hem ML hem Mw raporlanan olay: {len(both)} "
          "(Mw dönüşüm bağıntısının yeniden regresyonu için)")


if __name__ == "__main__":
    main()
