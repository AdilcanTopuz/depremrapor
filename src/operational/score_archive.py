"""Yayımlanmış operasyonel tahminleri gerçekleşenle karşılaştırır.

Geriye dönük testler (`src/eval/`) modeli GEÇMİŞ veriyle sınar. Bu modül farklı
bir soruyu yanıtlar: *fiilen yayımladığımız* tahminler tuttu mu?

Fark önemsiz değildir. Geriye dönük test, kodun bugünkü hâlini geçmişe uygular;
arşiv puanlaması ise o gün gerçekten üretilmiş dosyayı puanlar. Aradaki her
sapma -- katalogdaki bir düzeltme, parametre güncellemesi, bir hata düzeltmesi --
yalnızca burada görünür. CSEP'in "prospective" ile "retrospective" ayrımı tam
olarak budur ve yalnızca ilki modelin gerçek başarısının kanıtı sayılır.

PUANLAMA

* N-testi: gözlenen toplam olay sayısı, beklenenle uyumlu mu? Poisson kuyruk
  olasılığı iki yönlü verilir. Küçük p, modelin sistematik olarak az ya da çok
  tahmin ettiğini gösterir.
* Bilgi kazancı: olay başına log-olabilirlik farkı (ETAS - Poisson temel model).
  Pozitif değer, tahminin olayların DÜŞTÜĞÜ yerlere temel modelden daha çok
  olasılık verdiği anlamına gelir. Toplamı doğru tutturup yeri ıskalayan bir
  model N-testini geçer ama burada kaybeder.
* Sıra (rank): olayın düştüğü hücre, tahmin listesinde kaçıncı sıradaydı?
  Yorumlaması en kolay ölçü; tek bir olayda bile anlamlıdır.

MONTE CARLO TABANI. Tahmin dosyasında yalnızca simülasyonda olay üretmiş hücreler
bulunur. Bir olay o listede olmayan bir hücreye düşerse olasılık sıfır değildir --
500 simülasyonun çözünürlüğünün altındadır. Bu hücrelere fiziksel taban (arka plan
oranı) verilir; aksi hâlde tek bir olay log-olabilirliği -sonsuza götürür ve ölçü
anlamsızlaşır. Aynı düzeltme günlük geriye dönük testte de kullanılıyor.

Kullanım:
    python -m src.operational.score_archive
    python -m src.operational.score_archive --csv     # özet tabloyu yaz
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT_DIR = ROOT / "data" / "operational"
SUMMARY = OUT_DIR / "score_archive.csv"


def _rates(origin: pd.Timestamp, target_mw: float, days: float,
           gr_b: float) -> tuple[pd.Series, pd.Series]:
    """Poisson karşılaştırma oranı ve Monte Carlo tabanı — İKİSİ FARKLI.

    * karşılaştırma (`rate_all_m5.0_yr`): ETAS'ın rakibi olan zamandan bağımsız
      model. ETAS bir dallanma süreci olarak artçıları da ürettiği için rakibin
      de artçı DAHİL oranı olması gerekir; ayrıştırılmış bir orana karşı ölçmek
      ETAS'ı hiç üretmediği bir şeyle sınamak olurdu.

    * taban (`rate_m5.0_yr`): simülasyon çözünürlüğünün altındaki hücrelere
      verilen alt sınır. Gerekçesi ETAS'ın tanımıdır: lambda = mu + tetikleme
      olduğundan lambda >= mu. Taban ANALİTİKTİR: arka plan artı geçmişin
      doğrudan tetiklemesi, hücre x pencere üzerinde integrallenmiş. İkincil
      kuşaklar yalnızca eklediği için kesin alt sınırdır ve modelin kendi
      parametrelerinden çıkar (bkz. src.models.etas_analytic). Üç değerlendirme
      yolu da aynı tabanı kullanır.
    """
    from src.models.etas_analytic import direct_expected_counts, load_state

    base = pd.read_csv(PROC / "baseline_poisson.csv").set_index("cell_id")
    scale = 10 ** (-gr_b * (target_mw - 5.0)) * days / 365.25
    trained, cat = load_state()
    floor = direct_expected_counts(origin, days, target_mw, cat, trained)
    return base["rate_all_m5.0_yr"].astype(float) * scale, floor


def score_counts(lam: np.ndarray, base: np.ndarray, n: np.ndarray) -> dict:
    """Puanlama matematiği — dosya okumadan, saf dizilerle.

    Ayrı tutulmasının nedeni sınanabilirlik: bu fonksiyon bundan sonraki tüm
    tahminleri yargılayacak, dolayısıyla analitik olarak bilinen girdilerle
    doğrulanabilmeli (bkz. tests/test_scoring.py).

    lam  : ETAS'ın hücre başına beklediği olay sayısı
    base : Poisson temel modelin beklediği olay sayısı (aynı pencere/büyüklük)
    n    : gözlenen olay sayıları

    Bilgi kazancında log(n!) terimi düşürülür: iki modelde de aynı olduğundan
    farkta sadeleşir. Yalnızca her iki oranın da pozitif olduğu hücreler
    toplanır; sıfır oranlı bir hücrede gözlem varsa log-olabilirlik tanımsızdır
    (çağıran taraf bu yüzden fiziksel taban uygular).
    """
    from scipy.stats import poisson

    n_obs, expected = int(n.sum()), float(lam.sum())
    p_n = min(1.0, 2 * min(poisson.cdf(n_obs, expected),
                           poisson.sf(n_obs - 1, expected)))
    ok = (lam > 0) & (base > 0)
    ll_e = float((-lam[ok] + n[ok] * np.log(lam[ok])).sum())
    ll_b = float((-base[ok] + n[ok] * np.log(base[ok])).sum())
    return {"observed": n_obs, "expected": expected,
            "expected_pois": float(base.sum()), "n_test_p": p_n,
            "ll_etas": ll_e, "ll_base": ll_b,
            "info_gain": ((ll_e - ll_b) / n_obs) if n_obs else float("nan")}


def score_one(path: Path, cat: pd.DataFrame, gr_b: float) -> dict | None:
    """Tek bir tahmin dosyasını puanlar; penceresi dolmamışsa None döndürür."""
    from src.config import cell_id

    gj = json.loads(path.read_text(encoding="utf-8"))
    meta = gj["properties"]
    origin = pd.Timestamp(meta["origin"]).tz_localize(None)
    days = float(meta["window_days"])
    target = float(meta["target_magnitude"])
    mode = meta.get("mode", "live")
    end = origin + pd.Timedelta(days=days)

    # Penceresi henüz dolmamış bir tahmini puanlamak, kısmi gözlemi tam pencere
    # beklentisiyle kıyaslamak olur; sistematik olarak "az tahmin" gösterir.
    if cat.time.max() < end:
        return {"file": path.name, "origin": origin, "window_days": days,
                "target_mw": target, "mode": mode, "status": "pencere sürüyor",
                "observed": None, "expected": None}

    rate = {int(f["properties"]["cell_id"]): float(f["properties"]["expected_events"])
            for f in gj["features"]}

    cmp_rate, bg_rate = _rates(origin, target, days, gr_b)
    cmp_d, bg_d = cmp_rate.to_dict(), bg_rate.to_dict()
    cells = sorted(set(rate) | set(cmp_d))
    lam = np.array([max(rate.get(c, 0.0), bg_d.get(c, 0.0)) for c in cells])
    base = np.array([cmp_d.get(c, 0.0) for c in cells])

    obs = cat[(cat.time >= origin) & (cat.time < end) & (cat.mw >= target)].copy()
    counts = pd.Series(0, index=cells, dtype=int)
    if not obs.empty:
        obs["cell_id"] = cell_id(obs.lat, obs.lon)
        hit = obs.cell_id.value_counts()
        for c, n in hit.items():
            if c in counts.index:
                counts.loc[c] = n
    n = counts.to_numpy()
    sc = score_counts(lam, base, n)

    # Gözlenen olayların tahmin sıralamasındaki yeri.
    order = pd.Series(lam, index=cells).sort_values(ascending=False)
    ranks = [int(order.index.get_loc(c)) + 1 for c in counts[counts > 0].index]

    return {"file": path.name, "origin": origin, "window_days": days,
            "target_mw": target, "mode": mode, "status": "puanlandı",
            "observed": sc["observed"], "expected": round(sc["expected"], 3),
            "bekl_poisson": round(sc["expected_pois"], 3),
            "n_test_p": round(sc["n_test_p"], 4),
            "info_gain": (None if sc["observed"] == 0 else round(sc["info_gain"], 3)),
            "hit_ranks": ",".join(map(str, sorted(ranks))) or "-",
            "n_cells": len(order)}


def main() -> None:
    ap = argparse.ArgumentParser(description="Operasyonel tahmin arşivini puanla")
    ap.add_argument("--csv", action="store_true", help="özet tabloyu diske yaz")
    args = ap.parse_args()

    from src.config import load_mc_and_b
    from src.ingest.catalog_io import read_catalog

    files = sorted(OUT_DIR.glob("forecast_*.geojson"))
    if not files:
        raise SystemExit("arşivde tahmin yok — önce src.operational.forecast_now çalıştırın.")

    cat = read_catalog(PROC / "catalog_merged.csv")
    # Tahmin dosyalarındaki başlangıçlar (ETAS tarafı gibi) UTC-farkındalıksız
    # yazılır; katalog ise farkındalıklı. Karşılaştırma yapmadan önce tek bir
    # gösterime indirilir, aksi hâlde her kıyas TypeError verir.
    if cat.time.dt.tz is not None:
        cat = cat.assign(time=cat.time.dt.tz_convert("UTC").dt.tz_localize(None))
    _, gr_b = load_mc_and_b()
    rows = [r for r in (score_one(f, cat, gr_b) for f in files) if r]
    df = pd.DataFrame(rows).sort_values("origin")

    done = df[df.status == "puanlandı"]
    print(f"{len(df)} tahmin bulundu; {len(done)} tanesinin penceresi doldu.\n")
    show = [c for c in ("origin", "mode", "observed", "expected", "bekl_poisson",
                        "n_test_p", "info_gain", "hit_ranks", "status") if c in df]
    print(df[show].to_string(index=False))

    if not done.empty:
        tot_o, tot_e = int(done.observed.sum()), float(done.expected.sum())
        tot_p = float(done.bekl_poisson.sum())
        # İki model de aynı dönemde raporlanır: "ETAS çok tahmin ediyor"
        # ifadesi ancak rakibiyle birlikte anlamlıdır. Zamandan bağımsız model
        # de aynı yönde sapıyorsa sorun tetiklemede değil, dönemin
        # sakinliğindedir.
        print()
        print(f"TOPLAM gözlenen {tot_o}  |  ETAS {tot_e:.1f} ({tot_o/tot_e:.2f}x)"
              f"  |  Poisson {tot_p:.1f} ({tot_o/tot_p:.2f}x)")
        scored = done[done.info_gain.notna()]
        if not scored.empty:
            print(f"Ortalama bilgi kazancı (olay başına): {scored.info_gain.mean():+.3f}")
        # Tek tek pencereler az olaylıdır; birleşik N-testi çok daha güçlüdür.
        from scipy.stats import poisson
        p = min(1.0, 2 * min(poisson.cdf(tot_o, tot_e), poisson.sf(tot_o - 1, tot_e)))
        print(f"Birleşik N-testi p = {p:.4f}"
              f"{'  -> uyumlu' if p > 0.05 else '  -> SAPMA VAR'}")

    if args.csv:
        df.to_csv(SUMMARY, index=False)
        print(f"\n-> {SUMMARY}")


if __name__ == "__main__":
    main()
