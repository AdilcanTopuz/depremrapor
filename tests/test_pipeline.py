"""Veri hattı korumaları — her biri REDDETTİĞİ bir deneyle gösterilir.

Kural 9: bir korumanın "kurulu" sayılması için reddettiği bir deney
gösterilmelidir. Bu dosyada beş koruma için beş ret, ve her ret için bir de
"geçerli durumda susuyor" karşılığı vardır — koruma her şeye ötmemeli.
"""
import json
import pathlib

import pandas as pd
import pytest

from src.operational import pipeline as P


# --- 1. KİRLİ AĞAÇ ---------------------------------------------------------

def test_kirli_agac_reddedilir(monkeypatch):
    monkeypatch.setattr("src.operational.forecast_now._fingerprint",
                        lambda: {"worktree": "dirty", "commit": "abc123"})
    with pytest.raises(P.KirliAgacHatasi):
        P.kontrol_agac()


def test_temiz_agac_gecer(monkeypatch):
    monkeypatch.setattr("src.operational.forecast_now._fingerprint",
                        lambda: {"worktree": "clean", "commit": "abc123"})
    assert P.kontrol_agac() == "abc123"


def test_kirli_agac_bilincli_izinle_gecer(monkeypatch):
    """--allow-dirty bilinçli bir karardır; künye 'dirty' damgası taşır."""
    monkeypatch.setattr("src.operational.forecast_now._fingerprint",
                        lambda: {"worktree": "dirty", "commit": "abc123"})
    assert P.kontrol_agac(izin_ver=True) == "abc123"


# --- 2. BAYAT KATALOG ------------------------------------------------------
#
# EN TEHLİKELİ SESSİZ HATA: AFAD çekme başarısız olur, katalog eskir, tahmin
# ESKİ VERİYLE üretilir. Çıktı normal görünür, künye doğrudur, veri bayattır.

def _sahte_katalog(monkeypatch, son: pd.Timestamp):
    monkeypatch.setattr(P.PROC.__class__, "exists", lambda self: True)
    monkeypatch.setattr("src.ingest.catalog_io.read_catalog",
                        lambda *a, **k: pd.DataFrame({"time": [son]}))


def test_bayat_katalog_reddedilir(monkeypatch):
    simdi = pd.Timestamp("2026-08-26 12:00", tz="UTC")
    _sahte_katalog(monkeypatch, simdi - pd.Timedelta(hours=100))
    with pytest.raises(P.BayatKatalogHatasi):
        P.kontrol_katalog_tazeligi(simdi=simdi)


def test_taze_katalog_gecer(monkeypatch):
    simdi = pd.Timestamp("2026-08-26 12:00", tz="UTC")
    _sahte_katalog(monkeypatch, simdi - pd.Timedelta(hours=3))
    r = P.kontrol_katalog_tazeligi(simdi=simdi)
    assert r["yas_saat"] == pytest.approx(3.0, abs=0.01)


# --- 3. ŞEMA ---------------------------------------------------------------

def _gecerli_gj():
    """ÖLÇÜLMÜŞ şema — data/operational/*.geojson'dan okundu, varsayılmadı."""
    return {
        "type": "FeatureCollection",
        "properties": {
            "origin": "2026-08-26T00:00:00Z", "window_days": 7,
            "target_magnitude": 4.5, "model": "ETAS", "mode": "live",
            "fingerprint": {"method": "analytic-branching",
                            "etas_params_sha256": "ab" * 32,
                            # V37: katalog künyesi ZORUNLU -- dondurulmuş
                            # sonucun dondurulmamış zemini olmasın
                            "catalog_sha256": "cd" * 32,
                            "catalog_last_event": "2026-08-26 06:53:43",
                            "commit": "abc123", "worktree": "clean",
                            "randomness": "none"},
            # V43: kapsam alanı ZORUNLU -- ölçemediğimiz yerde konuşmayız
            "kapsam": {"izgara_hucre": 2560, "kapsam_disi_elenen": 1450,
                       "sinir_kaynagi": "Natural Earth 10m admin-0",
                       "tampon_derece": 0.125},
            "min_times_normal": 2.0, "cells_before_threshold": 1110,
            "cells_published": 299,
            "disclaimer": "Bu bir olasılık beyanıdır; kesinlik iddiası değil.",
        },
        "features": [{"type": "Feature", "properties": {
            "cell_id": 1234, "probability": 0.012, "expected_events": 0.012,
            "normal_probability": 0.004, "times_normal": 3.1}}],
    }


def test_kunyesiz_gj_reddedilir():
    gj = _gecerli_gj()
    del gj["properties"]["fingerprint"]
    with pytest.raises(P.SemaHatasi):
        P.kontrol_sema(gj)


def test_kirli_kunye_reddedilir():
    """Künyede 'dirty' damgası varsa yayım durur -- ikinci savunma hattı."""
    gj = _gecerli_gj()
    gj["properties"]["fingerprint"]["worktree"] = "dirty"
    with pytest.raises(P.SemaHatasi, match="dirty"):
        P.kontrol_sema(gj)


def test_bos_features_reddedilir():
    gj = _gecerli_gj()
    gj["features"] = []
    with pytest.raises(P.SemaHatasi):
        P.kontrol_sema(gj)


