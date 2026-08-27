"""GEM Global Active Faults veritabanından Türkiye faylarını indirir.

Kaynak: GEMScienceTools/gem-global-active-faults (açık erişim, CC-BY).
Türkiye için MTA diri fay haritası daha ayrıntılıdır ama kurumsal indirme
gerektirir; GEM veritabanı Türkiye faylarını (KAF, DAF, Ege genişleme sistemi)
kayma hızlarıyla birlikte içerdiği için başlangıç katmanı olarak yeterlidir.

Çıktı: data/raw/faults/turkey_faults.geojson  (Türkiye kutusuna kırpılmış)

Öznitelikler arasında en değerlisi `net_slip_rate` — "(tercih, alt, üst)" biçiminde
mm/yıl. Hızlı kayan bir fay gerilmeyi daha hızlı biriktirir, dolayısıyla bu doğrudan
fiziksel bir kovaryattır.

Kullanım:
    python scripts/04_download_faults.py
"""
import json
from pathlib import Path

import requests

URL = ("https://raw.githubusercontent.com/GEMScienceTools/gem-global-active-faults"
       "/master/geojson/gem_active_faults_harmonized.geojson")
RAW = Path(__file__).resolve().parents[1] / "data" / "raw" / "faults"
LAT0, LAT1, LON0, LON1 = 35.0, 43.0, 25.0, 45.0


def vertices(geom: dict):
    """LineString ya da MultiLineString'in tüm noktalarını verir."""
    if geom["type"] == "LineString":
        return list(geom["coordinates"])
    if geom["type"] == "MultiLineString":
        return [p for line in geom["coordinates"] for p in line]
    return []


def in_box(geom: dict) -> bool:
    return any(LON0 <= x <= LON1 and LAT0 <= y <= LAT1
               for x, y, *_ in vertices(geom))


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    cache = RAW / "gem_active_faults.geojson"
    if cache.exists() and cache.stat().st_size > 1_000_000:
        print(f"önbellek kullanılıyor: {cache}")
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        print("GEM aktif fay veritabanı indiriliyor...")
        r = requests.get(URL, timeout=300,
                         headers={"User-Agent": "deprem-tahmin-research/0.1"})
        r.raise_for_status()
        cache.write_text(r.text, encoding="utf-8")
        data = r.json()
    print(f"küresel fay sayısı: {len(data['features'])}")

    kept = [f for f in data["features"] if in_box(f["geometry"])]
    out = {"type": "FeatureCollection", "features": kept}
    dst = RAW / "turkey_faults.geojson"
    dst.write_text(json.dumps(out), encoding="utf-8")
    print(f"Türkiye kutusundaki fay: {len(kept)} -> {dst}")

    with_slip = sum(1 for f in kept
                    if (f["properties"].get("net_slip_rate") or "").strip("()") .split(",")[0].strip())
    print(f"kayma hızı bilgisi olan: {with_slip}/{len(kept)}")
    types = {}
    for f in kept:
        t = f["properties"].get("slip_type") or "bilinmiyor"
        types[t] = types.get(t, 0) + 1
    print("fay tipleri:")
    for t, n in sorted(types.items(), key=lambda kv: -kv[1])[:8]:
        print(f"  {t:28s} {n:4d}")


if __name__ == "__main__":
    main()
