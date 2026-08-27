"""36 bileşim x 3 tohum hiperparametre araması — ilan edilen protokol.

İLAN: docs/FAZ3_PLAN.md "(c) Hiperparametre arama protokolü", commit a49f84e.
Uzay ve seçim kuralı SONUÇ GÖRÜLMEDEN önce dondurulmuştur; bu betik onu
uygular, değiştirmez.

İKİ YAPISAL KORUMA

1. TEST SETİ BU BETİĞE HİÇ GİRMEZ. `load_dataset` üç bölümü de döndürür ama
   burada `data["test"]` silinir ve bir daha adı geçmez. Seçim kuralının test
   dönemini görmediği bir SÖZ değil, bir VERİ YOKLUĞUDUR (history_view ile
   aynı ilke).

2. HER KOŞU ANINDA DİSKE YAZILIR (jsonl, append). NameError vakasının dersi:
   25 dakikalık bir bootstrap, sonuçları bellekte tuttuğu için tek bir isim
   hatasıyla kayboldu. Burada 108 koşu var; çökme hâlinde biten koşular durur
   ve betik kaldığı yerden devam eder.

Kullanım:
    python scripts/20_hiperparametre_arama.py          # koş / devam et
    python scripts/20_hiperparametre_arama.py --rapor  # yalnızca tabloyu bas
"""
import itertools
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TARGET = "target_7d_m45_all"
TABLE = "grid_features_weekly.parquet"
SEEDS = (1, 2, 3)
LOG = ROOT / "data" / "processed" / "hp_arama.jsonl"

# --- İLAN EDİLEN UZAY (sabit, genişletilmez) -------------------------------
SPACE = {
    "learning_rate": (0.02, 0.05),
    "num_leaves": (7, 15, 31),
    "min_child_samples": (20, 50, 200),
    "lambda_l2": (1.0, 10.0),
}
FIXED = dict(objective="binary", metric="binary_logloss",
             feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1,
             verbosity=-1, num_threads=4)
NUM_BOOST_ROUND = 3000
EARLY_STOPPING = 150


def combos() -> list[dict]:
    keys = list(SPACE)
    return [dict(zip(keys, v)) for v in itertools.product(*SPACE.values())]


def _key(c: dict, seed: int) -> str:
    return json.dumps({**c, "seed": seed}, sort_keys=True)


def _done() -> set[str]:
    if not LOG.exists():
        return set()
    out = set()
    for line in LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            out.add(_key(r["params"], r["seed"]))
    return out


def rapor() -> None:
    import numpy as np

    rows = [json.loads(l) for l in LOG.read_text(encoding="utf-8").splitlines()
            if l.strip()]
    by: dict[str, list] = {}
    for r in rows:
        by.setdefault(json.dumps(r["params"], sort_keys=True), []).append(r)

    print(f"\nARAMA SONUÇLARI — {len(by)}/36 bileşim, {len(rows)}/108 koşu")
    print("Seçim ölçütü: DOĞRULAMA logloss'unun 3 tohum ortalaması (küçük iyi)")
    print("Test dönemi bu tabloya HİÇ girmemiştir.\n")
    print(f"{'#':>3s} {'lr':>5s} {'yap':>4s} {'mcs':>4s} {'l2':>5s} "
          f"{'ort logloss':>13s} {'ss':>9s} {'n':>2s} {'ort yin':>8s}")

    tab = []
    for k, rs in by.items():
        p = json.loads(k)
        ll = np.array([r["val_logloss"] for r in rs])
        tab.append((float(ll.mean()), float(ll.std(ddof=1)) if len(ll) > 1
                    else float("nan"), p, len(rs),
                    float(np.mean([r["best_iteration"] for r in rs]))))
    # BERABERLİK KURALI: eşitlikte daha AZ yapraklı model önce.
    #
    # İLK SÜRÜMDE round(x[0], 6) KULLANILIYORDU VE BU BİR SAPMADIR. İlan
    # edilen kural "doğrulama logloss ortalamasının en küçüğü; BERABERLİKTE
    # daha az yapraklı" idi. 6 haneye yuvarlamak, ilanda olmayan bir
    # "beraberlik" tanımı uydurur: ilk üç bileşim yapay olarak eşitlendi,
    # üçünün de yaprak sayısı 7 olduğu için beraberlik kuralı ayırt edemedi ve
    # seçim EKLENME SIRASINA düştü. Sonuç: ham üçüncü sıradaki bileşim
    # seçilmişti (V23).
    #
    # Düzeltme, sonuca göre yapılan bir ayar DEĞİLDİR: kod, önceden ilan
    # edilmiş kuralı uygulamıyordu; şimdi uyguluyor.
    tab.sort(key=lambda x: (x[0], x[2]["num_leaves"]))

    for i, (m, s, p, n, it) in enumerate(tab, 1):
        print(f"{i:3d} {p['learning_rate']:5.2f} {p['num_leaves']:4d} "
              f"{p['min_child_samples']:4d} {p['lambda_l2']:5.1f} "
              f"{m:13.6f} {s:9.6f} {n:2d} {it:8.0f}")

    if len(tab) == 36 and all(t[3] == 3 for t in tab):
        best = tab[0]
        print(f"\nSEÇİLEN: lr={best[2]['learning_rate']} "
              f"yaprak={best[2]['num_leaves']} "
              f"min_child={best[2]['min_child_samples']} "
              f"l2={best[2]['lambda_l2']}")
        print(f"  doğrulama logloss {best[0]:.6f} +- {best[1]:.6f}")
        print(f"  en yakın rakip    {tab[1][0]:.6f} "
              f"(fark {tab[1][0]-best[0]:+.6f})")
        (ROOT / "data" / "processed" / "hp_secim.json").write_text(
            json.dumps({"params": best[2], "val_logloss_mean": best[0],
                        "val_logloss_sd": best[1],
                        "runner_up_gap": tab[1][0] - best[0]},
                       indent=2, ensure_ascii=False), encoding="utf-8")
        print("\n-> data/processed/hp_secim.json")
    else:
        eksik = 108 - len(rows)
        print(f"\nARAMA TAMAMLANMADI: {eksik} koşu eksik. Seçim YAPILMAZ.")


