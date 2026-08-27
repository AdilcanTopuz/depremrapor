"""Zaliapin & Ben-Zion (2013) nearest-neighbor declustering.

Her olay için "en yakın komşu" (zaman-mekân-büyüklük metriğinde) mesafesi hesaplanır;
mesafe dağılımı iki moda ayrılır: kümelenmiş (artçı/öncü) ve bağımsız (ana şok/arka plan).
Eşik, log-mesafe histogramındaki iki Gauss karışımından veya sabit eşikten (log10(eta0)
~ -5 civarı tipik) alınır.

Çıktı: data/processed/catalog_declustered.csv  (is_mainshock kolonu eklenmiş tam katalog)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import epoch_seconds, read_catalog

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

FRACTAL_DIM = 1.6      # deprem episantr dağılımı fraktal boyutu (literatür tipik)
ETA0_FALLBACK = -5.0   # GMM ayrımı başarısız olursa kullanılacak literatür eşiği
MODEL_START = "1990-01-01"  # öznitelik/model döneminin başı — Mc bu dönemden seçilir


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(np.clip(a, 0, 1)))


DEG_KM = 111.19492664455873   # 1 derece enlem, ortalama Dünya yarıçapında


def nearest_neighbor_distances(df: pd.DataFrame, b_value: float):
    """Her olay j için en yakın komşu mesafesi eta_j ve o komşunun (ebeveynin) indeksi.

    Maliyet O(n^2). n burada on binlerce olduğu için iç döngüdeki her trigonometrik
    işlem doğrudan saatlere mal olur; bu yüzden iki şey yapılır:

    1. Olay başına sabit olan çarpanlar (10^(-b*m), cos(enlem)) döngü ÖNCESİNDE
       hesaplanır.
    2. Mesafe için haversine yerine eşdikdörtgen (equirectangular) yaklaşımı
       kullanılır: çiftin ortalama enlemindeki cos ile boylam farkı ölçeklenir.
       Türkiye kutusunda (35-43K) bu yaklaşımın hatası birkaç yüz km'ye kadar
       binde birkaç mertebesindedir — declustering'in kendisi zaten fraktal boyut
       gibi deneysel bir çekirdeğe dayandığı için bu fazlasıyla yeterli.
       Doğruluk `validate_distance()` ile ölçülebilir.
    """
    t_yr = epoch_seconds(df["time"]) / (365.25 * 24 * 3600)
    lat, lon = df["lat"].to_numpy(), df["lon"].to_numpy()
    mw = df["mw"].to_numpy()
    n = len(df)

    cos_lat = np.cos(np.radians(lat))
    mag_factor = 10.0 ** (-b_value * mw)     # olay başına sabit
    eta = np.full(n, np.inf)
    parent = np.full(n, -1, dtype=int)

    for j in range(1, n):
        dt = t_yr[j] - t_yr[:j]
        valid = np.flatnonzero(dt > 0)
        if not len(valid):
            continue
        dy = lat[valid] - lat[j]
        dx = (lon[valid] - lon[j]) * (0.5 * (cos_lat[valid] + cos_lat[j]))
        r = np.maximum(np.sqrt(dx * dx + dy * dy) * DEG_KM, 0.1)
        e = dt[valid] * (r ** FRACTAL_DIM) * mag_factor[valid]
        k = int(e.argmin())
        eta[j] = e[k]
        parent[j] = int(valid[k])
    return eta, parent


def validate_distance(lat: np.ndarray, lon: np.ndarray, n_pairs: int = 20000) -> None:
    """Eşdikdörtgen yaklaşımının haversine'a göre hatasını raporlar."""
    rng = np.random.default_rng(0)
    i = rng.integers(0, len(lat), n_pairs)
    j = rng.integers(0, len(lat), n_pairs)
    exact = haversine_km(lat[i], lon[i], lat[j], lon[j])
    cos_lat = np.cos(np.radians(lat))
    dy = lat[i] - lat[j]
    dx = (lon[i] - lon[j]) * (0.5 * (cos_lat[i] + cos_lat[j]))
    approx = np.sqrt(dx * dx + dy * dy) * DEG_KM
    m = exact > 1.0
    rel = np.abs(approx[m] - exact[m]) / exact[m]
    print(f"Mesafe yaklaşımı: ortanca hata %{100*np.median(rel):.3f}, "
          f"en kötü %{100*rel.max():.2f} ({m.sum()} çift, >1 km)")


