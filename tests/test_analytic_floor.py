"""Analitik ETAS tabanının özellikleri.

Taban, gerçek beklentinin ALT SINIRI olduğu iddiasıyla kullanılıyor. İddia
yanlışsa bilgi kazancı sistematik olarak şişer ve bu sessiz bir hatadır --
sayı çıkar, makul görünür, modelin değil tabanın başarısını ölçer.
"""
import numpy as np
import pandas as pd
import pytest

from src.config import DEG_KM, LAT0, LON0, STEP
from src.models.etas_analytic import direct_expected_counts, spatial_table

from tests.conftest import veri_gerekir

# Bu modülün tamamı türetilmiş kataloğa bağlıdır (bkz. conftest).
pytestmark = veri_gerekir


@pytest.fixture(scope="module")
def state():
    from src.models.etas_analytic import load_state
    return load_state()


def _empty_catalog(mc: float) -> pd.DataFrame:
    return pd.DataFrame({"latitude": [], "longitude": [], "magnitude": [],
                         "time": pd.to_datetime([])})


def test_spatial_table_is_a_probability_partition():
    """Uzaysal paylar toplamı 1'i AŞMAMALI (kuyruk kesildiği için 1'in altında)."""
    params = {"log10_d": 2.11, "rho": 3.513, "gamma": 0.655}
    for m in (3.3, 5.0, 7.0):
        t = spatial_table(m, 39.0, params, mc=3.3, half_width=8)
        assert t.sum() <= 1.0 + 1e-9, f"m={m}: paylar toplamı {t.sum()}"
        assert (t >= 0).all()
        # kütle merkeze yığılmalı
        c = t.shape[0] // 2
        assert t[c, c] == t.max()


def test_larger_magnitude_spreads_further():
    """Büyük olayın tetiklemesi daha geniş alana yayılır (gamma > 0)."""
    params = {"log10_d": 2.11, "rho": 3.513, "gamma": 0.655}
    small = spatial_table(3.5, 39.0, params, mc=3.3, half_width=8)
    big = spatial_table(6.5, 39.0, params, mc=3.3, half_width=8)
    c = small.shape[0] // 2
    assert big[c, c] < small[c, c], "büyük olay merkeze daha az yığmalı"
    assert big.sum() < small.sum(), "büyük olayda kuyruk kesme kaybı daha fazla"


def test_background_only_matches_closed_form(state):
    """Geçmiş yokken taban tam olarak düzgün arka plandır.

    ETAS'ın arka planı bu kurulumda uzaysal olarak düzgündür
    (background_probs None -> paket çokgen üzerinde düzgün dağıtır), yani
    hücre başına beklenti mu * alan * gün * büyüklük ölçeği olmalıdır.
    """
    trained, _ = state
    mc = trained["mc"]
    cat = _empty_catalog(mc)
    days, target = 7.0, 4.5
    got = direct_expected_counts(pd.Timestamp("2024-01-01"), days, target,
                                 cat, trained)

    mu = 10 ** trained["params"]["log10_mu"]
    # Eşik delta_m/2 kadar aşağı kaydırılır: kataloglar 0.1'e yuvarlıdır,
    # "M >= 4.5" sayılan olayın gerçek büyüklüğü 4.45'ten başlar. Bu düzeltme
    # olmadan analitik hesap simülasyondan exp(beta*0.05) = 1.158 kat düşük
    # kalıyordu (ölçüldü).
    delta_m = trained.get("delta_m", 0.1)
    mag_scale = np.exp(-trained["beta"] * (target - delta_m / 2 - mc))
    lat_c = LAT0 + (int(got.index[0]) // 1000 + 0.5) * STEP
    area = (STEP * DEG_KM) * (STEP * DEG_KM * np.cos(np.radians(lat_c)))
    assert got.iloc[0] == pytest.approx(mu * area * days * mag_scale, rel=1e-9)


def test_floor_grows_with_window(state):
    """Daha uzun pencere daha çok olay bekler."""
    trained, cat = state
    o = pd.Timestamp("2023-03-01")
    a = direct_expected_counts(o, 1, 4.5, cat, trained).sum()
    b = direct_expected_counts(o, 7, 4.5, cat, trained).sum()
    assert b > a


def test_floor_drops_with_higher_target_magnitude(state):
    """Daha yüksek hedef büyüklük daha az olay bekler (Gutenberg-Richter)."""
    trained, cat = state
    o = pd.Timestamp("2023-03-01")
    lo = direct_expected_counts(o, 7, 4.5, cat, trained).sum()
    hi = direct_expected_counts(o, 7, 5.5, cat, trained).sum()
    assert hi < lo
    # oran ETAS'ın KENDİ beta'sından çıkmalı, katalog b'sinden değil
    assert hi / lo == pytest.approx(np.exp(-trained["beta"] * 1.0), rel=1e-6)


def test_no_look_ahead(state):
    """Taban yalnızca başlangıç ÖNCESİ olayları kullanmalı.

    6 Şubat 2023'ten hemen önceki taban, hemen sonrakinden çok daha düşük
    olmalıdır; tersi look-ahead sızıntısı demektir.
    """
    trained, cat = state
    before = direct_expected_counts(pd.Timestamp("2023-02-06"), 7, 4.5,
                                    cat, trained).sum()
    after = direct_expected_counts(pd.Timestamp("2023-02-07"), 7, 4.5,
                                   cat, trained).sum()
    assert after > 5 * before, f"önce {before:.3f}, sonra {after:.3f}"
