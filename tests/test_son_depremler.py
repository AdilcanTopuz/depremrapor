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


# --- İLERİ BAKIŞ (V-ilerleyen) --------------------------------------------
#
# Sicil, olayın kendi TARİHİNE ait yayına bakıyordu. O yayın sabah üretiliyor
# ve katalogunda o saate kadarki olaylar bulunuyordu; gece yarısından sonra
# olan bir deprem, KENDİSİNİ ZATEN GÖRMÜŞ bir listeyle karşılaştırılıyordu.
# Üstelik M4,5 bir olay hücrenin ETAS oranını yükselttiği için "listede
# vardı" sonucu neredeyse garantiydi -- ölçülen şey tahmin gücü değil, olayın
# kendisiydi.

def _sahte_yayin(kok, zaman_iso, hucreler):
    """Verilen üretim zamanıyla tek bir yayın dizini kurar."""
    ad = pd.Timestamp(zaman_iso).strftime("%Y-%m-%dT%H%M")
    d = kok / ad
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(
        json.dumps({"uretim_zamani": zaman_iso}), encoding="utf-8")
    (d / "forecast_1d_m45.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties":
                      {"cell_id": c, "times_normal": 3.0}} for c in hucreler],
    }), encoding="utf-8")
    return d


def test_olaydan_SONRA_uretilen_yayin_sayilmaz(tmp_path, monkeypatch):
    """Kural 9: ölçütün ileri bakışı gerçekten REDDETTİĞİ gösterilir.

    Aynı gün içinde iki yayın var: biri olaydan önce (hücre YOK), biri
    olaydan sonra (hücre VAR). Eski ölçüt gün eşleştirdiği için sonrakini
    de sayardı ve "listede vardı" derdi. Yeni ölçüt zamana bakar.
    """
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "PUBLISH", tmp_path)
    _sahte_yayin(tmp_path, "2026-08-27T03:30:00", hucreler=[])        # önce
    _sahte_yayin(tmp_path, "2026-08-27T09:30:00", hucreler=[4032])    # sonra

    olay = pd.Timestamp("2026-08-27T06:00:00")
    yayin = S._yayin_hucreleri(olay, gun=1)

    assert yayin is not None, "olaydan önce yayın vardı, None dönmemeli"
    assert 4032 not in yayin, (
        "İLERİ BAKIŞ: olaydan SONRA üretilmiş yayın sayılmış — "
        "bir tahmin, olaydan önce yayımlanmadıysa o olay hakkında "
        "hiçbir şey söyleyemez")


def test_olaydan_ONCEKI_yayin_sayilir(tmp_path, monkeypatch):
    """Aynı kurulumda, olaydan önceki yayında hücre varsa SAYILIR.

    Önceki test tek başına 'hiçbir şeyi saymayan' bir ölçütle de geçerdi.
    """
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "PUBLISH", tmp_path)
    _sahte_yayin(tmp_path, "2026-08-27T03:30:00", hucreler=[4032])
    _sahte_yayin(tmp_path, "2026-08-27T09:30:00", hucreler=[])

    yayin = S._yayin_hucreleri(pd.Timestamp("2026-08-27T06:00:00"), gun=1)
    assert yayin is not None and 4032 in yayin


def test_olaydan_once_hic_yayin_yoksa_None(tmp_path, monkeypatch):
    """'Yayın yoktu' ile 'listede yoktu' ayrımı zamanda da korunur."""
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "PUBLISH", tmp_path)
    _sahte_yayin(tmp_path, "2026-08-27T09:30:00", hucreler=[4032])
    assert S._yayin_hucreleri(pd.Timestamp("2026-08-27T06:00:00"), gun=1) is None


def test_ESKI_ad_bicimi_de_okunur(tmp_path, monkeypatch):
    """Devredilen arşiv YYYY-MM-DD adlıdır; sicil onları kaybetmemeli."""
    from src.operational import son_depremler as S

    monkeypatch.setattr(S, "PUBLISH", tmp_path)
    d = tmp_path / "2026-08-26"
    d.mkdir()
    (d / "manifest.json").write_text(
        json.dumps({"uretim_zamani": "2026-08-26T03:30:00"}), encoding="utf-8")
    (d / "forecast_1d_m45.geojson").write_text(json.dumps({
        "type": "FeatureCollection",
        "features": [{"type": "Feature",
                      "properties": {"cell_id": 4032, "times_normal": 2.5}}],
    }), encoding="utf-8")

    zamanlar = [t for t, _ in S._yayin_dizini()]
    assert len(zamanlar) == 1, "eski ad biçimindeki yayın görülmedi"
    yayin = S._yayin_hucreleri(pd.Timestamp("2026-08-26T12:00:00"), gun=1)
    assert yayin is not None and 4032 in yayin
