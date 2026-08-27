# -*- coding: utf-8 -*-
"""Testlerin türetilmiş veriye bağımlılığı.

SORUN. Bu deponun bazı testleri, ham katalogdan **türetilen** dosyalara
ihtiyaç duyar (`catalog_merged.csv`, `catalog_declustered.csv`). Bu
dosyalar depoda durmaz: 4 GB'lık ham veriden üretilirler ve büyük eserler
depoya girmez (`docs/SAYI_HARITASI.md`).

Sonuç olarak, depoyu ilk kez klonlayan biri `pytest` çalıştırdığında
16 hata ve 3 düşme görüyordu. Hiçbiri gerçek bir kusur değildi — ama
**içlerinden biri gerçekti** (kurulmamış pre-commit kancası) ve o tek
gerçek bulgu, on altı gürültünün arasında görünmez hâle geliyordu.

Bu projenin kendi dersi tam da budur: gürültü sinyali gizler. "Veri yok"
ile "bozuk" ayrı şeylerdir ve ayrı görünmelidirler. Bu yüzden veriye
bağlı testler ATLANIR ve atlanma sebebi yazılır; çökmez.

DİKKAT. `veri_gerekir` bir muafiyet değildir: veri varken testler tam
olarak eskisi gibi koşar. Geliştirme ortamında (hattın bir kez çalıştığı
her yerde) hiçbir şey atlanmaz.
"""
from __future__ import annotations

import pathlib

import pytest

KOK = pathlib.Path(__file__).resolve().parents[1]

# Hattın bir kez çalışmasıyla oluşan türetilmiş eserler.
TUREV_ESERLER = (
    "data/processed/catalog_merged.csv",
    "data/processed/catalog_declustered.csv",
)

EKSIK = [y for y in TUREV_ESERLER if not (KOK / y).exists()]

veri_gerekir = pytest.mark.skipif(
    bool(EKSIK),
    reason=("türetilmiş katalog yok (" + ", ".join(EKSIK) + "). "
            "Bu dosyalar depoda durmaz; önce hattı bir kez çalıştırın: "
            "python -m src.operational.pipeline"),
)

# Yayın arşivine bağlı testler için ayrı ölçüt: bir klon deposunda
# `data/publish` hiç yoktur, ilk koşudan sonra oluşur.
yayin_gerekir = pytest.mark.skipif(
    not (KOK / "data" / "publish").exists(),
    reason=("data/publish yok — yayın arşivi ilk koşudan sonra oluşur "
            "(bulutta `yayin` dalından geri yüklenir)."),
)
