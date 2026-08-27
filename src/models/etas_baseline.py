"""Baseline 2: ETAS — projenin asıl çıtası.

ETAS (Epidemic-Type Aftershock Sequence), her depremin kendi artçılarını Omori
yasasına göre tetiklediği bir dallanma (branching) sürecidir. Koşullu yoğunluk:

    lambda(t, x, y) = mu(x, y) + SUM_{t_i < t} k(m_i) * g(t - t_i) * f(x - x_i, y - y_i)

Burada mu arka plan oranı, k üretkenlik (10^(a(m-mref))), g Omori-Utsu zaman
çekirdeği, f mekânsal çekirdektir. Parametreler EM ile katalogdan kestirilir.

**Bu modelin rolü:** README'nin kuralı gereği ETAS'ı geçmeyen hiçbir ML sonucu
başarı sayılmaz. Poisson baseline yalnızca "nerede deprem olur"u bilir; ETAS
"şu an neresi tetiklenmiş durumda"yı da bilir ve kısa pencerelerde (1-7 gün)
kıyaslanamayacak kadar güçlüdür.

Uygulama: ETH Zürich'in `etas` paketi (Mizrahi et al.), CSEP uyumlu.

ÖNEMLİ: ETAS, kümelenmeyi kendisi modellediği için **ayrıştırılmamış** (declustered
olmayan) katalogla çalışır — catalog_merged.csv, catalog_declustered.csv değil.

Kullanım:
    python -m src.models.etas_baseline invert     # parametreleri kestir
"""
import argparse
import contextlib
import itertools
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from etas.inversion import RANGES as _RANGES

from src.ingest.catalog_io import read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# Izgara ile aynı bölge (grid_features: 35-43N, 25-45E)
LAT0, LAT1, LON0, LON1 = 35.0, 43.0, 25.0, 45.0
REGION = [[LAT0, LON0], [LAT0, LON1], [LAT1, LON1], [LAT1, LON0]]

AUXILIARY_START = "1990-01-01"   # kaynak olarak sayılır, hedef olarak değil
TIMEWINDOW_START = "1992-01-01"  # hem kaynak hem hedef
TRAIN_END = "2016-01-01"         # backtest'teki eğitim sonu ile aynı
DELTA_M = 0.1
MC_FALLBACK = 3.3

# İki olay, Coppersmith yüzey-altı kırık uzunluğunun bu katından uzaksa ilişkisiz
# sayılır ve mesafe matrisine girmez. Bilimsel bir sabit değil, hesaplama kısıtıdır
# ve maliyeti belirler: aynı veride 100 -> 379 sn, 30 -> 33 sn ölçüldü.
# 30 kaybettirmez: M7.8 için kırık uzunluğu ~100 km, 30 katı 3000 km — Türkiye
# kutusunun köşegeninden (~1800 km) zaten büyük. Küçük olaylarda menzil kısalır
# (M3.3 için ~15 km) ama o olayların tetikleme alanı da birkaç km mertebesindedir.
COPPERSMITH_MULTIPLIER = 30

# Kısa vadeli artçı eksikliğine (STAI) dayanıklı kalibrasyon.
#
# Büyük bir depremden hemen sonra ağ, üst üste binen dalga formları yüzünden
# küçük olayların bir kısmını kaydedemez. Ölçüldü: 6 Şubat 2023'ten sonraki ilk
# 6 saatte katalogdaki ortanca büyüklük 3.8, 30-90 gün sonra 2.3. Yani katalog
# "büyük depremler az artçı üretiyor" gibi görünür ve ETAS üretkenliği OLDUĞUNDAN
# DÜŞÜK öğrenir. Sonuç: aktif dönemlerde olay sayısı eksik tahmin edilir
# (ölçüldü: gözlenen/beklenen = 2.14x).
#
# Van der Elst (2021) yöntemi bu soruna dayanıklıdır: sabit bir Mc kesmesi yerine
# yalnızca BİR ÖNCEKİ OLAYDAN BÜYÜK olayları kullanır. Büyüklük FARKLARINA
# dayandığı için zamanla değişen tamlıktan etkilenmez.
#
# Ölçülen etki (2013-2016 penceresi): dallanma oranı 0.691 -> 0.834.
MC_MODE = "positive"        # "positive" (STAI'ye dayanıklı) ya da "fixed"

# Bu değerin altındaki dallanma oranı "tetikleme yok" demektir ve yakınsama
# başarısızlığı sayılır (artçı dizisi olan bir katalogda fiziksel karşılığı yok).
LOW_BRANCHING = 0.3

