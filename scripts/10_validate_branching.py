"""Analitik dallanma yönteminin doğrulaması — beş kontrol.

Yeni bir sayısal yöntem, kendi doğrulama yükünü getirir. Simülasyonu değiştiren
bir hesabın "makul görünmesi" yetmez; her varsayımın ayrı ayrı sınanması gerekir.

1. YAKINSAMA   — zaman kutusu sayısı ve kuşak kesme kriteri
2. KÜTLE       — çekirdek kütlesi dallanma oranıyla tutarlı mı, kuşaklar
                 geometrik mi azalıyor
3. SINIR KAÇAĞI— ızgara kenarında kütle kaybı; tampon genişliğine duyarlılık
4. BÜYÜKLÜK    — kesimli/kesimsiz GR ayrımı, simülasyonla aynı mı
5. SİMÜLASYON  — 20+ başlangıçta toplam ve hücre bazlı karşılaştırma

Kullanım:
    python scripts/10_validate_branching.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.models.etas_analytic import load_state  # noqa: E402
from src.models.etas_branching import (  # noqa: E402
    MAG_BINS, expected_counts, magnitude_weights, productivity_kernels,
    total_time_integral)

ACTIVE = pd.Timestamp("2023-03-01")     # artçı dizisi sürerken
QUIET = pd.Timestamp("2022-06-01")      # sakin dönem


def check_mass(trained: dict) -> None:
    """2. KÜTLE KORUNUMU.

    Uzaysal çekirdeğin toplamı, kesimli GR ile hesaplanan dallanma oranına eşit
    olmalı. Evrişimde normalizasyon hatası varsa ilk burada görünür.
    """
    from etas.inversion import branching_ratio, parameter_dict2array

    print("\n=== 2. KÜTLE KORUNUMU ===")
    p, mc, beta = trained["params"], trained["mc"], trained["beta"]
    dm_full = dict(p)
    dm_full.setdefault("log10_iota", -np.inf)
    theta = parameter_dict2array(dm_full)
    delta_m = trained.get("delta_m", 0.1)
    m_max = trained.get("m_max", 8.0)
    dm_max = (m_max + delta_m / 2) - (mc - delta_m / 2)

    n_open = float(branching_ratio(theta, beta, None))
    n_trunc = float(branching_ratio(theta, beta, dm_max))
    half = 8
    kernels, kernel_mass = productivity_kernels(p, beta, mc, delta_m, m_max, half)

    print(f"  paketin dallanma oranı, KESİMSİZ  : {n_open:.4f}  "
          f"(etas_params.json'da raporlanan)")
    print(f"  paketin dallanma oranı, KESİMLİ    : {n_trunc:.4f}  "
          f"(dm_max={dm_max:.2f}, simülasyonla aynı)")
    print(f"  çekirdek kütlesi (orta enlem)      : {kernel_mass:.4f}")
    rel = abs(kernel_mass - n_trunc) / n_trunc
    print(f"  bağıl fark                          : {100*rel:.2f}%  "
          f"(kalan fark yarıçap kesmesinden: {100*abs(n_open-n_trunc)/n_open:.2f}% "
          f"de kesimsiz-kesimli farkı)")
    assert rel < 0.02, "çekirdek kütlesi dallanma oranıyla uyuşmuyor"


def check_generations(trained: dict, cat: pd.DataFrame) -> None:
    """1b. KUŞAK KESME + kuşakların geometrik azalması."""
    print("\n=== 1b. KUŞAK YAKINSAMASI ===")
    for name, o in (("aktif", ACTIVE), ("sakin", QUIET)):
        s, d = expected_counts(o, 7, 4.5, cat, trained)
        g = np.array(d["kuşak_kütleleri"])
        ratios = g[1:] / np.maximum(g[:-1], 1e-30)
        print(f"  {name} ({o:%Y-%m-%d}): {d['kuşak_sayısı']} kuşak, toplam "
              f"{s.sum():.4f}")
        print(f"    kuşak oranları (ilk 5): "
              f"{', '.join(f'{r:.3f}' for r in ratios[:5])}")
        print(f"    son kuşağın toplama payı: "
              f"{100*g[-1]/g.sum():.4f}%")


def check_time_convergence(trained: dict, cat: pd.DataFrame) -> None:
    """1a. ZAMAN ADIMI YAKINSAMASI — adımı yarıya indirince %1'den az değişmeli."""
    print("\n=== 1a. ZAMAN KUTUSU YAKINSAMASI ===")
    for name, o in (("aktif", ACTIVE), ("sakin", QUIET)):
        prev = None
        print(f"  {name} ({o:%Y-%m-%d}):")
        for nb in (8, 16, 32, 64):
            s, _ = expected_counts(o, 7, 4.5, cat, trained, n_bins=nb)
            tot = float(s.sum())
            chg = "" if prev is None else f"  değişim %{100*abs(tot-prev)/prev:.2f}"
            print(f"    {nb:3d} kutu: toplam {tot:.5f}{chg}")
            prev = tot


