"""SON DEPREMLER / TAHMİN KAYDI — iddia sınırının testleri.

Bu dosyanın konusu biçim değil, DÜRÜSTLÜKTÜR. Sınanan üç şey:

  1. "yayın yoktu" ile "listede yoktu" AYRI kalır (None vs False)
  2. hedef büyüklüğün altındaki olaylar öyle işaretlenir
  3. "bu bir skor değildir" beyanı çıktıda DURUR
"""
from __future__ import annotations

import json

import pandas as pd
import pytest

from tests.conftest import veri_gerekir, yayin_gerekir


def _sahte_olay(mag=5.0, lat=39.0, lon=35.0, zaman="2026-08-26 10:00:00+00:00"):
    return pd.Series({
        "time": pd.Timestamp(zaman), "lat": lat, "lon": lon,
        "mag": mag, "depth_km": 10.0, "source": "TEST",
    })


def test_yayin_yoksa_None_donar_False_DONMEZ(monkeypatch):
    """En kritik ayrım: yokluk, olumsuzluk DEĞİLDİR.

    Sistem 26 Ağustos 2026'da yayına başladı. Ondan önceki bir depremi
    'listede yoktu' diye göstermek, OLMAYAN BİR BAŞARISIZLIK uydurmak
    olurdu -- o gün ortada bir liste yoktu ki içinde olsun.
    """
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "_yayin_hucreleri", lambda tarih, gun=1: None)
    o = S._olay_kaydi(_sahte_olay(), {}, {})
    assert o["tahminde"] is None, "yayın yokken None dönmeli"
    assert o["tahminde"] is not False
    assert "yayın yoktu" in o["gerekce"]


def test_yayin_var_ama_hucre_yoksa_False_donar(monkeypatch):
    """Yayın yapıldı ve hücre listede değil: bu GERÇEK bir olumsuzluktur.

    Boş sözlük ({}) ile None arasındaki fark tam burada işler: yayın
    yapılmış ama eşik üstü hücre çıkmamışsa soru sorulabilir ve cevabı
    'hayır'dır.
    """
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "_yayin_hucreleri", lambda tarih, gun=1: {})
    o = S._olay_kaydi(_sahte_olay(), {}, {})
    assert o["tahminde"] is False
    assert "sıfır olduğu anlamına gelmez" in o["gerekce"]


def test_listede_varsa_kat_da_tasinir(monkeypatch):
    from src.operational import son_depremler as S
    from src.config import cell_id
    import numpy as np

    cid = int(cell_id(np.array([39.0]), np.array([35.0]))[0])
    monkeypatch.setattr(S, "_yayin_hucreleri",
                        lambda tarih, gun=1: {cid: {"times_normal": 7.3}})
    o = S._olay_kaydi(_sahte_olay(), {}, {})
    assert o["tahminde"] is True
    assert o["kat"] == 7.3


def test_hedef_buyuklugun_altindaki_olay_ISARETLENIR(monkeypatch):
    """Liste M4,5 için üretilir; M3,1'lik bir olayın eşleşmesi bilgi taşımaz.

    İşaretlenmezse arayüz onu 'listede vardı' diye gösterir ve okuyucu
    bunu tahminin tuttuğu sanır. Hedef dışı olmak, çıktının kendisinde
    yazılı olmalıdır.
    """
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "_yayin_hucreleri", lambda tarih, gun=1: {})
    assert S._olay_kaydi(_sahte_olay(mag=3.1), {}, {})["hedef_buyuklukte"] is False
    assert S._olay_kaydi(_sahte_olay(mag=4.5), {}, {})["hedef_buyuklukte"] is True
    assert S._olay_kaydi(_sahte_olay(mag=6.0), {}, {})["hedef_buyuklukte"] is True


@veri_gerekir
@yayin_gerekir
def test_iddia_siniri_CIKTIDA_durur():
    """'Bu bir skor değildir' beyanı üretilen dosyada bulunmak ZORUNDA.

    Beyan koddan silinirse bu test kırılır. Bir iddia sınırı, yalnızca
    yorumda değil ÇIKTIDA durmalıdır: dosyayı indiren biri de görmelidir.
    """
    from src.operational.son_depremler import son_depremler, tahmin_kaydi

    s = son_depremler(saat=6)
    assert "GELMEZ" in s["iddia_notu"]
    assert "olasılık bildirir" in s["iddia_notu"]

    k = tahmin_kaydi()
    assert "SKOR DEĞİLDİR" in k["not"]
    assert "eşik düşürülse" in k["not"]


@veri_gerekir
@yayin_gerekir
def test_sayim_alanlari_tutarli():
    """toplam = listede + listede_degil + yayin_yoktu — sessizce kaybolan yok."""
    from src.operational.son_depremler import tahmin_kaydi

    k = tahmin_kaydi()
    s = k["sayim"]
    assert s["toplam"] == s["listede"] + s["listede_degil"] + s.get("yayin_yoktu", 0)
