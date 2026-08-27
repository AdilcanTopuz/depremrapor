"""Zaman bazlı backtest iskeleti.

Bölme:
  Eğitim   : 1990-01-01 .. 2015-12-31
  Doğrulama: 2016-01-01 .. 2020-12-31
  Test     : 2021-01-01 .. 2023-12-31  (Kahramanmaraş 2023-02-06 testte!)

Metrikler: ROC-AUC, log-loss, Molchan diyagramı (alan-kaplama vs kaçırma oranı),
ETAS'a göre olay başına bilgi kazancı (Faz 2'de pyCSEP entegre edilecek).
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# Hiçbir hücreye sıfır olasılık verilmez: bir hücrede deprem olduğunda log-loss
# sonsuza gider. 1e-5, 1000 simülasyonun çözebileceğinden (1e-3) belirgin daha
# küçük ama sonlu bir taban.
PROB_FLOOR = 1e-5

FORECAST_PATH = PROC / "etas_forecast.csv"
LGBM_PATH = PROC / "lgbm_predictions.csv"

SPLITS = {
    "train": ("1990-01-01", "2016-01-01"),
    "val":   ("2016-01-01", "2021-01-01"),
    # Test dönemi kataloğun sonuna kadar uzatıldı (2024-2026 verisi bu ana
    # kadar hiç kullanılmadı, örneklem dışı).
    "test":  ("2021-01-01", "2026-09-01"),
}


def load_split(target: str = "target_30d_m50"):
    feat = pd.read_parquet(PROC / "grid_features.parquet")
    feat["ref_date"] = pd.to_datetime(feat["ref_date"], utc=True)
    out = {}
    for name, (a, b) in SPLITS.items():
        m = (feat.ref_date >= pd.Timestamp(a, tz="UTC")) & (feat.ref_date < pd.Timestamp(b, tz="UTC"))
        out[name] = feat[m].dropna(subset=[target])
    return out, target


def molchan(y_true: np.ndarray, y_score: np.ndarray, n_points: int = 50):
    """Molchan diyagramı: alan-kaplama tau vs kaçırma oranı nu. Köşegen = rastgele."""
    thresholds = np.quantile(y_score, np.linspace(0, 1, n_points))
    taus, nus = [], []
    for th in thresholds:
        alarm = y_score >= th
        taus.append(alarm.mean())
        hits = (y_true.astype(bool) & alarm).sum()
        total = y_true.sum()
        nus.append(1 - hits / total if total > 0 else np.nan)
    return np.array(taus), np.array(nus)


def evaluate(y_true, y_score, label: str):
    from sklearn.metrics import log_loss, roc_auc_score
    auc = roc_auc_score(y_true, y_score) if y_true.sum() > 0 else np.nan
    ll = log_loss(y_true, np.clip(y_score, 1e-9, 1 - 1e-9))
    tau, nu = molchan(np.asarray(y_true), np.asarray(y_score))
    # Molchan alan skoru (0.5 = rastgele, düşük = iyi). Eşik büyüdükçe tau KÜÇÜLDÜĞÜ
    # için integral artan tau sırasına göre alınmalı; aksi halde işaret ters döner.
    order = np.argsort(tau)
    area = np.trapezoid(np.nan_to_num(nu, nan=1.0)[order], tau[order])
    print(f"[{label}] AUC={auc:.3f}  logloss={ll:.4f}  molchan_area={area:.3f}  "
          f"pozitif={int(y_true.sum())}/{len(y_true)}")
    return dict(auc=auc, logloss=ll, molchan_area=area)


def poisson_scores(rows: pd.DataFrame, window_days: int,
                   all_events: bool = False) -> np.ndarray:
    """Smoothed-seismicity Poisson baseline'ının bu satırlar için olasılıkları.

    Model zamandan bağımsızdır (uzun vadeli oran), bu yüzden skor yalnızca hücreye
    bağlıdır: p = 1 - exp(-oran * pencere/365.25).

    `all_events`, hedefin tanımıyla eşleşmelidir: artçı dahil hedeflerde artçı
    dahil oran kullanılmazsa baseline haksız yere düşük kalır (eğitim döneminde
    9.39 vs 15.31 olay/yıl).
    """
    col = "rate_all_m5.0_yr" if all_events else "rate_m5.0_yr"
    base = pd.read_csv(PROC / "baseline_poisson.csv")
    rate = rows[["cell_id"]].merge(base[["cell_id", col]],
                                   on="cell_id", how="left")[col]
    rate = rate.fillna(0.0).to_numpy()
    return 1 - np.exp(-rate * window_days / 365.25)


def _load_forecast():
    """ETAS tahmin dosyasını okur. Yoksa (None, yol) döner."""
    if not FORECAST_PATH.exists():
        return None, FORECAST_PATH
    fc = pd.read_csv(FORECAST_PATH)
    fc["ref_date"] = pd.to_datetime(fc["ref_date"], utc=True)
    return fc, FORECAST_PATH


def etas_scores(rows: pd.DataFrame, window_days: int, target_mw: float = 5.0,
                column: str = "p_etas"):
    """ETAS tahminlerini satırlara eşler. Tahmin yoksa (None, yol).

    Simülasyonda hiç olay üretmemiş hücreler dosyada yer almaz; bunlar 0 değil,
    çok küçük bir taban değeri alır — log-loss sonsuza gitmesin diye (bir hücreye
    "imkânsız" demek, orada deprem olduğunda sonsuz ceza demektir).
    """
    fc, path = _load_forecast()
    if fc is None:
        return None, path
    sel = fc[(fc.window_days == window_days) & (fc.target_mw == target_mw)]
    merged = rows[["cell_id", "ref_date"]].merge(
        sel[["cell_id", "ref_date", column]], on=["cell_id", "ref_date"], how="left")
    return merged[column].fillna(0.0).clip(lower=PROB_FLOOR).to_numpy(), path


def lgbm_scores(rows: pd.DataFrame, target: str, split: str):
    """LightGBM tahminlerini satırlara eşler. Yoksa None.

    Yalnızca AYNI hedef için üretilmiş tahminler kullanılır: model hedefe özel
    eğitildiği için başka bir hedefin tahminlerini buraya eşlemek sessizce
    yanlış bir karşılaştırma üretir.
    """
    if not LGBM_PATH.exists():
        return None
    pr = pd.read_csv(LGBM_PATH)
    pr = pr[(pr.target == target) & (pr.split == split)]
    if not len(pr):
        return None
    pr["ref_date"] = pd.to_datetime(pr["ref_date"], utc=True)
    merged = rows[["cell_id", "ref_date"]].merge(
        pr[["cell_id", "ref_date", "p_lgbm"]], on=["cell_id", "ref_date"], how="left")
    if merged["p_lgbm"].isna().all():
        return None
    return merged["p_lgbm"].fillna(PROB_FLOOR).clip(lower=PROB_FLOOR).to_numpy()


def forecast_coverage(window_days: int, target_mw: float = 5.0):
    """ETAS tahmininin kapsadığı referans tarihleri. Dosya yoksa (None, yol)."""
    fc, path = _load_forecast()
    if fc is None:
        return None, path
    sel = fc[(fc.window_days == window_days) & (fc.target_mw == target_mw)]
    return pd.DatetimeIndex(sel["ref_date"].unique()), path


def compare(rows: pd.DataFrame, target: str, window_days: int, label: str,
            with_etas: bool = True) -> None:
    """Aynı satır kümesi üzerinde tüm modelleri değerlendirir.

    `with_etas=False` ise ETAS hiç skorlanmaz. Kapsam dışında ETAS'ı yine de
    hesaplamak, tüm satırların olasılık tabanını aldığı sabit bir skor üretir;
    bu da hata vermeden AUC 0.500 yazar ve "ETAS kötü" gibi okunur.
    """
    y = rows[target].to_numpy()
    if y.sum() == 0:
        print(f"[{label}] pozitif yok — atlandı")
        return
    all_events = target.endswith("_all")
    evaluate(y, poisson_scores(rows, window_days, all_events), f"{label}/poisson")
    # naif referans: son 1 yıldaki olay sayısı (model değil, sadece aktiflik)
    n365 = rows["n365"].to_numpy().astype(float)
    evaluate(y, n365 / (n365.max() or 1), f"{label}/n365-naif")
    lg = lgbm_scores(rows, target, label)
    if lg is not None:
        evaluate(y, lg, f"{label}/LightGBM")
    if not with_etas:
        return
    scores, _ = etas_scores(rows, window_days)
    if scores is not None:
        evaluate(y, scores, f"{label}/ETAS")


def main(window_days: int = 30) -> None:
    splits, _ = load_split("target_30d_m50")
    covered, fc_path = forecast_coverage(window_days)

    if covered is None:
        print(f"UYARI: ETAS tahmini yok ({fc_path.name}) — asıl çıta odur.\n"
              "  Üretmek için: python -m src.models.etas_baseline forecast\n")
    else:
        print(f"ETAS tahmini {len(covered)} referans tarihini kapsıyor "
              f"({covered.min():%Y-%m} - {covered.max():%Y-%m})\n")

    # Hedefin iki tanımı da raporlanır:
    #   _all   : artçılar dahil — ETAS bir dallanma süreci olarak artçı da ürettiği
    #            için ASIL karşılaştırma budur
    #   (düz)  : yalnızca ana şoklar — README'nin ürün tanımı
    for target in ("target_30d_m50_all", "target_30d_m50"):
        print(f"=== {target} ===")
        for name in ("val", "test"):
            rows = splits[name]
            if not len(rows):
                continue
            # ETAS varsa TÜM modeller aynı satırlarda ölçülür. Aksi halde Poisson
            # daha geniş bir kümede skorlanır ve karşılaştırma haksız olur; ayrıca
            # ETAS'ın kapsamadığı satırlar taban değeri alıp anlamsız bir AUC üretir.
            suffix, with_etas = "", covered is not None
            if covered is not None:
                in_cov = rows[rows.ref_date.isin(covered)]
                if len(in_cov):
                    rows = in_cov
                else:
                    # Kapsam dışı: ETAS burada ölçülemez ama Poisson/naif
                    # sonuçlarını atmanın anlamı yok — açıkça etiketlenerek verilir.
                    suffix = " (ETAS kapsamı dışı — yalnızca Poisson/naif)"
                    with_etas = False
            n_pos = int(rows[target].sum())
            print(f"  {name}: {len(rows)} satır, {n_pos} pozitif{suffix}")
            compare(rows, target, window_days, name, with_etas)
        print()

    print("Not: ETAS'ı geçmeyen hiçbir ML sonucu başarı sayılmaz (README §3.5).")


if __name__ == "__main__":
    main()
