"""Yeniden üretilebilirlik künyesi.

Manşet taslağının kuralı: künyesiz sayı yayımlanmaz. Bu betik künyeyi üretir --
elle yazılırsa bayatlar, üretilirse bayatlayamaz.

Künye, bir sayının hangi koşullarda üretildiğini eksiksiz tanımlar: hangi
parametreler, hangi kod sürümü, hangi tahmin çıktısı. Bu üçü sabitse sayı
yeniden üretilebilir (analitik yöntem deterministiktir).

VAKA KAYDI

**Vaka 1 — 24 Ağustos 2026, ilk çalıştırma.** Künye üreteci ilk testinde
KENDİSİNİ yakaladı: betik henüz commit edilmemişti, dolayısıyla çalışma ağacı
kirliydi ve "üreten commit" alanı o anki durumu yansıtmıyordu. Üreteç
"KİRLİ -- künye güvenilmez" damgasını bastı.

Değerlendirme: mekanizma kurucusuna da istisna tanımıyor. Bu, sayı haritası
koruyucusunun ilk vakasıyla aynı sınıftan bir doğrulamadır -- bir kontrolün
kendi yazarını da durdurması, kontrolün gerçekten çalıştığının en ucuz kanıtıdır.

Kullanım:
    python scripts/17_fingerprint.py --setup haftalik-analitik
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

SETUPS = {
    "aylik-1000": ("etas_monthly", "aylık başlangıç, 30g pencere, simülasyon n_sim=1000"),
    "aylik-analitik": ("etas_analytic_monthly", "aylık başlangıç, 30g pencere, analitik"),
    "haftalik-analitik": ("etas_analytic_weekly",
                          "haftalık örtüşmeyen 7g pencere, analitik"),
}


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def dir_sha(d: Path) -> tuple[str, int]:
    """Dizin özeti: dosya adlarına göre sıralı, içeriklerin birleşik özeti."""
    files = sorted(d.glob("shard_*.csv"))
    h = hashlib.sha256()
    for f in files:
        h.update(f.name.encode())
        h.update(bytes.fromhex(sha(f)))
    return h.hexdigest(), len(files)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--setup", required=True, choices=sorted(SETUPS))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    sub, desc = SETUPS[a.setup]
    params_path = PROC / "etas_params.json"
    params = json.loads(params_path.read_text())
    out_dir = PROC / sub
    out_sha, n_shard = dir_sha(out_dir) if out_dir.exists() else ("YOK", 0)

    git = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                         text=True, cwd=ROOT).stdout.strip()
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True,
                           text=True, cwd=ROOT).stdout.strip()

    sys.path.insert(0, str(ROOT))
    from src.models.etas_params import EtasParams
    ep = EtasParams.load()

    info = {
        "kurulum kimliği": a.setup,
        "tanım": desc,
        "ETAS parametreleri (sha256)": sha(params_path),
        "kalibrasyon penceresi": f'{params["timewindow_start"]} .. {params["timewindow_end"]}',
        "tamlık kipi": params.get("mc_mode", "?"),
        "dallanma (nominal / efektif)": f"{ep.branching_nominal:.4f} / "
                                        f"{ep.branching_effective:.4f}",
        "b (ETAS beta'dan)": f"{ep.b_value:.4f}",
        "mu": "başlangıç başına yerel kestirim (n_hat / alan / süre)",
        "tahmin çıktısı": f"{sub}/ ({n_shard} parça)",
        "tahmin çıktısı (sha256)": out_sha,
        # "Deterministik" kelimesi bir kez YANLIŞ çıktı (V16): expected_counts
        # bit-özdeşti ama uçtan uca yol, EM adımındaki tohumsuz local_params'ı
        # içeriyordu. Beyan artık mekanizmayı adlandırıyor -- iddia, testin
        # sınadığı kapsamla birebir örtüşsün.
        "rastgelelik": (
            "analitik hesapta yok; ETAS durumu kuran EM adımı TOHUMLU "
            "(tohum = başlangıç tarihi, etas_baseline.simulation_seed). "
            "Uçtan uca bit-özdeşlik test edilir: "
            "test_local_params_is_deterministic + "
            "test_result_is_bit_identical_across_runs"
            if "analitik" in a.setup
            else "simülasyon; tohum başlangıç tarihinden türetilir"),
        "üreten commit": git,
        "çalışma ağacı": "temiz" if not dirty else "KİRLİ — künye güvenilmez",
    }
    if a.json:
        print(json.dumps(info, indent=2, ensure_ascii=False))
    else:
        width = max(len(k) for k in info)
        for k, v in info.items():
            print(f"{k:<{width}} : {v}")
    if dirty:
        print("\n! Çalışma ağacı kirli: künye, commit'lenmemiş değişiklikleri "
              "yansıtmaz. Yayımlamadan önce commit edin.", file=sys.stderr)


if __name__ == "__main__":
    main()
