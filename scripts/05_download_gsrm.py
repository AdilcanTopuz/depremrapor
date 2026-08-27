"""GEM Global Strain Rate Model (GSRM) gerinim hızı verisini indirir ve kırpar.

Bu, projenin ASIL ARAŞTIRMA BAHSİ için gereken katmandır (README §1, Kol B):
mevcut nöral nokta süreçleri yalnızca katalog kullanıyor; jeodezik gerinim hızı
eklemek literatürde denenmemiş kombinasyon.

Fay geometrisinden farklı bir bilgi taşır ve bu ayrım önemlidir: fay haritası
"burada bir fay var" der, gerinim hızı "burada kabuk şu hızla deforme oluyor",
yani gerilme birikim HIZINI verir. Fay katmanı ablasyonda katkı vermemişti
(geçmiş sismisiteyle büyük ölçüde artık çıktı); gerinim hızı jeodeziden gelir
ve sismisiteden bağımsız bir ölçümdür.

Kaynak: https://geodesy.unr.edu/GSRM/  (Kreemer, Blewitt & Klein 2014,
doi:10.1002/2014GC005407). Küresel 0.1 derece ızgara, birim 1e-9/yıl.

!!! LİSANS UYARISI !!!
GSRM v2.2 **CC-BY-NC-SA 3.0** ile dağıtılıyor — TİCARİ KULLANIMA KAPALI.
Bu proje araştırma/akademik amaçla kullanabilir, ancak README §8'de belirtilen
ticari kullanım senaryosunda bu katman KULLANILAMAZ; GEM'den
(licensing@globalquakemodel.org) ayrı izin gerekir. Türetilmiş modeller de aynı
lisansla dağıtılmak zorundadır (ShareAlike).

Çıktı: data/raw/gsrm/turkey_strain.csv

Kullanım:
    python scripts/05_download_gsrm.py
"""
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import requests

VERSION = "v2.2"
URL = f"https://geodesy.unr.edu/GSRM/{VERSION}/GSRM_strain.txt.Z"
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "gsrm"
ARCHIVE = RAW / f"GSRM_strain_{VERSION}.txt.Z"

LAT0, LAT1, LON0, LON1 = 35.0, 43.0, 25.0, 45.0
COLUMNS = ["lat", "lon", "exx", "eyy", "exy", "vorticity",
           "rl_nlc", "ll_nlc", "e1", "e2", "azi_e1"]


def download() -> None:
    if ARCHIVE.exists() and ARCHIVE.stat().st_size > 50_000_000:
        print(f"önbellek kullanılıyor: {ARCHIVE} "
              f"({ARCHIVE.stat().st_size/1e6:.0f} MB)")
        return
    RAW.mkdir(parents=True, exist_ok=True)
    print(f"indiriliyor: {URL}")
    with requests.get(URL, stream=True, timeout=900,
                      headers={"User-Agent": "deprem-tahmin-research/0.1"}) as r:
        r.raise_for_status()
        with open(ARCHIVE, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    print(f"-> {ARCHIVE} ({ARCHIVE.stat().st_size/1e6:.0f} MB)")


def extract_turkey() -> pd.DataFrame:
    """Sıkıştırılmış dosyayı AKIŞ halinde okuyup Türkiye kutusunu süzer.

    Dosya açıldığında birkaç yüz MB; tamamını belleğe almak yerine gzip'in
    çıktısı satır satır işlenir. (`.Z` Unix compress biçimidir; GNU gzip açar,
    Python'un standart kütüphanesinde karşılığı yoktur.)
    """
    print("Türkiye kutusu süzülüyor (akış halinde)...")
    proc = subprocess.Popen(["gzip", "-dc", str(ARCHIVE)],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    rows, seen = [], 0
    for raw in proc.stdout:
        line = raw.decode("ascii", errors="ignore")
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 11:
            continue
        seen += 1
        lat, lon = float(parts[0]), float(parts[1])
        if LAT0 <= lat <= LAT1 and LON0 <= lon <= LON1:
            rows.append([lat, lon] + [float(x) for x in parts[2:11]])
    proc.stdout.close()
    proc.wait()
    print(f"{seen} küresel satır tarandı, {len(rows)} tanesi Türkiye kutusunda")
    return pd.DataFrame(rows, columns=COLUMNS)


def main() -> None:
    if not shutil_which("gzip"):
        sys.exit("! gzip bulunamadı — .Z açmak için gerekli.")
    download()
    df = extract_turkey()
    if df.empty:
        sys.exit("! Türkiye kutusunda satır bulunamadı — biçimi kontrol edin.")

    # İkinci invaryant: sqrt(exx^2 + eyy^2 + 2*exy^2). Simetrik 2B tensör için
    # bu sqrt(e1^2 + e2^2) ile ÖZDEŞTİR; ikisi de hesaplanıp karşılaştırılarak
    # hem formül hem dosya biçimi doğrulanır.
    df["strain_2nd_inv"] = np.sqrt(df.exx**2 + df.eyy**2 + 2 * df.exy**2)
    check = np.sqrt(df.e1**2 + df.e2**2)
    denom = np.maximum(df.strain_2nd_inv.to_numpy(), 1e-12)
    rel = np.abs(check - df.strain_2nd_inv) / denom
    print(f"doğrulama: ikinci invaryant iki yoldan hesaplandı, "
          f"ortanca bağıl fark %{100*np.median(rel):.4f}")

    dst = RAW / "turkey_strain.csv"
    df.to_csv(dst, index=False)
    print(f"-> {dst}")
    print("\ngerinim hızı (1e-9/yıl) özet:")
    print(df["strain_2nd_inv"].describe().round(2).to_string())
    print("\nLİSANS: CC-BY-NC-SA 3.0 — ticari kullanıma KAPALI (bkz. modül başlığı)")


def shutil_which(name: str):
    import shutil
    return shutil.which(name)


if __name__ == "__main__":
    main()
