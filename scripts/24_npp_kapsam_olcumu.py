"""NPP girdi tasarımı için KAPSAM ÖLÇÜMÜ — ilan paketi yazılmadan önce.

SORU. Nöral model, geçmişteki kaç olayı görmeli ve hangi yarıçapa kadar?
K ve R keyfî seçilirse, modelin ETAS'ı geçememesi "mimari yetersiz" mi yoksa
"girdi kırpılmış" mı olduğu ayırt edilemez.

YÖNTEM. ETAS'ın kendi tetiklenme çekirdeği bir ÖLÇÜ verir: bir hücre-pencerede
beklenen tetiklenme, geçmiş olaylar üzerinde bir toplamdır. Her olayın payı
hesaplanır, büyükten küçüğe sıralanır ve "ilk K olay toplam kütlenin yüzde
kaçını taşıyor" ölçülür.

Bu, mimarinin değil GİRDİNİN yeterliliğini ölçer. K, ETAS'ın kütlesinin
neredeyse tamamını taşıyacak şekilde seçilirse, nöral modelin başarısızlığı
girdi kırpmasına atılamaz.

Test setine DOKUNMAZ: ölçüm EĞİTİM döneminden örneklenmiş başlangıçlarla
yapılır.

Kullanım:  python scripts/24_npp_kapsam_olcumu.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

N_ORNEK_REF = 40            # eğitim döneminden örneklenen başlangıç sayısı
SEED = 20260825
GECMIS_YIL = 10.0
K_LISTE = (4, 8, 16, 32, 64, 128)
R_LISTE = (50.0, 100.0, 200.0, 400.0)


def main() -> None:
    from src.config import cell_center
    from src.ingest.catalog_io import epoch_seconds, read_catalog
    from src.models.etas_params import EtasParams

    ep = EtasParams.load()
    p = ep.p
    c_gun = ep.c_days
    omega = p["omega"]
    d2 = 10 ** p["log10_d"]
    gamma = p["gamma"]
    rho = ep.rho
    a = p["a"]
    mc = ep.mc

    print(f"ETAS çekirdeği: p={ep.omori_p:.3f} · c={c_gun * 86400:.1f} sn · "
          f"d={ep.d_km:.2f} km · rho={rho:.3f} · gamma={gamma:.3f}\n")

    cat = read_catalog(PROC / "catalog_merged.csv")
    cat = cat.dropna(subset=["lat", "lon", "mw"]).sort_values("time")
    cat = cat[cat.mw >= mc]
    t = epoch_seconds(cat["time"])
    la = cat.lat.to_numpy()
    lo = cat.lon.to_numpy()
    mw = cat.mw.to_numpy()
    print(f"katalog {len(cat):,} olay (mc={mc}), "
          f"{cat.time.min():%Y-%m-%d} - {cat.time.max():%Y-%m-%d}")

    base = pd.read_csv(PROC / "baseline_poisson.csv")
    cells = np.sort(base.cell_id.unique())
    rng = np.random.default_rng(SEED)

    # EĞİTİM dönemi başlangıçları (test dönemine dokunulmaz)
    refs = pd.date_range("1995-01-06", "2015-12-25", freq="7D", tz="UTC")
    sec_ref = rng.choice(len(refs), size=N_ORNEK_REF, replace=False)

    pay_k = {k: [] for k in K_LISTE}
    pay_r = {r: [] for r in R_LISTE}
    n_hucre = 0

    for si in sec_ref:
        ref = refs[si]
        ref_s = float(epoch_seconds(pd.DatetimeIndex([ref]))[0])
        gor = (t < ref_s) & (t >= ref_s - GECMIS_YIL * 365.25 * 86400.0)
        if gor.sum() < 10:
            continue
        tt, lla, llo, mmw = t[gor], la[gor], lo[gor], mw[gor]
        dt_gun = (ref_s - tt) / 86400.0
        # zaman çekirdeği (Omori-Utsu, pencereye integralsiz -- oransal ölçü)
        k_t = (dt_gun + c_gun) ** (-(1.0 + omega))
        uret = np.exp(a * (mmw - mc))

        # o başlangıçta en yüksek tetiklenmeli 20 hücre örneklenir
        sec_c = rng.choice(len(cells), size=20, replace=False)
        for ci in sec_c:
            cla, clo = cell_center(int(cells[ci]))
            dx = (llo - clo) * 111.32 * np.cos(np.radians(cla))
            dy = (lla - cla) * 110.57
            r2 = dx * dx + dy * dy
            k_s = (r2 + d2 * np.exp(gamma * (mmw - mc))) ** (-rho)
            pay = uret * k_t * k_s
            tot = pay.sum()
            if tot <= 0:
                continue
            n_hucre += 1
            sira = np.sort(pay)[::-1]
            kum = np.cumsum(sira) / tot
            for k in K_LISTE:
                pay_k[k].append(float(kum[min(k, len(kum)) - 1]))
            r_km = np.sqrt(r2)
            for r in R_LISTE:
                pay_r[r].append(float(pay[r_km <= r].sum() / tot))

    print(f"{n_hucre:,} hücre-başlangıç örneklendi "
          f"({N_ORNEK_REF} başlangıç x 20 hücre)\n")

    print("--- KAÇ OLAY? ilk K olayın taşıdığı tetiklenme kütlesi payı ---")
    print(f"{'K':>5s} {'ortalama':>10s} {'medyan':>9s} {'%5 dilim':>10s} "
          f"{'%1 dilim':>10s}")
    out_k = {}
    for k in K_LISTE:
        v = np.array(pay_k[k])
        out_k[k] = {"ort": float(v.mean()), "medyan": float(np.median(v)),
                    "p5": float(np.percentile(v, 5)),
                    "p1": float(np.percentile(v, 1))}
        print(f"{k:5d} {v.mean():10.4f} {np.median(v):9.4f} "
              f"{np.percentile(v, 5):10.4f} {np.percentile(v, 1):10.4f}")

    print("\n--- HANGİ YARIÇAP? R km içindeki olayların payı ---")
    print(f"{'R km':>6s} {'ortalama':>10s} {'medyan':>9s} {'%5 dilim':>10s}")
    out_r = {}
    for r in R_LISTE:
        v = np.array(pay_r[r])
        out_r[r] = {"ort": float(v.mean()), "medyan": float(np.median(v)),
                    "p5": float(np.percentile(v, 5))}
        print(f"{r:6.0f} {v.mean():10.4f} {np.median(v):9.4f} "
              f"{np.percentile(v, 5):10.4f}")

    print("\n--- SEÇİM ÖLÇÜTÜ (ilan edilecek) ---")
    print("  K ve R, ETAS kütlesinin %5 diliminde bile >= 0,95'ini taşıyacak")
    print("  en küçük değerler olarak seçilir. Böylece nöral modelin")
    print("  başarısızlığı GİRDİ KIRPMASINA atılamaz.")
    k_sec = next((k for k in K_LISTE if out_k[k]["p5"] >= 0.95), None)
    r_sec = next((r for r in R_LISTE if out_r[r]["p5"] >= 0.95), None)
    print(f"\n  K = {k_sec}   R = {r_sec} km")
    if k_sec is None or r_sec is None:
        print("  ! ölçüt hiçbir denenen değerde karşılanmadı — liste genişletilmeli")

    dst = PROC / "npp_kapsam.json"
    dst.write_text(json.dumps(
        {"n_hucre": n_hucre, "n_ref": N_ORNEK_REF, "seed": SEED,
         "K": {str(k): v for k, v in out_k.items()},
         "R": {str(r): v for r, v in out_r.items()},
         "secim": {"K": k_sec, "R": r_sec, "olcut": "p5 >= 0,95"}},
        indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {dst}")


if __name__ == "__main__":
    main()
