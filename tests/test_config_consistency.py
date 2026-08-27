"""Modüller arası tutarlılık testleri.

Bu projede en pahalı hatalar sessiz olanlardı: zaman birimi 1000 kat yanlış,
Mc kesmesi kataloğun %18'ini eliyor, hücre kimliği tahminleri yanlış hücreye
düşürüyor. Hiçbiri istisna fırlatmadı; hepsi "çalışan ama yanlış" idi.

Bu testler o sınıfı hedefler: bir modül sabitini değiştirir de diğerleri
uymazsa, sonuç bozulmadan ÖNCE burada patlar.

Çalıştırma:  python -m pytest tests/ -v
"""
import numpy as np
import pandas as pd

from src import config


def test_grid_constants_match_config():
    """Izgara sabitleri her modülde config ile aynı olmalı."""
    from src.features import grid_features
    from src.models import etas_baseline

    assert grid_features.STEP == config.STEP
    assert grid_features.WINDOWS == config.WINDOWS
    assert grid_features.TARGET_MAGS == config.TARGET_MAGS
    assert (grid_features.LAT0, grid_features.LON0) == (config.LAT0, config.LON0)

    # ETAS tahminleri grid_features hedefleriyle eşleşmek zorunda; ayrışırsa
    # tahminler sessizce yanlış pencereye/büyüklüğe düşer.
    assert etas_baseline.STEP == config.STEP
    assert etas_baseline.WINDOWS == config.WINDOWS
    assert etas_baseline.TARGET_MAGS == config.TARGET_MAGS


def test_cell_id_roundtrip():
    """cell_id ve cell_center birbirinin tersi olmalı."""
    lat = np.array([37.15, 40.76, 39.00])
    lon = np.array([37.03, 31.16, 35.50])
    ids = config.cell_id(pd.Series(lat), pd.Series(lon)).to_numpy()
    for i, cid in enumerate(ids):
        clat, clon = config.cell_center(int(cid))
        assert abs(clat - lat[i]) <= config.STEP
        assert abs(clon - lon[i]) <= config.STEP


