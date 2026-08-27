"""NPP girdi dizini — her (hücre, başlangıç) için komşu olay indeksleri.

TASARIM. Olaylar, **literatürden alınmış ve bu veriye uydurulmamış** bir öncül
çekirdekle sıralanır (bkz. `docs/NPP_ILAN.md` Zeyilname 1). Uydurulmuş ETAS
çekirdeğiyle sıralamak, karşılaştırılan modelin cevabını rakibinin girdisine
sokardı — sızıntı taksonomisinin dördüncü ekseni (V24).

    ÖNCÜL:      p=1,10 · c=0,01 gün · d=5 km · rho=0,75 · alpha10=1,00
    UYDURULMUŞ: p=1,097 · c=9,8 sn  · d=1,45 km · rho=0,591 · alpha10=0,922

Bu modül **uydurulmuş parametreleri hiç okumaz.** Bağımsızlık, kodun
yapısıyla güvence altındadır: `etas_params` içe aktarılmaz.

ÇIKTI. `npp_index.i32` — (satır, K) int32 memmap, öncül sıralamaya göre en
üstteki K olayın KATALOG indeksleri; eksikler -1. Satır sırası, öznitelik
tablosunun sırasıyla BİREBİR aynıdır.

KÜNYE ZİNCİRİ. Yanında `npp_index.json`: dosyanın sha256'sı, üreten commit,
katalog sha256'sı, öncül parametreler, K/R/geçmiş. Bu dosya artık her koşunun
girdisidir; bayatlarsa V6'nın veri tarafındaki karşılığı doğar.
"""
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# --- ÖNCÜL ÇEKİRDEK (literatür; bu veriye uydurulmamış) --------------------
ONCUL = {"p": 1.10, "c_gun": 0.01, "d_km": 5.0, "rho": 0.75, "alpha10": 1.00}

K = 256
R_KM = 200.0
GECMIS_YIL = 10.0
MC = 3.3                      # katalog tamlık eşiği (sabit, ETAS'tan bağımsız)

IDX_PATH = PROC / "npp_index.i32"
KUNYE_PATH = PROC / "npp_index.json"


def oncul_agirlik(dt_gun: np.ndarray, dr_km: np.ndarray,
                  mw: np.ndarray) -> np.ndarray:
    """Öncül tetiklenme ağırlığı — SIRALAMA için, değer olarak kullanılmaz."""
    o = ONCUL
    return (10.0 ** (o["alpha10"] * (mw - MC))
            * (dt_gun + o["c_gun"]) ** (-o["p"])
            * (dr_km * dr_km + o["d_km"] ** 2) ** (-o["rho"]))


def _sha256(path: Path, blok: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(blok):
            h.update(chunk)
    return h.hexdigest()


def _commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                              capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return "bilinmiyor"


def _kirli() -> bool:
    try:
        return bool(subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                                   capture_output=True, text=True,
                                   check=True).stdout.strip())
    except Exception:
        return True


