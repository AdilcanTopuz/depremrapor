"""Mekanizma testi: hücre düzeyi ayrışmanın kaynağı hücre-merkezi yaklaşıklığı mı?

Analitik yöntem, uzaysal çekirdeği evrişime indirgemek için kaynak olayları
KENDİ HÜCRE MERKEZLERİNE yerleştiriyor. Simülasyon ise artçıları kaynağın gerçek
koordinatına göre üretiyor. Hücre ~25 km, çekirdek ölçeği sqrt(D) ~ 11 km; yani
yaklaşıklık hücre boyutuyla karşılaştırılabilir büyüklükte ve hücre düzeyinde
kütleyi farklı dağıtması beklenir.

Bu betik iddiayı DOĞRUDAN sınar: kaynaklar gerçek konumlarına yerleştirildiğinde
simülasyonla korelasyon yükseliyor mu?

YÖNTEM. Çekirdek yalnızca yakın hücrelerde sivridir; uzakta hücre-merkezi
yaklaşıklığı zararsızdır (mesafe >> hücre boyutu). Bu yüzden yakın alan
(5x5 hücre) kaynağın GERÇEK konumuna göre yeniden hesaplanır, uzak alan
önbelleklenmiş tablodan gelir. Kütle sapması raporlanır.

Bu bir istatistiksel ölçüt değil, mekanizma sınamasıdır: hipotez doğruysa
korelasyon yükselir, yanlışsa yükselmez ve ayrışmanın kaynağı hâlâ bilinmiyordur.

Kullanım:
    python scripts/15_exact_source_position.py
"""
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.config import DEG_KM, LAT0, LON0, STEP  # noqa: E402
from src.models.etas_analytic import load_state, spatial_table  # noqa: E402
from src.models.etas_branching import (  # noqa: E402
    MAG_BINS, NLAT, NLON, _spatial_spread, _time_transition, expected_counts,
    productivity_kernels, time_bins, time_integral)

NEAR = 2          # yakın alan yarıçapı (hücre)
GAUSS = 20
N_SIM = 1000


def exact_near_field(m, lat_s, lon_s, params, mc):
    """Kaynağın GERÇEK konumuna göre yakın alan (2*NEAR+1)^2 payları."""
    d = 10 ** params["log10_d"]
    rho, gamma = params["rho"], params["gamma"]
    D = d * np.exp(gamma * (m - mc))
    norm = np.pi / (rho * D ** rho)

    i_src = int(np.floor((lat_s - LAT0) / STEP))
    j_src = int(np.floor((lon_s - LON0) / STEP))
    dy_km = STEP * DEG_KM
    dx_km = STEP * DEG_KM * np.cos(np.radians(lat_s))

    gx, gw = np.polynomial.legendre.leggauss(GAUSS)
    u, wu = 0.5 * (gx + 1.0), 0.5 * gw

    offs = np.arange(-NEAR, NEAR + 1)
    # kaynağın hücre içindeki konumu (0..1)
    fy = (lat_s - (LAT0 + i_src * STEP)) / STEP
    fx = (lon_s - (LON0 + j_src * STEP)) / STEP

    cy = (offs[:, None, None, None] + u[None, None, :, None] - fy) * dy_km
    cx = (offs[None, :, None, None] + u[None, None, None, :] - fx) * dx_km
    dens = 1.0 / np.power(cy ** 2 + cx ** 2 + D, 1.0 + rho)
    w = (wu[None, None, :, None] * wu[None, None, None, :]) * dx_km * dy_km
    return (dens * w).sum(axis=(2, 3)) / norm, i_src, j_src


def seed_exact(origin, edges, cat, trained, half, params, history_years=5.0):
    """Tohum -- yakın alan GERÇEK konumla, uzak alan önbellekli tabloyla."""
    mc = trained["mc"]
    delta_m = trained.get("delta_m", 0.1)
    mc_eff = mc - delta_m / 2
    k0 = 10 ** params["log10_k0"]
    d = 10 ** params["log10_d"]
    a, gamma, rho = params["a"], params["gamma"], params["rho"]
    K = len(edges) - 1
    out = np.zeros((K, NLAT, NLON))

    mu = 10 ** params["log10_mu"]
    widths = np.diff(edges)
    for i in range(NLAT):
        lat_c = LAT0 + (i + 0.5) * STEP
        area = (STEP * DEG_KM) * (STEP * DEG_KM * np.cos(np.radians(lat_c)))
        out[:, i, :] += (mu * area * widths)[:, None]

    hist_start = origin - pd.Timedelta(days=history_years * 365.25)
    src = cat[(cat.time >= hist_start) & (cat.time < origin)]
    src = src[src.magnitude >= mc]
    if not len(src):
        return out, 0.0

    age = (origin - src.time).dt.total_seconds().to_numpy() / 86400.0
    m = src.magnitude.to_numpy()
    dm = m - mc_eff
    amp = (k0 * np.exp(a * dm) * (np.pi / rho)
           * np.power(d * np.exp(gamma * dm), -rho))
    lats, lons = src.latitude.to_numpy(), src.longitude.to_numpy()

    cache: dict[tuple[int, int], np.ndarray] = {}
    mb = np.round(m / MAG_BINS).astype(int)
    mass_dev = []
    for k in range(len(src)):
        tint = time_integral(age[k] + edges[:-1], age[k] + edges[1:], params)
        if tint.sum() <= 0:
            continue
        i_src = int(np.floor((lats[k] - LAT0) / STEP))
        j_src = int(np.floor((lons[k] - LON0) / STEP))
        if not (0 <= i_src < NLAT and 0 <= j_src < NLON):
            continue
        key = (int(mb[k]), i_src)
        tab = cache.get(key)
        if tab is None:
            tab = spatial_table(mb[k] * MAG_BINS, LAT0 + (i_src + 0.5) * STEP,
                                params, mc_eff, half_width=half)
            cache[key] = tab
        tab = tab.copy()
        near, _, _ = exact_near_field(mb[k] * MAG_BINS, lats[k], lons[k],
                                      params, mc_eff)
        c = half
        mass_dev.append(near.sum() - tab[c - NEAR:c + NEAR + 1,
                                         c - NEAR:c + NEAR + 1].sum())
        tab[c - NEAR:c + NEAR + 1, c - NEAR:c + NEAR + 1] = near

        i0, j0 = i_src - half, j_src - half
        ia, ib = max(0, i0), min(NLAT, i0 + 2 * half + 1)
        ja, jb = max(0, j0), min(NLON, j0 + 2 * half + 1)
        if ia >= ib or ja >= jb:
            continue
        block = amp[k] * tab[ia - i0:ib - i0, ja - j0:jb - j0]
        out[:, ia:ib, ja:jb] += tint[:, None, None] * block[None, :, :]
    return out, float(np.mean(mass_dev)) if mass_dev else 0.0


