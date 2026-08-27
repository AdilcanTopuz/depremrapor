"""Bilgi kazancı NEREDEN geliyor? — zaman ve mekân ayrıştırması.

Tek bir toplam sayı ("olay başına +1.08 nat") yanıltıcı olabilir. Kazanç test
dönemine yayılmışsa model genel olarak iyidir; birkaç artçı dizisine yığılmışsa
model "büyük depremden sonra artçı olur" bilgisinden ibarettir. İkisi çok farklı
iddialardır ve toplam sayı ikisini ayırt etmez.

AYRIŞTIRMA. Kazanç, olaylar üzerinde bir TOPLAMDIR:

    IG = (1/N) * Σ_olay [ln λ_ETAS - ln λ_Poisson]  -  (Σλ_ETAS - Σλ_Poisson)/N

Birinci terim olay başına ayrıştırılabilir; ikinci terim (maruziyet farkı) tüm
hücrelere yayılır ve olaylara atfedilemez, bu yüzden ayrı raporlanır. Böylece
"kazancın %X'i şu dönemden geliyor" ifadesi tanımlı hale gelir.

Kullanım:
    python -m src.eval.gain_breakdown
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# 6 Şubat 2023 Kahramanmaraş dizisi. Bitiş kesin değil; artçılar yıllarca sürer.
# 90 gün, dizinin baskın olduğu dönem için yaygın bir seçimdir ve duyarlılığı
# aşağıda 30/180/365 günle ayrıca raporlanır.
KAHRAMANMARAS = pd.Timestamp("2023-02-06", tz="UTC")

# Kaba bölge tanımları (enlem, boylam kutuları) — kazancın mekânsal dağılımı için.
REGIONS = {
    "Doğu Anadolu (Maraş-Malatya)": (36.5, 39.5, 35.5, 39.5),
    "Kuzey Anadolu doğu (Erzincan-Erzurum)": (39.0, 41.0, 39.5, 43.0),
    "Kuzey Anadolu batı (Marmara)": (40.0, 41.5, 26.0, 31.5),
    "Batı Anadolu (Ege grabenleri)": (37.0, 40.0, 26.0, 30.0),
    "Ege denizi / Yunanistan": (35.0, 40.0, 25.0, 26.0),
}


def region_of(lat: float, lon: float) -> str:
    for name, (a, b, c, d) in REGIONS.items():
        if a <= lat <= b and c <= lon <= d:
            return name
    return "diğer"


KAPSAM_BEYANI = (
    "KAPSAM: güven aralıkları YALNIZCA gözlenen olay sayısından gelen "
    "belirsizliği kapsar. ETAS parametre belirsizliğini ve model "
    "yanlış-belirlemesini KAPSAMAZ. Model oranları deterministiktir "
    "(analitik hesap), dolayısıyla oranlarda örnekleme gürültüsü yoktur; "
    "ama parametrelerin kendisi bir kalibrasyondan gelir ve o belirsizlik "
    "buraya girmez."
)

def _ig_ci(rows: pd.DataFrame, n_boot: int = 2000, seed: int = 20260824
           ) -> tuple[float, float, float]:
    """Bilgi kazancı ve %95 güven aralığı — OLAY bazlı bootstrap.

    Belirsizliğin kaynağı olay sayısıdır, hücre-pencere sayısı değil: 2.3 milyon
    satırın neredeyse tamamı boştur ve bilgi taşımaz. Bu yüzden yeniden
    örnekleme olaylar üzerinden yapılır.

    Maruziyet terimi (beklenen toplamlar farkı) yeniden örneklemede SABİT
    tutulur: o terim tüm hücrelere yayılan bir kalibrasyon cezasıdır, olayların
    örneklemesine bağlı değildir. Yalnızca olay terimi yeniden örneklenir ve
    olay başına ortalamaya bölünürken aynı N kullanılır.

    "Aralık sıfırı içeriyor" ile "model daha kötü" AYNI ŞEY DEĞİLDİR; ayrım
    raporda korunur.
    """
    n = int(rows.y.sum())
    if n < 2:
        return (float("nan"), float("nan"), float("nan"),
                float("nan"), "olay sayısı yetersiz")
    p = rows[rows.y == 1]
    a = np.maximum(p.rate_pois.to_numpy(), 1e-12)
    b = np.maximum(p.rate_etas.to_numpy(), 1e-12)
    per_event = np.log(b) - np.log(a)
    exposure = -(rows.rate_etas.sum() - rows.rate_pois.sum()) / n

    rng = np.random.default_rng(seed)
    idx = rng.integers(0, n, size=(n_boot, n))
    boot = per_event[idx].mean(axis=1) + exposure

    # ASGARİ SAPTANABİLİR ETKİ. "Aralık sıfırı içeriyor" iki farklı şey
    # olabilir: fark yok, ya da veri farkı görecek güçte değil. Ayırt etmeden
    # yazılan "fark gösterilemedi" okuyucuyu birincisine iter. MDE, mevcut
    # olay sayısı ve varyansla %80 güçte saptanabilecek en küçük farktır.
    #
    # Standart hata BOOTSTRAP dağılımından alınır, analitik sd/sqrt(n)
    # formülünden değil: aynı yeniden örnekleme aralığı da ürettiği için ikisi
    # tutarlı olur ve MDE, aralığın dayandığı belirsizlikle aynı kaynaktan gelir.
    #
    # KÜÇÜK ÖRNEKLEM: z katsayıları (1.960 + 0.842 = 2.802) büyük örneklem
    # varsayımı taşır. Bölge satırlarının bir kısmı 10-30 olaya düşer ve orada
    # normal yaklaşım MDE ile aralığı olduğundan DAR gösterir. n < 30 iken
    # t-dağılımı katsayıları kullanılır.
    from scipy import stats

    se_boot = float(boot.std(ddof=1))
    if n < 30:
        mult = float(stats.t.ppf(0.975, n - 1) + stats.t.ppf(0.80, n - 1))
        basis = f"bootstrap SE, t({n - 1}) katsayısı {mult:.3f}"
    else:
        mult = 2.802
        basis = "bootstrap SE, z katsayısı 2.802"
    mde = mult * se_boot
    return (float(per_event.mean() + exposure),
            float(np.percentile(boot, 2.5)), float(np.percentile(boot, 97.5)),
            float(mde), basis)


def _full_ig(rows: pd.DataFrame) -> float:
    """Bir alt küme için TAM bilgi kazancı (olay + maruziyet terimleri)."""
    n = int(rows.y.sum())
    if n == 0:
        return float("nan")
    p = rows[rows.y == 1]
    a = np.maximum(p.rate_pois.to_numpy(), 1e-12)
    b = np.maximum(p.rate_etas.to_numpy(), 1e-12)
    return float((np.log(b) - np.log(a)).sum() / n
                 - (rows.rate_etas.sum() - rows.rate_pois.sum()) / n)


def per_event_gain(tgt: pd.DataFrame) -> pd.DataFrame:
    """Her POZİTİF satır için ln λ_ETAS - ln λ_Poisson katkısı."""
    pos = tgt[tgt.y == 1].copy()
    a = np.maximum(pos.rate_pois.to_numpy(), 1e-12)
    b = np.maximum(pos.rate_etas.to_numpy(), 1e-12)
    pos["gain"] = np.log(b) - np.log(a)
    return pos


def main(window_days: int = 7, target_mw: float = 4.5,
         source: str = "etas_daily") -> None:
    from src.config import cell_center
    from src.eval import daily_backtest as db

    # Kaynak dizin modül düzeyinde tutulur; build_table onu okur.
    db.FORECAST_DIR = source
    print(f"tahmin kaynağı: {source}")
    tgt = db.build_table(window_days, target_mw)
    pos = per_event_gain(tgt)
    n = len(pos)
    exposure = -(tgt.rate_etas.sum() - tgt.rate_pois.sum()) / n
    total = pos.gain.sum() / n + exposure
    print(f"olay başına toplam bilgi kazancı: {total:+.3f} nat "
          f"({n} pozitif hücre-pencere)")
    print(f"  olay terimi     : {pos.gain.sum()/n:+.3f}")
    print(f"  maruziyet terimi: {exposure:+.3f}   "
          f"(ETAS toplam {tgt.rate_etas.sum():.1f} vs "
          f"Poisson {tgt.rate_pois.sum():.1f} beklenen olay)")

    print("\n--- ZAMAN: Kahramanmaraş dizisi dahil / hariç ---")
    rows = []
    for d in (30, 90, 180, 365):
        end = KAHRAMANMARAS + pd.Timedelta(days=d)
        m = (pos.ref_date >= KAHRAMANMARAS) & (pos.ref_date < end)
        # TAM bilgi kazancı alt küme için yeniden hesaplanır: maruziyet terimi
        # de o alt kümenin başlangıçlarıyla sınırlanır. Yalnızca olay terimini
        # bölmek, dizi dışındaki kazancı olduğundan YÜKSEK gösterirdi, çünkü
        # çok tahmin etme cezası tüm döneme yayılıyor.
        inside = (tgt.ref_date >= KAHRAMANMARAS) & (tgt.ref_date < end)
        ig_in, *_ = _ig_ci(tgt[inside])
        ig_out, lo, hi, mde, mde_basis = _ig_ci(tgt[~inside])
        verdict = ("ETAS daha iyi" if lo > 0 else
                   "Poisson daha iyi" if hi < 0 else "fark gösterilemedi")
        rows.append({
            "dizi_penceresi": f"{d} gün",
            "n_dizi": int(m.sum()), "IG_dizi": round(ig_in, 3),
            "n_dışı": int((~m).sum()), "IG_dizi_dışı": round(ig_out, 3),
            "GA_alt": round(lo, 3), "GA_üst": round(hi, 3),
            # MDE yalnızca "fark gösterilemedi" durumunda anlamlıdır.
            "MDE": round(mde, 3) if verdict == "fark gösterilemedi" else None,
            "MDE_dayanak": (mde_basis if verdict == "fark gösterilemedi" else ""),
            "sonuç": verdict})
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    print("(TAM bilgi kazancı: olay terimi + o alt kümenin maruziyet terimi; "
          "GA olay bazlı bootstrap)")
    print(KAPSAM_BEYANI)

    print("--- ZAMAN: kazanç ne kadar yığılmış? ---")
    # PAYDA TANIMI: burada "başlangıç", EN AZ BİR gözlenen olayı olan tahmin
    # başlangıcıdır -- toplam başlangıç sayısı değil. Olaysız başlangıçlar olay
    # terimine katkı vermez, dolayısıyla yığılma ölçüsünün paydası olamazlar.
    # Etiketi "gün" yazmak yanıltıcıydı: haftalık kurulumda başlangıçlar 7 gün
    # arayla ve bir başlangıç tek bir günü değil bir pencereyi temsil ediyor.
    by_day = pos.groupby(pos.ref_date.dt.floor("D")).gain.sum().sort_values(
        ascending=False)
    tot = by_day.sum()
    n_all = int(tgt.ref_date.nunique())
    print(f"  payda: olaylı başlangıç sayısı = {len(by_day)} "
          f"(toplam {n_all} başlangıcın {n_all - len(by_day)} tanesinde hiç "
          f"M>={target_mw} olay yok)")
    for k in (1, 5, 10):
        if k <= len(by_day):
            print(f"  en yüksek {k:3d} olaylı başlangıç: toplam olay teriminin "
                  f"%{100*by_day.head(k).sum()/tot:.1f} i")
    # 30 ve üstü satır YAZILMIYOR: negatif başlangıçlar toplamı aşağı çektiği
    # için pay %100u aşabiliyor (ölçüldü: %130,7) ve yüzde olarak yazmak
    # yanıltıcı oluyor.
    neg = int((by_day < 0).sum())
    print(f"  ETAS'ın KAYBETTİĞİ olaylı başlangıç: {neg}/{len(by_day)} "
          f"(%{100*neg/len(by_day):.1f})")

    print("\n--- ZAMAN: yıllara göre ---")
    yr = pos.groupby(pos.ref_date.dt.year).gain.agg(["count", "mean", "sum"])
    yr["pay_%"] = 100 * yr["sum"] / tot
    print(yr.round(3).to_string())

    print()
    print("--- MEKÂN: bölgelere göre (TAM bilgi kazancı + GA + MDE) ---")
    # Bölge satırları ARALIKLARIYLA okunur; ortalama tek başına iddia taşımaz.
    # Bölge başına olay sayısı düşüktür ve aralıklar geniştir.
    ctr_all = tgt.cell_id.map(lambda c: cell_center(int(c)))
    tgt["bölge"] = [region_of(la, lo) for la, lo in ctr_all]
    reg_rows = []
    for name, sub in tgt.groupby("bölge"):
        n_ev = int(sub.y.sum())
        if n_ev < 5:
            reg_rows.append({"bölge": name, "olay": n_ev, "IG": None,
                             "GA_alt": None, "GA_üst": None, "MDE": None,
                             "sonuç": "olay sayısı yetersiz"})
            continue
        ig, lo, hi, mde, mde_basis = _ig_ci(sub)
        verdict = ("ETAS daha iyi" if lo > 0 else
                   "Poisson daha iyi" if hi < 0 else "fark gösterilemedi")
        reg_rows.append({"bölge": name, "olay": n_ev, "IG": round(ig, 3),
                         "GA_alt": round(lo, 3), "GA_üst": round(hi, 3),
                         "MDE": (round(mde, 3)
                                 if verdict == "fark gösterilemedi" else None),
                         "MDE_dayanak": (mde_basis
                                         if verdict == "fark gösterilemedi"
                                         else ""),
                         "sonuç": verdict})
    rg = pd.DataFrame(reg_rows).sort_values("olay", ascending=False)
    print(rg.to_string(index=False))
    print(KAPSAM_BEYANI)

    print("\n--- Poisson'un ETAS'ı geçtiği durumlar ---")
    lost = pos[pos.gain < 0]
    print(f"{len(lost)}/{n} olayda (%{100*len(lost)/n:.1f}) Poisson daha iyi; "
          f"ortalama kayıp {lost.gain.mean():.3f} nat" if len(lost)
          else "hiçbir olayda Poisson daha iyi değil")
    if len(lost):
        lr = lost.groupby(lost.ref_date.dt.year).size()
        print("  yıllara göre:", ", ".join(f"{y}: {c}" for y, c in lr.items()))

    out = {"window_days": window_days, "target_mw": target_mw,
           "n_positive": int(n), "total_gain": float(total),
           "event_term": float(pos.gain.sum() / n),
           "exposure_term": float(exposure),
           "top10_day_share": float(by_day.head(10).sum() / tot),
           "negative_days": neg, "n_days": int(len(by_day)),
           "lost_events": int(len(lost))}
    dst = PROC / "gain_breakdown.json"
    dst.write_text(json.dumps(out, indent=2))
    print(f"\n-> {dst}")


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    ap.add_argument("--source", default="etas_daily")
    a = ap.parse_args()
    main(a.window, a.mw, a.source)
