"""Tamlık büyüklüğü (Mc) analizi — README §3.1 adım 3.

Mc, kataloğun "her depremi yakaladığı" en küçük büyüklüktür. Bunun altında kalan
olaylar eksiktir; b-değeri, olay oranları ve ETAS kalibrasyonu Mc'nin altında
hesaplanırsa **sistematik olarak yanlış** çıkar. Ağ yoğunluğu zamanla arttığı için
Mc dönem dönem düşer — bu yüzden tek bir global Mc değil, dönem bazlı Mc üretilir.

Üç yöntem (Wiemer & Wyss 2000; Woessner & Wiemer 2005):
  1. MAXC — büyüklük-frekans histogramının tepe noktası. Hızlı ama Mc'yi düşük
            tahmin etme eğiliminde; literatürde +0.2 düzeltmesiyle kullanılır.
  2. GFT  — goodness-of-fit: sentetik GR dağılımıyla uyumun %90'ı (yoksa %95)
            aştığı ilk kesme büyüklüğü.
  3. MBS  — b-değeri kararlılığı: b(Mc) eğrisinin düzleştiği ilk Mc.

Çıktı:
  data/processed/mc_by_period.csv   — dönem bazlı Mc (üç yöntem + seçilen) ve b
  data/processed/mc_analysis.png    — GR grafikleri ve b(Mc) kararlılık eğrileri
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

BIN = 0.1
# Ağ tarihçesine göre dönemler: analog / WWSSN sonrası / ulusal ağ / yoğun dijital ağ
PERIODS = [
    ("1900-1970", "1900-01-01", "1970-01-01"),
    ("1970-1990", "1970-01-01", "1990-01-01"),
    ("1990-2003", "1990-01-01", "2003-01-01"),
    ("2003-2012", "2003-01-01", "2012-01-01"),
    ("2012-2020", "2012-01-01", "2020-01-01"),
    ("2020+", "2020-01-01", "2100-01-01"),
]
NAN = float("nan")

# Mc araması bu değerin altına inmez. Kataloglar farklı eşiklerle indirildi
# (AFAD M>=2.0, KOERI/EMSC/USGS M>=3.0), dolayısıyla:
#   * Mw 3.0'ın altında yalnızca AFAD katkı verir — karışık tamlık
#   * Her indirme eşiği, dönüşüm sonrası histogramda yapay bir YIĞILMA bırakır
#     (AFAD'ın ML=2.0 kesmesi Mw~1.94'e düşer); MAXC bu sahte tepeye kilitlenir
# Bu taban kaldırılacaksa önce kataloglar aynı eşikle yeniden indirilmelidir.
MC_SEARCH_FLOOR = 3.0


def bvalue_mle(mags: np.ndarray, mc: float, bin_w: float = BIN):
    """Aki-Utsu MLE b-değeri ve Shi & Bolt (1982) standart hatası."""
    m = mags[mags >= mc - bin_w / 2]
    n = len(m)
    if n < 25:
        return NAN, NAN
    mean_m = float(m.mean())
    denom = mean_m - (mc - bin_w / 2)
    if denom <= 0:
        return NAN, NAN
    b = np.log10(np.e) / denom
    sigma = 2.30 * b**2 * np.sqrt(((m - mean_m) ** 2).sum() / (n * (n - 1)))
    return float(b), float(sigma)


def mc_maxc(mags: np.ndarray, bin_w: float = BIN) -> float:
    """Maksimum eğrilik: en çok olayın düştüğü büyüklük kutusu (+0.2 düzeltme)."""
    mags = mags[mags >= MC_SEARCH_FLOOR]
    if len(mags) == 0:
        return NAN
    edges = np.arange(np.floor(mags.min() * 10) / 10 - bin_w / 2,
                      mags.max() + bin_w, bin_w)
    counts, _ = np.histogram(mags, bins=edges)
    if counts.sum() == 0:
        return NAN
    return float(edges[counts.argmax()] + bin_w / 2 + 0.2)


def mc_gft(mags: np.ndarray, bin_w: float = BIN):
    """Goodness-of-fit testi. %90 uyumun sağlandığı ilk Mc; yoksa %95'e düşülür."""
    cands = np.arange(max(np.floor(mags.min() * 10) / 10, MC_SEARCH_FLOOR),
                      mags.max() - 0.5, bin_w)
    best95 = NAN
    for mc in cands:
        m = mags[mags >= mc - bin_w / 2]
        if len(m) < 50:
            continue
        b, _ = bvalue_mle(m, mc, bin_w)
        if np.isnan(b):
            continue
        edges = np.arange(mc - bin_w / 2, m.max() + bin_w, bin_w)
        if len(edges) < 3:
            continue
        obs, _ = np.histogram(m, bins=edges)
        centers = edges[:-1] + bin_w / 2
        a = np.log10(len(m)) + b * mc
        cum_syn = 10 ** (a - b * centers)
        syn = np.clip(-np.diff(np.append(cum_syn, 0.0)), 0, None)
        if syn.sum() <= 0 or obs.sum() == 0:
            continue
        syn = syn * obs.sum() / syn.sum()
        fit = 100 - 100 * np.abs(obs - syn).sum() / obs.sum()
        if fit >= 90:
            return float(mc), "GFT-90"
        if fit >= 95 and np.isnan(best95):
            best95 = float(mc)
    return (best95, "GFT-95") if not np.isnan(best95) else (NAN, "GFT-yok")


