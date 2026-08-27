"""Blok bootstrap'ın blok kurulumunun testleri.

Bu fonksiyon bir kurulumda doğru, başka bir kurulumda sessizce yanlış çalışıyordu:
bloklar takvim zamanından değil, benzersiz gün DİZİSİNDEKİ İNDİSTEN kuruluyordu.
Günlük başlangıçlarda 30 benzersiz gün = 30 takvim günü olduğu için doğru
görünüyordu; haftalık başlangıçlarda 30 benzersiz gün = 210 takvim günü ve
202 başlangıç yalnızca 7 bloğa düşüyordu.

Yedi bloklu bir bootstrap anlamlı aralık üretmez -- ve hiçbir hata vermez.
"""
import numpy as np
import pandas as pd

from src.eval.daily_backtest import BLOCK_DAYS, calendar_blocks


def test_daily_origins_give_calendar_blocks():
    """Günlük başlangıç, L=30 gün -> ~n/30 blok."""
    d = pd.Series(pd.date_range("2022-01-01", periods=1096, freq="D", tz="UTC"))
    b = calendar_blocks(d, BLOCK_DAYS)
    assert len(np.unique(b)) == 37


def test_weekly_origins_give_one_block_per_origin():
    """Haftalık örtüşmeyen başlangıç, L=7 gün -> her blok TEK başlangıç.

    Pencereler örtüşmediği için başlangıçlar bağımsızdır; blok yapısı bu durumda
    sıradan bootstrap'a döner ve bu DOĞRUDUR.
    """
    w = pd.Series(pd.date_range("2021-01-01", periods=202, freq="7D", tz="UTC"))
    b = calendar_blocks(w, 7)
    assert len(np.unique(b)) == 202


def test_block_count_does_not_depend_on_origin_spacing_bug():
    """Blok sayısı TAKVİM süresine bağlı olmalı, başlangıç sayısına değil.

    Aynı takvim aralığını kapsayan iki kurulum (günlük ve haftalık), aynı L ile
    yaklaşık aynı sayıda blok vermelidir. Eski indis tabanlı kurulumda haftalık
    kurulum yedi kat az blok veriyordu.
    """
    span_days = 700
    daily = pd.Series(pd.date_range("2021-01-01", periods=span_days, freq="D",
                                    tz="UTC"))
    weekly = pd.Series(pd.date_range("2021-01-01", periods=span_days // 7,
                                     freq="7D", tz="UTC"))
    nd = len(np.unique(calendar_blocks(daily, 30)))
    nw = len(np.unique(calendar_blocks(weekly, 30)))
    assert abs(nd - nw) <= 1, f"günlük {nd} blok, haftalık {nw} blok"


def test_blocks_are_contiguous_in_time():
    """Bir bloktaki başlangıçlar takvimde ardışık olmalı.

    Blok bootstrap'ın amacı zamansal bağımlılığı korumak; bloklar zamanda
    dağınıksa bu amaç boşa çıkar.
    """
    d = pd.Series(pd.date_range("2022-01-01", periods=200, freq="D", tz="UTC"))
    b = calendar_blocks(d, 30)
    for blk in np.unique(b):
        idx = np.flatnonzero(b == blk)
        assert np.array_equal(idx, np.arange(idx[0], idx[-1] + 1))


def test_bootstrap_ci_is_finite_with_many_blocks():
    """Çok bloklu kurulumda aralık üretilebilmeli."""
    from src.eval.daily_backtest import block_bootstrap

    rng = np.random.default_rng(0)
    n = 4000
    block_id = np.repeat(np.arange(200), n // 200)
    y = (rng.random(n) < 0.05).astype(int)
    a = rng.random(n)
    b = a + 0.3 * y + 0.1 * rng.random(n)
    mean, (lo, hi) = block_bootstrap(block_id, y, a, b, n_boot=200)
    assert np.isfinite(mean) and lo < hi
    assert lo > 0, "kurgu olarak b daha iyi; aralık sıfırın üstünde olmalı"
