# -*- coding: utf-8 -*-
"""Ham katalog yazımının küçülmeye karşı korunması.

V38'de hattın kendi girdisini imha edebildiği görülmüş ve monotonluk
koruması eklenmişti -- ama o koruma YAYIM yolundaydı. Yapabildiği şey
yayımı durdurmaktı; yapamadığı şey, indiricinin iyi dosyanın üzerine
kırpılmış bir dosya yazmasını engellemekti.

28 Ağustos 2026'da tam bu oldu: KOERI sunucusu yılların çoğuna yanıt
vermedi, indirici eksikleri sessizce atladı, 19.339 satırı 72.473 satırlık
dosyanın üzerine yazdı ve 0 ile çıktı. Yayım korumadan döndü, ham dosya
gitti.

Ders: bir kaynağı korumak, onu KULLANAN yolu değil YAZAN yolu korumakla
olur.
"""
from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from src.ingest.ham_yaz import HamKatalogKuculdu, guvenli_yaz


def _n(yol: pathlib.Path) -> int:
    with yol.open("rb") as f:
        return max(sum(1 for _ in f) - 1, 0)


def test_ilk_yazim_serbest(tmp_path):
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(10)}), y)
    assert _n(y) == 10


def test_buyume_ve_esitlik_kabul(tmp_path):
    """Katalog güncellemesi doğal olarak büyür ya da aynı kalır."""
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(10)}), y)
    guvenli_yaz(pd.DataFrame({"a": range(25)}), y)
    assert _n(y) == 25
    guvenli_yaz(pd.DataFrame({"a": range(25)}), y)
    assert _n(y) == 25


def test_KUCULME_REDDEDILIR_ve_dosya_KORUNUR(tmp_path):
    """Kural 9: korumanın reddettiği VE dosyayı koruduğu gösterilir.

    Reddetmek tek başına yetmez -- reddederken dosyayı bozmuş olsaydı
    koruma zararlı olurdu.
    """
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(100)}), y)
    with pytest.raises(HamKatalogKuculdu) as e:
        guvenli_yaz(pd.DataFrame({"a": range(40)}), y)
    assert "100" in str(e.value) and "40" in str(e.value)
    assert _n(y) == 100, "reddetti ama dosyayı bozdu"


def test_bilincli_kucultme_MUMKUN_ama_sessiz_degil(tmp_path):
    y = tmp_path / "k.csv"
    guvenli_yaz(pd.DataFrame({"a": range(100)}), y)
    guvenli_yaz(pd.DataFrame({"a": range(40)}), y, izin_kucultme=True)
    assert _n(y) == 40


def test_BUTUN_indiriciler_bu_yoldan_yaziyor():
    """Koruma, yalnızca hatırlanan indiricide değil HEPSİNDE olmalı.

    Tek bir betik doğrudan `to_csv` çağırırsa koruma orada yoktur ve
    kusur oradan geri gelir.
    """
    kok = pathlib.Path(__file__).resolve().parents[1] / "scripts"
    for ad in ("01_download_afad.py", "02_download_usgs.py",
               "02b_download_emsc.py", "02c_download_koeri.py"):
        metin = (kok / ad).read_text(encoding="utf-8")
        assert "guvenli_yaz(" in metin, f"{ad}: korumadan geçmiyor"
        kod = "\n".join(s for s in metin.splitlines()
                        if not s.strip().startswith("#"))
        assert ".to_csv(" not in kod, \
            f"{ad}: ham katalogu doğrudan to_csv ile yazıyor"


def test_INDIRICILER_BETIK_OLARAK_CALISIYOR():
    """Hattın çağırdığı BİÇİMDE çalıştıklarını gösterir.

    V60'ın kaynağı: `guvenli_yaz` korumasını eklerken dört indiriciye
    `from src.ingest...` importu koydum. Testler geçti, çünkü testler modülü
    doğrudan içe aktarıyor ve o sırada depo kökü zaten sys.path'te. Ama hat
    betikleri `python scripts/xx.py` diye çağırıyor; o zaman sys.path[0]
    `scripts/` olur ve `src` görünmez.

    Sonuç: üç kaynağın üçü de ModuleNotFoundError ile çöktü ve ~20 koşu
    boyunca hiçbir yayın yapılamadı. Bir betiği DEĞİŞTİRİP bir kez bile
    ÇALIŞTIRMAMIŞ olmanın bedeli.

    `--help` ağ kullanmaz; sınanan şey yalnızca modülün ayağa kalkabilmesi.
    """
    import subprocess
    import sys

    kok = pathlib.Path(__file__).resolve().parents[1]
    for ad in ("01_download_afad.py", "02_download_usgs.py",
               "02b_download_emsc.py", "02c_download_koeri.py"):
        r = subprocess.run([sys.executable, f"scripts/{ad}", "--help"],
                           cwd=kok, capture_output=True, text=True)
        assert r.returncode == 0, (
            f"scripts/{ad} betik olarak ayağa kalkmıyor:\n"
            f"{(r.stderr or r.stdout).strip()[-400:]}")


