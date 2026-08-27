"""Analitik dallanma yönteminin birim testleri.

Bu yöntem simülasyonun yerini alıyor; hataları sessizdir (sayı çıkar, makul
görünür, yanlıştır). Testler, doğrulama betiğindeki beş kontrolün ucuz
olanlarını CI'da sabitler; pahalı olanlar (24 başlangıç kıyası, yakınsama
taramaları) `scripts/10_validate_branching.py` içindedir.
"""
import numpy as np
import pandas as pd
import pytest

from src.models.etas_params import EtasParams

from tests.conftest import veri_gerekir

# Bu modülün tamamı türetilmiş kataloğa bağlıdır (bkz. conftest).
pytestmark = veri_gerekir


@pytest.fixture(scope="module")
def ep():
    return EtasParams.load()


@pytest.fixture(scope="module")
def state():
    from src.models.etas_analytic import load_state
    return load_state()


# --- parametre dönüşümleri: TEK kaynak -------------------------------------

def test_parameter_conversions_match_closed_forms(ep):
    """Dönüşümler kapalı formlarıyla birebir uyuşmalı."""
    import math

    assert ep.omori_p == pytest.approx(1.0 + ep.p["omega"])
    assert ep.alpha_base10 == pytest.approx(ep.p["a"] / math.log(10))
    assert ep.b_value == pytest.approx(ep.beta / math.log(10))
    assert ep.c_days == pytest.approx(10 ** ep.p["log10_c"])
    assert ep.d_km == pytest.approx(math.sqrt(10 ** ep.p["log10_d"]))


def test_spatial_alpha_is_not_the_raw_a(ep):
    """Uzay-integralli üretkenlik üsteli a DEĞİL, a - rho*gamma olmalı.

    Bu ayrım sessizce kaybolursa üretkenlik büyüklükle çok hızlı büyür ve
    dallanma oranı tutmaz. Paketin branching_ratio'su da a - rho*gamma kullanır.
    """
    assert ep.alpha_spatial == pytest.approx(
        ep.p["a"] - ep.rho * ep.p["gamma"])
    assert ep.alpha_spatial < ep.p["a"]


def test_effective_magnitude_bounds_match_the_package(ep):
    """mc_eff ve m_max_eff, mc_b_est.simulate_magnitudes ile aynı olmalı."""
    assert ep.mc_eff == pytest.approx(ep.mc - ep.delta_m / 2)
    assert ep.m_max_eff == pytest.approx(ep.m_max + ep.delta_m / 2)


def test_nominal_and_effective_branching_ratios_differ(ep):
    """İki dallanma oranı AYNI DEĞİLDİR ve karıştırılmamalıdır.

    etas_params.json'da raporlanan değer kesimsizdir (dm_max=None); simülasyon
    ise büyüklükleri keser. Kütle korunumu testi EFEKTİF değeri hedeflemelidir;
    nominali beklemek testi haksız yere başarısız gösterir.
    """
    assert ep.branching_effective < ep.branching_nominal
    assert ep.branching_nominal == pytest.approx(
        float(ep.raw["branching_ratio"]), rel=1e-3)
    assert 0.0 < ep.branching_effective < 1.0


# --- kütle korunumu ---------------------------------------------------------

def test_productivity_bins_conserve_mass(ep):
    """Üretkenlik genliklerinin toplamı efektif dallanma oranına eşit olmalı.

    Kutu ortasında değerlendirme %0.32 fazla veriyordu (N(m) dışbükey); genlik
    artık kutu üzerindeki gerçek integraldir.
    """
    from src.models.etas_branching import productivity_bins

    _, amps = productivity_bins(ep.p, ep.beta, ep.mc_eff, ep.m_max_eff)
    assert amps.sum() == pytest.approx(ep.branching_effective, rel=1e-4)


