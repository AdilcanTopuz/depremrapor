"""Asgari saptanabilir etki (MDE) hesabının testleri.

MDE, "fark gösterilemedi" cümlesinin yanında duracak ve okuyucunun bunu
"fark yok" diye okumasını engelleyecek. Yanlış hesaplanırsa tam ters etki
yapar: gücü olduğundan yüksek gösterip "ölçtük, fark yok" izlenimi verir.
"""
import numpy as np
import pandas as pd
import pytest

from src.eval.gain_breakdown import _ig_ci


def _rows(n_event: int, seed: int = 5, spread: float = 1.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    n_bg = 5000
    return pd.DataFrame({
        "y": np.r_[np.ones(n_event), np.zeros(n_bg)],
        "rate_etas": np.r_[rng.lognormal(0, spread, n_event) * 1e-3,
                           rng.lognormal(0, spread, n_bg) * 1e-4],
        "rate_pois": np.r_[rng.lognormal(0, spread, n_event) * 1e-3,
                           rng.lognormal(0, spread, n_bg) * 1e-4],
    })


def test_mde_shrinks_with_more_events():
    """MDE olay sayısıyla küçülmeli — yaklaşık 1/sqrt(n) hızında."""
    _, _, _, mde_small, _ = _ig_ci(_rows(50))
    _, _, _, mde_big, _ = _ig_ci(_rows(200))
    assert mde_big < mde_small
    ratio = mde_small / mde_big
    assert 1.6 < ratio < 2.6, f"1/sqrt(n) ölçeklemesi bozuk: {ratio:.2f}"


def test_small_samples_use_t_coefficients():
    """n < 30'da t katsayısı kullanılmalı; z varsayımı MDE'yi DAR gösterir."""
    _, _, _, _, basis_small = _ig_ci(_rows(12))
    _, _, _, _, basis_big = _ig_ci(_rows(60))
    assert "t(11)" in basis_small, basis_small
    assert "z katsayısı" in basis_big, basis_big


def test_t_coefficient_is_larger_than_z():
    """Küçük örneklemde katsayı BÜYÜK olmalı, küçük değil.

    Ters kurulursa düzeltme, düzeltmeye çalıştığı hatayı büyütür.
    """
    from scipy import stats

    for n in (6, 12, 25):
        mult_t = stats.t.ppf(0.975, n - 1) + stats.t.ppf(0.80, n - 1)
        assert mult_t > 2.802, f"n={n}: t katsayısı z'den küçük ({mult_t:.3f})"


def test_mde_uses_bootstrap_se_not_analytic():
    """MDE bootstrap dağılımından gelmeli; aralıkla aynı kaynaktan.

    Aralık bootstrap'tan, MDE analitik formülden gelirse ikisi tutarsız olur ve
    "aralık şu kadar geniş ama MDE bu kadar dar" gibi anlamsız bir çift çıkar.
    """
    rows = _rows(80)
    ig, lo, hi, mde, basis = _ig_ci(rows)
    assert "bootstrap" in basis
    # Aralık genişliği ~ 2*1.96*SE, MDE ~ 2.802*SE -> oran ~ 1.40
    ratio = (hi - lo) / mde
    assert 1.2 < ratio < 1.6, f"aralık/MDE oranı beklenenden uzak: {ratio:.2f}"


def test_too_few_events_returns_nan():
    """İki olaydan az -> hesap yapılmaz, işaretlenir."""
    ig, lo, hi, mde, basis = _ig_ci(_rows(1))
    assert np.isnan(ig) and np.isnan(mde)
    assert "yetersiz" in basis