def build_clusters(log_eta: np.ndarray, parent: np.ndarray, eta0: float,
                   mw: np.ndarray) -> np.ndarray:
    """NN grafiğini eşikten keserek kümeleri kurar; her kümenin en büyüğü ana şoktur.

    Sadece eşiğe bakmak yeterli DEĞİLDİR: kendisi güçlü öncü/artçı bağı olan büyük bir
    deprem (1999 İzmit M7.6, 2023 Elbistan M7.5 gibi) "kümelenmiş" çıkar ve saf eşik
    kuralıyla ana şok sayılmaz. Zaliapin & Ben-Zion prosedürü bağları keserek orman
    oluşturur ve her ağacın en büyük olayını ana şok ilan eder; kalanlar öncü/artçıdır.
    """
    n = len(log_eta)
    root = np.arange(n)

    def find(i: int) -> int:
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    # eta <= eta0 olan bağ "kümelenmiş" kabul edilir; olay ebeveyniyle aynı kümeye girer
    linked = (log_eta <= eta0) & (parent >= 0)
    for j in np.flatnonzero(linked):
        rj, rp = find(int(j)), find(int(parent[j]))
        if rj != rp:
            root[rj] = rp

    labels = np.array([find(i) for i in range(n)])
    is_mainshock = np.zeros(n, dtype=bool)
    order = np.lexsort((np.arange(n), -mw))  # büyükten küçüğe, eşitlikte erken olan önce
    seen = set()
    for i in order:
        lab = labels[i]
        if lab not in seen:
            seen.add(lab)
            is_mainshock[i] = True
    n_clusters = len(seen)
    n_multi = int((pd.Series(labels).value_counts() > 1).sum())
    print(f"Küme: {n_clusters} küme ({n_multi} tanesi çok olaylı), "
          f"{n - n_clusters} öncü/artçı")
    return is_mainshock


def load_mc_and_b(default_mc: float = 3.7, default_b: float = 1.0) -> tuple[float, float]:
    """Model dönemindeki (MODEL_START sonrası) en yüksek Mc ve olay-ağırlıklı b.

    En YÜKSEK Mc alınır: kataloğun her alt döneminde eksiksiz olan tek kesim odur.
    Daha düşük bir kesim, ağın seyrek olduğu dönemlerde eksik olayları "yok" saymaya
    ve dolayısıyla sahte sismik sessizliğe yol açar.
    """
    path = PROC / "mc_by_period.csv"
    if not path.exists():
        print(f"! {path} yok — varsayılan Mc={default_mc}, b={default_b} kullanılıyor "
              "(önce src.features.completeness çalıştırın).")
        return default_mc, default_b
    mc_df = pd.read_csv(path)
    start_year = pd.Timestamp(MODEL_START).year
    mc_df = mc_df[mc_df["period"].str.slice(0, 4).astype(int) >= start_year]
    mc_df = mc_df.dropna(subset=["mc"])
    if mc_df.empty:
        return default_mc, default_b
    mc = float(mc_df["mc"].max())
    b = float(np.average(mc_df["b"], weights=mc_df["n"]))
    print(f"Mc analizi: model dönemi Mc={mc:.2f}, b={b:.2f} "
          f"({', '.join(mc_df['period'])})")
    return mc, b


