"""CSEP değerlendirme testleri — ETAS gerçekten Poisson'u geçiyor mu?

`backtest.py` sıralama kalitesini ölçer (AUC, Molchan). Bu modül farklı ve daha
sert bir soru sorar: tahmin edilen **olay sayıları** gözlemle tutarlı mı, ve iki
model arasındaki fark **istatistiksel olarak anlamlı** mı?

Uygulanan testler (Schorlemmer et al. 2007; Zechar et al. 2010; Rhoades et al. 2011),
CSEP topluluğunun standardı olan `pycsep` paketiyle:

  N-testi : Tahmin edilen TOPLAM olay sayısı gözlemle tutarlı mı? Model çok fazla
            ya da çok az olay öngörüyorsa sıralaması iyi olsa bile kalibresizdir.
  S-testi : Olayların MEKÂNSAL dağılımı doğru mu? Toplam sayı gözleme
            normalize edilir, geriye yalnızca "nerede" sorusu kalır.
  T-testi : İki modelin olay başına bilgi kazancı farkı ve güven aralığı.
            Projenin asıl sorusu budur — güven aralığı sıfırı içeriyorsa
            "ETAS daha iyi" demek istatistiksel olarak temelsizdir.

KAYAN PENCERELERİN BİRLEŞTİRİLMESİ: elimizde aylık başlangıçlı 30 günlük
tahminler var, CSEP testleri ise sabit bir dönem için tek bir tahmin bekler.
Ardışık ve örtüşmeyen tahminlerin toplamı, birleşim dönemi için geçerli bir
tahmindir; bu yüzden hücre başına beklenen olay sayıları başlangıçlar boyunca
toplanır. Yaklaşıklık payı: ay uzunlukları 28-31 gün arasında değiştiği için
30 günlük pencereler birkaç gün boşluk/örtüşme bırakır (Şubat'ta ~2 gün örtüşme,
31 günlük aylarda 1 gün boşluk). Bu, toplam maruziyeti %1 mertebesinde etkiler
ve iki model için de AYNI olduğundan karşılaştırmayı yanlı hale getirmez.

Çıktı: data/processed/csep_results.json + konsol raporu
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

LAT0, LAT1, LON0, LON1, STEP = 35.0, 43.0, 25.0, 45.0, 0.25
TEST_START, TEST_END = "2021-01-01", "2024-01-01"
TARGET_MW = 5.0
WINDOW_DAYS = 30

# Hiçbir hücreye SIFIR oran verilmez. Olabilirlik log(oran) içerdiğinden sıfır,
# o hücrede bir deprem olduğunda -sonsuz katkı üretir ve T-testinin bilgi kazancı
# sayısını bozar. Taban, dönem boyunca beklenen toplamın hücre başına çok küçük
# bir kesridir — modelin sıralamasını değiştirmez, yalnızca sonsuzu engeller.
RATE_FLOOR = 1e-6


# Hangi tahmin kaynağının kullanıldığı; CLI ile değiştirilir.
FORECAST_DIR = "etas_monthly"


def load_monthly_forecast() -> pd.DataFrame:
    """Aylık ETAS tahminleri — parçalı dizin varsa oradan, yoksa tek dosyadan."""
    import glob

    shards = sorted(glob.glob(str(PROC / FORECAST_DIR / "shard_*.csv")))
    if shards:
        fc = pd.concat([pd.read_csv(f) for f in shards], ignore_index=True)
    else:
        fc = pd.read_csv(PROC / "etas_forecast.csv")
    fc["ref_date"] = pd.to_datetime(fc["ref_date"], utc=True)
    return fc


def _cell_origin(cell_id: int) -> tuple[float, float]:
    """cell_id -> hücrenin sol-alt köşesi (grid_features ile aynı kural)."""
    return (LAT0 + (cell_id // 1000) * STEP, LON0 + (cell_id % 1000) * STEP)


def build_region(cell_ids: np.ndarray):
    """Hücre kimliklerinden pyCSEP ızgara bölgesi kurar."""
    from csep.core.regions import CartesianGrid2D

    origins = np.array([_cell_origin(int(c))[::-1] for c in cell_ids])  # (lon, lat)
    return CartesianGrid2D.from_origins(origins, dh=STEP)


def background_rates(cell_ids: np.ndarray, origins) -> np.ndarray:
    """Hücre başına ARKA PLAN (ayrıştırılmış) beklentisi — Monte Carlo tabanı.

    ETAS'ın koşullu yoğunluğu tanım gereği lambda = mu + tetikleme, yani
    lambda >= mu. Sonlu sayıda simülasyondan kestirilen oran gürültü nedeniyle
    bunun altına (çoğu hücrede sıfıra) düşebilir; arka plan oranıyla alttan
    sınırlamak o garantiyi geri verir. Günlük değerlendirme de aynı tabanı
    kullanıyor -- iki değerlendirme yolu aynı kuralı kullanmak zorunda.

    Poisson'a taban uygulamak gereksizdir: onun oranı zaten artçı DAHİL orandır
    ve her hücrede arka plan oranından büyüktür, dolayısıyla taban etkisizdir.
    Bu yüzden taban ETAS'ı kayırmaz; yalnızca çözünürlük sınırını onarır.
    """
    from src.models.etas_analytic import floor_table

    tab = floor_table(origins, WINDOW_DAYS, TARGET_MW, quiet=True)
    total = tab.groupby("cell_id").rate_analytic.sum()
    return total.reindex(cell_ids).fillna(0.0).to_numpy()


def etas_rates(cell_ids: np.ndarray, origins: pd.DatetimeIndex) -> np.ndarray:
    """ETAS'ın test dönemi boyunca hücre başına beklediği toplam olay sayısı."""
    fc = load_monthly_forecast()
    fc["ref_date"] = pd.to_datetime(fc["ref_date"], utc=True)
    sel = fc[(fc.window_days == WINDOW_DAYS) & (fc.target_mw == TARGET_MW)
             & (fc.ref_date.isin(origins))]
    total = sel.groupby("cell_id")["rate_etas"].sum()
    return np.maximum(total.reindex(cell_ids).fillna(0.0).to_numpy(), RATE_FLOOR)


