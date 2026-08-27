"""GERİ ÇEKME PROTOKOLÜNÜN KURAL-9 DENEYİ.

Bir protokol, işlediği GÖSTERİLENE kadar "kurulu" sayılmaz. Burada sahte
bir yayın dalı kurulur, bir yayın geri çekilir ve ÜÇ ŞEY doğrulanır:

    1. geri çekilen yayın `latest/` altından DÜŞTÜ
    2. dosyalar SİLİNMEDİ -- `_geri_cekilen/` altında duruyor
    3. bir önceki geçerli yayın `latest/` oldu

Ayrıca gerekçesiz geri çekmenin REDDEDİLDİĞİ gösterilir.
"""
from __future__ import annotations

import json

import pytest

from src.operational.geri_cek import GeriCekmeHatasi, geri_cek


def _yayin_kur(kok, ad, zaman, sayi):
    d = kok / "_arsiv" / ad
    d.mkdir(parents=True)
    (d / "manifest.json").write_text(json.dumps({
        "uretim_zamani": zaman, "commit": "a" * 40,
        "katalog": {"sha256": "b" * 64},
        "dosyalar": [{"dosya": "forecast_7d_m45.geojson", "n_hucre": sayi}],
    }), encoding="utf-8")
    (d / "forecast_7d_m45.geojson").write_text(
        json.dumps({"n": sayi}), encoding="utf-8")
    return d


def test_geri_cekme_yayindan_DUSURUR_ama_SILMEZ(tmp_path):
    _yayin_kur(tmp_path, "20260825T063000Z", "2026-08-25T06:30:00Z", 300)
    _yayin_kur(tmp_path, "latest", "2026-08-26T06:30:00Z", 999)

    k = geri_cek(tmp_path, gerekce=(
        "Kapsam filtresi uygulanmadan yayımlandı; Türkiye dışındaki "
        "hücreler haritaya çıktı (V43 sınıfı)."), olcum="309 hücrenin 154'ü dışarıda",
        quiet=True)

    # 1. yayından DÜŞTÜ -- latest artık o yayın değil
    yeni = json.loads((tmp_path / "_arsiv" / "latest" / "forecast_7d_m45.geojson")
                      .read_text(encoding="utf-8"))
    assert yeni["n"] == 300, "latest bir önceki yayına dönmedi"

    # 2. SİLİNMEDİ
    tasinan = tmp_path / "_geri_cekilen" / k["zaman"] / "forecast_7d_m45.geojson"
    assert tasinan.exists(), "dosyalar silinmiş -- taşınmalıydı"
    assert json.loads(tasinan.read_text(encoding="utf-8"))["n"] == 999

    # 3. BEYAN yazıldı ve gerekçeyi taşıyor
    md = (tmp_path / "GERI_CEKILDI.md").read_text(encoding="utf-8")
    assert "Kapsam filtresi" in md and "309 hücrenin" in md
    assert k["yerine_gecen"] == "20260825T063000Z"


def test_yerine_gecen_YOKSA_acikca_beyan_edilir(tmp_path):
    """Tek yayın geri çekilirse site sessizce boş kalmaz, durum yazılır."""
    _yayin_kur(tmp_path, "latest", "2026-08-26T06:30:00Z", 999)
    k = geri_cek(tmp_path, gerekce=(
        "Kalibre b değeri varsayılana düşmüştü; oranlar ~%5 kaymış "
        "durumda (V49)."), quiet=True)
    assert k["yerine_gecen"] is None
    assert not (tmp_path / "_arsiv" / "latest").exists()
    assert "(yok)" in (tmp_path / "GERI_CEKILDI.md").read_text(encoding="utf-8")


def test_GEREKCESIZ_geri_cekme_REDDEDILIR(tmp_path):
    """Sessiz geri çekme, sessiz hata kadar kötüdür."""
    _yayin_kur(tmp_path, "latest", "2026-08-26T06:30:00Z", 999)
    with pytest.raises(GeriCekmeHatasi) as e:
        geri_cek(tmp_path, gerekce="hata", quiet=True)
    assert "gerekçe" in str(e.value)
    # ve HİÇBİR ŞEY değişmedi
    assert (tmp_path / "_arsiv" / "latest").exists()
    assert not (tmp_path / "_geri_cekilen").exists()


def test_KUNYESIZ_yayin_geri_cekilmez(tmp_path):
    """Künyesi olmayan bir yayın, ne olduğu bilinmediği için geri çekilemez."""
    d = tmp_path / "_arsiv" / "latest"
    d.mkdir(parents=True)
    (d / "forecast_7d_m45.geojson").write_text("{}", encoding="utf-8")
    with pytest.raises(GeriCekmeHatasi) as e:
        geri_cek(tmp_path, gerekce="a" * 50, quiet=True)
    assert "künyesiz" in str(e.value).lower()


def test_ESKI_KAYITLAR_SILINMEZ(tmp_path):
    """İkinci bir geri çekme, birincinin kaydını ezmez."""
    _yayin_kur(tmp_path, "20260824T063000Z", "2026-08-24T06:30:00Z", 100)
    _yayin_kur(tmp_path, "20260825T063000Z", "2026-08-25T06:30:00Z", 200)
    _yayin_kur(tmp_path, "latest", "2026-08-26T06:30:00Z", 300)

    geri_cek(tmp_path, gerekce="BİRİNCİ SEBEP: " + "x" * 40,
             zaman="20260826T100000Z", quiet=True)
    geri_cek(tmp_path, gerekce="İKİNCİ SEBEP: " + "y" * 40,
             zaman="20260826T110000Z", quiet=True)

    md = (tmp_path / "GERI_CEKILDI.md").read_text(encoding="utf-8")
    assert "BİRİNCİ SEBEP" in md and "İKİNCİ SEBEP" in md
    assert md.index("İKİNCİ SEBEP") < md.index("BİRİNCİ SEBEP"), "en yeni üstte"
    assert json.loads((tmp_path / "_arsiv" / "latest" /
                       "forecast_7d_m45.geojson").read_text(encoding="utf-8"))["n"] == 100
