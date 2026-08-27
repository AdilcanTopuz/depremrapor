"""Kanarya 2'nin SAPTAMA TABANI — kural 10 korumaya uygulanır.

Zamansal kanarya 7 günlük ileri bakışı yakalıyor (AUC 0,9989, alarm VAR) ama
1 günlüğü kaçırıyor (0,8135, alarm YOK). Eşik "yakalar" diye ilan edilmeden
önce, NEYİ yakaladığı ölçülmelidir.

Eşik AYARLANMAZ. Bu sonuca bakıp ALARM_JUMP düşürülürse ölçüt sonuca göre
seçilmiş olur -- kaçındığımız şey. Ölçülen taban RAPORLANIR; kanaryanın
kapsamı o tabanla sınırlı olarak beyan edilir.

Kullanım:  python scripts/19_kanarya_duyarlilik.py
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TARGET = "target_7d_m45_all"
GUNLER = (1, 2, 3, 5, 7)
DST = ROOT / "data" / "processed" / "kanarya_duyarlilik.json"
TABAN = "doğrulama"   # 2026-08-25'e kadar "test"ti; bkz. TEST_DOKUNUSLARI.md


def main() -> None:
    import src.models.lgbm as L

    L.FEATURE_TABLE = "grid_features_weekly.parquet"
    from src.eval import leakage_canary as C

    temiz = C.temiz_taban(TARGET)
    print(f"temiz taban AUC {temiz:.4f}  (bölüm: {TABAN})")

    g = C.canary_gross(TARGET)
    print(f"KABA kanarya: AUC {g['auc']:.4f}  "
          f"alarm {'VAR' if g['alarm'] else 'yok'}")

    print(f"{'ileri bakış':>12s} {'AUC':>8s} {'fark':>8s} {'alarm':>6s}")

    kayit = {"temiz": temiz, "hedef": TARGET, "bolum": TABAN,
             "kaba": {"auc": g["auc"], "alarm": g["alarm"]},
             "olcumler": []}
    for d in GUNLER:
        t0 = time.time()
        r = C.canary_temporal(TARGET, days_ahead=d)
        fark = r["auc"] - temiz
        print(f"{d:9d} gün {r['auc']:8.4f} {fark:+8.4f} "
              f"{'VAR' if r['alarm'] else 'yok':>6s}  ({time.time()-t0:.0f} sn)")
        kayit["olcumler"].append(
            {"gun": d, "auc": r["auc"], "fark": fark, "alarm": r["alarm"]})
        DST.write_text(json.dumps(kayit, indent=2, ensure_ascii=False),
                       encoding="utf-8")   # parça parça yaz

    yakalanan = [o["gun"] for o in kayit["olcumler"] if o["alarm"]]
    kacan = [o["gun"] for o in kayit["olcumler"] if not o["alarm"]]
    print(f"\nYAKALANAN: {yakalanan or 'hiçbiri'}")
    print(f"KAÇAN    : {kacan or 'hiçbiri'}")
    if yakalanan and kacan:
        print(f"\nSaptama tabanı {max(kacan)} ile {min(yakalanan)} gün arasında.")
        print("Bu tabanın ALTINDAKİ ileri bakış sızıntıları bu kanaryayla")
        print("saptanmaz -- kanaryanın kapsamı budur, kusuru değil.")
    print(f"\n-> {DST}")


if __name__ == "__main__":
    main()
