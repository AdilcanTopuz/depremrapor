"""DONDURULMUŞ BULGUYU JSON'A AL — 109 MB bağımlılığı düşürür.

Bölge kartlarının 1. katmanı (modelin hangi bölgede ayırt edici olduğu)
2021-2024 dönemine aittir ve **DEĞİŞMEZ**. Her yayında 532.480 satırlık
değerlendirme tablosunu yeniden okumanın sebebi yok.

Bir kez hesaplanır, KÜNYELİ bir JSON olarak saklanır. Künye, dondurulmuş
bulgunun izlenebilirliğini korur: hangi tablodan, hangi katalogdan, hangi
parametrelerle, ne zaman.

Yeniden koşulması gereken tek durum: değerlendirme zemininin değişmesi
(yeni dönem, yeni katalog, yeni parametreler). O zaman künye de değişir ve
fark görünür olur.

Kullanım:  python scripts/35_bulgu_dondur.py
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"
TABLO = "etas_analytic_weekly"


def _sha_dizin(d: Path) -> str:
    """Dizindeki shard'ların birleşik sha256'sı — sıralı, kararlı."""
    h = hashlib.sha256()
    for f in sorted(d.glob("shard_*.csv")):
        h.update(f.name.encode())
        h.update(hashlib.sha256(f.read_bytes()).digest())
    return h.hexdigest()


def main() -> None:
    from src.operational.bolge_kartlari import dondurulmus_bulgu

    b = dondurulmus_bulgu(tablo=TABLO)
    b["kunye"] = {
        "uretim": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "kaynak_tablo": TABLO,
        "tablo_sha256": _sha_dizin(PROC / TABLO),
        "katalog_sha256": hashlib.sha256(
            (PROC / "catalog_merged.csv").read_bytes()).hexdigest(),
        "etas_params_sha256": hashlib.sha256(
            (PROC / "etas_params.json").read_bytes()).hexdigest(),
        "not": ("DONDURULMUŞ BULGU -- değerlendirme dönemine aittir ve "
                "yayından yayına değişmez. Zemin değişirse bu dosya yeniden "
                "üretilmelidir; künyedeki sha'lar farkı görünür kılar."),
    }
    dst = PROC / "bolge_bulgu_dondurulmus.json"
    dst.write_text(json.dumps(b, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"dönem {b['donem']} · {b['n_olay']} olay · "
          f"{len(b['bolgeler'])} bölge")
    for ad, v in sorted(b["bolgeler"].items()):
        h = v["hukum"]
        print(f"  {ad:38s} {v['olay']:3d} olay · {h}")
    print(f"\ntablo sha256 {b['kunye']['tablo_sha256'][:24]}…")
    print(f"-> {dst}  ({dst.stat().st_size / 1024:.1f} KB)")
    print(f"   (değerlendirme tablosu: "
          f"{sum(f.stat().st_size for f in (PROC / TABLO).glob('*.csv')) / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
