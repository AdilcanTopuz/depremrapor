"""Sızıntı kanaryasının kendi testleri — kural 9 kanaryaya uygulanır.

Bir korumanın "kurulu" sayılması için REDDETTİĞİ bir deney gösterilmelidir.
Kanarya için bu, ALARMIN ÇALDIĞI bir durumdur.

NOT: `check_alarm`'ın açıklaması bu dosyaya atıf yapıyordu ama dosya YOKTU
(2026-08-25'te fark edildi). Var olmayan bir doğrulamaya atıf, V13 sınıfı bir
hatadır: iddia, kanıttan önce yazılmış olur. Dosya bu yüzden yazıldı.
"""
import pytest

from src.eval import leakage_canary as C


# --- alarm ölçütü: REDDETTİĞİ durumlar -------------------------------------

def test_alarm_fires_on_absolute_threshold():
    """Mutlak eşiği aşan skor alarm vermeli."""
    r = C.check_alarm(0.95, "deneme", raise_on_alarm=False, taban=0.78)
    assert r["alarm"]
    assert any("mutlak eşik" in x for x in r["reasons"])


def test_alarm_fires_on_jump_over_clean_baseline():
    """Temiz tabanı 0,10'dan fazla geçmek — mutlak eşiğin ALTINDA bile — alarm."""
    r = C.check_alarm(0.89, "deneme", raise_on_alarm=False, taban=0.78)
    assert r["alarm"], "0,89 mutlak eşiğin altında ama tabanı +0,11 geçiyor"
    assert not any("mutlak eşik" in x for x in r["reasons"])


def test_alarm_silent_on_plausible_score():
    """Makul bir skor alarm vermemeli — kanarya her şeye ötmez."""
    assert not C.check_alarm(0.80, "deneme", raise_on_alarm=False,
                             taban=0.78)["alarm"]


def test_alarm_raises_when_asked():
    with pytest.raises(C.LeakageAlarm):
        C.check_alarm(0.99, "deneme", raise_on_alarm=True, taban=0.78)


def test_baseline_is_matched_not_constant():
    """Taban parametreliDİR: tablo değişince kendini günceller.

    Eskiden sabitti (0,7909, ETAS TEST dönemi) ve eşleşmemiş bir
    karşılaştırmaydı. Aynı AUC, tabana göre farklı hüküm almalı.
    """
    auc = 0.87
    assert C.check_alarm(auc, raise_on_alarm=False, taban=0.70)["alarm"]
    assert not C.check_alarm(auc, raise_on_alarm=False, taban=0.80)["alarm"]


def test_thresholds_are_the_declared_ones():
    """Eşikler İLAN EDİLDİĞİ gibi kalmalı — sonuca göre oynatılmadığının kaydı."""
    assert C.ALARM_AUC == 0.90
    assert C.ALARM_JUMP == 0.10


# --- test bölümünün YOKLUĞU ------------------------------------------------

def test_load_drops_the_test_split(monkeypatch):
    """`_load` test bölümünü YÜKLER YÜKLEMEZ silmeli.

    Söz değil veri yokluğu: kanarya kodu ne kadar yanlış yazılırsa yazılsın
    olmayan bölümü okuyamaz (bkz. docs/TEST_DOKUNUSLARI.md, Düzeltme 1).
    """
    import src.models.lgbm as L

    sahte = {"train": "TR", "val": "VA", "test": "TE"}
    monkeypatch.setattr(L, "load_dataset", lambda *a, **k: dict(sahte))
    out = C._load("herhangi")
    assert "test" not in out, "test bölümü silinmedi"
    assert set(out) == {"train", "val"}


# --- ağaçlarda etkisiz olan kanarya SESSİZCE GEÇMEMELİ ---------------------

def test_indirect_canary_refuses_for_trees():
    """DOLAYLI kanarya ağaç modelinde çağrılırsa HATA vermeli, 'temiz' değil.

    Ölçekleme sızıntısı ağaçlarda var olmayan bir kanaldır (monoton dönüşüme
    duyarsızlık). Sessizce 'fark yok' döndürmek, var olmayan bir korumanın
    varlığını ima ederdi.
    """
    with pytest.raises(NotImplementedError):
        C.canary_indirect()
