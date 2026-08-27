"""ETAS beklenen olay sayısı — TAM ANALİTİK, dallanma yinelemesiyle.

`etas_analytic` yalnızca BİRİNCİL kuşağı verir (arka plan + geçmişin doğrudan
tetiklemesi) ve gerçek beklentinin alt sınırıdır. Bu modül ikincil kuşakları da
ekleyerek beklentiyi tamamlar; Monte Carlo tamamen devreden çıkar.

NEDEN GEREKLİ. Ölçüldü: haftalık hücre oranlarının ortancası 4.1e-04. Simülasyon
oranı n_sim denemeden kestirir, yani 1/n_sim altındaki oranlar sıfır görünür.
5000 simülasyonda bile pozitif hücrelerin %43.7'si eşiğin altında kalıyor;
güvenilir kestirim için hücre başına ~10 sentetik olay, yani n_sim ~ 25.000
gerekir ve bu 209 başlangıç için günler sürer. Simülasyon bu ölçekte yanlış
araçtır.

YÖNTEM. Koşullu yoğunluk

    lambda(x,t) = mu(x) + SUM_i k(m_i) g(t-t_i) f(x-x_i; m_i)

olduğundan, pencere içindeki beklenen sayı bir Volterra denklemidir: pencerede
oluşan olaylar da tetikler. Kuşaklar üzerinden yinelenir:

    nu_0        = arka plan + geçmişin doğrudan tetiklemesi     (tohum)
    nu_{g+1}    = S( nu_g )  zaman ekseninde nedensel Q ile taşınmış
    toplam      = SUM_g nu_g

S uzaysal evrişim (büyüklük üzerinden beklenti alınmış üretkenlik çekirdeği),
Q ise nedensel zaman geçiş matrisidir. Dallanma oranı 1'in altında olduğu için
seri geometrik hızda yakınsar.

BÜYÜKLÜK KESİMİ — İKİ YÖNTEMİN SESSİZCE AYRIŞABİLECEĞİ YER. Paketin raporladığı
dallanma oranı (etas_params.json'daki 0.821) `dm_max=None` ile, yani KESİMSİZ
Gutenberg-Richter ile hesaplanır. Simülasyon ise büyüklükleri
`m_max + delta_m/2` = 8.05'te keser ve `mc - delta_m/2` = 3.25'ten başlatır
(mc_b_est.simulate_magnitudes). Bu modül SİMÜLASYONLA aynı olmak zorunda
olduğundan kesimli GR kullanır; fark ~%1.1'dir ve `mass_check` ile raporlanır.

UZAYSAL ÜSTEL. Üretkenliğin büyüklük üsteli a değil, alpha = a - rho*gamma'dır:
uzaysal çekirdeğin alan integrali D^(-rho) = (d e^(gamma dm))^(-rho) çarpanını
getirir. Paketin branching_ratio'su da bunu kullanır; ayrı türetmek iki yöntemi
ayrıştırırdı.
"""
import numpy as np
import pandas as pd

from src.config import DEG_KM, LAT0, LAT1, LON0, LON1, STEP
import src.models.etas_analytic as _ea
from src.models.etas_analytic import spatial_table

NEAR = 2          # gerçek konumla hesaplanan yakın alan yarıçapı (hücre)
# Kaynakları gerçek konumlarına yerleştirmeyi kapatır; YALNIZCA eski davranışı
# yeniden üretip düzeltmenin etkisini ölçmek için. Üretimde daima True.
USE_EXACT_POSITION = True
GAUSS = 20

NLAT = int(round((LAT1 - LAT0) / STEP))
NLON = int(round((LON1 - LON0) / STEP))

# Varsayılan sayısal ayarlar; yakınsama testiyle seçildi (bkz. convergence()).
N_TIME_BINS = 32
GEN_TOL = 1e-3        # kuşak katkısı toplamın bu oranının altına inince dur
MAX_GENERATIONS = 200
MAG_BINS = 0.1


