"""Kural 10: cevaplanabilirlik haritası — hangi sorular bu veriyle sorulabilir?

Ölçüt ilan edilmeden önce, o eşiğin ULAŞILABİLİR olduğu gösterilmelidir. Bu
betik Faz 3'ün ana sorusunu seçmek için gereken haritayı üretir: her kesitte,
hangi büyüklükteki bir fark %80 güçle saptanabilir?

ÜÇ KESİT
    genel        haftalık kurulum, 252 pozitif
    dizi-içi     Kahramanmaraş penceresi (30/90/180/365 gün)
    dizi-dışı    kalanı

İKİ METRİK
    IG    olay bazlı bootstrap SE'den (küçük örneklemde t katsayısı)
    AUC   blok bootstrap SE'den (L = 7 takvim günü, örtüşmeyen)

MDE'LER ÜST SINIRDIR. Buradaki SE'ler ETAS-Poisson farkından türetilir. Benzer
iki model (ETAS ile ML) arasındaki farkın varyansı DAHA KÜÇÜKTÜR: eşleşmiş
karşılaştırmada ortak bileşen sadeleşir. Dolayısıyla "saptanamaz" sonucu,
eşleşmiş varyans ölçüldüğünde yumuşayabilir (bkz. docs/KABUL_OLCUTLERI Ö5).

Kullanım:
    python scripts/18_mde_haritasi.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

KAHRAMANMARAS = pd.Timestamp("2023-02-06", tz="UTC")


def _mde(n: int, se: float) -> tuple[float, str]:
    """%80 güçte saptanabilir en küçük fark; n<30'da t katsayısı."""
    from scipy import stats

    if n < 2 or not np.isfinite(se):
        return float("nan"), "olay sayısı yetersiz"
    if n < 30:
        k = float(stats.t.ppf(0.975, n - 1) + stats.t.ppf(0.80, n - 1))
        return k * se, f"t({n - 1}) = {k:.3f}"
    return 2.802 * se, "z = 2.802"


def ig_mde(rows: pd.DataFrame, n_boot: int = 2000, seed: int = 20260825):
    """IG için MDE — olay bazlı bootstrap SE'sinden."""
    n = int(rows.y.sum())
    if n < 2:
        return {"n": n, "mde": float("nan"), "dayanak": "olay sayısı yetersiz"}
    p = rows[rows.y == 1]
    a = np.maximum(p.rate_pois.to_numpy(), 1e-12)
    b = np.maximum(p.rate_etas.to_numpy(), 1e-12)
    per = np.log(b) - np.log(a)
    rng = np.random.default_rng(seed)
    boot = per[rng.integers(0, n, size=(n_boot, n))].mean(axis=1)
    se = float(boot.std(ddof=1))
    mde, dayanak = _mde(n, se)
    return {"n": n, "se": se, "mde": float(mde), "dayanak": dayanak}


def auc_mde(tgt: pd.DataFrame, block_id: np.ndarray, n_boot: int = 400,
            seed: int = 20260825):
    """AUC farkı için MDE — blok bootstrap SE'sinden."""
    from sklearn.metrics import roc_auc_score

    y = tgt.y.to_numpy()
    sa = tgt.p_pois.to_numpy()
    sb = tgt.p_etas.to_numpy()
    uniq = np.unique(block_id)
    rows_of = {b: np.flatnonzero(block_id == b) for b in uniq}
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_boot):
        pick = rng.integers(0, len(uniq), len(uniq))
        idx = np.concatenate([rows_of[uniq[b]] for b in pick])
        yy = y[idx]
        if yy.sum() == 0 or yy.sum() == len(yy):
            continue
        diffs.append(roc_auc_score(yy, sb[idx]) - roc_auc_score(yy, sa[idx]))
    d = np.asarray(diffs)
    se = float(d.std(ddof=1))
    n_ev = int(y.sum())
    mde, dayanak = _mde(n_ev, se)
    return {"n_olay": n_ev, "n_blok": int(len(uniq)), "se": se,
            "mde": float(mde), "dayanak": dayanak}


