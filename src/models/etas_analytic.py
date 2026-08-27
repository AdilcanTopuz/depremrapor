"""ETAS beklenen olay sayısının ANALİTİK alt sınırı — Monte Carlo tabanı yerine.

NEDEN. Simülasyondan kestirilen hücre oranları, 1/n_sim çözünürlüğünün altında
sıfır görünür. Ölçüldü: 500 simülasyonla pozitif hücrelerin %53'ünde oran sıfır
çıkıyor ve log-olabilirlik tanımsız hâle geliyor. Bir "taban" koymak zorunlu,
ama tabanın SEÇİMİ sonucu belirlerse ölçüm modelin değil tabanın başarısını
ölçer -- nitekim üç farklı taban üç farklı sonuç verdi (-8.93 / +0.68 / +1.07).

ÇÖZÜM. Taban modelden türetilir. ETAS'ın koşullu yoğunluğu

    lambda(x,t) = mu(x) + SUM_i  k(m_i) * g(t - t_i) * f(x - x_i; m_i)

ve hücre x pencere üzerindeki integrali, İKİNCİL kuşaklar hariç tutulduğunda
analitik olarak hesaplanabilir. İkincil kuşaklar yalnızca EKLER, dolayısıyla bu
integral gerçek beklentinin KESİN ALT SINIRIDIR. Keyfî bir sayı değil, modelin
kendi parametrelerinden çıkan bir taban.

Paket bunu hazır vermiyor: `etas.evaluation` olabilirlik için analitik parçalar
taşır ama ızgara tahmini üretmez. Fonksiyonel biçimler yine de paketten alınır
(`inversion.expected_aftershocks`, `inversion.triggering_kernel`); makaleden
yeniden türetmek, taban ile modelin ayrışması riskini doğururdu.

ARKA PLAN DÜZGÜNDÜR. `ETASSimulation.background_probs` bu kurulumda None kalıyor
ve paket arka plan olaylarını çokgen üzerinde DÜZGÜN dağıtıyor
(simulation.generate_background_events). Bu yüzden mu terimi hücre alanıyla
orantılıdır. Bu modelin bir sınırlılığıdır (gerçek arka plan düzgün değildir)
ama tabanın modele sadık kalması gerekir.

YAKLAŞIKLIK. Kaynak olaylar kendi hücre merkezlerinde varsayılır; böylece
uzaysal çekirdek bir evrişime (convolution) indirgenir ve büyüklük x enlem
kutusu başına önceden hesaplanmış tablolarla uygulanabilir. Bu, yakın alanı
biraz yumuşatır. Sonucu bozmaz çünkü taban yalnızca simülasyonun sıfır verdiği
DÜŞÜK oranlı hücrelerde bağlayıcıdır; yüksek oranlı hücrelerde simülasyon zaten
çözünürlük içindedir ve max(simülasyon, taban) simülasyonu seçer.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.config import DEG_KM, LAT0, LON0, STEP

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# Çekirdek bu yarıçapın ötesinde ihmal edilir. rho ~ 3.5 ile uzaysal azalım
# r^(-2(1+rho)) ~ r^-9; 200 km'de katkı tepe değerin 1e-9 katının altındadır.
MAX_RADIUS_KM = 200.0
MAG_BIN = 0.1
# Gauss-Legendre mertebesi; yakınsama ölçüldü (bkz. spatial_table).
GAUSS_ORDER = 20


def _theta8(params: dict) -> list:
    """Paketin expected_aftershocks fonksiyonunun beklediği 8'li sıra."""
    return [params["log10_k0"], params["a"], params["log10_c"], params["omega"],
            params["log10_tau"], params["log10_d"], params["gamma"],
            params["rho"]]


def _cell_area_km2(lat: float) -> float:
    return (STEP * DEG_KM) * (STEP * DEG_KM * np.cos(np.radians(lat)))


def spatial_table(m: float, lat: float, params: dict, mc: float,
                  half_width: int = 8) -> np.ndarray:
    """Bir kaynağın çevre hücrelere düşen tetikleme PAYLARI (toplamı <= 1).

    Uzaysal çekirdek f(r^2) = 1/(r^2 + D)^(1+rho),  D = d * exp(gamma*(m-mc)).
    Tüm düzlem üzerindeki integrali pi/(rho * D^rho) olduğundan normalize pdf
    buradan çıkar.

    Hücre integrali Gauss-Legendre ile alınır. Mertebe ÖLÇÜLEREK seçildi:
    çekirdek kaynağın kendi hücresinde sivridir (sqrt(D) ~ 11.4 km, hücre
    ~25 km) ve 5 nokta payların toplamını 1.037'ye çıkarıyordu -- yani %3.7
    fazla kütle. 20 noktada toplam 1.00000'a yakınsıyor. Tablolar
    önbelleklendiği için yüksek mertebenin maliyeti ihmal edilebilir.
    """
    d = 10 ** params["log10_d"]
    rho, gamma = params["rho"], params["gamma"]
    D = d * np.exp(gamma * (m - mc))
    norm = np.pi / (rho * D ** rho)          # tüm düzlem integrali

    dx_km = STEP * DEG_KM * np.cos(np.radians(lat))
    dy_km = STEP * DEG_KM
    gx, gw = np.polynomial.legendre.leggauss(GAUSS_ORDER)
    # [-0.5, 0.5] hücre koordinatına ölçekle
    u, wu = gx / 2.0, gw / 2.0

    n = 2 * half_width + 1
    offs = np.arange(-half_width, half_width + 1)
    # hücre merkezleri (kaynak hücresi 0,0)
    cx = offs[None, :, None, None] * dx_km + u[None, None, None, :] * dx_km
    cy = offs[:, None, None, None] * dy_km + u[None, None, :, None] * dy_km
    r2 = cx ** 2 + cy ** 2
    dens = 1.0 / np.power(r2 + D, 1.0 + rho)
    w = (wu[None, None, :, None] * wu[None, None, None, :]) * dx_km * dy_km
    table = (dens * w).sum(axis=(2, 3)) / norm
    return table.reshape(n, n)


