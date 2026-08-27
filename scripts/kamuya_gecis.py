# -*- coding: utf-8 -*-
"""Kamuya açık depo için temiz dışa aktarım (squash-import hazırlığı).

    python -m scripts.kamuya_gecis <hedef-dizin>
    python -m scripts.kamuya_gecis <hedef-dizin> --commit "Adı" "e-posta"

NE YAPAR. Çalışma ağacındaki **izlenen dosyaları** boş bir dizine kopyalar,
kamuya bakan düzenlemeleri uygular ve isteğe bağlı olarak tek commit'lik
bir git deposu kurar.

NEDEN `git ls-files`. Dosyalar elle seçilseydi, seçim yapılan her yerde bir
şey unutulurdu. İzlenen dosya listesi zaten deponun kendi beyanıdır:
`.gitignore`'daki her şey (4 GB'lık ham katalog, `.venv`, `.claude/`,
`data/publish`, üretilmiş HTML) **tanım gereği** dışarıda kalır. Dışlama
listesi tutulmaz; tutulan bir liste kaynağından ayrışır.

NEDEN GEÇMİŞ TAŞINMAZ. Gerekçesi `DEVIR.md` dosyasındadır.
"""
from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys

KOK = pathlib.Path(__file__).resolve().parents[1]

# Kamuya bakan yüz değişir; araştırma günlüğü belgelere iner.
TASIMALAR = (
    ("README.md", "docs/PROJE_NOTLARI.md"),
    ("docs/README_KAMU.md", "README.md"),
)


def _izlenen() -> list[str]:
    ck = subprocess.run(["git", "ls-files"], cwd=KOK,
                        capture_output=True, text=True, check=True)
    return [x for x in ck.stdout.split("\n") if x.strip()]


def disa_aktar(hedef: pathlib.Path) -> dict:
    if hedef.exists() and any(hedef.iterdir()):
        raise SystemExit(f"! {hedef} boş değil — üzerine yazılmaz")
    hedef.mkdir(parents=True, exist_ok=True)

    dosyalar = _izlenen()
    for d in dosyalar:
        kaynak = KOK / d
        if not kaynak.is_file():      # silinmiş ama indekste kalmış
            continue
        varis = hedef / d
        varis.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kaynak, varis)

    # Kamuya bakan düzenlemeler. İKİ AŞAMALI: taşımalar birbirinin hedefine
    # yazıyor (README.md -> docs/PROJE_NOTLARI.md ve docs/README_KAMU.md ->
    # README.md). Tek geçişte yapılırsa ikinci taşıma birincinin çıktısını
    # ezer; önce hepsi geçici ada alınır, sonra yerine konur.
    ara: list[tuple[pathlib.Path, pathlib.Path]] = []
    for eski, yeni in TASIMALAR:
        e = hedef / eski
        if not e.exists():
            raise SystemExit(f"! taşınacak dosya yok: {eski}")
        gecici = hedef / (eski + ".gecici")
        e.rename(gecici)
        ara.append((gecici, hedef / yeni))
    for gecici, yeni in ara:
        yeni.parent.mkdir(parents=True, exist_ok=True)
        gecici.rename(yeni)

    # eski koşu tetikleri yeni depoda anlamsız
    tetik = hedef / ".github" / "tetik"
    if tetik.exists():
        tetik.write_text("yeni depo — ilk koşu elle tetiklenir\n",
                         encoding="utf-8")

    boy = sum(p.stat().st_size for p in hedef.rglob("*") if p.is_file())
    return {"dosya": sum(1 for p in hedef.rglob("*") if p.is_file()),
            "bayt": boy}