def time_integral(t1: np.ndarray, t2: np.ndarray, params: dict) -> np.ndarray:
    """Omori-tipi zaman çekirdeğinin [t1, t2] integrali (normalize DEĞİL).

    Paketin expected_aftershocks'undaki time_factor ile aynı ifade; ayrı
    türetmek iki yolun ayrışması demek olurdu.
    """
    from etas.inversion import upper_gamma_ext

    c = 10 ** params["log10_c"]
    tau = 10 ** params["log10_tau"]
    omega = params["omega"]
    pref = np.power(tau, -omega) * np.exp(c / tau)
    g1 = np.vectorize(upper_gamma_ext)(-omega, (np.maximum(t1, 0) + c) / tau)
    g2 = np.vectorize(upper_gamma_ext)(-omega, (np.maximum(t2, 0) + c) / tau)
    return pref * (g1 - g2)


def total_time_integral(params: dict) -> float:
    """T(0, sonsuz) — zaman çekirdeğinin toplam kütlesi."""
    from etas.inversion import upper_gamma_ext

    c = 10 ** params["log10_c"]
    tau = 10 ** params["log10_tau"]
    omega = params["omega"]
    return float(np.power(tau, -omega) * np.exp(c / tau)
                 * upper_gamma_ext(-omega, c / tau))


def magnitude_weights(beta: float, mc_eff: float, m_max_eff: float,
                      step: float = MAG_BINS):
    """Kesimli Gutenberg-Richter ağırlıkları — simülasyonla AYNI kesimle.

    simulate_magnitudes: mc - delta_m/2 ile m_max + delta_m/2 arasında,
    yoğunluk beta*exp(-beta*(m-mc)) / (1 - exp(-beta*(m_max-mc))).
    """
    edges = np.arange(mc_eff, m_max_eff + step, step)
    lo, hi = edges[:-1], edges[1:]
    norm = 1.0 - np.exp(-beta * (m_max_eff - mc_eff))
    w = (np.exp(-beta * (lo - mc_eff)) - np.exp(-beta * (hi - mc_eff))) / norm
    return 0.5 * (lo + hi), w


def productivity_bins(params: dict, beta: float, mc_eff: float,
                      m_max_eff: float, step: float = MAG_BINS, sub: int = 64):
    """Büyüklük kutusu başına (temsili büyüklük, TAM üretkenlik genliği).

    Kutu genliği, kutu ortasında değerlendirilmiş bir çarpım DEĞİL, kutu
    üzerindeki gerçek integraldir:

        genlik = INT_lo^hi  p(m) N(m) dm

    Ortada değerlendirmek 0.1'lik kutularla toplam kütleyi %0.32 fazla veriyordu
    (0.8151 yerine 0.8125) çünkü N(m) = e^(alpha_s dm) dışbükeydir. Kutuyu 0.005'e
    indirmek düzeltirdi ama uzaysal tablo sayısını 20 katına çıkarırdı; integrali
    analitik almak aynı sonucu bedelsiz verir.

    Temsili büyüklük de kutu ortası değil, ÜRETKENLİK AĞIRLIKLI ortalamadır:
    uzaysal yayılma büyüklükle değiştiği için, kütlenin çoğunu hangi büyüklük
    taşıyorsa yayılma da ona göre olmalıdır.
    """
    k0 = 10 ** params["log10_k0"]
    d = 10 ** params["log10_d"]
    a, gamma, rho = params["a"], params["gamma"], params["rho"]
    T_inf = total_time_integral(params)
    norm = 1.0 - np.exp(-beta * (m_max_eff - mc_eff))

    edges = np.arange(mc_eff, m_max_eff + step, step)
    reps, amps = [], []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = np.linspace(lo, hi, sub)
        dm = m - mc_eff
        pdf = beta * np.exp(-beta * dm) / norm
        n_of_m = (k0 * np.exp(a * dm) * (np.pi / rho)
                  * np.power(d * np.exp(gamma * dm), -rho) * T_inf)
        integrand = pdf * n_of_m
        amp = float(np.trapezoid(integrand, m))
        if amp <= 0:
            continue
        reps.append(float(np.trapezoid(integrand * m, m) / amp))
        amps.append(amp)
    return np.array(reps), np.array(amps)


