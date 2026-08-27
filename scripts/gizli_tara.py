# -*- coding: utf-8 -*-
"""Kamuya açılış öncesi gizli dizi / kişisel veri taraması.

    python -m scripts.gizli_tara            # izlenen dosyaları tarar
    python -m scripts.gizli_tara <dizin>    # bir dışa aktarım dizinini tarar

NEDEN BU BETİK VAR. Tarama bir kez elle yapılıp "temiz" denseydi, sonraki
her değişiklikte yeniden yapılması gerekirdi ve yapılmazdı. Betik, tarama
ölçütünü yazılı ve tekrarlanabilir kılar.

NEDEN ÇIKTISI "TEMİZ/KİRLİ" DEĞİL. Desen tabanlı tarama yanlış pozitif
üretir: bir sha256'nın orta parçası T.C. kimlik numarasına, bir ondalık
sayının basamakları telefon numarasına benzer. Bu betik KARAR VERMEZ,
bulguyu ve bulunduğu satırı gösterir; kararı bakan verir. "0 bulgu"
demenin tek dürüst yolu, her bulguya bakılmış olmasıdır.
"""
from __future__ import annotations

import collections
import pathlib
import re
import subprocess
import sys

DESENLER = {
    "API anahtarı / token": re.compile(
        r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token"
        r"|bearer\s+[A-Za-z0-9._-]{20,}|xox[baprs]-|ghp_[A-Za-z0-9]{20,}"
        r"|github_pat_[A-Za-z0-9_]{20,}|AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,})"),
    "özel anahtar bloğu": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "e-posta": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "mutlak yerel yol": re.compile(
        r"(?i)([A-Z]:[\\/](?:Users|WEB_PROJECTS)|/Users/[a-z]|/home/[a-z])"),
    "IP adresi": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    "telefon (TR)": re.compile(
        r"(?:\+90|0)\s?5\d{2}[\s.-]?\d{3}[\s.-]?\d{2}[\s.-]?\d{2}"),
    "TCKN benzeri": re.compile(r"(?<!\d)[1-9]\d{10}(?!\d)"),
}

# BEYAZ LİSTE DAR TUTULUR. Geniş bir beyaz liste, taramayı sessizce
# işlevsizleştirir; buraya yalnızca kaynağı açılıp doğrulanmış,
# kişisel olmayan değerler girer.
BEYAZ = (
    "noreply@anthropic.com",          # devrolmayan geçmişte kalır
    "bot@users.noreply.github.com",   # Actions bot kimliği
    "deprem@afad.gov.tr",             # AFAD kurumsal başvuru adresi
    "licensing@globalquakemodel.org",  # GEM kurumsal lisans adresi
    "127.0.0.1", "0.0.0.0", "example.com",
)


def _dosyalar(kok: pathlib.Path) -> list[pathlib.Path]:
    """İzlenen dosyalar; git yoksa dizindeki her şey."""
    try:
        ck = subprocess.run(["git", "ls-files"], cwd=kok,
                            capture_output=True, text=True, check=True)
        return [kok / x for x in ck.stdout.split("\n") if x.strip()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [p for p in kok.rglob("*")
                if p.is_file() and ".git" not in p.parts]


def tara(kok: pathlib.Path) -> dict[str, list[tuple[str, int, str]]]:
    bulgu: dict[str, list] = collections.defaultdict(list)
    for p in _dosyalar(kok):
        if not p.is_file():
            continue
        try:
            t = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for ad, rx in DESENLER.items():
            for m in rx.finditer(t):
                s = m.group(0)
                if any(b in s for b in BEYAZ):
                    continue
                bulgu[ad].append(
                    (str(p.relative_to(kok)), t[:m.start()].count("\n") + 1, s))
    return bulgu


def main(argv: list[str]) -> int:
    kok = pathlib.Path(argv[1]).resolve() if len(argv) > 1 else \
        pathlib.Path(__file__).resolve().parents[1]
    sys.stdout.reconfigure(encoding="utf-8")
    n = len(_dosyalar(kok))
    print(f"Taranan dosya: {n}  ({kok})\n")
    bulgu = tara(kok)
    for ad in DESENLER:
        v = bulgu.get(ad, [])
        if not v:
            print(f"  eşleşme yok   {ad}")
            continue
        print(f"  {len(v):5} eşleşme  {ad}")
        for dosya, sat, s in v[:12]:
            print(f"               {dosya}:{sat}  ->  {s[:78]}")
        if len(v) > 12:
            print(f"               ... {len(v) - 12} tane daha")
    print("\nBu çıktı bir karar değildir. Her eşleşmenin kaynağına bakınız;")
    print("bir sha256 parçası TCKN'ye, bir ondalık sayı telefona benzeyebilir.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
