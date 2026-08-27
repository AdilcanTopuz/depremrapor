"""Kanarya 3'ün SAPTAMA TABANI — "kör mü, kanal mı boş?" ayrımı.

BULGU. NPP'de gerçek ölçekleme sızıntısı AUC'yi +0,0003 değiştirdi; alarm yok.
İki okuma mümkündür ve AYIRT EDİLMELİDİR:

    (a) dedektör kör        (b) kanaldan geçen sinyal yok denecek kadar küçük

ÖLÇÜLDÜ: sızıntılı ile temiz girdi arasındaki fark, standartlaştırılmış
ölçekte ortalama 0,0125 sd (en büyük 0,0367). Yani (b) güçlü adaydır.

Bu betik (a)'yı sınar: ölçekleme bozulması KASTEN büyütülür ve dedektörün
hangi büyüklükten itibaren alarm verdiği ölçülür. Bu, kanarya 2'de yapılanın
aynısıdır — dedektörün kapsamı, gerçek sızıntının büyüklüğünden BAĞIMSIZ
olarak belirlenir.

Kullanım:  python scripts/27_kanarya3_taban.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

KAYMALAR = (0.05, 0.15, 0.50, 1.50)   # sd biriminde kasten eklenen kayma
GERCEK_KAYMA = 0.0125                 # ölçülen gerçek sızıntının büyüklüğü


def main() -> None:
    from src.eval.leakage_canary import check_alarm
    from src.models import npp
    from src.models.lgbm import CATALOG_FEATURES

    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib
    k = importlib.import_module("25_npp_kanarya")

    print("KANARYA 3 SAPTAMA TABANI — 'kör mü, kanal mı boş?'")
    print(f"gerçek sızıntının büyüklüğü: {GERCEK_KAYMA:.4f} sd "
          f"(ölçüldü) -> AUC +0,0003, alarm YOK\n")

    t0 = time.time()
    yigin = npp.Yigin(k.TABLO, k.HEDEF, list(CATALOG_FEATURES))
    tr, va = k._bolumler(yigin)
    yigin_temiz = npp.Yigin(k.TABLO, k.HEDEF, list(CATALOG_FEATURES),
                            olcek_satirlari=tr)
    taban = k._auc(yigin_temiz, tr, va)
    print(f"temiz taban AUC {taban:.4f}  ({time.time() - t0:.0f} sn)\n")

    asil = yigin_temiz.statik.copy()
    n_oz = len(CATALOG_FEATURES)
    rng = np.random.default_rng(20260825)
    kayit = {"taban": taban, "gercek_kayma": GERCEK_KAYMA, "olcumler": []}

    print(f"{'kayma (sd)':>11s} {'AUC':>8s} {'fark':>8s} {'alarm':>6s}")
    for k_sd in KAYMALAR:
        # KASITLI bozulma: her özniteliğe rastgele işaretli sabit kayma.
        # Gerçek sızıntının biçimini taklit eder (ortalama kayması), ama
        # büyüklüğü kontrollü.
        yon = rng.choice([-1.0, 1.0], size=n_oz)
        yigin_temiz.statik = asil.copy()
        yigin_temiz.statik[:, :n_oz] += (k_sd * yon).astype(np.float32)
        r = check_alarm(k._auc(yigin_temiz, tr, va),
                        f"kanarya3 kayma {k_sd} sd", raise_on_alarm=False,
                        taban=taban)
        kayit["olcumler"].append({"kayma_sd": k_sd, **r})
        print(f"{k_sd:11.2f} {r['auc']:8.4f} {r['auc'] - taban:+8.4f} "
              f"{'VAR' if r['alarm'] else 'yok':>6s}")
        (PROC / "kanarya3_taban.json").write_text(
            json.dumps(kayit, indent=2, ensure_ascii=False), encoding="utf-8")
    yigin_temiz.statik = asil

    yak = [o["kayma_sd"] for o in kayit["olcumler"] if o["alarm"]]
    kac = [o["kayma_sd"] for o in kayit["olcumler"] if not o["alarm"]]
    print(f"\nYAKALANAN {yak or 'hiçbiri'} · KAÇAN {kac or 'hiçbiri'}")
    if yak:
        print(f"saptama tabanı {max(kac) if kac else 0} ile {min(yak)} sd "
              f"arasında -> gerçek sızıntı ({GERCEK_KAYMA} sd) bunun "
              f"{min(yak) / GERCEK_KAYMA:.0f} kat ALTINDA")
        print("HÜKÜM: dedektör kör DEĞİL; KANAL BOŞ.")
    else:
        # İKİLİ HÜKÜM YETERSİZDİ -- ilk sürüm burada "DEDEKTÖR KÖR" yazıyordu
        # ve bu YANLIŞ çerçevelemeydi (V29). Üçüncü ihtimal ölçüldü:
        # SONDA UYGULANAN BOZULMANIN KENDİSİ BİLGİ TAŞIMIYOR.
        artan = all(kayit["olcumler"][i]["auc"] <= kayit["olcumler"][i + 1]["auc"]
                    for i in range(len(kayit["olcumler"]) - 1))
        print("1,5 sd'lik bozulma bile yakalanmadı.")
        print(f"etki tekdüze artıyor mu: {'EVET' if artan else 'HAYIR'}")
        if not artan:
            print("HÜKÜM: 'dedektör kör' DEĞİL -- etki tekdüze bile değil,")
            print("yani ölçülen şey sinyal değil GÜRÜLTÜ. Sonda uygulanan")
            print("afin kayma, nöral ağın ilk katmanınca SOĞURULUYOR;")
            print("dönüşüm hipotez sınıfını değiştirmiyor. Bu bir dedektör")
            print("kusuru değil, SONDA KUSURUDUR.")
        else:
            print("HÜKÜM: dedektör kör -- etki artıyor ama alarm yok.")
    print(f"\ntoplam {(time.time() - t0) / 60:.1f} dk")


if __name__ == "__main__":
    main()
