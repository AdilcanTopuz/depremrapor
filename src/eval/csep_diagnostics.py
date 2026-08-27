"""CSEP testlerinin tanılayıcı ayrıntıları.

`csep_tests` özet kuantilleri verir. Bu modül iki soruyu ayrıca yanıtlar:

1. **N-testi başarısızlığı yapısal mı, tek diziden mi?** Aylık güncellemeli bir
   sistem, ay ORTASINDA başlayan bir diziyi tanım gereği ıskalar: 6 Şubat 2023
   M7.8'ini içeren pencere 1 Şubat'ta üretilmişti. Bu bir mazeret değil,
   kurulumun ölçtüğü şeyin sınırıdır. O pencereyi çıkarıp kalan 35 pencerede
   sayı kalibrasyonunun makul olup olmadığına bakarız: eksik tahmin orada da
   sürüyorsa sorun güncelleme sıklığında değil, modelin üretkenliğindedir.

2. **S-testi ayırt edebiliyor mu?** ETAS'a 1.000, Poisson'a 0.000 verilmesi
   beklenen yöndedir ama uç değerler testin ayrım gücünün düşük olabileceğini
   de düşündürür. Gözlenen mekânsal olabilirliğin simülasyon dağılımının
   NERESİNE düştüğünü sayıyla göstermek bu şüpheyi giderir ya da doğrular.

Kullanım:
    python -m src.eval.csep_diagnostics
"""
import json

import numpy as np
import pandas as pd

from src.eval.csep_tests import (PROC, TARGET_MW, WINDOW_DAYS, background_rates,
                                 build_forecast, build_region, etas_rates,
                                 load_monthly_forecast, observed_catalog,
                                 poisson_rates)

# 6 Şubat 2023 M7.8 Kahramanmaraş dizisini içeren pencerenin başlangıcı.
SEQUENCE_ORIGIN = pd.Timestamp("2023-02-01", tz="UTC")


def _n_test(rates, region, obs, name, start, end):
    from csep.core import poisson_evaluations as pe

    f = build_forecast(rates, region, name, start, end)
    r = pe.number_test(f, obs)
    d1, d2 = (float(x) for x in r.quantile)
    return {"beklenen": float(rates.sum()), "delta1": d1, "delta2": d2,
            "red": bool(d1 < 0.025 or d2 < 0.025)}


def main() -> None:
    fc = load_monthly_forecast()
    origins = pd.DatetimeIndex(sorted(
        fc[(fc.window_days == WINDOW_DAYS) & (fc.target_mw == TARGET_MW)]
        ["ref_date"].unique()))
    cells = np.sort(pd.read_csv(PROC / "baseline_poisson.csv")["cell_id"].unique())
    region = build_region(cells)

    out = {}
    for label, sel in (("tüm pencereler", origins),
                       ("Şubat 2023 hariç", origins[origins != SEQUENCE_ORIGIN])):
        start, end = sel.min(), sel.max() + pd.Timedelta(days=WINDOW_DAYS)
        obs = observed_catalog(region, sel)
        r_e = np.maximum(etas_rates(cells, sel), background_rates(cells, sel))
        r_p = poisson_rates(cells, len(sel))

        print(f"\n=== {label} ({len(sel)} pencere) ===")
        print(f"gözlenen: {obs.event_count} olay (M>={TARGET_MW})")
        res = {"n_origins": int(len(sel)), "gözlenen": int(obs.event_count)}
        for name, rates in (("ETAS", r_e), ("Poisson", r_p)):
            t = _n_test(rates, region, obs, name, start, end)
            res[name] = t
            ratio = obs.event_count / t["beklenen"] if t["beklenen"] else float("nan")
            print(f"  {name:8s} beklenen {t['beklenen']:7.1f}  "
                  f"gözlenen/beklenen {ratio:5.2f}x  "
                  f"delta1={t['delta1']:.4f} delta2={t['delta2']:.4f}  "
                  f"-> {'RED' if t['red'] else 'uyumlu'}")
        out[label] = res

    # --- S-testi tanılaması ---
    print("\n=== S-testi ayrıntısı (tüm pencereler) ===")
    from csep.core import poisson_evaluations as pe

    start, end = origins.min(), origins.max() + pd.Timedelta(days=WINDOW_DAYS)
    obs = observed_catalog(region, origins)
    r_e = np.maximum(etas_rates(cells, origins), background_rates(cells, origins))
    r_p = poisson_rates(cells, len(origins))
    out["s_test"] = {}
    for name, rates in (("ETAS", r_e), ("Poisson", r_p)):
        f = build_forecast(rates, region, name, start, end)
        s = pe.spatial_test(f, obs, num_simulations=5000, seed=7)
        dist = np.asarray(s.test_distribution, dtype=float)
        dist = dist[np.isfinite(dist)]
        o = float(s.observed_statistic)
        # Kuantil skoru: simülasyonların yüzde kaçı gözlenenin ALTINDA.
        q = float((dist < o).mean())
        pcts = np.percentile(dist, [1, 5, 25, 50, 75, 95, 99])
        print(f"  {name}: gözlenen mekânsal olabilirlik {o:.2f}")
        print(f"    simülasyon dağılımı  %1 {pcts[0]:.2f} | %5 {pcts[1]:.2f} | "
              f"ortanca {pcts[3]:.2f} | %95 {pcts[5]:.2f} | %99 {pcts[6]:.2f}")
        print(f"    kuantil skoru = {q:.4f}   (tek yönlü test: q < 0.05 ise RED)"
              f"  -> {'RED' if q < 0.05 else 'uyumlu'}")
        # Gözlenenin dağılımdan kaç standart sapma uzakta olduğu, ayrım gücü
        # hakkında kuantilden daha bilgilendiricidir: kuantil 0 ya da 1'e
        # dayandığında fark 0.1 sigma da olabilir 10 sigma da.
        z = (o - dist.mean()) / dist.std(ddof=1)
        print(f"    z = {z:+.2f} standart sapma")
        out["s_test"][name] = {"gözlenen": o, "kuantil": q, "z": float(z),
                               "dağılım_ortanca": float(pcts[3]),
                               "dağılım_p5": float(pcts[1]),
                               "dağılım_p95": float(pcts[5])}

    dst = PROC / "csep_diagnostics.json"
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {dst}")


if __name__ == "__main__":
    main()
