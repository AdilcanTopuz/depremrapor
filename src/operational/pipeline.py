"""VERİ HATTI — AFAD çekme -> katalog -> tahmin -> yayın, tek akış.

Bu modül, elle çalıştırılan adımları **zamanlanabilir tek bir akışa** bağlar.
Cron bunu çağırır; başka hiçbir şey çağırmaz.

    AFAD çekme  ->  katalog güncelleme  ->  analitik tahmin  ->  yayın dizini

HER HALKA KÜNYELİ, HER KORUMA KURAL 9'A TABİ. Bir korumanın "kurulu" sayılması
için REDDETTİĞİ bir deney gösterilmelidir; `tests/test_pipeline.py` her koruma
için bir ret gösterir.

KORUMALAR (her biri kendi hata tipiyle -- test edilebilsin diye):

    KirliAgacHatasi      commit'lenmemiş değişiklikle yayım
    BayatKatalogHatasi   katalog beklenenden eski (AFAD çekme sessizce başarısız)
    SemaHatasi           üretilen GeoJSON beklenen şemayı taşımıyor
    DilHatasi            yayımlanan metinde KESİNLİK DİLİ (yasak kelime)
    EsikHatasi           yayımlanan hücre sayısı ölçülmüş banttan sapıyor

Hiçbiri "uyarı" değildir; hepsi yayımı DURDURUR. Sessizce güvenilmez tahmin
yayımlamaktansa hiç yayımlamamak doğrudur.

Kullanım:
    python -m src.operational.pipeline               # tam akış
    python -m src.operational.pipeline --no-update   # katalogu tazeleme
    python -m src.operational.pipeline --kontrol     # yalnızca kontroller
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
PUBLISH = ROOT / "data" / "publish"

# --- İLAN EDİLMİŞ ÜRÜN AYARLARI -------------------------------------------
PENCERELER = (1, 7, 30)           # gün — README'deki 1g/7g/30g seçici
HEDEF_MW = 4.5
MIN_TIMES_NORMAL = 2.0            # ölçülerek seçildi (forecast_now tablosu)

# Katalog tazeliği: AFAD çekme sessizce başarısız olursa katalog eskir ve
# tahmin ESKİ VERİYLE üretilir. Bu, en tehlikeli sessiz hatadır: çıktı normal
# görünür, künye doğrudur, veri bayattır.
AZAMI_KATALOG_YASI_SAAT = 48

# YAYIN KADANSI VE BAYAT YAYIN EŞİĞİ -- ürün kararı, gerekçesi burada.
#
# NEDEN 3 SAAT, NEDEN GÜNDE BİR DEĞİL. Modelin değeri zamanda yoğundur:
# ölçüldüğünde olay teriminin %98,8'i 120 başlangıç içindeki en yüksek 10
# olaylı başlangıçtan geliyordu (docs/MANSET.md). Yani ETAS "her gün biraz
# daha iyi" değil, KRİTİK GÜNLERDE çok daha iyi. Bir M6 sonrası artçı oranı
# saatler içinde büyüklük mertebesi değiştirir; 24 saatlik tazeleme, modelin
# tam da en değerli olduğu anda bağlayıcı kısıt hâline gelir.
#
# Üç saat, koşu süresinin (önbellekli ~45 dk) rahatça altında kaldığı en sık
# kadanstır. Daha sıkısı koşuları üst üste bindirir.
#
# GitHub Actions `schedule` GARANTİLİ DEĞİLDİR: 5-15 dk gecikme olağandır,
# ender olarak bir koşu hiç çalışmaz. Bir koşunun atlanması yayını geçersiz
# kılmaz; eşik bir atlamayı tolere edip ikincisinde uyarır:
#
#     3 saat (koşu aralığı) + 3 saat (bir atlama) + 1 saat (gecikme payı) = 7
#
# Eşik aşılınca arayüz AÇIKÇA UYARIR ve manifest bunu MAKİNE-OKUNUR biçimde
# taşır: bir izleme aracı ya da kurumsal kullanıcı da bayatlığı programatik
# görebilsin -- "sessizce eskime" hiçbir tüketici için olmasın.
BAYAT_YAYIN_ESIGI_SAAT = 7
YAYIN_ARALIGI_SAAT = 3

# YAYIN ADRESİ TEK YERDE DURUR. Künyeye, manifeste, sayfaların canonical ve
# og:url etiketlerine ve sitemap'e buradan gider. İkinci bir yerde elle
# yazılırsa biri güncellenir öteki kalır -- V52'nin ("beyan sistemden
# türetilir") adres tarafındaki karşılığı.
YAYIN_ADRESI = "https://depremrapor.com"

# Yayımlanan hücre sayısı bandı. Ölçülmüş beklenti ~300 (eşik 2,0'da 299).
# Bandın DIŞI, eşiğin ya da katalogun beklenmedik biçimde değiştiğini gösterir.
# BANT, KAPSAM KISITLAMASINDAN ÖNCE ölçülmüştü (2560 hücrelik ızgara,
# başlangıç başına ~300). Kapsam Türkiye ile sınırlanınca sayılar ~%64
# düştü (309 -> 110). Bant, YENİ kapsamla yeniden ölçülene kadar geçici
# olarak genişletilmiştir ve bu AÇIKÇA yazılıdır -- sessizce gevşetilmedi.
#
# Yeniden ölçüm: scripts/33_kapsam_bandi.py (kapsam içi hücre sayısının
# 208 başlangıçtaki dağılımı).
HUCRE_BANDI = (20, 400)
HUCRE_BANDI_NOTU = ("geçici: kapsam kısıtlamasından sonra yeniden "
                    "ölçülecek (V43)")

# KESİNLİK DİLİ YASAK (README §8). Bu kelimeler yayımlanan hiçbir metinde
# geçemez; olasılık beyanı zorunludur.
# İKİ SINIF YASAK KALIP (V46).
#
# 1. KOŞULSUZ: kesinlik iddiasının kendisi. Nerede geçerse geçsin ihlaldir.
# 2. KOŞULLU: sıradan Türkçe yardımcı fiiller. Tek başına ihlal DEĞİLDİR --
#    "lazım olacak satır budur", "taranmış olacak" meşru cümlelerdir.
#    İhlal olmaları için DEPREM BAĞLAMINDA geçmeleri gerekir.
#
# İlk sürüm çıplak "olacak"ı koşulsuz yasaklıyordu ve denetim mirası
# sayfasını reddetti -- üçüncü yanlış pozitif (V33 büyük harf, V45 sözcük
# sınırı, V46 bağlam). Çözüm kalıbı SİLMEK değil, KOŞULA BAĞLAMAK.
YASAK_KOSULSUZ = (
    "kesin", "kesinlikle", "garanti", "bekleniyor ki",
    "tahmin ediyoruz ki",
)
YASAK_KOSULLU = ("olacak", "olacağ", "gerçekleşecek", "vuracak", "bekliyoruz")
DEPREM_SOZCUKLERI = ("deprem", "sarsıntı", "sarsinti", "artçı", "artçi",
                     "fay", "büyüklük", "magnitüd", "şiddet")
YAKINLIK = 60          # karakter -- aynı cümle mertebesi

YASAK_KALIPLAR = YASAK_KOSULSUZ + YASAK_KOSULLU   # geriye dönük uyum


class YayimHatasi(Exception):
    """Yayımı durduran her hata bunun altındadır."""


class KirliAgacHatasi(YayimHatasi):
    pass


class BayatKatalogHatasi(YayimHatasi):
    pass


class SemaHatasi(YayimHatasi):
    pass


class DilHatasi(YayimHatasi):
    pass


class EsikHatasi(YayimHatasi):
    pass


class KapiHatasi(YayimHatasi):
    """Operasyonel modelin kalibrasyonu ilan edilmiş bandın dışında."""


class ParametreHatasi(YayimHatasi):
    """Kalibre parametre dosyası yok — sessiz varsayılanla yayım yapılmaz."""


class KartTutarsizligi(YayimHatasi):
    """Bölge kartları, bu koşunun tahmininden üretilmemiş."""


# --- KORUMALAR --------------------------------------------------------------

# YÜRÜRLÜKTEKİ KORUMA LİSTESİ — tek kaynak.
#
# Liste künyeye buradan yazılır ve siteye buradan çıkar. Elle yazılmış bir
# liste kaynağından AYRIŞIR ve ayrışma sessizdir: künyedeki liste altı
# koruma sayarken sistemde dokuz tane vardı -- monotonluk, kapsam ve
# kalibre parametreler listeye hiç girmemişti (V52). Site o listeyi
# gösterecekti; yani YANLIŞ BİR KORUMA LİSTESİ yayımlanacaktı.
#
# Ayrışma yapısal olarak kapatılır: her koruma kendi istisna tipini taşır ve
# `tests/test_pipeline.py::test_koruma_listesi_KODLA_AYNI` bu tuple'daki
# istisna kümesinin, modüllerde tanımlı koruma istisnalarının kümesine EŞİT
# olduğunu doğrular. Yeni bir koruma eklenip listeye yazılmazsa test kırılır.
#
# (ad, istisna_adi, nerede_calisir)
KORUMALAR = (
    ("kirli ağaç",            "KirliAgacHatasi",  "pipeline"),
    ("katalog tazeliği",      "BayatKatalogHatasi", "pipeline"),
    ("katalog monotonluğu",   "KatalogKuculdu",   "forecast_now"),
    ("kalibre parametreler",  "ParametreHatasi",  "pipeline"),
    ("ürün kapısı",           "KapiHatasi",       "pipeline"),
    ("yayın kapsamı",         "KapsamHatasi",     "kapsam"),
    ("şema",                  "SemaHatasi",       "pipeline"),
    ("dil",                   "DilHatasi",        "pipeline"),
    ("hücre sayısı bandı",    "EsikHatasi",       "pipeline"),
    ("kart-tahmin tutarlılığı", "KartTutarsizligi", "pipeline"),
)


def kontrol_agac(izin_ver: bool = False) -> str:
    """Çalışma ağacı temiz mi. Kirli ağaçtan yayım künyeyi YALANCI yapar."""
    from src.operational.forecast_now import _fingerprint

    fp = _fingerprint()
    if fp["worktree"] == "dirty" and not izin_ver:
        raise KirliAgacHatasi(
            "çalışma ağacı KİRLİ: künyedeki commit, üretilen dosyanın "
            "içeriğini yansıtmaz. Cron TEMİZ bir checkout'tan çalışmalıdır.")
    return fp["commit"]


def kontrol_katalog_tazeligi(azami_saat: float = AZAMI_KATALOG_YASI_SAAT,
                             simdi: pd.Timestamp | None = None) -> dict:
    """Katalog ne kadar eski?

    AFAD çekme sessizce başarısız olursa (ağ hatası, API değişikliği, boş
    cevap) katalog eskir ama HİÇBİR ŞEY hata vermez: tahmin eski veriyle
    üretilir, künye doğrudur, çıktı normal görünür. En tehlikeli sessiz hata
    sınıfı budur; bu yüzden yaş AÇIKÇA ölçülür.
    """
    from src.ingest.catalog_io import read_catalog

    yol = PROC / "catalog_merged.csv"
    if not yol.exists():
        raise BayatKatalogHatasi(f"{yol} yok")
    son = read_catalog(yol).time.max()
    simdi = simdi or pd.Timestamp(datetime.now(timezone.utc))
    yas = (simdi - son).total_seconds() / 3600.0
    if yas > azami_saat:
        raise BayatKatalogHatasi(
            f"katalog {yas:.1f} saat eski (azami {azami_saat}). AFAD çekme "
            "başarısız olmuş olabilir; ESKİ VERİYLE tahmin yayımlanmaz.")
    return {"son_olay": str(son), "yas_saat": round(yas, 2)}


# ÖLÇÜLMÜŞ ŞEMA. İlk sürümde bu alan adları VARSAYILMIŞTI ("kunye", "p") ve
# koruma GEÇERLİ bir çıktıyı reddetti -- yanlış pozitif (V34). Adlar artık
# üretilen dosyadan okunarak yazıldı.
UST_ALANLAR = ("origin", "window_days", "target_magnitude", "model", "mode",
               "fingerprint", "kapsam", "min_times_normal",
               "cells_before_threshold", "cells_published", "disclaimer")
HUCRE_ALANLARI = ("cell_id", "probability", "expected_events",
                  "normal_probability", "times_normal")
KUNYE_ALANLARI = ("method", "etas_params_sha256", "catalog_sha256",
                  "catalog_last_event", "commit", "worktree", "randomness")


def kontrol_sema(gj: dict) -> dict:
    """Üretilen GeoJSON ÖLÇÜLMÜŞ şemayı taşıyor mu."""
    if gj.get("type") != "FeatureCollection":
        raise SemaHatasi("type != FeatureCollection")

    ust = gj.get("properties") or {}
    eksik_ust = [k for k in UST_ALANLAR if k not in ust]
    if eksik_ust:
        raise SemaHatasi(f"üst düzey alanlar eksik: {eksik_ust}")

    kunye = ust.get("fingerprint")
    if not kunye:
        raise SemaHatasi("künye (fingerprint) YOK — künyesiz tahmin "
                         "yayımlanmaz")
    eksik_k = [k for k in KUNYE_ALANLARI if k not in kunye]
    if eksik_k:
        raise SemaHatasi(f"künye alanları eksik: {eksik_k}")
    if kunye.get("worktree") == "dirty":
        raise SemaHatasi("künye 'dirty' damgası taşıyor — cron temiz "
                         "checkout'tan çalışmalıdır")

    ozellikler = gj.get("features")
    if not isinstance(ozellikler, list) or not ozellikler:
        raise SemaHatasi("features boş")
    eksik_h = [k for k in HUCRE_ALANLARI
               if k not in (ozellikler[0].get("properties") or {})]
    if eksik_h:
        raise SemaHatasi(f"hücre alanları eksik: {eksik_h}")

    # UYARI METNİ ZORUNLU (README §8) -- ve dil denetimine tabi
    if not str(ust.get("disclaimer", "")).strip():
        raise SemaHatasi("uyarı metni (disclaimer) YOK ya da boş")

    return {"n_hucre": len(ozellikler),
            "esik_oncesi": ust.get("cells_before_threshold"),
            "yayimlanan": ust.get("cells_published")}


def tr_kucult(metin: str) -> str:
    """TÜRKÇE farkındalıklı küçültme.

    `str.lower()` Türkçe için YANLIŞTIR ve bu koruma onu kullandığı için
    KÖRDÜ (V33): büyük `İ`, Unicode kurallarına göre `i` + BİRLEŞEN NOKTA
    (U+0307) verir; `"kesinlikle"` ile eşleşmez. Yani "KESİNLİKLE" yazan bir
    metin yasak kelime taramasından geçiyordu.

    Ölçüldü: `'KESİNLİKLE'.lower()` çıktısı cp1254'e kodlanamıyor bile.

    Doğrusu, küçültmeden ÖNCE Türkçeye özgü iki eşlemeyi yapmaktır:
        İ -> i        I -> ı
    """
    return metin.replace("İ", "i").replace("I", "ı").lower()


# ONAYLI UYARI METNİ — künye zincirinin METNE uygulanması.
#
# Uyarı metni, kesinliği REDDEDEN bir metindir ve zorunlu olarak yasak
# kelimeleri içerir: "kesin deprem tahmini DEĞİLDİR". Naif bir kelime
# taraması bunu ihlal sanar (V35) -- kendi uyarımızı yasaklar.
#
# İki çözüm vardı ve biri seçildi:
#   (a) olumsuzlama sezgiselliği yaz  -> KIRILGAN, dilbilgisine bağlı,
#       yanlış negatif üretir (ihlali "değildir" ekleyerek gizlemek kolay)
#   (b) onaylı metni KİMLİĞİYLE muaf tut -> DENETLENEBİLİR
#
# (b) seçildi. Onaylı metnin sha256'sı burada sabittir; metin değişirse
# hash tutmaz ve hat DURUR -- yeni metin insan tarafından gözden geçirilip
# yeniden sabitlenene kadar yayım olmaz. Muafiyet, desene değil KİMLİĞE
# verilir; bu yüzden "değildir" ekleyerek muafiyet kazanılamaz.
ONAYLI_UYARI_SHA = "b824f0f1095753e1a73e8e8413e1202a581c956640607e27ac203b53ff5ad83b"


def _uyari_muaf(metin: str) -> str:
    """Onaylı uyarı metnini çıkarır; geri kalan sıkı taramaya girer."""
    import re

    for parca in re.findall(r'"([^"]{80,})"', metin):
        if hashlib.sha256(parca.encode("utf-8")).hexdigest() == ONAYLI_UYARI_SHA:
            metin = metin.replace(parca, " [ONAYLI UYARI METNİ] ")
    return metin


def kontrol_dil(metin: str, uyari_muafiyeti: bool = True) -> None:
    """Yayımlanan metinde kesinlik dili var mı (README §8)."""
    if uyari_muafiyeti:
        metin = _uyari_muaf(metin)
    # SÖZCÜK SINIRI GÖZETİLİR (V44).
    #
    # Naif alt dize eşleşmesi yanlış alarm üretiyordu: "tehlikesinin"
    # kelimesi `kesin` içeriyor (teh-li-KESİN-in) ve koruma, yazılması
    # ZORUNLU bir cümleyi -- "deprem tehlikesinin düşük olduğu anlamına
    # gelmez" -- ihlal saydı.
    #
    # Türkçe eklemeli bir dildir: yasak kalıp sözcüğün BAŞINDA olmalıdır,
    # sonrasına ek gelebilir. `kesin` -> "kesin", "kesinlikle", "kesindir"
    # yakalanır; "tehlikesinin", "eksiksiz" yakalanmaz.
    #
    # Bu bir GEVŞETME DEĞİL, DÜZELTMEDİR: koruma aynı ihlalleri yakalamaya
    # devam eder (testlerle sabit), yalnızca yanlış pozitifler kalkar.
    import re

    kucuk = tr_kucult(metin)
    sinir = r"(?<![0-9a-zçğıöşü])"
    bulunan = [k for k in YASAK_KOSULSUZ
               if re.search(sinir + re.escape(k), kucuk)]

    # KOŞULLU kalıplar: yalnızca deprem bağlamında ihlal.
    for k in YASAK_KOSULLU:
        for m in re.finditer(sinir + re.escape(k), kucuk):
            pencere = kucuk[max(0, m.start() - YAKINLIK):m.end() + YAKINLIK]
            if any(d in pencere for d in DEPREM_SOZCUKLERI):
                bulunan.append(f"{k} (deprem bağlamında)")
                break
    if bulunan:
        raise DilHatasi(
            f"KESİNLİK DİLİ bulundu: {bulunan}. Her tahmin olasılık beyanıyla "
            "yayımlanır; kesinlik dili yasaktır.")


def kontrol_kalibre_parametreler() -> dict:
    """Kalibre Mc ve b değeri VAR MI — sessiz varsayılana düşülmesin.

    `config.load_mc_and_b()` dosya yoksa SESSİZCE varsayılana döner
    (mc=3.3, b=1.0). Ama kalibre b bu katalogda **1,045**'tir ve kodun kendi
    yorumu şunu söylüyor: *"küçük görünen fark M4.5 hedefinde normal oranı
    ~%5 kaydırır ve doğrudan 'normalin kaç katı' alanını bozar."*
    
    Taze checkout'lu bir ortamda dosya unutulursa, hat **sessizce yanlış b
    ile** tahmin üretirdi -- çıktı normal görünür, künye doğrudur, sayı
    yanlıştır. En tehlikeli hata sınıfı (V38 ailesi).
    
    Bu yüzden varsayılana düşme YAYIMDA YASAKTIR ve açıkça kontrol edilir.
    """
    from src.config import MC_FALLBACK, PROC as _P, load_mc_and_b

    yol = _P / "mc_by_period.csv"
    if not yol.exists():
        raise ParametreHatasi(
            f"{yol.name} YOK -- kalibre Mc/b olmadan yayım yapılmaz. "
            "Dosya yoksa load_mc_and_b sessizce mc=3.3, b=1.0 döner ve "
            "'normalin kaç katı' alanı ~%5 kayar.")
    mc, b = load_mc_and_b()
    if abs(b - 1.0) < 1e-9:
        raise ParametreHatasi(
            f"b değeri tam 1,0 -- varsayılana düşülmüş olabilir. "
            f"Bu katalogda kalibre değer 1,045 ölçülmüştü.")
    return {"mc": mc, "b": b, "kaynak": yol.name}


def kontrol_urun_kapisi(model: str = "ETAS") -> dict:
    """Operasyonel model kalibrasyon şartını sağlıyor mu (site şartnamesi).

    Bugün tek model var ve kontrol trivial görünüyor. Otomatik olmasının
    sebebi YARIN: kalibrasyonu düzeltilmiş bir aday kapıya dayandığında,
    ölçüt sonuca göre yorumlanamaz -- çünkü kod yorumlamaz.
    """
    from src.operational.urun_kapisi import KapiKapali, operasyonel_model_kontrolu

    try:
        return operasyonel_model_kontrolu(model)
    except KapiKapali as e:
        raise KapiHatasi(str(e)) from e


def kontrol_kart_tutarliligi(kart: dict, kayitlar: list) -> dict:
    """Bölge kartları, BU koşunun 7 günlük tahmininden mi üretildi.

    V53. Kartlar `latest/`ten okunuyordu ve `latest` o anda BİR ÖNCEKİ
    yayındı: harita bugünü, kartlar dünü gösteriyordu. Yerelde çökmedi
    çünkü `latest/` hep doluydu -- hata SESSİZDİ ve ancak taze
    checkout'lu bulut koşusunda görünür oldu.

    Yolu zorunlu kılmak hatayı düzeltir ama TEKRARINI engellemez: biri
    yarın yanlış yolu geçirebilir. Bu koruma iki sha256'yı karşılaştırır
    -- kartların okuduğu dosya ile bu koşunun yayımladığı dosya AYNI
    OLMAK ZORUNDADIR.

    Karşılaştırma YOL üzerinden değil İÇERİK üzerindendir: yol doğru
    görünüp içerik başka olabilir (kopya, önbellek, yarış).
    """
    k2 = kart.get("katman2_kunyesi") or {}
    kart_sha = k2.get("kaynak_sha256")
    if not kart_sha:
        raise KartTutarsizligi(
            "kartlarda kaynak_sha256 yok — hangi tahminden üretildiği "
            "bilinmiyor; künyesiz kart yayımlanmaz")

    hedef = "forecast_7d_m45.geojson"
    yayin_sha = next((k.get("sha256") for k in kayitlar
                      if k.get("dosya") == hedef), None)
    if yayin_sha is None:
        raise KartTutarsizligi(f"{hedef} bu koşuda yayımlanmamış")
    if kart_sha != yayin_sha:
        raise KartTutarsizligi(
            "bölge kartları BAŞKA bir tahminden üretilmiş." + "\n"
            + f"  kartların okuduğu : {kart_sha[:16]}…" + "\n"
            + f"  bu koşunun yayını : {yayin_sha[:16]}…" + "\n"
            + "Harita ile kartlar farklı günleri gösterirdi (V53).")
    return {"kaynak_dosya": k2.get("kaynak_dosya"), "sha256": kart_sha[:16]}


def kontrol_hucre_sayisi(n: int, band: tuple = HUCRE_BANDI) -> None:
    """Yayımlanan hücre sayısı ölçülmüş bandın içinde mi."""
    if not (band[0] <= n <= band[1]):
        raise EsikHatasi(
            f"yayımlanan hücre sayısı {n}, ölçülmüş bandın ({band[0]}-"
            f"{band[1]}) dışında. Eşik ya da katalog beklenmedik biçimde "
            "değişmiş olabilir.")


# --- AKIŞ -------------------------------------------------------------------

def _sha256(veri: bytes) -> str:
    return hashlib.sha256(veri).hexdigest()


def _ham_satir_sayilari() -> dict:
    """Ham katalog dosyalarının satır sayıları — monotonluk referansı."""
    from src.operational.forecast_now import _satir_say

    out = {}
    for ad in ("afad_catalog.csv", "koeri_catalog.csv", "emsc_catalog.csv"):
        yol = ROOT / "data" / "raw" / ad
        if yol.exists():
            out[ad] = _satir_say(yol)
    return out


def calistir(pencereler: tuple = PENCERELER, hedef_mw: float = HEDEF_MW,
             guncelle: bool = True, izin_kirli: bool = False,
             quiet: bool = False) -> dict:
    """Uçtan uca tek akış. Herhangi bir koruma reddederse YAYIM OLMAZ."""
    from src.operational.forecast_now import (load_state, run_forecast_analytic,
                                              to_geojson, update_catalog)

    t0 = datetime.now(timezone.utc)
    commit = kontrol_agac(izin_kirli)
    par = kontrol_kalibre_parametreler()
    if not quiet:
        print(f"kalibre parametreler: mc={par['mc']} · b={par['b']:.4f}")
    kapi = kontrol_urun_kapisi()
    if not quiet:
        print(f"ürün kapısı: {kapi['model']} oran {kapi['oran']:.3f} "
              f"band {kapi['band']} -> GEÇTİ")
    if not quiet:
        print(f"commit {commit[:12]} · ağaç temiz")

    if guncelle:
        update_catalog(quiet=quiet)
    tazelik = kontrol_katalog_tazeligi()
    if not quiet:
        print(f"katalog son olay {tazelik['son_olay']} "
              f"({tazelik['yas_saat']} saat önce)")

    origin = pd.Timestamp(t0).tz_localize(None).normalize()
    durum = load_state()
    # DİZİN ADINDA SAAT DE VAR. Günde sekiz yayın aynı gün adını
    # paylaşsaydı sonuncusu öncekilerin üstüne yazar ve arşiv, o günün
    # yalnızca son hâlini taşırdı -- oysa sicil, HANGİ AN neyin yayımlandığını
    # bilmeye dayanır.
    gun_dizini = PUBLISH / f"{origin:%Y-%m-%dT%H%M}"
    gun_dizini.mkdir(parents=True, exist_ok=True)

    kayitlar = []
    for gun in pencereler:
        blok = run_forecast_analytic(gun, hedef_mw, origin=origin, state=durum)
        gj = to_geojson(blok, gun, hedef_mw, origin, mode="live",
                        min_times_normal=MIN_TIMES_NORMAL)
        sema = kontrol_sema(gj)
        kontrol_hucre_sayisi(sema["n_hucre"])
        icerik = json.dumps(gj, ensure_ascii=False).encode("utf-8")
        kontrol_dil(icerik.decode("utf-8"))
        ad = f"forecast_{gun}d_m{str(hedef_mw).replace('.', '')}.geojson"
        (gun_dizini / ad).write_bytes(icerik)
        kayitlar.append({"dosya": ad, "pencere_gun": gun,
                         "hedef_mw": hedef_mw, "n_hucre": sema["n_hucre"],
                         "sha256": _sha256(icerik)})
        if not quiet:
            print(f"  {gun:2d} gün · {sema['n_hucre']:4d} hücre · {ad}")

    # BÖLGE KARTLARI — iki zaman katmanı ayrı, aralarında aritmetik yok
    from src.operational.bolge_kartlari import kartlar as _kartlar
    # KARTLAR BU KOŞUNUN ÇIKTISINDAN ÜRETİLİR -- `latest`ten DEĞİL.
    #
    # V53: `latest` bu satırda hâlâ BİR ÖNCEKİ yayındır (aşağıda, en sonda
    # güncellenir). Kartlar oradan okununca harita bugünü, kartlar dünü
    # gösteriyordu. Yol artık açıkça verilir.
    kart = _kartlar(gun_dizini / "forecast_7d_m45.geojson")
    kart_tut = kontrol_kart_tutarliligi(kart, kayitlar)
    if not quiet:
        print(f"kart-tahmin tutarlılığı: {kart_tut['sha256']}… -> GEÇTİ")
    kart_icerik = json.dumps(kart, ensure_ascii=False).encode("utf-8")
    kontrol_dil(kart_icerik.decode("utf-8"))
    (gun_dizini / "bolge_kartlari.json").write_bytes(kart_icerik)
    kayitlar.append({"dosya": "bolge_kartlari.json",
                     "n_bolge": len(kart["bolgeler"]),
                     "sha256": _sha256(kart_icerik)})

    # SON DEPREMLER + TAHMİN KAYDI
    #
    # Olan biteni yayımlanmış tahminle eşleştirir. İDDİA SINIRI dosyanın
    # kendi başında yazılıdır: "listede vardı" bir sicildir, bir skor değil.
    # Buraya konmasının sebebi, eşleştirmenin YAYIN ANINDA ve yayımlanan
    # dosyanın kendisiyle yapılması gerektiğidir -- sonradan, başka bir
    # dosyadan yapılan eşleştirme V53 ailesine girer.
    from src.operational.son_depremler import son_depremler, tahmin_kaydi

    for ad, uret in (("son_depremler.json", son_depremler),
                     ("tahmin_kaydi.json", tahmin_kaydi)):
        veri = uret()
        icerik = json.dumps(veri, ensure_ascii=False).encode("utf-8")
        kontrol_dil(icerik.decode("utf-8"))
        (gun_dizini / ad).write_bytes(icerik)
        kayitlar.append({"dosya": ad,
                         "n_olay": len(veri.get("olaylar", [])),
                         "sha256": _sha256(icerik)})
        if not quiet:
            print(f"  {ad:22s} {len(veri.get('olaylar', [])):3d} olay")
    if not quiet:
        print(f"  bölge kartları · {len(kart['bolgeler'])} bölge · "
              "iki katman ayrı")

    manifest = {
        "uretim_zamani": t0.isoformat(),
        "origin": origin.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit, "calisma_agaci": "dirty" if izin_kirli else "clean",
        "katalog": tazelik, "urun_kapisi": kapi,
        "kalibre_parametreler": par,
        # MONOTONLUK REFERANSI -- bir sonraki koşu buradan okur.
        # Koruma böylece önbellekten bağımsız hâle gelir (Actions taşıması).
        "ham_satir_sayilari": _ham_satir_sayilari(),
        # TAZELİK SÖZLEŞMESİ -- makine-okunur.
        "tazelik": {
            "uretim_zamani": t0.isoformat(),
            "sonraki_beklenen": (t0 + timedelta(hours=YAYIN_ARALIGI_SAAT))
                                .isoformat(),
            "yayin_araligi_saat": YAYIN_ARALIGI_SAAT,
            "bayatlik_esigi_saat": BAYAT_YAYIN_ESIGI_SAAT,
            "kural": ("üretim zamanı FİİLÎ zamandır, planlanan değil. "
                      "Bu yayın, üretiminden BAYATLIK EŞİĞİ kadar süre "
                      "sonra 'güncel değil' sayılır ve arayüz uyarır."),
        },
        "min_times_normal": MIN_TIMES_NORMAL,
        "hedef_mw": hedef_mw, "pencereler": list(pencereler),
        "dosyalar": kayitlar,
        "korumalar": [ad for ad, _, _ in KORUMALAR],
        "korumalar_ayrinti": [{"ad": a, "istisna": i, "nerede": n}
                              for a, i, n in KORUMALAR],
        "yayin_adresi": YAYIN_ADRESI,
        "surum": 1,
    }
    (gun_dizini / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    # "latest" -- sembolik bağ yerine KOPYA (Windows'ta bağ ayrıcalık ister)
    son = PUBLISH / "latest"
    if son.exists():
        shutil.rmtree(son)
    shutil.copytree(gun_dizini, son)

    if not quiet:
        print(f"-> {gun_dizini}  ve  {son}")
    return manifest


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Operasyonel veri hattı")
    ap.add_argument("--no-update", action="store_true")
    ap.add_argument("--allow-dirty", action="store_true")
    ap.add_argument("--kontrol", action="store_true",
                    help="yalnızca korumaları çalıştır, yayım yapma")
    a = ap.parse_args()

    if a.kontrol:
        print("commit:", kontrol_agac(a.allow_dirty)[:12])
        print("katalog:", kontrol_katalog_tazeligi())
        print("korumalar çalışıyor.")
        return
    calistir(guncelle=not a.no_update, izin_kirli=a.allow_dirty)


if __name__ == "__main__":
    main()
