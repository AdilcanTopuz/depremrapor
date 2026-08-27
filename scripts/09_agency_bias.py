"""Kurumlar arası sistematik büyüklük farkı kontrolü.

Birleşik katalog, aynı olayı birden çok kurum bildirdiğinde AFAD'ı önceliklendirir.
Bu seçim, kurumlar arasında sistematik bir kayma varsa katalogda dönemsel bir
sıçrama yaratabilir: kapsama zamanla değişir (USGS yalnızca büyük olayları
bildirir), dolayısıyla önceliklendirme büyüklük dağılımını dolaylı olarak
kaydırır ve b-değeri ile Mc kestirimlerini bozar.

Kontrol: aynı olayı bildiren kurum çiftleri eşleştirilir ve Mw farkının ortancası
ile dağılımı raporlanır. Eşleştirme merge_catalogs ile aynı ölçütü kullanır
(zaman ve mesafe yakınlığı), ancak burada amaç elemek değil KARŞILAŞTIRMAKTIR.

Kullanım:  python scripts/09_agency_bias.py
"""
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DEG_KM  # noqa: E402
from src.ingest.catalog_io import epoch_seconds  # noqa: E402
from src.ingest.merge_catalogs import load as load_raw  # noqa: E402
from src.ingest.merge_catalogs import load_conversions  # noqa: E402

RAW = ROOT / "data" / "raw"
DT_SEC = 30.0     # merge_catalogs ile aynı zaman toleransı
DIST_KM = 50.0    # merge_catalogs ile aynı mesafe toleransı


def load(name: str, conv: dict) -> pd.DataFrame:
    """Ham katalogu birleştirmeyle AYNI dönüşümlerden geçirerek yükler.

    merge_catalogs.load yeniden kullanılıyor: farkın kurumlardan mı yoksa iki
    ayrı dönüşüm uygulamasından mı geldiği belirsiz kalmasın.
    """
    df = load_raw(RAW / f"{name.lower()}_catalog.csv", conv)
    df = df.dropna(subset=["mw"]).sort_values("time").reset_index(drop=True)
    df["t"] = epoch_seconds(df["time"])
    return df


def pair(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """a'daki her olay için b'de zaman/mesafe toleransındaki EN YAKIN eşi."""
    out = []
    tb = b["t"].to_numpy()
    lo = np.searchsorted(tb, a["t"].to_numpy() - DT_SEC, side="left")
    hi = np.searchsorted(tb, a["t"].to_numpy() + DT_SEC, side="right")
    for i, (l, h) in enumerate(zip(lo, hi)):
        if h <= l:
            continue
        la, lo_a = a.lat.iat[i], a.lon.iat[i]
        d = np.sqrt(((b.lat.values[l:h] - la) * DEG_KM) ** 2 +
                    ((b.lon.values[l:h] - lo_a) * DEG_KM *
                     np.cos(np.radians(la))) ** 2)
        j = int(np.argmin(d))
        if d[j] <= DIST_KM:
            out.append((a.mw.iat[i], b.mw.values[l:h][j], a.time.iat[i]))
    return pd.DataFrame(out, columns=["mw_a", "mw_b", "time"])


def main() -> None:
    names = ["AFAD", "KOERI", "EMSC", "USGS"]
    conv = load_conversions()
    cats = {n: load(n, conv) for n in names}
    for n, d in cats.items():
        print(f"{n:6s}: {len(d):7d} olay, {d.time.min():%Y} - {d.time.max():%Y}")
    print()

    rows = []
    for x, y in combinations(names, 2):
        m = pair(cats[x], cats[y])
        if len(m) < 30:
            print(f"{x}-{y}: yalnızca {len(m)} eşleşme, atlanıyor")
            continue
        d = m.mw_a - m.mw_b
        # Test döneminde ayrıca ölçülür: kapsama zamanla değişir, bu yüzden
        # tüm katalogdaki ortalama fark test dönemini temsil etmeyebilir.
        late = d[m.time >= pd.Timestamp("2021-01-01", tz="UTC")]
        rows.append({
            "çift": f"{x}-{y}", "n": len(m), "ortanca_fark": d.median(),
            "ortalama": d.mean(), "std": d.std(),
            "n_2021+": len(late),
            "ortanca_2021+": late.median() if len(late) >= 30 else np.nan,
        })
    df = pd.DataFrame(rows)
    print(df.round(3).to_string(index=False))
    print("\n(pozitif = ilk kurum daha BÜYÜK bildiriyor)")
    worst = df.loc[df.ortanca_fark.abs().idxmax()]
    print(f"\nen büyük sistematik fark: {worst['çift']} "
          f"{worst.ortanca_fark:+.3f} Mw ({int(worst.n)} eşleşme)")
    if df.ortanca_fark.abs().max() < 0.1:
        print("-> Tüm çiftlerde |ortanca fark| < 0.1 Mw: sistematik kayma ihmal edilebilir.")
    else:
        print("-> 0.1 Mw üstü fark var; önceliklendirmenin etkisi değerlendirilmeli.")


if __name__ == "__main__":
    main()
