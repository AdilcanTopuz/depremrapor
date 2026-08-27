"""Mw dönüşüm bağıntılarını Türkiye verisiyle yeniden kalibre eder.

Katalog birleştirmesi, farklı büyüklük tiplerini (ML, Md, Ms, mb) ortak bir ölçeğe —
moment büyüklüğü Mw'ye — çevirmek zorundadır. Şimdiye kadar literatürden alınmış
ortalama bağıntılar kullanıldı; bunlar Türkiye ağına özgü değil ve büyüklükleri
sistematik kaydırabilir. Bir kaydırma doğrudan Mc'ye, b-değerine ve ETAS
üretkenliğine geçer.

Kandilli kataloğu aynı olay için birden fazla büyüklük tipi raporlar; bu, dönüşümü
doğrudan Türkiye verisinden regresyonla kestirmeyi mümkün kılar.

**Yöntem: ortogonal (Deming) regresyon, sıradan EKK değil.** Sıradan en küçük
kareler bağımsız değişkenin hatasız olduğunu varsayar. Burada ML de Mw de ölçüm
hatası taşır; EKK bu durumda eğimi sistematik olarak sıfıra doğru bastırır
(regression dilution). Ortogonal regresyon her iki eksendeki hatayı da hesaba katar
ve büyüklük dönüşümü literatüründe standarttır (Castellaro et al., 2006).

Çıktı: data/processed/mw_conversion.json  (merge_catalogs bunu otomatik okur)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

# Şu an kullanılan literatür değerleri — karşılaştırma için
LITERATURE = {"ml": (0.953, 0.422), "md": (1.011, 0.038), "mb": (1.048, -0.142)}
MIN_PAIRS = 100          # altında regresyon güvenilmez
MAX_RESIDUAL = 1.5       # bu kadar sapan çiftler eşleşme hatası sayılır


def deming(x: np.ndarray, y: np.ndarray, lam: float = 1.0):
    """Ortogonal (Deming) regresyon: y = a*x + b. lam = var(y)/var(x)."""
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    syy = ((y - ym) ** 2).sum()
    sxy = ((x - xm) * (y - ym)).sum()
    if abs(sxy) < 1e-12:
        return np.nan, np.nan
    a = (syy - lam * sxx + np.sqrt((syy - lam * sxx) ** 2 + 4 * lam * sxy ** 2)) / (2 * sxy)
    return float(a), float(ym - a * xm)


def calibrate(df: pd.DataFrame, src: str) -> dict | None:
    """Tek bir büyüklük tipi için (src -> mw) bağıntısını kestirir."""
    xcol, ycol = f"mag_{src}", "mag_mw"
    if xcol not in df.columns or ycol not in df.columns:
        return None
    # KOERI eksik değerleri 0.0 yazar, NaN değil
    m = df[[xcol, ycol]].apply(pd.to_numeric, errors="coerce")
    m = m[(m[xcol] > 0) & (m[ycol] > 0)].dropna()
    if len(m) < MIN_PAIRS:
        print(f"[{src}] yetersiz çift ({len(m)}) — atlandı")
        return None

    x, y = m[xcol].to_numpy(), m[ycol].to_numpy()
    # Kaba eşleşme hatalarını at (ör. farklı olayların büyüklükleri karışmışsa)
    keep = np.abs(y - x) <= MAX_RESIDUAL
    x, y, n_out = x[keep], y[keep], int((~keep).sum())

    a, b = deming(x, y)
    if np.isnan(a):
        return None
    resid = y - (a * x + b)
    rms = float(np.sqrt((resid ** 2).mean()))
    ss_res = float((resid ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else np.nan

    lit = LITERATURE.get(src)
    lit_txt = ""
    if lit:
        # Bağıntının pratikte ne kadar kaydığı, temsili bir büyüklükte ölçülür
        probe = 4.0
        shift = (a * probe + b) - (lit[0] * probe + lit[1])
        lit_txt = (f" | literatür: Mw={lit[0]:.3f}*{src.upper()}{lit[1]:+.3f}"
                   f" -> M{probe:.1f}'te fark {shift:+.2f}")
    print(f"[{src}] n={len(x):5d} (atılan {n_out})  "
          f"Mw = {a:.3f}*{src.upper()} {b:+.3f}  R²={r2:.3f}  RMS={rms:.3f}{lit_txt}")
    return {"slope": a, "intercept": b, "n": int(len(x)), "r2": r2, "rms": rms,
            "n_outliers": n_out}


def main() -> None:
    src_path = RAW / "koeri_catalog.csv"
    if not src_path.exists():
        print(f"! {src_path} yok — önce scripts/02c_download_koeri.py çalıştırın.")
        return
    df = pd.read_csv(src_path, low_memory=False)
    print(f"KOERI kataloğu: {len(df)} olay\n")

    out = {}
    for src in ("ml", "md", "ms", "mb"):
        result = calibrate(df, src)
        if result:
            out[src] = result
    if not out:
        print("Hiçbir bağıntı kalibre edilemedi.")
        return

    dst = PROC / "mw_conversion.json"
    PROC.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps({"source": "KOERI", "relations": out}, indent=2))
    print(f"\n-> {dst}")
    print("merge_catalogs bu dosyayı varsa otomatik kullanır, yoksa literatür "
          "değerlerine döner.")


if __name__ == "__main__":
    main()