def test_eksik_hucre_alani_reddedilir():
    gj = _gecerli_gj()
    del gj["features"][0]["properties"]["times_normal"]
    with pytest.raises(P.SemaHatasi, match="hücre alanları eksik"):
        P.kontrol_sema(gj)


def test_uyari_metni_zorunlu():
    gj = _gecerli_gj()
    gj["properties"]["disclaimer"] = "   "
    with pytest.raises(P.SemaHatasi, match="uyarı"):
        P.kontrol_sema(gj)


def test_gecerli_gj_gecer():
    r = P.kontrol_sema(_gecerli_gj())
    assert r["n_hucre"] == 1 and r["yayimlanan"] == 299


# --- 4. KESİNLİK DİLİ ------------------------------------------------------

@pytest.mark.parametrize("metin", [
    "Yarın İstanbul'da deprem olacak.",
    "Bu bölgede KESİNLİKLE hareket bekleniyor.",
    "Sonuç garanti edilmektedir.",
])
def test_kesinlik_dili_reddedilir(metin):
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(metin)


def test_olasilik_dili_gecer():
    P.kontrol_dil(
        "Önümüzdeki 7 günde bu hücrede M>=4,5 olay olasılığı %1,2'dir; "
        "uzun vadeli ortalamanın 3,1 katı. Bu bir olasılık beyanıdır.")


# --- 5. HÜCRE SAYISI BANDI -------------------------------------------------

def test_bandin_disi_reddedilir():
    with pytest.raises(P.EsikHatasi):
        P.kontrol_hucre_sayisi(5)
    with pytest.raises(P.EsikHatasi):
        P.kontrol_hucre_sayisi(5000)


def test_bandin_ici_gecer():
    P.kontrol_hucre_sayisi(299)


# --- 6. KORUMALAR YAYIMI DURDURUR, UYARMAKLA KALMAZ ------------------------

def test_butun_korumalar_yayimhatasi_altinda():
    """Hepsi tek bir üst tipten türer: cron tek yakalamayla durabilsin."""
    for tip in (P.KirliAgacHatasi, P.BayatKatalogHatasi, P.SemaHatasi,
                P.DilHatasi, P.EsikHatasi):
        assert issubclass(tip, P.YayimHatasi)


# --- 4b. TÜRKÇE BÜYÜK HARF KÖRLÜĞÜ (V33) -----------------------------------
#
# Koruma ilk sürümde str.lower() kullanıyordu ve BÜYÜK HARFLİ TÜRKÇE metne
# KÖRDÜ: 'İ'.lower() -> 'i' + BİRLEŞEN NOKTA (U+0307), "kesinlikle" ile
# eşleşmiyor. Yasak kelime taraması, en yüksek sesle yazılmış ihlali
# kaçırıyordu.

@pytest.mark.parametrize("metin", [
    "KESİNLİKLE deprem olacak",
    "KESİN sonuç",
    "GARANTİ ediyoruz",
    "Deprem OLACAK",
])
def test_buyuk_harfli_turkce_ihlal_yakalanir(metin):
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(metin)


def test_tr_kucult_dogru_esliyor():
    assert P.tr_kucult("KESİNLİKLE") == "kesinlikle"
    assert P.tr_kucult("IRAK") == "ırak"
    assert "\u0307" not in P.tr_kucult("İSTANBUL")


# --- 4c. ONAYLI UYARI METNİ MUAFİYETİ (V35) --------------------------------
#
# Uyarı metni kesinliği REDDEDER ve zorunlu olarak yasak kelime içerir
# ("kesin deprem tahmini DEĞİLDİR"). Muafiyet DESENE değil KİMLİĞE verilir:
# onaylı metnin sha256'sı sabittir.

# METİN BURAYA KOPYALANMAZ (V52 dersi: elle yazılan liste kaynaktan kayar).
# Testin kopyası olsaydı, kaynaktaki metin değişip hash güncellenmediğinde
# test YİNE GEÇERDİ -- yani korumanın bozulduğunu göstermezdi. Tek kaynak:
from src.operational.forecast_now import DISCLAIMER as ONAYLI


def test_onayli_uyari_metni_muaf():
    """Onaylı metin, içinde yasak kelime olmasına rağmen geçer."""
    P.kontrol_dil(f'{{"disclaimer": "{ONAYLI}"}}')


def test_muafiyet_KIMLIGE_verilir_desene_degil():
    """'değildir' ekleyerek muafiyet KAZANILAMAZ.

    Sezgisel bir olumsuzlama kuralı olsaydı, ihlali "değildir" ekleyerek
    gizlemek mümkün olurdu. Muafiyet hash'e bağlı olduğu için bu yol kapalı.
    """
    sahte = ONAYLI.replace("OLASILIK tahminidir", "KESİN tahmindir")
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(f'{{"disclaimer": "{sahte}"}}')


def test_onayli_metin_disindaki_ihlal_yakalanir():
    """Muafiyet yalnızca onaylı metni kapsar; gerisi sıkı taranır."""
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(f'{{"disclaimer": "{ONAYLI}", "not": "deprem olacak"}}')


