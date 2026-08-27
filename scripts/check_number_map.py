"""Sayı haritasının bayatlamasını ENGELLEYEN kontrol.

docs/SAYI_HARITASI.md'nin kuralı şuydu: "her kurulum ya da yöntem değişikliğinde
aynı commit'te güncellenir." Bu kural SÜRECE güveniyordu -- yani unutulabilirdi.
Bu betik onu MEKANİZMAYA çevirir.

Gerekçe: bu projede bir sayı bir kez bayatladı (CSEP sonuçları STAI yeniden
kalibrasyonundan önceki parametrelerle üretilmişti ve README'de duruyordu).
Fark edilmesi saatler aldı ve yalnızca dosya zaman damgalarına bakınca mümkün
oldu. Sayı haritası tam olarak bunu önlemek için var; kendisi bayatlarsa amacını
yitirir.

Kural: izlenen dosyalardan biri değişmiş ama SAYI_HARITASI.md değişmemişse
commit reddedilir. Bilinçli olarak atlamak gerekiyorsa:

    git commit --no-verify

VAKA KAYDI
----------

Bu bölüm, "bu hook gereksiz sürtünme mü?" tartışması açılırsa cevabın yerinde
durması içindir. Her gerçek yakalama buraya işlenir.

**Vaka 1 — 24 Ağustos 2026, kurulumundan ~3 dakika sonra.**
`src/eval/gain_breakdown.py` değiştirildi (MDE raporlaması eklendi) ve
`docs/SAYI_HARITASI.md` güncellenmeden commit denendi. Hook commit'i reddetti.

Çözüm: haritanın "son güncelleme" satırına kayıt düşüldü -- bu değişikliğin
hiçbir sayıyı etkilemediği, yalnızca raporlamaya güç beyanı eklediği yazıldı.
Toplam maliyet: bir satır.

Değerlendirme: YANLIŞ ALARM DEĞİL. Değişiklik gerçekten sayı raporlamasına
dokunuyordu ve "etkilemiyor" kaydının kendisi de bir bilgidir -- altı ay sonra
"MDE ne zaman geldi, sayıları değiştirdi mi?" sorusunun cevabı orada duruyor.
Hook'un istediği şey haritayı doldurmak değil, DÜŞÜNMEYİ zorunlu kılmaktı.

**Vaka 2 — 24 Ağustos 2026, aynı gün.**
`src/config.py` değiştirildi (ızgara sınır durumunun belgelenmesi) ve harita
güncellenmeden commit denendi. Hook yine reddetti.

Çözüm: haritaya "2 hücre ayıklanıyor, mevcut sayılara etkisi ölçülen SIFIR"
kaydı düşüldü.

Değerlendirme: bu vaka birincisinden DAHA değerli. `config.cell_id` kanonik bir
fonksiyondur ve tüm ızgara çıktıları ondan türer; oraya dokunup sayı haritasına
bakmamak, tam olarak bu koruyucunun engellemek için var olduğu şeydir. Etki bu
kez sıfır çıktı -- ama bunu ÖLÇEREK öğrendik, çünkü hook ölçmeye zorladı.

ORTAK DERS
----------

Her iki vakada da cevap "etki yok" çıktı. Ve her iki vakada da bunu ÖLÇEREK
öğrendik.

**Hook'un değeri yakaladığı hatalar değil, zorunlu kıldığı ölçümlerdir.**

Koruyucu "harita doldur" demiyor; "bu değişiklik hangi sayıyı etkiliyor?" diye
soruyor. Cevap çoğu zaman "hiçbirini" olacaktır. Kıymetli olan cevabın kendisi
değil, sorunun sorulmuş olmasıdır -- çünkü sorulmadığı gün cevap "hiçbirini"
olmayacak ve kimse fark etmeyecektir.

Kurulum:
    python scripts/check_number_map.py --install
Çalıştırma (CI):
    python scripts/check_number_map.py --ci
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = "docs/SAYI_HARITASI.md"

# Değişmesi sayı haritasını etkileyebilecek dosyalar: kurulum tanımları,
# parametreler, tahmin üreten ve değerlendiren kod.
WATCHED = [
    "data/processed/etas_params.json",
    "src/config.py",
    "src/models/etas_baseline.py",
    "src/models/etas_analytic.py",
    "src/models/etas_branching.py",
    "src/models/etas_params.py",
    "src/eval/csep_tests.py",
    "src/eval/daily_backtest.py",
    "src/eval/gain_breakdown.py",
    "src/operational/forecast_now.py",
    "src/operational/score_archive.py",
    "scripts/12_analytic_forecast.py",
]

HOOK = """#!/bin/sh
# Sayı haritası bayatlama kontrolü (scripts/check_number_map.py)
python scripts/check_number_map.py || exit 1
"""


def changed_files(staged: bool) -> list[str]:
    cmd = ["git", "diff", "--name-only"]
    if staged:
        cmd.append("--cached")
    out = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]


def check(staged: bool = True) -> int:
    files = changed_files(staged)
    if not files:
        return 0
    hits = [f for f in files if f in WATCHED]
    if not hits:
        return 0
    if MAP in files:
        return 0
    print("HATA: sayı haritası güncellenmemiş.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Değişen ve haritayı etkileyebilecek dosyalar:", file=sys.stderr)
    for f in hits:
        print(f"  - {f}", file=sys.stderr)
    print("", file=sys.stderr)
    print(f"{MAP} de güncellenmeli: hangi sayılar bu değişiklikten etkilendi,", file=sys.stderr)
    print("hangileri artık GEÇERSİZ, 'son güncelleme / olay' sütunu ne diyor?", file=sys.stderr)
    print("", file=sys.stderr)
    print("Bu değişiklik hiçbir sayıyı etkilemiyorsa haritanın 'son güncelleme'", file=sys.stderr)
    print("satırına dokunmak yeterlidir. Bilinçli atlamak için:  git commit --no-verify",
          file=sys.stderr)
    return 1


def install() -> int:
    hooks = ROOT / ".git" / "hooks"
    if not hooks.exists():
        print(f"! {hooks} yok", file=sys.stderr)
        return 1
    dst = hooks / "pre-commit"
    dst.write_text(HOOK, encoding="utf-8", newline="\n")
    try:
        dst.chmod(0o755)
    except OSError:
        pass
    print(f"kuruldu -> {dst}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true", help="pre-commit hook kur")
    ap.add_argument("--ci", action="store_true",
                    help="CI kipi: staged değil, çalışma ağacındaki değişiklikler")
    a = ap.parse_args()
    if a.install:
        return install()
    return check(staged=not a.ci)


if __name__ == "__main__":
    sys.exit(main())