def learn_eta0(log_eta: np.ndarray) -> float:
    """log_eta dağılımına iki bileşenli Gauss karışımı oturtup eşiği öğrenir.

    Zaliapin ayrımı bimodaldir: kümelenmiş olaylar (küçük eta) ve arka plan olayları
    (büyük eta). Eşik, iki bileşenin posterior olasılığının eşitlendiği noktadır.
    """
    from sklearn.mixture import GaussianMixture

    x = log_eta[np.isfinite(log_eta)].reshape(-1, 1)
    if len(x) < 200:
        print(f"! GMM için yetersiz veri — eşik {ETA0_FALLBACK} kullanılıyor.")
        return ETA0_FALLBACK
    gm = GaussianMixture(n_components=2, random_state=0, n_init=5).fit(x)
    order = np.argsort(gm.means_.ravel())
    lo, hi = order  # lo = kümelenmiş bileşen, hi = arka plan
    mean_lo, mean_hi = float(gm.means_[lo, 0]), float(gm.means_[hi, 0])

    # Eşik İKİ ORTALAMANIN ARASINDA aranır. Bileşenlerin genişlikleri farklıysa
    # (burada kümelenmiş sigma ~2.0, arka plan ~0.7) posterior eğrileri İKİ kez
    # kesişir: biri iki mod arasındaki vadide — aranan ayrım noktası — diğeri çok
    # daha sağda, geniş bileşenin dar olanı kuyrukta tekrar geçtiği yerde. Arama
    # aralığı sınırlanmazsa ikinci kesişim seçilebilir; o zaman eşik arka plan
    # modunun bile sağına düşer, tüm katalog tek bir küme olur ve ana şok kalmaz.
    grid = np.linspace(mean_lo, mean_hi, 4000).reshape(-1, 1)
    post = gm.predict_proba(grid)
    crossings = np.where(np.diff(np.sign(post[:, hi] - post[:, lo])))[0]
    if not len(crossings):
        print(f"! GMM iki mod arasında ayrım noktası bulamadı — "
              f"eşik {ETA0_FALLBACK} kullanılıyor.")
        return ETA0_FALLBACK
    eta0 = float(grid[crossings[0], 0])
    w = gm.weights_
    print(f"GMM: kümelenmiş N({gm.means_[lo,0]:.2f}, {np.sqrt(gm.covariances_[lo,0,0]):.2f}) "
          f"ağırlık {w[lo]:.2f} | arka plan N({gm.means_[hi,0]:.2f}, "
          f"{np.sqrt(gm.covariances_[hi,0,0]):.2f}) ağırlık {w[hi]:.2f}  ->  ETA0={eta0:.2f}")
    return eta0


def plot_eta(log_eta: np.ndarray, eta0: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(log_eta[np.isfinite(log_eta)], bins=80, color="steelblue", edgecolor="none")
    ax.axvline(eta0, color="r", ls="--", label=f"ETA0={eta0:.2f}")
    ax.set_xlabel("log10(eta) — en yakın komşu mesafesi")
    ax.set_ylabel("olay sayısı")
    ax.set_title("Zaliapin NN mesafe dağılımı (bimodal olmalı: kümelenmiş | arka plan)")
    ax.legend()
    fig.tight_layout()
    dst = PROC / "declustering_eta.png"
    fig.savefig(dst, dpi=130)
    print(f"-> {dst}")


def main(min_mw: float | None = None) -> None:
    mc, b_value = load_mc_and_b()
    if min_mw is None:
        min_mw = mc
    df = read_catalog(PROC / "catalog_merged.csv")
    df = df[df["mw"] >= min_mw].sort_values("time").reset_index(drop=True)
    print(f"Mw>={min_mw}: {len(df)} olay, NN mesafeleri hesaplanıyor...")
    eta, parent = nearest_neighbor_distances(df, b_value)
    with np.errstate(divide="ignore"):
        log_eta = np.log10(eta)
    eta0 = learn_eta0(log_eta)
    df["log_eta"] = log_eta
    df["is_mainshock"] = build_clusters(log_eta, parent, eta0, df["mw"].to_numpy())
    out = PROC / "catalog_declustered.csv"
    df.to_csv(out, index=False)
    n_main = int(df["is_mainshock"].sum())
    print(f"Ana şok: {n_main}/{len(df)} ({100*n_main/len(df):.1f}%) -> {out}")
    plot_eta(log_eta, eta0)


if __name__ == "__main__":
    main()
