"""ML-1: LightGBM — tablosal özniteliklerle gradyan artırma.

Bu, Kol B'nin (araştırma kolu) ilk modelidir. Sorusu şudur: katalogdan türetilen
tablosal öznitelikler (olay oranları, b-değeri, sismik sessizlik, moment birikimi),
Poisson ve ETAS'ın veremediği bir bilgi taşıyor mu?

**Beklenti dürüstçe düşük tutulmalıdır.** README §3.5'teki literatür dersi: 1994-2019
arası ANN-deprem makalelerinin çoğu zayıf baseline'la kıyaslandığı için değersiz
bulundu. Burada baseline zayıf değil — ETAS, kısa pencerelerde son derece güçlü bir
modeldir. Bu modelin ETAS'ı geçmemesi beklenen sonuçtur ve öyle raporlanacaktır.

TASARIM KARARLARI

1. **Poisson oranı öznitelik olarak verilir.** Model sıfırdan "nerede deprem olur"u
   öğrenmek zorunda kalmasın; asıl soru, uzun vadeli oranın ÜSTÜNE bir şey
   ekleyip ekleyemediğidir. Bu, baseline'ı geçmeyi kolaylaştırmaz — tam tersine
   çıtayı modelin içine koyar.

2. **Aşırı dengesizlik.** Pozitif oranı binde birkaç. `scale_pos_weight` yerine
   `is_unbalance=False` + düşük öğrenme oranı + erken durdurma tercih edildi:
   ağırlıklandırma olasılıkları bozar, bizse kalibre olasılık istiyoruz
   (log-loss ve Molchan bunu gerektirir).

3. **Sızıntı.** grid_features öznitelikleri yalnızca t < ref olaylardan üretir.
   Buna ek olarak eğitim/doğrulama/test bölmesi ZAMAN bazlıdır; hücreler
   bölmeler arasında paylaşılır ama zaman paylaşılmaz.

4. **Erken durdurma doğrulama setinde yapılır**, test seti hiç görülmez.

Çıktı:
  data/processed/lgbm_predictions.csv  — backtest'in okuduğu tahminler
  data/processed/lgbm_importance.csv   — SHAP tabanlı öznitelik önemleri
  docs/eda/lgbm_shap.png               — SHAP özet grafiği
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
FIGS = ROOT / "docs" / "eda"

SPLITS = {
    "train": ("1990-01-01", "2016-01-01"),
    "val": ("2016-01-01", "2021-01-01"),
    # Test dönemi kataloğun sonuna kadar uzatıldı. Gerekçe: M>=5.0 ve
    # 3 yıllık pencerede yalnızca 66 pozitif vardı ve jeofizik katman
    # ablasyonunun güven aralıkları bu yüzden sıfırı içeriyordu.
    # 2024-2026 verisi bu ana kadar HİÇ kullanılmadı, örneklem dışı.
    "test": ("2021-01-01", "2026-09-01"),
}
DEFAULT_TARGET = "target_30d_m50_all"
PRED_PATH = PROC / "lgbm_predictions.csv"

# Katalogdan türetilen öznitelikler + konum + baseline oranı
CATALOG_FEATURES = ["n30", "n90", "n365", "n3650", "bval", "bval_trend",
                    "quiescence_z", "tmax_since_m5", "moment_rate",
                    "lat_c", "lon_c", "poisson_rate"]

# Jeofizik katmanlar AYRI tutulur ki "bu katman gerçekten katkı veriyor mu?"
# sorusu kontrollü biçimde ölçülebilsin — README §3.4'ün ana sorusu budur.
LAYERS = {
    # fay geometrisi: "burada bir fay var"
    "fay": ["fault_dist_km", "fault_slip_rate", "fault_slip_max_50km",
            "fault_slip_sum_50km", "fault_count_50km"],
    # jeodezik gerinim: "kabuk burada şu hızla deforme oluyor"
    "gerinim": ["strain_mean", "strain_max", "strain_smooth25", "strain_grad"],
    # Coulomb: "şu ana kadarki depremler burayı ne kadar yükledi/boşalttı"
    "coulomb": ["cfs_cum", "cfs_last", "days_since_cfs_event"],
}
LAYER_FILES = {"fay": "fault_features.csv", "gerinim": "strain_features.csv",
               "coulomb": "coulomb_features.csv"}

# Coulomb ZAMANLA DEĞİŞİR: (hücre, referans tarihi) çiftine bağlıdır, diğer iki
# katman gibi yalnızca hücreye değil. Yanlış anahtarla birleştirmek her hücreye
# tek bir değer yapıştırır ve katmanın tüm bilgisini sessizce yok eder.
TIME_VARYING = {"coulomb"}


# Hangi öznitelik tablosunun okunacağı. "grid_features.parquet" aylık
# referanslıdır (eski kurulum); "grid_features_weekly.parquet" ETAS'ın 208
# haftalık başlangıcına DEMİRLENMİŞTİR ve eşit-bilgi karşılaştırması için
# zorunludur (bkz. VAKA_DEFTERI V18, V19).
FEATURE_TABLE = "grid_features.parquet"


def load_dataset(target: str, layers: tuple = ()) -> dict:
    """Öznitelik tablosunu okur, Poisson oranını ve istenen katmanları ekler."""
    feat = pd.read_parquet(PROC / FEATURE_TABLE)
    feat["ref_date"] = pd.to_datetime(feat["ref_date"], utc=True)

    rate_col = "rate_all_m5.0_yr" if target.endswith("_all") else "rate_m5.0_yr"
    base = pd.read_csv(PROC / "baseline_poisson.csv")[["cell_id", rate_col]]
    feat = feat.merge(base, on="cell_id", how="left")
    feat["poisson_rate"] = feat[rate_col].fillna(0.0)

    for name in layers:
        fpath = PROC / LAYER_FILES[name]
        if not fpath.exists():
            print(f"! {fpath} yok — '{name}' katmanı atlanıyor.")
            continue
        layer = pd.read_csv(fpath)
        if name in TIME_VARYING:
            layer["ref_date"] = pd.to_datetime(layer["ref_date"], utc=True)
            feat = feat.merge(layer, on=["cell_id", "ref_date"], how="left")
        else:
            feat = feat.merge(layer, on="cell_id", how="left")

    out = {}
    for name, (a, b) in SPLITS.items():
        m = ((feat.ref_date >= pd.Timestamp(a, tz="UTC"))
             & (feat.ref_date < pd.Timestamp(b, tz="UTC")))
        out[name] = feat[m].dropna(subset=[target]).reset_index(drop=True)
    return out


def train(target: str = DEFAULT_TARGET, seed: int = 42,
          layers: tuple = (), quiet: bool = False,
          data: dict | None = None, extra_features: list | None = None) -> dict:
    """LightGBM eğitir.

    `data` ve `extra_features`, SIZINTI KANARYALARI için vardır
    (`src/eval/leakage_canary.py`): kanarya, kendi oyuncak modelini değil
    GERÇEK eğitim yolunu sınamalıdır. Kanarya kendi modelini kurarsa, sınadığı
    şey boru hattı değil o oyuncak olur -- nitekim ilk sürümde tam bu oldu ve
    temiz model 0,4584 (şanstan kötü) verdi.

    Üretimde bu iki parametre kullanılmaz.
    """
    import lightgbm as lgb

    data = load_dataset(target, layers) if data is None else data
    features = list(CATALOG_FEATURES) + list(extra_features or [])
    for name in layers:
        cols = LAYERS[name]
        if all(c in data["train"].columns for c in cols):
            features += cols
    if not quiet:
        for name, df in data.items():
            print(f"{name}: {len(df):7d} satır, {int(df[target].sum()):4d} pozitif "
                  f"(%{100*df[target].mean():.3f})")
        print(f"öznitelik: {len(features)} "
              f"(katman: {', '.join(layers) if layers else 'yok — yalnızca katalog'})")

    if data["train"][target].sum() < 20:
        raise RuntimeError("Eğitim setinde yeterli pozitif yok — hedefi değiştirin.")

    def xy(df):
        return df[features], df[target].astype(int)

    x_tr, y_tr = xy(data["train"])
    x_va, y_va = xy(data["val"])

    # Az pozitifli, çok gürültülü bir problem: küçük ağaçlar, güçlü düzenlileştirme,
    # düşük öğrenme oranı ve doğrulama setinde erken durdurma.
    params = dict(
        objective="binary", metric="binary_logloss", learning_rate=0.02,
        num_leaves=15, min_child_samples=200, feature_fraction=0.8,
        bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0,
        verbosity=-1, seed=seed, num_threads=4,
    )
    model = lgb.train(
        params, lgb.Dataset(x_tr, y_tr),
        num_boost_round=3000,
        valid_sets=[lgb.Dataset(x_va, y_va)], valid_names=["val"],
        callbacks=[lgb.early_stopping(150, verbose=False),
                   lgb.log_evaluation(0)],
    )
    val_ll = float(model.best_score["val"]["binary_logloss"])
    if not quiet:
        print(f"\nEn iyi yineleme: {model.best_iteration} "
              f"(doğrulama logloss {val_ll:.5f})")

    rows = []
    # YALNIZCA VAR OLAN bölümler. Sızıntı kanaryası test bölümünü hiç
    # yüklemez (docs/TEST_DOKUNUSLARI.md, Düzeltme 1); `train` bunu bir hata
    # değil, geçerli bir çağrı olarak görmelidir -- aksi hâlde "test verisini
    # silmek" yolu tıkanır ve veri-yokluğu deseni uygulanamaz.
    for name in [n for n in ("val", "test") if n in data]:
        df = data[name]
        p = model.predict(df[features], num_iteration=model.best_iteration)
        rows.append(pd.DataFrame({"cell_id": df.cell_id, "ref_date": df.ref_date,
                                  "split": name, "target": target, "p_lgbm": p}))
    preds = pd.concat(rows, ignore_index=True)
    if not quiet:
        preds.to_csv(PRED_PATH, index=False)
        print(f"{len(preds)} tahmin -> {PRED_PATH}")
        explain(model, x_va, seed, features)
    return {"model": model, "preds": preds, "val_logloss": val_ll,
            "features": features, "data": data}


def explain(model, x_sample: pd.DataFrame, seed: int, features: list,
            n_sample: int = 20000) -> None:
    """SHAP ile öznitelik katkılarını raporlar.

    Soru "hangi öznitelik önemli" değil, "hangi KATMAN bilgi getiriyor" —
    README §3.4'te SHAP'ın konuluş amacı budur. Jeofizik katmanlar (gerinim,
    Coulomb, fay uzaklığı) eklendiğinde bu tablo onların gerçekten katkı verip
    vermediğini gösterecek.
    """
    try:
        import shap
    except ImportError:
        print("! shap kurulu değil — öznitelik önemi gain ile raporlanıyor.")
        imp = pd.DataFrame({"feature": model.feature_name(),
                            "gain": model.feature_importance("gain")})
        imp = imp.sort_values("gain", ascending=False)
        imp.to_csv(PROC / "lgbm_importance.csv", index=False)
        print(imp.to_string(index=False))
        return

    sample = x_sample.sample(min(n_sample, len(x_sample)), random_state=seed)
    values = shap.TreeExplainer(model).shap_values(sample)
    if isinstance(values, list):          # ikili sınıflandırmada [neg, poz]
        values = values[1]
    mean_abs = np.abs(values).mean(axis=0)
    imp = (pd.DataFrame({"feature": sample.columns, "mean_abs_shap": mean_abs})
           .sort_values("mean_abs_shap", ascending=False))
    imp.to_csv(PROC / "lgbm_importance.csv", index=False)
    print("\nSHAP öznitelik katkıları (ortalama |değer|):")
    print(imp.to_string(index=False))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    FIGS.mkdir(parents=True, exist_ok=True)
    shap.summary_plot(values, sample, show=False, max_display=len(features))
    plt.tight_layout()
    plt.savefig(FIGS / "lgbm_shap.png", dpi=130, bbox_inches="tight")
    plt.close()
    print(f"-> {FIGS / 'lgbm_shap.png'}")


CONFIGS = [((), "yalnızca katalog"), (("fay",), "+ fay"),
           (("gerinim",), "+ gerinim"), (("coulomb",), "+ coulomb"),
           (("fay", "gerinim", "coulomb"), "+ hepsi")]


def ablation(target: str = DEFAULT_TARGET, seeds: tuple = (1, 2, 3, 4, 5)) -> None:
    """Jeofizik katmanlar gerçekten katkı veriyor mu? — kontrollü karşılaştırma.

    Aynı veri, aynı hiperparametreler, tek fark eklenen katman.

    BİRDEN FAZLA TOHUM zorunlu: LightGBM'in örnekleme rastgeleliği, pozitif
    sayısı yüzler mertebesindeyken tek bir koşuyu yanıltıcı yapar. Bir farkın
    "katkı" sayılabilmesi için tohumlar arası saçılımın İKİ KATINDAN büyük
    olması aranır. Literatürdeki zayıf-baseline hatasının (README §3.5) bu
    projedeki karşılığı, gürültüyü sinyal sanmaktır.
    """
    from sklearn.metrics import roc_auc_score

    print(f"Katman ablasyonu — hedef {target}, {len(seeds)} tohum")
    rows = []
    for layers, label in CONFIGS:
        for seed in seeds:
            r = train(target, seed=seed, layers=layers, quiet=True)
            data, preds = r["data"], r["preds"]
            out = {"katman": label, "seed": seed, "val_logloss": r["val_logloss"],
                   "n_feat": len(r["features"])}
            for split in ("val", "test"):
                p = preds[preds.split == split]
                y = data[split][target].astype(int).to_numpy()
                out[f"{split}_auc"] = (roc_auc_score(y, p["p_lgbm"].to_numpy())
                                       if y.sum() else np.nan)
            rows.append(out)
        done = [d for d in rows if d["katman"] == label]
        print(f"  {label:18s} ({done[0]['n_feat']:2d} öznitelik): "
              f"val AUC {np.mean([d['val_auc'] for d in done]):.4f}  "
              f"test AUC {np.mean([d['test_auc'] for d in done]):.4f}")

    df = pd.DataFrame(rows)
    summary = df.groupby("katman")[["val_auc", "test_auc"]].agg(["mean", "std"])
    print()
    print(summary.round(5).to_string())

    base = df[df.katman == "yalnızca katalog"]
    print()
    print("Katalog-only referansına göre (tohum ortalaması):")
    for label in [c[1] for c in CONFIGS[1:]]:
        cur = df[df.katman == label]
        for col in ("val_auc", "test_auc"):
            delta = cur[col].mean() - base[col].mean()
            spread = max(base[col].std(), cur[col].std())
            print(f"  {label:18s} {col:9s}: {delta:+.4f} (tohum saçılımı ~{spread:.4f})")

    # ASIL SINAMA: olay bazlı bootstrap.
    #
    # Tohum saçılımı YETERSİZ bir ölçüttür ve bu proje bunu somut olarak yaşadı:
    # Coulomb katmanı 15 tohumda +0.0205 kazanç ve p=1e-13 verdi, ama olay bazlı
    # bootstrap güven aralığı sıfırı içeriyordu. Tohum p-değeri yalnızca
    # TEKRARLANABİLİRLİĞİ ölçer; asıl belirsizlik test setindeki pozitif olay
    # sayısından (burada 66) gelir. Bir katman ancak bootstrap aralığı sıfırın
    # dışındaysa "katkı veriyor" sayılır.
    print()
    print("Olay bazlı bootstrap (asıl sınama):")
    for layers, label in CONFIGS[1:]:
        _bootstrap_layer(target, layers, label)

    df.to_csv(PROC / "lgbm_ablation.csv", index=False)
    print(f"-> {PROC / 'lgbm_ablation.csv'}")


def _bootstrap_layer(target: str, layers: tuple, label: str,
                     seed: int = 7, n_boot: int = 2000) -> None:
    from sklearn.metrics import roc_auc_score

    a = train(target, seed=seed, layers=(), quiet=True)
    b = train(target, seed=seed, layers=layers, quiet=True)
    y = a["data"]["test"][target].astype(int).to_numpy()
    pa = a["preds"][a["preds"].split == "test"]["p_lgbm"].to_numpy()
    pb = b["preds"][b["preds"].split == "test"]["p_lgbm"].to_numpy()
    if y.sum() < 5:
        print(f"  {label:18s}: yetersiz pozitif")
        return
    rng = np.random.default_rng(0)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        if y[idx].sum() == 0:
            continue
        diffs.append(roc_auc_score(y[idx], pb[idx]) - roc_auc_score(y[idx], pa[idx]))
    diffs = np.array(diffs)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    verdict = ("KATKI VAR" if lo > 0 else "ZARAR" if hi < 0
               else "belirsiz — aralık sıfırı içeriyor")
    print(f"  {label:18s}: {diffs.mean():+.4f}  %95 GA [{lo:+.4f}, {hi:+.4f}]"
          f"  -> {verdict}", flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="LightGBM modeli")
    ap.add_argument("stage", nargs="?", default="train",
                    choices=["train", "ablation"])
    ap.add_argument("--target", default=DEFAULT_TARGET)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--layers", default="", help="virgülle ayrılmış: fay,gerinim")
    args = ap.parse_args()
    layers = tuple(x.strip() for x in args.layers.split(",") if x.strip())
    if args.stage == "ablation":
        ablation(args.target)
    else:
        train(args.target, args.seed, layers=layers)


if __name__ == "__main__":
    main()