def poisson_rates(cell_ids: np.ndarray, n_origins: int) -> np.ndarray:
    """Poisson baseline'ının aynı dönem için beklediği toplam olay sayısı."""
    base = pd.read_csv(PROC / "baseline_poisson.csv").set_index("cell_id")
    # ARTÇI DAHİL oran: gözlem kataloğu da artçıları içeriyor ve ETAS onları
    # üretiyor. Ana şok oranıyla kıyaslamak baseline'ı haksız yere düşük gösterir.
    yearly = base[f"rate_all_m{TARGET_MW}_yr"].reindex(cell_ids).fillna(0.0).to_numpy()
    return np.maximum(yearly * (n_origins * WINDOW_DAYS) / 365.25, RATE_FLOOR)


def observed_catalog(region, origins: pd.DatetimeIndex):
    """Test döneminde gerçekleşen M>=TARGET_MW olayları — CSEP katalog nesnesi.

    Yalnızca tahminlerin kapsadığı pencerelere düşen olaylar alınır; aksi halde
    gözlem, tahminin öngörmediği bir zaman aralığını da içerir ve N-testi haksız
    yere başarısız olur.
    """
    from csep.core.catalogs import CSEPCatalog

    cat = read_catalog(PROC / "catalog_merged.csv")
    cat = cat[(cat.mw >= TARGET_MW)
              & cat.lat.between(LAT0, LAT1) & cat.lon.between(LON0, LON1)]
    keep = np.zeros(len(cat), dtype=bool)
    for o in origins:
        keep |= ((cat.time >= o) & (cat.time < o + pd.Timedelta(days=WINDOW_DAYS))).to_numpy()
    cat = cat[keep]

    rows = [(str(i).encode(), int(t.timestamp() * 1000), float(la), float(lo),
             float(d if pd.notna(d) else 10.0), float(m))
            for i, (t, la, lo, d, m) in enumerate(
                zip(cat.time, cat.lat, cat.lon, cat.depth_km, cat.mw))]
    arr = np.array(rows, dtype=CSEPCatalog.dtype)
    out = CSEPCatalog(data=arr)
    out.region = region
    return out


def build_forecast(rates: np.ndarray, region, name: str, start, end):
    """Hücre başına beklenen olay sayısından pyCSEP tahmin nesnesi kurar."""
    from csep.core.forecasts import GriddedForecast

    return GriddedForecast(
        data=rates.reshape(-1, 1), region=region,
        magnitudes=np.array([TARGET_MW]), name=name,
        start_time=start.to_pydatetime(), end_time=end.to_pydatetime())


