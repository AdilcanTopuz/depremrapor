"""Jeodezik gerinim hızından ızgara öznitelikleri — projenin asıl araştırma bahsi.

Fay katmanı ablasyonda katkı vermemişti: haritalanmış fay izleri, geçmiş
sismisiteyle büyük ölçüde artık (redundant) çıktı. Gerinim hızı FARKLI bir
kaynaktan gelir — GPS/jeodezi — ve farklı bir şey ölçer:

  fay haritası    : "burada bir fay var" (geometri)
  gerinim hızı    : "burada kabuk şu hızla deforme oluyor" (gerilme birikim HIZI)

İkincisi sismisiteden bağımsız bir ölçümdür. Bir hücrede geçmişte deprem olmamış
olabilir ama kabuk hızla deforme oluyorsa gerilme birikiyordur — katalog tabanlı
hiçbir öznitelik bunu göremez. Hipotezin sınandığı yer tam olarak burasıdır.

Üretilen öznitelikler (hücre başına):
  strain_mean      : hücre içindeki ortalama ikinci invaryant (1e-9/yıl)
  strain_max       : hücre içindeki en yüksek değer
  strain_smooth25  : 25 km yarıçapta Gauss ağırlıklı ortalama — sismisite
                     yumuşatmasıyla aynı ölçek, böylece iki katman aynı
                     mekânsal çözünürlükte karşılaştırılabilir
  strain_grad      : yerel gradyanın büyüklüğü (komşu hücrelerle fark) —
                     gerinim hızındaki keskin değişimler fay sınırlarına
                     işaret eder

Çıktı: data/processed/strain_features.csv

LİSANS: kaynak veri CC-BY-NC-SA 3.0 (ticari kullanıma kapalı).
Bkz. scripts/05_download_gsrm.py
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "gsrm"
PROC = ROOT / "data" / "processed"

STEP = 0.25
DEG_KM = 111.19492664455873
SMOOTH_KM = 25.0


def main() -> None:
    src = RAW / "turkey_strain.csv"
    if not src.exists():
        raise SystemExit(f"! {src} yok — önce scripts/05_download_gsrm.py çalıştırın.")
    strain = pd.read_csv(src)
    print(f"{len(strain)} GSRM ızgara noktası (0.1 derece)")

    feat = pd.read_parquet(PROC / "grid_features.parquet")
    cells = (feat[["cell_id", "lat_c", "lon_c"]].drop_duplicates()
             .sort_values("cell_id").reset_index(drop=True))

    s_lat = strain["lat"].to_numpy()
    s_lon = strain["lon"].to_numpy()
    s_val = strain["strain_2nd_inv"].to_numpy()
    sig_deg = SMOOTH_KM / DEG_KM

    rows = []
    for _, c in cells.iterrows():
        # hücre içi (0.25 derece kutu)
        inside = ((np.abs(s_lat - c.lat_c) <= STEP / 2)
                  & (np.abs(s_lon - c.lon_c) <= STEP / 2))
        coslat = np.cos(np.radians(c.lat_c))
        d2 = ((s_lat - c.lat_c) ** 2 + ((s_lon - c.lon_c) * coslat) ** 2)
        w = np.exp(-d2 / (2 * sig_deg ** 2))
        rows.append({
            "cell_id": int(c.cell_id),
            "strain_mean": float(s_val[inside].mean()) if inside.any() else np.nan,
            "strain_max": float(s_val[inside].max()) if inside.any() else np.nan,
            "strain_smooth25": float((w * s_val).sum() / w.sum()) if w.sum() > 0 else np.nan,
        })

    out = pd.DataFrame(rows)
    # Gradyan: komşu hücrelerle farkın büyüklüğü. cell_id = lat_idx*1000 + lon_idx
    lut = out.set_index("cell_id")["strain_smooth25"]
    grads = []
    for cid in out.cell_id:
        here = lut.get(cid, np.nan)
        neigh = [lut.get(cid + d, np.nan) for d in (1, -1, 1000, -1000)]
        diffs = [abs(here - n) for n in neigh if pd.notna(n) and pd.notna(here)]
        grads.append(max(diffs) if diffs else np.nan)
    out["strain_grad"] = grads

    dst = PROC / "strain_features.csv"
    out.to_csv(dst, index=False)
    print(f"{len(out)} satır -> {dst}\n")
    print(out[["strain_mean", "strain_max", "strain_smooth25",
               "strain_grad"]].describe().round(1).to_string())

    # Fiziksel sağlama: gerinim hızı arttıkça sismisite artmalı.
    n = feat.groupby("cell_id")["n3650"].max()
    chk = out.set_index("cell_id").join(n.rename("n3650"))
    q = pd.qcut(chk.strain_smooth25, 5, labels=["en düşük", "düşük", "orta",
                                                "yüksek", "en yüksek"])
    print("\nSağlama — gerinim hızı beşlik dilimlerine göre olay sayısı (son 10 yıl):")
    print(chk.groupby(q, observed=True)["n3650"]
          .agg(["mean", "median", "count"]).round(1).to_string())


if __name__ == "__main__":
    main()
