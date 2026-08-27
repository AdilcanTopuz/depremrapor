"""Ö3c: hücre düzeyi farkın simülasyon gürültüsü olup olmadığının keskin sınaması.

Ö3a (katmanlı korelasyon) aralık daraltması nedeniyle kötü tasarlanmış bir
testti ve kaldı. Bu test aynı hipotezi, aralık daraltmasından etkilenmeyen ve
kesin bir sayısal öngörü taşıyan bir ölçüyle sınar.

Öngörü: fark yalnızca sonlu-örneklem gürültüsündense, bağıl saçılma
sqrt(phi/lambda) ile, yani lambda^(-1/2) ile ölçeklenir. Log-log eğim -0.5'e
yakın olmalı ve phi katmanlar arası kararlı kalmalıdır.

Bu betiğin Ö3a KALDIKTAN SONRA tanımlandığı docs/KABUL_OLCUTLERI.md'de kayıtlıdır.

Kullanım:
    python scripts/14_noise_scaling.py
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.etas_analytic import load_state  # noqa: E402
from src.models.etas_branching import expected_counts  # noqa: E402

N_SIM = 1000
EDGES = np.array([0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 300.0])


def main() -> None:
    cmp = pd.concat([pd.read_csv(f) for f in
                     glob.glob(str(ROOT / "data/processed/analytic_vs_sim/shard_*.csv"))])
    sim_all = pd.concat([pd.read_csv(f) for f in
                         glob.glob(str(ROOT / "data/processed/etas_monthly/shard_*.csv"))])
    sim_all = sim_all[(sim_all.window_days == 7) & (sim_all.target_mw == 4.5)]
    trained, cat = load_state()

    origins = sorted(cmp.origin.unique())
    picks = [origins[i] for i in np.linspace(0, len(origins) - 1, 12).astype(int)]

    frames = []
    for o in picks:
        mu_ratio = float(cmp.loc[cmp.origin == o, "mu_orani"].iloc[0])
        params = dict(trained["params"])
        params["log10_mu"] = (trained["params"]["log10_mu"]
                              + float(np.log10(mu_ratio)))
        an, _ = expected_counts(pd.Timestamp(o), 7, 4.5, cat, trained,
                                params=params)
        sim = sim_all[sim_all.ref_date == o].set_index("cell_id").rate_etas
        cells = an.index.union(sim.index)
        x = an.reindex(cells).fillna(0.0).to_numpy()
        y = sim.reindex(cells).fillna(0.0).to_numpy()
        frames.append(pd.DataFrame({"lam": N_SIM * x, "rel": (y - x) /
                                    np.maximum(x, 1e-30)}))
        print(f"  {o} işlendi", flush=True)

    d = pd.concat(frames, ignore_index=True)
    d = d[d.lam > 0]
    rows = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (d.lam >= lo) & (d.lam < hi)
        if m.sum() < 50:
            continue
        lam_mid = float(np.exp(np.log(d.lam[m]).mean()))
        sd = float(d.rel[m].std())
        rows.append({"lambda_ort": lam_mid, "n": int(m.sum()), "sacilma": sd,
                     "phi": sd ** 2 * lam_mid})
    t = pd.DataFrame(rows)
    print("\n=== Ö3c: bağıl saçılmanın lambda ile ölçeklenmesi ===")
    print(t.round(4).to_string(index=False))

    slope, intercept = np.polyfit(np.log(t.lambda_ort), np.log(t.sacilma), 1)
    phi_ratio = t.phi.max() / t.phi.min()
    print(f"\n  log-log eğim : {slope:+.4f}   (öngörü -0.5, eşik ±0.1)")
    print(f"  phi aralığı  : [{t.phi.min():.3f}, {t.phi.max():.3f}]  "
          f"oran {phi_ratio:.2f}   (eşik < 3)")
    ok = abs(slope + 0.5) <= 0.1 and phi_ratio < 3
    print(f"\n  SONUÇ: {'GEÇTİ' if ok else 'KALDI'}")
    if ok:
        print("  Bağıl saçılma lambda^(-1/2) ile ölçekleniyor ve phi kararlı:")
        print("  hücre düzeyi fark, simülasyonun sonlu-örneklem gürültüsüdür.")
    else:
        print("  Saçılma örnekleme gürültüsüyle açıklanamıyor; sistematik bir")
        print("  mekânsal ayrışma var ve operasyonel geçişten önce bulunmalıdır.")
    t.to_csv(ROOT / "data" / "processed" / "noise_scaling.csv", index=False)


if __name__ == "__main__":
    main()