# EM yerel bir eniyileyicidir ve paket başlangıç değerlerini rastgele seçer.
# Çözüm: fiziksel olarak makul, SABİT bir başlangıç noktasından başla, sonra
# birkaç rastgele deneme daha yap ve en iyisini al.
#
# Neden salt rastgele arama değil: dejenere denemeler iki yinelemede durup hızlı
# biter, ama gerçekten ilerleyen bir EM her yinelemede 9 parametre üzerinde
# scipy eniyilemesi çalıştırır ve tek bir deneme 8+ dakika sürebilir (ölçüldü).
# Yani maliyet "iyi" denemelerin sayısıyla belirlenir; onlarca rastgele deneme
# saatler alır ve çoğu zaten çöpe gider.
RESTARTS = 5
SEED = 20260822

# Türkiye kataloğunda daha önce YAKINSAMIŞ bir çözümden alınan başlangıç noktası
# (dallanma oranı 0.837, beta'dan türeyen b = 1.255 bağımsız ölçümle uyumluydu).
# Nihai sonuç değil, yalnızca eniyileyiciye makul bir yer göstermek için başlangıç;
# EM buradan yine veriye göre hareket eder ve sonuç olabilirlikle seçilir.
ANCHOR_THETA_0 = {
    "log10_mu": -6.95, "log10_k0": -0.82, "a": 1.41, "log10_c": -2.50,
    "omega": -0.12, "log10_tau": 3.41, "log10_d": 1.46, "gamma": 0.46,
    "rho": 0.84, "log10_iota": None,
}

# `etas` paketinin optimizasyon sınırları. Bir parametrenin sınıra yapışması,
# olabilirliğin o yönde düz olduğunu — yani ters çözümün çuvalladığını — gösterir.
PARAM_ORDER = ("log10_mu", "log10_iota", "log10_k0", "a", "log10_c", "omega",
               "log10_tau", "log10_d", "gamma", "rho")
BOUNDS = {k: (float(lo), float(hi))
          for k, (lo, hi) in zip(PARAM_ORDER, _RANGES)}

PARAMS_PATH = PROC / "etas_params.json"
# Uzun süren kalibrasyonda o ana kadarki en iyi çözümün yedeği
PARTIAL_PATH = PROC / "etas_params_partial.json"
# Paralel denemelerin tek tek sonuçları
RESTART_DIR = PROC / "etas_restarts"

# Tahmin üretiminde kaynak olayların alınacağı geçmiş penceresi (yıl).
# Bkz. _calculation_at: Omori azalımı nedeniyle eski olayların katkısı ihmal
# edilebilir, buna karşılık mesafe matrisi maliyeti olay sayısının karesiyle büyür.
FORECAST_HISTORY_YEARS = 5.0

# grid_features ile AYNI olmak zorunda: hücre kimliği ve hedef tanımları oradan
# türetilir, uyuşmazlık tahminlerin sessizce yanlış hücreye/pencereye düşmesine
# yol açar.
STEP = 0.25
WINDOWS = [1, 7, 30, 90]
TARGET_MAGS = [4.5, 5.0, 5.5]

FORECAST_PATH = PROC / "etas_forecast.csv"


def load_mc() -> float:
    path = PROC / "mc_by_period.csv"
    if not path.exists():
        return MC_FALLBACK
    mc_df = pd.read_csv(path)
    mc_df = mc_df[mc_df["period"].str.slice(0, 4).astype(int) >= 1990].dropna(subset=["mc"])
    return float(mc_df["mc"].max()) if not mc_df.empty else MC_FALLBACK


def etas_catalog(mc: float) -> pd.DataFrame:
    """Birleşik katalogdan `etas` paketinin beklediği şemayı üretir.

    Beklenen kolonlar: id, latitude, longitude, time, magnitude.
    """
    from etas.inversion import round_half_up

    df = read_catalog(PROC / "catalog_merged.csv")
    df = df[(df.lat.between(LAT0, LAT1)) & (df.lon.between(LON0, LON1))]
    # Büyüklükler DELTA_M ızgarasına yuvarlanmalı: ETAS'ın olasılık yoğunluğu
    # kesikli büyüklük kutuları varsayar. Mw dönüşümü (0.953*Ml + 0.422 gibi)
    # sahte ondalık hassasiyet ürettiği için bu adım zorunlu.
    # round_half_up 3.8'i 3.8000000000000003 olarak döndürür; paketin `mag == mc`
    # tamlık kontrolü bu artık yüzünden tutmaz ("Rounding issues found"). Ek bir
    # np.round ile değer, kutu ızgarasında tam temsil edilebilir hale getirilir.
    df = df.assign(mw_binned=np.round(round_half_up(df["mw"].to_numpy(), 1), 1))
    df = df[df.mw_binned >= mc].sort_values("time").reset_index(drop=True)
    return pd.DataFrame({
        "id": np.arange(len(df)),
        "latitude": df["lat"].to_numpy(),
        "longitude": df["lon"].to_numpy(),
        # etas paketi tz-bilgisiz datetime bekler
        "time": df["time"].dt.tz_localize(None),
        "magnitude": df["mw_binned"].to_numpy(),
    })


