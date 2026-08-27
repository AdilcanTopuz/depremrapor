"""ML-2: Nöral yoğunluk modeli — RECAST'in fikri, bu projenin ızgarasında.

RECAST (Dascher-Cousineau ve ark. 2023) bir nöral nokta sürecidir: koşullu
yoğunluğu (intensity) sinir ağıyla modeller ve olay geçmişini bir RNN ile
kodlar. Bu modül aynı fikri projenin mekânsal ızgarasına taşır ve README §1'deki
bahsi sınar: jeofizik kovaryatlar yoğunluğa DOĞRUDAN girdiğinde katkı verir mi?

**NEDEN LightGBM YETMEYEBİLİR — sınanan hipotez budur.**
Mevcut LightGBM bir İKİLİ SINIFLANDIRICI: "pencerede en az bir olay var mı?"
sorusunu log-loss ile eniyiler. Oysa ETAS bir ORAN modelidir ve değerlendirmede
kullandığımız bilgi kazancı metriği de oranların doğruluğunu ölçer. Yani model,
ölçüldüğü amaçtan FARKLI bir amaç için eniyilenmiş oluyor. Kovaryatların
katkı vermemesinin bir açıklaması bu uyumsuzluk olabilir.

Bu modül Poisson olabilirliğiyle eğitilir — değerlendirmenin kullandığı
büyüklüğün ta kendisi.

DENEY TASARIMI (her biri kovaryatlı ve kovaryatsız):
  1. LightGBM ikili    — mevcut referans
  2. LightGBM Poisson  — YALNIZCA amaç fonksiyonu değişir (nöral değil)
  3. Nöral Poisson     — amaç aynı, model ailesi değişir
Bu üçlü, "nöral olmak" ile "doğru amacı eniyilemek" etkilerini AYIRIR. İkisini
birden değiştirip iyileşme görmek, hangisinin işe yaradığını söylemez.

Çıktı: data/processed/neural_predictions.csv
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

SPLITS = {
    "train": ("1990-01-01", "2016-01-01"),
    "val": ("2016-01-01", "2021-01-01"),
    "test": ("2021-01-01", "2026-09-01"),
}
DEFAULT_TARGET = "count_30d_m45_all"
SEED = 42


def poisson_information_gain(y: np.ndarray, rate_a: np.ndarray,
                             rate_b: np.ndarray) -> float:
    """Olay başına bilgi kazancı (Rhoades ve ark. 2011) — değerlendirme ölçütü.

    Sayım hedefleriyle çalışır: gözlenen her olay, modelin o hücreye atadığı
    oranın logaritmasıyla ödüllendirilir; toplam beklenen sayı farkı cezalandırılır.
    """
    n = float(y.sum())
    if n == 0:
        return np.nan
    a = np.maximum(rate_a, 1e-12)
    b = np.maximum(rate_b, 1e-12)
    return float((y * (np.log(b) - np.log(a))).sum() / n
                 - (b.sum() - a.sum()) / n)


def load_data(target: str, layers: tuple = ()) -> dict:
    from src.models.lgbm import load_dataset
    return load_dataset(target, layers)


def features_for(layers: tuple, columns) -> list:
    from src.models.lgbm import CATALOG_FEATURES, LAYERS
    feats = list(CATALOG_FEATURES)
    for name in layers:
        cols = LAYERS[name]
        if all(c in columns for c in cols):
            feats += cols
    return feats


def train_lgbm_poisson(target: str, layers: tuple = (), seed: int = SEED,
                       quiet: bool = False) -> dict:
    """Aynı ağaç modeli, Poisson amacıyla. Nöral etkiyi izole etmek için kontrol."""
    import lightgbm as lgb

    data = load_data(target, layers)
    feats = features_for(layers, data["train"].columns)
    x_tr, y_tr = data["train"][feats], data["train"][target].astype(float)
    x_va, y_va = data["val"][feats], data["val"][target].astype(float)

    params = dict(objective="poisson", metric="poisson", learning_rate=0.02,
                  num_leaves=15, min_child_samples=200, feature_fraction=0.8,
                  bagging_fraction=0.8, bagging_freq=1, lambda_l2=10.0,
                  verbosity=-1, seed=seed, num_threads=4)
    model = lgb.train(params, lgb.Dataset(x_tr, y_tr), num_boost_round=3000,
                      valid_sets=[lgb.Dataset(x_va, y_va)], valid_names=["val"],
                      callbacks=[lgb.early_stopping(150, verbose=False),
                                 lgb.log_evaluation(0)])
    preds = {s: model.predict(data[s][feats], num_iteration=model.best_iteration)
             for s in ("val", "test")}
    if not quiet:
        print(f"  LightGBM-Poisson: en iyi yineleme {model.best_iteration}, "
              f"{len(feats)} öznitelik")
    return {"preds": preds, "data": data, "features": feats}


class IntensityNet:
    """Poisson olabilirliğiyle eğitilen küçük ileri beslemeli ağ.

    Çıkış softplus'tan geçirilir: yoğunluk POZİTİF olmak zorundadır ve exp()
    kullanmak seyrek hedeflerde taşmaya yol açar. Ağ küçük tutulur (iki gizli
    katman); eğitim setinde 652 pozitif var, daha büyük bir ağ ezberler.
    """

    def __init__(self, n_features: int, hidden: int = 64, seed: int = SEED):
        import torch
        import torch.nn as nn

        torch.manual_seed(seed)
        self.torch = torch
        self.net = nn.Sequential(
            nn.Linear(n_features, hidden), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden, hidden // 2), nn.ReLU(), nn.Dropout(0.2),
            nn.Linear(hidden // 2, 1), nn.Softplus(),
        )

    def fit(self, x_tr, y_tr, x_va, y_va, epochs: int = 200,
            lr: float = 1e-3, patience: int = 25, quiet: bool = False):
        torch = self.torch
        opt = torch.optim.Adam(self.net.parameters(), lr=lr, weight_decay=1e-4)
        xt = torch.tensor(x_tr, dtype=torch.float32)
        yt = torch.tensor(y_tr, dtype=torch.float32).unsqueeze(1)
        xv = torch.tensor(x_va, dtype=torch.float32)
        yv = torch.tensor(y_va, dtype=torch.float32).unsqueeze(1)

        def nll(rate, y):
            # Poisson negatif log-olabilirlik (sabit terim atlanır)
            return (rate - y * torch.log(rate + 1e-12)).mean()

        best, best_state, bad = np.inf, None, 0
        n = len(xt)
        batch = 8192
        for ep in range(epochs):
            self.net.train()
            perm = torch.randperm(n)
            for i in range(0, n, batch):
                idx = perm[i:i + batch]
                opt.zero_grad()
                loss = nll(self.net(xt[idx]), yt[idx])
                loss.backward()
                opt.step()
            self.net.eval()
            with torch.no_grad():
                v = float(nll(self.net(xv), yv))
            if v < best - 1e-7:
                best, bad = v, 0
                best_state = {k: t.clone() for k, t in self.net.state_dict().items()}
            else:
                bad += 1
                if bad >= patience:
                    break
        if best_state is not None:
            self.net.load_state_dict(best_state)
        if not quiet:
            print(f"  Nöral: {ep+1} devir, en iyi doğrulama NLL {best:.6f}")
        return best

    def predict(self, x) -> np.ndarray:
        torch = self.torch
        self.net.eval()
        with torch.no_grad():
            return self.net(torch.tensor(x, dtype=torch.float32)).numpy().ravel()


def standardize(train: np.ndarray, *others):
    """Öznitelikleri eğitim setinin istatistikleriyle ölçekler.

    Sinir ağları ölçeğe duyarlıdır; ölçekleme İSTATİSTİKLERİ yalnızca eğitim
    setinden alınır — doğrulama/test setinden almak sızıntı olur.
    """
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd[sd < 1e-9] = 1.0
    fix = lambda a: np.nan_to_num((a - mu) / sd, nan=0.0, posinf=0.0, neginf=0.0)
    return (fix(train), *[fix(o) for o in others])


def train_neural(target: str, layers: tuple = (), seed: int = SEED,
                 quiet: bool = False) -> dict:
    data = load_data(target, layers)
    feats = features_for(layers, data["train"].columns)
    x = {s: data[s][feats].to_numpy(dtype=float) for s in data}
    y = {s: data[s][target].to_numpy(dtype=float) for s in data}
    xs_tr, xs_va, xs_te = standardize(x["train"], x["val"], x["test"])

    net = IntensityNet(len(feats), seed=seed)
    net.fit(xs_tr, y["train"], xs_va, y["val"], quiet=quiet)
    return {"preds": {"val": net.predict(xs_va), "test": net.predict(xs_te)},
            "data": data, "features": feats}


def _poisson_reference(rows: pd.DataFrame, target: str) -> np.ndarray:
    """Poisson baseline'ının bu satırlar için beklediği olay sayısı."""
    import re

    m = re.match(r"count_(\d+)d_m(\d+)", target)
    window = int(m.group(1))
    mag = float(m.group(2)) / 10.0
    base = pd.read_csv(PROC / "baseline_poisson.csv").set_index("cell_id")
    col = "rate_all_m5.0_yr" if target.endswith("_all") else "rate_m5.0_yr"
    # GR ile ölçekle — kalibre b ile (bkz. daily_backtest'teki aynı düzeltme)
    from src.config import load_mc_and_b
    scale = 10 ** (-load_mc_and_b()[1] * (mag - 5.0)) * window / 365.25
    return rows.cell_id.map(base[col]).fillna(0.0).to_numpy() * scale