def main() -> None:
    fc = load_monthly_forecast()
    origins = pd.DatetimeIndex(sorted(
        fc[(fc.window_days == WINDOW_DAYS) & (fc.target_mw == TARGET_MW)]
        ["ref_date"].unique()))
    if not len(origins):
        print("! tahmin dosyasında bu pencere/büyüklük için satır yok.")
        return

    # Izgara: Poisson baseline hangi hücreleri tanımlıyorsa onlar (aktif hücreler)
    cells = np.sort(pd.read_csv(PROC / "baseline_poisson.csv")["cell_id"].unique())
    region = build_region(cells)

    start, end = origins.min(), origins.max() + pd.Timedelta(days=WINDOW_DAYS)
    r_etas = etas_rates(cells, origins)
    r_pois = poisson_rates(cells, len(origins))
    obs = observed_catalog(region, origins)

    print(f"Dönem   : {start:%Y-%m-%d} - {end:%Y-%m-%d} ({len(origins)} başlangıç)")
    print(f"Hücre   : {len(cells)}")
    print(f"Gözlenen: {obs.event_count} olay (M>={TARGET_MW})")
    print(f"Beklenen: ETAS {r_etas.sum():.1f} | Poisson {r_pois.sum():.1f}\n")

    from csep.core import poisson_evaluations as pe

    f_etas = build_forecast(r_etas, region, "ETAS", start, end)
    f_pois = build_forecast(r_pois, region, "Poisson", start, end)

    results = {"period": [str(start), str(end)], "n_origins": len(origins),
               "observed": int(obs.event_count),
               "expected": {"ETAS": float(r_etas.sum()),
                            "Poisson": float(r_pois.sum())}}

    for name, f in (("ETAS", f_etas), ("Poisson", f_pois)):
        n = pe.number_test(f, obs)
        s = pe.spatial_test(f, obs, num_simulations=2000, seed=7)
        results[name] = {"n_test_quantile": _q(n), "s_test_quantile": _q(s)}
        print(f"[{name}] N-testi kuantil = {_fmt_q(n)}   "
              f"S-testi kuantil = {_fmt_q(s)}")

    # İKİ TABAN BİRDEN raporlanır. 1e-6 sembolik tabandır ve simülasyonda olay
    # üretmemiş her hücreyi neredeyse imkânsız ilan eder; oraya bir deprem
    # düştüğünde ETAS ağır ceza alır. Fiziksel taban (lambda >= mu) bu cezayı
    # kaldırır. Hangisinin seçildiği sonucu değiştirebileceği için ikisi de
    # verilir; seçim gizlenirse sonuç denetlenemez.
    r_etas_phys = np.maximum(r_etas, background_rates(cells, origins))
    f_etas_phys = build_forecast(r_etas_phys, region, "ETAS (fiziksel taban)",
                                 start, end)
    results["expected"]["ETAS_fiziksel_taban"] = float(r_etas_phys.sum())

    t = pe.paired_t_test(f_etas, f_pois, obs)
    lo, hi = t.test_distribution[0], t.test_distribution[1]
    ig = t.observed_statistic
    beats = lo > 0
    results["t_test"] = {"information_gain": float(ig),
                         "ci_low": float(lo), "ci_high": float(hi),
                         "etas_beats_poisson": bool(beats)}
    print(f"\nT-testi (ETAS - Poisson), olay başına bilgi kazancı:")
    print(f"  {ig:+.3f}   %95 güven aralığı [{lo:+.3f}, {hi:+.3f}]")
    print("  -> " + ("ETAS Poisson'u ANLAMLI biçimde geçiyor (aralık sıfırın üstünde)"
                     if beats else
                     "fark anlamlı DEĞİL (güven aralığı sıfırı içeriyor) — "
                     "ETAS'ın üstünlüğü bu veriyle kanıtlanamıyor"))

    t2 = pe.paired_t_test(f_etas_phys, f_pois, obs)
    lo2, hi2 = t2.test_distribution[0], t2.test_distribution[1]
    results["t_test_physical_floor"] = {
        "information_gain": float(t2.observed_statistic),
        "ci_low": float(lo2), "ci_high": float(hi2),
        "etas_beats_poisson": bool(lo2 > 0)}
    print(f"  fiziksel tabanla: {t2.observed_statistic:+.3f}   "
          f"%95 GA [{lo2:+.3f}, {hi2:+.3f}]")

    n2 = pe.number_test(f_etas_phys, obs)
    results["ETAS_fiziksel_taban"] = {"n_test_quantile": _q(n2)}
    print(f"  fiziksel tabanla N-testi kuantil = {_fmt_q(n2)}  "
          f"(beklenen {r_etas_phys.sum():.1f})")

    dst = PROC / globals().get("OUT_NAME", "csep_results.json")
    dst.write_text(json.dumps(results, indent=2))
    print(f"\n-> {dst}")
    print("\nYorum kılavuzu: N ve S testlerinde kuantil 0.025-0.975 aralığının\n"
          "dışına düşerse model o boyutta reddedilir (çok/az olay ya da yanlış\n"
          "mekânsal dağılım). T-testinde belirleyici olan güven aralığıdır,\n"
          "nokta tahmini değil.")


def _q(result):
    q = result.quantile
    return [float(x) for x in q] if isinstance(q, (list, tuple, np.ndarray)) else float(q)


def _fmt_q(result) -> str:
    q = _q(result)
    return f"[{q[0]:.3f}, {q[1]:.3f}]" if isinstance(q, list) else f"{q:.3f}"


def _cli() -> None:
    import argparse

    global FORECAST_DIR
    ap = argparse.ArgumentParser(description="CSEP testleri")
    ap.add_argument("--source", default="etas_monthly",
                    help="tahmin dizini: etas_monthly (simülasyon) veya "
                         "etas_analytic_monthly (analitik)")
    ap.add_argument("--out", default="csep_results.json")
    a = ap.parse_args()
    FORECAST_DIR = a.source
    globals()["OUT_NAME"] = a.out
    print(f"tahmin kaynağı: {FORECAST_DIR}")
    main()


if __name__ == "__main__":
    _cli()
