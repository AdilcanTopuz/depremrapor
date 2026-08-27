# -*- coding: utf-8 -*-
"""Sayfa genelinde KAYMA korumaları.

Buradaki iki şey, tek bir sayfada elle yapıldığında sessizce eksik kalır:

  1. ÖLÇÜM BETİĞİ. `analitik.js` yedi sayfaya bağlanır. Sekizinci sayfa
     eklendiğinde unutulursa hiçbir şey bozulmaz -- yalnızca o sayfa
     ölçülmez ve bu, ancak aylar sonra sayılara bakılırken fark edilir.

  2. ATIF. Harita altlığı değiştiğinde atıf metni de değişmek zorundadır.
     Atıfsız altlık kullanmak bir lisans ihlalidir ve kod çalışmaya devam
     ettiği için kendini hiçbir yerde belli etmez.

Her ikisi de "çalışan ama yanlış" sınıfındandır; bu yüzden teste bağlanır.
"""
import pathlib
import re

import pytest

KOK = pathlib.Path(__file__).resolve().parents[1]
WEB = KOK / "web"


def _sayfalar():
    return sorted(p for p in WEB.glob("*.html"))


def test_her_sayfa_olcum_betigini_cagirir():
    eksik = [p.name for p in _sayfalar()
             if 'src="analitik.js"' not in p.read_text(encoding="utf-8")]
    assert not eksik, f"ölçüm betiği bağlanmamış sayfalar: {eksik}"


def test_olcum_kontrolu_EKSIK_SAYFAYI_YAKALAR(tmp_path):
    """Kural 9: koruma, bir şeyi REDDETTİĞİ gösterilene kadar kurulu değildir.

    Yukarıdaki test her zaman geçiyor olabilir çünkü hiçbir şeye bakmıyordur.
    Burada betiği çağırmayan bir sayfa üretilir ve aynı ölçütün onu ayırt
    ettiği gösterilir.
    """
    sahte = tmp_path / "yeni.html"
    sahte.write_text("<html><head></head><body></body></html>", encoding="utf-8")
    assert 'src="analitik.js"' not in sahte.read_text(encoding="utf-8")


def test_olcum_etiketi_girilmeden_istek_yapilmaz():
    """Yer tutucu etiketle üçüncü taraf bir adrese BAĞLANILMAZ.

    "Ölçülüyor sanmak ama ölçmemek" kadar, "ölçmüyoruz demek ama bağlanmak"
    da hatadır; ikincisi yasal.html §5'teki beyanı yanlış yapardı.
    """
    s = (WEB / "analitik.js").read_text(encoding="utf-8")
    assert 'const ANALITIK_ETIKET = "ETIKET_GIRILMEDI"' in s or \
        re.search(r'ANALITIK_ETIKET = "[0-9a-f]{32}"', s), \
        "etiket ya yer tutucu ya da 32 haneli onaltılık olmalı"
    assert re.search(r'/\^\[0-9a-f\]\{32\}\$/\.test\(ANALITIK_ETIKET\)', s), \
        "biçim sınaması kaldırılmış: yer tutucuyla istek yapılabilir"


def test_altlik_ve_atif_AYNI_KALEMDE_degisir():
    """Atıf, kullanılan altlığı anmak zorundadır."""
    s = (WEB / "script.js").read_text(encoding="utf-8")
    assert "cartocdn.com" not in s, \
        "CARTO geri gelmiş: anonim kullanımda 'API key required' damgası veriyor"
    assert "tile.openstreetmap.org" in s
    atiflar = re.findall(r'atif: "([^"]+)"', s)
    assert atiflar, "atıf metni bulunamadı"
    assert all("OpenStreetMap" in a for a in atiflar)
    kaynaklar = re.search(r"kaynaklar:\s*\n?\s*(\"[^;]+)", s).group(1)
    assert "OpenStreetMap" in kaynaklar and "OpenMapTiles" not in kaynaklar, \
        "METIN.kaynaklar altlıkla birlikte güncellenmemiş"
    yasal = (WEB / "yasal.html").read_text(encoding="utf-8")
    assert "OpenStreetMap" in yasal, "yasal.html §3 altlık kaynağını anmıyor"
    for artik in ("CARTO", "OpenMapTiles"):
        assert artik not in yasal, \
            f"yasal.html §3 artık kullanılmayan {artik} satırını taşıyor"


@pytest.mark.parametrize("sayfa", [p.name for p in _sayfalar()])
def test_altlik_secimi_anahtarsizdir(sayfa):
    """Hiçbir sayfa anahtar gerektiren bir karo adresi çağırmaz."""
    s = (WEB / sayfa).read_text(encoding="utf-8")
    for kotali in ("cartocdn.com", "api.mapbox.com", "maptiler.com",
                   "tiles.stadiamaps.com"):
        assert kotali not in s, f"{sayfa}: anahtar/kota gerektiren altlık {kotali}"


