"""Boru hattının tamamında paylaşılan sabitler ve tamlık kesmesi.

NEDEN AYRI BİR MODÜL: bu değerler ondan fazla yerde kopyalanmıştı — bölge
sınırları 10, hücre boyu 8, `load_mc` ise DÖRT ayrı uygulama halinde ve
birbirinden farklı varsayılanlarla (3.7, 3.8, 3.3). Böyle bir kopya ayrıştığında
hata vermez; modüller sessizce farklı bir ızgaraya ya da farklı bir Mc'ye göre
çalışır ve sonuçlar birbirine uymaz. Bu projede tam olarak bu sınıf hatalar
(zaman birimi, Mc kesmesi, hücre kimliği) en pahalı olanlardı.

`tests/test_config_consistency.py` bu değerlerin modüller arasında aynı kaldığını
sınar.
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"

# --- Izgara -----------------------------------------------------------------
LAT0, LAT1 = 35.0, 43.0
LON0, LON1 = 25.0, 45.0
STEP = 0.25
REGION = [[LAT0, LON0], [LAT0, LON1], [LAT1, LON1], [LAT1, LON0]]

# 1 derece enlemin km karşılığı (ortalama Dünya yarıçapında). Mesafe hesapları
# eşdikdörtgen yaklaşımı kullanır; Türkiye kutusunda ortanca hatası %0.011
# ölçüldü (bkz. src/ingest/declustering.validate_distance).
DEG_KM = 111.19492664455873

# --- Hedef tanımları --------------------------------------------------------
WINDOWS = [1, 7, 30, 90]
TARGET_MAGS = [4.5, 5.0, 5.5]

# --- Zaman bölmeleri --------------------------------------------------------
MODEL_START = "1990-01-01"      # tamlık dönemi başlangıcı
TRAIN_END = "2016-01-01"
VAL_END = "2021-01-01"
TEST_END = "2026-09-01"
SPLITS = {"train": (MODEL_START, TRAIN_END),
          "val": (TRAIN_END, VAL_END),
          "test": (VAL_END, TEST_END)}

MC_FALLBACK = 3.3


def cell_id(lat, lon):
    """Coğrafi koordinattan hücre kimliği — TEK tanım.

    Tüm modüller bu kuralı kullanmak zorundadır; ayrışırsa tahminler sessizce
    yanlış hücreye düşer.

    BİLİNEN SINIR DURUMU (yarı-açık aralık hatası).
    ------------------------------------------------
    floor((x - x0) / adım) üst sınırda bir taşar: tam 43,0000 K ya da tam
    45,0000 D'deki bir olay, bölge kutusunun bir satır/sütun DIŞINDA kalan bir
    hücre kimliği alır. Bölge filtresi `between(35, 43)` KAPALI aralık olduğu
    için bu olaylar filtreyi geçer -- kapalı filtre ile yarı-açık binlemenin
    tutarsızlığı.

    Ölçüldü (24 Ağustos 2026): tüm katalogda 2 olay bu duruma düşüyor
    (304.168 olayın 2'si), ikisi de M < 4,5 ve test döneminin dışında.
    Değerlendirme ızgarasının 2102 hücresinin 2'si (%0,095) bu şekilde
    oluşmuş.

    ÇÖZÜM (24 Ağustos 2026, dondurma sonrası 1. iş): ÜST SINIR KAPATILDI.
    Tam sınır değerindeki olay son hücreye atanır (`clip`). Böylece kapalı bölge
    filtresi ile ızgara ataması tutarlı hâle gelir ve olay ızgara dışına düşmez.

    Kapsam ölçülmüştü: birleşik katalogda 10 sınır olayı, bunların 2'si Mc
    üstünde, HİÇBİRİ M>=4,5 değil. Beklenen ve gerçekleşen etki karşılaştırması:
    `docs/CELLID_BEKLENEN_ETKI.md`.

    Not: `clip` yalnızca ÜST sınırı kapatır. Alt sınır (35,0 K / 25,0 D) zaten
    doğrudur: floor orada 0 verir ve bu son hücre değil ilk hücredir.
    """
    import numpy as np

    i = ((lat - LAT0) // STEP).astype(int)
    j = ((lon - LON0) // STEP).astype(int)
    # Üst sınırı kapat: tam LAT1 / LON1 üzerindeki olay son hücreye girer.
    n_lat = int(round((LAT1 - LAT0) / STEP))
    n_lon = int(round((LON1 - LON0) / STEP))
    return np.minimum(i, n_lat - 1) * 1000 + np.minimum(j, n_lon - 1)


def cell_center(cid: int) -> tuple[float, float]:
    """Hücre kimliğinden merkez koordinatı."""
    return (LAT0 + (cid // 1000) * STEP + STEP / 2,
            LON0 + (cid % 1000) * STEP + STEP / 2)


def load_mc(default: float = MC_FALLBACK) -> float:
    """Model dönemindeki (MODEL_START sonrası) EN YÜKSEK tamlık büyüklüğü.

    En yükseği alınır: kataloğun her alt döneminde eksiksiz olan tek kesim odur.
    Daha düşük bir kesim, ağın seyrek olduğu dönemlerde eksik olayları "yok"
    saymaya ve dolayısıyla sahte sismik sessizliğe yol açar.
    """
    path = PROC / "mc_by_period.csv"
    if not path.exists():
        return default
    df = pd.read_csv(path)
    start_year = pd.Timestamp(MODEL_START).year
    df = df[df["period"].str.slice(0, 4).astype(int) >= start_year]
    df = df.dropna(subset=["mc"])
    return float(df["mc"].max()) if not df.empty else default


def load_mc_and_b(default_mc: float = MC_FALLBACK,
                  default_b: float = 1.0) -> tuple[float, float]:
    """Mc ile birlikte olay-ağırlıklı b-değeri."""
    import numpy as np

    path = PROC / "mc_by_period.csv"
    if not path.exists():
        return default_mc, default_b
    df = pd.read_csv(path)
    start_year = pd.Timestamp(MODEL_START).year
    df = df[df["period"].str.slice(0, 4).astype(int) >= start_year]
    df = df.dropna(subset=["mc"])
    if df.empty:
        return default_mc, default_b
    return float(df["mc"].max()), float(np.average(df["b"], weights=df["n"]))
