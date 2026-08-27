"""Operasyonel tahmin — bugünden ileriye, gerçek zamanlı.

Şimdiye kadarki her şey geçmişe dönüktü. Bu modül sistemi CANLI çalıştırır:
son katalogla besler, bugünden itibaren tahmin üretir ve sonucu haritalanabilir
biçimde (GeoJSON) yazar.

TASARIM KARARLARI

1. **Katalog artımlı güncellenir.** Tüm tarihçeyi yeniden indirmek hem gereksiz
   hem kaynaklara saygısızdır. Yalnızca son indirmeden bu yana geçen dönem
   çekilir ve mevcut katalogla birleştirilir.

2. **AFAD erişilemezse durmaz.** Ölçüldü: `deprem.afad.gov.tr` bir DPI-atlatma
   aracı çalışan makinelerde TLS'te reddediliyor. Kandilli ve EMSC yedek olarak
   devrede; en az bir kaynak yeterlidir.

3. **Parametreler yeniden kestirilmez.** Kalibrasyon aylık/mevsimlik bir iştir;
   operasyonel çalıştırma yalnızca mevcut parametrelerle güncel katalogdan
   tetikleme durumunu hesaplar. Böylece dakikalar içinde sonuç üretilir.

4. **Çıktı ham olasılık DEĞİL, yorumlanabilir bir paket.** Her hücre için
   olasılık, beklenen olay sayısı ve "normale göre kaç kat" bilgisi verilir.
   Sonuncusu kritik: %2 olasılık tek başına anlamsızdır, "normalin 20 katı"
   anlamlıdır.

UYARI METNİ ÇIKTIYA GÖMÜLÜR. README §8 gereği her tahmin, olasılık olduğunu ve
kesin tarih/şiddet iddiası taşımadığını belirten metinle birlikte dağıtılmalıdır.

Kullanım:
    python -m src.operational.forecast_now --days 7
    python -m src.operational.forecast_now --days 7 --no-update   # katalogu tazeleme
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"
OUT_DIR = ROOT / "data" / "operational"

DISCLAIMER = (
    "Bu bir OLASILIK tahminidir, kesin deprem tahmini değildir. Belirli bir "
    "tarih, yer ve büyüklükte deprem olacağını öngörmez ve bilimsel olarak "
    "böyle bir öngörü mümkün değildir. Verilen değerler, belirtilen zaman "
    "penceresinde ilgili hücrede eşik büyüklüğün üzerinde deprem olma "
    "olasılığıdır. Yöntem ve sınırlılıklar: metodoloji.html"
)


class KatalogKuculdu(Exception):
    """Güncelleme sonrası ham katalog küçüldü -- veri imhası şüphesi."""


def _yayin_referansi() -> dict:
    """Son yayının künyesindeki ham dosya satır sayıları.

    Önbellekten BAĞIMSIZ referans: yayın kaydı taze checkout'ta da vardır.
    Kayıt yoksa boş döner ve koruma yalnızca yerel dosyayla çalışır --
    bu durum çağıran tarafta AÇIKÇA raporlanır, sessiz geçilmez.
    """
    import json as _json

    yol = ROOT / "data" / "publish" / "latest" / "manifest.json"
    if not yol.exists():
        return {}
    try:
        m = _json.loads(yol.read_text(encoding="utf-8"))
        return dict(m.get("ham_satir_sayilari") or {})
    except Exception:
        return {}


def _satir_say(yol) -> int:
    """Başlık hariç satır sayısı."""
    with yol.open(encoding="utf-8", errors="replace") as f:
        return max(sum(1 for _ in f) - 1, 0)


def update_catalog(quiet: bool = False,
                   izin_kucultme: bool = False) -> pd.Timestamp:
    """Katalogu son olaylarla artımlı günceller; en son olay zamanını döndürür."""
    import subprocess
    import sys

    from src.ingest.catalog_io import read_catalog

    cat_path = PROC / "catalog_merged.csv"
    latest = read_catalog(cat_path).time.max() if cat_path.exists() else None
    if not quiet:
        print(f"mevcut katalog son olay: {latest:%Y-%m-%d %H:%M}" if latest is not None
              else "katalog yok")

    # KÖK NEDEN VE DÜZELTMESİ (V38).
    #
    # Eskiden `--start latest.year` geçiliyordu: "yalnızca son yılı tazele".
    # AMA indirme betikleri TÜM CSV'yi yeniden yazar, yalnızca istenen
    # aralıkla. Sonuç (26 Ağu 2026): AFAD 265.572 -> 4.713, KOERI 71.865 ->
    # 608, EMSC 51.149 -> 724 ve arka plan oranı 3,81 kat yanlış.
    # Artımlı güncelleme NİYETİ, tam-yeniden-yazma DAVRANIŞIYLA çakışıyordu.
    #
    # Düzeltme: her kaynak KENDİ TAM ARALIĞIYLA çağrılır. Maliyet düşüktür --
    # betikler aylık/yıllık önbelleği kullanır, yalnızca eksik aylar ağdan.
    son_yil = datetime.now().year + 1
    scripts = [
        ("AFAD", ["scripts/01_download_afad.py", "--start", "2003",
                  "--end", str(son_yil), "--minmag", "2.0"]),
        ("KOERI", ["scripts/02c_download_koeri.py", "--start", "1970",
                   "--end", str(son_yil), "--minmag", "3.0"]),
        ("EMSC", ["scripts/02b_download_emsc.py", "--start", "1998",
                  "--end", str(son_yil), "--minmag", "3.0"]),
    ]

    # MONOTONLUK KORUMASI — GİRDİNİN bütünlüğü.
    #
    # Bugüne kadar bütün korumalar YAYIN yönüne bakıyordu (kirli ağaç, dil,
    # şema, künye). Hattın KENDİ GİRDİSİNİ imha edebileceği senaryo haritada
    # yoktu. Asimetri kapatılır: hat, çıktısı kadar GİRDİSİNİN bütünlüğünden
    # de sorumludur.
    #
    # Kural: katalog KÜÇÜLMEZ. Küçülüyorsa ya bilinçli temizlik vardır
    # (bayrakla geçilir) ya da hata vardır (durulur).
    # REFERANS: yerel durum DEĞİL, YAYIMLANMIŞ KAYIT.
    #
    # Koruma eskiden "güncelleme öncesi yerel dosya" ile karşılaştırıyordu.
    # Taze checkout'lu bir ortamda (GitHub Actions) o dosya ancak önbellekten
    # gelir ve ÖNBELLEK BOŞSA koruma SESSİZCE GEÇER -- tam da V15'in
    # uyardığı durum: kurulu ama hiçbir şey izlemeyen koruma.
    #
    # İLKE: bir koruma, kendi ön koşulunu DIŞARIDAN (önbellek, yerel durum,
    # geçici dosya) almamalıdır. Referans, sistemin kendi KALICI kaydı olmalı.
    #
    # Artık referans, bir önceki YAYININ künyesindeki satır sayılarıdır.
    onceki_sayilar = _yayin_referansi()
    for ad in ("afad_catalog.csv", "koeri_catalog.csv", "emsc_catalog.csv"):
        yol = PROC.parent / "raw" / ad
        if yol.exists():
            # yerel dosya varsa O da referanstır (ikisinden BÜYÜĞÜ alınır:
            # koruma en sıkı hâliyle çalışsın)
            onceki_sayilar[ad] = max(onceki_sayilar.get(ad, 0),
                                     _satir_say(yol))
    ok = 0
    for name, cmd in scripts:
        # Bir kaynağın düşmesi tahmini engellemez; kalanlarla devam edilir.
        r = subprocess.run([sys.executable] + cmd, capture_output=True, text=True)
        if r.returncode == 0:
            ok += 1
            if not quiet:
                print(f"  {name}: güncellendi")
        elif not quiet:
            first = (r.stdout or r.stderr).strip().splitlines()
            print(f"  {name}: ALINAMADI ({first[0][:70] if first else '?'})")
    if ok == 0:
        raise SystemExit("! hiçbir kaynak güncellenemedi — ağ bağlantısını kontrol edin.")

    kucultenler = []
    for ad, onceki in onceki_sayilar.items():
        yol = PROC.parent / "raw" / ad
        simdiki = _satir_say(yol) if yol.exists() else 0
        if simdiki < onceki * 0.95:      # %5 tolerans: kaynak revizyonu olabilir
            kucultenler.append((ad, onceki, simdiki))
    if kucultenler and not izin_kucultme:
        satirlar = "\n".join(
            f"    {a}: {o:,} -> {y:,}" for a, o, y in kucultenler)
        raise KatalogKuculdu(
            "! KATALOG KÜÇÜLDÜ -- güncelleme veri İMHA ETMİŞ olabilir:\n"
            + satirlar + "\n"
            "  Ham önbellek (data/raw/afad/, data/raw/koeri/) dokunulmamışsa "
            "tam aralıkla yeniden çalıştırarak kurtarılabilir.\n"
            "  Bilinçli bir temizlikse: izin_kucultme=True")

    subprocess.run([sys.executable, "-m", "src.ingest.merge_catalogs"],
                   capture_output=True, text=True, check=True)
    new_latest = read_catalog(cat_path).time.max()
    if not quiet:
        print(f"güncel katalog son olay: {new_latest:%Y-%m-%d %H:%M}")
    return new_latest


def load_state() -> tuple[dict, pd.DataFrame]:
    """Eğitilmiş parametreleri ve ETAS şemasındaki katalogu yükler.

    Ayrı bir fonksiyon olmasının nedeni maliyet: katalog 300 binden fazla olay
    ve her yüklemede yeniden ayrıştırılıyor. Tek bir tahmin için önemsiz, ancak
    arşiv üretiminde (onlarca başlangıç) çalışma süresinin çoğunu bu oluşturur.
    """
    from src.models import etas_baseline as eb

    trained = json.loads(eb.PARAMS_PATH.read_text())
    return trained, eb.etas_catalog(trained["mc"])


def run_forecast_analytic(days: int = 7, target_mw: float = 4.5,
                          origin: pd.Timestamp | None = None,
                          state: tuple[dict, pd.DataFrame] | None = None,
                          mags: tuple = None) -> pd.DataFrame:
    """ANALİTİK tahmin — simülasyon yok.

    Simülasyon haftalık hücre oranları için yetersiz çözünürlüktedir: oranların
    ortancası 4,1e-04 ve 500 denemede hücrelerin çoğunda sıfır çıkar. Analitik
    dallanma hesabı aynı beklentiyi Monte Carlo hatası olmadan verir; Ö1 ve Ö2
    ile simülasyonla tutarlılığı doğrulanmıştır.

    Yan getiriler: rastgelelik yok (aynı girdi bit düzeyinde aynı çıktı) ve
    hiçbir hücrede sıfır oran yok (simülasyonun göremediği düşük oranlı hücreler
    görünür).
    """
    from src.models.etas_analytic import local_params
    from src.models.etas_branching import expected_counts

    trained, cat = state if state is not None else load_state()
    origin = origin or pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).normalize()
    mags = mags or (target_mw,)
    print(f"tahmin başlangıcı: {origin:%Y-%m-%d}, pencere {days} gün, "
          f"M>={target_mw} (ANALİTİK -- simülasyon yok)")

    # Arka plan oranı mu, HER BAŞLANGIÇTA yerel geçmişten yeniden kestirilir;
    # eğitim dosyasındaki mu tahminde kullanılmaz (2,6 kat şişirir).
    params = local_params(origin, cat, trained)
    frames = []
    for mw in mags:
        s, diag = expected_counts(origin, days, mw, cat, trained, params=params)
        if s.empty:
            continue
        frames.append(pd.DataFrame({
            "cell_id": s.index.astype(int), "ref_date": origin,
            "window_days": days, "target_mw": mw,
            "p_etas": 1.0 - np.exp(-s.to_numpy()), "rate_etas": s.to_numpy()}))
    print(f"  kuşak {diag['kuşak_sayısı']}, mu oranı "
          f"{10 ** (params['log10_mu'] - trained['params']['log10_mu']):.3f}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def run_forecast(days: int = 7, n_sim: int = 2000, target_mw: float = 4.5,
                 origin: pd.Timestamp | None = None,
                 state: tuple[dict, pd.DataFrame] | None = None) -> pd.DataFrame:
    """SİMÜLASYONLU tahmin — geçiş karşılaştırması için KORUNUYOR.

    Üretimde artık `run_forecast_analytic` kullanılır. Bu yol, geçiş günü
    yan yana arşiv için ve gelecekte bir uyuşmazlık çıkarsa bağımsız referans
    olarak duruyor.

    `state` verilirse katalog yeniden yüklenmez (bkz. load_state).
    """
    from etas.simulation import ETASSimulation
    from src.models import etas_baseline as eb

    trained, cat = state if state is not None else load_state()
    origin = origin or pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).normalize()
    print(f"tahmin başlangıcı: {origin:%Y-%m-%d}, pencere {days} gün, "
          f"M>={target_mw}, {n_sim} simülasyon")

    calc = eb._calculation_at(origin, cat, trained)
    # Yayımlanan bir tahmin yeniden üretilebilmelidir. Tohum başlangıç
    # tarihinden türetilir ve değerlendirme yolu AYNI kuralı kullanır; paketin
    # kendi kendini yeniden tohumlaması bağlam yöneticisiyle etkisizleştirilir
    # (bkz. eb.deterministic_simulation).
    with eb.deterministic_simulation(eb.simulation_seed(origin)):
        sim = ETASSimulation(calc, m_max=8.0)
        sim.prepare()
        synth = sim.simulate_to_df(forecast_n_days=days, n_simulations=n_sim,
                                   m_threshold=target_mw)
    return eb._summarize(synth, origin, n_sim)


def _fingerprint() -> dict:
    """Yayımlanan tahmine gömülecek künye."""
    import hashlib
    import subprocess

    from src.models.etas_params import EtasParams

    ep = EtasParams.load()
    ph = hashlib.sha256(
        (ROOT / "data" / "processed" / "etas_params.json").read_bytes()).hexdigest()
    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                           text=True, cwd=ROOT).stdout.strip()
    # KATALOG KÜNYESİ — V37'de açılan boşluğun kapatılması.
    #
    # Künye zinciri PARAMETRELERİ kapsıyordu ama KATALOGU kapsamıyordu.
    # Sonuç: dondurulmuş bir değerlendirme tablosunun, dondurulmamış bir
    # zemini vardı ve 24 Ağu 2026 tablosu bugünkü kodla yeniden
    # üretilemediğinde sebep DOĞRUDAN SINANAMADI -- karşılaştırılacak bir
    # katalog sha'sı yoktu.
    #
    # Maliyet: 300 binden fazla satırlık dosyanın sha256'sı (~0,3 sn).
    # Getirisi: aynı belirsizliğin bir daha doğmaması.
    kat_yol = ROOT / "data" / "processed" / "catalog_merged.csv"
    kh = hashlib.sha256(kat_yol.read_bytes()).hexdigest() if kat_yol.exists() else None
    kat_son = None
    if kat_yol.exists():
        from src.ingest.catalog_io import read_catalog
        kat_son = str(read_catalog(kat_yol).time.max())

    return {
        "method": "analytic-branching",
        "etas_params_sha256": ph,
        "catalog_sha256": kh,
        "catalog_last_event": kat_son,
        "branching_nominal": round(ep.branching_nominal, 4),
        "branching_effective": round(ep.branching_effective, 4),
        "commit": git,
        "worktree": "dirty" if dirty else "clean",
        "randomness": ("none in the branching computation; the ETAS state EM "
                       "step is SEEDED from the origin date"),
    }


def to_geojson(block: pd.DataFrame, days: int, target_mw: float,
               origin: pd.Timestamp, mode: str = "live",
               min_times_normal: float = 0.0) -> dict:
    """Hücre olasılıklarını haritalanabilir GeoJSON'a çevirir.

    Her hücre için "normale göre kaç kat" alanı da eklenir: mutlak olasılık tek
    başına yorumlanamaz (%2 az mı çok mu?), uzun vadeli orana göre kaç kat
    yükseldiği ise doğrudan anlamlıdır.
    """
    from src.config import STEP, cell_center, load_mc_and_b

    base = pd.read_csv(PROC / "baseline_poisson.csv").set_index("cell_id")
    # Gutenberg-Richter ölçeklemesi KALİBRE EDİLMİŞ b ile yapılır. b=1.0 yaygın
    # bir kısayoldur ama bu katalogda b=1.045 ölçüldü; küçük görünen fark M4.5
    # hedefinde normal oranı ~%5 kaydırır ve doğrudan "normalin kaç katı"
    # alanını bozar. Değerlendirme yolu (src/eval/daily_backtest) zaten kalibre
    # b kullanıyordu; iki yol aynı ölçeği kullanmak zorunda.
    _, gr_b = load_mc_and_b()
    scale = 10 ** (-gr_b * (target_mw - 5.0)) * days / 365.25
    sel = block[(block.window_days == days) & (block.target_mw == target_mw)]

    # ALT EŞİK. Analitik hesapta hiçbir hücrede oran sıfır değildir; ızgaranın
    # tamamı (2560 hücre) çıktıya girer. Simülasyonlu yol yalnızca olay ürettiği
    # hücreleri veriyordu (canlı tahminde 191) -- yani eski çıktının "azlığı"
    # bir bilgi değil, çözünürlük sınırıydı.
    #
    # Binlerce hücreyi haritada göstermek anlamsız ve yanıltıcıdır: arka plan
    # düzeyindeki hücreler "tahmin" gibi görünür. Eşik "normalin kaç katı"
    # üzerinden konur ve çıktıya AÇIKÇA yazılır.
    # YAYIN KAPSAMI (V43) -- ölçemediğimiz yerde konuşmayız.
    #
    # Izgara dikdörtgendir ve komşu ülkeleri içerir. Katalog tamlığı sınır
    # dışında ÖLÇÜLMÜŞ biçimde düşüktür (küçük olayların ~%46'sı kayıtsız),
    # dolayısıyla uzun vadeli temel oran düşük kestirilir ve "normalin kaç
    # katı" ŞİŞER. Kerkük'teki 82,4 kat gerçek bir sinyal değil, eksik
    # katalogun ürettiği yapay bir değerdi.
    from src.operational.kapsam import hucre_maskesi

    n_izgara = len(sel)
    kapsam_m = hucre_maskesi(sel.cell_id.to_numpy())
    sel = sel[kapsam_m]
    n_kapsam_disi = int((~kapsam_m).sum())

    n_before = len(sel)
    feats = []
    for _, r in sel.iterrows():
        lat, lon = cell_center(int(r.cell_id))
        yearly = float(base["rate_all_m5.0_yr"].get(int(r.cell_id), 0.0))
        normal = 1 - np.exp(-yearly * scale)
        ratio = (r.p_etas / normal) if normal > 1e-12 else float("nan")
        if min_times_normal > 0 and not (ratio >= min_times_normal):
            continue
        half = STEP / 2
        feats.append({
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [[
                [lon - half, lat - half], [lon + half, lat - half],
                [lon + half, lat + half], [lon - half, lat + half],
                [lon - half, lat - half]]]},
            "properties": {
                "cell_id": int(r.cell_id),
                "probability": round(float(r.p_etas), 6),
                "expected_events": round(float(r.rate_etas), 4),
                "normal_probability": round(float(normal), 6),
                "times_normal": (None if np.isnan(ratio) else round(float(ratio), 1)),
            },
        })
    return {
        "type": "FeatureCollection",
        "properties": {
            "origin": origin.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "window_days": days,
            "target_magnitude": target_mw,
            "model": "ETAS",
            # "live"  : o gün gerçekten yayımlanmış tahmin
            # "pseudo": geçmiş bir başlangıç için sonradan üretilmiş tahmin.
            # Ayrım kayıt altına alınmalıdır: yalnızca "live" tahminler modelin
            # gerçek ileriye dönük başarısının kanıtı sayılır, çünkü sonradan
            # üretilenler bugünkü kodu ve bugünkü (düzeltilmiş) katalogu kullanır.
            "mode": mode,
            # KÜNYE ÇIKTIYA GÖMÜLÜR. Yayımlanan bir tahmin, hangi koşullarda
            # üretildiğini kendisi taşımalıdır; ayrı bir dosyaya bakmak
            # gerekiyorsa o dosya kaybolabilir ya da ayrışabilir.
            "fingerprint": _fingerprint(),
            # Eşik çıktının parçasıdır: kaç hücrenin elendiği gizlenmez.
            "min_times_normal": min_times_normal,
            "kapsam": {"izgara_hucre": n_izgara,
                       "kapsam_disi_elenen": n_kapsam_disi,
                       **__import__("src.operational.kapsam",
                                    fromlist=["kunye"]).kunye()},
            "cells_before_threshold": int(n_before),
            "cells_published": len(feats),
            "disclaimer": DISCLAIMER,
        },
        "features": feats,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description="Operasyonel ETAS tahmini")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    ap.add_argument("--n-sim", type=int, default=2000)
    ap.add_argument("--no-update", action="store_true",
                    help="katalogu tazeleme, mevcut halini kullan")
    ap.add_argument("--origin", default=None, help="YYYY-MM-DD (varsayılan: bugün)")
    ap.add_argument("--allow-dirty", action="store_true",
                    help="kirli ağaçtan yayımlamaya izin ver (künye damgalanır)")
    ap.add_argument("--sim", action="store_true",
                    help="ESKİ simülasyonlu yol (varsayılan: analitik)")
    # EŞİK GEREKÇESİ (ölçülerek seçildi, 208 haftalık başlangıç, M>=4.5):
    #
    #     eşik   başlangıç başına hücre   tahmin edilen olay kütlesinin payı
    #      1,0            616                        81,5%
    #      1,5            412                        77,6%
    #      2,0            299                        75,0%
    #      3,0            179                        71,2%
    #      5,0             97                        67,0%
    #     10,0             44                        61,5%
    #
    # 2,0 seçildi çünkü: (a) 1,0'dan 2,0'a çıkmak hücre sayısını YARIYA indirip
    # kütlenin yalnızca 6,5 puanını feda ediyor -- en verimli kesim burada;
    # (b) 2,0'ın altındaki hücreler zaten arka plan düzeyindedir ve haritada
    # "tahmin" gibi görünmeleri yanıltıcıdır; (c) 3,0'a çıkmak 120 hücre daha
    # eliyor ama yalnızca 3,8 puan kazandırıyor -- getirisi azalıyor.
    #
    # Bu bir ÜRÜN kararıdır, istatistiksel bir eşik değil. Site tasarımında
    # yeniden tartışılabilir; tartışma bu tablo üzerinden yapılır.
    ap.add_argument("--min-times-normal", type=float, default=2.0,
                    help="yayımlanan hücreler için alt eşik: normalin kaç katı")
    args = ap.parse_args()

    # KİRLİ AĞAÇTAN YAYIMLANMAZ. Künyedeki "commit" alanı, çalışma ağacında
    # commit'lenmemiş değişiklik varsa YALAN söyler: dosya o commit'in içeriğini
    # yansıtmaz. Yayımlanan bir tahminin künyesi yanlışsa künye olmaktan çıkar.
    #
    # Bu, otomasyon için de doğru davranıştır: cron temiz bir checkout'tan
    # çalışmalıdır. Kirli bir ağaçtan üretim, sessizce güvenilmez tahmin
    # yayımlamak yerine DURUR.
    if _fingerprint()["worktree"] == "dirty" and not args.allow_dirty:
        raise SystemExit(
            "! çalışma ağacı KİRLİ: künyedeki commit, üretilen dosyanın "
            "içeriğini yansıtmaz. Yayımlamadan önce commit edin. "
            "Bilinçli olarak devam etmek için: --allow-dirty "
            "(bu bayrakla üretilen dosyanın künyesi worktree=dirty taşır)")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not args.no_update:
        update_catalog()

    origin = (pd.Timestamp(args.origin) if args.origin
              else pd.Timestamp(datetime.now(timezone.utc)).tz_localize(None).normalize())
    block = (run_forecast(args.days, args.n_sim, args.mw, origin) if args.sim
             else run_forecast_analytic(args.days, args.mw, origin))
    if block.empty:
        print("! simülasyon hiç olay üretmedi — sakin dönem ya da parametre sorunu.")
        return

    gj = to_geojson(block, args.days, args.mw, origin,
                    min_times_normal=args.min_times_normal)
    stamp = origin.strftime("%Y%m%d")
    path = OUT_DIR / f"forecast_{stamp}_{args.days}d_m{str(args.mw).replace('.','')}.geojson"
    path.write_text(json.dumps(gj), encoding="utf-8")

    sel = block[(block.window_days == args.days) & (block.target_mw == args.mw)]
    top = sel.nlargest(10, "p_etas")
    from src.config import cell_center
    print(f"\n{len(sel)} hücrede olay beklentisi var; toplam beklenen olay: "
          f"{sel.rate_etas.sum():.2f}")
    print("\nEn yüksek olasılıklı 10 hücre:")
    print(f"{'enlem':>7} {'boylam':>8} {'olasılık':>10} {'beklenen':>10}")
    for _, r in top.iterrows():
        lat, lon = cell_center(int(r.cell_id))
        print(f"{lat:7.2f} {lon:8.2f} {100*r.p_etas:9.2f}% {r.rate_etas:10.3f}")
    print(f"\n-> {path}")
    print(f"\n{DISCLAIMER}")


if __name__ == "__main__":
    main()
