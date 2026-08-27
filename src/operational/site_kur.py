"""SİTE KURUCUSU — yayımlanan veriyi statik siteye taşır.

TEK İLKE: **arayüz, verinin söylediğinden fazlasını söyleyemez.**

Bu modül hiçbir sayı ÜRETMEZ; yalnızca `data/publish/latest/` altındakileri
`web/data/` altına kopyalar ve künyeyi tek bir yerde toplar. Sitede görünen
her şeyin JSON'da bir karşılığı vardır ve o JSON indirilebilir.

NEDEN KOPYA, SEMBOLİK BAĞ DEĞİL. Statik barındırma sembolik bağ izlemez;
ayrıca kopyanın sha256'sı künyeye yazılır ve sitede gösterilen dosyanın
yayımlanan dosyayla aynı olduğu DENETLENEBİLİR olur.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISH = ROOT / "data" / "publish" / "latest"
WEB = ROOT / "web"
WEB_DATA = WEB / "data"

# Siteye taşınacak dosyalar. Listede OLMAYAN bir dosya siteye çıkmaz --
# "her ihtimale karşı kopyala" yok.
DOSYALAR = (
    "hucre_yer_adlari.json",
    "forecast_1d_m45.geojson",
    "forecast_7d_m45.geojson",
    "forecast_30d_m45.geojson",
    "bolge_kartlari.json",
    "son_depremler.json",
    "tahmin_kaydi.json",
    "manifest.json",
)


import datetime as _dt


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def kur(quiet: bool = False) -> dict:
    if not PUBLISH.exists():
        raise SystemExit(f"! {PUBLISH} yok — önce hat çalıştırılmalı")
    WEB_DATA.mkdir(parents=True, exist_ok=True)

    tasinan = {}
    for ad in DOSYALAR:
        # Yer adları yayın dizininde değil, işlenmiş veride durur: yayından
        # yayına değişmez (katalog büyüdükçe seyrek güncellenir).
        kaynak = (ROOT / "data" / "processed" / ad
                  if ad == "hucre_yer_adlari.json" else PUBLISH / ad)
        if not kaynak.exists():
            raise SystemExit(f"! {kaynak} yok — eksik dosyayla site kurulmaz")
        hedef = WEB_DATA / ad
        shutil.copy2(kaynak, hedef)
        h = _sha256(hedef)
        assert h == _sha256(kaynak), "kopya bozuldu"
        tasinan[ad] = {"sha256": h, "bayt": hedef.stat().st_size}
        if not quiet:
            print(f"  {ad:28s} {hedef.stat().st_size / 1024:8.1f} KB  "
                  f"{h[:12]}…")

    # BELGE SAYFALARI HER KURULUMDA YENİDEN ÜRETİLİR.
    #
    # Vaka defteri ve denetim mirası sitede yayımlanır (şeffaflık kararı).
    # Elle HTML'e çevrilmez: kopya kaynakla ayrışır ve ayrışma SESSİZDİR --
    # V42'de tam bu oldu. Tek kaynak: docs/*.md
    from src.operational.belge_sayfa import uret as _belge_uret

    for yol in _belge_uret(quiet=True):
        if not quiet:
            print(f"  {yol.name:28s} belgeden üretildi")

    # SAYFALAR DA DİL DENETİMİNDEN GEÇER.
    #
    # Yayımlanan JSON denetleniyordu ama SAYFALAR denetlenmiyordu -- oysa
    # kullanıcının okuduğu metin sayfadır. İlk sürümde metodoloji sayfası
    # uyarı metnini ELLE KOPYALAMIŞTI ve denetimden düştü (V42): kopya,
    # onaylı metinle birebir olmadığı için muafiyetini kaybetmişti.
    # Çözüm kopyayı düzeltmek değil, KOPYAYI KALDIRMAK oldu; sayfa metni
    # kunye.json'dan yükler.
    # KAPSAM: dil denetimi TAHMİN SUNAN sayfalara uygulanır.
    #
    # Belge sayfaları (vaka defteri, denetim mirası) korumanın KENDİSİNİ
    # belgeler ve yasak kalıpların listesini ZORUNLU OLARAK içerir --
    # "kesin", "garanti", örnek ihlal cümleleri. Bir metnin bir kalıbı
    # KULLANMASI ile ANMASI farklı şeylerdir ve desen eşleşmesi bunu ayırt
    # edemez (V48; V47'nin kardeşi -- orada iddia/ret, burada kullanım/anma).
    #
    # Kaçınarak çözülemez: defter, ihlalleri örneklemek ZORUNDADIR.
    #
    # MİTİGASYON: belge sayfaları tahmin sunmaz (sayı, harita, olasılık
    # içermezler) ve insan gözüyle okunur. Koruma onların yerine geçmez;
    # unutulmaya karşı korur -- ve belge sayfalarında unutulacak bir şey
    # yoktur, çünkü içerikleri kaynak belgelerden gelir.
    from src.operational.belge_sayfa import BELGELER
    from src.operational.pipeline import DilHatasi, kontrol_dil

    belge_sayfalari = set(BELGELER)
    for sayfa in sorted(WEB.glob("*.html")):
        if sayfa.name in belge_sayfalari:
            if not quiet:
                print(f"  {sayfa.name:28s} dil denetimi KAPSAM DIŞI "
                      "(belge — kalıpları anar, kullanmaz)")
            continue
        try:
            kontrol_dil(sayfa.read_text(encoding="utf-8"))
        except DilHatasi as e:
            raise SystemExit(f"! {sayfa.name}: {e}")
        if not quiet:
            print(f"  {sayfa.name:28s} dil denetimi TEMİZ")

    # SITEMAP VE ROBOTS ÜRETİLİR, ELLE YAZILMAZ.
    #
    # Elle tutulan bir sitemap, sayfa eklendiğinde ya da silindiğinde
    # kaynağından ayrışır ve ayrışma SESSİZDİR (V42'nin kalıbı). Burada
    # gerçekten var olan sayfalardan üretilir; adres tek kaynaktan gelir.
    from src.operational.pipeline import YAYIN_ADRESI

    _sayfalar = sorted(x.name for x in WEB.glob("*.html"))
    _gun = _dt.datetime.now(_dt.timezone.utc).date().isoformat()
    _girdiler = "\n".join(
        f"  <url><loc>{YAYIN_ADRESI}/"
        f"{'' if ad == 'index.html' else ad}</loc>"
        f"<lastmod>{_gun}</lastmod></url>"
        for ad in _sayfalar)
    (WEB / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{_girdiler}\n</urlset>\n", encoding="utf-8")
    (WEB / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\n"
        f"Sitemap: {YAYIN_ADRESI}/sitemap.xml\n", encoding="utf-8")
    if not quiet:
        print(f"  {'sitemap.xml':28s} {len(_sayfalar)} sayfa + robots.txt")

    # VAKA SAYISI KÜNYEDEN OKUNUR, SAYFAYA YAZILMAZ.
    #
    # Metodoloji sayfasında "Vaka defteri — 38 kayıt" diye ELLE yazılmış bir
    # sayı vardı; defter 51 kayda çıkmıştı. Elle yazılan bir sayı kaynağından
    # ayrışır ve ayrışma SESSİZDİR -- V42'nin tam kalıbı. Sayı burada
    # sayılır, sayfa onu künyeden okur.
    import re as _re

    _defter = ROOT / "docs" / "VAKA_DEFTERI.md"
    # BAŞLIK DEĞİL VAKA sayılır: bir başlık iki vakayı taşıyabilir
    # (`## V11 / V12 — ...`). Başlık saymak 50 verirdi, oysa 51 vaka var.
    _b = _re.findall(r"^##\s+(V\d+.*)$",
                     _defter.read_text(encoding="utf-8"), _re.M)
    vaka_sayisi = len({int(n) for b in _b for n in _re.findall(r"V(\d+)", b)})

    man = json.loads((PUBLISH / "manifest.json").read_text(encoding="utf-8"))
    gj = json.loads((PUBLISH / "forecast_7d_m45.geojson").read_text(
        encoding="utf-8"))
    kunye = {
        "site_kurulum": datetime.now(timezone.utc).isoformat(),
        "yayin_origin": man["origin"],
        "yayin_uretim": man["uretim_zamani"],
        "commit": man["commit"],
        "calisma_agaci": man["calisma_agaci"],
        "katalog": man["katalog"],
        "tazelik": man.get("tazelik"),
        "urun_kapisi": man.get("urun_kapisi"),
        "min_times_normal": man["min_times_normal"],
        "model_kunyesi": gj["properties"]["fingerprint"],
        "uyari_metni": gj["properties"]["disclaimer"],
        "yayin_adresi": man.get("yayin_adresi"),
        "vaka_sayisi": vaka_sayisi,
        "korumalar": man.get("korumalar"),
        "dosyalar": tasinan,
        "ilke": ("Sitede görünen her sayının bu dosyalarda bir karşılığı "
                 "vardır; dosyalar indirilebilir ve sha256'ları buradadır."),
    }
    (WEB_DATA / "kunye.json").write_text(
        json.dumps(kunye, indent=2, ensure_ascii=False), encoding="utf-8")
    if not quiet:
        print(f"  {'kunye.json':28s} (künye + sha256 listesi)")
        print(f"-> {WEB_DATA}")
    return kunye


if __name__ == "__main__":
    kur()
