"""BÖLGE KARTLARI — iki zaman katmanı, birbirine karışmadan.

İLAN EDİLMİŞ ÜÇ KURAL (`docs/SITE_SARTNAME.md`):

  1. ARALIKSIZ BÖLGESEL İDDİA YOK -- her bölgesel sayı güven aralığıyla gelir
  2. "FARK GÖSTERİLEMEDİ" bölgeleri AÇIKÇA işaretli (zayıflık değil belirsizlik)
  3. MDE'LER GÖRÜNÜR -- "fark yok" MDE olmadan yazılmaz

VE DÖRDÜNCÜ, EN KOLAY KARIŞAN:

  4. İKİ ZAMAN KATMANI AYRI DURUR

        KATMAN 1  dondurulmuş bulgu   "Marmara'da fark GÖSTERİLEMEDİ"
                  2021-2024 · künyeli · MDE'li -- TARİHLİ BİR BULGU
        KATMAN 2  güncel tahmin       "bu hafta M>=4,5 olasılığı %X"
                  bugünün sayısı -- GÜNLÜK BİR ÖLÇÜM

Birincisi modelin o bölgedeki AYIRT EDİCİLİK durumunu söyler; ikincisi
bugünün OLASILIĞINI. Tek iddiaya birleştirilirse, tarihli bir belirsizlik
beyanı günlük bir tahmin gibi okunur.

Kartlar bu yüzden iki ayrı alan taşır: `dondurulmus_bulgu` ve `guncel`.
Aralarında hiçbir aritmetik yapılmaz.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
PUBLISH = ROOT / "data" / "publish"

ASGARI_OLAY = 5          # bunun altında IG yazılmaz (ilan edilmiş)


def _bolge_of(cell_id: int) -> str:
    from src.config import cell_center
    from src.eval.gain_breakdown import region_of

    la, lo = cell_center(int(cell_id))
    return region_of(la, lo)


BULGU_YOLU = PROC / "bolge_bulgu_dondurulmus.json"


class BulguYok(Exception):
    """Dondurulmuş bulgu dosyası yok ya da künyesi eksik."""


def bulgu_oku() -> dict:
    """KATMAN 1'i DONDURULMUŞ dosyadan okur — hesaplamaz.

    NEDEN DOSYADAN. Bu katman 2021-2024 dönemine aittir ve yayından yayına
    DEĞİŞMEZ. Her koşuda 532.480 satırlık değerlendirme tablosunu okumak
    109 MB'lık bir bağımlılık yaratıyordu; dosya 2,2 KB.

    Değişmeyen verinin her koşuda taşınması da ÖLÇÜLMEMİŞ bir bağımlılıktı
    (bileşen-gerekliliği ilkesinin veri tarafı).

    KÜNYE ZORUNLU: dondurulmuş bir eser bayatlayabilir; künyesi olmayan
    dosya okunmaz.
    """
    if not BULGU_YOLU.exists():
        raise BulguYok(
            f"{BULGU_YOLU.name} yok — bulgu olmadan kart üretilmez. "
            "Üretim: scripts/35_bulgu_dondur.py")
    b = json.loads(BULGU_YOLU.read_text(encoding="utf-8"))
    k = b.get("kunye") or {}
    eksik = [a for a in ("uretim", "kaynak_tablo", "tablo_sha256",
                         "katalog_sha256", "etas_params_sha256")
             if not k.get(a)]
    if eksik:
        raise BulguYok(f"dondurulmuş bulgunun künyesi eksik: {eksik}")
    return b


def dondurulmus_bulgu(tablo: str = "etas_analytic_weekly",
                      pencere: int = 7, mw: float = 4.5) -> dict:
    """KATMAN 1'i YENİDEN HESAPLAR — yalnızca dondurma betiği çağırır.

    Bu, TARİHLİ bir bulgudur: değerlendirme dönemine aittir ve günlük
    tahminle karıştırılmaz. Günlük yayın bunu ÇAĞIRMAZ; `bulgu_oku()`
    kullanır.
    """
    from src.eval import daily_backtest as db
    from src.eval.gain_breakdown import _ig_ci

    db.FORECAST_DIR = tablo
    t = db.build_table(pencere, mw, quiet=True)
    t["bölge"] = [_bolge_of(c) for c in t.cell_id]

    out = {}
    for ad, sub in t.groupby("bölge"):
        n = int(sub.y.sum())
        if n < ASGARI_OLAY:
            out[ad] = {"olay": n, "hukum": "olay sayısı yetersiz",
                       "ig": None, "ga": None, "mde": None}
            continue
        ig, lo, hi, mde, _ = _ig_ci(sub)
        if lo > 0:
            hukum = "ETAS üstün"
        elif hi < 0:
            hukum = "ETAS altında"
        else:
            hukum = "fark gösterilemedi"
        out[ad] = {"olay": n, "hukum": hukum, "ig": round(ig, 3),
                   "ga": [round(lo, 3), round(hi, 3)], "mde": round(mde, 3)}
    return {
        "katman": "dondurulmuş bulgu",
        "ne_soyler": ("modelin o bölgede uzun vadeli orana göre AYIRT EDİCİ "
                      "olup olmadığı"),
        "donem": f"{t.ref_date.min():%Y-%m-%d} .. {t.ref_date.max():%Y-%m-%d}",
        "pencere_gun": pencere, "hedef_mw": mw, "tablo": tablo,
        "n_olay": int(t.y.sum()), "bolgeler": out,
        "uyari": ("'fark gösterilemedi' ZAYIFLIK DEĞİL BELİRSİZLİKTİR: "
                  "o bölgede fark olmadığı değil, bu veriyle GÖSTERİLEMEDİĞİ "
                  "ölçülmüştür. MDE, gösterilebilecek en küçük farktır."),
    }


def guncel(geojson_yolu: Path) -> dict:
    """KATMAN 2 — BU KOŞUNUN tahmini, bölgeye toplanmış.

    YOL ZORUNLUDUR VE VARSAYILANI YOKTUR (V53).

    İlk yazımda varsayılan `PUBLISH/latest/forecast_7d_m45.geojson` idi.
    Ama hat, bugünün tahminlerini önce GÜN DİZİNİNE yazar ve `latest`i
    ancak en sonda günceller. Yani kartlar, koşunun kendi çıktısını değil
    **BİR ÖNCEKİ YAYINI** okuyordu: harita bugünü, kartlar dünü
    gösteriyordu ve aynı sayfada iki farklı güne ait sayı vardı.

    Yerelde hiç görülmedi çünkü `latest/` her zaman doluydu; hata
    sessizdi. Taze checkout'lu ilk bulut koşusunda `latest/` yoktu ve
    sessiz ayrışma bir ÇÖKMEYE dönüştü -- taşımanın kendisi hatayı
    görünür kıldı.

    Varsayılan geri konmaz: bir varsayılan yol, "hangi dosyayı okuduğumu
    düşünmedim" demenin sessiz biçimidir. Çağıran, hangi tahmini
    okuduğunu SÖYLEMEK zorundadır.
    """
    yol = Path(geojson_yolu)
    if not yol.exists():
        raise FileNotFoundError(f"{yol} yok — bu koşunun tahmini okunamadı")
    gj = json.loads(yol.read_text(encoding="utf-8"))
    p = gj["properties"]

    satir = []
    for f in gj["features"]:
        pr = f["properties"]
        satir.append({"cell_id": int(pr["cell_id"]),
                      "p": float(pr["probability"]),
                      "kat": pr.get("times_normal")})
    d = pd.DataFrame(satir)
    if d.empty:
        return {"katman": "güncel tahmin", "bolgeler": {}, "uyari": "boş"}
    d["bölge"] = [_bolge_of(c) for c in d.cell_id]

    out = {}
    for ad, sub in d.groupby("bölge"):
        # BÖLGE OLASILIĞI = en az bir hücrede olay; hücreler bağımsız
        # varsayılır (ETAS'ta yaklaşık doğru: aynı pencerede farklı
        # hücrelerin tetiklenmesi büyük ölçüde ayrık kaynaklardan gelir).
        # VARSAYIM AÇIKÇA YAZILIR.
        p_yok = float(np.prod(1.0 - sub.p.to_numpy()))
        katlar = sub.kat.dropna()
        out[ad] = {
            "yayimlanan_hucre": len(sub),
            "bolge_olasiligi": round(1.0 - p_yok, 5),
            "en_yuksek_hucre_p": round(float(sub.p.max()), 5),
            "en_yuksek_kat": (round(float(katlar.max()), 1)
                              if len(katlar) else None),
        }
    return {
        "katman": "güncel tahmin",
        "ne_soyler": "bugünün olasılığı",
        "origin": p["origin"], "pencere_gun": p["window_days"],
        "hedef_mw": p["target_magnitude"],
        "esik": p["min_times_normal"],
        "kunye": p["fingerprint"],
        # KAYNAK KİMLİĞİ. Kartların hangi tahmin dosyasından üretildiği
        # künyeye yazılır; harita ile kartların ayrışması (V53) bir daha
        # olursa SESSİZ olamaz -- iki sha256 karşılaştırılabilir.
        "kaynak_dosya": yol.name,
        "kaynak_sha256": hashlib.sha256(yol.read_bytes()).hexdigest(),
        "bolgeler": out,
        "varsayim": ("bölge olasılığı, hücrelerin BAĞIMSIZ olduğu "
                     "varsayımıyla birleştirilmiştir; aynı pencerede "
                     "komşu hücreler bir arada tetiklenebilir, bu yüzden "
                     "gerçek olasılık biraz DAHA DÜŞÜK olabilir"),
    }


def kartlar(geojson_yolu: Path) -> dict:
    """İki katman, YAN YANA ama BİRLEŞTİRİLMEDEN.

    `geojson_yolu` BU KOŞUNUN 7 günlük tahmin dosyasıdır (V53).
    """
    k1 = bulgu_oku()
    k2 = guncel(geojson_yolu)
    ortak = sorted(set(k1["bolgeler"]) | set(k2["bolgeler"]))
    birlesik = {}
    for ad in ortak:
        g = k2["bolgeler"].get(ad)
        if g is None:
            # YOKLUĞUN SESSİZLİĞİ DEĞİL, YOKLUĞUN BEYANI.
            #
            # Bir bölgede bu hafta eşik üstü hücre yoksa, kart o bölgeyi
            # ATLAMAZ -- açıkça "eşik üstü hücre yok" der. Satırın olmaması,
            # okuyucuya "veri yok" ile "risk yok" arasında ayrım bırakmaz;
            # ikisi farklı ifadelerdir.
            #
            # (Aracın sessizliğini dünyanın sessizliği sanmama ilkesinin
            #  arayüz karşılığı.)
            g = {"yayimlanan_hucre": 0, "bolge_olasiligi": None,
                 "en_yuksek_hucre_p": None, "en_yuksek_kat": None,
                 "beyan": ("bu hafta bu bölgede eşik üstü hücre YOK -- "
                           "yayımlanan hücre eşiği normalin "
                           f"{k2.get('esik', '?')} katıdır; bölgedeki "
                           "hücreler bu eşiğin altında kaldı")}
        birlesik[ad] = {
            "dondurulmus_bulgu": k1["bolgeler"].get(ad),
            "guncel": g,
        }
    return {
        "uretim": datetime.now(timezone.utc).isoformat(),
        "KURAL": ("iki katman AYRI okunur; aralarında aritmetik YAPILMAZ. "
                  "Katman 1 tarihli bir bulgudur (modelin ayırt ediciliği), "
                  "katman 2 bugünün ölçümüdür (olasılık)."),
        "katman1_kunyesi": {**{k: k1[k] for k in
                               ("donem", "pencere_gun", "hedef_mw", "tablo",
                                "n_olay", "uyari")},
                            "dondurulmus": k1["kunye"]},
        "katman2_kunyesi": {k: k2[k] for k in
                            ("origin", "pencere_gun", "hedef_mw", "esik",
                             "kunye", "varsayim",
                             "kaynak_dosya", "kaynak_sha256") if k in k2},
        "bolgeler": birlesik,
    }


def yaz(geojson_yolu: Path, dst: Path | None = None) -> Path:
    dst = dst or (PUBLISH / "latest" / "bolge_kartlari.json")
    dst.write_text(json.dumps(kartlar(geojson_yolu), indent=2,
                              ensure_ascii=False),
                   encoding="utf-8")
    return dst