def test_muafiyet_kapatilabilir():
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(f'{{"d": "{ONAYLI}"}}', uyari_muafiyeti=False)


# --- 7. KATALOG KÜNYESİ ZORUNLU (V37) --------------------------------------

def test_katalog_kunyesi_zorunlu():
    """Katalog sha'sı olmayan künye reddedilir.

    V37: künye zinciri parametreleri kapsıyordu, KATALOGU kapsamıyordu.
    Dondurulmuş bir değerlendirme tablosunun dondurulmamış bir zemini vardı
    ve yeniden üretilemediğinde sebep DOĞRUDAN SINANAMADI.
    """
    from tests.test_pipeline import _gecerli_gj as _g
    for alan in ("catalog_sha256", "catalog_last_event"):
        gj = _g()
        del gj["properties"]["fingerprint"][alan]
        with pytest.raises(P.SemaHatasi, match="künye alanları eksik"):
            P.kontrol_sema(gj)


# --- 8. GİRDİ BÜTÜNLÜĞÜ: KATALOG KÜÇÜLMEZ (V38) ----------------------------
#
# Bugüne kadar bütün korumalar YAYIN yönüne bakıyordu. Hattın KENDİ GİRDİSİNİ
# imha edebileceği senaryo haritada yoktu -- ve 26 Ağu 2026'da tam bu oldu:
# update_catalog üç kaynağın ham dosyalarını yalnızca son yılla üzerine yazdı
# (AFAD 265.572 -> 4.713). Koruma bu asimetriyi kapatır.

def test_katalog_kuculmesi_reddedilir(tmp_path, monkeypatch):
    """Güncelleme sonrası ham dosya küçülürse DURULUR."""
    from src.operational import forecast_now as F

    ham = tmp_path / "raw"
    ham.mkdir()
    for ad in ("afad_catalog.csv", "koeri_catalog.csv", "emsc_catalog.csv"):
        (ham / ad).write_text("time,lat,lon,mag\n" + "x\n" * 1000,
                              encoding="utf-8")
    monkeypatch.setattr(F, "PROC", tmp_path / "processed")
    monkeypatch.setattr(F, "ROOT", tmp_path)  # yayın referansı da yalıtılır
    (tmp_path / "processed").mkdir()

    def sahte_indir(cmd, **kw):
        # HASAR: dosyaları 10 satıra düşür (gerçek hatanın birebir taklidi)
        for ad in ("afad_catalog.csv", "koeri_catalog.csv", "emsc_catalog.csv"):
            (ham / ad).write_text("time,lat,lon,mag\n" + "x\n" * 10,
                                  encoding="utf-8")

        class R:
            returncode = 0
            stdout = stderr = ""
        return R()

    import subprocess as _sp
    monkeypatch.setattr(_sp, "run", sahte_indir)
    monkeypatch.setattr("src.ingest.catalog_io.read_catalog",
                        lambda *a, **k: pd.DataFrame(
                            {"time": [pd.Timestamp("2026-08-26", tz="UTC")]}))
    with pytest.raises(F.KatalogKuculdu, match="KÜÇÜLDÜ"):
        F.update_catalog(quiet=True)


def test_kucultme_bilincli_izinle_gecer(tmp_path, monkeypatch):
    """Bilinçli temizlik bayrakla geçer -- koruma mutlak engel değil."""
    from src.operational import forecast_now as F

    ham = tmp_path / "raw"
    ham.mkdir()
    (ham / "afad_catalog.csv").write_text("a\n" + "x\n" * 1000, encoding="utf-8")
    monkeypatch.setattr(F, "PROC", tmp_path / "processed")
    monkeypatch.setattr(F, "ROOT", tmp_path)  # yayın referansı da yalıtılır
    (tmp_path / "processed").mkdir()

    class R:
        returncode = 0
        stdout = stderr = ""

    def sahte(cmd, **kw):
        (ham / "afad_catalog.csv").write_text("a\n" + "x\n" * 10,
                                              encoding="utf-8")
        return R()

    import subprocess as _sp
    monkeypatch.setattr(_sp, "run", sahte)
    monkeypatch.setattr("src.ingest.catalog_io.read_catalog",
                        lambda *a, **k: pd.DataFrame(
                            {"time": [pd.Timestamp("2026-08-26", tz="UTC")]}))
    F.update_catalog(quiet=True, izin_kucultme=True)   # hata VERMEMELİ


def test_kucuk_dalgalanma_gecer(tmp_path, monkeypatch):
    """%5 tolerans: kaynak revizyonu birkaç satır eksiltebilir, durmamalı."""
    from src.operational import forecast_now as F

    ham = tmp_path / "raw"
    ham.mkdir()
    (ham / "afad_catalog.csv").write_text("a\n" + "x\n" * 1000, encoding="utf-8")
    monkeypatch.setattr(F, "PROC", tmp_path / "processed")
    monkeypatch.setattr(F, "ROOT", tmp_path)  # yayın referansı da yalıtılır
    (tmp_path / "processed").mkdir()

    class R:
        returncode = 0
        stdout = stderr = ""

    def sahte(cmd, **kw):
        (ham / "afad_catalog.csv").write_text("a\n" + "x\n" * 980,
                                              encoding="utf-8")
        return R()

    import subprocess as _sp
    monkeypatch.setattr(_sp, "run", sahte)
    monkeypatch.setattr("src.ingest.catalog_io.read_catalog",
                        lambda *a, **k: pd.DataFrame(
                            {"time": [pd.Timestamp("2026-08-26", tz="UTC")]}))
    F.update_catalog(quiet=True)


