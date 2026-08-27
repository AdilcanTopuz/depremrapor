"""FARKLILAŞMA ANALİZİ — ML ile ETAS nerede ve neden ayrışıyor?

İLAN: docs/FAZ3_PLAN.md "(d) Farklılaşma analizi". Eşdeğerlik çıksa da
çıkmasa da yapılır: "hangi kesitte hangi model" sorusunun cevabı, tek bir
toplam skordan daha bilgilendiricidir.

BEŞ KESİT
    1. SHAP        hangi öznitelikler ETAS'ın veremediği bilgiyi taşıyor
    2. Rejim       dizi-dışı (ölçülebilir) · dizi-içi ("ölçülemez" etiketli)
    3. Bölge       yalnızca olay >= 5 olan bölgeler
    4. Kalibrasyon gözlenen/beklenen, iki model yan yana
    5. Anlaşmazlık iki modelin en çok ayrıştığı hücre-pencereler

İKİ KURAL — ilan edilmiş, burada uygulanıyor:

  * DİZİ-İÇİ KESİTTE HÜKÜM VERİLMEZ. Kahramanmaraş penceresi 13 blok içerir;
    13 bloktan bootstrap anlamlı aralık üretmez (V9). Satır "ölçülemez"
    etiketiyle gelir, sayıyla değil.
  * OLAY SAYISI < 5 OLAN BÖLGE için IG yazılmaz; "olay sayısı yetersiz" denir.

ÖNKOŞUL: data/processed/ml_etas_birlesik.parquet (scripts/21).

Kullanım:  python scripts/22_farklilasma.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

KAHRAMANMARAS = pd.Timestamp("2023-02-06", tz="UTC")
DIZI_GUN = 90                 # ilan edilen dizi penceresi
SHAP_ORNEK = 50_000           # SHAP için örneklem — açıkça beyan edilir
SHAP_SEED = 20260825


def _ig_satiri(sub: pd.DataFrame, taban: str, aday: str):
    """Bir alt küme için IG + GA + MDE; olay yetersizse None."""
    from src.eval.gain_breakdown import _ig_ci

    n = int(sub.y.sum())
    if n < 5:
        return {"olay": n, "IG": None, "not": "olay sayısı yetersiz (<5)"}
    kiyas = sub.assign(rate_pois=sub[taban], rate_etas=sub[aday])
    ig, lo, hi, mde, basis = _ig_ci(kiyas)
    return {"olay": n, "IG": ig, "lo": lo, "hi": hi, "mde": mde,
            "dayanak": basis}


def _yaz(ad: str, r: dict) -> None:
    if r["IG"] is None:
        print(f"  {ad:38s} {r['olay']:5d}  {r['not']}")
    else:
        print(f"  {ad:38s} {r['olay']:5d}  {r['IG']:+7.3f} "
              f"[{r['lo']:+7.3f}, {r['hi']:+7.3f}]  MDE {r['mde']:.3f}")


def main() -> None:
    src = PROC / "ml_etas_birlesik.parquet"
    if not src.exists():
        raise SystemExit("! ml_etas_birlesik.parquet yok — önce scripts/21")
    j = pd.read_parquet(src)
    j["ref_date"] = pd.to_datetime(j.ref_date, utc=True)
    print(f"{len(j):,} satır, {int(j.y.sum())} olay "
          f"({j.ref_date.min():%Y-%m-%d} - {j.ref_date.max():%Y-%m-%d})")

    rapor: dict = {"n_satir": len(j), "n_olay": int(j.y.sum())}

    # === 2. REJİM ==========================================================
    print("\n=== REJİM KIRILIMI (ML - ETAS, nat/olay) ===")
    ic = ((j.ref_date >= KAHRAMANMARAS)
          & (j.ref_date < KAHRAMANMARAS + pd.Timedelta(days=DIZI_GUN)))
    n_blok_ic = j[ic].ref_date.nunique()
    print(f"  dizi penceresi: {DIZI_GUN} gün, {n_blok_ic} haftalık blok")
    disi = _ig_satiri(j[~ic], "rate_etas", "rate_ml")
    _yaz("dizi-dışı", disi)
    print(f"  {'dizi-içi':38s} {int(j[ic].y.sum()):5d}  ÖLÇÜLEMEZ "
          f"({n_blok_ic} blok; bootstrap anlamlı aralık üretmez — V9)")
    rapor["rejim"] = {"dizi_disi": disi,
                      "dizi_ici": {"olay": int(j[ic].y.sum()),
                                   "n_blok": int(n_blok_ic),
                                   "hukum": "ölçülemez"}}

    # === 3. BÖLGE ==========================================================
    from src.config import cell_center
    from src.eval.gain_breakdown import region_of

    print("\n=== BÖLGE KIRILIMI (ML - ETAS) ===")
    ctr = j.cell_id.map(lambda c: cell_center(int(c)))
    j["bölge"] = [region_of(la, lo) for la, lo in ctr]
    bolge = {}
    for ad, sub in j.groupby("bölge"):
        r = _ig_satiri(sub, "rate_etas", "rate_ml")
        bolge[ad] = r
        _yaz(ad, r)
    rapor["bolge"] = bolge

    # === 4. KALİBRASYON ====================================================
    print("\n=== KALİBRASYON (gözlenen / beklenen) ===")
    n_obs = float(j.y.sum())
    kal = {}
    for ad, col in (("Poisson", "rate_pois"), ("ETAS", "rate_etas"),
                    ("ML", "rate_ml")):
        bek = float(j[col].sum())
        kal[ad] = {"beklenen": bek, "gozlenen": n_obs, "oran": n_obs / bek}
        print(f"  {ad:8s} beklenen {bek:8.1f} · gözlenen {n_obs:5.0f} · "
              f"oran {n_obs / bek:5.2f}")
    print("  (1,00 = kalibre; >1 eksik tahmin, <1 fazla tahmin)")
    rapor["kalibrasyon"] = kal

    # === 5. ANLAŞMAZLIK HARİTASI ==========================================
    print("\n=== ANLAŞMAZLIK: iki modelin en çok ayrıştığı 10 hücre-pencere ===")
    j["log_oran"] = np.log(np.maximum(j.rate_ml, 1e-12)
                           / np.maximum(j.rate_etas, 1e-12))
    print(f"  {'tarih':12s} {'hücre':>6s} {'ln(ML/ETAS)':>12s} "
          f"{'ETAS':>10s} {'ML':>10s}  olay")
    ayr = []
    for yon, sub in (("ML çok daha yüksek",
                      j.nlargest(5, "log_oran")),
                     ("ETAS çok daha yüksek",
                      j.nsmallest(5, "log_oran"))):
        print(f"  -- {yon} --")
        for _, r in sub.iterrows():
            print(f"  {r.ref_date:%Y-%m-%d} {int(r.cell_id):6d} "
                  f"{r.log_oran:12.2f} {r.rate_etas:10.2e} {r.rate_ml:10.2e}"
                  f"  {int(r.y)}")
            ayr.append({"yon": yon, "tarih": f"{r.ref_date:%Y-%m-%d}",
                        "cell_id": int(r.cell_id),
                        "log_oran": float(r.log_oran), "y": int(r.y)})
    rapor["anlasmazlik"] = ayr

    # olayların hangi modelde daha yüksek olduğu — asıl soru bu
    ol = j[j.y == 1]
    ml_ustun = int((ol.rate_ml > ol.rate_etas).sum())
    print(f"\n  GERÇEKLEŞEN {len(ol)} olayın {ml_ustun}'inde ML daha yüksek "
          f"oran verdi (%{100 * ml_ustun / len(ol):.1f})")
    print("  (%50 = ayırt edici bilgi yok; işaret testi tek başına hüküm değil)")
    from scipy import stats
    p_isaret = float(stats.binomtest(ml_ustun, len(ol), 0.5).pvalue)
    print(f"  işaret testi p = {p_isaret:.4f}")
    rapor["isaret_testi"] = {"ml_ustun": ml_ustun, "n": len(ol),
                             "p": p_isaret}

    # === 1. SHAP ===========================================================
    print(f"\n=== SHAP (test dönemi, {SHAP_ORNEK:,} satırlık örneklem) ===")
    model_dosyasi = PROC / "lgbm_secilen_t1.txt"
    if not model_dosyasi.exists():
        # LightGBM eksik dosyada ImportError DEĞİL LightGBMError atar; sessiz
        # geçmesin diye açıkça kontrol edilir (V21 sınıfı: gürültüsüz hata yok).
        print(f"  ATLANDI: {model_dosyasi.name} yok — önce scripts/21")
        rapor["shap"] = {"durum": "atlandı (model dosyası yok)"}
        model_dosyasi = None
    try:
        if model_dosyasi is None:
            raise ImportError("model dosyası yok")
        import lightgbm as lgb
        import shap

        import src.models.lgbm as L
        L.FEATURE_TABLE = "grid_features_weekly.parquet"
        from src.models.lgbm import CATALOG_FEATURES, load_dataset

        te = load_dataset("target_7d_m45_all")["test"]
        rng = np.random.default_rng(SHAP_SEED)
        idx = rng.choice(len(te), size=min(SHAP_ORNEK, len(te)), replace=False)
        x = te.iloc[idx][list(CATALOG_FEATURES)]

        m = lgb.Booster(model_file=str(model_dosyasi))
        sv = shap.TreeExplainer(m).shap_values(x)
        onem = np.abs(sv).mean(axis=0)
        sira = np.argsort(onem)[::-1]
        print(f"  {'öznitelik':22s} {'ort |SHAP|':>12s}  pay")
        toplam = onem.sum()
        shap_out = []
        for i in sira:
            ad = list(CATALOG_FEATURES)[i]
            print(f"  {ad:22s} {onem[i]:12.5f}  %{100 * onem[i] / toplam:.1f}")
            shap_out.append({"oznitelik": ad, "shap": float(onem[i]),
                             "pay": float(onem[i] / toplam)})
        rapor["shap"] = {"ornek": int(len(x)), "tohum": SHAP_SEED,
                         "siralama": shap_out}
        print(f"\n  KAPSAM: tek tohumun (t1) modeli, {len(x):,} satırlık "
              f"örneklem. Sıralama tohumlar arasında oynayabilir; buradaki")
        print("  pay değerleri bir büyüklük mertebesidir, kesin katkı değil.")
    except ImportError as e:
        if "model dosyası yok" not in str(e):
            print(f"  ATLANDI: {e}")
            rapor["shap"] = {"durum": f"atlandı ({e})"}

    dst = PROC / "farklilasma.json"
    dst.write_text(json.dumps(rapor, indent=2, ensure_ascii=False,
                              default=float), encoding="utf-8")
    print(f"\n-> {dst}")

    print("\nKAPSAM BEYANI: bütün kesitler TEST dönemine (2021-01-01 ..")
    print("2024-12-20), haftalık kuruluma ve M>=4.5 hedefine aittir. Kesitler")
    print("aynı 252 olayı böler; bağımsız sınamalar değildir ve çoklu")
    print("karşılaştırma düzeltmesi UYGULANMAMIŞTIR — kesit sonuçları hüküm")
    print("değil, farklılaşmanın nerede olduğuna dair tarifdir.")


if __name__ == "__main__":
    main()