def fit_with_restarts(calc, n_restarts: int = RESTARTS, seed: int = SEED) -> dict:
    """EM'i farklı başlangıç noktalarından defalarca çalıştırıp en iyisini seçer.

    NEDEN GEREKLİ: `etas` paketi başlangıç değerlerini parametre aralığının
    tamamından RASTGELE çeker (`create_initial_values`), üstelik tohumsuz. EM ise
    yalnızca yerel bir eniyileyicidir; kötü bir başlangıçta iki yinelemede
    "yakınsadım" deyip takılır. Gözlenen sonuç: aynı veri ve aynı kodla bir
    çalıştırmada dallanma oranı 0.837, diğerinde 0.000 çıkıyordu — fark yalnızca
    tohumsuz rastgele başlangıçtı.

    Maliyet açısından bu ucuzdur: pahalı olan `prepare()` (mesafe matrisi) bir kez
    yapılır, her yeniden başlatma yalnızca EM'i tekrarlar (saniyeler).

    Seçim ölçütü: geçerli dallanma oranına sahip adaylar arasında en düşük negatif
    log-olabilirlik. Model uyumunu ölçen doğru büyüklük budur; dallanma oranı
    yalnızca fiziksel geçerlilik filtresidir.
    """
    from etas.inversion import (branching_ratio, create_initial_values,
                                neg_log_likelihood, parameter_array2dict,
                                parameter_dict2array)

    rng = np.random.default_rng(seed)
    mc_min = calc.m_ref - calc.delta_m / 2
    best, tried = None, []

    for k in range(n_restarts):
        # 0. deneme sabit başlangıç noktasından, kalanlar rastgele.
        # create_initial_values global np.random kullanır; tekrarlanabilirlik için
        # her denemeden önce tohumu kendi üreticimizden besliyoruz.
        np.random.seed(int(rng.integers(0, 2**31 - 1)))
        try:
            calc.theta_0 = (dict(ANCHOR_THETA_0) if k == 0
                            else parameter_array2dict(create_initial_values()))
            calc.inversion_done = False
            calc.invert()
            theta = parameter_dict2array(calc.theta)
            params = {kk: float(vv) for kk, vv in calc.theta.items() if vv is not None}
            n = float(branching_ratio(theta, calc.beta))
            # neg_log_likelihood mu ve iota'yı ALMAZ; yalnızca tetikleme
            # parametrelerini bekler (paketin optimize_parameters'ı da theta[2:]
            # kullanır). Tam diziyi vermek "too many values to unpack" verir.
            nll = float(neg_log_likelihood(theta[2:], calc.pij, calc.source_events,
                                           mc_min))
        except Exception as e:  # noqa: BLE001
            print(f"  deneme {k+1:2d}/{n_restarts}: hata ({type(e).__name__}: {e})",
                  flush=True)
            continue
        valid = LOW_BRANCHING <= n < 1.0
        tried.append((nll, n, valid))
        origin = "sabit" if k == 0 else "rastgele"
        print(f"  deneme {k+1:2d}/{n_restarts} ({origin:8s}): n={n:6.3f}  "
              f"-logL={nll:14.2f}  {'geçerli' if valid else 'ELENDİ'}", flush=True)
        if valid and (best is None or nll < best["nll"]):
            best = {"params": params, "nll": nll,
                    "branching_ratio": n, "restart": k}
            # Her iyileşme anında diske yaz. Tek bir deneme saatler sürebiliyor;
            # sonraki bir denemede çökme ya da makinenin kapanması, o ana kadar
            # kazanılmış en iyi çözümü kaybettirmemeli.
            try:
                PARTIAL_PATH.write_text(json.dumps(best, indent=2))
            except Exception as e:  # noqa: BLE001
                print(f"  ! ara sonuç yazılamadı: {e}", flush=True)

    if best is None:
        raise RuntimeError(
            f"{n_restarts} denemenin hiçbiri geçerli parametre üretmedi "
            f"(dallanma oranı {LOW_BRANCHING}-1.0 aralığında olmalı). "
            "Katalog tamlığını ve pencereyi kontrol edin.")
    n_valid = sum(1 for _, _, v in tried if v)
    print(f"\n{n_valid}/{len(tried)} deneme geçerli; en iyisi #{best['restart']+1} "
          f"(-logL={best['nll']:.2f}, n={best['branching_ratio']:.3f})")
    return best


