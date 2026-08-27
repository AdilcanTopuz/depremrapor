"""Günlük başlangıçlı değerlendirme — ETAS'ın gerçek üstünlüğünü ölçmek için.

NEDEN GEREKLİ: aylık başlangıçlarla yapılan değerlendirmede ETAS, Poisson'u
AUC'de geçemedi. Sebebi modelde değildi — M7.8 Kahramanmaraş 6 Şubat'ta oldu ama
Şubat tahmini 1 Şubat'ta üretilmişti, ETAS bilemezdi. Test dönemindeki
pozitiflerin çoğu o bayat pencereye düşüyordu. Operasyonel OEF sistemleri günlük
ya da her büyük olaydan sonra güncellenir; bu modül o kurulumu değerlendirir.

Aynı zamanda Coulomb katmanına da en uygun koşulu sağlar: gerilim transferi
bilgisi büyük depremden hemen sonra en tazedir, aylık pencerede seyrelir.

!!! İSTATİSTİKSEL TUZAK: ÖRTÜŞEN PENCERELER !!!
Günlük başlangıç + 7 günlük pencere demek, ardışık satırların aynı depremleri
paylaşması demektir. Bir M6 olayı 7 ayrı başlangıçta pozitif üretir. Satırları
BAĞIMSIZ varsayıp bootstrap yapmak, etkin örneklem büyüklüğünü kat kat abartır
ve güven aralıklarını sahte biçimde daraltır — yani "anlamlı" sonuçlar uydurur.

Bu yüzden burada BLOK BOOTSTRAP kullanılır: satırlar değil, ardışık ZAMAN
BLOKLARI yeniden örneklenir. Blok uzunluğu pencere genişliğinden büyük seçilir,
böylece örtüşmenin yarattığı bağımlılık blok içinde kalır.

Çıktı: data/processed/daily_backtest.json + konsol raporu
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import epoch_seconds, read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
# (tahmin dizini FORECAST_DIR ile seçilir; sabit yol kaldırıldı)

LAT0, LAT1, LON0, LON1, STEP = 35.0, 43.0, 25.0, 45.0, 0.25
PROB_FLOOR = 1e-5
BLOCK_DAYS = 30          # pencere genişliğinden (7) belirgin büyük
DAY = 86400.0


# Hangi tahmin kaynağının değerlendirileceği. "etas_daily" simülasyonla üretilmiş
# günlük kurulumdur (BIRAKILDI); "etas_analytic_weekly" analitik haftalıktır.
FORECAST_DIR = "etas_daily"


def _is_analytic() -> bool:
    return "analytic" in FORECAST_DIR


def load_forecast() -> pd.DataFrame:
    """Paralel süreçlerin ürettiği tahmin parçalarını birleştirir."""
    src_dir = PROC / FORECAST_DIR
    files = sorted(src_dir.glob("shard_*.csv"))
    if not files:
        raise SystemExit(f"! {src_dir} altında tahmin yok.")
    parts = [pd.read_csv(f) for f in files if f.stat().st_size > 0]
    fc = pd.concat(parts, ignore_index=True)
    fc["ref_date"] = pd.to_datetime(fc["ref_date"], utc=True)
    return fc


def build_targets(origins: pd.DatetimeIndex, cells: np.ndarray,
                  window_days: int, target_mw: float) -> pd.DataFrame:
    """Her (hücre, başlangıç) için ileriye dönük ikili etiket.

    Izgaranın TAMAMI kullanılır — yalnızca tahminde geçen hücreler değil.
    Aksi halde modelin "olay beklemediği" hücrelerdeki gerçek depremler
    değerlendirmeden düşer ve sonuç yanlı çıkar.
    """
    cat = read_catalog(PROC / "catalog_merged.csv")
    cat = cat[(cat.mw >= target_mw) & cat.lat.between(LAT0, LAT1)
              & cat.lon.between(LON0, LON1)]
    # KANONİK fonksiyon kullanılır; elle kopyalanan formül üst sınırı kapatmaz
    # ve sınırdaki olayı ızgara dışına düşürür (bkz. config.cell_id).
    from src.config import cell_id as _cell_id

    ev_cell = _cell_id(cat.lat, cat.lon).to_numpy()
    ev_sec = epoch_seconds(cat["time"])
    org_sec = epoch_seconds(origins)

    idx = {c: i for i, c in enumerate(cells)}
    hits = np.zeros((len(origins), len(cells)), dtype=np.int8)
    for c, t in zip(ev_cell, ev_sec):
        j = idx.get(int(c))
        if j is None:
            continue
        # Olayı KAPSAYAN tüm başlangıçlar: [başlangıç, başlangıç + pencere)
        lo = np.searchsorted(org_sec, t - window_days * DAY, side="right")
        hi = np.searchsorted(org_sec, t, side="right")
        if hi > lo:
            hits[lo:hi, j] = 1

    return pd.DataFrame({
        "ref_date": np.repeat(origins.to_numpy(), len(cells)),
        "cell_id": np.tile(cells, len(origins)),
        "y": hits.ravel(),
    })


def calendar_blocks(ref_date: pd.Series, block_days: int) -> np.ndarray:
    """Satır başına blok kimliği — TAKVİM zamanından, indisten değil.

    block_days GERÇEK takvim günüdür. Örtüşen pencerelerde pencere genişliğinden
    belirgin büyük seçilmelidir; örtüşmeyen kurulumda pencere genişliği yeterlidir
    (her blok tek başlangıç içerir ve yeniden örnekleme sıradan bootstrap'a döner).
    """
    t = pd.to_datetime(ref_date, utc=True)
    delta = (t - t.min()).dt.total_seconds() / 86400.0
    return (delta // block_days).to_numpy().astype(np.int64)


def block_bootstrap(block_id: np.ndarray, y: np.ndarray, score_a: np.ndarray,
                    score_b: np.ndarray, n_boot: int = 1000, seed: int = 0):
    """AUC farkı için blok bootstrap güven aralığı.

    Bir blok seçildiğinde içindeki TÜM satırlar birlikte gelir; böylece örtüşen
    pencerelerin yarattığı bağımlılık korunur.

    BLOK KİMLİĞİ DIŞARIDAN GELİR ve TAKVİM ZAMANINDAN türetilir (bkz.
    `calendar_blocks`). Önceki sürüm blokları benzersiz gün DİZİSİNDEKİ İNDİSE
    göre kuruyordu: `uniq[i:i+30]`. Günlük başlangıçlarda 30 benzersiz gün 30
    takvim günü demekti ve doğru çalışıyordu; HAFTALIK başlangıçlarda ise 30
    benzersiz gün 210 takvim günü demek ve 202 başlangıç yalnızca 7 bloğa
    düşüyordu. Yedi bloklu bir bootstrap anlamlı aralık üretmez.

    Ayrıca eski sürüm `days` dizisini `astype("int64")` ile alıyordu; pandas'ın
    çözünürlük seçimi (ns/us) bu projede bir kez 1000 kat hataya yol açmıştı.
    Blok kimliğini takvimden türetmek o belirsizliği tamamen kaldırır.
    """
    from sklearn.metrics import roc_auc_score

    uniq = np.unique(block_id)
    blocks = [np.array([b]) for b in uniq]
    day_rows = {b: np.flatnonzero(block_id == b) for b in uniq}
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(blocks), len(blocks))
        rows = np.concatenate([np.concatenate([day_rows[d] for d in blocks[b]])
                               for b in pick])
        yy = y[rows]
        if yy.sum() == 0 or yy.sum() == len(yy):
            continue
        diffs.append(roc_auc_score(yy, score_b[rows])
                     - roc_auc_score(yy, score_a[rows]))
    diffs = np.array(diffs)
    return diffs.mean(), np.percentile(diffs, [2.5, 97.5])


def information_gain(y: np.ndarray, rate_a: np.ndarray, rate_b: np.ndarray):
    """Olay başına bilgi kazancı: (1/N) * sum[ln λ_B - ln λ_A] - (N_B - N_A)/N.

    Rhoades ve ark. (2011). Sıralamayı değil, ORANLARIN doğruluğunu ölçer —
    ETAS'ın Poisson'dan asıl farkı burada görünür.
    """
    n = int(y.sum())
    if n == 0:
        return np.nan
    a = np.maximum(rate_a, 1e-12)
    b = np.maximum(rate_b, 1e-12)
    return float(np.log(b[y == 1]).sum() - np.log(a[y == 1]).sum()) / n \
        - (b.sum() - a.sum()) / n


def build_table(window_days: int = 7, target_mw: float = 4.5,
                quiet: bool = False) -> pd.DataFrame:
    """Değerlendirme tablosunu kurar: hedefler + iki modelin oranları.

    evaluate() ve kazanç ayrıştırması (gain_breakdown) AYNI tablodan beslenmek
    zorunda; ayrı kurulan iki tablo, raporlanan toplam kazanç ile
    ayrıştırmanın toplamının uyuşmamasına yol açardı.
    """
    fc = load_forecast()
    fc = load_forecast()
    sel = fc[(fc.window_days == window_days) & (fc.target_mw == target_mw)]
    if sel.empty:
        raise SystemExit("! tahmin dosyasında bu pencere/büyüklük yok.")
    origins = pd.DatetimeIndex(sorted(fc.ref_date.unique()))
    base = pd.read_csv(PROC / "baseline_poisson.csv")
    cells = np.sort(base.cell_id.unique())

    # BÖLGE DIŞI HÜCRELERİN AYIKLANMASI.
    #
    # Poisson temel modelin ızgarası, tam sınırda (43,0000 K ya da 45,0000 D)
    # gerçekleşen olaylar yüzünden bölge kutusunun bir satır/sütun dışına taşan
    # hücreler içerebiliyor. Tahmin ızgarası [35,43] x [25,45] ile sınırlı
    # olduğundan bu hücrelerde tahmin YOKTUR; sessizce sıfır oran atanırsa,
    # oraya bir olay düştüğü gün log(0) çıkar ve bilgi kazancı tanımsız olur.
    #
    # Ölçüldü (24 Ağu 2026): 2102 hücrenin 2'si (%0,095) bölge dışında; her
    # birinde tek bir katalog olayı var, ikisi de M<4,5 ve test döneminin
    # dışında -- yani mevcut sonuçlara etkisi TAM OLARAK SIFIR. Yine de
    # ayıklanıyor ve sayısı raporlanıyor: sessiz bir sıfır, ileride patlayacak
    # bir hatadır.
    from src.models.etas_branching import NLAT, NLON

    inside = ((cells // 1000 >= 0) & (cells // 1000 < NLAT)
              & (cells % 1000 >= 0) & (cells % 1000 < NLON))
    if not inside.all() and not quiet:
        print(f"bölge dışı {int((~inside).sum())} hücre ayıklandı: "
              f"{list(cells[~inside])}")
    cells = cells[inside]
    if not quiet:
        print(f"{len(origins)} günlük başlangıç ({origins.min():%Y-%m-%d} - "
              f"{origins.max():%Y-%m-%d}), {len(cells)} hücre, "
              f"{window_days} gün, M>={target_mw}")

    tgt = build_targets(origins, cells, window_days, target_mw)
    tgt = tgt.merge(sel[["cell_id", "ref_date", "p_etas", "rate_etas"]],
                    on=["cell_id", "ref_date"], how="left")
    tgt["p_etas"] = tgt.p_etas.fillna(0.0).clip(lower=PROB_FLOOR)
    tgt["rate_etas"] = tgt.rate_etas.fillna(0.0)

    # Poisson M>=5.0 için kalibre; hedef daha düşükse Gutenberg-Richter ile ölçekle
    # Gutenberg-Richter ölçeklemesinde KALİBRE b kullanılır. b=1.0 varsayımı
    # yaygın bir kısayoldu ama bu katalogda b=1.045; fark, Poisson temel modelin
    # M4.5 oranını ~%5 kaydırır ve bilgi kazancı doğrudan bu orana karşı
    # ölçüldüğü için sonuca sızar. Operasyonel yol da (forecast_now.to_geojson)
    # aynı kalibre değeri kullanır; iki yol ayrışmamalı.
    from src.config import load_mc_and_b
    gr_b = load_mc_and_b()[1]
    scale = 10 ** (-gr_b * (target_mw - 5.0)) * window_days / 365.25
    yearly = base.set_index("cell_id")["rate_all_m5.0_yr"]
    rate_p = tgt.cell_id.map(yearly).fillna(0.0).to_numpy() * scale
    tgt["rate_pois"] = rate_p
    tgt["p_pois"] = 1 - np.exp(-rate_p)

    # MONTE CARLO ÇÖZÜNÜRLÜK TABANI — bu düzeltme olmadan olabilirlik anlamsız.
    #
    # Simülasyon, oranı N deneme üzerinden kestirir; N=500 ise 1/500 = 0.002'nin
    # altındaki oranlar SIFIR görünür. Ölçüldü: pozitif hücrelerin %48'inde
    # rate_etas = 0 çıkıyor. Her biri log-olabilirliğe log(1e-12) ~ -27.6
    # katkı verdiği için bilgi kazancı -7.44 gibi anlamsız bir değere düşüyordu.
    #
    # Düzeltme fizikseldir: ETAS'ın koşullu yoğunluğu TANIM GEREĞİ arka plan
    # oranından küçük olamaz (lambda = mu + tetikleme >= mu). Simülasyon
    # kestirimi gürültüden dolayı bunun altına düşebilir; bağımsız kestirilmiş
    # arka plan oranıyla alttan sınırlamak o garantiyi geri verir.
    # Arka plan için ANA ŞOK oranı kullanılır (artçı dahil oran değil), çünkü
    # ETAS'ın mu terimi ayrıştırılmış arka plana karşılık gelir.
    # TABAN YALNIZCA SİMÜLASYONLA ÜRETİLMİŞ TAHMİNLER İÇİN GEREKLİDİR.
    #
    # Simülasyon oranı 1/n_sim çözünürlüğünün altında sıfır görünür ve
    # log-olabilirlik tanımsız kalır. Analitik hesapta böyle bir sorun yoktur:
    # arka plan her hücrede pozitiftir, dolayısıyla hiçbir hücrede oran sıfır
    # değildir. Taban kavramı analitik yolda GEREKSİZDİR ve uygulanmaz --
    # uygulanması, sonucu keyfî bir seçime yeniden bağımlı kılardı.
    if _is_analytic():
        if not quiet:
            print("analitik kaynak: Monte Carlo tabanı uygulanmıyor (gereksiz)")
        tgt["rate_analytic"] = tgt.rate_etas
        rate_bg = np.zeros(len(tgt))
    else:
        from src.models.etas_analytic import floor_table

        floor = floor_table(pd.DatetimeIndex(sorted(tgt.ref_date.unique())),
                            window_days, target_mw, quiet=quiet)
        tgt = tgt.merge(floor, on=["cell_id", "ref_date"], how="left")
        rate_bg = tgt.rate_analytic.fillna(0.0).to_numpy()
    tgt["rate_etas_raw"] = tgt.rate_etas
    tgt["rate_etas"] = np.maximum(tgt.rate_etas.to_numpy(), rate_bg)

    if not quiet:
        print(f"{len(tgt):,} satır, {int(tgt.y.sum()):,} pozitif "
              f"(%{100*tgt.y.mean():.4f})")
        print()
    return tgt


def evaluate(window_days: int = 7, target_mw: float = 4.5) -> dict:
    from sklearn.metrics import roc_auc_score

    tgt = build_table(window_days, target_mw)
    y = tgt.y.to_numpy()
    # Örtüşmeyen kurulumda blok = pencere genişliği (her blok tek başlangıç);
    # örtüşen kurulumda pencereden belirgin büyük.
    spacing = int(pd.Series(sorted(tgt.ref_date.unique())).diff().dt.days.median() or 1)
    blk_days = window_days if spacing >= window_days else BLOCK_DAYS
    block_id = calendar_blocks(tgt.ref_date, blk_days)

    auc_p = roc_auc_score(y, tgt.p_pois.to_numpy())
    auc_e = roc_auc_score(y, tgt.p_etas.to_numpy())
    ig = information_gain(y, tgt.rate_pois.to_numpy(), tgt.rate_etas.to_numpy())
    ig_raw = information_gain(y, tgt.rate_pois.to_numpy(),
                              tgt.rate_etas_raw.to_numpy())
    n_zero = int((tgt.rate_etas_raw[y == 1] == 0).sum())
    print(f"AUC        : Poisson {auc_p:.4f}   ETAS {auc_e:.4f}   "
          f"fark {auc_e-auc_p:+.4f}")
    print(f"Bilgi kazancı (ETAS - Poisson), olay başına: {ig:+.3f}")
    print(f"  (tabansız ham değer {ig_raw:+.3f}; pozitiflerin "
          f"{n_zero}/{int(y.sum())} tanesinde simülasyon oranı sıfırdı — "
          f"Monte Carlo çözünürlük sınırı)")

    print("\nBlok bootstrap (örtüşen pencereler için zorunlu)...")
    n_blocks = len(np.unique(block_id))
    print(f"  blok uzunluğu L = {blk_days} takvim günü, {n_blocks} blok "
          f"(başlangıç aralığı {spacing} gün)")
    mean, (lo, hi) = block_bootstrap(block_id, y, tgt.p_pois.to_numpy(),
                                     tgt.p_etas.to_numpy())
    verdict = ("ETAS ANLAMLI biçimde daha iyi" if lo > 0 else
               "Poisson anlamlı biçimde daha iyi" if hi < 0 else
               "fark anlamlı değil")
    print(f"  AUC farkı {mean:+.4f}  %95 GA [{lo:+.4f}, {hi:+.4f}]  -> {verdict}")

    # origins build_table içinde kaldı; satırlardan geri sayılır. Daha önce
    # burada tanımsız değişken vardı ve 25 dakikalık bootstrap sonucu KAYDEDİLMEDEN
    # kayboldu -- bu yüzden sonuç önce yazdırılıyor, sonra kaydediliyor.
    out = {"window_days": window_days, "target_mw": target_mw,
           "n_origins": int(tgt.ref_date.nunique()), "n_rows": len(tgt),
           "n_positive": int(y.sum()), "auc_poisson": auc_p, "auc_etas": auc_e,
           "information_gain": ig, "block_days": int(blk_days),
           "n_blocks": int(n_blocks), "auc_diff_mean": float(mean),
           "auc_diff_ci": [float(lo), float(hi)]}
    dst = PROC / "daily_backtest.json"
    dst.write_text(json.dumps(out, indent=2))
    print(f"\n-> {dst}")
    return out


def compare_lgbm(window_days: int = 7, target_mw: float = 4.5,
                 seed: int = 7) -> dict:
    """Coulomb, bilgi TAZEYKEN katkı veriyor mu? — günlük çözünürlükte ablasyon.

    Aylık kurulumda hiçbir jeofizik katman katkı vermemişti. Coulomb için en
    olası açıklama, bilginin aylık pencerede seyrelmesiydi: gerilim transferi
    büyük depremden hemen sonra en anlamlıdır. Bu fonksiyon o savunmayı sınar.

    Model AYLIK referanslarla eğitilir, GÜNLÜK referanslarda tahmin yapar.
    Bu tutarsızlık değildir: öznitelikler aynı fonksiyonlarla, yalnızca farklı
    referans anlarında hesaplanır; dağılımları aynıdır. Günlük veriyle eğitmek
    (1990-2016 için ~20 milyon satır) hem gereksiz hem pratik değildir.
    """
    from sklearn.metrics import roc_auc_score
    from src.models.lgbm import CATALOG_FEATURES, LAYERS, train

    target = f"target_{window_days}d_m{str(target_mw).replace('.', '')}_all"
    daily = pd.read_parquet(PROC / "grid_features_daily.parquet")
    daily["ref_date"] = pd.to_datetime(daily["ref_date"], utc=True)
    base = pd.read_csv(PROC / "baseline_poisson.csv")[["cell_id", "rate_all_m5.0_yr"]]
    daily = daily.merge(base, on="cell_id", how="left")
    daily["poisson_rate"] = daily["rate_all_m5.0_yr"].fillna(0.0)

    cou = pd.read_csv(PROC / "coulomb_daily.csv")
    cou["ref_date"] = pd.to_datetime(cou["ref_date"], utc=True)
    daily = daily.merge(cou, on=["cell_id", "ref_date"], how="left")

    y = daily[target].astype(int).to_numpy()
    # Bu kurulum GÜNLÜK referanslarla çalışır ve pencereler örtüşür; blok
    # uzunluğu pencereden belirgin büyük seçilir (BLOCK_DAYS).
    block_id = calendar_blocks(daily.ref_date, BLOCK_DAYS)
    print(f"\nLightGBM ablasyonu (günlük): {len(daily):,} satır, "
          f"{int(y.sum()):,} pozitif, hedef {target}")

    scores = {}
    for layers, label in (((), "katalog"), (("coulomb",), "katalog+coulomb")):
        r = train(target, seed=seed, layers=layers, quiet=True)
        feats = list(CATALOG_FEATURES) + (LAYERS["coulomb"] if layers else [])
        missing = [c for c in feats if c not in daily.columns]
        if missing:
            raise SystemExit(f"! günlük tabloda eksik öznitelik: {missing}")
        scores[label] = r["model"].predict(
            daily[feats], num_iteration=r["model"].best_iteration)
        print(f"  {label:16s}: AUC {roc_auc_score(y, scores[label]):.4f}")

    mean, (lo, hi) = block_bootstrap(block_id, y, scores["katalog"],
                                     scores["katalog+coulomb"])
    verdict = ("KATKI VAR" if lo > 0 else "ZARAR" if hi < 0
               else "belirsiz — aralık sıfırı içeriyor")
    print(f"  Coulomb farkı {mean:+.4f}  %95 GA (blok bootstrap) "
          f"[{lo:+.4f}, {hi:+.4f}]  -> {verdict}")
    return {"auc_diff": float(mean), "ci": [float(lo), float(hi)]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    ap.add_argument("--source", default="etas_daily",
                    help="tahmin dizini (etas_daily / etas_analytic_weekly)")
    ap.add_argument("--lgbm", action="store_true", help="LightGBM ablasyonunu da çalıştır")
    a = ap.parse_args()
    FORECAST_DIR = a.source
    print(f"tahmin kaynağı: {FORECAST_DIR}")
    if a.lgbm:
        compare_lgbm(a.window, a.mw)
    else:
        evaluate(a.window, a.mw)
