"""ÜRÜN KAPISI ÖLÇÜMÜ — son kapanmış değerlendirme üzerinden kalibrasyon.

Kapı, yayın günü ölçülemez: pencere henüz kapanmamıştır. Bu betik, son
kapanmış değerlendirme döneminden gözlenen/beklenen oranını üretir ve
`kapi_olcumu.json` yazar. Hat, yayın öncesi bunu okur.

Ölçüm künyelidir: hangi dönem, hangi pencere, hangi tablo, hangi tarih.

Kullanım:  python scripts/32_kapi_olcumu.py
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

TABLO = "etas_analytic_weekly"
PENCERE = 7
MW = 4.5


def main() -> None:
    from src.eval import daily_backtest as db

    db.FORECAST_DIR = TABLO
    t = db.build_table(PENCERE, MW, quiet=True)
    n = int(t.y.sum())
    kayit = {
        "olcum_tarihi": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "tablo": TABLO, "pencere_gun": PENCERE, "hedef_mw": MW,
        "donem": f"{t.ref_date.min():%Y-%m-%d} .. {t.ref_date.max():%Y-%m-%d}",
        "n_satir": len(t), "gozlenen": n,
        "modeller": {},
    }
    print(f"dönem {kayit['donem']} · {len(t):,} satır · {n} olay\n")
    print(f"{'model':10s} {'beklenen':>10s} {'oran':>7s}  kapı")
    for ad, sut in (("ETAS", "rate_etas"), ("Poisson", "rate_pois")):
        bek = float(t[sut].sum())
        kayit["modeller"][ad] = {"gozlenen": n, "beklenen": bek}
        oran = n / bek
        print(f"{ad:10s} {bek:10.1f} {oran:7.3f}  "
              f"{'GEÇER' if 0.80 <= oran <= 1.25 else 'GEÇMEZ'}")

    dst = PROC / "kapi_olcumu.json"
    dst.write_text(json.dumps(kayit, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n-> {dst}")


if __name__ == "__main__":
    main()
