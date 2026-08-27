"""Ö3: "hücre düzeyinde ayrışan taraf simülasyondur" iddiasının sınanması.

Analitik ile simülasyon toplamda %1 içinde buluşuyor ama hücre bazlı korelasyon
~0.90'da kalıyor. İddia: fark simülasyonun hücre başına gürültüsünden geliyor,
çünkü 1000 simülasyonda bir hücrede beklenen sentetik olay sayısı çoğu yerde
1'in altında.

Bu ŞU AN BİR HİPOTEZDİR. Kanıta çevirmek için iki test (bkz.
docs/KABUL_OLCUTLERI.md, Ö3):

  Ö3a  Hücreler, simülasyonun o hücrede beklediği sentetik olay sayısına göre
       katmanlanır. Gürültü simülasyondansa, beklenti arttıkça korelasyon
       1'e yaklaşmalıdır.
  Ö3b  Komşu hücreler 2x2 toplanır. Toplama gürültüyü ortalar; korelasyon
       belirgin biçimde yükselmelidir.

Beklenen yönde çıkmazlarsa hücre düzeyi ayrışmanın BAŞKA bir kaynağı vardır ve
operasyonel geçişten önce bulunmalıdır.

`local_params` yeniden hesaplanmaz: karşılaştırma çıktısındaki mu oranından geri
kurulur, böylece pahalı `_calculation_at` adımı atlanır.

Kullanım:
    python scripts/13_stratified_correlation.py
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.etas_analytic import load_state  # noqa: E402
from src.models.etas_branching import NLON, expected_counts  # noqa: E402

N_SIM = 1000          # aylık simülasyon koşusunda kullanılan değer
STRATA = [(10, np.inf, "> 10", 0.95), (1, 10, "1 - 10", 0.85),
          (0, 1, "< 1", None)]


def main() -> None:
    cmp = pd.concat([pd.read_csv(f) for f in
                     glob.glob(str(ROOT / "data/processed/analytic_vs_sim/shard_*.csv"))])
    sim_all = pd.concat([pd.read_csv(f) for f in
                         glob.glob(str(ROOT / "data/processed/etas_monthly/shard_*.csv"))])
    sim_all = sim_all[(sim_all.window_days == 7) & (sim_all.target_mw == 4.5)]

    # Rejim çeşitliliği için eşit aralıklı seçim
    origins = sorted(cmp.origin.unique())
    picks = [origins[i] for i in np.linspace(0, len(origins) - 1, 8).astype(int)]
    trained, cat = load_state()

    rows, agg_rows = [], []
    for o in picks:
        mu_ratio = float(cmp.loc[cmp.origin == o, "mu_orani"].iloc[0])
        params = dict(trained["params"])
        params["log10_mu"] = (trained["params"]["log10_mu"]
                              + float(np.log10(mu_ratio)))
        an, _ = expected_counts(pd.Timestamp(o), 7, 4.5, cat, trained,
                                params=params)
        sim = sim_all[sim_all.ref_date == o].set_index("cell_id").rate_etas

        cells = an.index.union(sim.index)
        x = an.reindex(cells).fillna(0.0)
        y = sim.reindex(cells).fillna(0.0)
        exp_syn = N_SIM * x                     # beklenen sentetik olay sayısı

        for lo, hi, label, _thr in STRATA:
            m = (exp_syn >= lo) & (exp_syn < hi)
            if m.sum() < 10:
                continue
            r = np.corrcoef(x[m], y[m])[0, 1]
            rows.append({"origin": o, "katman": label, "n_hücre": int(m.sum()),
                         "r": float(r)})

        # Ö3b: 2x2 toplama
        idx = np.asarray(cells)
        blk = (idx // 1000 // 2) * 1000 + (idx % 1000) // 2
        g = pd.DataFrame({"blk": blk, "x": x.to_numpy(), "y": y.to_numpy()})
        gg = g.groupby("blk").sum()
        agg_rows.append({"origin": o,
                         "r_hücre": float(np.corrcoef(x, y)[0, 1]),
                         "r_2x2": float(np.corrcoef(gg.x, gg.y)[0, 1]),
                         "n_hücre": len(cells), "n_blok": len(gg)})
        print(f"  {o} işlendi", flush=True)

    df = pd.DataFrame(rows)
    print("\n=== Ö3a: beklenen sentetik olay sayısına göre katmanlı korelasyon ===")
    s = df.groupby("katman").agg(n_origin=("r", "size"),
                                 ortanca_r=("r", "median"),
                                 ort_hücre=("n_hücre", "mean"))
    order = [lab for _, _, lab, _ in STRATA if lab in s.index]
    print(s.loc[order].round(4).to_string())
    print("\n  eşikler (KABUL_OLCUTLERI Ö3a): >10 -> r>0.95, 1-10 -> r>0.85, "
          "<1 -> r<0.80")
    ok_a = True
    for lo, hi, lab, thr in STRATA:
        if lab not in s.index:
            continue
        r = s.loc[lab, "ortanca_r"]
        if thr is not None:
            good = r > thr
            print(f"  {lab:8s}: r = {r:.4f}  {'GEÇTİ' if good else 'KALDI'}")
        else:
            good = r < 0.80
            print(f"  {lab:8s}: r = {r:.4f}  "
                  f"{'GEÇTİ (belirgin düşük)' if good else 'KALDI'}")
        ok_a &= good

    a = pd.DataFrame(agg_rows)
    print("\n=== Ö3b: 2x2 uzaysal toplama ===")
    print(a.round(4).to_string(index=False))
    gain = (a.r_2x2 - a.r_hücre).median()
    ok_b = gain >= 0.04
    print(f"\n  korelasyon artışı (ortanca): {gain:+.4f}   "
          f"eşik >= +0.04  -> {'GEÇTİ' if ok_b else 'KALDI'}")

    print("\n=== SONUÇ ===")
    if ok_a and ok_b:
        print("  Her iki test de beklenen yönde: hücre düzeyi ayrışmanın kaynağı")
        print("  simülasyonun sonlu-örneklem gürültüsüdür. 'Kusur değil, kanıt'")
        print("  ifadesi raporda kalabilir.")
    else:
        print("  EN AZ BİR TEST KALDI. Hücre düzeyi ayrışmanın başka bir kaynağı")
        print("  var; operasyonel geçişten ÖNCE bulunmalıdır.")

    out = ROOT / "data" / "processed" / "stratified_correlation.csv"
    df.to_csv(out, index=False)
    a.to_csv(out.with_name("aggregation_correlation.csv"), index=False)
    print(f"\n-> {out}")


if __name__ == "__main__":
    main()
