"""NPP hiperparametre araması — 4 bileşim x 3 tohum (Zeyilname 3).

İLAN: `docs/NPP_ILAN.md` §4-§5, commit `36701dc` (Zeyilname 1 ve 2 ile).

İKİ YAPISAL KORUMA — Faz 3'ün deseni aynen:

1. TEST BÖLÜMÜ BU BETİĞE HİÇ GİRMEZ. Satır indeksleri yalnızca eğitim ve
   doğrulama dönemleri için üretilir; test aralığı bir kez bile
   indekslenmez. Ölçekleme istatistikleri de yalnızca EĞİTİM satırlarından
   (V26).

2. HER KOŞU ANINDA DİSKE YAZILIR (jsonl, append) ve betik kaldığı yerden
   devam eder (NameError vakasının dersi).

SEÇİM: doğrulama Poisson NLL'inin 3 tohum ortalaması, YUVARLAMA YOK (V23),
beraberlikte daha AZ parametreli.

Kullanım:
    python scripts/26_npp_arama.py            # koş / devam et
    python scripts/26_npp_arama.py --rapor    # yalnızca tabloyu bas
    python scripts/26_npp_arama.py --zamanla  # TEK koşu zamanla (ilan şartı)
"""
import itertools
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
SEEDS = (1, 2, 3)
LOG = PROC / "npp_arama.jsonl"

# --- İLAN EDİLEN UZAY (sabit, genişletilmez) -------------------------------
# ZEYİLNAME 3 UYGULANDI (sonuç görülmeden bağlanmış kural):
#   yakınsama ölçütü p = 0,0344 >= 0,02  -> "hâlâ ilerliyor" dalı
#   -> tur 40->80, sabır 8->12, lr ekseni DÜŞER (1e-3'te sabit)
# lr'nin düşme gerekçesi soruya bağlıdır: H2 bir TEMSİL KAPASİTESİ sorusu;
# gizli ve katman kapasiteyi belirler, lr yalnızca ona ulaşma hızını.
SPACE = {"gizli": (32, 64), "katman": (2, 3)}
SABIT = dict(lr=1e-3, tur=80, sabir=12, yigin_boyu=16384, weight_decay=1e-5)
N_BILESIM = 4


def combos() -> list[dict]:
    k = list(SPACE)
    return [dict(zip(k, v)) for v in itertools.product(*SPACE.values())]


def _key(c: dict, s: int) -> str:
    return json.dumps({**c, "seed": s}, sort_keys=True)


def _done() -> set[str]:
    if not LOG.exists():
        return set()
    return {_key(json.loads(l)["params"], json.loads(l)["seed"])
            for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()}


def _kur():
    """Yigin + bölüm indeksleri. Test aralığı HİÇ indekslenmez."""
    from src.models import npp
    from src.models.lgbm import CATALOG_FEATURES

    d = pd.read_parquet(PROC / TABLO, columns=["ref_date"])
    d = pd.to_datetime(d.ref_date, utc=True)
    tr = np.flatnonzero(d < pd.Timestamp("2016-01-01", tz="UTC"))
    va = np.flatnonzero((d >= pd.Timestamp("2016-01-01", tz="UTC"))
                        & (d < pd.Timestamp("2021-01-01", tz="UTC")))
    yigin = npp.Yigin(TABLO, HEDEF, list(CATALOG_FEATURES),
                      olcek_satirlari=tr)
    return yigin, tr, va


