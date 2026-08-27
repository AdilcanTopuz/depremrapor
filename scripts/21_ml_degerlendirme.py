"""Seçilen ML modelinin TEST DEĞERLENDİRMESİ — bir kez, ilan edilen protokolle.

ÖNKOŞUL: `data/processed/hp_secim.json` (36 bileşimin tamamı bitmeden yazılmaz).

BU BETİK TEST SETİNE DOKUNUR. docs/TEST_DOKUNUSLARI.md'ye Dokunuş 2 olarak
yazılır ve bu, seçim sonrası TEK dokunuştur. Sonuç ne çıkarsa raporlanır;
yeniden seçim yapılmaz (ilan: docs/FAZ3_PLAN.md, commit a49f84e).

KÜME EŞİTLİĞİ. ML ile ETAS aynı satırlarda karşılaştırılmalıdır. Sayı eşitliği
YETMEZ (V19): iki tabloda da 252 pozitif olması, AYNI 252 pozitif olduğunu
göstermez. Bu betik (cell_id, ref_date) kümelerini KESİŞTİRİR ve her iki
yöndeki farkı SAYIYLA raporlar; fark varsa değerlendirme kesişim üzerinde
yapılır ve kapsam beyanına yazılır.

Kullanım:  python scripts/21_ml_degerlendirme.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

TARGET = "target_7d_m45_all"
TABLE = "grid_features_weekly.parquet"
SEEDS = (1, 2, 3)
ESDEGERLIK_BANDI = 0.515      # nat/olay — İLAN EDİLMİŞ (Ö5), değiştirilmedi


def _ig(y, rate_a, rate_b) -> float:
    """IG = (1/N)*sum_olay[ln(b/a)] - (sum b - sum a)/N   — nat/olay."""
    n = int(y.sum())
    a = np.maximum(rate_a, 1e-12)
    b = np.maximum(rate_b, 1e-12)
    m = y.astype(bool)
    return float((np.log(b[m]) - np.log(a[m])).sum() / n
                 - (b.sum() - a.sum()) / n)


def main() -> None:
    sec_path = PROC / "hp_secim.json"
    if not sec_path.exists():
        raise SystemExit("! hp_secim.json yok — arama tamamlanmadan seçim "
                         "yapılamaz. Önce scripts/20_hiperparametre_arama.py")
    sec = json.loads(sec_path.read_text(encoding="utf-8"))
    print("SEÇİLEN BİLEŞİM (doğrulama dönemiyle, test görülmeden):")
    print(f"  {sec['params']}")
    print(f"  doğrulama logloss {sec['val_logloss_mean']:.6f} "
          f"+- {sec['val_logloss_sd']:.6f}")
    print(f"  en yakın rakiple fark {sec['runner_up_gap']:+.6f}")

    import lightgbm as lgb

    import src.models.lgbm as L
    L.FEATURE_TABLE = TABLE
    from src.models.lgbm import CATALOG_FEATURES, load_dataset

    data = load_dataset(TARGET)
    feats = list(CATALOG_FEATURES)
    tr, va, te = data["train"], data["val"], data["test"]

    FIXED = dict(objective="binary", metric="binary_logloss",
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
                 verbosity=-1, num_threads=4)
    d_tr = lgb.Dataset(tr[feats], tr[TARGET].astype(int))
    d_va = lgb.Dataset(va[feats], va[TARGET].astype(int))

    print("\nSeçilen bileşim 3 tohumla yeniden eğitiliyor:")
    preds, models = [], []
    for s in SEEDS:
        m = lgb.train({**FIXED, **sec["params"], "seed": s}, d_tr,
                      num_boost_round=3000, valid_sets=[d_va],
                      valid_names=["val"],
                      callbacks=[lgb.early_stopping(150, verbose=False),
                                 lgb.log_evaluation(0)])
        preds.append(m.predict(te[feats], num_iteration=m.best_iteration))
        models.append(m)
        print(f"  tohum {s}: {m.best_iteration} yineleme, doğrulama logloss "
              f"{m.best_score['val']['binary_logloss']:.6f}")

    p_ml = np.mean(preds, axis=0)
    ml = pd.DataFrame({"cell_id": te.cell_id.to_numpy(),
                       "ref_date": pd.to_datetime(te.ref_date, utc=True),
                       "y_ml": te[TARGET].astype(int).to_numpy(),
                       "p_ml": p_ml})
    for i, s in enumerate(SEEDS):
        ml[f"p_ml_t{s}"] = preds[i]

    # --- ETAS tablosu, AYNI kurulum ---------------------------------------
    from src.eval import daily_backtest as db
    db.FORECAST_DIR = "etas_analytic_weekly"
    tgt = db.build_table(7, 4.5, quiet=True)
    tgt["ref_date"] = pd.to_datetime(tgt.ref_date, utc=True)
    tgt = tgt[tgt.ref_date >= ml.ref_date.min()]

    # --- KÜME EŞİTLİĞİ (sayı değil, KÜME) ---------------------------------
    k_ml = set(map(tuple, ml[["cell_id", "ref_date"]].to_numpy()))
    k_et = set(map(tuple, tgt[["cell_id", "ref_date"]].to_numpy()))
    print("\n--- KÜME EŞİTLİĞİ ---")
    print(f"  ML satır      {len(k_ml):,}   pozitif {int(ml.y_ml.sum())}")
    print(f"  ETAS satır    {len(k_et):,}   pozitif {int(tgt.y.sum())}")
    print(f"  yalnızca ML'de   {len(k_ml - k_et):,}")
    print(f"  yalnızca ETAS'ta {len(k_et - k_ml):,}")
    print(f"  KÜMELER EŞİT Mİ: {'EVET' if k_ml == k_et else 'HAYIR'}")

    j = tgt.merge(ml, on=["cell_id", "ref_date"], how="inner")
    assert (j.y.to_numpy() == j.y_ml.to_numpy()).all(), \
        "aynı satırda hedef etiketleri ayrışıyor — birleştirme hatalı"
    print(f"  kesişim {len(j):,} satır, {int(j.y.sum())} pozitif")

    # ML olasılığı -> oran (aynı pencere), IG için
    j["rate_ml"] = -np.log1p(-np.clip(j.p_ml, 0, 1 - 1e-12))

    y = j.y.to_numpy()

    from sklearn.metrics import roc_auc_score
    print("\n--- SONUÇ (test dönemi, TEK değerlendirme) ---")
    auc_ml = roc_auc_score(y, j.p_ml.to_numpy())
    auc_et = roc_auc_score(y, j.p_etas.to_numpy())
    auc_po = roc_auc_score(y, j.p_pois.to_numpy())
    print(f"  AUC   Poisson {auc_po:.4f} | ETAS {auc_et:.4f} | ML {auc_ml:.4f}")
    sac = " ".join(f"{roc_auc_score(y, j['p_ml_t%d' % s]):.4f}" for s in SEEDS)
    print(f"  ML AUC tohum saçılımı: {sac}")

    ig_et = _ig(y, j.rate_pois.to_numpy(), j.rate_etas.to_numpy())
    ig_ml = _ig(y, j.rate_pois.to_numpy(), j.rate_ml.to_numpy())
    print(f"\n  IG (Poisson'a karşı, nat/olay)  ETAS {ig_et:+.3f} | "
          f"ML {ig_ml:+.3f}")

    # ML - ETAS aralığı, ETAS - Poisson ile AYNI kod yolundan geçer.
    # `_ig_ci` sütun adlarına bağlıdır (rate_pois = taban, rate_etas = aday);
    # ayrı bir kestirici yazmak yerine sütunlar yeniden adlandırılır. Ayrı
    # kestirici, iki ölçütü sessizce ayrıştırma riski taşırdı -- rapordaki
    # "ETAS-Poisson" ile "ML-ETAS" aralıkları aynı tanımdan gelmeli.
    from src.eval.gain_breakdown import _ig_ci
    kiyas = j.assign(rate_pois=j.rate_etas, rate_etas=j.rate_ml)
    ig, lo, hi, mde, basis = _ig_ci(kiyas)
    print(f"\n  ML - ETAS: {ig:+.3f} nat/olay  [{lo:+.3f}, {hi:+.3f}]")
    print(f"  MDE {mde:.3f} ({basis})")

    # --- Ö5 EŞDEĞERLİK HÜKMÜ (ilan edilmiş band, değiştirilmedi) ----------
    print(f"\n--- Ö5 HÜKMÜ (band +-{ESDEGERLIK_BANDI} nat, İLAN EDİLMİŞ) ---")
    ustun = lo > 0
    zayif = hi < 0
    icinde = (lo > -ESDEGERLIK_BANDI) and (hi < ESDEGERLIK_BANDI)
    if ustun:
        hukum = "ML ETAS'I GEÇTİ (güven aralığı tümüyle sıfırın üstünde)"
    elif zayif:
        hukum = "ML ETAS'IN ALTINDA (güven aralığı tümüyle sıfırın altında)"
    elif icinde:
        hukum = "EŞDEĞER (aralık bandın içinde ve yeterince dar)"
    else:
        hukum = (f"HÜKÜM YOK — aralık [{lo:+.3f}, {hi:+.3f}] hem sıfırı hem "
                 f"band sınırını içeriyor; bu veriyle ayırt edilemez "
                 f"(saptanabilir en küçük fark {mde:.3f} nat)")
    print(f"  {hukum}")
    print("\n  README 3.5: ML, ETAS'ı GEÇMEDİKÇE başarı sayılmaz.")
    print(f"  Bu ölçüt karşılandı mı: {'EVET' if ustun else 'HAYIR'}")

    out = {"params": sec["params"], "n_satir": len(j), "n_pozitif": int(y.sum()),
           "kume_esit": bool(k_ml == k_et),
           "yalniz_ml": len(k_ml - k_et), "yalniz_etas": len(k_et - k_ml),
           "auc": {"poisson": auc_po, "etas": auc_et, "ml": auc_ml},
           "auc_tohum": {str(s): float(roc_auc_score(y, j["p_ml_t%d" % s]))
                         for s in SEEDS},
           "ig_vs_poisson": {"etas": ig_et, "ml": ig_ml},
           "ml_eksi_etas": {"ig": ig, "lo": lo, "hi": hi, "mde": mde,
                            "dayanak": basis},
           "band": ESDEGERLIK_BANDI, "hukum": hukum,
           "readme_3_5_gecti": bool(ustun)}
    (PROC / "ml_test_sonucu.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    j.to_parquet(PROC / "ml_etas_birlesik.parquet", index=False)
    for i, s in enumerate(SEEDS):
        models[i].save_model(str(PROC / f"lgbm_secilen_t{s}.txt"))
    print(f"\n-> {PROC / 'ml_test_sonucu.json'}")
    print(f"-> {PROC / 'ml_etas_birlesik.parquet'}  (farklılaşma analizi için)")


if __name__ == "__main__":
    main()