def etas_config(cat: pd.DataFrame, mc: float, timewindow_end: str,
                auxiliary_start: str = AUXILIARY_START,
                timewindow_start: str = TIMEWINDOW_START,
                for_simulation: bool = False) -> dict:
    """ETAS yapılandırmasının TEK kaynağı.

    Daha önce yapılandırma iki ayrı yerde (invert ve _build_calc) kuruluyordu.
    mc="positive" seçeneği yalnızca birine eklendiği için paralel süreçler eski
    ayarla çalıştı ve iki saatlik kalibrasyon sessizce eski sonucu üretti —
    hata vermeden, tam olarak aynı sayılarla. Yapılandırma tek yerde kalmalı.

    KALİBRASYON İLE SİMÜLASYON FARKLI TAMLIK KABULÜ KULLANIR — bu bir tutarsızlık
    değil, iki farklı sorunun cevabıdır:

      kalibrasyon : "eksik veriyle parametre kestirirken tamlıkla nasıl başa
                     çıkılır?"  -> mc="positive" (büyüklük farkları, STAI'ye
                     dayanıklı)
      simülasyon  : "hangi büyüklük aralığında olay üretilecek?"  -> fiziksel Mc

    İkisini aynı sanmak somut bir hataya yol açtı: mc="positive" kaynak
    katalogun en küçük büyüklüğünü 3.4'e çıkarıyor, simülasyon ise 3.3'ten
    yukarısını üretmeye çalışınca paket doğrulama hatası veriyor.
    """
    cfg = {
        "catalog": cat,
        "auxiliary_start": auxiliary_start,
        "timewindow_start": timewindow_start,
        "timewindow_end": timewindow_end,
        "mc": mc if for_simulation else ("positive" if MC_MODE == "positive" else mc),
        "delta_m": DELTA_M,
        "coppersmith_multiplier": COPPERSMITH_MULTIPLIER,
        "shape_coords": REGION,
    }
    if MC_MODE == "positive" and not for_simulation:
        cfg["m_ref"] = mc
    return cfg


def _build_calc(train_end: str):
    """Ters çözüm nesnesini kurar ve pahalı hazırlığı (mesafe matrisi) yapar."""
    from etas.inversion import ETASParameterCalculation

    mc = load_mc()
    cat = etas_catalog(mc)
    window = cat[(cat.time >= pd.Timestamp(AUXILIARY_START))
                 & (cat.time < pd.Timestamp(train_end))]
    config = etas_config(cat, mc, train_end)
    calc = ETASParameterCalculation(config)
    calc.prepare()
    return calc, mc, len(window)


def worker(index: int, train_end: str = TRAIN_END) -> None:
    """TEK bir başlangıç noktasından ters çözüm yapar; sonucu diske yazar.

    Her deneme ayrı bir SÜREÇ olarak çalışır. Sebep: `etas` ters çözümü tek
    çekirdeklidir (ölçüldü: 16 çekirdekli makinede ~%90 tek çekirdek kullanımı),
    ve denemeler birbirinden bağımsızdır. Sırayla çalıştırmak toplam süreyi
    denemelerin TOPLAMI yapar; paralel çalıştırmak EN YAVAŞ olanına indirir.
    Bedeli, her sürecin mesafe matrisini yeniden hazırlaması — tek bir başarılı
    ters çözümün yanında küçük kalan bir maliyet.

    index 0 sabit başlangıç noktasını kullanır, diğerleri rastgele.
    """
    import time
    from etas.inversion import (branching_ratio, create_initial_values,
                                neg_log_likelihood, parameter_array2dict,
                                parameter_dict2array)

    RESTART_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESTART_DIR / f"restart_{index:02d}.json"
    print(f"[deneme {index}] hazırlanıyor...", flush=True)
    calc, mc, n_events = _build_calc(train_end)

    np.random.seed(SEED + index)
    calc.theta_0 = (dict(ANCHOR_THETA_0) if index == 0
                    else parameter_array2dict(create_initial_values()))
    print(f"[deneme {index}] ters çözüm başlıyor "
          f"({'sabit' if index == 0 else 'rastgele'} başlangıç)", flush=True)
    t0 = time.time()
    calc.invert()
    elapsed = time.time() - t0

    params = {k: float(v) for k, v in calc.theta.items() if v is not None}
    beta = float(calc.beta)
    # ÖNCE yazdır: sonraki adımların hatası pahalı sonucu kaybettirmesin.
    print(f"[deneme {index}] parametreler ({elapsed:.0f} sn): "
          + json.dumps({k: round(v, 4) for k, v in params.items()}), flush=True)

    result = {"index": index, "params": params, "beta": beta, "mc": mc,
              "n_events": n_events, "seconds": elapsed,
              "anchor": index == 0, "seed": SEED + index}
    try:
        theta = parameter_dict2array(calc.theta)
        result["branching_ratio"] = float(branching_ratio(theta, beta))
        # neg_log_likelihood mu ve iota'yı ALMAZ (paketin optimize_parameters'ı da
        # theta[2:] kullanır); tam diziyi vermek "too many values to unpack" verir.
        result["nll"] = float(neg_log_likelihood(
            theta[2:], calc.pij, calc.source_events, calc.m_ref - calc.delta_m / 2))
    except Exception as e:  # noqa: BLE001
        print(f"[deneme {index}] skorlama hatası: {e}", flush=True)
    out_path.write_text(json.dumps(result, indent=2))
    print(f"[deneme {index}] -> {out_path}", flush=True)


