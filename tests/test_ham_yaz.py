# -*- coding: utf-8 -*-
"""Ham katalog yazımının küçülmeye karşı korunması.

V38'de hattın kendi girdisini imha edebildiği görülmüş ve monotonluk
koruması eklenmişti -- ama o koruma YAYIM yolundaydı. Yapabildiği şey
yayımı durdurmaktı; yapamadığı şey, indiricinin iyi dosyanın üzerine
kırpılmış bir dosya yazmasını engellemekti.

28 Ağustos 2026'da tam bu oldu: KOERI sunucusu yılların çoğuna yanıt
vermedi, indirici eksikleri sessizce atladı, 19.339 satırı 72.473 satırlık
dosyanın üzerine yazdı ve 0 ile çıktı. Yayım korumadan döndü, ham dosya
gitti.

Ders: bir kaynağı korumak, onu KULLANAN yolu değil YAZAN yolu korumakla
olur.
"""
from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from src.ingest.ham_yaz import HamKatalogKuculdu, guvenli_yaz


def _n(yol: pathlib.Path) -> int:
    with yol.open("rb") as f:
        return max(sum(1 for _ in f) - 1, 0)


def test_ilk_yazim_serbest(tmp_path):
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(10)}), y)
    assert _n(y) == 10


def test_buyume_ve_esitlik_kabul(tmp_path):
    """Katalog güncellemesi doğal olarak büyür ya da aynı kalır."""
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(10)}), y)
    guvenli_yaz(pd.DataFrame({"a": range(25)}), y)
    assert _n(y) == 25
    guvenli_yaz(pd.DataFrame({"a": range(25)}), y)
    assert _n(y) == 25


def test_KUCULME_REDDEDILIR_ve_dosya_KORUNUR(tmp_path):
    """Kural 9: korumanın reddettiği VE dosyayı koruduğu gösterilir.

    Reddetmek tek başına yetmez -- reddederken dosyayı bozmuş olsaydı
    koruma zararlı olurdu.
    """
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(100)}), y)
    with pytest.raises(HamKatalogKuculdu) as e:
        guvenli_yaz(pd.DataFrame({"a": range(40)}), y)
    assert "100" in str(e.value) and "40" in str(e.value)
    assert _n(y) == 100, "reddetti ama dosyayı bozdu"


def test_bilincli_kucultme_MUMKUN_ama_sessiz_degil(tmp_path):
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(100)}), y)
    guvenli_yaz(pd.DataFrame({"a": range(40)}), y, izin_kucultme=True)
    assert _n(y) == 40


def test_BUTUN_indiriciler_bu_yoldan_yaziyor():
    """Koruma, yalnızca hatırlanan indiricide değil HEPSİNDE olmalı.

    Tek bir betik doğrudan `to_csv` çağırırsa koruma orada yoktur ve
    kusur oradan geri gelir.
    """
    kok = pathlib.Path(__file__).resolve().parents[1] / "scripts"
    for ad in ("01_download_afad.py", "02_download_usgs.py",
               "02b_download_emsc.py", "02c_download_koeri.py"):
        metin = (kok / ad).read_text(encoding="utf-8")
        assert "guvenli_yaz(" in metin, f"{ad}: korumadan geçmiyor"
        kod = "\n".join(s for s in metin.splitlines()
                        if not s.strip().startswith("#"))
        assert ".to_csv(" not in kod, \
            f"{ad}: ham katalogu doğrudan to_csv ile yazıyor"
