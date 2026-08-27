"""Puanlama matematiğinin analitik doğrulaması.

`score_counts`, yayımlanan her tahmini yargılayacak fonksiyondur. Yanlış olması,
modelin başarısı hakkında yanlış sonuç üretir ve bu tür bir hata sessizdir --
sayı çıkar, makul görünür, yanlıştır. Bu yüzden cevabı elle hesaplanabilen
girdilerle sınanır.
"""
import numpy as np
import pytest

from src.operational.score_archive import score_counts


def test_identical_models_give_zero_information_gain():
    """İki model aynıysa bilgi kazancı tam olarak sıfır olmalı."""
    lam = np.array([0.5, 0.2, 0.1])
    n = np.array([1, 0, 2])
    assert score_counts(lam, lam.copy(), n)["info_gain"] == pytest.approx(0.0)


def test_information_gain_matches_hand_computation():
    """Tek hücre, tek olay: kazanç log(lam/base) olmalı, eksi oran farkı.

    LL = -lam + n*log(lam);  fark = -(lam-base) + n*log(lam/base)
    lam=2.0, base=0.5, n=1  ->  -(1.5) + log(4) = -1.5 + 1.3862944 = -0.1137056
    """
    got = score_counts(np.array([2.0]), np.array([0.5]), np.array([1]))
    assert got["info_gain"] == pytest.approx(-1.5 + np.log(4.0))


def test_gain_is_positive_when_forecast_puts_mass_where_event_fell():
    """Doğru hücreyi işaret eden tahmin, düz temel modeli yenmeli.

    İki model de toplamda aynı beklentiye sahip (1.0), yani N-testi ikisini de
    ayırt edemez; fark yalnızca MEKÂNSAL dağılımdadır. Bilgi kazancının
    yakaladığı ve N-testinin yakalayamadığı şey tam olarak budur.
    """
    lam = np.array([0.9, 0.05, 0.05])     # olayın düştüğü hücreye yığılmış
    base = np.array([1 / 3, 1 / 3, 1 / 3])  # düz
    n = np.array([1, 0, 0])
    out = score_counts(lam, base, n)
    assert out["info_gain"] > 0
    assert out["expected"] == pytest.approx(base.sum())  # toplamlar eşit


def test_gain_is_negative_when_forecast_misses():
    """Aynı kurulum, olay yığının OLMADIĞI hücreye düşerse kazanç negatif."""
    lam = np.array([0.9, 0.05, 0.05])
    base = np.array([1 / 3, 1 / 3, 1 / 3])
    out = score_counts(lam, base, np.array([0, 1, 0]))
    assert out["info_gain"] < 0


def test_n_test_flags_systematic_under_prediction():
    """Beklenen 1, gözlenen 20 ise N-testi sapmayı işaretlemeli."""
    lam = np.array([1.0])
    assert score_counts(lam, lam.copy(), np.array([20]))["n_test_p"] < 0.05
    # Beklentiye yakın gözlem işaretlenmemeli
    assert score_counts(lam, lam.copy(), np.array([1]))["n_test_p"] > 0.05


def test_zero_observation_gives_undefined_gain_not_zero():
    """Hiç olay yoksa olay BAŞINA kazanç tanımsızdır -- sıfır değil.

    Sıfır döndürmek, olaysız pencereleri ortalamaya "nötr" olarak katardı ve
    çok sayıda sessiz pencere gerçek kazancı sıfıra doğru seyreltirdi.
    """
    out = score_counts(np.array([0.5]), np.array([0.2]), np.array([0]))
    assert np.isnan(out["info_gain"])
    assert out["observed"] == 0


def test_zero_rate_cells_are_excluded_not_infinite():
    """Sıfır oranlı hücre toplamı -sonsuza götürmemeli.

    500 simülasyonun çözünürlüğü altındaki hücreler tahmin dosyasında yer almaz;
    oraya bir olay düştüğünde log(0) oluşur. Çağıran taraf fiziksel taban
    uygular, ama fonksiyonun kendisi de sonlu kalmalıdır.
    """
    out = score_counts(np.array([0.0, 0.5]), np.array([0.1, 0.2]), np.array([1, 1]))
    assert np.isfinite(out["ll_etas"]) and np.isfinite(out["info_gain"])
