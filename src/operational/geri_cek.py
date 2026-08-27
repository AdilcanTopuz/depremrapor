"""GERİ ÇEKME — yayımlanmış bir tahmini yayından düşürmek.

İLKE: **yayımlanmış ve geri çekilmiş, hiç yayımlanmamıştan farklı bir
statüdür.** Bu yüzden geri çekme bir silme değil, bir *taşıma ve beyan*
işlemidir. Dosyalar `_geri_cekilen/<zaman>/` altına taşınır, gerekçe
`GERI_CEKILDI.md` dosyasına yazılır ve `latest/` bir önceki geçerli yayına
döndürülür.

NEDEN GIT YETMEZ. Git geçmişi zaten her şeyi saklar; dosya silinse bile
commit'te durur. Ama geçmişi okumak için git bilmek gerekir. Geri çekilmiş
bir sonucu görmek **git bilmeyi gerektirmemelidir** -- bu yüzden dosyalar
taşınır, silinmez ve site üzerinden erişilebilir kalır.

NE YAPMAZ. Bu modül bir *karar* vermez. Neyin geri çekileceğine insan karar
verir ve gerekçeyi yazar. Gerekçesiz geri çekme reddedilir: sessiz bir geri
çekme, sessiz bir hata kadar kötüdür.

KAPSAM. Yalnızca `yayin` dalının çalışma kopyası üzerinde çalışır. `main`
dalına dokunmaz -- oraya üretilmiş çıktı hiç girmez.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


class GeriCekmeHatasi(Exception):
    """Geri çekme reddedildi."""


# Geri çekmenin gerekçesi bu asgari uzunluğun altında olamaz.
#
# Sayı keyfî değil, İŞLEVSEL: "hata" ya da "yanlıştı" gibi bir kelime,
# altı ay sonra okuyan biri için hiçbir şey ifade etmez. Gerekçe en az
# şunları içerecek kadar yer tutmalıdır: NE yanlıştı, NASIL bulundu, NE
# yapıldı. Kısa bir cümle bunu taşıyamaz.
#
# Bu bir kalite güvencesi DEĞİLDİR -- 40 karakterlik anlamsız bir metin de
# geçer. Amacı, gerekçeyi yazmayı unutmuş birini durdurmaktır, kötü niyetli
# birini değil.
ASGARI_GEREKCE = 40


def _zaman_damgasi() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def geri_cek(kok: Path, gerekce: str, olcum: str = "",
             zaman: str | None = None, quiet: bool = False) -> dict:
    """`kok` altındaki yayını geri çeker.

    kok     -- yayın dalının çalışma kopyası (içinde `_arsiv/latest/`)
    gerekce -- NEDEN geri çekildiği; boş ya da çok kısa olamaz
    olcum   -- varsa, kararı destekleyen ölçüm (serbest metin)
    """
    if len(gerekce.strip()) < ASGARI_GEREKCE:
        raise GeriCekmeHatasi(
            f"gerekçe en az {ASGARI_GEREKCE} karakter olmalı "
            f"(verilen: {len(gerekce.strip())}). Sessiz geri çekme yoktur: "
            "ne yanlıştı, nasıl bulundu, ne yapıldı -- yazılmadan olmaz.")

    arsiv = kok / "_arsiv"
    latest = arsiv / "latest"
    if not latest.exists():
        raise GeriCekmeHatasi(
            f"{latest} yok -- geri çekilecek bir yayın bulunamadı")

    man_yolu = latest / "manifest.json"
    if not man_yolu.exists():
        raise GeriCekmeHatasi(f"{man_yolu} yok -- künyesiz yayın geri çekilmez")
    man = json.loads(man_yolu.read_text(encoding="utf-8"))

    zaman = zaman or _zaman_damgasi()
    hedef = kok / "_geri_cekilen" / zaman
    hedef.parent.mkdir(parents=True, exist_ok=True)

    # 1. TAŞI (silme değil).
    shutil.copytree(latest, hedef)

    # 2. GERİ ÇEKİLEN YAYININ ARŞİV KOPYASI DA ÇEKİLİR.
    #
    # V50. İlk yazımda yalnızca `latest/` taşınıyordu; yayının arşivdeki
    # kendi dizini yerinde kalıyordu. Sonuç: ikinci bir geri çekmede,
    # **az önce geri çekilen sürüm aday listesinin başına geçip geri
    # dönüyordu.** Yani geri çekme kalıcı değildi.
    #
    # Testin bulduğu bir kusurdur (`test_ESKI_KAYITLAR_SILINMEZ`); tek bir
    # geri çekmeyle sınayan bir test bunu asla göremezdi -- hata ancak
    # İKİNCİ işlemde ortaya çıkıyor.
    #
    # Eşleştirme künyeyle yapılır, dizin adıyla değil: yayının kimliği
    # üretim zamanı + katalog sha'sıdır, klasörün adı değil.
    kimlik = (man.get("uretim_zamani"),
              (man.get("katalog") or {}).get("sha256"))
    eslesen = []
    for d in arsiv.iterdir():
        if not d.is_dir() or d.name == "latest":
            continue
        m = d / "manifest.json"
        if not m.exists():
            continue
        mm = json.loads(m.read_text(encoding="utf-8"))
        if (mm.get("uretim_zamani"),
                (mm.get("katalog") or {}).get("sha256")) == kimlik:
            eslesen.append(d)
    for d in eslesen:
        shutil.move(str(d), str(hedef / f"_arsiv_{d.name}"))

    # 3. ÖNCEKİ GEÇERLİ YAYINI BUL.
    #
    # Arşivde kalan en yeni dizin. Yoksa geri dönülecek bir yayın yoktur ve
    # bu AÇIKÇA beyan edilir -- site "yayın geri çekildi, yerine geçen yok"
    # durumunu göstermelidir, sessizce boş kalmamalıdır.
    adaylar = sorted((d for d in arsiv.iterdir()
                      if d.is_dir() and d.name != "latest"),
                     key=lambda d: d.name, reverse=True)
    onceki = adaylar[0] if adaylar else None

    shutil.rmtree(latest)
    if onceki is not None:
        shutil.copytree(onceki, latest)

    # 4. BEYAN.
    kayit = {
        "zaman": zaman,
        "geri_cekilen": {
            "uretim_zamani": man.get("uretim_zamani"),
            "commit": man.get("commit"),
            "katalog_sha256": (man.get("katalog") or {}).get("sha256"),
            "dosyalar": [x.get("dosya") for x in man.get("dosyalar", [])],
        },
        "gerekce": gerekce.strip(),
        "olcum": olcum.strip() or None,
        "yerine_gecen": onceki.name if onceki else None,
        "nereye_tasindi": f"_geri_cekilen/{zaman}/",
    }
    (hedef / "geri_cekme_kaydi.json").write_text(
        json.dumps(kayit, indent=2, ensure_ascii=False), encoding="utf-8")

    _beyan_yaz(kok, kayit)

    if not quiet:
        print(f"geri çekildi -> _geri_cekilen/{zaman}/")
        print(f"  yerine geçen: {kayit['yerine_gecen'] or 'YOK'}")
    return kayit


def _beyan_yaz(kok: Path, kayit: dict) -> None:
    """`GERI_CEKILDI.md` -- en yeni kayıt en üstte, eskiler SİLİNMEZ."""
    yol = kok / "GERI_CEKILDI.md"
    baslik = "# GERİ ÇEKİLEN YAYINLAR\n\n"
    eski = ""
    if yol.exists():
        eski = yol.read_text(encoding="utf-8")
        if eski.startswith(baslik):
            eski = eski[len(baslik):]

    g = kayit["geri_cekilen"]
    yeni = (
        f"## {kayit['zaman']}\n\n"
        f"**Geri çekilen yayın:** {g['uretim_zamani']} "
        f"(commit `{(g['commit'] or '')[:12]}`, "
        f"katalog `{(g['katalog_sha256'] or '')[:12]}`)\n\n"
        f"**Gerekçe.** {kayit['gerekce']}\n\n"
        + (f"**Ölçüm.** {kayit['olcum']}\n\n" if kayit["olcum"] else "")
        + f"**Yerine geçen:** {kayit['yerine_gecen'] or '(yok)'}\n\n"
        f"**Nereye taşındı:** `{kayit['nereye_tasindi']}` — dosyalar "
        f"silinmedi. Yayımlanmış ve geri çekilmiş bir sonuç, hiç "
        f"yayımlanmamış bir sonuçtan farklı bir statüdedir.\n\n---\n\n")
    yol.write_text(baslik + yeni + eski, encoding="utf-8")


if __name__ == "__main__":
    import argparse

    a = argparse.ArgumentParser(description="Yayımlanmış bir tahmini geri çek")
    a.add_argument("kok", type=Path, help="yayın dalı çalışma kopyası")
    a.add_argument("--gerekce", required=True)
    a.add_argument("--olcum", default="")
    n = a.parse_args()
    geri_cek(n.kok, n.gerekce, n.olcum)