def test_cell_id_matches_modules():
    """Hücre kimliği kuralı tüm modüllerde aynı sonucu vermeli."""
    lat, lon = pd.Series([38.5]), pd.Series([39.5])
    expected = int(config.cell_id(lat, lon).iloc[0])

    from src.features import grid_features
    manual = (int((38.5 - grid_features.LAT0) // grid_features.STEP) * 1000
              + int((39.5 - grid_features.LON0) // grid_features.STEP))
    assert manual == expected


def test_epoch_seconds_is_real_seconds():
    """Zaman dönüşümü GERÇEK saniye vermeli.

    Bu projedeki en pahalı hata buydu: pandas bu kataloglarda çözünürlüğü
    mikrosaniye seçiyor ve `astype("int64")/1e9` 1000 kat yanlış ölçek üretiyordu.
    30 günlük pencereler 30.000 gün olarak uygulanıyordu.
    """
    from src.ingest.catalog_io import epoch_seconds

    idx = pd.date_range("2023-02-06", periods=2, freq="D", tz="UTC")
    secs = epoch_seconds(idx)
    assert abs((secs[1] - secs[0]) - 86400.0) < 1e-6


def test_mc_is_on_magnitude_bin():
    """Mc, 0.1'lik büyüklük ızgarasına oturmalı.

    np.arange kayan nokta artığı üretiyordu (3.8 yerine 3.8000000000000007);
    bu değer kesme olarak kullanıldığında tam 3.8 olan olayları sessizce eliyor
    ve ETAS'ın kesikli büyüklük varsayımını bozuyordu.
    """
    mc = config.load_mc()
    assert abs(mc * 10 - round(mc * 10)) < 1e-9, f"Mc kutu ızgarasında değil: {mc!r}"


def test_splits_do_not_overlap():
    """Zaman bölmeleri örtüşmemeli — sızıntının en kaba biçimi."""
    bounds = [(pd.Timestamp(a), pd.Timestamp(b)) for a, b in config.SPLITS.values()]
    for (a1, b1), (a2, b2) in zip(bounds, bounds[1:]):
        assert b1 <= a2, f"bölmeler örtüşüyor: {b1} > {a2}"


def test_all_load_mc_implementations_agree():
    """Mc yükleme dört ayrı modülde uygulanmış; hepsi AYNI değeri vermeli.

    Varsayılanları farklıydı (3.7 / 3.8 / 3.3). Bu kopyalar ayrıştığında hata
    vermez — modüller sessizce farklı bir kesme kullanır ve declustering,
    öznitelikler, baseline ile ETAS birbirine uymayan kataloglar üzerinde
    çalışır. Kanonik değer src/config.load_mc'dir.
    """
    from src.features import grid_features
    from src.ingest import declustering
    from src.models import baseline_poisson, etas_baseline

    canonical = config.load_mc()
    assert grid_features.load_mc() == canonical
    assert etas_baseline.load_mc() == canonical
    assert declustering.load_mc_and_b()[0] == canonical
    assert baseline_poisson.load_mc_and_b()[0] == canonical


def test_etas_config_is_single_source():
    """ETAS yapılandırması TEK yerden kurulmalı.

    Kalibrasyon ve tahmin yolları ayrı yapılandırma sözlükleri kuruyordu.
    mc="positive" seçeneği yalnızca birine eklendiğinde paralel süreçler eski
    ayarla çalıştı ve iki saatlik kalibrasyon HATA VERMEDEN eski sonucu üretti —
    tam olarak aynı sayılarla, yani fark edilmesi ancak sonuçlara bakınca mümkün
    oldu. Bu test o ayrışmayı yakalar.
    """
    import inspect

    from src.models import etas_baseline as eb

    src = inspect.getsource(eb)
    # Yapılandırmayı tanımlayan anahtar yalnızca etas_config içinde geçmeli
    assert src.count('"coppersmith_multiplier": COPPERSMITH_MULTIPLIER') == 1, (
        "ETAS yapılandırması birden fazla yerde kuruluyor — etas_config kullanın")

    # Kalibrasyon: STAI'ye dayanıklı kip
    cfg = eb.etas_config(pd.DataFrame(), 3.3, "2016-01-01")
    if eb.MC_MODE == "positive":
        assert cfg["mc"] == "positive" and cfg["m_ref"] == 3.3
    else:
        assert cfg["mc"] == 3.3

    # Simülasyon: fiziksel Mc. Bu bir tutarsızlık DEĞİL — kalibrasyon "eksik
    # veriyle parametre nasıl kestirilir", simülasyon "hangi büyüklükler
    # üretilir" sorusuna cevap verir. İkisini aynı sanmak paket doğrulama
    # hatasına yol açtı (kaynak katalog min 3.4, simülasyon 3.3 istiyordu).
    sim_cfg = eb.etas_config(pd.DataFrame(), 3.3, "2016-01-01", for_simulation=True)
    assert sim_cfg["mc"] == 3.3


def test_gutenberg_richter_scaling_uses_calibrated_b():
    """Büyüklük ölçeklemesi hiçbir yerde b=1.0 varsayımına gömülü olmamalı.

    Poisson temel modelin oranı M>=5.0 için kalibre edilmiştir; daha düşük bir
    hedefe Gutenberg-Richter ile ölçeklenir. b=1.0 yaygın bir kısayoldur ama bu
    katalogda b=1.045 ölçüldü. Fark küçük görünür (~%5) ancak bilgi kazancı
    DOĞRUDAN bu orana karşı tanımlıdır, dolayısıyla sonuca sızar.

    Daha kötüsü: değerlendirme yolu ile operasyonel yol farklı b kullanırsa
    "normalin kaç katı" alanı, raporlanan kazançla tutarsız olur. İkisi de
    src.config.load_mc_and_b'den okumak zorunda.
    """
    import inspect
    import re

    from src.eval import daily_backtest
    from src.models import neural_intensity
    from src.operational import forecast_now

    for mod in (daily_backtest, neural_intensity, forecast_now):
        src = inspect.getsource(mod)
        hard = re.findall(r"10 \*\* \(-\s*1\.0\s*\*\s*\(", src)
        assert not hard, f"{mod.__name__}: GR ölçeklemesinde sabit b=1.0"
        assert "load_mc_and_b" in src, f"{mod.__name__}: kalibre b okunmuyor"


def test_all_evaluation_paths_use_the_analytic_floor():
    """Üç değerlendirme yolu da AYNI analitik tabanı kullanmalı.

    Ayrı taban tanımları aynı modelin farklı yollarda farklı puan almasına yol
    açar ve bu fark sessizdir. Bu projede tam olarak bu oldu: üç farklı taban
    (ayrıştırma oranı / ölçeklenmiş arka plan / yok) sırasıyla +1.07, +0.68 ve
    -8.93 bilgi kazancı verdi. Taban seçimi sonucu belirliyorsa ölçüm modelin
    değil tabanın başarısını ölçer.
    """
    import inspect

    from src.eval import csep_tests, daily_backtest
    from src.operational import score_archive

    for mod in (daily_backtest, csep_tests, score_archive):
        assert "etas_analytic" in inspect.getsource(mod), (
            f"{mod.__name__}: analitik tabanı kullanmıyor")


def test_evaluation_grid_stays_inside_forecast_grid():
    """Değerlendirme ızgarası, tahmin ızgarasının DIŞINA taşmamalı.

    Tam sınırda (43,0000 K / 45,0000 D) gerçekleşen olaylar, bölge kutusunun bir
    satır/sütun dışına düşen hücre kimliği üretiyor. O hücrelerde tahmin yoktur;
    sessizce sıfır oran atanırsa oraya bir olay düştüğü gün log(0) çıkar.

    Bu test taşmanın VARLIĞINI değil, BÜYÜKLÜĞÜNÜ sınırlar: birkaç sınır hücresi
    beklenir ve ayıklanır, ama oran büyürse ızgara tanımlarında bir ayrışma var
    demektir.
    """
    from src.models.etas_branching import NLAT, NLON

    base = pd.read_csv(config.PROC / "baseline_poisson.csv")
    cells = base.cell_id.unique()
    outside = [(int(c) // 1000 >= NLAT) or (int(c) % 1000 >= NLON) for c in cells]
    frac = sum(outside) / len(cells)
    assert frac < 0.01, (
        f"hücrelerin %{100*frac:.2f}'si tahmin ızgarasının dışında -- "
        "ızgara tanımları ayrışmış olabilir")


def test_cell_id_closes_the_upper_bound():
    """Tam üst sınırdaki olay SON hücreye girmeli, ızgara dışına değil.

    floor((x - x0) / adım) üst sınırda bir taşar; bölge filtresi kapalı aralık
    olduğu için sınırdaki olay filtreyi geçip ızgara dışına düşüyordu. Ölçülmüş
    kapsam: birleşik katalogda 10 olay.
    """
    from src.models.etas_branching import NLAT, NLON

    lat = pd.Series([config.LAT1, config.LAT0, 39.0, config.LAT1])
    lon = pd.Series([config.LON1, config.LON1, 35.0, config.LON0])
    cid = config.cell_id(lat, lon)
    for c in cid:
        i, j = int(c) // 1000, int(c) % 1000
        assert 0 <= i < NLAT, f"satır {i} ızgara dışında"
        assert 0 <= j < NLON, f"sütun {j} ızgara dışında"
    # üst köşe son hücre olmalı
    assert int(cid.iloc[0]) == (NLAT - 1) * 1000 + (NLON - 1)


def test_no_module_duplicates_the_cell_id_formula():
    """Hiçbir modül hücre kimliği formülünü ELLE kopyalamamalı.

    Üst sınır düzeltmesi kanonik fonksiyona yapıldı; elle kopyalanan formüller
    düzeltmeden habersiz kalır ve sınır olaylarını ızgara dışına düşürmeye devam
    eder. Bu, bu projede "aynı kuralın iki yerde kurulması" örüntüsünün
    (bkz. VAKA_DEFTERI V4) bir başka örneğidir.
    """
    import pathlib
    import re

    root = pathlib.Path(config.ROOT)
    pat = re.compile(r"//\s*STEP")
    suspects = []
    for f in list((root / "src").rglob("*.py")) + list((root / "scripts").glob("*.py")):
        if f.name == "config.py":
            continue
        if pat.search(f.read_text(encoding="utf-8")):
            suspects.append(str(f.relative_to(root)))
    assert not suspects, f"cell_id formülünü kopyalayan modüller: {suspects}"