def mc_mbs(mags: np.ndarray, bin_w: float = BIN, n_avg: int = 5):
    """b kararlılığı: sonraki n_avg b değerinin ortalaması b(Mc)'nin hata bandına
    girdiği ilk Mc. Ayrıca çizim için (kesmeler, b, sigma) eğrisini döndürür."""
    cands = np.arange(max(np.floor(mags.min() * 10) / 10, MC_SEARCH_FLOOR),
                      mags.max() - 0.5, bin_w)
    bs, sgs = [], []
    for mc in cands:
        b, s = bvalue_mle(mags, mc, bin_w)
        bs.append(b)
        sgs.append(s)
    bs, sgs = np.array(bs), np.array(sgs)
    for i in range(len(cands) - n_avg):
        window = bs[i:i + n_avg]
        if np.isnan(window).any() or np.isnan(sgs[i]):
            continue
        if abs(float(window.mean()) - bs[i]) <= sgs[i]:
            return float(cands[i]), (cands, bs, sgs)
    return NAN, (cands, bs, sgs)


def _fmt(x: float) -> str:
    return "  n/a" if np.isnan(x) else f"{x:5.2f}"


def analyze(df: pd.DataFrame, label: str) -> dict:
    mags = df["mw"].dropna().to_numpy()
    if len(mags) < 100:
        print(f"[{label}] yetersiz olay ({len(mags)}) — atlandı")
        return {}
    m_maxc = mc_maxc(mags)
    m_gft, gft_note = mc_gft(mags)
    m_mbs, curve = mc_mbs(mags)
    # Seçim: bu KARIŞIK katalog için MAXC birincil alınır.
    #
    # Literatür (Woessner & Wiemer 2005) tek bir ağın kataloğunda MBS'i en güvenilir
    # sayar, ilk sürüm de öyle yapıyordu. Ancak burada dört kaynak ve dört ayrı
    # büyüklük tipi birleştiriliyor; b(Mc) eğrisi temiz bir plato vermiyor ve MBS
    # komşu dönemler arasında 3.0 ile 4.3 arasında zıplıyor. Mc ağ yoğunluğunun
    # özelliğidir ve on yıllar içinde YAVAŞ değişir — böyle bir zıplama gerçek bir
    # Mc değişimi değil, tahmincinin bu veride başarısız olduğunun kanıtıdır.
    # MAXC ise 5.6 -> 3.3 -> 3.3 -> 3.3 -> 3.2 -> 3.2 gibi tekdüze azalan, ağın
    # yoğunlaşmasıyla uyumlu bir seri veriyor.
    chosen = next((v for v in (m_maxc, m_gft, m_mbs) if not np.isnan(v)), NAN)
    # Mc, büyüklük kutusu ızgarasına oturmalı. np.arange kayan nokta artığı üretir
    # (3.8 yerine 3.8000000000000007); bu değer kesme olarak kullanıldığında tam
    # 3.8 olan olayları sessizce eler ve ETAS'ın kutu varsayımını bozar.
    chosen = round(chosen, 1) if not np.isnan(chosen) else chosen
    b, sigma = bvalue_mle(mags, chosen) if not np.isnan(chosen) else (NAN, NAN)
    # Yöntemler ciddi ayrışıyorsa bunu görünür kıl — sessizce birini seçme.
    spread = [v for v in (m_maxc, m_gft, m_mbs) if not np.isnan(v)]
    disagree = " [!] yöntemler ayrışıyor" if spread and max(spread) - min(spread) > 0.5 else ""
    print(f"[{label}] n={len(mags):6d}  MAXC={_fmt(m_maxc)}  GFT={_fmt(m_gft)} ({gft_note})"
          f"  MBS={_fmt(m_mbs)}  ->  Mc={_fmt(chosen)}  b={_fmt(b)}±{_fmt(sigma)}{disagree}")
    return dict(period=label, n=len(mags), mc_maxc=m_maxc, mc_gft=m_gft, mc_mbs=m_mbs,
                mc=chosen, b=b, b_sigma=sigma, _curve=curve, _mags=mags)


