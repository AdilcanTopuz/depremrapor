"""EŞİK TEYİDİ — hat ile değerlendirme yolu ayrışmış mı?

SORU. Canlı hat bugün 146 hücre yayımladı (7 gün); ölçülmüş beklenti 299'du.
İki açıklama var ve AYIRT EDİLMELİDİR:

    (a) REJİM  -- 299, dondurulmuş değerlendirme dönemi (2021-2024) ortalaması;
                  bugün sakin, sayı doğal olarak düşük
    (b) AYRIŞMA -- hat, eşik ya da normalizasyon katmanında değerlendirmeden
                  farklı davranıyor (V18/V19 ailesinden birleşim hatası)

YÖNTEM. Değerlendirme döneminden başlangıçlar seçilir (aktif + sakin) ve AYNI
başlangıç iki yoldan geçirilir:

    YOL 1  değerlendirme tablosu (etas_analytic_weekly) + aynı eşik tanımı
    YOL 2  canlı hattın kullandığı forecast_now.to_geojson

Sayılar örtüşüyorsa fark REJİMDENDİR ve 146 doğru sayıdır.
Örtüşmüyorsa hat ile değerlendirme AYRIŞMIŞTIR ve cron başlamaz.

Kullanım:  python scripts/29_esik_teyidi.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

ESIK = 2.0
PENCERE = 7
MW = 4.5
KAHRAMANMARAS = pd.Timestamp("2023-02-06")


def yol1_degerlendirme(origin, fc, base, gr_b):
    """Değerlendirme tablosundan, hattın eşik tanımıyla aynı hesap."""
    sel = fc[(fc.ref_date == origin) & (fc.window_days == PENCERE)
             & (fc.target_mw == MW)]
    if sel.empty:
        return None
    scale = 10 ** (-gr_b * (MW - 5.0)) * PENCERE / 365.25
    normal = sel.cell_id.map(base["rate_all_m5.0_yr"]).fillna(0.0) * scale
    p_normal = 1.0 - np.exp(-normal)
    # TANIMSIZ, SONSUZ DEĞİLDİR (V40).
    #
    # Izgara 2560 hücre, uzun vadeli temel model 2100 hücre. Kalan 460
    # hücrede normal oran YOKTUR ve "normalin kaç katı" TANIMSIZDIR.
    #
    # İlk sürüm bunlara `np.inf` veriyordu -> eşiği otomatik geçiyorlardı ve
    # sayım 460 fazla çıkıyordu. `to_geojson` doğrusunu yapıyor: NaN üretir
    # ve NaN >= eşik karşılaştırması False'tur, yani hücre elenir.
    #
    # Sonuç: iki kez YANLIŞ "AYRIŞMA" hükmü verildi ve cron var olmayan bir
    # sebeple bloke edilecekti. Fark tam olarak 774 - 314 = 460'tı.
    with np.errstate(divide="ignore", invalid="ignore"):
        kat = np.where(p_normal > 0, sel.p_etas.to_numpy() / p_normal, np.nan)
    return {"toplam": len(sel), "esik_ustu": int((kat >= ESIK).sum()),
            "tanimsiz": int(np.isnan(kat).sum())}


def main() -> None:
    from src.config import load_mc_and_b
    from src.operational import forecast_now as F

    gr_b = load_mc_and_b()[1]
    base = pd.read_csv(PROC / "baseline_poisson.csv").set_index("cell_id")

    # DEĞERLENDİRME YOLUNUN KENDİ YÜKLEYİCİSİ kullanılır. Kendi okuyucumu
    # yazmak, karşılaştırmayı iki farklı okuma mantığına dayandırırdı; oysa
    # sınanan şey tam olarak "iki yol aynı mı" sorusudur.
    from src.eval import daily_backtest as db
    db.FORECAST_DIR = "etas_analytic_weekly"
    fc = db.load_forecast()
    fc["ref_date"] = pd.to_datetime(fc.ref_date).dt.tz_localize(None)
    origins = np.sort(fc.ref_date.unique())
    print(f"değerlendirme tablosu: {len(origins)} başlangıç "
          f"({pd.Timestamp(origins[0]):%Y-%m-%d} - "
          f"{pd.Timestamp(origins[-1]):%Y-%m-%d})")

    # AKTİF: dizi penceresinden · SAKİN: dizi dışından, rastgele
    aktif = [o for o in origins
             if KAHRAMANMARAS <= pd.Timestamp(o) < KAHRAMANMARAS
             + pd.Timedelta(days=60)][:3]
    rng = np.random.default_rng(7)
    disi = [o for o in origins
            if not (KAHRAMANMARAS <= pd.Timestamp(o)
                    < KAHRAMANMARAS + pd.Timedelta(days=90))]
    sakin = list(rng.choice(disi, size=3, replace=False))

    durum = F.load_state()
    print(f"\n{'başlangıç':12s} {'rejim':6s} {'YOL1 eşik üstü':>15s} "
          f"{'YOL2 yayımlanan':>16s} {'örtüşüyor':>10s}")
    kayit, ayrisma = [], 0
    for o, rejim in [(x, "aktif") for x in aktif] + [(x, "sakin") for x in sakin]:
        origin = pd.Timestamp(o)
        y1 = yol1_degerlendirme(origin, fc, base, gr_b)
        if y1 is None:
            continue
        blok = F.run_forecast_analytic(PENCERE, MW, origin=origin, state=durum)
        gj = F.to_geojson(blok, PENCERE, MW, origin, mode="pseudo",
                          min_times_normal=ESIK)
        y2 = gj["properties"]["cells_published"]
        ok = y1["esik_ustu"] == y2
        ayrisma += not ok
        kayit.append({"origin": f"{origin:%Y-%m-%d}", "rejim": rejim,
                      "yol1": y1["esik_ustu"], "yol2": y2, "ortusuyor": ok})
        print(f"{origin:%Y-%m-%d}   {rejim:6s} {y1['esik_ustu']:15d} "
              f"{y2:16d} {'EVET' if ok else 'HAYIR':>10s}")

    print()
    if ayrisma == 0:
        print("HÜKÜM: iki yol ÖRTÜŞÜYOR -> fark REJİMDENDİR.")
        print("       Bugünkü 146 hücre, güncel sakin rejimin sayısıdır;")
        print("       299 dondurulmuş dönemin ORTALAMASIYDI.")
    else:
        print(f"HÜKÜM: {ayrisma} başlangıçta AYRIŞMA -> hat ile değerlendirme")
        print("       farklı davranıyor. CRON BAŞLAMAZ; sebep bulunmalı.")

    (PROC / "esik_teyidi.json").write_text(json.dumps(
        {"esik": ESIK, "pencere": PENCERE, "mw": MW, "olcumler": kayit,
         "ayrisma_sayisi": ayrisma}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"\n-> {PROC / 'esik_teyidi.json'}")


if __name__ == "__main__":
    main()
