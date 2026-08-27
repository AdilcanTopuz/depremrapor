"""Simülasyon determinizmi — yayımlanan tahmin yeniden üretilebilmeli.

`etas` paketi simülasyon içinde ARGÜMANSIZ np.random.seed() çağırıyor; bu çağrı
tohumu işletim sistemi entropisinden yeniden kurar ve dışarıdan verilen tohumu
siler. Ölçüldü: kabuk olmadan aynı başlangıç iki farklı sonuç veriyordu
(526 ve 477 satır), kabukla birebir aynı sonucu veriyor.

Uçtan uca bir simülasyon testi dakikalar sürer ve teste uygun değildir; bu
yüzden kabuğun kendisi sınanır. Paket sürümü değişip yeniden tohumlama noktaları
kaybolsa bile kabuk zararsızdır, ama kabuk KALDIRILIRSA bu testler patlar.
"""
import numpy as np

from src.models.etas_baseline import deterministic_simulation, simulation_seed


def _draw_like_package():
    """Paketin yaptığını taklit eder: arada kendini yeniden tohumlar."""
    out = [np.random.uniform(size=3)]
    np.random.seed()          # paketin simulation.py:317 / :1171 davranışı
    out.append(np.random.uniform(size=3))
    np.random.seed()
    out.append(np.random.poisson(2.0, size=3))
    return np.concatenate([np.asarray(x, dtype=float) for x in out])


def test_package_self_reseeding_breaks_determinism_without_shim():
    """Kabuk olmadan tekrarlanabilirlik YOKTUR — sorunun varlığını sabitler."""
    np.random.seed(123)
    a = _draw_like_package()
    np.random.seed(123)
    b = _draw_like_package()
    assert not np.array_equal(a, b), (
        "paket artık kendini yeniden tohumlamıyor olabilir; kabuk hâlâ zararsız "
        "ama bu testin gerekçesi değişmiş demektir")


def test_shim_makes_it_deterministic():
    """Kabukla aynı tohum aynı diziyi üretir."""
    with deterministic_simulation(20260824):
        a = _draw_like_package()
    with deterministic_simulation(20260824):
        b = _draw_like_package()
    assert np.array_equal(a, b)


def test_different_seeds_give_different_streams():
    """Farklı tohum farklı akış vermeli — aksi hâlde kabuk akışı dondurmuş olur."""
    with deterministic_simulation(1):
        a = _draw_like_package()
    with deterministic_simulation(2):
        b = _draw_like_package()
    assert not np.array_equal(a, b)


def test_shim_does_not_repeat_the_same_stream():
    """Argümansız her çağrı FARKLI tohum almalı.

    Hepsine aynı tohumu vermek akışı baştan başlatır: simülasyonlar birbirinin
    kopyası olur ve Monte Carlo kestirimi çöker. Kabuk sayaçla ilerlediği için
    ardışık bloklar farklı olmalıdır.
    """
    with deterministic_simulation(7):
        np.random.seed()
        first = np.random.uniform(size=5)
        np.random.seed()
        second = np.random.uniform(size=5)
    assert not np.array_equal(first, second)


def test_shim_restores_numpy_afterwards():
    """Bağlamdan çıkınca np.random.seed eski hâline dönmeli."""
    original = np.random.seed
    with deterministic_simulation(1):
        assert np.random.seed is not original
    assert np.random.seed is original


def test_explicit_seeds_pass_through():
    """Argümanlı çağrılar kabukta değiştirilmeden geçmeli."""
    with deterministic_simulation(99):
        np.random.seed(555)
        a = np.random.uniform(size=4)
        np.random.seed(555)
        b = np.random.uniform(size=4)
    assert np.array_equal(a, b)


def test_seed_depends_on_date_not_order():
    """Tohum başlangıç TARİHİNDEN türetilmeli, sırasından değil.

    Sıra numarası kullanılsaydı parça (shard) sayısını değiştirmek tüm
    tahminleri değiştirirdi ve eski çıktılar yeniden üretilemezdi.
    """
    import pandas as pd

    d = pd.Timestamp("2023-02-06")
    assert simulation_seed(d) == simulation_seed(pd.Timestamp("2023-02-06"))
    assert simulation_seed(d) != simulation_seed(pd.Timestamp("2023-02-07"))