def local_params(origin: pd.Timestamp, cat: pd.DataFrame, trained: dict,
                 history_years: float = 5.0) -> dict:
    """O başlangıca ait ETAS parametreleri.

    KRİTİK: tetikleme parametreleri eğitimden gelir ve SABİTTİR, ama ARKA PLAN
    ORANI mu her başlangıçta yerel geçmişten yeniden kestirilir. Paket bunu
    `n_hat / (alan * pencere_uzunluğu)` olarak hesaplar ve simülasyon bu yerel
    değeri kullanır.

    Bu fark önemsiz değil: ölçüldü, mu_yerel/mu_eğitim = 0.38. Eğitim dosyasındaki
    mu'yu kullanmak arka plan terimini 2.6 KAT şişiriyordu ve analitik toplamı
    simülasyonun üstüne çıkarıyordu (24 başlangıcın hepsinde sim/analitik < 1).
    Tetikleme parametrelerinin sabit olduğu ayrıca doğrulandı: sekizi de eğitim
    dosyasıyla birebir aynı.

    Maliyet: `_calculation_at` çağrısı (~2 dk). Simülasyon da aynı maliyeti
    ödüyor; analitik yöntemin kazancı simülasyon adımını ortadan kaldırmasıdır.
    """
    from src.models import etas_baseline as eb

    # DETERMİNİZM. `_calculation_at` paketin EM adımını çalıştırır ve o adım
    # rastgelelik taşır: ölçüldü, aynı başlangıçta log10_mu 5. ondalıkta
    # oynuyordu (-6.54154000821231 vs -6.5415908942714065; oranlarda bağıl
    # 1.2e-04 fark).
    #
    # Dallanma hesabı zaten deterministikti (aynı parametrelerle birebir aynı
    # çıktı); rastgelelik yalnızca DURUM KURMA adımındaydı. Künyedeki
    # "rastgelelik YOK" beyanı bu düzeltme olmadan eksikti.
    #
    # Tohum, simülasyon yolundakiyle AYNI kuraldan gelir: başlangıç tarihinden
    # türetilir, sırasından değil.
    with eb.deterministic_simulation(eb.simulation_seed(origin)):
        calc = eb._calculation_at(origin, cat, trained, history_years)
    out = dict(trained["params"])
    out["log10_mu"] = float(np.log10(calc.n_hat
                                     / (calc.area * calc.timewindow_length)))
    return out


