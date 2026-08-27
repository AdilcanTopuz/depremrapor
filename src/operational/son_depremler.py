"""SON DEPREMLER ve TAHMİN KAYDI — olan biteni yayımlanmış tahminle eşleştirir.

İKİ ÇIKTI ÜRETİR:

  son_depremler.json  son N saatte Türkiye'de kaydedilen olaylar; her olayın
                      yanında, o gün yayımlanmış listede yer alıp almadığı
  tahmin_kaydi.json   arşivdeki BÜTÜN yayınlar üzerinden aynı eşleştirmenin
                      birikimli dökümü

--------------------------------------------------------------------------
BURADA NE İDDİA EDİLİYOR, NE EDİLMİYOR — bu dosyanın en önemli kısmı
--------------------------------------------------------------------------

Bir deprem, o gün yayımlanmış bir hücrenin içinde olduysa bunu söyleriz:
**"bu alan o gün yayımlanan listede vardı."** Söylediğimiz şey budur ve
yalnızca budur.

SÖYLEMEDİĞİMİZ ŞEY: "tahmin tuttu", "doğru bildik", "yöntem başarılı".
Bunlar bu veriden ÇIKARILAMAZ, üç sebeple:

  1. LİSTEYİ BÜYÜTMEK "İSABETİ" ARTIRIR. Eşiği 2 kat yerine 1,1 kat
     yapsak liste üç katına çıkar ve neredeyse her deprem "listede"
     olurdu. İsabet oranı, listenin genişliğiyle birlikte şişer; tek
     başına hiçbir şey ölçmez.

  2. TABAN ORAN YOK. Bir olayın listede olması, ancak "listede olmasaydı
     ne beklerdik" ile karşılaştırıldığında anlam taşır. O karşılaştırma
     bilgi kazancı ölçümüdür ve `metodoloji.html` sayfasındadır --
     güven aralığı ve saptanabilir en küçük farkla birlikte.

  3. HEDEF BÜYÜKLÜK M4,5. Liste M4,5 ve üzeri için üretilir. M3,2'lik bir
     olayın listedeki bir hücreye düşmesi, M4,5 tahmini hakkında bilgi
     TAŞIMAZ. Bu yüzden her olayın yanına hedef içinde mi dışında mı
     olduğu yazılır.

Bu dosya bir SİCİLDİR, bir SKOR DEĞİLDİR. Sicil tutulur çünkü yayımlanmış
bir tahminin ne olduğu geriye dönük olarak görülebilmelidir; skor iddia
etmek ayrı bir iştir ve ayrı bir yerde, ölçümle yapılır.

--------------------------------------------------------------------------
YAYIN ÖNCESİ OLAYLAR
--------------------------------------------------------------------------
Sistem 26 Ağustos 2026'da yayına başladı. Ondan önceki olaylar için
"listede miydi" sorusunun cevabı YOK'tur -- yanlış değil, YOK. Bu durum
`tahminde: null` ile işaretlenir ve arayüzde "o tarihte yayın yoktu" diye
yazılır. Yokluğu "listede değildi" diye göstermek, olmayan bir başarısızlık
uydurmak olurdu.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
PUBLISH = ROOT / "data" / "publish"

PENCERE_SAAT = 48          # "son depremler" penceresi
ASGARI_MAG = 2.5           # bu büyüklüğün altı listelenmez (katalog gürültüsü)
HEDEF_MW = 4.5             # tahminin hedefi; eşleştirme yalnızca bunun için anlamlı


class KayitHatasi(Exception):
    """Son depremler / tahmin kaydı üretilemedi."""


def _yer_adlari() -> dict:
    y = PROC / "hucre_yer_adlari.json"
    if not y.exists():
        return {}
    return json.loads(y.read_text(encoding="utf-8"))


def _katalog(saat: float) -> pd.DataFrame:
    from src.ingest.catalog_io import read_catalog

    yol = PROC / "catalog_merged.csv"
    if not yol.exists():
        raise KayitHatasi(f"{yol} yok — önce katalog güncellenmeli")
    df = read_catalog(yol)
    if df.empty:
        raise KayitHatasi("katalog boş")
    sinir = df.time.max() - pd.Timedelta(hours=saat)
    return df[df.time >= sinir].copy()


def _hucre(lat, lon) -> np.ndarray:
    from src.config import cell_id
    return cell_id(np.asarray(lat, dtype=float), np.asarray(lon, dtype=float))


def _yayin_hucreleri(tarih: str, gun: int = 1) -> dict | None:
    """Belirli bir tarihte yayımlanmış hücreler. Yayın yoksa None.

    None ile boş sözlük ARASINDAKİ FARK ÖNEMLİDİR:
      None  -> o gün yayın YAPILMADI (soru sorulamaz)
      {}    -> yayın yapıldı ama eşik üstü hücre yoktu (soru sorulur, cevap hayır)
    """
    ad = f"forecast_{gun}d_m{str(HEDEF_MW).replace('.', '')}.geojson"
    yol = PUBLISH / tarih / ad
    if not yol.exists():
        return None
    gj = json.loads(yol.read_text(encoding="utf-8"))
    return {int(f["properties"]["cell_id"]): f["properties"]
            for f in gj.get("features", [])}


def _olay_kaydi(satir, yerler: dict, onbellek: dict) -> dict:
    """Tek bir olayı, o günün yayımlanmış listesiyle eşleştirir."""
    from src.operational.kapsam import icinde

    cid = int(_hucre([satir.lat], [satir.lon])[0])
    tarih = satir.time.strftime("%Y-%m-%d")
    if tarih not in onbellek:
        onbellek[tarih] = _yayin_hucreleri(tarih, gun=1)
    yayin = onbellek[tarih]

    y = yerler.get(str(cid)) or {}
    hedefte = float(satir.mag) >= HEDEF_MW

    if yayin is None:
        tahminde, kat, gerekce = None, None, "o tarihte yayın yoktu"
    elif cid in yayin:
        tahminde = True
        kat = yayin[cid].get("times_normal")
        gerekce = "o gün yayımlanan listede vardı"
    else:
        tahminde = False
        kat = None
        gerekce = ("o gün yayımlanan listede yoktu — bu, olasılığın sıfır "
                   "olduğu anlamına gelmez, alan eşiğin altındaydı")

    return {
        "zaman": satir.time.isoformat(),
        "enlem": round(float(satir.lat), 4),
        "boylam": round(float(satir.lon), 4),
        "buyukluk": round(float(satir.mag), 1),
        "derinlik_km": (None if pd.isna(satir.depth_km)
                        else round(float(satir.depth_km), 1)),
        "kaynak": str(satir.source),
        "hucre_id": cid,
        "yer": y.get("ad"),
        "il": y.get("il"),
        "ilce": y.get("ilce"),
        "turkiye_ici": bool(icinde(float(satir.lat), float(satir.lon))),
        "hedef_buyuklukte": hedefte,
        "tahminde": tahminde,
        "kat": kat,
        "gerekce": gerekce,
    }


def son_depremler(saat: float = PENCERE_SAAT,
                  asgari_mag: float = ASGARI_MAG) -> dict:
    """Son N saatteki olaylar + yayımlanmış listeyle eşleştirme."""
    df = _katalog(saat)
    df = df[df.mag >= asgari_mag].sort_values("time", ascending=False)
    yerler = _yer_adlari()
    onbellek: dict = {}
    olaylar = [_olay_kaydi(r, yerler, onbellek) for r in df.itertuples()]
    ic = [o for o in olaylar if o["turkiye_ici"]]

    return {
        "uretim_zamani": datetime.now(timezone.utc).isoformat(),
        "pencere_saat": saat,
        "asgari_buyukluk": asgari_mag,
        "hedef_buyukluk": HEDEF_MW,
        "katalog_son_olay": str(df.time.max()) if len(df) else None,
        "toplam": len(olaylar),
        "turkiye_ici": len(ic),
        "hedef_buyuklukte": sum(1 for o in ic if o["hedef_buyuklukte"]),
        "olaylar": olaylar,
        "kapsam_notu": (
            "Liste, birleşik katalogda son {:.0f} saatte kaydedilen ve "
            "büyüklüğü {}'in üstünde olan olaylardır. Katalog AFAD, Kandilli, "
            "USGS ve EMSC'den derlenir; küçük olaylar bazı kaynaklara geç "
            "düşebilir, bu yüzden liste saatler içinde değişebilir."
        ).format(saat, str(asgari_mag).replace(".", ",")),
        "iddia_notu": (
            "Bir olayın yanında 'listede vardı' yazması, tahminin tuttuğu "
            "anlamına GELMEZ. Yayımlanan liste M{} ve üzeri için üretilir ve "
            "bir olasılık bildirir, bir olay bildirmez. Yöntemin uzun vadeli "
            "ortalamadan daha iyi olup olmadığı ayrı bir ölçümdür ve yöntem "
            "sayfasındadır."
        ).format(str(HEDEF_MW).replace(".", ",")),
    }


def tahmin_kaydi(asgari_mag: float = HEDEF_MW) -> dict:
    """Arşivdeki BÜTÜN yayınlar üzerinden birikimli sicil.

    Yalnızca HEDEF BÜYÜKLÜKTEKİ olaylar sayılır: liste M4,5 için üretilir,
    dolayısıyla eşleştirme yalnızca M4,5 ve üzeri için anlamlıdır.
    """
    from src.ingest.catalog_io import read_catalog

    tarihler = sorted(d.name for d in PUBLISH.iterdir()
                      if d.is_dir() and len(d.name) == 10 and d.name[4] == "-")
    if not tarihler:
        return {
            "uretim_zamani": datetime.now(timezone.utc).isoformat(),
            "yayin_gunu": 0, "ilk_yayin": None, "son_yayin": None,
            "asgari_buyukluk": asgari_mag, "olaylar": [],
            "sayim": {"toplam": 0, "listede": 0, "listede_degil": 0},
            "not": "Henüz arşivlenmiş yayın yok.",
        }

    yol = PROC / "catalog_merged.csv"
    if not yol.exists():
        raise KayitHatasi(f"{yol} yok")
    df = read_catalog(yol)
    bas = pd.Timestamp(tarihler[0] + " 00:00:00", tz="UTC")
    df = df[(df.time >= bas) & (df.mag >= asgari_mag)].sort_values(
        "time", ascending=False)

    yerler = _yer_adlari()
    onbellek: dict = {}
    olaylar = [_olay_kaydi(r, yerler, onbellek) for r in df.itertuples()]
    olaylar = [o for o in olaylar if o["turkiye_ici"]]

    listede = sum(1 for o in olaylar if o["tahminde"] is True)
    degil = sum(1 for o in olaylar if o["tahminde"] is False)
    yok = sum(1 for o in olaylar if o["tahminde"] is None)

    return {
        "uretim_zamani": datetime.now(timezone.utc).isoformat(),
        "yayin_gunu": len(tarihler),
        "ilk_yayin": tarihler[0],
        "son_yayin": tarihler[-1],
        "asgari_buyukluk": asgari_mag,
        "olaylar": olaylar,
        "sayim": {"toplam": len(olaylar), "listede": listede,
                  "listede_degil": degil, "yayin_yoktu": yok},
        "not": (
            "Bu bir SİCİLDİR, bir SKOR DEĞİLDİR. 'Listede vardı' sayısı tek "
            "başına yöntemin başarısını ölçmez: eşik düşürülse liste büyür ve "
            "bu sayı kendiliğinden artardı. Yöntemin uzun vadeli ortalamadan "
            "daha iyi olup olmadığı, bilgi kazancıyla ve güven aralığıyla "
            "ölçülür; o ölçüm yöntem sayfasındadır."
        ),
    }


if __name__ == "__main__":
    import sys

    s = son_depremler()
    print(f"son {s['pencere_saat']:.0f} saat: {s['toplam']} olay · "
          f"Türkiye içi {s['turkiye_ici']} · "
          f"hedef büyüklükte {s['hedef_buyuklukte']}")
    k = tahmin_kaydi()
    print(f"tahmin kaydı: {k['sayim']['toplam']} olay · "
          f"listede {k['sayim']['listede']} · "
          f"listede değil {k['sayim']['listede_degil']} · "
          f"yayın yoktu {k['sayim'].get('yayin_yoktu', 0)}")
    if "--json" in sys.argv:
        print(json.dumps(s, ensure_ascii=False, indent=2)[:2000])
