"""ZEMİN KARŞILAŞTIRMASI — dondurulmuş tablo yeniden üretilebiliyor mu?

İLAN: `docs/ZEMIN_YENIDEN_URETIM.md` (koşudan önce yazıldı). İki dal bağlı:

    DAL A  örtüşürse -> V37 "yeniden üretim doğrulandı" ile kapanır,
                        manşet YERİNDE kalır
    DAL B  farklıysa -> manşet yeniden ölçülür, mühür "sayı değişikliği,
                        sebep: zemin yeniden üretildi" ile tazelenir;
                        Ö5/H1/H2/ürün kapısı TEK TEK yeniden ölçülür

TOPLAM ÖRTÜŞMESİ YETMEZ. Toplamda birbirini götüren farklar olabilir; bu
yüzden karşılaştırma HÜCRE DÜZEYİNDE yapılır ve üç eksende ölçülür:

    1. hücre bazlı oran dağılımı (medyan, %5, %95, en büyük sapma)
    2. başlangıç bazlı toplam farkı
    3. DONDURULMUŞ MANŞET SAYILARININ yeniden hesabı (AUC, IG, kalibrasyon)

Üçüncüsü asıl ölçüttür: sayılar aynıysa zemin yeniden üretilmiştir.

Kullanım:  python scripts/30_zemin_karsilastirma.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

ESKI = "etas_analytic_weekly"
YENI = "etas_analytic_weekly_v2"

# DONDURULMUŞ MANŞET SAYILARI — karşılaştırma hedefleri
DONMUS = {"auc_etas": 0.7909, "auc_poisson": 0.6503, "ig_etas": 1.068,
          "kalibrasyon_etas": 1.09, "auc_farki": 0.1407}
TOLERANS = 0.001          # 3 ondalık: manşet bu hassasiyette yazılmış


def _yukle(ad: str) -> pd.DataFrame:
    from src.eval import daily_backtest as db
    db.FORECAST_DIR = ad
    fc = db.load_forecast()
    fc["ref_date"] = pd.to_datetime(fc.ref_date, utc=True)
    return fc[(fc.window_days == 7) & (fc.target_mw == 4.5)]


def _manset(ad: str) -> dict:
    """Dondurulmuş manşet sayılarını bu tablodan yeniden hesaplar."""
    from sklearn.metrics import roc_auc_score
    from src.eval import daily_backtest as db

    db.FORECAST_DIR = ad
    t = db.build_table(7, 4.5, quiet=True)
    y = t.y.to_numpy()
    n = int(y.sum())
    a = np.maximum(t.rate_pois.to_numpy(), 1e-12)
    b = np.maximum(t.rate_etas.to_numpy(), 1e-12)
    m = y.astype(bool)
    ig = float((np.log(b[m]) - np.log(a[m])).sum() / n - (b.sum() - a.sum()) / n)
    auc_e = float(roc_auc_score(y, t.p_etas))
    auc_p = float(roc_auc_score(y, t.p_pois))
    return {"n_satir": len(t), "n_olay": n, "auc_etas": auc_e,
            "auc_poisson": auc_p, "auc_farki": auc_e - auc_p, "ig_etas": ig,
            "kalibrasyon_etas": float(n / t.rate_etas.sum())}


def main() -> None:
    print("=== 1. HÜCRE DÜZEYİ ===")
    e, y = _yukle(ESKI), _yukle(YENI)
    print(f"  eski {len(e):,} satır · yeni {len(y):,} satır")
    oe = set(e.ref_date.unique())
    oy = set(y.ref_date.unique())
    print(f"  başlangıç: eski {len(oe)} · yeni {len(oy)} · "
          f"kümeler eşit {oe == oy}")
    if oe != oy:
        print(f"  yalnız eskide {len(oe - oy)} · yalnız yenide {len(oy - oe)}")

    m = e.merge(y, on=["cell_id", "ref_date"], suffixes=("_e", "_y"))
    print(f"  kesişim {len(m):,} hücre-başlangıç")
    r = m.rate_etas_y / m.rate_etas_e.replace(0, np.nan)
    print(f"  oran (yeni/eski): medyan {r.median():.6f} · "
          f"%5 {r.quantile(.05):.6f} · %95 {r.quantile(.95):.6f}")
    sap = float(np.abs(r - 1).max())
    print(f"  en büyük sapma: {sap:.3e}")
    birebir = bool(np.allclose(m.rate_etas_e, m.rate_etas_y, rtol=1e-9,
                               atol=0.0))
    print(f"  BİREBİR (rtol 1e-9): {'EVET' if birebir else 'HAYIR'}")

    print("\n=== 2. BAŞLANGIÇ DÜZEYİ ===")
    g = m.groupby("ref_date")[["rate_etas_e", "rate_etas_y"]].sum()
    gr = g.rate_etas_y / g.rate_etas_e
    print(f"  başlangıç toplam oranı: medyan {gr.median():.6f} · "
          f"en küçük {gr.min():.6f} · en büyük {gr.max():.6f}")

    print("\n=== 3. DONDURULMUŞ MANŞET SAYILARI — asıl ölçüt ===")
    me, my = _manset(ESKI), _manset(YENI)
    print(f"  {'sayı':18s} {'donmuş':>9s} {'eski tablo':>11s} "
          f"{'yeni tablo':>11s} {'fark':>10s}")
    sapan = []
    for k, hedef in DONMUS.items():
        fark = my[k] - hedef
        print(f"  {k:18s} {hedef:9.4f} {me[k]:11.4f} {my[k]:11.4f} "
              f"{fark:+10.5f}")
        if abs(fark) > TOLERANS:
            sapan.append((k, hedef, my[k], fark))
    print(f"  satır/olay: eski {me['n_satir']:,}/{me['n_olay']} · "
          f"yeni {my['n_satir']:,}/{my['n_olay']}")

    print("\n=== HÜKÜM ===")
    if birebir and not sapan:
        print("  DAL A — ZEMİN YENİDEN ÜRETİLDİ (birebir).")
        print("  V37 'yeniden üretim doğrulandı' ile kapanır; manşet yerinde.")
        dal = "A-birebir"
    elif not sapan:
        print(f"  DAL A — manşet sayıları {TOLERANS} toleransında ÖRTÜŞÜYOR")
        print(f"  (hücre düzeyinde en büyük sapma {sap:.3e}).")
        print("  V37 kapanır; manşet yerinde. Sapmanın kaynağı kayda geçer.")
        dal = "A-toleransta"
    else:
        print("  DAL B — MANŞET SAYILARI DEĞİŞTİ:")
        for k, h, v, f in sapan:
            print(f"    {k}: {h} -> {v:.4f} ({f:+.5f})")
        print("  Mühür tazelenir: 'sayı değişikliği, sebep: zemin yeniden")
        print("  üretildi'. Ö5/H1/H2/ürün kapısı TEK TEK yeniden ölçülür.")
        dal = "B"

    (PROC / "zemin_karsilastirma.json").write_text(json.dumps(
        {"dal": dal, "birebir": birebir, "en_buyuk_sapma": sap,
         "manset_eski": me, "manset_yeni": my, "donmus": DONMUS,
         "sapan": [{"sayi": k, "donmus": h, "yeni": v, "fark": f}
                   for k, h, v, f in sapan]},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {PROC / 'zemin_karsilastirma.json'}")


if __name__ == "__main__":
    main()
