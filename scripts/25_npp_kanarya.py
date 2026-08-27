"""NPP kurulumunda SIZINTI KANARYALARI — ana koşudan ÖNCE.

İLAN: `docs/NPP_ILAN.md` §7. Üç kanarya da NPP kurulumunda koşulur ve
**reddettikleri bir deneyle** gösterilir (kural 9). Kanarya 3 burada İLK KEZ
anlamlıdır: ağaçlarda ölçekleme kanalı yoktu, nöral modelde var.

TABAN VE BÖLÜM. Kanarya 2'nin saptama tabanı BÖLÜME BAĞLIYDI (test 3-5 gün,
doğrulama 2-3 gün). NPP kurulumunda taban DOĞRULAMA bölümünde ölçülür ve
künyeye hangi bölüm olduğu yazılır. Test bölümü kanaryalarda KULLANILMAZ
(`docs/TEST_DOKUNUSLARI.md`, Düzeltme 1).

Ölçüt (İLAN EDİLMİŞ, değiştirilmedi): mutlak AUC > 0,90 · sıçrama > taban+0,10

Kullanım:  python scripts/25_npp_kanarya.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

TABLO = "grid_features_weekly.parquet"
HEDEF = "target_7d_m45_all"
BOLUM_OLCUM = "doğrulama"          # kanarya AUC'si bu bölümde ölçülür
TUR = 6                            # kanarya için kısa eğitim (tanılama)
ILERI_GUNLER = (1, 2, 3, 5, 7)


def _bolumler(yigin) -> tuple[np.ndarray, np.ndarray]:
    d = pd.to_datetime(yigin.ref_date, utc=True)
    tr = np.flatnonzero(d < pd.Timestamp("2016-01-01", tz="UTC"))
    va = np.flatnonzero((d >= pd.Timestamp("2016-01-01", tz="UTC"))
                        & (d < pd.Timestamp("2021-01-01", tz="UTC")))
    return tr, va


def _auc(yigin, tr, va, ek: np.ndarray | None = None, tohum: int = 0) -> float:
    """Kısa bir NPP eğitir ve DOĞRULAMA AUC'sini döndürür."""
    import torch
    from sklearn.metrics import roc_auc_score

    from src.models import npp

    if ek is not None:
        asil = yigin.statik
        z = (ek - ek[tr].mean()) / max(ek[tr].std(), 1e-6)
        yigin.statik = np.concatenate(
            [asil, z.astype(np.float32)[:, None]], axis=1)
    try:
        r = npp.egit(yigin, tr, va, tohum=tohum, gizli=32, katman=2,
                     tur=TUR, sabir=TUR)
        m = r["model"]
        m.eval()
        p = []
        with torch.no_grad():
            for b in range(0, len(va), 16384):
                st, ol, mk, _ = yigin(va[b:b + 16384])
                p.append(m(st, ol, mk).numpy())
        return float(roc_auc_score(yigin.y[va].astype(int),
                                   np.concatenate(p)))
    finally:
        if ek is not None:
            yigin.statik = asil