def main() -> None:
    from src.eval import daily_backtest as db

    db.FORECAST_DIR = "etas_analytic_weekly"
    tgt = db.build_table(7, 4.5, quiet=True)
    block_id = db.calendar_blocks(tgt.ref_date, 7)

    print("CEVAPLANABİLİRLİK HARİTASI — haftalık analitik kurulum, M>=4.5")
    print(f"{len(tgt):,} satır, {int(tgt.y.sum())} pozitif, "
          f"{len(np.unique(block_id))} blok\n")

    kesitler = {"genel": np.ones(len(tgt), dtype=bool)}
    for d in (30, 90, 180, 365):
        m = ((tgt.ref_date >= KAHRAMANMARAS)
             & (tgt.ref_date < KAHRAMANMARAS + pd.Timedelta(days=d))).to_numpy()
        kesitler[f"dizi-içi {d}g"] = m
        kesitler[f"dizi-dışı {d}g"] = ~m

    print("--- IG (bilgi kazancı, nat/olay) ---")
    print(f"{'kesit':>16s} {'olay':>6s} {'SE':>8s} {'MDE':>8s}  dayanak")
    ig = {}
    for ad, m in kesitler.items():
        r = ig_mde(tgt[m])
        ig[ad] = r
        print(f"{ad:>16s} {r['n']:6d} {r.get('se', float('nan')):8.4f} "
              f"{r['mde']:8.4f}  {r['dayanak']}")

    print("\n--- AUC farkı ---")
    print(f"{'kesit':>16s} {'olay':>6s} {'blok':>5s} {'SE':>8s} {'MDE':>8s}")
    auc = {}
    for ad in ("genel", "dizi-içi 90g", "dizi-dışı 90g"):
        m = kesitler[ad]
        r = auc_mde(tgt[m], block_id[m])
        auc[ad] = r
        print(f"{ad:>16s} {r['n_olay']:6d} {r['n_blok']:5d} {r['se']:8.4f} "
              f"{r['mde']:8.4f}")

    # --- cevaplanabilirlik: VARSAYIMSIZ ---
    #
    # İlk sürümde "AÇIK/KAPALI" hükmü, benim varsaydığım tipik ML-ETAS farkına
    # (0,35 nat) dayanıyordu. MDE ölçülmüştü ama HÜKÜM VARSAYIMA dayanıyordu --
    # tam da kaçındığımız şey. Artık yalnızca ÖLÇÜLEN saptanabilirlik yazılır ve
    # soru bazında hangi büyüklüklerin ayırt edilebildiği gösterilir.
    print()
    print("=== CEVAPLANABİLİRLİK ===")
    print("(MDE'ler ÜST SINIRDIR: benzer modeller arasında fark varyansı daha")
    print(" küçüktür, eşleşmiş ölçüm yapılınca yumuşayabilir -- Ö5)")
    print()

    g_ig, g_auc = ig["genel"], auc["genel"]
    d_ig = ig["dizi-dışı 90g"]
    print("  SAPTANABİLİR fark büyüklükleri (%80 güç):")
    print(f"    IG genel      : |fark| > {g_ig['mde']:.3f} nat")
    print(f"    IG dizi-dışı  : |fark| > {d_ig['mde']:.3f} nat")
    print(f"    IG dizi-içi   : |fark| > {ig['dizi-içi 90g']['mde']:.3f} nat")
    print(f"    AUC genel     : |fark| > {g_auc['mde']:.4f}")
    print(f"    AUC dizi-dışı : |fark| > {auc['dizi-dışı 90g']['mde']:.4f}")

    print()
    print("  ÖLÇEK KARŞILAŞTIRMASI (ölçülmüş, varsayım değil):")
    print("    ETAS'ın Poisson'a IG üstünlüğü      : +1,068 nat")
    print("    ETAS'ın Poisson'a AUC üstünlüğü     : +0,1407")
    print(f"    IG genel MDE / bu üstünlük           : {g_ig['mde']/1.068:.2f}")
    print(f"    AUC genel MDE / bu üstünlük          : {g_auc['mde']/0.1407:.2f}")

    print()
    print("  SORU BAZINDA:")
    print(f"    'ML, ETAS'tan ÇOK daha kötü mü?' (fark > {g_ig['mde']:.2f} nat)")
    print("       -> AÇIK. ETAS-Poisson farkının yarısı kadar bir düşüş saptanır.")
    print(f"    'ML biraz daha iyi/kötü mü?' (fark < {g_ig['mde']:.2f} nat)")
    print("       -> KAPALI. Bu veriyle ayırt edilemez.")

    # Ö5 eşdeğerlik ölçütünün UYGULANABİLİRLİĞİ
    print()
    print("  Ö5 EŞDEĞERLİK ÖLÇÜTÜ UYGULANABİLİR Mİ?")
    for ad, r in (("IG genel", g_ig), ("IG dizi-dışı", d_ig)):
        ga = 2 * 1.96 * r["se"]
        olur = ga < 2 * r["mde"]
        print(f"    {ad:14s}: beklenen GA genişliği {ga:.3f}, "
              f"gereken < {2*r['mde']:.3f}  -> {'EVET' if olur else 'HAYIR'}")
    print("    (Ö5 koşul 2: aralık, eşdeğerlik demeye yetecek kadar dar olmalı)")

    out = {"ig": ig, "auc": auc,
           "not": "MDE'ler ETAS-Poisson farkından; ML-ETAS için ÜST SINIR"}
    dst = ROOT / "data" / "processed" / "mde_haritasi.json"
    dst.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {dst}")


if __name__ == "__main__":
    main()