def productivity_kernels(params: dict, beta: float, mc: float, delta_m: float,
                         m_max: float, half: int) -> tuple[np.ndarray, float]:
    """Enlem satırı başına uzaysal üretkenlik çekirdeği ve toplam kütlesi.

    kernel[i] toplamı ~ dallanma oranıdır (kesimli GR ile, kenar kaybı düşülmüş).
    Bu, kütle korunumu kontrolünün dayanağıdır.
    """
    mc_eff = mc - delta_m / 2
    m_max_eff = m_max + delta_m / 2
    reps, amps = productivity_bins(params, beta, mc_eff, m_max_eff)

    kernels = np.zeros((NLAT, 2 * half + 1, 2 * half + 1))
    for i in range(NLAT):
        lat_c = LAT0 + (i + 0.5) * STEP
        acc = np.zeros((2 * half + 1, 2 * half + 1))
        for m, amp in zip(reps, amps):
            if amp < 1e-12:
                continue
            acc += amp * spatial_table(m, lat_c, params, mc_eff,
                                       half_width=half)
        kernels[i] = acc
    return kernels, float(kernels[NLAT // 2].sum())


def time_bins(days: float, params: dict, n_bins: int = N_TIME_BINS):
    """Geometrik zaman kutuları.

    Düzgün kutular yanlış olurdu: c = 9.8 saniye, yani tetiklemenin büyük kısmı
    ilk dakikalarda gerçekleşir. Geometrik kutular hem o ani kısmı hem pencere
    sonunu çözer.
    """
    t0 = 10 ** params["log10_c"]          # ~1e-4 gün
    edges = np.concatenate([[0.0], np.geomspace(t0, days, n_bins)])
    return edges


def _time_transition(edges: np.ndarray, params: dict,
                     n_sub: int = 8) -> np.ndarray:
    """q[j, k]: j kutusunda oluşan bir olayın yavrusunun k kutusuna düşme payı.

    Kaynak zamanı kutu İÇİNDE ORTALANIR, tek bir noktada değil. Kutu ortasını
    kullanmak yakınsamayı yavaşlatıyordu: kutu sayısını iki katına çıkarmak
    toplamı %0.61 -> %0.50 -> %0.32 değiştiriyordu, yani hata kutu sayısıyla
    yarılanmıyordu. Zaman çekirdeği kutu içinde çok hızlı değiştiği için
    (c = 9.8 saniye) tek nokta yetmez.

    Kaynakların kutu içinde düzgün dağıldığı varsayılır. Bu da bir yaklaşıklıktır
    (gerçek dağılım Omori'ye göre çarpıktır) ama kutular geometrik olduğu için
    her kutu içinde çekirdek yaklaşık sabit oranda değişir ve düzgün ortalama
    iyi bir kestirimdir. Yakınsama testi bunu doğrular.

    Pencere dışına düşen yavrular kaybolur -- bu doğru davranıştır, onlar
    pencerede sayılmaz.
    """
    T_inf = total_time_integral(params)
    K = len(edges) - 1
    q = np.zeros((K, K))
    gx, gw = np.polynomial.legendre.leggauss(n_sub)
    u, wu = 0.5 * (gx + 1.0), 0.5 * gw          # [0,1] aralığına ölçekle
    for j in range(K):
        lo, hi = edges[j], edges[j + 1]
        acc = np.zeros(K)
        for uk, wk in zip(u, wu):
            s = lo + uk * (hi - lo)
            t0 = np.maximum(edges[:-1] - s, 0.0)
            t1 = edges[1:] - s
            acc += wk * np.where(edges[1:] > s,
                                 time_integral(t0, t1, params) / T_inf, 0.0)
        q[j] = acc
    return q


def exact_near_field(m, lat_s, lon_s, params, mc):
    """Kaynağın GERÇEK konumuna göre yakın alan payları.

    NEDEN GEREKLİ. Uzaysal çekirdeği evrişime indirgemek için kaynaklar hücre
    merkezine oturtuluyordu. Hücre ~25 km, çekirdek ölçeği sqrt(D) ~ 11 km;
    yani yaklaşıklık hücre boyutuyla karşılaştırılabilir ve hücre düzeyinde
    kütleyi yanlış dağıtıyor. Toplamı koruduğu için toplam kıyaslarında
    görünmüyor, hücre bazlı korelasyonda görünüyordu.

    Ölçüldü (8 başlangıç): gerçek konuma geçince simülasyonla korelasyon
    hepsinde arttı, ortanca +0.0218; kütle sapması -1.1e-05.

    Uzak alanda hücre-merkezi yaklaşıklığı zararsızdır (mesafe >> hücre boyutu),
    bu yüzden yalnızca yakın alan (5x5) yeniden hesaplanır ve önbelleklenmiş
    tablonun ilgili bölümünün yerine konur.
    """
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



def seed_counts(origin: pd.Timestamp, edges: np.ndarray, cat: pd.DataFrame,
                trained: dict, half: int, history_years: float = 5.0,
                params: dict | None = None) -> np.ndarray:
    """Tohum: arka plan + geçmişin doğrudan tetiklemesi, (kutu, enlem, boylam)."""
    params = params if params is not None else trained["params"]
    mc = trained["mc"]
    delta_m = trained.get("delta_m", 0.1)
    mc_eff = mc - delta_m / 2
    k0 = 10 ** params["log10_k0"]
    d = 10 ** params["log10_d"]
    a, gamma, rho = params["a"], params["gamma"], params["rho"]
    K = len(edges) - 1
    out = np.zeros((K, NLAT, NLON))

    # arka plan: düzgün, hücre alanı x kutu süresi
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
        return out

    age = (origin - src.time).dt.total_seconds().to_numpy() / 86400.0
    m = src.magnitude.to_numpy()
    dm = m - mc_eff
    amp = (k0 * np.exp(a * dm) * (np.pi / rho)
           * np.power(d * np.exp(gamma * dm), -rho))

    i_src = np.floor((src.latitude.to_numpy() - LAT0) / STEP).astype(int)
    j_src = np.floor((src.longitude.to_numpy() - LON0) / STEP).astype(int)
    ok = (i_src >= 0) & (i_src < NLAT) & (j_src >= 0) & (j_src < NLON)

    cache: dict[tuple[int, int], np.ndarray] = {}
    mb = np.round(m / MAG_BINS).astype(int)
    for k in np.where(ok)[0]:
        # zaman payları: olayın yaşından itibaren kutu sınırlarına
        tint = time_integral(age[k] + edges[:-1], age[k] + edges[1:], params)
        if tint.sum() <= 0:
            continue
        key = (int(mb[k]), int(i_src[k]))
        tab = cache.get(key)
        if tab is None:
            tab = spatial_table(mb[k] * MAG_BINS, LAT0 + (i_src[k] + 0.5) * STEP,
                                params, mc_eff, half_width=half)
            cache[key] = tab
        # Yakın alan kaynağın GERÇEK konumuna göre yeniden hesaplanır.
        if USE_EXACT_POSITION:
            tab = tab.copy()
            near, _, _ = exact_near_field(mb[k] * MAG_BINS,
                                          src.latitude.iat[k],
                                          src.longitude.iat[k],
                                          params, mc_eff)
            c = half
            tab[c - NEAR:c + NEAR + 1, c - NEAR:c + NEAR + 1] = near
        i0, j0 = i_src[k] - half, j_src[k] - half
        ia, ib = max(0, i0), min(NLAT, i0 + 2 * half + 1)
        ja, jb = max(0, j0), min(NLON, j0 + 2 * half + 1)
        if ia >= ib or ja >= jb:
            continue
        block = amp[k] * tab[ia - i0:ib - i0, ja - j0:jb - j0]
        out[:, ia:ib, ja:jb] += tint[:, None, None] * block[None, :, :]
    return out


def _spatial_spread(nu: np.ndarray, kernels: np.ndarray, half: int) -> np.ndarray:
    """Uzaysal evrişim; çekirdek KAYNAK satırına göre değişir (enlem etkisi)."""
    out = np.zeros_like(nu)
    for i in range(NLAT):
        row = nu[:, i, :]
        if not row.any():
            continue
        ker = kernels[i]
        for di in range(-half, half + 1):
            ii = i + di
            if not 0 <= ii < NLAT:
                continue          # ızgara dışına giden kütle kaybolur
            krow = ker[di + half]
            for dj in range(-half, half + 1):
                w = krow[dj + half]
                if w <= 0:
                    continue
                if dj >= 0:
                    out[:, ii, dj:] += w * row[:, :NLON - dj] if dj else w * row
                else:
                    out[:, ii, :NLON + dj] += w * row[:, -dj:]
    return out


def expected_counts(origin: pd.Timestamp, days: float, target_mw: float,
                    cat: pd.DataFrame, trained: dict,
                    n_bins: int = N_TIME_BINS, tol: float = GEN_TOL,
                    history_years: float = 5.0, report: bool = False,
                    params: dict | None = None) -> tuple[pd.Series, dict]:
    """Hücre başına TAM beklenen olay sayısı (tüm kuşaklar dahil).

    `params` verilmezse eğitim parametreleri kullanılır. DOĞRU KULLANIM
    `etas_analytic.local_params` ile o başlangıcın yerel mu'sunu geçirmektir;
    eğitim mu'su arka plan terimini 2.6 kat şişirir (ölçüldü).

    Dönüş: (hücre kimliğine göre Series, tanılama sözlüğü).
    """
    params = params if params is not None else trained["params"]
    mc = trained["mc"]
    beta = trained["beta"]
    delta_m = trained.get("delta_m", 0.1)
    m_max = trained.get("m_max", 8.0)
    # _ea üzerinden okunur, içe aktarma anında DEĞİL: doğrulama betiği yarıçapı
    # değiştirip duyarlılık ölçüyor. İçe aktarılan bir kopya kullanılırsa o test
    # sessizce hiçbir şey sınamaz -- nitekim ilk sürümde dört yarıçapta da
    # birebir aynı sonucu verdi ve "kusursuz" göründü.
    half = int(np.ceil(_ea.MAX_RADIUS_KM / (STEP * DEG_KM)))

    edges = time_bins(days, params, n_bins)
    q = _time_transition(edges, params)
    kernels, kernel_mass = productivity_kernels(params, beta, mc, delta_m,
                                                m_max, half)

    nu = seed_counts(origin, edges, cat, trained, half, history_years, params)
    total = nu.copy()
    gen_mass = [float(nu.sum())]
    for g in range(MAX_GENERATIONS):
        spread = _spatial_spread(nu, kernels, half)
        nu = np.einsum("jk,jab->kab", q, spread)
        s = float(nu.sum())
        gen_mass.append(s)
        total += nu
        if s < tol * float(total.sum()):
            break

    grid = total.sum(axis=0)
    # M >= mc'den M >= target'a: KESİMLİ Gutenberg-Richter kuyruk payı.
    #
    # EŞİK delta_m/2 KADAR AŞAĞI KAYDIRILIR. Hem sentetik hem gözlenen katalogda
    # büyüklükler 0.1'e yuvarlanmıştır; "M >= 4.5" olarak sayılan bir olayın
    # gerçek büyüklüğü [4.45, 4.55) aralığındadır. Sürekli dağılımda 4.5'ten
    # kesmek, yuvarlanmış katalogda 4.5 görünen olayların yaklaşık yarısını
    # dışarıda bırakır.
    #
    # Ölçüldü: bu düzeltme olmadan simülasyon/analitik oranı iki farklı rejimde
    # de 1.17 çıkıyordu; beklenen çarpan exp(beta*delta_m/2) = 1.158.
    mc_eff, m_max_eff = mc - delta_m / 2, m_max + delta_m / 2
    thr = target_mw - delta_m / 2
    norm = 1.0 - np.exp(-beta * (m_max_eff - mc_eff))
    tail = (np.exp(-beta * (thr - mc_eff))
            - np.exp(-beta * (m_max_eff - mc_eff))) / norm
    grid = grid * tail

    ii, jj = np.nonzero(grid)
    series = pd.Series(grid[ii, jj], index=ii * 1000 + jj, name="rate_analytic")
    diag = {"kuşak_sayısı": len(gen_mass) - 1, "kuşak_kütleleri": gen_mass,
            "çekirdek_kütlesi": kernel_mass, "zaman_kutusu": n_bins,
            "büyüklük_kuyruğu": float(tail)}
    if report:
        print(f"  kuşak {diag['kuşak_sayısı']}, çekirdek kütlesi "
              f"{kernel_mass:.4f}, toplam {series.sum():.4f}")
    return series, diag
