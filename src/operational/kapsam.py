"""YAYIN KAPSAMI — nerede konuşabiliriz?

BULGU (26 Ağu 2026, V43). Izgara ilan edilmiş bir dikdörtgendir
([35-43] K x [25-45] D) ve Yunanistan, Bulgaristan, Gürcistan, Suriye, Irak,
İran'ın bir kısmını içine alır. Yayımlanan 309 hücrenin **%50'si** Türkiye
dışındaydı ve en yüksek oranlı hücre (normalin **82,4 katı**) Irak'taydı.

SORUN SUNUM DEĞİL, GEÇERLİLİK. Katalog tamlığı ölçüldü:

    dış/iç olay oranı   M>=3,3: 0,346   M>=5,5: 0,639

Gerçek sismisite oranı büyüklüğe göre SABİT kalmalıdır. Artıyorsa küçük
olaylar kaydedilmiyor demektir: sınır dışında küçük olayların ~%46'sı
katalogda YOK.

Sonuç zincirleme:

    katalog eksik  ->  uzun vadeli temel oran DÜŞÜK kestiriliyor
                       (medyan 0,00180 vs içeride 0,00411)
                   ->  "normalin kaç katı" ŞİŞİYOR
                   ->  Kerkük'teki 82,4 kat gerçek bir sinyal değil,
                       eksik katalogun ürettiği YAPAY bir değer

KARAR (A). Yayın Türkiye sınırlarıyla kısıtlanır. Gerekçe projenin kendi
ilkesidir: **ölçemediğimiz yerde konuşmayız.** "Yayımla ama işaretle"
seçeneği, bilinen yanlış bir sayıyı uyarıyla süslemek olurdu.

AÇIK BIRAKILAN. Bölgesel Mc ölçüp temel oranı düzeltmek (seçenek C) daha
doğrusudur ama ayrı bir ölçüm işidir; bir sonraki ilan paketinin önceden
kayıtlı sorusu olarak yazılır.

SINIR KAYNAĞI. Natural Earth 10m admin-0 (kamu malı), künyeli:
`data/processed/tr_sinir.geojson`.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
SINIR_YOLU = PROC / "tr_sinir.geojson"

# Kıyı hücreleri: hücre MERKEZİ sınırın dışındaysa ama sınıra çok yakınsa,
# hücrenin bir kısmı karada olabilir. Tampon AÇIKÇA ilan edilir ve
# ÖLÇÜLMÜŞTÜR: ızgara adımı 0,25 derece; yarım hücre 0,125 derece.
# Tampon = yarım hücre, yani "merkezi dışarıda ama hücresi sınıra değiyor"
# durumunu kapsar, daha fazlasını değil.
TAMPON_DERECE = 0.125


class KapsamHatasi(Exception):
    """Kapsam sınırı okunamadı ya da uygulanamadı."""


def _halkalar() -> list[np.ndarray]:
    if not SINIR_YOLU.exists():
        raise KapsamHatasi(f"{SINIR_YOLU} yok — sınır olmadan yayım yapılmaz")
    g = json.loads(SINIR_YOLU.read_text(encoding="utf-8"))["geometry"]
    return [np.asarray(r, dtype=float)
            for p in g["coordinates"] for r in p]


def _nokta_ic(lon: float, lat: float, halka: np.ndarray) -> bool:
    """Işın atma (ray casting) — bir halkanın içinde mi."""
    x, y = halka[:, 0], halka[:, 1]
    x2, y2 = np.roll(x, -1), np.roll(y, -1)
    kesisim = ((y > lat) != (y2 > lat))
    with np.errstate(divide="ignore", invalid="ignore"):
        xk = x + (lat - y) * (x2 - x) / (y2 - y)
    return bool(np.sum(kesisim & (lon < xk)) % 2 == 1)


def _mesafe_derece(lon: float, lat: float, halka: np.ndarray) -> float:
    """Halkaya en kısa uzaklık (derece) — tampon kontrolü için."""
    return float(np.min(np.hypot(halka[:, 0] - lon, halka[:, 1] - lat)))


def icinde(lat: float, lon: float, tampon: float = TAMPON_DERECE) -> bool:
    """Hücre merkezi Türkiye sınırları içinde mi (tamponla)."""
    for h in _halkalar():
        if _nokta_ic(lon, lat, h):
            return True
    if tampon > 0:
        for h in _halkalar():
            if _mesafe_derece(lon, lat, h) <= tampon:
                return True
    return False


def hucre_maskesi(cell_ids) -> np.ndarray:
    """Hücre kimliklerinden kapsam maskesi (True = yayımlanabilir)."""
    from src.config import cell_center

    halkalar = _halkalar()
    out = []
    for c in cell_ids:
        la, lo = cell_center(int(c))
        ic = any(_nokta_ic(lo, la, h) for h in halkalar)
        if not ic and TAMPON_DERECE > 0:
            ic = any(_mesafe_derece(lo, la, h) <= TAMPON_DERECE
                     for h in halkalar)
        out.append(ic)
    return np.asarray(out, dtype=bool)


def kunye() -> dict:
    g = json.loads(SINIR_YOLU.read_text(encoding="utf-8"))
    p = g["properties"]
    return {
        "sinir_kaynagi": p["kaynak"], "lisans": p["lisans"],
        "kaynak_sha256": p["kaynak_sha256"],
        "sinir_sha256": hashlib.sha256(SINIR_YOLU.read_bytes()).hexdigest(),
        "tampon_derece": TAMPON_DERECE,
        "gerekce": ("katalog tamlığı sınır dışında ölçülmüş biçimde düşüktür "
                    "(küçük olayların ~%46'sı kayıtsız); temel oran düşük "
                    "kestirildiği için 'normalin kaç katı' şişer -- V43"),
    }
