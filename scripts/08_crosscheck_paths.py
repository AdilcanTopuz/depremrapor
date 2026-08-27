"""İki tahmin yolunun ayrışmadığını doğrular.

Değerlendirme modülleri `etas_baseline.forecast` yolunu, operasyonel çalıştırma
ise `forecast_now.run_forecast` yolunu kullanır. İkisi de aynı `_calculation_at`
durumunu kurup aynı simülasyonu çalıştırmalı -- ama bunu hiç ölçmedik ve bu
projede tam olarak bu tür sessiz ayrışmalar (kalibrasyon ile tahminin ayrı
yapılandırma kurması) saatler kaybettirdi.

YÖNTEM. Günlük geriye dönük testin kapsadığı dönemden birkaç başlangıç seçilir,
aynı başlangıçlar operasyonel yoldan yeniden üretilir ve hücre başına beklenen
olay sayıları karşılaştırılır.

TAM EŞİTLİK BEKLENMEZ. Simülasyon rastgeledir ve tohum paylaşılmaz; 500
simülasyonla hücre başına beklenti kaba bir ızgaraya oturur (0.002 adımlarla).
Aranan şey yapısal uyumdur: aynı hücreler, aynı büyüklük mertebesi, toplamda
Monte Carlo hatası içinde eşitlik. Korelasyonun düşmesi ya da toplamların
sistematik biçimde kayması ayrışma demektir.

Kullanım:
    python scripts/08_crosscheck_paths.py --n 6
"""
import argparse
import glob
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DAILY = ROOT / "data" / "processed" / "etas_daily"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="kaç başlangıç karşılaştırılsın")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--mw", type=float, default=4.5)
    ap.add_argument("--n-sim", type=int, default=500)
    a = ap.parse_args()

    from src.operational.forecast_now import load_state, run_forecast

    ref = pd.concat([pd.read_csv(f) for f in glob.glob(str(DAILY / "shard_*.csv"))])
    ref = ref[(ref.window_days == a.days) & (ref.target_mw == a.mw)]
    dates = sorted(ref.ref_date.unique())
    # Dönem boyunca eşit aralıklı seçim: sakin ve etkin dönemlerin ikisi de
    # örneklenir. Baştan n tane almak yalnızca tek bir rejimi sınardı.
    picks = [dates[i] for i in np.linspace(0, len(dates) - 1, a.n).astype(int)]
    print(f"{len(dates)} başlangıçtan {len(picks)} tanesi seçildi: "
          f"{picks[0]} .. {picks[-1]}\n")

    state = load_state()
    rows = []
    for d in picks:
        origin = pd.Timestamp(d)
        blk = run_forecast(a.days, a.n_sim, a.mw, origin, state=state)
        op = (blk[(blk.window_days == a.days) & (blk.target_mw == a.mw)]
              .set_index("cell_id")["rate_etas"])
        ev = ref[ref.ref_date == d].set_index("cell_id")["rate_etas"]

        cells = sorted(set(op.index) | set(ev.index))
        x = op.reindex(cells).fillna(0.0).to_numpy()
        y = ev.reindex(cells).fillna(0.0).to_numpy()
        both = len(set(op.index) & set(ev.index))
        rows.append({
            "origin": d, "op_toplam": x.sum(), "eval_toplam": y.sum(),
            "oran": x.sum() / y.sum() if y.sum() else np.nan,
            "ortak_hücre": both, "yalnız_op": len(set(op.index) - set(ev.index)),
            "yalnız_eval": len(set(ev.index) - set(op.index)),
            "korelasyon": np.corrcoef(x, y)[0, 1] if len(cells) > 2 else np.nan,
        })
        print(f"  {d}: oran {rows[-1]['oran']:.3f}, r = {rows[-1]['korelasyon']:.3f}",
              flush=True)

    df = pd.DataFrame(rows)
    print("\n" + df.round(3).to_string(index=False))
    r_med, ratio_med = df.korelasyon.median(), df.oran.median()
    print(f"\nortanca korelasyon: {r_med:.3f}   ortanca toplam oranı: {ratio_med:.3f}")
    if r_med > 0.95 and 0.85 < ratio_med < 1.15:
        print("-> İki yol uyumlu; ayrışma yok.")
    else:
        print("-> DİKKAT: yollar ayrışmış görünüyor, incelenmeli.")


if __name__ == "__main__":
    main()