# --- 9. ÜRÜN KAPISI (site şartnamesi) --------------------------------------

def test_kapi_bant_disini_reddeder():
    """Kalibrasyon bandın dışındaysa model operasyonel katmana ALINMAZ."""
    from src.operational.urun_kapisi import KapiKapali, kontrol

    r = kontrol("SahteML", gozlenen=252, beklenen=138.8)   # oran 1,82 (LGBM)
    assert not r["gecti"] and r["oran"] > 1.25
    r2 = kontrol("SahteNPP", gozlenen=252, beklenen=165.4)  # oran 1,52 (NPP)
    assert not r2["gecti"]


def test_kapi_bant_icini_gecirir():
    from src.operational.urun_kapisi import kontrol

    r = kontrol("ETAS", gozlenen=252, beklenen=231.5)       # oran 1,089
    assert r["gecti"] and 0.80 <= r["oran"] <= 1.25


def test_kapi_tanimsiz_orani_reddeder():
    """beklenen=0 -> oran TANIMSIZ; tanımsız GEÇERLİ değildir (V40)."""
    from src.operational.urun_kapisi import KapiKapali, kontrol

    with pytest.raises(KapiKapali, match="tanımsız"):
        kontrol("Bos", gozlenen=252, beklenen=0.0)


def test_kapi_olcumu_yoksa_yayim_yok(tmp_path, monkeypatch):
    """Ölçüm dosyası yoksa yayım YAPILMAZ -- varsayılan 'geç' değil 'dur'."""
    from src.operational import urun_kapisi as U

    monkeypatch.setattr(U, "PROC", tmp_path)
    with pytest.raises(U.KapiKapali, match="kapı ölçümü olmadan"):
        U.operasyonel_model_kontrolu("ETAS")


def test_kapi_esikleri_ilan_edildigi_gibi():
    from src.operational.urun_kapisi import BAND

    assert BAND == (0.80, 1.25)


# --- 10. BÖLGE KARTLARI: yokluğun BEYANI ------------------------------------

def test_esik_ustu_hucresi_olmayan_bolge_ATLANMAZ(monkeypatch, tmp_path):
    """Bölgede hücre yoksa kart onu atlamaz, AÇIKÇA beyan eder.

    Satırın olmaması, okuyucuya "veri yok" ile "risk yok" arasında ayrım
    bırakmaz; ikisi farklı ifadelerdir.
    """
    from src.operational import bolge_kartlari as B

    monkeypatch.setattr(B, "bulgu_oku", lambda: {
        "kunye": {"uretim": "x", "kaynak_tablo": "t", "tablo_sha256": "a" * 64,
                  "katalog_sha256": "b" * 64, "etas_params_sha256": "c" * 64},
        "donem": "x", "pencere_gun": 7, "hedef_mw": 4.5, "tablo": "t",
        "n_olay": 10, "uyari": "u",
        "bolgeler": {"A": {"olay": 9, "hukum": "ETAS üstün", "ig": 1.0,
                           "ga": [0.5, 1.5], "mde": 0.4},
                     "B": {"olay": 3, "hukum": "olay sayısı yetersiz",
                           "ig": None, "ga": None, "mde": None}}})
    monkeypatch.setattr(B, "guncel", lambda *a, **k: {
        "origin": "2026-08-26", "pencere_gun": 7, "hedef_mw": 4.5, "esik": 2.0,
        "kunye": {}, "varsayim": "v",
        "bolgeler": {"A": {"yayimlanan_hucre": 5, "bolge_olasiligi": 0.01,
                           "en_yuksek_hucre_p": 0.004, "en_yuksek_kat": 3.1}}})

    k = B.kartlar(tmp_path / "x.geojson")
    assert set(k["bolgeler"]) == {"A", "B"}, "bölge ATLANDI"
    b = k["bolgeler"]["B"]["guncel"]
    assert b["yayimlanan_hucre"] == 0
    assert b["bolge_olasiligi"] is None      # SIFIR değil, TANIMSIZ
    assert "eşik üstü hücre YOK" in b["beyan"]