def collect(train_end: str = TRAIN_END) -> dict:
    """Paralel denemelerin sonuçlarından en iyisini seçip etas_params.json yazar."""
    files = sorted(RESTART_DIR.glob("restart_*.json")) if RESTART_DIR.exists() else []
    if not files:
        raise RuntimeError(f"{RESTART_DIR} altında deneme sonucu yok.")
    cands = [json.loads(f.read_text()) for f in files]

    print(f"{len(cands)} deneme bulundu:")
    valid = []
    for c in sorted(cands, key=lambda d: d["index"]):
        n = c.get("branching_ratio")
        nll = c.get("nll")
        ok = n is not None and nll is not None and LOW_BRANCHING <= n < 1.0
        at_b = [k for k, v in c["params"].items()
                if k in BOUNDS and (abs(v - BOUNDS[k][0]) < 1e-6
                                    or abs(v - BOUNDS[k][1]) < 1e-6)]
        print(f"  #{c['index']} ({'sabit   ' if c['anchor'] else 'rastgele'}): "
              f"n={n if n is None else round(n, 3)}  -logL="
              f"{'yok' if nll is None else round(nll, 2)}  "
              f"{'geçerli' if ok else 'ELENDİ'}"
              + (f"  [sınırda: {', '.join(at_b)}]" if at_b else ""))
        if ok:
            valid.append(c)
    if not valid:
        raise RuntimeError("Hiçbir deneme geçerli parametre üretmedi "
                           f"(dallanma oranı {LOW_BRANCHING}-1.0 olmalı).")

    best = min(valid, key=lambda d: d["nll"])
    out = {
        "params": best["params"], "mc": best["mc"], "delta_m": DELTA_M,
        "beta": best["beta"], "n_events": best["n_events"],
        "neg_log_likelihood": best["nll"], "branching_ratio": best["branching_ratio"],
        "chosen_restart": best["index"], "n_restarts": len(cands),
        "from_anchor": best["anchor"], "seed": best["seed"],
        # Hangi tamlık kabulüyle kestirildiği kaydedilmeli: parametreler bu
        # varsayıma bağlıdır ve dosya tek başına yorumlanabilir olmalı.
        "mc_mode": MC_MODE,
        "auxiliary_start": AUXILIARY_START, "timewindow_start": TIMEWINDOW_START,
        "timewindow_end": train_end, "region": REGION,
    }
    PARAMS_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nSeçilen: #{best['index']} (-logL={best['nll']:.2f}, "
          f"n={best['branching_ratio']:.3f}) -> {PARAMS_PATH}")
    for k, v in best["params"].items():
        print(f"  {k:12s} = {v: .4f}")
    print(f"  beta         = {best['beta']: .4f}  (b = {best['beta']/np.log(10): .3f})")
    return out


def invert(train_end: str = TRAIN_END) -> dict:
    """ETAS parametrelerini eğitim penceresinde EM ile kestirir."""
    from etas.inversion import ETASParameterCalculation

    mc = load_mc()
    cat = etas_catalog(mc)
    window = cat[(cat.time >= pd.Timestamp(AUXILIARY_START))
                 & (cat.time < pd.Timestamp(train_end))]
    print(f"ETAS kalibrasyonu: Mc={mc:.2f}, {len(window)} olay "
          f"({AUXILIARY_START} - {train_end})")

    config = etas_config(cat, mc, train_end)
    calc = ETASParameterCalculation(config)
    calc.prepare()
    best = fit_with_restarts(calc)
    params = best["params"]
    out = {
        "params": params,
        "mc": mc,
        "delta_m": DELTA_M,
        "beta": float(calc.beta),
        "n_events": int(len(window)),
        "neg_log_likelihood": best["nll"],
        "branching_ratio": best["branching_ratio"],
        "n_restarts": RESTARTS,
        "seed": SEED,
        "mc_mode": MC_MODE,
        "auxiliary_start": AUXILIARY_START,
        "timewindow_start": TIMEWINDOW_START,
        "timewindow_end": train_end,
        "region": REGION,
    }
    PARAMS_PATH.write_text(json.dumps(out, indent=2))
    print(f"\nKestirilen parametreler -> {PARAMS_PATH}")
    for k, v in params.items():
        print(f"  {k:12s} = {v: .4f}")
    print(f"  beta         = {out['beta']: .4f}  (b = {out['beta']/np.log(10): .3f})")
    report_branching(params, out["beta"], mc)
    return out