def build(tablo: str = "grid_features_weekly.parquet",
          cell_chunk: int = 256, quiet: bool = False) -> None:
    from src.config import cell_center
    from src.ingest.catalog_io import epoch_seconds, read_catalog

    kat_yol = PROC / "catalog_merged.csv"
    cat = read_catalog(kat_yol)
    cat = cat.dropna(subset=["lat", "lon", "mw"]).sort_values("time")
    cat = cat[cat.mw >= MC].reset_index(drop=True)
    et = epoch_seconds(cat["time"])
    ela = cat.lat.to_numpy()
    elo = cat.lon.to_numpy()
    emw = cat.mw.to_numpy()

    rows = pd.read_parquet(PROC / tablo, columns=["cell_id", "ref_date"])
    rows["ref_date"] = pd.to_datetime(rows.ref_date, utc=True)
    n = len(rows)
    if not quiet:
        print(f"katalog {len(cat):,} olay (mc={MC}) · tablo {n:,} satır")
        print(f"K={K} · R={R_KM} km · geçmiş {GECMIS_YIL} yıl · öncül {ONCUL}")

    hucreler = np.sort(rows.cell_id.unique())
    merkez = {int(c): cell_center(int(c)) for c in hucreler}

    out = np.lib.format.open_memmap(
        IDX_PATH.with_suffix(".npy"), mode="w+", dtype=np.int32, shape=(n, K))
    out[:] = -1
    aday_sayisi = np.zeros(n, dtype=np.int32)

    refs = np.sort(rows.ref_date.unique())
    ref_of_row = rows.ref_date.to_numpy()
    cell_of_row = rows.cell_id.to_numpy()
    t0 = time.time()

    for ri, ref in enumerate(refs):
        ref_s = float(epoch_seconds(pd.DatetimeIndex([ref]))[0])
        gor = np.flatnonzero((et < ref_s)
                             & (et >= ref_s - GECMIS_YIL * 365.25 * 86400.0))
        satir = np.flatnonzero(ref_of_row == ref)
        if len(gor) == 0 or len(satir) == 0:
            continue
        gt = (ref_s - et[gor]) / 86400.0        # gün
        gla, glo, gmw = ela[gor], elo[gor], emw[gor]

        for b in range(0, len(satir), cell_chunk):
            grup = satir[b:b + cell_chunk]
            cl = np.array([merkez[int(c)][0] for c in cell_of_row[grup]])
            co = np.array([merkez[int(c)][1] for c in cell_of_row[grup]])
            dx = (glo[None, :] - co[:, None]) * 111.32 * np.cos(
                np.radians(cl[:, None]))
            dy = (gla[None, :] - cl[:, None]) * 110.57
            dr = np.sqrt(dx * dx + dy * dy)
            icinde = dr <= R_KM
            w = np.where(icinde,
                         oncul_agirlik(gt[None, :], dr, gmw[None, :]), -1.0)
            aday_sayisi[grup] = icinde.sum(1)
            kk = min(K, w.shape[1])
            ust = np.argpartition(-w, kk - 1, axis=1)[:, :kk]
            # ağırlığa göre sırala (en büyük önce) — kararlı ve okunabilir
            duz = np.take_along_axis(w, ust, axis=1)
            sira = np.argsort(-duz, axis=1)
            ust = np.take_along_axis(ust, sira, axis=1)
            gecerli = np.take_along_axis(w, ust, axis=1) > 0
            blok = np.full((len(grup), K), -1, dtype=np.int32)
            blok[:, :kk] = np.where(gecerli, gor[ust], -1).astype(np.int32)
            out[grup] = blok

        if not quiet and (ri + 1) % 25 == 0:
            gecen = time.time() - t0
            print(f"  [{ri + 1:4d}/{len(refs)}] {gecen / 60:5.1f} dk geçti · "
                  f"kalan ~{gecen / (ri + 1) * (len(refs) - ri - 1) / 60:5.1f} dk")

    out.flush()
    np.save(PROC / "npp_aday_sayisi.npy", aday_sayisi)
    yol = IDX_PATH.with_suffix(".npy")

    kunye = {
        "dosya": yol.name, "sha256": _sha256(yol),
        "ureten_commit": _commit(), "calisma_agaci_kirli": _kirli(),
        "katalog": kat_yol.name, "katalog_sha256": _sha256(kat_yol),
        "tablo": tablo, "n_satir": int(n), "K": K, "R_km": R_KM,
        "gecmis_yil": GECMIS_YIL, "mc": MC,
        "oncul_cekirdek": ONCUL,
        "bagimsizlik": ("Sıralama ÖNCÜL çekirdekle yapıldı; uydurulmuş ETAS "
                        "parametreleri bu modülde HİÇ okunmuyor (V24)."),
        "aday_ortalama": float(aday_sayisi.mean()),
        "aday_medyan": float(np.median(aday_sayisi)),
        "dolu_oran": float((aday_sayisi >= K).mean()),
        "sure_dk": round((time.time() - t0) / 60, 1),
    }
    KUNYE_PATH.write_text(json.dumps(kunye, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    if not quiet:
        print(f"\naday sayısı: ort {kunye['aday_ortalama']:.0f} · "
              f"medyan {kunye['aday_medyan']:.0f} · "
              f"K dolu olan satır oranı %{100 * kunye['dolu_oran']:.1f}")
        print(f"-> {yol}  ({yol.stat().st_size / 1e9:.2f} GB)")
        print(f"-> {KUNYE_PATH}")


def load() -> tuple[np.ndarray, dict]:
    """Dizini ve künyesini okur; sha uyuşmazsa HATA verir (V6'nın veri tarafı)."""
    yol = IDX_PATH.with_suffix(".npy")
    if not yol.exists():
        raise FileNotFoundError(f"{yol} yok — önce npp_index.build()")
    kunye = json.loads(KUNYE_PATH.read_text(encoding="utf-8"))
    if _sha256(yol) != kunye["sha256"]:
        raise RuntimeError(
            "npp_index.npy künyedeki sha256 ile uyuşmuyor — dosya değişmiş "
            "ya da künye bayat. Yeniden üretilmeden kullanılamaz.")
    return np.load(yol, mmap_mode="r"), kunye


if __name__ == "__main__":
    build()