def direct_expected_counts(origin: pd.Timestamp, days: float, target_mw: float,
                           cat: pd.DataFrame, trained: dict,
                           history_years: float = 5.0,
                           params: dict | None = None) -> pd.Series:
    """Hücre başına BİRİNCİL beklenen olay sayısı (arka plan + doğrudan tetikleme).

    Gerçek ETAS beklentisinin kesin alt sınırıdır: ikincil kuşaklar yalnızca
    ekler. Dönen değer hücre kimliğine göre indekslenmiş Series'tir.
    """
    from etas.inversion import expected_aftershocks

    # params verilmezse eğitim değerleri kullanılır. Yerel mu için local_params
    # çağrılmalıdır; eğitim mu'su arka planı 2.6 kat şişirir.
    params = params if params is not None else trained["params"]
    mc = trained["mc"]
    beta = trained["beta"]
    theta = _theta8(params)

    # Büyüklük ölçeklemesi ETAS'IN KENDİ beta'sıyla yapılır, katalog b'siyle
    # değil: taban modelin beklentisi olmalı, katalog kestirimi değil.
    # Eşik delta_m/2 kadar aşağı kaydırılır: kataloglar 0.1'e yuvarlanmıştır,
    # "M >= target" sayılan olayın gerçek büyüklüğü target-0.05'ten başlar.
    # (Aynı düzeltme etas_branching'de gerekçesiyle birlikte açıklanmıştır.)
    delta_m = trained.get("delta_m", 0.1)
    mag_scale = float(np.exp(-beta * (target_mw - delta_m / 2 - mc)))

    hist_start = origin - pd.Timedelta(days=history_years * 365.25)
    src = cat[(cat.time >= hist_start) & (cat.time < origin)]
    src = src[src.magnitude >= mc]

    nlat = int(round((43.0 - LAT0) / STEP))
    nlon = int(round((45.0 - LON0) / STEP))
    grid = np.zeros((nlat, nlon))

    # --- arka plan: düzgün, hücre alanıyla orantılı ---
    mu = 10 ** params["log10_mu"]                     # olay / km^2 / gün, M>=mc
    for i in range(nlat):
        lat_c = LAT0 + (i + 0.5) * STEP
        grid[i, :] += mu * _cell_area_km2(lat_c) * days

    # --- doğrudan tetikleme ---
    if len(src):
        t_start = (origin - src.time).dt.total_seconds().to_numpy() / 86400.0
        t_end = t_start + days
        m = src.magnitude.to_numpy()
        n_direct = expected_aftershocks([m, t_start, t_end], [theta, mc])

        i_src = np.floor((src.latitude.to_numpy() - LAT0) / STEP).astype(int)
        j_src = np.floor((src.longitude.to_numpy() - LON0) / STEP).astype(int)
        ok = (i_src >= 0) & (i_src < nlat) & (j_src >= 0) & (j_src < nlon)

        half = int(np.ceil(MAX_RADIUS_KM / (STEP * DEG_KM)))
        # Tablolar (büyüklük kutusu, enlem satırı) başına önbelleklenir; aynı
        # kutudaki binlerce kaynak tek bir tabloyu paylaşır.
        cache: dict[tuple[int, int], np.ndarray] = {}
        mb = np.round(m / MAG_BIN).astype(int)
        for k in np.where(ok)[0]:
            key = (int(mb[k]), int(i_src[k]))
            tab = cache.get(key)
            if tab is None:
                tab = spatial_table(mb[k] * MAG_BIN,
                                    LAT0 + (i_src[k] + 0.5) * STEP,
                                    params, mc, half_width=half)
                cache[key] = tab
            i0, j0 = i_src[k] - half, j_src[k] - half
            ia, ib = max(0, i0), min(nlat, i0 + 2 * half + 1)
            ja, jb = max(0, j0), min(nlon, j0 + 2 * half + 1)
            if ia >= ib or ja >= jb:
                continue
            grid[ia:ib, ja:jb] += n_direct[k] * tab[ia - i0:ib - i0,
                                                    ja - j0:jb - j0]

    grid *= mag_scale
    ii, jj = np.nonzero(grid)
    cell_ids = ii * 1000 + jj
    return pd.Series(grid[ii, jj], index=cell_ids, name="rate_analytic")


def load_state():
    """Eğitilmiş parametreler ve ETAS şemasındaki katalog."""
    from src.models import etas_baseline as eb

    trained = json.loads(eb.PARAMS_PATH.read_text())
    return trained, eb.etas_catalog(trained["mc"])


def floor_table(origins, days: float, target_mw: float,
                cat: pd.DataFrame | None = None,
                trained: dict | None = None, quiet: bool = False) -> pd.DataFrame:
    """Birden çok başlangıç için analitik taban tablosu.

    Dönen sütunlar: cell_id, ref_date, rate_analytic.
    """
    if trained is None or cat is None:
        trained, cat = load_state()
    out = []
    idx = pd.DatetimeIndex(origins)
    # Katalog ETAS şemasında zaman dilimi taşımaz; başlangıçlar değerlendirme
    # tablolarında UTC-farkındalıklı gelebilir. Hesap farkındalıksız yapılır,
    # ref_date ise ÇAĞIRANIN verdiği biçimde döner ki birleştirme tutsun.
    naive = idx.tz_convert("UTC").tz_localize(None) if idx.tz is not None else idx
    for k, (o, o_naive) in enumerate(zip(idx, naive), 1):
        r = direct_expected_counts(o_naive, days, target_mw, cat, trained)
        out.append(pd.DataFrame({"cell_id": r.index.astype(int),
                                 "ref_date": o, "rate_analytic": r.to_numpy()}))
        if not quiet and k % 100 == 0:
            print(f"  analitik taban {k}/{len(origins)}", flush=True)
    return pd.concat(out, ignore_index=True)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Analitik ETAS taban tablosu")
    ap.add_argument("--start", required=True)
    ap.add_argument("--end", required=True)
    ap.add_argument("--freq", default="D")
    ap.add_argument("--days", type=float, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    origins = pd.date_range(pd.Timestamp(a.start), pd.Timestamp(a.end), freq=a.freq)
    print(f"{len(origins)} başlangıç, {a.days} gün, M>={a.mw}")
    tab = floor_table(origins, a.days, a.mw)
    dst = PROC / a.out
    tab.to_parquet(dst, index=False)
    print(f"{len(tab):,} satır -> {dst}")
    print(f"başlangıç başına ortalama taban toplamı: "
          f"{tab.groupby('ref_date').rate_analytic.sum().mean():.4f}")


if __name__ == "__main__":
    main()