def dogrula(hedef: pathlib.Path) -> list[str]:
    """Aktarımdan sonra bakılması gerekenler. Boş liste = itiraz yok."""
    sorun = []
    if (hedef / ".claude").exists():
        sorun.append(".claude/ dizini aktarıma girmiş")
    if (hedef / ".venv").exists():
        sorun.append(".venv/ dizini aktarıma girmiş")
    # DİZİNİN VARLIĞI DEĞİL, İÇERİĞİ ÖLÇÜLÜR. `data/raw/.gitkeep` izlenen bir
    # işaretçidir ve taşınMALIdır: hat oraya yazar, dizin yoksa ilk koşu
    # düşer. İlk yazımda ölçüt "dizin var mı" idi ve bu işaretçiye takıldı --
    # yani doğru bir dosyayı yanlış bulgu olarak gösterdi.
    for dizin, ne in (("raw", "ham katalog"), ("publish", "yayın çıktısı")):
        d = hedef / "data" / dizin
        if not d.exists():
            continue
        icerik = [p for p in d.rglob("*") if p.is_file() and p.name != ".gitkeep"]
        if icerik:
            sorun.append(f"data/{dizin} {ne} aktarıma girmiş "
                         f"({len(icerik)} dosya, ilki: {icerik[0].name})")
    for gerek in ("LICENSE", "NOTICE", "DEVIR.md", "README.md",
                  ".github/workflows/yayin.yml"):
        if not (hedef / gerek).exists():
            sorun.append(f"eksik: {gerek}")
    if (hedef / "docs" / "README_KAMU.md").exists():
        sorun.append("docs/README_KAMU.md hâlâ duruyor — taşınmamış")
    return sorun


def main(argv: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    if len(argv) < 2:
        print(__doc__)
        return 2
    hedef = pathlib.Path(argv[1]).resolve()

    kirli = subprocess.run(["git", "status", "--porcelain"], cwd=KOK,
                           capture_output=True, text=True).stdout.strip()
    if kirli:
        raise SystemExit(
            "! çalışma ağacı kirli. Devredilen şey, DENETLENEBİLİR TEK BİR\n"
            "  durumdur; hangi durumun devredildiği belirsizse devir kaydı\n"
            "  da belirsizdir. Önce commit'leyin.\n\n" + kirli)

    ozet = disa_aktar(hedef)
    print(f"-> {hedef}")
    print(f"   {ozet['dosya']} dosya · {ozet['bayt'] / 1048576:.1f} MB")

    sorun = dogrula(hedef)
    if sorun:
        print("\n! DOĞRULAMA İTİRAZLARI:")
        for s in sorun:
            print("   -", s)
        return 1
    print("   doğrulama: itiraz yok")

    if "--commit" in argv:
        i = argv.index("--commit")
        ad, eposta = argv[i + 1], argv[i + 2]
        gun = subprocess.run(["git", "log", "-1", "--format=%cs"], cwd=KOK,
                             capture_output=True, text=True).stdout.strip()
        for k in (["init", "-b", "main"],
                  ["config", "user.name", ad],
                  ["config", "user.email", eposta],
                  ["add", "-A"]):
            subprocess.run(["git"] + k, cwd=hedef, check=True,
                           capture_output=True)
        mesaj = (
            f"depremrapor — özel geliştirme arşivinin {gun} tarihli hâli\n"
            "\n"
            "Bu depo, özel geliştirme arşivinin son halidir; önceki künye ve\n"
            "commit atıfları arşiv repo'suna aittir. Geçmiş taşınmadı,\n"
            "gerekçesi DEVIR.md dosyasındadır.\n"
            "\n"
            "Künye zinciri kopmadı, devredildi: bundan sonraki künyeler bu\n"
            "deponun hash'leriyle üretilir.\n")
        subprocess.run(["git", "commit", "-m", mesaj], cwd=hedef, check=True,
                       capture_output=True)
        print(f"   tek commit atıldı: {ad} <{eposta}>")
        print("\n   Şimdi gizli dizi taraması:")
        print(f"     python -m scripts.gizli_tara {hedef}")
    else:
        print("\n   commit atılmadı (--commit \"Ad\" \"e-posta\" ile atılır)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