def test_bos_bolgede_olasilik_SIFIR_degil_TANIMSIZ(monkeypatch, tmp_path):
    """Eşik üstü hücre yokluğu, 'olasılık sıfır' demek DEĞİLDİR (V40 ailesi).

    Eşiğin altındaki hücrelerde de olasılık vardır; yalnızca yayımlanmazlar.
    """
    from src.operational import bolge_kartlari as B

    monkeypatch.setattr(B, "bulgu_oku", lambda: {
        "kunye": {"uretim": "x", "kaynak_tablo": "t", "tablo_sha256": "a" * 64,
                  "katalog_sha256": "b" * 64, "etas_params_sha256": "c" * 64},
        "donem": "x", "pencere_gun": 7, "hedef_mw": 4.5, "tablo": "t",
        "n_olay": 1, "uyari": "u", "bolgeler": {"Z": {"olay": 1,
                                                      "hukum": "olay sayısı yetersiz",
                                                      "ig": None, "ga": None,
                                                      "mde": None}}})
    monkeypatch.setattr(B, "guncel", lambda *a, **k: {
        "origin": "2026-08-26", "pencere_gun": 7, "hedef_mw": 4.5, "esik": 2.0,
        "kunye": {}, "varsayim": "v", "bolgeler": {}})
    z = B.kartlar(tmp_path / "x.geojson")["bolgeler"]["Z"]["guncel"]
    assert z["bolge_olasiligi"] is None and z["yayimlanan_hucre"] == 0


# --- 11. YAYIN KAPSAMI (V43) ------------------------------------------------
#
# Izgara dikdörtgendir ve komşu ülkeleri içerir. Katalog tamlığı sınır dışında
# ÖLÇÜLMÜŞ biçimde düşüktür; temel oran düşük kestirilir ve "normalin kaç
# katı" şişer. Yayımlanan 309 hücrenin %64'ü kapsam dışıydı.

@pytest.mark.parametrize("ad,lat,lon", [
    ("Ankara", 39.93, 32.86), ("İstanbul", 41.01, 28.98),
    ("Van", 38.50, 43.38), ("Antalya", 36.90, 30.70),
])
def test_turkiye_icindeki_noktalar_kapsamda(ad, lat, lon):
    from src.operational.kapsam import icinde
    assert icinde(lat, lon), ad


@pytest.mark.parametrize("ad,lat,lon", [
    ("Kerkük", 35.47, 44.39), ("Halep", 36.20, 37.16),
    ("Atina", 37.98, 23.73), ("Tebriz", 38.08, 46.29),
    ("Sofya", 42.70, 23.32), ("Batum", 41.64, 41.64),
])
def test_turkiye_disindaki_noktalar_KAPSAM_DISI(ad, lat, lon):
    """Koruma REDDEDİYOR — en yüksek oranlı hücre (Kerkük, 82,4 kat) dâhil."""
    from src.operational.kapsam import icinde
    assert not icinde(lat, lon), ad


def test_sinir_yoksa_yayim_yok(tmp_path, monkeypatch):
    """Sınır dosyası yoksa DURULUR -- varsayılan 'hepsini yayımla' değil."""
    from src.operational import kapsam as K

    monkeypatch.setattr(K, "SINIR_YOLU", tmp_path / "yok.geojson")
    with pytest.raises(K.KapsamHatasi, match="sınır olmadan"):
        K.icinde(39.93, 32.86)


def test_kapsam_kunyesi_kaynagi_tasiyor():
    from src.operational.kapsam import kunye

    k = kunye()
    for alan in ("sinir_kaynagi", "lisans", "kaynak_sha256", "sinir_sha256",
                 "tampon_derece", "gerekce"):
        assert k.get(alan), alan


# --- 4d. SÖZCÜK SINIRI (V44) -----------------------------------------------
#
# Naif alt dize eşleşmesi "tehlikesinin" içinde `kesin` buluyordu ve
# yazılması ZORUNLU bir cümleyi engelledi. Türkçe eklemeli bir dil: kalıp
# sözcüğün BAŞINDA olmalı, sonrasına ek gelebilir.

@pytest.mark.parametrize("metin", [
    "deprem tehlikesinin düşük olduğu anlamına gelmez",
    "bölgedeki tehlikesi yüksektir",
    "ölçüm eksiksiz değildir",
    "veri seti eksiktir",
])
def test_yanlis_pozitif_YOK(metin):
    """Yasak kalıbı ALT DİZE olarak içeren masum kelimeler geçmeli."""
    P.kontrol_dil(metin)


@pytest.mark.parametrize("metin", [
    "kesin tahmin",
    "kesinlikle olacak",
    "sonuç kesindir",
    "deprem olacak",
    "garanti veriyoruz",
    "KESİNLİKLE deprem",
])
def test_gercek_ihlaller_HALA_yakalaniyor(metin):
    """Düzeltme bir GEVŞETME değil: aynı ihlaller yakalanmaya devam eder."""
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(metin)


# --- 4e. KOŞULLU KALIPLAR (V46) ---------------------------------------------
#
# Çıplak "olacak" koşulsuz yasaklıydı ve MEŞRU cümleleri reddetti
# ("taranmış olacak", "lazım olacak satır budur"). Kalıp SİLİNMEDİ,
# KOŞULA BAĞLANDI: deprem bağlamında geçerse hâlâ ihlal.

@pytest.mark.parametrize("metin", [
    "her tekil bulgunun sınıfı taranmış olacak",
    "koruyucular var derken lazım olacak satır budur",
    "bu ölçüm bir sonraki pakette yapılmış olacak",
    "sonuç raporda görünür olacak",
])
def test_deprem_disi_baglamda_olacak_GECER(metin):
    P.kontrol_dil(metin)