def _afad_modulu():
    import importlib.util

    yol = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "01_download_afad.py"
    spec = importlib.util.spec_from_file_location("afad_indirici", yol)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class _Yanit:
    def __init__(self, veri, status_code=200):
        self.veri = veri
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise OSError(f"HTTP {self.status_code}")

    def json(self):
        return self.veri


class _Oturum:
    """Açık AFAD oturumu (`afad_sid` çerezi var); Init yeni çerez verir."""

    def __init__(self):
        self.cookies = {"afad_sid": "gecerli"}
        self.init_sayisi = 0

    def get(self, url, **k):
        assert url.endswith("Session/Init")
        self.init_sayisi += 1
        self.cookies["afad_sid"] = f"yeni{self.init_sayisi}"
        return _Yanit(None, 204)


def test_AFAD_ALINAMAYAN_AY_BOS_AY_SAYILMAZ(monkeypatch):
    """Başarısızlık `[]` değil None döner -- önbelleğe "olaysız ay" yazılmaz.

    Ekim 2026: eski apiv2 ucu geçmiş ayları HTTP 200 + `[]` ile döndürmeye
    başladı ve başarısız aylar da `[]` olarak önbelleğe giriyordu. İkisi
    birlikte katalogu 266.527 -> 196 satıra indirdi.
    """
    m = _afad_modulu()
    monkeypatch.setattr(m.time, "sleep", lambda s: None)

    class Bozuk(_Oturum):
        def post(self, *a, **k):
            raise OSError("zaman aşımı")

    assert m.fetch_month(2015, 3, 2.0, oturum=Bozuk()) is None

    class Yarim(_Oturum):
        """totalCount 3 der ama tek sayfadan sonra boş döner."""
        def post(self, url, json, **k):
            if json["Skip"] == 0:
                return _Yanit({"totalCount": 3, "eventList": [
                    {"id": 1, "eventDate": "2015-03-01T00:00:00"}]})
            return _Yanit({"totalCount": 3, "eventList": None})

    assert m.fetch_month(2015, 3, 2.0, oturum=Yarim()) is None

    class Oturumsuz(_Oturum):
        """Oturum hiç açılmıyor; uç 200 ile session_required döner."""
        def post(self, *a, **k):
            return _Yanit({"code": "session_required", "reason": "missing"})

    assert m.fetch_month(2015, 3, 2.0, oturum=Oturumsuz()) is None


def test_AFAD_DUSEN_OTURUM_YENILENIR(monkeypatch):
    """Ekim 2026: uç `afad_sid` çerezi olmadan 401 döner. Çerez yoksa önce
    açılır; süresi dolmuşsa (401) Session/Init ile yenilenip yeniden sorulur.
    """
    m = _afad_modulu()
    monkeypatch.setattr(m.time, "sleep", lambda s: None)

    class Suresi_Dolan(_Oturum):
        def post(self, url, json, **k):
            if self.cookies.get("afad_sid") == "gecerli":
                return _Yanit({"code": "session_required",
                               "reason": "invalid"}, 401)
            return _Yanit({"totalCount": 1, "eventList": [
                {"id": 7, "eventDate": "2015-03-01T00:00:00"}]})

    o = Suresi_Dolan()
    assert len(m.fetch_month(2015, 3, 2.0, oturum=o)) == 1
    assert o.init_sayisi == 1

    o = Suresi_Dolan()
    o.cookies.clear()
    assert len(m.fetch_month(2015, 3, 2.0, oturum=o)) == 1
    assert o.init_sayisi == 1, "çerez yokken ilk istekten ÖNCE açılmalı"


def test_AFAD_SAYFALAMA_VE_ALAN_ESLEMESI(monkeypatch):
    m = _afad_modulu()
    olaylar = [{"id": i, "eventDate": f"2015-03-01T00:00:{i:02d}",
                "latitude": 40.0, "longitude": 30.0, "depth": 7.0,
                "magnitude": 2.5, "magnitudeType": "ML",
                "location": "Ege Denizi - [18.08 km] Ayvacık (Çanakkale)"}
               for i in range(45)]

    class Sahte(_Oturum):
        def post(self, url, json, **k):
            assert json["Take"] <= 20, "AFAD Take>20'de boş döner"
            s = json["Skip"]
            return _Yanit({"totalCount": len(olaylar),
                           "eventList": olaylar[s:s + json["Take"]]})

    monkeypatch.setattr(m.time, "sleep", lambda s: None)
    sonuc = m.fetch_month(2015, 3, 2.0, oturum=Sahte())
    assert len(sonuc) == 45
    e = sonuc[0]
    assert (e["eventID"], e["date"], e["type"]) == ("0", "2015-03-01T00:00:00", "ML")
    assert (e["province"], e["district"]) == ("Çanakkale", "Ayvacık")
