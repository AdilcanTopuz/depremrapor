"""ÜRÜN KAPISI — hangi model operasyonel katmana girebilir.

İLAN EDİLMİŞ ÖLÇÜT (`docs/SITE_SARTNAME.md`, sonuç görülmeden bağlandı):

    gözlenen / beklenen oranı [0,80; 1,25] bandının DIŞINDA ise
    model operasyonel katmana ALINMAZ

NEDEN OTOMATİK. Bugün operasyonel katmanda tek model var (ETAS, 1,09) ve
kontrol trivial görünüyor. Ama kalibrasyonu düzeltilmiş bir NPP kapıya
dayandığında, kapının **otomatik ve kural-9 sınanmış** olması o günün
tartışmasını şimdiden bitirir: ölçüt sonuca göre yorumlanamaz, çünkü kod
yorumlamaz.

NEDEN SIRALAMA YETMEZ. AUC mükemmel olsa bile kalibrasyon bozuksa risk
kartında yazan sayı yanlıştır. Kullanıcı sıralama görmez, SAYI görür.

ÖLÇÜM PENCERESİ. Kalibrasyon geriye dönük ölçülür: yayımlanmış tahminler ile
gerçekleşen olaylar. Yayın günü ölçülemez -- pencere henüz kapanmamıştır.
Bu yüzden kapı, **son kapanmış değerlendirme** üzerinden kontrol edilir ve
hangi ölçüme dayandığı künyeye yazılır.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

BAND = (0.80, 1.25)          # İLAN EDİLMİŞ -- sonuca bakılarak değiştirilmez


class KapiKapali(Exception):
    """Model kalibrasyon şartını sağlamıyor; operasyonel katmana alınmaz."""


def kontrol(model: str, gozlenen: float, beklenen: float,
            band: tuple = BAND) -> dict:
    """Bir modelin kapıdan geçip geçmediği.

    Döner: {'model', 'oran', 'gecti', 'band', 'gerekce'}
    """
    if beklenen <= 0:
        raise KapiKapali(
            f"{model}: beklenen olay sayısı {beklenen} -- oran tanımsız. "
            "TANIMSIZ, GEÇERLİ DEĞİLDİR (V40).")
    oran = gozlenen / beklenen
    gecti = band[0] <= oran <= band[1]
    return {"model": model, "gozlenen": gozlenen, "beklenen": beklenen,
            "oran": oran, "gecti": gecti, "band": list(band),
            "gerekce": ("bandın içinde" if gecti else
                        f"bandın {'altında' if oran < band[0] else 'üstünde'}"
                        f" -- risk kartındaki sayı sistematik olarak "
                        f"{'yüksek' if oran < band[0] else 'düşük'} olur")}


def operasyonel_model_kontrolu(model: str = "ETAS") -> dict:
    """Yayın öncesi kapı kontrolü — son kapanmış değerlendirmeye dayanır.

    Kapı KAPALIYSA `KapiKapali` yükseltir; hat yayımı durdurur.
    """
    yol = PROC / "kapi_olcumu.json"
    if not yol.exists():
        raise KapiKapali(
            f"{yol.name} yok -- kapı ölçümü olmadan operasyonel yayım "
            "yapılmaz. Ölçüm: scripts/32_kapi_olcumu.py")
    o = json.loads(yol.read_text(encoding="utf-8"))
    if model not in o["modeller"]:
        raise KapiKapali(f"{model} için kapı ölçümü YOK: "
                         f"{sorted(o['modeller'])}")
    r = kontrol(model, o["modeller"][model]["gozlenen"],
                o["modeller"][model]["beklenen"])
    r["olcum_kunyesi"] = {k: o[k] for k in ("donem", "pencere_gun", "hedef_mw",
                                            "tablo", "olcum_tarihi")
                          if k in o}
    if not r["gecti"]:
        raise KapiKapali(
            f"{model} kalibrasyon oranı {r['oran']:.3f}, band {BAND} "
            f"{r['gerekce']}. Operasyonel katmana ALINMAZ.")
    return r