@pytest.mark.parametrize("metin", [
    "yarın İstanbul'da deprem olacak",
    "bu fay hattında büyük bir sarsıntı olacak",
    "önümüzdeki hafta deprem olacağı öngörülüyor",
    "artçılar yarın duracak ve ana şok olacak",
    "DEPREM OLACAK",
])
def test_deprem_baglaminda_olacak_YAKALANIR(metin):
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil(metin)


def test_kosulsuz_kaliplar_baglamsiz_yakalanir():
    """Kesinlik iddiasının kendisi, bağlam gerektirmez."""
    for m in ("kesin sonuç", "kesinlikle", "garanti ediyoruz"):
        with pytest.raises(P.DilHatasi):
            P.kontrol_dil(m)


# --- 4f. KULLANIM / ANMA (V48) ----------------------------------------------

def test_belge_sayfalari_kapsam_disi_ve_LISTELI():
    """Kapsam dışı sayfalar AÇIKÇA listelenmiş olmalı -- sessiz atlama YOK."""
    from src.operational.belge_sayfa import BELGELER

    assert set(BELGELER) == {"vaka-defteri.html", "denetim-mirasi.html"}


def test_tahmin_sunan_sayfa_kapsam_disi_DEGIL():
    """index ve metodoloji muaf olmamalı -- onlar tahmin sunar."""
    from src.operational.belge_sayfa import BELGELER

    for s in ("index.html", "metodoloji.html"):
        assert s not in BELGELER


def test_kalip_ANMA_hala_ihlal_sayilir_yayin_sayfasinda():
    """Muafiyet SAYFAYA verilir, cümleye değil: yayın sayfasında anma da ihlal.

    Bu kasıtlıdır -- yayın sayfasında bir ihlali 'örneklemek' için meşru
    sebep yoktur; belge sayfasında vardır.
    """
    with pytest.raises(P.DilHatasi):
        P.kontrol_dil("Örnek yasak cümle: 'deprem olacak'.")


# --- 12. DONDURULMUŞ BULGU (Actions taşıması, adım 1) -----------------------

def test_bulgu_dosyasi_yoksa_kart_uretilmez(tmp_path, monkeypatch):
    """Bulgu yoksa DURULUR -- varsayılan 'katman 1'i atla' değil."""
    from src.operational import bolge_kartlari as B

    monkeypatch.setattr(B, "BULGU_YOLU", tmp_path / "yok.json")
    with pytest.raises(B.BulguYok, match="bulgu olmadan"):
        B.bulgu_oku()


def test_kunyesiz_bulgu_reddedilir(tmp_path, monkeypatch):
    """Dondurulmuş bir eser bayatlayabilir; künyesiz dosya OKUNMAZ."""
    from src.operational import bolge_kartlari as B

    y = tmp_path / "b.json"
    y.write_text(json.dumps({"bolgeler": {}, "kunye": {"uretim": "2026-08-26"}}),
                 encoding="utf-8")
    monkeypatch.setattr(B, "BULGU_YOLU", y)
    with pytest.raises(B.BulguYok, match="künyesi eksik"):
        B.bulgu_oku()


def test_gecerli_bulgu_okunur():
    """Gerçek dosya okunuyor ve künyesi tam."""
    from src.operational.bolge_kartlari import bulgu_oku

    b = bulgu_oku()
    assert b["n_olay"] == 252 and len(b["bolgeler"]) == 6
    for a in ("tablo_sha256", "katalog_sha256", "etas_params_sha256"):
        assert len(b["kunye"][a]) == 64


# --- 13. MONOTONLUK REFERANSI YAYIN KAYDINDA (Actions taşıması, adım 3) -----
#
# İLKE: bir koruma, kendi ön koşulunu DIŞARIDAN (önbellek, yerel durum)
# almamalıdır. Taze checkout'lu bir ortamda yerel "önceki durum" yoktur ve
# koruma SESSİZCE GEÇERDİ -- V15'in uyardığı durum.

def test_yayin_referansi_kunyeden_okunur(tmp_path, monkeypatch):
    from src.operational import forecast_now as F

    d = tmp_path / "data" / "publish" / "latest"
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps(
        {"ham_satir_sayilari": {"afad_catalog.csv": 265572}}), encoding="utf-8")
    monkeypatch.setattr(F, "ROOT", tmp_path)
    assert F._yayin_referansi()["afad_catalog.csv"] == 265572


def test_yayin_kaydi_yoksa_bos_doner(tmp_path, monkeypatch):
    """Kayıt yoksa BOŞ döner -- uydurma referans üretilmez."""
    from src.operational import forecast_now as F

    monkeypatch.setattr(F, "ROOT", tmp_path)
    assert F._yayin_referansi() == {}


def test_manifest_ham_sayilari_tasiyor():
    """Yayımlanmış manifest, bir sonraki koşunun referansını içermeli."""
    y = pathlib.Path("data/publish/latest/manifest.json")
    if not y.exists():
        pytest.skip("henüz yayın yok")
    m = json.loads(y.read_text(encoding="utf-8"))
    h = m.get("ham_satir_sayilari")
    assert h and h.get("afad_catalog.csv", 0) > 100000


# --- 14. TAZELİK SÖZLEŞMESİ (Actions taşıması, adım 4) ---------------------