# --- ZORUNLU BİLEŞENLER ----------------------------------------------------
#
# Tasarım 41'e geçilirken `index.html` bütünüyle değiştirildi ve
# "Bu harita neyi gösterir / göstermez" kutuları SESSİZCE düştü. Hiçbir şey
# bozulmadı: sayfa açıldı, sayılar doğru çıktı, testler geçti. Düşen şey bir
# işlev değil bir BEYANDI -- ve beyanların kaybı, işlevlerin kaybı gibi
# kendini belli etmez.
#
# Ders V42'nin kalıbı: elle tutulan bir şey kaynağından ayrışır ve ayrışma
# sessizdir. Bu yüzden metinler `script.js` içindeki METIN'de tek kaynakta
# durur ve varlıkları burada sınanır.

ZORUNLU = {
    "iki katman ayrımı": ["ikiKatman"],
    "gösterir/göstermez": ["gosterir:", "gostermez:"],
    "hüküm etiketi ve açıklaması": ["hukumEtiketi", "HUKUM_ACIKLAMA"],
    "künye": ["kunyeSatirlari"],
    "bayatlık göstergesi": ["tazelik", "HAZIRLIK_ESIGI"],
    "hazırlık yönlendirmesi": ["hazirlikMetni", "AFAD_URL"],
    "olasılık dili": ["katCumlesi", "guvenCumlesi"],
    "kaynak/atıf satırı": ["kaynaklar:"],
}


@pytest.mark.parametrize("ad,parcalar", sorted(ZORUNLU.items()))
def test_zorunlu_bilesen_tek_kaynakta_duruyor(ad, parcalar):
    s = (WEB / "script.js").read_text(encoding="utf-8")
    eksik = [p for p in parcalar if p not in s]
    assert not eksik, f"{ad}: script.js'te yok -> {eksik}"


@pytest.mark.parametrize("kanca", ["gg", "iki-katman", "uyari", "bayat",
                                   "kartlar", "pencereler"])
def test_zorunlu_bilesen_SAYFAYA_BAGLI(kanca):
    """Metnin var olması yetmez; sayfada onu basan bir yer de olmalı.

    Bir önceki hata tam buradaydı: metin `ortak.js`te duruyordu, sayfa onu
    hiç çağırmıyordu. Tek kaynak, çağrılmadığı sürece yayımlanmaz.
    """
    s = (WEB / "index.html").read_text(encoding="utf-8")
    assert f'id="{kanca}"' in s, f"index.html'de #{kanca} yok"
    assert f'getElementById("{kanca}")' in s, \
        f"#{kanca} sayfada var ama hiç doldurulmuyor"


def test_bilesen_kontrolu_REDDEDIYOR():
    """Kural 9: yukarıdaki iki denetimin boş çalışmadığı gösterilir.

    İlk yazımda ikinci onaylama `... or f'"{kanca}"' in s` idi; o dal id
    varken her zaman doğru olduğu için denetim aslında hiçbir şey
    sınamıyordu. Aşağıda hem "metin yok" hem "sayfa çağırmıyor" durumları
    üretilir ve ölçütün ikisini de ayırt ettiği gösterilir.
    """
    js = (WEB / "script.js").read_text(encoding="utf-8")
    html = (WEB / "index.html").read_text(encoding="utf-8")

    # 1) metin tek kaynaktan silinirse
    assert "gosterir:" not in js.replace("gosterir:", "", 1)
    # 2) sayfa çağrıyı kaybederse (kutu dururken)
    kirli = html.replace('getElementById("gg")', 'getElementById("yok")')
    assert 'id="gg"' in kirli and 'getElementById("gg")' not in kirli, \
        "senaryo kurulamadı: çağrı silinmiş sayfa üretilemedi"


def test_gosterir_gostermez_UCER_MADDE():
    """Listeler boşaltılarak da 'kaldırılmış' olurdu."""
    s = (WEB / "script.js").read_text(encoding="utf-8")
    for ad in ("gosterir", "gostermez"):
        blok = s[s.index(f"{ad}: ["):]
        blok = blok[:blok.index("],")]
        assert blok.count('",') + blok.count('",\n') >= 3, \
            f"METIN.{ad} üçten az madde taşıyor"


def test_yayin_adresi_TEK_KAYNAKTAN():
    """Adres birden çok yerde elle yazılırsa biri güncellenir öteki kalır."""
    from src.operational.pipeline import YAYIN_ADRESI
    assert YAYIN_ADRESI == "https://depremrapor.com"
    for sayfa in _sayfalar():
        s = sayfa.read_text(encoding="utf-8")
        assert 'rel="canonical"' in s, f"{sayfa.name}: canonical yok"
        assert YAYIN_ADRESI in s, f"{sayfa.name}: canonical yanlış adreste"