def report_branching(params: dict, beta: float, mc: float) -> None:
    """Dallanma oranını (branching ratio) raporlar — modelin sağlık göstergesi.

    n = bir depremin doğrudan tetiklediği ortalama artçı sayısı. Türkiye gibi bir
    bölgede tipik değer 0.5-0.95'tir. İKİ YÖNDE de başarısızlık vardır:

      n >= 1    : süperkritik — dizi sönmez, kestirim güvenilmez
      n ~ 0     : "hiç tetikleme yok" — ters çözüm yakınsamamıştır. Artçı dizileri
                  olan bir katalog için bu fiziksel olarak imkânsızdır ve
                  parametrelerin sınır değerlerine yapıştığının işaretidir.

    Kriterin yalnızca üst sınırı denetlemesi gerçek bir hataydı: dejenere bir
    kestirim (n = 0.000) "normal aralık" diye raporlanıyordu.
    """
    try:
        from etas.inversion import branching_ratio, parameter_dict2array
        n = float(branching_ratio(parameter_dict2array(params), beta))
        if n >= 1:
            verdict = "BAŞARISIZ: süperkritik — dizi sönmüyor"
        elif n < LOW_BRANCHING:
            verdict = ("BAŞARISIZ: tetikleme yok — ters çözüm yakınsamadı, "
                       "parametreler sınır değerlerinde olabilir")
        else:
            verdict = "kabul edilebilir"
        print(f"  dallanma oranı n = {n:.3f}  ({verdict})")
        at_bounds = [k for k, v in params.items()
                     if k in BOUNDS and (abs(v - BOUNDS[k][0]) < 1e-6
                                         or abs(v - BOUNDS[k][1]) < 1e-6)]
        if at_bounds:
            print(f"  ! sınır değerine yapışan parametreler: {', '.join(at_bounds)}")
    except Exception as e:  # noqa: BLE001
        print(f"  ! dallanma oranı hesaplanamadı: {e}")


@contextlib.contextmanager
def deterministic_simulation(seed: int):
    """`etas` paketinin simülasyonunu yeniden üretilebilir hâle getirir.

    SORUN. Paket, `simulate_to_df` başında ve her arka plan konumu üretiminde
    ARGÜMANSIZ `np.random.seed()` çağırıyor (simulation.py:317 ve :1171).
    Argümansız çağrı, tohumu işletim sistemi entropisinden yeniden kurar ve
    dışarıdan verilen her tohumu siler. Ölçüldü: aynı başlangıç iki kez
    çalıştırıldığında farklı hücre kümesi çıkıyordu (526 ve 477 satır).

    ÇÖZÜM. Argümansız çağrılar, tohumdan türetilen SABİT bir diziden beslenir.
    Her çağrıya aynı tohumu vermek yanlış olurdu: akış her seferinde baştan
    başlar, simülasyonlar birbirinin kopyası olur ve Monte Carlo kestirimi
    çöker. Bu yüzden sayaçla ilerleyen ayrı ayrı tohumlar üretilir; kontrol
    akışı deterministik olduğu için dizi de deterministiktir.

    Açık çağrılar (argümanlı) dokunulmadan geçirilir.
    """
    real_seed = np.random.seed
    counter = itertools.count()

    def shim(value=None):
        if value is None:
            # Knuth çarpanı: ardışık sayaç değerlerini birbirinden uzak
            # tohumlara dağıtır, böylece akışlar örtüşmez.
            value = (seed + next(counter) * 2654435761) % (2 ** 32)
        real_seed(value)

    np.random.seed = shim
    try:
        real_seed(seed)
        yield
    finally:
        np.random.seed = real_seed


def simulation_seed(origin: pd.Timestamp) -> int:
    """Bir tahmin başlangıcı için deterministik tohum.

    Simülasyon tohumlanmazsa aynı komut her çalıştırmada Monte Carlo gürültüsü
    kadar farklı oran üretir; bu, yayımlanan bir tahminin sonradan yeniden
    üretilememesi demektir ve değerlendirmeyi denetlenemez hâle getirir.

    Tohum BAŞLANGIÇ TARİHİNDEN türetilir, sırasından değil. Böylece parçalama
    (sharding) düzeni değişse de her başlangıç aynı sonucu verir; sıra numarası
    kullanılsaydı parça sayısını değiştirmek tüm tahminleri değiştirirdi.
    """
    return (SEED + int(origin.strftime("%Y%m%d"))) % (2 ** 31 - 1)


