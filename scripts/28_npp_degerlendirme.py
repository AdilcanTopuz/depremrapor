"""NPP TEST DEĞERLENDİRMESİ — bir kez, ilan edilen protokolle.

ÖNKOŞUL: `data/processed/npp_secim.json` (12/12 koşu bitmeden yazılmaz).

İKİ AŞAMA — ikincisi birincisine BAĞLIDIR:

  AŞAMA 1  seçilen bileşim, arama koşusuyla BİREBİR aynı protokolle yeniden
           eğitilir. Doğrulama NLL'leri `npp_arama.jsonl` ile BİREBİR
           tutmalıdır. TUTMAZSA BETİK DURUR ve test setine DOKUNULMAZ.

           Bu, determinizm protokolünün (docs/NPP_ILAN.md §6) uçtan uca
           kanıtıdır: şimdiye kadar aynı süreç içinde iki eğitimin eşitliği
           gösterilmişti; burada AYRI SÜREÇ, AYRI GÜN, AYRI ÇAĞRI ile
           gösterilir.

  AŞAMA 2  test dönemi BİR KEZ değerlendirilir.
           H1 · H2 · Ö5 · ürün kapısı — hepsi önceden ilan edilmiş.

Modeller kaydedilir (künyeleriyle): gelecekteki analizler yeniden eğitim
maliyeti ödemez.

Kullanım:  python scripts/28_npp_degerlendirme.py
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
SEEDS = (1, 2, 3)
SABIT = dict(lr=1e-3, tur=80, sabir=12, yigin_boyu=16384, weight_decay=1e-5)

ESDEGERLIK_BANDI = 0.515          # Ö5 — Faz 3 ile AYNI
URUN_KAPISI = (0.80, 1.25)        # site şartnamesi
KAHRAMANMARAS = pd.Timestamp("2023-02-06", tz="UTC")
DIZI_GUN = 90
ML_DIZI_BEKLENTI = 19.8           # Faz 3 referansı
ETAS_DIZI_BEKLENTI = 84.3


def _ig(y, ra, rb) -> float:
    n = int(y.sum())
    a = np.maximum(ra, 1e-12)
    b = np.maximum(rb, 1e-12)
    m = y.astype(bool)
    return float((np.log(b[m]) - np.log(a[m])).sum() / n
                 - (b.sum() - a.sum()) / n)


def main() -> None:
    import torch

    from src.models import npp
    from src.models.lgbm import CATALOG_FEATURES

    sec_path = PROC / "npp_secim.json"
    if not sec_path.exists():
        raise SystemExit("! npp_secim.json yok — arama tamamlanmadan seçim yok.")
    sec = json.loads(sec_path.read_text(encoding="utf-8"))
    par = sec["params"]
    print("SEÇİLEN BİLEŞİM (doğrulamayla, test görülmeden):")
    print(f"  {par}  ·  doğrulama NLL {sec['val_nll_mean']:.8f} "
          f"+- {sec['val_nll_sd']:.8f}")
    print(f"  en yakın rakiple fark {sec['runner_up_gap']:+.8f} · "
          f"ayırt edilebilir: {sec['ayirt_edilebilir']}")
    print(f"  yayılım/saçılım {sec['yayilim_sacilim']:.2f}\n")

    # arama koşusundaki değerler — BİREBİR tutmalı
    bekl = {}
    for line in (PROC / "npp_arama.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r["params"] == par:
            bekl[r["seed"]] = (r["val_nll"], r["en_iyi_tur"])
    print(f"aramadaki değerler: " + " · ".join(
        f"t{s}={v[0]:.8f}({v[1]} tur)" for s, v in sorted(bekl.items())))

    t0 = time.time()
    d = pd.read_parquet(PROC / TABLO, columns=["ref_date"])
    d = pd.to_datetime(d.ref_date, utc=True)
    tr = np.flatnonzero(d < pd.Timestamp("2016-01-01", tz="UTC"))
    va = np.flatnonzero((d >= pd.Timestamp("2016-01-01", tz="UTC"))
                        & (d < pd.Timestamp("2021-01-01", tz="UTC")))
    te = np.flatnonzero(d >= pd.Timestamp("2021-01-01", tz="UTC"))
    yigin = npp.Yigin(TABLO, HEDEF, list(CATALOG_FEATURES),
                      olcek_satirlari=tr)
    print(f"kurulum {time.time() - t0:.0f} sn · dizin "
          f"{yigin.kunye['sha256'][:16]}...\n")

    # === AŞAMA 1: DETERMİNİZM ZİNCİRİ ===================================
    print("=== AŞAMA 1 — determinizm zinciri (ayrı süreç, ayrı gün) ===")
    modeller, sapma = {}, []
    for s in SEEDS:
        t1 = time.time()
        r = npp.egit(yigin, tr, va, tohum=s, **par, **SABIT)
        b_nll, b_tur = bekl[s]
        ayni = (r["val_nll"] == b_nll) and (r["en_iyi_tur"] == b_tur)
        print(f"  tohum {s}: {r['val_nll']:.8f} ({r['en_iyi_tur']} tur, "
              f"{(time.time() - t1) / 60:.1f} dk)  "
              f"aramadaki ile BİREBİR: {'EVET' if ayni else 'HAYIR'}")
        if not ayni:
            sapma.append((s, b_nll, r["val_nll"], b_tur, r["en_iyi_tur"]))
        modeller[s] = r["model"]

    if sapma:
        print("\n! DETERMİNİZM ZİNCİRİ KIRILDI — TEST SETİNE DOKUNULMUYOR.")
        for s, a, b, ta, tb in sapma:
            print(f"  tohum {s}: aramada {a:.10f} ({ta} tur) · "
                  f"şimdi {b:.10f} ({tb} tur) · fark {b - a:+.3e}")
        raise SystemExit("Ön şart karşılanmadı (docs/TEST_DOKUNUSLARI.md, "
                         "Dokunuş 3). Fark açıklanmadan değerlendirme yok.")
    print("  -> ZİNCİR SAĞLAM. Test değerlendirmesine geçiliyor.\n")

    for s, m in modeller.items():
        torch.save(m.state_dict(), PROC / f"npp_secilen_t{s}.pt")
    print(f"modeller kaydedildi: npp_secilen_t{{1,2,3}}.pt\n")

    # === AŞAMA 2: TEST — BİR KEZ ========================================
    print("=== AŞAMA 2 — TEST DÖNEMİ, TEK DEĞERLENDİRME ===")
    lam_all = []
    for s in SEEDS:
        m = modeller[s]
        m.eval()
        p = []
        with torch.no_grad():
            for b in range(0, len(te), 16384):
                st, ol, mk, _ = yigin(te[b:b + 16384])
                p.append(m(st, ol, mk).numpy())
        lam_all.append(np.concatenate(p))
    lam = np.mean(lam_all, axis=0)

    npp_df = pd.DataFrame({
        "cell_id": yigin.cell_id[te],
        "ref_date": pd.to_datetime(yigin.ref_date, utc=True)[te],
        "y_npp": yigin.y[te].astype(int), "rate_npp": lam})
    for i, s in enumerate(SEEDS):
        npp_df[f"rate_npp_t{s}"] = lam_all[i]

    from src.eval import daily_backtest as db
    db.FORECAST_DIR = "etas_analytic_weekly"
    tgt = db.build_table(7, 4.5, quiet=True)
    tgt["ref_date"] = pd.to_datetime(tgt.ref_date, utc=True)
    tgt = tgt[tgt.ref_date >= npp_df.ref_date.min()]

    k_np = set(map(tuple, npp_df[["cell_id", "ref_date"]].to_numpy()))
    k_et = set(map(tuple, tgt[["cell_id", "ref_date"]].to_numpy()))
    print(f"  küme eşitliği: NPP {len(k_np):,} · ETAS {len(k_et):,} · "
          f"kesişim {len(k_np & k_et):,} · eşit {k_np == k_et}")
    j = tgt.merge(npp_df, on=["cell_id", "ref_date"], how="inner")
    assert (j.y.to_numpy() == j.y_npp.to_numpy()).all(), "etiketler ayrışıyor"
    y = j.y.to_numpy()
    print(f"  {len(j):,} satır, {int(y.sum())} olay\n")

    from sklearn.metrics import roc_auc_score
    from src.eval.gain_breakdown import _ig_ci

    p_npp = 1 - np.exp(-j.rate_npp.to_numpy())
    auc = {"poisson": roc_auc_score(y, j.p_pois), "etas": roc_auc_score(y, j.p_etas),
           "npp": roc_auc_score(y, p_npp)}
    print(f"  AUC  Poisson {auc['poisson']:.4f} | ETAS {auc['etas']:.4f} | "
          f"NPP {auc['npp']:.4f}")
    sac = [roc_auc_score(y, 1 - np.exp(-j[f"rate_npp_t{s}"])) for s in SEEDS]
    print(f"  NPP AUC tohum saçılımı: " + " ".join(f"{a:.4f}" for a in sac))

    ig_et = _ig(y, j.rate_pois.to_numpy(), j.rate_etas.to_numpy())
    ig_np = _ig(y, j.rate_pois.to_numpy(), j.rate_npp.to_numpy())
    print(f"\n  IG (Poisson'a karşı)  ETAS {ig_et:+.3f} | NPP {ig_np:+.3f}")

    kiyas = j.assign(rate_pois=j.rate_etas, rate_etas=j.rate_npp)
    ig, lo, hi, mde, basis = _ig_ci(kiyas)
    print(f"  NPP - ETAS: {ig:+.3f} nat/olay [{lo:+.3f}, {hi:+.3f}] MDE {mde:.3f}")

    # --- KALİBRASYON + ÜRÜN KAPISI ---
    print("\n  --- KALİBRASYON ---")
    kal = {}
    for ad, c in (("Poisson", "rate_pois"), ("ETAS", "rate_etas"),
                  ("NPP", "rate_npp")):
        bek = float(j[c].sum())
        kal[ad] = y.sum() / bek
        print(f"    {ad:8s} beklenen {bek:7.1f} · gözlenen {y.sum():4.0f} · "
              f"oran {kal[ad]:5.2f}")
    kapi = URUN_KAPISI[0] <= kal["NPP"] <= URUN_KAPISI[1]
    print(f"  ÜRÜN KAPISI [{URUN_KAPISI[0]}; {URUN_KAPISI[1]}]: "
          f"{'GEÇTİ' if kapi else 'GEÇMEDİ'}")

    # --- H2: dizi penceresi beklentisi ---
    ic = ((j.ref_date >= KAHRAMANMARAS)
          & (j.ref_date < KAHRAMANMARAS + pd.Timedelta(days=DIZI_GUN)))
    h2_npp = float(j[ic].rate_npp.sum())
    h2_etas = float(j[ic].rate_etas.sum())
    h2_obs = int(j[ic].y.sum())
    print(f"\n  --- H2: dizi penceresi ({DIZI_GUN} gün) ---")
    print(f"    beklenen  NPP {h2_npp:5.1f} | ETAS {h2_etas:5.1f} | "
          f"gözlenen {h2_obs}")
    print(f"    Faz 3 referansları: ML {ML_DIZI_BEKLENTI} · "
          f"ETAS {ETAS_DIZI_BEKLENTI}")
    h2 = (h2_npp > ML_DIZI_BEKLENTI * 1.5) and kapi
    print(f"    H2 {'GEÇTİ' if h2 else 'KALDI'}  "
          f"(beklenti 19,8'i belirgin aşıyor VE kalibrasyon bandda)")

    # --- H1: ölçek düzeltilmiş dizi-dışı ---
    c = j.rate_etas.sum() / j.rate_npp.sum()
    j["rate_npp_olcekli"] = j.rate_npp * c
    d1 = j[~ic].assign(rate_pois=j[~ic].rate_etas,
                       rate_etas=j[~ic].rate_npp_olcekli)
    i1, l1, h1_, m1, _ = _ig_ci(d1)
    print(f"\n  --- H1: ölçek düzeltilmiş dizi-dışı (ölçek çarpanı {c:.3f}) ---")
    print(f"    NPP - ETAS  {i1:+.3f} [{l1:+.3f}, {h1_:+.3f}]  MDE {m1:.3f}")
    print(f"    Faz 3 (LightGBM, KEŞFEDİCİ): +0,285 [+0,110; +0,452]")

    # --- Ö5 + README 3.5 ---
    ustun, zayif = lo > 0, hi < 0
    icinde = (lo > -ESDEGERLIK_BANDI) and (hi < ESDEGERLIK_BANDI)
    hukum = ("NPP ETAS'I GEÇTİ" if ustun else
             "NPP ETAS'IN ALTINDA" if zayif else
             "EŞDEĞER" if icinde else f"HÜKÜM YOK (MDE {mde:.3f})")
    print(f"\n  --- Ö5 (band +-{ESDEGERLIK_BANDI}) --- {hukum}")
    print(f"  README 3.5 karşılandı mı: {'EVET' if ustun else 'HAYIR'}")

    out = {"params": par, "n_satir": len(j), "n_olay": int(y.sum()),
           "kume_esit": bool(k_np == k_et),
           "auc": auc, "auc_tohum": sac,
           "ig_vs_poisson": {"etas": ig_et, "npp": ig_np},
           "npp_eksi_etas": {"ig": ig, "lo": lo, "hi": hi, "mde": mde,
                             "dayanak": basis},
           "kalibrasyon": kal, "urun_kapisi_gecti": bool(kapi),
           "H2": {"npp": h2_npp, "etas": h2_etas, "gozlenen": h2_obs,
                  "gecti": bool(h2)},
           "H1": {"ig": i1, "lo": l1, "hi": h1_, "mde": m1, "olcek": float(c)},
           "hukum": hukum, "readme_3_5_gecti": bool(ustun)}
    (PROC / "npp_test_sonucu.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    j.to_parquet(PROC / "npp_etas_birlesik.parquet", index=False)
    print(f"\n-> {PROC / 'npp_test_sonucu.json'}")
    print(f"-> {PROC / 'npp_etas_birlesik.parquet'}")
    print(f"\ntoplam {(time.time() - t0) / 60:.1f} dk")


if __name__ == "__main__":
    main()