def main() -> None:
    src = PROC / "catalog_merged.csv"
    if not src.exists():
        print(f"! {src} yok — önce src.ingest.merge_catalogs çalıştırın.")
        return
    df = read_catalog(src)
    df = df.dropna(subset=["mw", "time"])

    results = []
    for name, a, b in PERIODS:
        window = df[(df.time >= pd.Timestamp(a, tz="UTC")) & (df.time < pd.Timestamp(b, tz="UTC"))]
        r = analyze(window, name)
        if r:
            results.append(r)
    if not results:
        return

    out = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in results])
    dst = PROC / "mc_by_period.csv"
    out.to_csv(dst, index=False)
    print(f"\n-> {dst}")
    print("Not: grid_features'taki sabit MC yerine bu dönem bazlı Mc kullanılmalı —\n"
          "     bir dönemin öznitelikleri o dönemin Mc'si üstünde hesaplanır.")
    plot(results)


def plot(results: list) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    n = len(results)
    fig, axes = plt.subplots(2, n, figsize=(3.2 * n, 7), squeeze=False)
    for i, r in enumerate(results):
        mags, mc = r["_mags"], r["mc"]
        ax = axes[0][i]
        edges = np.arange(mags.min(), mags.max() + BIN, BIN)
        counts, _ = np.histogram(mags, bins=edges)
        centers = edges[:-1] + BIN / 2
        cum = counts[::-1].cumsum()[::-1]
        ax.semilogy(centers, np.maximum(cum, 0.5), "k.", ms=3, label="kümülatif")
        ax.semilogy(centers, np.maximum(counts, 0.5), "c.", ms=2, label="kutu")
        if not np.isnan(mc) and not np.isnan(r["b"]):
            ax.axvline(mc, color="r", ls="--", lw=1, label=f"Mc={mc:.1f}")
            xs = centers[centers >= mc]
            a = np.log10(max((mags >= mc).sum(), 1)) + r["b"] * mc
            ax.semilogy(xs, 10 ** (a - r["b"] * xs), "r-", lw=1, label=f"b={r['b']:.2f}")
        ax.set_title(f"{r['period']} (n={r['n']})", fontsize=9)
        ax.set_xlabel("Mw")
        ax.legend(fontsize=6)
        if i == 0:
            ax.set_ylabel("olay sayısı")

        ax2 = axes[1][i]
        cands, bs, sgs = r["_curve"]
        ax2.errorbar(cands, bs, yerr=sgs, fmt="b.-", ms=2, lw=0.7, elinewidth=0.4)
        if not np.isnan(mc):
            ax2.axvline(mc, color="r", ls="--", lw=1)
        ax2.set_xlabel("kesme Mc")
        ax2.set_ylim(0, 2.5)
        if i == 0:
            ax2.set_ylabel("b(Mc)")
    fig.suptitle("Tamlık büyüklüğü (Mc) ve b-değeri kararlılığı — dönem bazlı", fontsize=11)
    fig.tight_layout()
    dst = PROC / "mc_analysis.png"
    fig.savefig(dst, dpi=130)
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