def test_bayatlik_esigi_ilan_edildigi_gibi():
    """İlan edilmiş kadans ve eşik; sessizce kaymasınlar diye sabitlenir."""
    assert P.YAYIN_ARALIGI_SAAT == 3 and P.BAYAT_YAYIN_ESIGI_SAAT == 7


def test_esik_BIR_atlamayi_tolere_eder_IKINCISINDE_uyarir():
    """Sayılar keyfî değil, ilan edilmiş kuralın sonucudur.

    Kural: bir koşunun atlanması yayını geçersiz kılmaz, ikincisi kılar.
    Sayılar değişirse bu ilişki de sınanmış olur -- yalnızca iki sabitin
    eşleşmesi, aralarındaki gerekçenin korunduğunu göstermez.
    """
    a, esik = P.YAYIN_ARALIGI_SAAT, P.BAYAT_YAYIN_ESIGI_SAAT
    assert esik > 2 * a, "bir atlama tolere edilmiyor"
    assert esik < 3 * a, "iki atlama da tolere ediliyor -- eşik çok gevşek"


def test_manifest_tazelik_sozlesmesi_tasiyor():
    """Bayatlık MAKİNE-OKUNUR olmalı: izleme aracı da görebilsin."""
    y = pathlib.Path("data/publish/latest/manifest.json")
    if not y.exists():
        pytest.skip("henüz yayın yok")
    t = json.loads(y.read_text(encoding="utf-8")).get("tazelik")
    assert t, "tazelik sözleşmesi YOK"
    for a in ("uretim_zamani", "sonraki_beklenen", "yayin_araligi_saat",
              "bayatlik_esigi_saat"):
        assert t.get(a), a
    # SABİT SAYI YAZILMAZ: yayımlanan değer, KODDA İLAN EDİLENLE
    # karşılaştırılır. Sabit yazılsaydı, kod ile yayın arasındaki kayma
    # ancak biri elle güncellenirse görülürdü.
    assert t["bayatlik_esigi_saat"] == P.BAYAT_YAYIN_ESIGI_SAAT
    assert t["yayin_araligi_saat"] == P.YAYIN_ARALIGI_SAAT


# --- KURAL 9: kalibre parametre koruması reddediyor mu (V49) --------------

def test_kalibre_parametre_korumasi_dosya_yoksa_REDDEDER(tmp_path, monkeypatch):
    """Dosya yoksa yayım DURUR -- sessizce b=1,0'a düşmez.

    V49: `.gitignore` istisnası yanlış dosya adını yazıyordu ve
    `mc_by_period.csv` depoya hiç girmemişti. Taze checkout'lu bir bulut
    koşusu DÜŞMEZDİ; çalışır, künyesi doğru olur ve 'normalin kaç katı'
    alanı ~%5 kaymış olurdu. Koruma tam bunu keser.
    """
    from src.operational import pipeline as P

    monkeypatch.setattr("src.config.PROC", tmp_path)  # boş dizin = dosya yok
    with pytest.raises(P.ParametreHatasi) as e:
        P.kontrol_kalibre_parametreler()
    assert "mc_by_period.csv" in str(e.value)
    assert "1.0" in str(e.value) or "1,0" in str(e.value)


def test_kalibre_parametre_korumasi_b_bir_ise_REDDEDER(tmp_path, monkeypatch):
    """b tam 1,0 ise varsayılana düşülmüş olabilir -- yine reddedilir.

    İkinci ağ: dosya VAR ama içeriği varsayılanla ayırt edilemez bir b
    veriyorsa, koruma yine durur. Bir koruma yalnızca dosya varlığına
    bakarsa, boş/bozuk bir dosya onu sessizce geçirir.
    """
    from src.operational import pipeline as P

    (tmp_path / "mc_by_period.csv").write_text("x", encoding="utf-8")
    monkeypatch.setattr("src.config.PROC", tmp_path)
    monkeypatch.setattr("src.config.load_mc_and_b", lambda *a, **k: (3.3, 1.0))
    with pytest.raises(P.ParametreHatasi) as e:
        P.kontrol_kalibre_parametreler()
    assert "1,045" in str(e.value)


def test_kalibre_parametre_korumasi_GERCEK_veriyle_GECER():
    """Gevşetme testi: koruma, gerçek kalibre dosyayla geçmeli.

    Ret deneyi tek başına yeterli değil -- her şeyi reddeden bir koruma da
    testi geçerdi. Bu test korumanın SADECE yanlışı kestiğini gösterir.
    """
    from src.operational.pipeline import kontrol_kalibre_parametreler

    par = kontrol_kalibre_parametreler()
    assert abs(par["b"] - 1.045) < 0.01, par
    assert par["kaynak"] == "mc_by_period.csv"


# --- KORUMA LİSTESİ KODDAN AYRIŞAMAZ (V52) -------------------------------

