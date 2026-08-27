"""Baseline 1: Smoothed-seismicity uzun vadeli Poisson modeli.

Eğitim dönemindeki Mw>=Mc ana şok yoğunluğunu Gauss çekirdekle (sigma ~ 25 km)
yumuşatıp her hücre için yıllık M>=X oranı üretir; pencere olasılığı
p = 1 - exp(-rate * w/365).

Bu, her ML modelinin geçmesi gereken EN DÜŞÜK çıta. Asıl rakip ETAS'tır
(bkz. src/models/etas_notes.md).
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# Eğitim yalnızca tamlık dönemini kapsar. Kataloğun tamamını (1904+) kullanmak,
# Mw>=Mc olayların 1990 öncesinde büyük ölçüde kayıtsız olması nedeniyle oranı
# yıl sayısına bölerken sistematik olarak düşürür.
TRAIN_START = pd.Timestamp("1990-01-01", tz="UTC")
TRAIN_END = pd.Timestamp("2016-01-01", tz="UTC")
SIGMA_KM = 25.0
STEP = 0.25          # grid_features ile aynı hücre boyu
TARGET_MW = 5.0
MC_FALLBACK, GR_B_FALLBACK = 3.8, 1.0


def load_mc_and_b() -> tuple[float, float]:
    """Kesme büyüklüğü ve b — GR ölçeklemesi bu ikisine bağlıdır.

    Yumuşatılmış oran, katalogda fiilen kullanılan Mc üzerinden hesaplanır; hedef
    büyüklüğe 10^(-b·(M_hedef - Mc)) ile ölçeklenir. Mc'yi olduğundan düşük (ör. 3.0)
    varsaymak, oranları on kat mertebesinde yanlış verir.
    """
    path = PROC / "mc_by_period.csv"
    if not path.exists():
        print(f"! {path} yok — Mc={MC_FALLBACK}, b={GR_B_FALLBACK} varsayılıyor.")
        return MC_FALLBACK, GR_B_FALLBACK
    mc_df = pd.read_csv(path)
    mc_df = mc_df[mc_df["period"].str.slice(0, 4).astype(int) >= 1990].dropna(subset=["mc"])
    if mc_df.empty:
        return MC_FALLBACK, GR_B_FALLBACK
    return float(mc_df["mc"].max()), float(np.average(mc_df["b"], weights=mc_df["n"]))


def smooth(cells: pd.DataFrame, lat_e: np.ndarray, lon_e: np.ndarray,
           years: float) -> np.ndarray:
    """Gauss çekirdekle yumuşatılmış yıllık olay oranı (hücre başına).

    Çekirdek hücre alanına göre normalize edilir: bir olayın tüm ızgaraya dağıttığı
    toplam katkı tam olarak 1 olay olmalıdır. Normalize edilmemiş exp() toplamı,
    çekirdeğin hücre cinsinden alanı (2*pi*sigma^2 / STEP^2 ~ 5) kadar şişirir.
    """
    sig_deg = SIGMA_KM / 111.0            # derece ~ 111 km
    norm = 2 * np.pi * sig_deg ** 2 / (STEP ** 2)
    rates = np.zeros(len(cells))
    for i, c in cells.iterrows():
        d2 = ((lat_e - c.lat_c) ** 2
              + ((lon_e - c.lon_c) * np.cos(np.radians(c.lat_c))) ** 2)
        rates[i] = np.exp(-d2 / (2 * sig_deg ** 2)).sum() / norm / years
    return rates


def main() -> None:
    mc, gr_b = load_mc_and_b()
    print(f"Mc={mc:.2f}, b={gr_b:.2f}")
    dec = read_catalog(PROC / "catalog_declustered.csv")
    full = read_catalog(PROC / "catalog_merged.csv")
    in_train = lambda d: d.time.between(TRAIN_START, TRAIN_END, inclusive="left")

    # İKİ ORAN üretilir, çünkü iki farklı soruya cevap veriyorlar:
    #
    #   rate_m5.0_yr      — yalnızca ANA ŞOKLAR. README'nin ürün tanımı budur:
    #                       "yeni bir bağımsız deprem olma olasılığı".
    #   rate_all_m5.0_yr  — ARTÇILAR DAHİL tüm olaylar. ETAS ile karşılaştırma
    #                       için zorunludur: ETAS bir dallanma süreci olarak artçı
    #                       da üretir, ana şok oranıyla kıyaslamak modeli hiç
    #                       üretmediği bir şeyle sınamak olur. Nitekim ilk CSEP
    #                       denemesinde ana şok oranı 40.6 olay beklerken gözlem
    #                       102 çıktı ve N-testi haklı olarak reddetti.
    train_main = dec[in_train(dec) & dec.is_mainshock & (dec.mw >= mc)]
    train_all = full[in_train(full) & (full.mw >= mc)]
    years = (TRAIN_END - TRAIN_START).days / 365.25
    print(f"Eğitim: {len(train_main)} ana şok, {len(train_all)} toplam olay "
          f"/ {years:.1f} yıl")

    feat = pd.read_parquet(PROC / "grid_features.parquet")
    cells = feat[["cell_id", "lat_c", "lon_c"]].drop_duplicates().reset_index(drop=True)

    # "NEREDE" ile "KAÇ TANE" ayrı kaynaklardan alınır:
    #
    #   nerede  : Mc üstü BÜTÜN olaylardan yumuşatılmış alan. Binlerce olay
    #             olduğu için mekânsal çözünürlük yüksektir.
    #   kaç tane: eğitim döneminde GÖZLENEN M>=TARGET_MW olay sayısı.
    #
    # Alternatif olan Gutenberg-Richter ekstrapolasyonu (Mc'den hedefe tek bir b
    # ile çıkmak) burada sistematik hata veriyordu: artçılar küçük olaylara
    # ağırlıklı olduğu için tam katalogda etkin b daha yüksek, dolayısıyla
    # M>=5.0 oranı %56 fazla tahmin ediliyordu (23.96 vs gözlenen 15.31/yıl).
    # Bu yöntem b-değeri belirsizliğini denklemden tamamen çıkarır.
    def calibrated(events: pd.DataFrame, label: str) -> np.ndarray:
        shape = smooth(cells, events.lat.to_numpy(), events.lon.to_numpy(), years)
        total = shape.sum()
        n_target = int((events.mw >= TARGET_MW).sum())
        if total <= 0 or n_target == 0:
            return np.zeros(len(cells))
        observed_rate = n_target / years
        print(f"  {label}: {n_target} adet M>={TARGET_MW} olay "
              f"-> {observed_rate:.2f}/yıl")
        return shape / total * observed_rate

    cells["rate_mc_yr"] = smooth(cells, train_main.lat.to_numpy(),
                                 train_main.lon.to_numpy(), years)
    cells["rate_all_mc_yr"] = smooth(cells, train_all.lat.to_numpy(),
                                     train_all.lon.to_numpy(), years)
    cells[f"rate_m{TARGET_MW}_yr"] = calibrated(train_main, "ana şok")
    cells[f"rate_all_m{TARGET_MW}_yr"] = calibrated(train_all, "artçı dahil")
    for wdays in (1, 7, 30, 90):
        cells[f"p_{wdays}d"] = 1 - np.exp(
            -cells[f"rate_m{TARGET_MW}_yr"] * wdays / 365.25)
        cells[f"p_all_{wdays}d"] = 1 - np.exp(
            -cells[f"rate_all_m{TARGET_MW}_yr"] * wdays / 365.25)

    out = PROC / "baseline_poisson.csv"
    cells.to_csv(out, index=False)
    print(f"{len(cells)} hücre -> {out}")
    top = cells.nlargest(5, "p_30d")[["lat_c", "lon_c", "p_30d"]]
    print("En yüksek 30 günlük olasılıklı 5 hücre:\n", top.to_string(index=False))


if __name__ == "__main__":
    main()