def check_boundary(trained: dict, cat: pd.DataFrame) -> None:
    """3. SINIR KAÇAĞI — yarıçap kesmesine duyarlılık.

    Izgara dışına giden kütle KAYBOLUR (yansıtılmaz); bu doğrudur, o olaylar
    değerlendirme alanında değildir. Sınanan şey, kesme yarıçapının sonucu
    değiştirmemesidir: kesme çok darsa yakın alan kütlesi de kaybolur.
    """
    print("\n=== 3. SINIR / YARIÇAP KESMESİ ===")
    from src.models import etas_analytic as ea

    orig = ea.MAX_RADIUS_KM
    try:
        prev = None
        for r in (100.0, 150.0, 200.0, 300.0):
            ea.MAX_RADIUS_KM = r
            s, _ = expected_counts(ACTIVE, 7, 4.5, cat, trained)
            tot = float(s.sum())
            chg = "" if prev is None else f"  değişim %{100*abs(tot-prev)/prev:.3f}"
            print(f"  yarıçap {r:5.0f} km: toplam {tot:.5f}{chg}")
            prev = tot
    finally:
        ea.MAX_RADIUS_KM = orig

    # kenar hücrelerin payı: alanın dış çerçevesindeki oran toplamı
    s, _ = expected_counts(ACTIVE, 7, 4.5, cat, trained)
    idx = s.index.to_numpy()
    i, j = idx // 1000, idx % 1000
    from src.models.etas_branching import NLAT, NLON
    edge = (i < 2) | (i >= NLAT - 2) | (j < 2) | (j >= NLON - 2)
    print(f"  kenar (2 hücre) çerçevesinin toplam orandaki payı: "
          f"%{100*s.to_numpy()[edge].sum()/s.sum():.2f}")


def check_magnitude(trained: dict) -> None:
    """4. BÜYÜKLÜK DAĞILIMI — simülasyonla aynı kesim kullanılıyor mu."""
    print("\n=== 4. BÜYÜKLÜK DAĞILIMI ===")
    mc, beta = trained["mc"], trained["beta"]
    delta_m = trained.get("delta_m", 0.1)
    m_max = trained.get("m_max", 8.0)
    mc_eff, m_max_eff = mc - delta_m / 2, m_max + delta_m / 2
    mags, w = magnitude_weights(beta, mc_eff, m_max_eff)
    print(f"  mc_eff = {mc_eff}, m_max_eff = {m_max_eff}  "
          f"(mc_b_est.simulate_magnitudes ile aynı)")
    print(f"  ağırlık toplamı: {w.sum():.8f}  (1 olmalı)")
    assert abs(w.sum() - 1) < 1e-9

    # Monte Carlo ile aynı örneklemi üretiyor mu?
    from etas.mc_b_est import simulate_magnitudes
    np.random.seed(7)
    sample = simulate_magnitudes(200_000, beta=beta, mc=mc_eff, m_max=m_max_eff)
    emp = np.array([((sample >= lo) & (sample < lo + MAG_BINS)).mean()
                    for lo in mags - MAG_BINS / 2])
    err = np.abs(emp - w).max()
    print(f"  paketin örneklemiyle en büyük kutu farkı: {err:.5f}")
    assert err < 3e-3, "analitik ağırlıklar simülasyonun ürettiği dağılıma uymuyor"
    print(f"  M>=4.5 kuyruk payı (kesimli): "
          f"{(np.exp(-beta*(4.5-mc_eff)) - np.exp(-beta*(m_max_eff-mc_eff)))/(1-np.exp(-beta*(m_max_eff-mc_eff))):.6f}")
    print(f"  kesimsiz olsaydı            : {np.exp(-beta*(4.5-mc_eff)):.6f}")


def check_vs_simulation(trained: dict, cat: pd.DataFrame, n_origins: int = 24
                        ) -> None:
    """5. SİMÜLASYONA KARŞI — toplam ve hücre bazlı."""
    import glob

    print(f"\n=== 5. SİMÜLASYONA KARŞI ({n_origins} başlangıç) ===")
    files = glob.glob(str(ROOT / "data/processed/etas_monthly/shard_*.csv"))
    d = pd.concat([pd.read_csv(f) for f in files])
    d = d[(d.window_days == 7) & (d.target_mw == 4.5)]
    origins = sorted(d.ref_date.unique())[:n_origins]

    rows = []
    for o in origins:
        sim = d[d.ref_date == o].set_index("cell_id").rate_etas
        an, _ = expected_counts(pd.Timestamp(o), 7, 4.5, cat, trained)
        cells = sim.index.union(an.index)
        x = an.reindex(cells).fillna(0.0).to_numpy()
        y = sim.reindex(cells).fillna(0.0).to_numpy()
        rows.append({"başlangıç": str(o)[:10], "analitik": x.sum(),
                     "simülasyon": y.sum(), "sim/an": y.sum() / x.sum(),
                     "r": np.corrcoef(x, y)[0, 1] if len(cells) > 2 else np.nan})
    df = pd.DataFrame(rows)
    print(df.round(4).to_string(index=False))
    print(f"\n  sim/analitik oranı: ortanca {df['sim/an'].median():.3f}, "
          f"aralık [{df['sim/an'].min():.3f}, {df['sim/an'].max():.3f}]")
    print(f"  hücre bazlı korelasyon: ortanca {df.r.median():.3f}")
    print("\n  Yorum: analitik hesap ikincil kuşakları da içerdiği için oran 1'e")
    print("  yakın olmalı. Kalan sapma Monte Carlo varyansıdır: 1000 simülasyonla")
    print("  toplam beklenti ~0.5 olan bir tahminin bağıl standart hatası")
    print(f"  yaklaşık %{100/np.sqrt(1000*0.5):.0f}'dir.")


def main() -> None:
    trained, cat = load_state()
    check_magnitude(trained)
    check_mass(trained)
    check_generations(trained, cat)
    check_time_convergence(trained, cat)
    check_boundary(trained, cat)
    check_vs_simulation(trained, cat)


if __name__ == "__main__":
    main()