def run_exact(origin, days, target_mw, cat, trained, params, n_bins=32):
    """expected_counts ile aynı, ama tohum gerçek konumlarla."""
    beta = trained["beta"]
    mc = trained["mc"]
    delta_m = trained.get("delta_m", 0.1)
    m_max = trained.get("m_max", 8.0)
    import src.models.etas_analytic as _ea
    half = int(np.ceil(_ea.MAX_RADIUS_KM / (STEP * DEG_KM)))

    edges = time_bins(days, params, n_bins)
    q = _time_transition(edges, params)
    kernels, _ = productivity_kernels(params, beta, mc, delta_m, m_max, half)
    nu, mass_dev = seed_exact(origin, edges, cat, trained, half, params)
    total = nu.copy()
    for _ in range(200):
        nu = np.einsum("jk,jab->kab", q, _spatial_spread(nu, kernels, half))
        total += nu
        if nu.sum() < 1e-3 * total.sum():
            break
    grid = total.sum(axis=0)
    mc_eff, m_max_eff = mc - delta_m / 2, m_max + delta_m / 2
    thr = target_mw - delta_m / 2
    norm = 1.0 - np.exp(-beta * (m_max_eff - mc_eff))
    tail = (np.exp(-beta * (thr - mc_eff))
            - np.exp(-beta * (m_max_eff - mc_eff))) / norm
    grid *= tail
    ii, jj = np.nonzero(grid)
    return pd.Series(grid[ii, jj], index=ii * 1000 + jj), mass_dev


def main() -> None:
    cmp = pd.concat([pd.read_csv(f) for f in
                     glob.glob(str(ROOT / "data/processed/analytic_vs_sim/shard_*.csv"))])
    sim_all = pd.concat([pd.read_csv(f) for f in
                         glob.glob(str(ROOT / "data/processed/etas_monthly/shard_*.csv"))])
    sim_all = sim_all[(sim_all.window_days == 7) & (sim_all.target_mw == 4.5)]
    trained, cat = load_state()

    origins = sorted(cmp.origin.unique())
    picks = [origins[i] for i in np.linspace(0, len(origins) - 1, 8).astype(int)]

    rows = []
    for o in picks:
        mu_ratio = float(cmp.loc[cmp.origin == o, "mu_orani"].iloc[0])
        params = dict(trained["params"])
        params["log10_mu"] = (trained["params"]["log10_mu"]
                              + float(np.log10(mu_ratio)))
        snap, _ = expected_counts(pd.Timestamp(o), 7, 4.5, cat, trained,
                                  params=params)
        exact, dev = run_exact(pd.Timestamp(o), 7, 4.5, cat, trained, params)
        sim = sim_all[sim_all.ref_date == o].set_index("cell_id").rate_etas
        cells = snap.index.union(exact.index).union(sim.index)
        s = snap.reindex(cells).fillna(0.0).to_numpy()
        e = exact.reindex(cells).fillna(0.0).to_numpy()
        y = sim.reindex(cells).fillna(0.0).to_numpy()
        rows.append({"origin": o,
                     "r_merkez": float(np.corrcoef(s, y)[0, 1]),
                     "r_gercek": float(np.corrcoef(e, y)[0, 1]),
                     "toplam_merkez": float(s.sum()),
                     "toplam_gercek": float(e.sum()),
                     "kutle_sapmasi": dev})
        print(f"  {o}: r {rows[-1]['r_merkez']:.4f} -> "
              f"{rows[-1]['r_gercek']:.4f}", flush=True)

    df = pd.DataFrame(rows)
    print("\n=== MEKANİZMA TESTİ: hücre merkezi vs gerçek konum ===")
    print(df.round(4).to_string(index=False))
    gain = (df.r_gercek - df.r_merkez).median()
    print(f"\n  korelasyon değişimi (ortanca): {gain:+.4f}")
    print(f"  ortalama kütle sapması        : {df.kutle_sapmasi.mean():+.6f}")
    if gain > 0.01:
        print("\n  HİPOTEZ DESTEKLENDİ: ayrışmanın kaynağı hücre-merkezi")
        print("  yaklaşıklığıdır. Yaklaşıklık düzeltilmelidir.")
    else:
        print("\n  HİPOTEZ DESTEKLENMEDİ: gerçek konum korelasyonu belirgin")
        print("  biçimde artırmıyor. Ayrışmanın kaynağı hâlâ bilinmiyor;")
        print("  operasyonel geçiş YAPILMAMALIDIR.")
    df.to_csv(ROOT / "data" / "processed" / "exact_position_test.csv", index=False)


if __name__ == "__main__":
    main()
