"""Analitik ETAS tahmini üretimi — simülasyonun yerine.

Simülasyon haftalık hücre oranları için yetersiz çözünürlüktedir (ölçüldü:
oranların ortancası 4.1e-04, n_sim=5000'de bile pozitiflerin %43.7'si 1/n_sim
eşiğinin altında). Analitik dallanma hesabı aynı beklentiyi Monte Carlo hatası
olmadan verir ve simülasyonu %1 içinde yeniden ürettiği doğrulanmıştır.

Her başlangıç için:
  1. `local_params` -- tetikleme parametreleri sabit, mu YEREL geçmişten
     (paketin `n_hat / (alan * süre)` kestirimi). Bu adım `_calculation_at`
     gerektirir ve maliyetin tamamına yakınını oluşturur (~2 dk).
  2. `expected_counts` -- dallanma yinelemesi (~12 sn).

Çıktı şeması simülasyon yolununkiyle aynıdır (cell_id, ref_date, window_days,
target_mw, p_etas, rate_etas) ki değerlendirme boru hattı değişmeden çalışsın.

Kullanım:
    python scripts/12_analytic_forecast.py --start 2021-01-01 --end 2024-12-26 \
        --freq 7D --days 7 --shard 0 --n-shards 8
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import TARGET_MAGS  # noqa: E402
from src.models.etas_analytic import load_state, local_params  # noqa: E402
from src.models.etas_branching import expected_counts  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--freq", default="7D")
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--mags", default=",".join(str(m) for m in TARGET_MAGS))
    ap.add_argument("--out-dir", default="etas_analytic_weekly")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    a = ap.parse_args()

    mags = [float(x) for x in a.mags.split(",")]
    origins = pd.date_range(pd.Timestamp(a.start), pd.Timestamp(a.end), freq=a.freq)
    span = f"{origins[0]:%Y-%m-%d} .. {origins[-1]:%Y-%m-%d}"
    origins = origins[a.shard::a.n_shards]
    print(f"[parça {a.shard+1}/{a.n_shards}] {len(origins)} başlangıç ({span}), "
          f"{a.days} gün, M>={mags}", flush=True)

    out_dir = ROOT / "data" / "processed" / a.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    dst = out_dir / f"shard_{a.shard}.csv"

    trained, cat = load_state()
    rows = []
    for k, o in enumerate(origins, 1):
        lp = local_params(o, cat, trained)
        for mw in mags:
            s, diag = expected_counts(o, a.days, mw, cat, trained, params=lp)
            if s.empty:
                continue
            rows.append(pd.DataFrame({
                "cell_id": s.index.astype(int), "ref_date": o,
                "window_days": int(a.days), "target_mw": mw,
                # Hücrede EN AZ BİR olay olasılığı; oran Poisson beklentisidir.
                "p_etas": 1.0 - np.exp(-s.to_numpy()),
                "rate_etas": s.to_numpy()}))
        print(f"  [{k}/{len(origins)}] {o:%Y-%m-%d}: kuşak {diag['kuşak_sayısı']}, "
              f"mu oranı {10 ** (lp['log10_mu'] - trained['params']['log10_mu']):.3f}",
              flush=True)
        # Her başlangıçtan sonra yazılır: uzun koşuda kesinti olursa iş kaybolmaz.
        pd.concat(rows, ignore_index=True).to_csv(dst, index=False)
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
