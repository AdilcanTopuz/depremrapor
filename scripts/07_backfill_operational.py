"""Geçmiş başlangıçlar için operasyonel tahmin arşivi üretir.

AMAÇ. Puanlayıcının (src.operational.score_archive) sınanabilmesi ve operasyonel
yolun bağımsız bir doğrulaması. Değerlendirme modülleri `etas_baseline.forecast`
yolunu kullanır; operasyonel çalıştırma ise `forecast_now.run_forecast` yolunu.
İkisi aynı ETAS durumundan geçmeli -- ama bunu hiç ölçmedik. Aynı dönemi iki
yoldan üretip karşılaştırmak, sessizce ayrışmış olmadıklarını gösterir.

SIZINTI YOK. `_calculation_at` katalogu başlangıç anında kesin olarak keser
(`cat.time < origin`), parametreler eğitim penceresinden gelir ve yeniden
kestirilmez. Dolayısıyla üretilen tahminler sözde-ileriye-dönüktür.

Bunlar CANLI tahmin DEĞİLDİR ve dosyalara "mode": "pseudo" olarak işaretlenir:
bugünkü kodu ve bugünkü düzeltilmiş katalogu kullanırlar. Gerçek ileriye dönük
kanıt yalnızca zamanı geldikçe biriken "live" tahminlerden gelir.

Kullanım:
    python scripts/07_backfill_operational.py --weeks 52
"""
import argparse
import json
import sys
import traceback
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.operational.forecast_now import (  # noqa: E402
    OUT_DIR, load_state, run_forecast, to_geojson)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weeks", type=int, default=52)
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    ap.add_argument("--n-sim", type=int, default=500)
    # Parçalama: başlangıçlar birbirinden bağımsız olduğu için süreçlere
    # dönüşümlü (round-robin) dağıtılabilir. Aynı düzen ETAS tahmininde de
    # kullanılıyor. Dönüşümlü dağıtım blok dağıtıma yeğdir: yükü zamana göre
    # dengeler, çünkü yoğun dönemler (artçı dizileri) kataloğa kümelenmiştir
    # ve blok dağıtımda tek bir sürece yığılır.
    ap.add_argument("--shard", type=int, default=0)
    ap.add_argument("--n-shards", type=int, default=1)
    a = ap.parse_args()

    from src.ingest.catalog_io import read_catalog
    cat_end = read_catalog(ROOT / "data" / "processed" / "catalog_merged.csv").time.max()
    # Birleşik katalog UTC-farkındalıklı, ETAS şeması farkındalıksız çalışır.
    # Başlangıçlar ETAS tarafıyla kıyaslanacağı için burada farkındalık düşürülür.
    if cat_end.tzinfo is not None:
        cat_end = cat_end.tz_localize(None)

    # Yalnızca penceresi TAMAMEN dolmuş başlangıçlar; yarım pencere sistematik
    # olarak "az tahmin" gibi görünür.
    last = (cat_end - pd.Timedelta(days=a.days)).normalize()
    origins = [last - pd.Timedelta(days=a.days * i) for i in range(a.weeks)][::-1]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    span = f"{origins[0]:%Y-%m-%d} .. {origins[-1]:%Y-%m-%d}"
    origins = origins[a.shard::a.n_shards]
    print(f"[parça {a.shard+1}/{a.n_shards}] {len(origins)} başlangıç ({span})")

    state = load_state()   # katalog bir kez yüklenir, tüm başlangıçlarda paylaşılır
    made = skipped = failed = 0
    for i, origin in enumerate(origins, 1):
        stamp = origin.strftime("%Y%m%d")
        path = OUT_DIR / f"forecast_{stamp}_{a.days}d_m{str(a.mw).replace('.','')}.geojson"
        if path.exists():
            skipped += 1
            continue
        try:
            block = run_forecast(a.days, a.n_sim, a.mw, origin, state=state)
            gj = to_geojson(block, a.days, a.mw, origin, mode="pseudo")
            path.write_text(json.dumps(gj), encoding="utf-8")
            made += 1
            print(f"[{i}/{len(origins)}] {origin:%Y-%m-%d}: {len(gj['features'])} hücre",
                  flush=True)
        except Exception:
            failed += 1
            print(f"[{i}/{len(origins)}] {origin:%Y-%m-%d}: HATA", flush=True)
            traceback.print_exc()
    print(f"\nüretildi {made}, atlandı {skipped}, hata {failed}")


if __name__ == "__main__":
    main()