def _calculation_at(origin: pd.Timestamp, cat: pd.DataFrame, trained: dict,
                    history_years: float = FORECAST_HISTORY_YEARS):
    """Verilen tahmin başlangıcı için ETAS durumunu kurar — parametreler SABİT.

    Parametreler yalnızca eğitim penceresinden gelir ve burada yeniden
    kestirilmez; bu hem ileriye bakma (look-ahead) sızıntısını engeller hem de
    her başlangıçta pahalı optimizasyonu tekrarlamayı önler. Yeniden hesaplanan
    tek şey, o ana kadarki katalogdan gelen tetikleme durumudur.

    KAYAN GEÇMİŞ PENCERESİ: kaynak olaylar tüm katalogdan değil, başlangıçtan
    önceki `history_years` yıldan alınır. Bunun iki gerekçesi var:

    * Fizik: Omori azalımı (p ~ 1) ile bir olayın 30 günlük pencereye katkısı
      zamanla 1/t gibi düşer. 5 yıl önceki bir olayın katkısı, bir ay öncekinin
      yaklaşık altmışta biridir.
    * Maliyet: mesafe matrisi olay sayısının karesiyle büyür. Tüm katalogla
      (1990'dan itibaren) her başlangıç ~50 bin olay demek ve 36 aylık başlangıç
      18+ saat sürer; 5 yıllık pencerede bu birkaç bine iner.

    Pencere, büyük bir depremin yıllarca süren artçı dizisini kapsayacak kadar
    uzun tutulmalıdır — bu yüzden varsayılan 5 yıl. Duyarlılığı `history_years`
    değiştirilerek sınanabilir.
    """
    from etas.inversion import ETASParameterCalculation

    hist_start = origin - pd.Timedelta(days=history_years * 365.25)
    cat = cat[(cat.time >= hist_start) & (cat.time < origin)]
    # ilk yıl yalnızca kaynak (auxiliary), kalanı hem kaynak hem hedef
    aux_start = hist_start.strftime("%Y-%m-%d")
    tw_start = (hist_start + pd.Timedelta(days=365.25)).strftime("%Y-%m-%d")

    # Yapılandırma kalibrasyonla AYNI fonksiyondan gelir. Tahmin, parametrelerin
    # kestirildiği tamlık kabulünü kullanmak zorundadır; ayrı kurulan iki
    # yapılandırma daha önce tam da bu hatayı üretti (biri güncellendi, diğeri
    # eski ayarla çalıştı ve iki saatlik kalibrasyon sessizce boşa gitti).
    config = etas_config(cat, trained["mc"], origin.strftime("%Y-%m-%d"),
                         auxiliary_start=aux_start, timewindow_start=tw_start,
                         for_simulation=True)
    config["beta"] = trained["beta"]
    config["fixed_parameters"] = trained["params"]
    calc = ETASParameterCalculation(config)
    calc.prepare()
    calc.invert()
    return calc


def forecast(start: str, end: str, max_window: int = max(WINDOWS),
             n_sim: int = 1000, m_threshold: float = min(TARGET_MAGS),
             m_max: float = 8.0, freq: str = "MS",
             history_years: float = FORECAST_HISTORY_YEARS,
             out_path: Path | None = None, shard: int = 0,
             n_shards: int = 1) -> pd.DataFrame:
    """Aylık başlangıçlar için ETAS tahminleri üretir.

    Her başlangıçta n_sim adet sentetik katalog simüle edilir; bu, ikincil
    tetiklemeyi (artçının artçısı) doğal olarak hesaba katar — analitik
    yaklaşımların kaçırdığı kısım budur.

    TEK SİMÜLASYONDAN TÜM ÇIKTILAR: en uzun pencere (varsayılan 90 gün) ve en
    düşük hedef büyüklük (M>=5.0) ile bir kez simüle edilir; kısa pencereler ve
    yüksek büyüklükler aynı sentetik kataloglardan süzülerek elde edilir.
    Pahalı olan kısım simülasyonun kendisi olduğu için bu, dört pencere x iki
    büyüklük = sekiz çıktıyı tek maliyete indirir.

    Her (hücre, başlangıç, pencere, büyüklük) için İKİ büyüklük kaydedilir:
      p_etas    : en az bir olay içeren simülasyonların oranı — ikili hedeflerle
                  (AUC, Molchan) karşılaştırma için
      rate_etas : simülasyon başına ortalama olay sayısı, yani beklenen olay
                  sayısı — pyCSEP N/S/T testleri ve olabilirlik için gereken
                  büyüklük budur; olasılık bunun yerine geçmez.
    """
    from etas.simulation import ETASSimulation

    trained = json.loads(PARAMS_PATH.read_text())
    cat = etas_catalog(trained["mc"])
    origins = pd.date_range(start, end, freq=freq)
    if n_shards > 1:
        # Başlangıçlar süreçlere DÖNÜŞÜMLÜ dağıtılır (dilim dilim değil):
        # 2023 başlangıçları çok daha pahalı olduğundan (dizi yüzünden katalog
        # yoğun), ardışık dilimleme iş yükünü dengesiz bırakırdı.
        origins = origins[shard::n_shards]
    print(f"{len(origins)} tahmin başlangıcı x {n_sim} simülasyon "
          f"({max_window} gün, M>={m_threshold}); pencereler {WINDOWS}, "
          f"büyüklükler {TARGET_MAGS}", flush=True)

    dst = out_path or FORECAST_PATH
    dst.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, origin in enumerate(origins, 1):
        t0 = time.time()
        calc = _calculation_at(origin, cat, trained, history_years)
        with deterministic_simulation(simulation_seed(origin)):
            sim = ETASSimulation(calc, m_max=m_max)
            sim.prepare()
            synth = sim.simulate_to_df(forecast_n_days=max_window,
                                       n_simulations=n_sim,
                                       m_threshold=m_threshold)
        block = _summarize(synth, origin, n_sim)
        rows.append(block)
        print(f"  [{i}/{len(origins)}] {origin:%Y-%m}: {len(synth)} sentetik olay "
              f"-> {len(block)} satır ({time.time()-t0:.0f} sn)", flush=True)
        # Her başlangıçtan sonra diske yaz: uzun süren bir koşuda kesinti
        # o ana kadarki tüm işi kaybettirmesin.
        if rows:
            pd.concat(rows, ignore_index=True).to_csv(dst, index=False)

    out = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    out.to_csv(dst, index=False)
    print(f"{len(out)} satır -> {dst}")
    return out