def rapor() -> None:
    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(json.dumps(r["params"], sort_keys=True), []).append(r)

    print(f"\nNPP ARAMA — {len(by)}/{N_BILESIM} bileşim, {len(rows)}/{N_BILESIM * 3} koşu")
    print("Seçim: DOĞRULAMA Poisson NLL'inin 3 tohum ortalaması (küçük iyi)")
    print("Test dönemi bu tabloya HİÇ girmemiştir.\n")
    print(f"{'#':>2s} {'gizli':>6s} {'katman':>7s} "
          f"{'ort NLL':>14s} {'ss':>12s} {'n':>2s} {'par':>6s} {'tur':>4s}")

    tab = []
    for k, rs in by.items():
        p = json.loads(k)
        v = np.array([r["val_nll"] for r in rs])
        tab.append((float(v.mean()),
                    float(v.std(ddof=1)) if len(v) > 1 else float("nan"),
                    p, len(rs), int(np.mean([r["n_par"] for r in rs])),
                    float(np.mean([r["en_iyi_tur"] for r in rs]))))
    # YUVARLAMA YOK (V23); beraberlikte daha AZ parametreli
    tab.sort(key=lambda x: (x[0], x[4]))

    for i, (m, s, p, n, par, tur) in enumerate(tab, 1):
        print(f"{i:2d} {p['gizli']:6d} {p['katman']:7d} "
              f"{m:14.8f} {s:12.8f} {n:2d} {par:6d} {tur:4.0f}")

    if len(tab) == N_BILESIM and all(t[3] == 3 for t in tab):
        b = tab[0]
        ort = np.array([t[0] for t in tab])
        sac = np.array([t[1] for t in tab])
        print(f"\nyayılım/saçılım {ort.std(ddof=1) / sac.mean():.2f} · "
              f"genişlik/saçılım {(ort.max() - ort.min()) / sac.mean():.2f}")
        print(f"SEÇİLEN: {b[2]}  ({b[4]} parametre)")
        print(f"  doğrulama NLL {b[0]:.8f} +- {b[1]:.8f}")
        print(f"  en yakın rakip {tab[1][0]:.8f} (fark {tab[1][0] - b[0]:+.8f})")
        ayirt = (tab[1][0] - b[0]) > b[1]
        print(f"  fark tohum saçılımını aşıyor mu: "
              f"{'EVET' if ayirt else 'HAYIR -> seçildi ama AYIRT EDİLEMEDİ'}")
        (PROC / "npp_secim.json").write_text(json.dumps(
            {"params": b[2], "val_nll_mean": b[0], "val_nll_sd": b[1],
             "runner_up_gap": tab[1][0] - b[0], "ayirt_edilebilir": bool(ayirt),
             "yayilim_sacilim": float(ort.std(ddof=1) / sac.mean())},
            indent=2, ensure_ascii=False), encoding="utf-8")
        print("\n-> data/processed/npp_secim.json")
    else:
        print(f"\nARAMA TAMAMLANMADI: {N_BILESIM * 3 - len(rows)} koşu eksik. Seçim YOK.")


def main(zamanla: bool = False) -> None:
    from src.models import npp

    t0 = time.time()
    yigin, tr, va = _kur()
    print(f"eğitim {len(tr):,} · doğrulama {len(va):,} · "
          f"pozitif {int(yigin.y[tr].sum())}/{int(yigin.y[va].sum())}")
    print(f"statik girdi {yigin.statik.shape[1]} sütun "
          f"({len(yigin.eksik_sutunlar)} eksiklik göstergesi dâhil)")
    print(f"ölçekleme kapsamı: {yigin.olcek_kapsami}")
    print(f"dizin künyesi: {yigin.kunye['sha256'][:16]}...  "
          f"({time.time() - t0:.0f} sn kurulum)\n")

    if zamanla:
        c = combos()[0]
        t1 = time.time()
        r = npp.egit(yigin, tr, va, tohum=1, **c, **SABIT, quiet=False)
        dt = time.time() - t1
        print(f"\nTEK KOŞU {dt / 60:.1f} dk ({r['en_iyi_tur']} tur) "
              f"-> {N_BILESIM * 3} koşu ~{dt * N_BILESIM * 3 / 3600:.1f} sa")
        print("İlan şartı: tahmin tutmuyorsa arama uzayı KÜÇÜLTÜLÜR, "
              "süre uydurulmaz.")
        return

    done = _done()
    todo = [(c, s) for c in combos() for s in SEEDS if _key(c, s) not in done]
    print(f"{len(done)} koşu bitmiş, {len(todo)} kaldı.\n")

    for i, (c, s) in enumerate(todo, 1):
        t1 = time.time()
        r = npp.egit(yigin, tr, va, tohum=s, **c, **SABIT)
        rec = {"params": c, "seed": s, "val_nll": r["val_nll"],
               "en_iyi_tur": r["en_iyi_tur"], "n_par": r["n_par"],
               "seconds": round(time.time() - t1, 1)}
        with LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        gecen = time.time() - t0
        print(f"[{i:2d}/{len(todo)}] gizli={c['gizli']} kat={c['katman']} "
              f"t={s} -> NLL {r['val_nll']:.8f} "
              f"({r['en_iyi_tur']} tur, {rec['seconds'] / 60:.1f} dk) | "
              f"kalan ~{gecen / i * (len(todo) - i) / 60:.0f} dk")

    rapor()


if __name__ == "__main__":
    if "--rapor" in sys.argv:
        rapor()
    else:
        main(zamanla="--zamanla" in sys.argv)