def compare(target: str = DEFAULT_TARGET, seeds: tuple = (1, 2, 3)) -> None:
    """Üçlü karşılaştırma: amaç fonksiyonu mu, model ailesi mi belirleyici?"""
    from sklearn.metrics import roc_auc_score
    from src.models.lgbm import train as train_binary

    binary_target = target.replace("count_", "target_")
    rows = []
    for layers, lab in (((), "kovaryatsız"), (("coulomb",), "+ coulomb")):
        for seed in seeds:
            data = None
            # 1) İkili LightGBM — mevcut referans
            rb = train_binary(binary_target, seed=seed, layers=layers, quiet=True)
            # 2) Poisson LightGBM — yalnızca amaç değişti
            rp = train_lgbm_poisson(target, layers, seed, quiet=True)
            # 3) Nöral Poisson — amaç aynı, model ailesi değişti
            rn = train_neural(target, layers, seed, quiet=True)

            counts = rp["data"]["test"][target].to_numpy(dtype=float)
            binary = (counts > 0).astype(int)
            # REFERANS: eğitim verisiyle kalibre edilmiş Poisson baseline.
            #
            # Test verisinin ortalamasından sabit bir oran kurmak YANLIŞTIR:
            # o referans test dönemindeki toplam olay sayısını zaten bilir ve
            # hiçbir model onu geçemez. Nitekim Poisson baseline bile ona karşı
            # -0.084 veriyordu. Bilgi kazancı, örneklem dışı bir referansa göre
            # ölçülmelidir — ETAS değerlendirmesinde de böyle yapıldı.
            base_rate = _poisson_reference(rp["data"]["test"], target)
            for name, pred, src in (("LGBM-ikili", rb["preds"], "b"),
                                    ("LGBM-Poisson", rp["preds"], "p"),
                                    ("Nöral-Poisson", rn["preds"], "p")):
                p = (pred[pred.split == "test"]["p_lgbm"].to_numpy()
                     if src == "b" else pred["test"])
                rows.append({
                    "model": name, "katman": lab, "seed": seed,
                    "auc": roc_auc_score(binary, p),
                    # Bilgi kazancı yalnızca ORAN modelleri için anlamlı:
                    # ikili sınıflandırıcının çıktısı olasılıktır, oran değil.
                    "ig": (poisson_information_gain(counts, base_rate, p)
                           if src == "p" else np.nan),
                })
        print(f"{lab} tamamlandı", flush=True)

    df = pd.DataFrame(rows)
    print()
    print(df.groupby(["model", "katman"])[["auc", "ig"]]
          .agg(["mean", "std"]).round(4).to_string())
    df.to_csv(PROC / "neural_comparison.csv", index=False)
    print(f"\n-> {PROC / 'neural_comparison.csv'}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="compare", choices=["compare"])
    ap.add_argument("--target", default=DEFAULT_TARGET)
    args = ap.parse_args()
    compare(args.target)


if __name__ == "__main__":
    main()
