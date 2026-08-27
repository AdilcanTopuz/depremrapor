"""Fay geometrisinden ızgara öznitelikleri — Faz 3'ün ilk jeofizik katmanı.

README §1'deki araştırma bahsi şudur: mevcut nöral nokta süreçleri (RECAST vb.)
YALNIZCA katalog kullanıyor; jeofizik katman eklemek literatürde denenmemiş bir
kombinasyon. Bu modül o katmanların ilkini üretir.

Fiziksel gerekçe: depremler rastgele dağılmaz, fayların üzerinde olur. Hızlı kayan
bir fay gerilmeyi daha hızlı biriktirir, dolayısıyla birim zamanda daha çok deprem
üretir. Katalog tabanlı öznitelikler bunu ancak dolaylı olarak (geçmiş olaylardan)
görebilir; fay verisi doğrudan söyler ve özellikle SEYREK gözlemli hücrelerde
katalogda olmayan bilgiyi taşır.

Üretilen öznitelikler (hücre merkezi için):
  fault_dist_km        : en yakın fay izine mesafe
  fault_slip_rate      : en yakın fayın net kayma hızı (mm/yıl)
  fault_slip_max_50km  : 50 km içindeki en hızlı fayın kayma hızı
  fault_slip_sum_50km  : 50 km içindeki fayların toplam kayma hızı
  fault_count_50km     : 50 km içindeki fay sayısı

Mesafe için eşdikdörtgen yaklaşımı kullanılır; Türkiye kutusunda ortanca hatası
%0.011 ölçüldü (bkz. src/ingest/declustering.validate_distance).

Çıktı: data/processed/fault_features.csv  (cell_id ile birleştirilebilir)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "faults"
PROC = ROOT / "data" / "processed"

LAT0, LON0, STEP = 35.0, 25.0, 0.25
DEG_KM = 111.19492664455873
NEAR_KM = 50.0


def parse_slip(value) -> float:
    """`net_slip_rate` alanı "(tercih, alt, üst)" biçimindedir; tercih edileni alır."""
    if not value:
        return np.nan
    first = str(value).strip("() ").split(",")[0].strip()
    try:
        return float(first)
    except ValueError:
        return np.nan


def load_faults() -> list[dict]:
    """Her fay için {xy: (n,2) km dizisi, slip: mm/yıl} listesi döndürür."""
    path = RAW / "turkey_faults.geojson"
    if not path.exists():
        raise SystemExit(f"! {path} yok — önce scripts/04_download_faults.py çalıştırın.")
    data = json.loads(path.read_text(encoding="utf-8"))

    out = []
    for f in data["features"]:
        geom = f["geometry"]
        lines = ([geom["coordinates"]] if geom["type"] == "LineString"
                 else geom["coordinates"] if geom["type"] == "MultiLineString" else [])
        slip = parse_slip(f["properties"].get("net_slip_rate"))
        for line in lines:
            pts = np.array([(x, y) for x, y, *_ in line], dtype=float)
            if len(pts) < 2:
                continue
            out.append({"lon": pts[:, 0], "lat": pts[:, 1], "slip": slip})
    return out


def point_to_polyline_km(lat: float, lon: float, f: dict) -> float:
    """Bir noktadan çok-parçalı çizgiye en kısa mesafe (km).

    Yalnızca köşe noktalarına değil, PARÇALARA olan mesafe hesaplanır: uzun ve
    seyrek noktalı bir fay izinde köşe mesafesi gerçek uzaklığı ciddi biçimde
    fazla gösterir.
    """
    coslat = np.cos(np.radians(lat))
    fx = (f["lon"] - lon) * coslat * DEG_KM     # doğu-batı, km
    fy = (f["lat"] - lat) * DEG_KM              # kuzey-güney, km
    ax, ay = fx[:-1], fy[:-1]
    bx, by = fx[1:], fy[1:]
    dx, dy = bx - ax, by - ay
    seg_len2 = dx * dx + dy * dy
    with np.errstate(invalid="ignore", divide="ignore"):
        t = np.where(seg_len2 > 0, -(ax * dx + ay * dy) / seg_len2, 0.0)
    t = np.clip(t, 0.0, 1.0)
    cx, cy = ax + t * dx, ay + t * dy
    return float(np.sqrt(cx * cx + cy * cy).min())


def main() -> None:
    faults = load_faults()
    print(f"{len(faults)} fay parçası yüklendi "
          f"({sum(len(f['lon']) for f in faults)} nokta)")

    feat = pd.read_parquet(PROC / "grid_features.parquet")
    cells = (feat[["cell_id", "lat_c", "lon_c"]].drop_duplicates()
             .sort_values("cell_id").reset_index(drop=True))
    print(f"{len(cells)} hücre için fay öznitelikleri hesaplanıyor...")

    rows = []
    slips = np.array([f["slip"] for f in faults])
    for _, c in cells.iterrows():
        d = np.array([point_to_polyline_km(c.lat_c, c.lon_c, f) for f in faults])
        near = d <= NEAR_KM
        nearest = int(d.argmin())
        rows.append({
            "cell_id": int(c.cell_id),
            "fault_dist_km": float(d[nearest]),
            "fault_slip_rate": float(slips[nearest]),
            "fault_slip_max_50km": float(np.nanmax(slips[near])) if near.any() else 0.0,
            "fault_slip_sum_50km": float(np.nansum(slips[near])) if near.any() else 0.0,
            "fault_count_50km": int(near.sum()),
        })

    out = pd.DataFrame(rows)
    dst = PROC / "fault_features.csv"
    out.to_csv(dst, index=False)
    print(f"{len(out)} satır -> {dst}\n")
    print(out[["fault_dist_km", "fault_slip_rate", "fault_slip_max_50km",
               "fault_slip_sum_50km", "fault_count_50km"]].describe().round(2).to_string())

    # Sağlama: sismisite yoğunluğu faya yakınlıkla artmalı. Artmıyorsa ya fay
    # verisi ya da mesafe hesabı bozuktur.
    n = feat.groupby("cell_id")["n3650"].max()
    chk = out.set_index("cell_id").join(n.rename("n3650"))
    bins = pd.cut(chk.fault_dist_km, [0, 5, 10, 20, 40, 1000])
    print("\nSağlama — faya uzaklığa göre ortalama olay sayısı (son 10 yıl):")
    print(chk.groupby(bins, observed=True)["n3650"].agg(["mean", "count"]).round(1).to_string())


if __name__ == "__main__":
    main()