def _summarize(synth: pd.DataFrame, origin: pd.Timestamp, n_sim: int) -> pd.DataFrame:
    """Sentetik kataloglardan (hücre, pencere, büyüklük) bazlı özet üretir."""
    cols = ["cell_id", "ref_date", "window_days", "target_mw", "p_etas", "rate_etas"]
    if synth.empty:
        return pd.DataFrame(columns=cols)

    # Hücre kimliği grid_features ile AYNI kuralla üretilmeli
    # KANONİK fonksiyon; elle kopyalanan formül üst sınırı kapatmaz.
    from src.config import cell_id as _cell_id

    _cid = _cell_id(synth["latitude"], synth["longitude"])
    cell_lat = _cid // 1000
    cell_lon = _cid % 1000
    base = pd.DataFrame({
        "cell_id": (cell_lat * 1000 + cell_lon).to_numpy(),
        "sim": (synth["catalog_id"] if "catalog_id" in synth.columns else 0),
        "mw": synth["magnitude"].to_numpy(),
        "days": (pd.to_datetime(synth["time"]) - origin).dt.total_seconds() / 86400.0,
    })

    out = []
    for w in WINDOWS:
        in_window = base[base.days < w]
        for mw in TARGET_MAGS:
            sub = in_window[in_window.mw >= mw]
            if sub.empty:
                continue
            # beklenen olay sayısı = toplam olay / simülasyon sayısı
            rate = sub.groupby("cell_id").size() / n_sim
            # olasılık = en az bir olay içeren simülasyonların oranı
            prob = (sub[["cell_id", "sim"]].drop_duplicates()
                    .groupby("cell_id").size() / n_sim)
            out.append(pd.DataFrame({
                "cell_id": rate.index, "ref_date": origin,
                "window_days": w, "target_mw": mw,
                "p_etas": prob.reindex(rate.index).to_numpy(),
                "rate_etas": rate.to_numpy(),
            }))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=cols)


def main() -> None:
    ap = argparse.ArgumentParser(description="ETAS baseline")
    ap.add_argument("stage", choices=["invert", "worker", "collect", "forecast"],
                    help="çalıştırılacak aşama")
    ap.add_argument("--index", type=int, default=0, help="worker: deneme numarası")
    ap.add_argument("--train-end", default=TRAIN_END)
    ap.add_argument("--start", default="2021-01-01", help="tahmin başlangıçlarının ilki")
    ap.add_argument("--end", default="2023-12-01", help="tahmin başlangıçlarının sonuncusu")
    ap.add_argument("--window", type=int, default=max(WINDOWS),
                    help="simüle edilecek en uzun pencere (gün)")
    ap.add_argument("--n-sim", type=int, default=1000, help="başlangıç başına simülasyon")
    ap.add_argument("--freq", default="MS", help="başlangıç sıklığı (MS=aylık, D=günlük)")
    ap.add_argument("--history-years", type=float, default=FORECAST_HISTORY_YEARS)
    ap.add_argument("--out", default=None, help="çıktı dosyası")
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    args = ap.parse_args()
    if args.stage == "invert":
        invert(args.train_end)
    elif args.stage == "worker":
        worker(args.index, args.train_end)
    elif args.stage == "collect":
        collect(args.train_end)
    else:
        forecast(args.start, args.end, args.window, args.n_sim,
                 freq=args.freq, history_years=args.history_years,
                 out_path=Path(args.out) if args.out else None,
                 shard=args.shard, n_shards=args.n_shards)


if __name__ == "__main__":
    main()