def main() -> None:
    import lightgbm as lgb

    import src.models.lgbm as L
    L.FEATURE_TABLE = TABLE
    from src.models.lgbm import CATALOG_FEATURES, load_dataset

    data = load_dataset(TARGET)
    del data["test"]          # YAPISAL: test bu süreçte YOKTUR
    feats = list(CATALOG_FEATURES)

    tr, va = data["train"], data["val"]
    print(f"eğitim {len(tr):,} satır / {int(tr[TARGET].sum())} pozitif · "
          f"doğrulama {len(va):,} / {int(va[TARGET].sum())}")
    print(f"öznitelik {len(feats)} · bölümler: {sorted(data)}\n")

    d_tr = lgb.Dataset(tr[feats], tr[TARGET].astype(int), free_raw_data=False)
    d_va = lgb.Dataset(va[feats], va[TARGET].astype(int), free_raw_data=False)

    done = _done()
    todo = [(c, s) for c in combos() for s in SEEDS if _key(c, s) not in done]
    print(f"{len(done)} koşu zaten bitmiş, {len(todo)} kaldı.\n")

    t_start = time.time()
    for i, (c, seed) in enumerate(todo, 1):
        t0 = time.time()
        model = lgb.train(
            {**FIXED, **c, "seed": seed}, d_tr,
            num_boost_round=NUM_BOOST_ROUND,
            valid_sets=[d_va], valid_names=["val"],
            callbacks=[lgb.early_stopping(EARLY_STOPPING, verbose=False),
                       lgb.log_evaluation(0)])
        rec = {"params": c, "seed": seed,
               "val_logloss": float(model.best_score["val"]["binary_logloss"]),
               "best_iteration": int(model.best_iteration),
               "seconds": round(time.time() - t0, 1)}
        with LOG.open("a", encoding="utf-8") as f:     # ANINDA diske
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        gecen = time.time() - t_start
        kalan = gecen / i * (len(todo) - i)
        print(f"[{i:3d}/{len(todo)}] lr={c['learning_rate']} "
              f"yap={c['num_leaves']:2d} mcs={c['min_child_samples']:3d} "
              f"l2={c['lambda_l2']:4.1f} t={seed} -> "
              f"{rec['val_logloss']:.6f} (yin {rec['best_iteration']:4d}, "
              f"{rec['seconds']:.0f} sn) | kalan ~{kalan/60:.0f} dk")

    rapor()


if __name__ == "__main__":
    if "--rapor" in sys.argv:
        rapor()
    else:
        main()
