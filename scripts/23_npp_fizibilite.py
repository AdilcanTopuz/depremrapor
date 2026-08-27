"""NPP FİZİBİLİTE ÖLÇÜMÜ — ilan paketi yazılmadan ÖNCE.

NEDEN. Kural 10 (eşiğin ulaşılabilirliği gösterilmeden ilan edilmez) plana da
uygulanır: koşulamayacak bir arama uzayı ilan etmek, ilanı süs hâline getirir.
Bu ortamda torch **CPU-only**dır (2.13.0+cpu, GPU yok); 2,3 milyon satırlık
eğitim kümesinde dizi kodlayıcılı bir model saatler sürebilir.

Bu betik HİÇBİR HÜKÜM ÜRETMEZ. Yalnızca şunu ölçer: bir eğitim adımı ne kadar
sürüyor, bir tur ne kadar sürüyor, dolayısıyla kaç bileşim x kaç tohum
ilan edilebilir?

Test setine DOKUNMAZ (yüklenir yüklenmez silinir).

Kullanım:  python scripts/23_npp_fizibilite.py
"""
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"

TARGET = "target_7d_m45_all"
TABLE = "grid_features_weekly.parquet"


def main() -> None:
    import torch
    import torch.nn as nn

    torch.manual_seed(0)
    n_thread = torch.get_num_threads()
    print(f"torch {torch.__version__} · iş parçacığı {n_thread} · GPU yok\n")

    import src.models.lgbm as L
    L.FEATURE_TABLE = TABLE
    from src.models.lgbm import CATALOG_FEATURES, load_dataset

    data = load_dataset(TARGET)
    data.pop("test", None)          # YAPISAL: test bu ölçümde yok
    tr = data["train"]
    feats = list(CATALOG_FEATURES)
    print(f"eğitim {len(tr):,} satır · {len(feats)} statik öznitelik")
    print(f"pozitif {int(tr[TARGET].sum())} (%{100 * tr[TARGET].mean():.4f})\n")

    x = torch.tensor(tr[feats].to_numpy(dtype=np.float32))
    x = torch.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    mu = x.mean(0, keepdim=True)
    sd = x.std(0, keepdim=True).clamp_min(1e-6)
    x = (x - mu) / sd
    y = torch.tensor(tr[TARGET].to_numpy(dtype=np.float32))

    # Poisson NLL ile eğitilen küçük bir MLP: NPP'nin statik dalı.
    # Dizi dalı (yakın geçmişteki olaylar üzerinde kodlayıcı) buna eklenecek;
    # fizibilite için ALT SINIR ölçülür -- gerçek model bundan YAVAŞ olacaktır.
    class Basit(nn.Module):
        def __init__(self, d_in: int, gizli: int):
            super().__init__()
            self.net = nn.Sequential(
                nn.Linear(d_in, gizli), nn.ReLU(),
                nn.Linear(gizli, gizli), nn.ReLU(),
                nn.Linear(gizli, 1))

        def forward(self, v):
            return self.net(v).squeeze(-1)      # log oran

    sonuc = {"torch": torch.__version__, "threads": n_thread,
             "n_train": len(tr), "olcumler": []}

    for gizli, yigin in ((64, 4096), (64, 16384), (256, 16384)):
        m = Basit(len(feats), gizli)
        opt = torch.optim.Adam(m.parameters(), lr=1e-3)
        n_par = sum(p.numel() for p in m.parameters())
        idx = torch.randperm(len(x))
        n_adim = 20
        t0 = time.time()
        for k in range(n_adim):
            sel = idx[k * yigin:(k + 1) * yigin]
            log_lam = m(x[sel])
            # Poisson NLL: lambda - y*log(lambda), sayım biçiminde
            kayip = (log_lam.exp() - y[sel] * log_lam).mean()
            opt.zero_grad(); kayip.backward(); opt.step()
        dt = (time.time() - t0) / n_adim
        adim_tur = int(np.ceil(len(x) / yigin))
        tur_sn = dt * adim_tur
        print(f"gizli {gizli:3d} · yığın {yigin:5d} · {n_par:6,} parametre -> "
              f"adım {dt * 1000:6.1f} ms · tur {tur_sn:6.1f} sn "
              f"({adim_tur} adım)")
        sonuc["olcumler"].append(
            {"gizli": gizli, "yigin": yigin, "parametre": n_par,
             "adim_ms": dt * 1000, "tur_sn": tur_sn, "adim_tur": adim_tur})

    print("\n--- İLAN EDİLEBİLİR ARAMA BÜYÜKLÜĞÜ ---")
    ref = sonuc["olcumler"][1]          # orta kurulum
    for n_tur in (10, 20, 40):
        kosu = ref["tur_sn"] * n_tur
        print(f"  {n_tur:2d} tur -> koşu {kosu / 60:5.1f} dk · "
              f"12 bileşim x 3 tohum = {36 * kosu / 3600:5.1f} sa · "
              f"6 x 3 = {18 * kosu / 3600:5.1f} sa")
    print("\n  NOT: bunlar ALT SINIRDIR. Dizi kodlayıcı eklendiğinde adım")
    print("  süresi artacaktır; ilan paketi ölçülen gerçek modele göre yazılır.")

    dst = PROC / "npp_fizibilite.json"
    dst.write_text(json.dumps(sonuc, indent=2, ensure_ascii=False),
                   encoding="utf-8")
    print(f"\n-> {dst}")


if __name__ == "__main__":
    main()
