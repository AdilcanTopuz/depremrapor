"""Analitik yöntem ile simülasyonun toplu karşılaştırması (kontrol 5).

Tek başlangıçtan hüküm çıkmaz. Bu betik, aylık simülasyon arşivindeki tüm
başlangıçlarda analitik hesabı yeniden üretir ve iki yöntemi hem TOPLAM beklenen
sayı hem HÜCRE BAZLI korelasyon olarak karşılaştırır.

Beklenti: oran 1'e yakın ve rejimden BAĞIMSIZ olmalı. Sistematik sapma (örneğin
24 başlangıcın hepsinde aynı yönde) varyans değil YANLILIK demektir ve kaynağı
aranmalıdır -- nitekim bu şekilde üç ayrı hata bulundu (yerel mu, büyüklük
yuvarlaması, çekirdek kütlesi).

Her başlangıç `_calculation_at` gerektirir (~2 dk); parçalanabilir.

Kullanım:
    python scripts/11_compare_analytic_sim.py --shard 0 --n-shards 8
"""
import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.etas_analytic import load_state, local_params  # noqa: E402
from src.models.etas_branching import expected_counts  # noqa: E402

OUT = ROOT / "data" / "processed" / "analytic_vs_sim"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    a = ap.parse_args()

    d = pd.concat([pd.read_csv(f) for f in
                   glob.glob(str(ROOT / "data/processed/etas_monthly/shard_*.csv"))])
    d = d[(d.window_days == a.days) & (d.target_mw == a.mw)]
    origins = sorted(d.ref_date.unique())[a.shard::a.n_shards]
    print(f"[parça {a.shard+1}/{a.n_shards}] {len(origins)} başlangıç", flush=True)

    trained, cat = load_state()
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for k, o in enumerate(origins, 1):
        ts = pd.Timestamp(o)
        lp = local_params(ts, cat, trained)
        an, diag = expected_counts(ts, a.days, a.mw, cat, trained, params=lp)
        sim = d[d.ref_date == o].set_index("cell_id").rate_etas
        cells = sim.index.union(an.index)
        x = an.reindex(cells).fillna(0.0).to_numpy()
        y = sim.reindex(cells).fillna(0.0).to_numpy()
        rows.append({
            "origin": str(o)[:10], "analitik": float(x.sum()),
            "simulasyon": float(y.sum()),
            "sim_an": float(y.sum() / x.sum()) if x.sum() else np.nan,
            "r": float(np.corrcoef(x, y)[0, 1]) if len(cells) > 2 else np.nan,
            "mu_orani": float(10 ** (lp["log10_mu"]
                                     - trained["params"]["log10_mu"])),
            "kusak": diag["kuşak_sayısı"],
        })
        print(f"  [{k}/{len(origins)}] {rows[-1]['origin']}: "
              f"an {rows[-1]['analitik']:.4f} sim {rows[-1]['simulasyon']:.4f} "
              f"oran {rows[-1]['sim_an']:.4f} r {rows[-1]['r']:.3f}", flush=True)

    pd.DataFrame(rows).to_csv(OUT / f"shard_{a.shard}.csv", index=False)
    print(f"-> {OUT / f'shard_{a.shard}.csv'}")


if __name__ == "__main__":
    main()
