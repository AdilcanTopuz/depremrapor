"""Katalog CSV'leri için ortak okuma yardımcısı.

`pd.read_csv(..., parse_dates=["time"])` bu kataloglarda sessizce başarısız olur:
kayıtlar karışık zaman-damgası biçimleri (bazıları saniye kesirli, bazıları değil)
içerdiği için pandas kolonu `str` bırakır ve sonraki tarih karşılaştırmaları
`TypeError` verir. Tüm modüller tarih okumasını buradan yapar.
"""
from pathlib import Path

import numpy as np
import pandas as pd


def read_catalog(path: Path | str, time_col: str = "time") -> pd.DataFrame:
    """Katalog CSV'sini okur; `time_col`'u UTC-farkındalıklı datetime'a çevirir."""
    df = pd.read_csv(path, low_memory=False)
    df[time_col] = pd.to_datetime(df[time_col], utc=True, format="mixed", errors="coerce")
    return df.dropna(subset=[time_col])


def epoch_seconds(times) -> np.ndarray:
    """Datetime Series/Index -> epoch saniyesi (float64).

    `.astype("int64") / 1e9` KULLANMAYIN: pandas bu kataloglarda zaman çözünürlüğünü
    mikrosaniye (`us`) olarak seçer, nanosaniye değil — o bölme 1000 kat yanlış ölçek
    üretir. Ölçek her yerde aynı biçimde kaydığı için karşılaştırmalar doğru görünür,
    ama saniye cinsinden sabitlerle (pencere genişliği, dedup toleransı) karıştığı anda
    sessizce bozulur. Bu yardımcı, çözünürlüğü açıkça saniyeye sabitler.
    """
    if getattr(getattr(times, "dtype", None), "tz", None) is not None:
        times = times.dt.tz_localize(None) if hasattr(times, "dt") else times.tz_localize(None)
    values = times.to_numpy() if hasattr(times, "to_numpy") else np.asarray(times)
    return values.astype("datetime64[s]").astype("float64")