def main() -> None:
    from src.eval.leakage_canary import ALARM_AUC, ALARM_JUMP, check_alarm
    from src.ingest.catalog_io import epoch_seconds
    from src.models import npp
    from src.models.lgbm import CATALOG_FEATURES

    ozn = list(CATALOG_FEATURES)
    print(f"NPP KANARYA SETİ — ölçüm bölümü: {BOLUM_OLCUM}")
    print(f"eşikler (İLAN EDİLMİŞ): mutlak {ALARM_AUC} · "
          f"sıçrama taban+{ALARM_JUMP}\n")

    t0 = time.time()
    yigin = npp.Yigin(TABLO, HEDEF, ozn)
    tr, va = _bolumler(yigin)
    yigin_temiz = npp.Yigin(TABLO, HEDEF, ozn, olcek_satirlari=tr)
    print(f"eğitim {len(tr):,} · doğrulama {len(va):,} · "
          f"pozitif {int(yigin.y[tr].sum())}/{int(yigin.y[va].sum())}")
    print(f"ölçekleme kapsamı: temiz='{yigin_temiz.olcek_kapsami}' · "
          f"sızıntılı='{yigin.olcek_kapsami}'  ({time.time() - t0:.0f} sn)\n")

    kayit = {"bolum": BOLUM_OLCUM, "tur": TUR, "kunye": yigin.kunye["sha256"]}

    taban = _auc(yigin_temiz, tr, va)
    kayit["temiz_taban"] = taban
    print(f"TEMİZ TABAN  AUC {taban:.4f}\n")

    # --- KANARYA 1: KABA -------------------------------------------------
    g = check_alarm(_auc(yigin_temiz, tr, va, ek=yigin.y.copy()),
                    "NPP kaba", raise_on_alarm=False, taban=taban)
    kayit["kaba"] = g
    print(f"1) KABA      AUC {g['auc']:.4f}  "
          f"alarm {'VAR' if g['alarm'] else 'YOK'}")

    # --- KANARYA 2: ZAMANSAL, saptama tabanı ------------------------------
    print("\n2) ZAMANSAL — saptama tabanı")
    from src.config import cell_id as _cid
    from src.ingest.catalog_io import read_catalog

    cat = read_catalog(PROC / "catalog_declustered.csv")
    cat = cat.dropna(subset=["lat", "lon", "mw"]).sort_values("time")
    cat["cell_id"] = _cid(cat.lat, cat.lon)
    ct = epoch_seconds(cat["time"])
    ccid = cat.cell_id.to_numpy()

    kayit["zamansal"] = []
    for d in ILERI_GUNLER:
        ek = np.zeros(len(yigin.y))
        for cid in np.unique(yigin.cell_id):
            m = yigin.cell_id == cid
            tt = np.sort(ct[ccid == cid])
            if not len(tt):
                continue
            r = yigin.ref_s[m]
            ek[m] = (np.searchsorted(tt, r + d * 86400.0, "left")
                     - np.searchsorted(tt, r, "left"))
        z = check_alarm(_auc(yigin_temiz, tr, va, ek=ek),
                        f"NPP zamansal ref+{d}g", raise_on_alarm=False,
                        taban=taban)
        kayit["zamansal"].append({"gun": d, **z})
        print(f"   ref+{d}g  AUC {z['auc']:.4f}  fark {z['auc'] - taban:+.4f}  "
              f"alarm {'VAR' if z['alarm'] else 'yok'}")

    yak = [x["gun"] for x in kayit["zamansal"] if x["alarm"]]
    kac = [x["gun"] for x in kayit["zamansal"] if not x["alarm"]]
    print(f"   YAKALANAN {yak or 'hiçbiri'} · KAÇAN {kac or 'hiçbiri'}")
    if yak and kac:
        print(f"   saptama tabanı {max(kac)} ile {min(yak)} gün arasında "
              f"({BOLUM_OLCUM} bölümünde)")

    # --- KANARYA 3: DOLAYLI — İLK KEZ ANLAMLI ----------------------------
    print("\n3) DOLAYLI (ölçekleme) — nöral modelde İLK KEZ anlamlı")
    sizintili = _auc(yigin, tr, va)      # olcek_satirlari=None -> tüm tablo
    kayit["dolayli"] = {"temiz": taban, "sizintili": sizintili,
                        "fark": sizintili - taban}
    print(f"   temiz {taban:.4f} | sızıntılı {sizintili:.4f} | "
          f"fark {sizintili - taban:+.4f}")
    print("   (ağaçlarda bu fark -0,0000 idi: kanal yoktu)")

    dst = PROC / "npp_kanarya.json"
    dst.write_text(json.dumps(kayit, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\ntoplam {(time.time() - t0) / 60:.1f} dk -> {dst}")


if __name__ == "__main__":
    main()
