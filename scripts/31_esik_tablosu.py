"""EŞİK TABLOSU — `min_times_normal` kararının dayanağı, güncel zeminde.

Tablo `forecast_now.main()` içinde yorum olarak duruyordu ve **eski ızgara
tanımıyla** ölçülmüştü (2100 hücrelik temel modele göre; tanımsız hücreler
`inf` sayılıyordu — V40). Yeni tanımla yeniden üretilir:

    ızgara 2560 hücre · temel modelde olmayan 460 hücre TANIMSIZ -> elenir

Karar ürün kararıdır, istatistiksel eşik değildir; ama dayanağı **güncel**
olmalıdır. Tartışma bu tablo üzerinden yapılır.

Kullanım:  python scripts/31_esik_tablosu.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

ESIKLER = (1.0, 1.5, 2.0, 3.0, 5.0, 10.0)
PENCERE = 7
MW = 4.5


def main() -> None:
    from src.config import load_mc_and_b
    from src.eval import daily_backtest as db

    db.FORECAST_DIR = "etas_analytic_weekly"
    fc = db.load_forecast()
    fc = fc[(fc.window_days == PENCERE) & (fc.target_mw == MW)]
    fc["ref_date"] = pd.to_datetime(fc.ref_date, utc=True)
    base = pd.read_csv(PROC / "baseline_poisson.csv").set_index("cell_id")
    gr_b = load_mc_and_b()[1]
    scale = 10 ** (-gr_b * (MW - 5.0)) * PENCERE / 365.25

    n_baslangic = fc.ref_date.nunique()
    yearly = fc.cell_id.map(base["rate_all_m5.0_yr"])
    normal = 1.0 - np.exp(-yearly.to_numpy() * scale)
    # TANIMSIZ, SONSUZ DEĞİLDİR (V40): temel modelde olmayan hücre elenir
    with np.errstate(divide="ignore", invalid="ignore"):
        kat = np.where(normal > 1e-12, fc.p_etas.to_numpy() / normal, np.nan)
    tanimsiz = int(np.isnan(kat).sum())

    toplam_kutle = float(fc.rate_etas.sum())
    print(f"ızgara {fc.cell_id.nunique()} hücre · {n_baslangic} başlangıç · "
          f"{PENCERE} gün · M>={MW}")
    print(f"tanımsız (temel modelde yok): {tanimsiz:,} satır "
          f"({tanimsiz / len(fc) * 100:.1f}%) — ELENİR\n")

    print(f"{'eşik':>6s} {'başlangıç başına hücre':>23s} "
          f"{'olay kütlesi payı':>19s}")
    satirlar = []
    for e in ESIKLER:
        m = kat >= e
        n_hucre = int(m.sum()) / n_baslangic
        pay = float(fc.rate_etas.to_numpy()[m].sum()) / toplam_kutle
        satirlar.append({"esik": e, "hucre": n_hucre, "kutle_payi": pay})
        print(f"{e:6.1f} {n_hucre:23.0f} {pay * 100:18.1f}%")

    print("\n--- SEÇİLEN: 2,0 ---")
    s1 = next(x for x in satirlar if x["esik"] == 1.0)
    s2 = next(x for x in satirlar if x["esik"] == 2.0)
    s3 = next(x for x in satirlar if x["esik"] == 3.0)
    print(f"  1,0 -> 2,0: hücre {s1['hucre']:.0f} -> {s2['hucre']:.0f} "
          f"({(1 - s2['hucre'] / s1['hucre']) * 100:.0f}% azalma), "
          f"kütle {(s1['kutle_payi'] - s2['kutle_payi']) * 100:.1f} puan feda")
    print(f"  2,0 -> 3,0: hücre {s2['hucre']:.0f} -> {s3['hucre']:.0f} "
          f"({(1 - s3['hucre'] / s2['hucre']) * 100:.0f}% azalma), "
          f"kütle {(s2['kutle_payi'] - s3['kutle_payi']) * 100:.1f} puan feda")
    print("  Gerekçe: en verimli kesim 1,0->2,0'dadır; 3,0'a çıkmak daha az")
    print("  hücre eler ve daha çok kütle feda eder (getiri azalıyor).")
    print("\n  Bu bir ÜRÜN kararıdır, istatistiksel eşik değildir.")
    print("  Site tasarımında yeniden tartışılabilir; tartışma bu tablodan.")

    dst = PROC / "esik_tablosu.json"
    dst.write_text(json.dumps(
        {"pencere_gun": PENCERE, "hedef_mw": MW, "n_baslangic": n_baslangic,
         "izgara_hucre": int(fc.cell_id.nunique()),
         "tanimsiz_satir": tanimsiz, "secilen": 2.0, "tablo": satirlar,
         "not": ("tanımsız hücreler (temel modelde yok) ELENİR -- V40; "
                 "eski tablo bunları inf sayıyordu")},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {dst}")


if __name__ == "__main__":
    main()
