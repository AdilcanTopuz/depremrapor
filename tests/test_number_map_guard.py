"""Sayı haritası koruyucusunun gerçekten koruduğunun testi.

Bir koruyucu, koruduğu sanılıp korumuyorsa korumamaktan KÖTÜDÜR: yanlış güven
verir. Bu testler koruyucunun hem yakaladığını hem yanlış alarm vermediğini
sabitler.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_number_map as g  # noqa: E402


def _run(monkeypatch, files):
    monkeypatch.setattr(g, "changed_files", lambda staged: files)
    return g.check()


def test_watched_change_without_map_is_rejected(monkeypatch):
    """İzlenen dosya değişmiş, harita değişmemiş -> RED."""
    assert _run(monkeypatch, ["src/models/etas_branching.py"]) == 1


def test_watched_change_with_map_passes(monkeypatch):
    """İkisi birlikte değişmiş -> geçer."""
    assert _run(monkeypatch, ["src/models/etas_branching.py",
                              "docs/SAYI_HARITASI.md"]) == 0


def test_unwatched_change_passes(monkeypatch):
    """İlgisiz dosya -> yanlış alarm verilmemeli."""
    assert _run(monkeypatch, ["README.md", "notebooks/01_eda.ipynb"]) == 0


def test_no_changes_passes(monkeypatch):
    assert _run(monkeypatch, []) == 0


def test_params_file_is_watched():
    """Parametre dosyası MUTLAKA izlenmeli.

    Bayatlayan sayı tam olarak buradan gelmişti: parametreler yeniden
    kalibre edildi, CSEP sonuçları eski parametrelerle kaldı.
    """
    assert "data/processed/etas_params.json" in g.WATCHED


def test_all_watched_paths_exist():
    """İzleme listesi gerçek dosyaları göstermeli.

    Var olmayan bir yolu izlemek, koruyucunun o alanda sessizce devre dışı
    kalması demektir.
    """
    missing = [p for p in g.WATCHED if not (ROOT / p).exists()]
    assert not missing, f"izleme listesinde olmayan yollar: {missing}"


def test_hook_KURUCUSU_calisiyor(tmp_path):
    """Deponun garanti edebileceği şey KURUCUDUR, kurulum değil.

    `.git/hooks` git ile TAŞINMAZ; her klonda yeniden kurulur. Dolayısıyla
    "kanca kurulu" bir depo özelliği değil, yerel bir kurulum durumudur ve
    bir klonda düşmesi kusur sayılmaz. Depo yalnızca şunu garanti edebilir:
    kurucu çağrıldığında ÇALIŞAN bir kanca bırakır.

    Bu ayrım, yeni depoya geçişte ortaya çıktı: temiz bir klonda 16 "veri
    yok" hatasının arasında bu test de düşüyordu ve gerçek bulgu ile
    gürültü ayırt edilemiyordu.
    """
    sahte = tmp_path / "depo"
    (sahte / ".git" / "hooks").mkdir(parents=True)
    kaynak = (ROOT / "scripts" / "check_number_map.py").read_text(encoding="utf-8")
    (sahte / "scripts").mkdir()
    (sahte / "scripts" / "check_number_map.py").write_text(kaynak, encoding="utf-8")

    ck = subprocess.run(
        [sys.executable, "scripts/check_number_map.py", "--install"],
        cwd=sahte, capture_output=True, text=True)
    assert ck.returncode == 0, ck.stderr or ck.stdout

    hook = sahte / ".git" / "hooks" / "pre-commit"
    assert hook.exists(), "kurucu çalıştı ama kanca bırakmadı"
    assert "check_number_map" in hook.read_text(encoding="utf-8")


def test_hook_bu_klonda_kurulu_mu():
    """Bilgilendirme: bu klonda kanca kurulu mu?

    Kurulu değilse ATLANIR (bir klonun yerel durumu depo kusuru değildir),
    ama sebebi ve çözümü yazılır ki sessizce korumasız çalışılmasın.
    """
    hook = ROOT / ".git" / "hooks" / "pre-commit"
    if not hook.exists():
        pytest.skip("bu klonda pre-commit kancası kurulu değil — kurmak için: "
                    "python scripts/check_number_map.py --install")
    assert "check_number_map" in hook.read_text(encoding="utf-8"),         "pre-commit kancası var ama sayı haritası koruyucusunu çağırmıyor"


def test_every_watched_path_is_git_tracked():
    """İzlenen her yol GIT TARAFINDAN İZLENİYOR olmalı.

    Koruyucu `git diff --name-only` çıktısına bakar. Gitignore edilmiş ve
    izlenmeyen bir dosya o çıktıda HİÇBİR ZAMAN görünmez -- yani onu izleme
    listesine koymak koruma sağlamaz, koruma SANRISI sağlar.

    Ölçüldü (24 Ağustos 2026): `etas_params.json` izlenmiyordu. Dosya
    değiştirildi ve koruyucu 0 (geç) döndürdü. İzleme listesinde olması,
    `test_params_file_is_watched` testinin geçmesi ve hook'un kurulu olması --
    üçü birden doğruydu ve koruma yine de boştu.

    Bu test o boşluğu kapatır: liste ile mekanizmanın FİİLEN örtüştüğünü sınar.
    """
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         cwd=ROOT)
    tracked = set(out.stdout.replace("\\", "/").splitlines())
    missing = [p for p in g.WATCHED if p not in tracked]
    assert not missing, (
        f"izleme listesinde olup git tarafından İZLENMEYEN yollar: {missing} -- "
        "bu yollar için koruyucu asla tetiklenmez")


def test_result_jsons_are_tracked():
    """Sayı üreten json çıktıları izlenmeli (künye zinciri).

    İzlenmezlerse yeniden üretimde önceki sürüm kaybolur ve
    "beklenen/gerçekleşen etki" karşılaştırması yapılamaz. cell_id
    düzeltmesinde tam olarak bu yaşandı: 5. ondalıktaki kayma doğrudan
    karşılaştırılamadı.
    """
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         cwd=ROOT)
    tracked = set(out.stdout.replace("\\", "/").splitlines())
    gerekli = [
        "data/processed/etas_params.json",
        "data/processed/daily_backtest.json",
        "data/processed/gain_breakdown.json",
        "data/processed/csep_results.json",
    ]
    missing = [p for p in gerekli if p not in tracked]
    assert not missing, f"izlenmeyen sonuç dosyaları: {missing}"
