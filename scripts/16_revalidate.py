"""Ö1, Ö3a, Ö3b, Ö3c'nin DÜZELTİLMİŞ kodla yeniden koşulması.

Gerekçe: bu ölçütler kaynak konumu düzeltmesinden ÖNCEKİ kodla koşulmuştu.
"Geçti" damgası güncel kodla atılmış olmalıdır; aksi hâlde tablo, artık var
olmayan bir sürümün sonucunu raporlar.

`local_params` yeniden hesaplanmaz (başlangıç başına ~2 dk): kaynak konumu
düzeltmesi mu kestirimini etkilemez, bu yüzden önceki koşunun kaydettiği
mu oranları kullanılır.

Kullanım:
    python scripts/16_revalidate.py
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
STRATA = [(10, np.inf, "> 10", 0.95), (1, 10, "1 - 10", 0.85),
          (0, 1, "< 1", None)]
EDGES = np.array([0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 30.0, 300.0])


def main() -> None:
    cmp = pd.concat([pd.read_csv(f) for f in
                     glob.glob(str(ROOT / "data/processed/analytic_vs_sim/shard_*.csv"))])
    sim_all = pd.concat([pd.read_csv(f) for f in
                         glob.glob(str(ROOT / "data/processed/etas_monthly/shard_*.csv"))])
    sim_all = sim_all[(sim_all.window_days == 7) & (sim_all.target_mw == 4.5)]
    trained, cat = load_state()

    rows, strat, agg, noise = [], [], [], []
    for k, o in enumerate(sorted(cmp.origin.unique()), 1):
        mu_ratio = float(cmp.loc[cmp.origin == o, "mu_orani"].iloc[0])
        params = dict(trained["params"])
        params["log10_mu"] += float(np.log10(mu_ratio))
        an, _ = expected_counts(pd.Timestamp(o), 7, 4.5, cat, trained,
                                params=params)
        sim = sim_all[sim_all.ref_date == o].set_index("cell_id").rate_etas
        cells = an.index.union(sim.index)
        x = an.reindex(cells).fillna(0.0)
        y = sim.reindex(cells).fillna(0.0)
        xv, yv = x.to_numpy(), y.to_numpy()

        rows.append({"origin": o, "analitik": xv.sum(), "simulasyon": yv.sum(),
                     "sim_an": yv.sum() / xv.sum(),
                     "r": float(np.corrcoef(xv, yv)[0, 1])})

        exp_syn = N_SIM * x
        for lo, hi, label, _t in STRATA:
            m = (exp_syn >= lo) & (exp_syn < hi)
            if m.sum() >= 10:
                strat.append({"katman": label, "n": int(m.sum()),
                              "r": float(np.corrcoef(x[m], y[m])[0, 1])})

        idx = np.asarray(cells)
        blk = (idx // 1000 // 2) * 1000 + (idx % 1000) // 2
        gg = pd.DataFrame({"blk": blk, "x": xv, "y": yv}).groupby("blk").sum()
        agg.append({"origin": o, "r_hucre": rows[-1]["r"],
                    "r_2x2": float(np.corrcoef(gg.x, gg.y)[0, 1])})

        noise.append(pd.DataFrame({"lam": N_SIM * xv,
                                   "rel": (yv - xv) / np.maximum(xv, 1e-30)}))
        print(f"  [{k}] {o}", flush=True)

    d = pd.DataFrame(rows)
    print("\n=== Ö1 (yeniden) ===")
    from scipy import stats
    t = stats.ttest_1samp(np.log(d.sim_an), 0.0)
    print(f"  n = {len(d)}   ortanca oran {d.sim_an.median():.4f}   "
          f"aralık [{d.sim_an.min():.3f}, {d.sim_an.max():.3f}]")
    print(f"  log(oran) t-testi p = {t.pvalue:.4f}")
    inband = float(((d.sim_an >= 0.80) & (d.sim_an <= 1.25)).mean())
    o1 = (abs(d.sim_an.median() - 1) <= 0.03 and t.pvalue > 0.05
          and inband >= 0.90)
    print(f"  [0.80,1.25] içinde: %{100*inband:.1f}")
    print(f"  hücre korelasyonu ortanca: {d.r.median():.4f}")
    print(f"  -> Ö1 {'GEÇTİ' if o1 else 'KALDI'}")

    s = pd.DataFrame(strat).groupby("katman").r.median()
    print("\n=== Ö3a (yeniden) ===")
    o3a = True
    for lo, hi, lab, thr in STRATA:
        if lab not in s.index:
            continue
        r = s[lab]
        good = (r > thr) if thr is not None else (r < 0.80)
        o3a &= good
        print(f"  {lab:8s}: r = {r:.4f}   {'GEÇTİ' if good else 'KALDI'}")
    print(f"  -> Ö3a {'GEÇTİ' if o3a else 'KALDI'}")

    a = pd.DataFrame(agg)
    gain = float((a.r_2x2 - a.r_hucre).median())
    o3b = gain >= 0.04
    print(f"\n=== Ö3b (yeniden) ===\n  artış {gain:+.4f}  "
          f"-> {'GEÇTİ' if o3b else 'KALDI'}")

    nd = pd.concat(noise, ignore_index=True)
    nd = nd[nd.lam > 0]
    tt = []
    for lo, hi in zip(EDGES[:-1], EDGES[1:]):
        m = (nd.lam >= lo) & (nd.lam < hi)
        if m.sum() < 50:
            continue
        lam = float(np.exp(np.log(nd.lam[m]).mean()))
        sd = float(nd.rel[m].std())
        tt.append({"lambda": lam, "n": int(m.sum()), "sacilma": sd,
                   "phi": sd ** 2 * lam})
    tf = pd.DataFrame(tt)
    print("\n=== Ö3c (yeniden) ===")
    print(tf.round(4).to_string(index=False))
    slope = float(np.polyfit(np.log(tf["lambda"]), np.log(tf.sacilma), 1)[0])
    ratio = float(tf.phi.max() / tf.phi.min())
    o3c = abs(slope + 0.5) <= 0.1 and ratio < 3
    print(f"  eğim {slope:+.4f} (eşik -0.5±0.1)   phi oranı {ratio:.2f} "
          f"(eşik <3)   -> {'GEÇTİ' if o3c else 'KALDI'}")

    out = ROOT / "data" / "processed"
    d.to_csv(out / "revalidation_o1.csv", index=False)
    tf.to_csv(out / "revalidation_o3c.csv", index=False)
    print("\n=== ÖZET ===")
    for name, ok in (("Ö1", o1), ("Ö3a", o3a), ("Ö3b", o3b), ("Ö3c", o3c)):
        print(f"  {name}: {'GEÇTİ' if ok else 'KALDI'}")


if __name__ == "__main__":
    main()