def test_magnitude_weights_match_package_sampler(ep):
    """Analitik GR ağırlıkları paketin ürettiği örneklemle uyuşmalı."""
    from etas.mc_b_est import simulate_magnitudes
    from src.models.etas_branching import MAG_BINS, magnitude_weights

    mags, w = magnitude_weights(ep.beta, ep.mc_eff, ep.m_max_eff)
    assert w.sum() == pytest.approx(1.0)
    np.random.seed(11)
    sample = simulate_magnitudes(100_000, beta=ep.beta, mc=ep.mc_eff,
                                 m_max=ep.m_max_eff)
    emp = np.array([((sample >= lo) & (sample < lo + MAG_BINS)).mean()
                    for lo in mags - MAG_BINS / 2])
    assert np.abs(emp - w).max() < 5e-3


# --- determinizm: tohum protokolünün yerini alır ---------------------------

def test_result_is_bit_identical_across_runs(state):
    """Aynı girdi -> BİREBİR aynı çıktı.

    Simülasyonlu yolda tekrarlanabilirlik bir tohum protokolü gerektiriyordu ve
    paket argümansız np.random.seed() çağırdığı için o protokol kırılgandı.
    Analitik hesapta rastgelelik YOKTUR; tekrarlanabilirlik bir sözleşme değil,
    yöntemin özelliğidir. Bu test onu sabitler.
    """
    from src.models.etas_branching import expected_counts

    trained, cat = state
    o = pd.Timestamp("2023-03-01")
    a, _ = expected_counts(o, 7, 4.5, cat, trained, n_bins=8)
    b, _ = expected_counts(o, 7, 4.5, cat, trained, n_bins=8)
    assert a.index.equals(b.index)
    assert np.array_equal(a.to_numpy(), b.to_numpy()), "bit düzeyinde farklı"


def test_no_look_ahead(state):
    """Yalnızca başlangıç öncesi olaylar kullanılmalı."""
    from src.models.etas_branching import expected_counts

    trained, cat = state
    before, _ = expected_counts(pd.Timestamp("2023-02-06"), 7, 4.5, cat,
                                trained, n_bins=8)
    after, _ = expected_counts(pd.Timestamp("2023-02-07"), 7, 4.5, cat,
                               trained, n_bins=8)
    assert after.sum() > 5 * before.sum()


def test_branching_adds_mass_over_direct_only(state):
    """Dallanma, birincil kuşaktan DAHA ÇOK olay beklemeli.

    İkincil kuşaklar yalnızca ekler; toplam birincilin altına inerse yineleme
    ya da zaman geçişi yanlıştır.
    """
    from src.models.etas_analytic import direct_expected_counts
    from src.models.etas_branching import expected_counts

    trained, cat = state
    o = pd.Timestamp("2023-03-01")
    direct = direct_expected_counts(o, 7, 4.5, cat, trained).sum()
    full, _ = expected_counts(o, 7, 4.5, cat, trained, n_bins=8)
    assert full.sum() > direct
    # dallanma oranı 0.81 iken kısa pencerede çarpan 1 ile 1/(1-n) arasında olmalı
    ratio = full.sum() / direct
    assert 1.0 < ratio < 1.0 / (1.0 - 0.9)


def test_local_params_is_deterministic(state):
    """Durum kurma adımı da deterministik olmalı — UÇTAN UCA.

    `expected_counts`'un deterministik olması yetmez: `local_params` paketin EM
    adımını çalıştırır ve o adım tohumsuz bırakılırsa log10_mu her çağrıda
    oynar. Ölçüldü (V16): -6.54154000821231 vs -6.5415908942714065, oranlarda
    bağıl 1,2e-04 fark.

    Künye "rastgelelik YOK" diyor; bu test o beyanın UÇTAN UCA doğru olduğunu
    sabitler -- yalnızca son adımın değil.
    """
    from src.models.etas_analytic import local_params

    trained, cat = state
    o = pd.Timestamp("2026-08-24")
    p1 = local_params(o, cat, trained)
    p2 = local_params(o, cat, trained)
    assert p1["log10_mu"] == p2["log10_mu"], (
        f"durum kurma adımı deterministik değil: {p1['log10_mu']!r} vs "
        f"{p2['log10_mu']!r}")