def test_koruma_listesi_KODLA_AYNI():
    """İlan edilen koruma listesi, koddaki koruma istisnalarıyla AYNI KÜME.

    V52: künyedeki liste ELLE yazılmıştı ve altı koruma sayıyordu; sistemde
    dokuz vardı. Monotonluk, kapsam ve kalibre parametreler listeye hiç
    girmemişti. O liste siteye çıkacaktı -- yani yanlış bir koruma listesi
    yayımlanacaktı.

    SAYI DEĞİL KÜME karşılaştırılır: eşit sayıda ama farklı elemanlı iki
    liste, sayı kontrolünden geçerdi.
    """
    import ast
    import pathlib

    from src.operational.pipeline import KORUMALAR

    kok = pathlib.Path(__file__).resolve().parents[1] / "src" / "operational"
    bulunan = set()
    for ad, dosya in (("pipeline", "pipeline.py"),
                      ("forecast_now", "forecast_now.py"),
                      ("kapsam", "kapsam.py")):
        t = ast.parse((kok / dosya).read_text(encoding="utf-8"))
        for n in t.body:
            if not isinstance(n, ast.ClassDef):
                continue
            # KORUMA İSTİSNASI KİMLİĞİYLE TANINIR, ADIYLA DEĞİL.
            #
            # İlk yazımda tanıma ölçütü ad ekiydi ("...Hatasi" ya da
            # "...Kuculdu"). `KartTutarsizligi` eklenince test onu
            # GÖREMEDİ -- yani kayma denetçisinin kendisi kaydı.
            # V35'in dersinin tekrarı: muafiyet/tanıma DESENE değil
            # KİMLİĞE bağlanır. Kimlik burada TABAN SINIFTIR.
            tabanlar = {b.id for b in n.bases if isinstance(b, ast.Name)}
            if ad == "pipeline":
                if "YayimHatasi" not in tabanlar:
                    continue      # YayimHatasi'nın kendisi de elenir
            else:
                if "Exception" not in tabanlar:
                    continue
            bulunan.add(n.name)

    ilan = {i for _, i, _ in KORUMALAR}
    assert ilan == bulunan, (
        f"koruma listesi ayrışmış.\n"
        f"  ilan edilip kodda olmayan : {sorted(ilan - bulunan)}\n"
        f"  kodda olup ilan edilmeyen : {sorted(bulunan - ilan)}")

    # adlar da benzersiz olmalı -- künyede tekrar eden ad okunamaz
    adlar = [a for a, _, _ in KORUMALAR]
    assert len(adlar) == len(set(adlar)), adlar


# --- KURAL 9: kart-tahmin tutarlılığı (V53) ------------------------------

def _kart(sha):
    return {"katman2_kunyesi": {"kaynak_dosya": "forecast_7d_m45.geojson",
                                "kaynak_sha256": sha}}


def test_kart_BASKA_tahminden_uretilmisse_REDDEDER():
    """Kartlar dünün tahminini okumuşsa yayım DURUR.

    V53: kartlar `latest/`ten okunuyordu ve `latest` o anda BİR ÖNCEKİ
    yayındı. Harita bugünü, kartlar dünü gösteriyordu -- aynı sayfada iki
    farklı güne ait sayı. Yerelde çökmedi çünkü `latest/` hep doluydu.
    """
    from src.operational.pipeline import (KartTutarsizligi,
                                          kontrol_kart_tutarliligi)

    kayitlar = [{"dosya": "forecast_7d_m45.geojson", "sha256": "b" * 64}]
    with pytest.raises(KartTutarsizligi) as e:
        kontrol_kart_tutarliligi(_kart("a" * 64), kayitlar)
    assert "BAŞKA" in str(e.value)


def test_kart_KUNYESIZSE_REDDEDER():
    """Hangi tahminden üretildiği bilinmiyorsa yayımlanmaz."""
    from src.operational.pipeline import (KartTutarsizligi,
                                          kontrol_kart_tutarliligi)

    kayitlar = [{"dosya": "forecast_7d_m45.geojson", "sha256": "b" * 64}]
    with pytest.raises(KartTutarsizligi):
        kontrol_kart_tutarliligi({"katman2_kunyesi": {}}, kayitlar)


def test_kart_AYNI_tahminden_uretilmisse_GECER():
    """Gevşetme kontrolü: doğru kart reddedilmemeli.

    Yalnızca ret deneyi yapılsaydı, HER ŞEYİ reddeden bir koruma da
    testi geçerdi.
    """
    from src.operational.pipeline import kontrol_kart_tutarliligi

    kayitlar = [{"dosya": "forecast_7d_m45.geojson", "sha256": "b" * 64}]
    r = kontrol_kart_tutarliligi(_kart("b" * 64), kayitlar)
    assert r["kaynak_dosya"] == "forecast_7d_m45.geojson"


def test_guncel_VARSAYILAN_YOL_KABUL_ETMEZ():
    """`guncel()` argümansız çağrılamaz — varsayılan yol V53'ün sebebiydi.

    Bir varsayılan yol, 'hangi dosyayı okuduğumu düşünmedim' demenin
    sessiz biçimidir. Çağıran, hangi tahmini okuduğunu SÖYLEMEK zorunda.
    """
    import inspect

    from src.operational.bolge_kartlari import guncel, kartlar

    for f in (guncel, kartlar):
        par = list(inspect.signature(f).parameters.values())
        assert par and par[0].default is inspect.Parameter.empty, (
            f"{f.__name__} ilk parametresi varsayılan taşıyor — V53 geri döner")
