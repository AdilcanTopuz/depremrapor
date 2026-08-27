# -*- coding: utf-8 -*-
"""Sosyal paylaşım görselini (og:image) üretir -> web/og.png

    python -m scripts.og_gorsel

NEDEN ÜRETİLİYOR, ELLE ÇİZİLMİYOR. Depoya yapıştırılmış bir ikili dosya,
nasıl yapıldığı bilinmeyen bir eserdir; sınırın hangi kaynaktan geldiği,
ızgaranın gerçekten 0,25° olup olmadığı sonradan doğrulanamaz. Bu görsel
`data/processed/tr_sinir.geojson` ve `src/config`'teki ızgara tanımından
üretilir -- yani sitede gösterilen şeyin aynı kaynaklarından.

NEDEN CANLI TAHMİN GÖSTERMİYOR. Sosyal kart, bağlantı ne zaman paylaşılırsa
paylaşılsın aynı görseli gösterir; içine o günün hücreleri konsaydı, üç ay
sonra paylaşılan bir bağlantı ÜÇ AY ÖNCEKİ olasılıkları gösterirdi ve bunu
gören kimse tarihinin geçtiğini anlayamazdı. Kartta sayı yoktur: ülke
sınırı, ızgaranın kendisi ve renk ölçeği bir LEJANT olarak yer alır --
ölçeğin ne anlama geldiğini gösterir, bir ölçüm iddia etmez.

Görsel nadiren değişir; site kurulumunun parçası değildir ve `site_kur`
tarafından çağrılmaz (çalışma ağacını kirletmesin -- V51).
"""
from __future__ import annotations

import json
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                       # noqa: E402
from matplotlib.patches import Rectangle              # noqa: E402

KOK = pathlib.Path(__file__).resolve().parents[1]
SINIR = KOK / "data" / "processed" / "tr_sinir.geojson"
HEDEF = KOK / "web" / "og.png"

# Sitenin kendi paleti (web/index.html :root)
ZEMIN, PANEL, CIZGI = "#0B0E11", "#232D37", "#313B46"
METIN, SOLUK, VURGU = "#DDE4EA", "#7E8B98", "#F0883E"
# ColorBrewer YlOrRd -- CVD-güvenli, parlaklığı tek yönlü (web/script.js OLCEK)
OLCEK = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026"]

# 0.25° ızgara (src/config ile aynı tanım)
LAT0, LAT1, LON0, LON1, ADIM = 35.0, 43.0, 25.0, 45.0, 0.25


def _halkalar(gj: dict):
    g = gj["features"][0]["geometry"] if "features" in gj else gj["geometry"]
    coords = g["coordinates"]
    if g["type"] == "Polygon":
        coords = [coords]
    for parca in coords:
        for halka in parca:
            yield halka


def uret(hedef: pathlib.Path = HEDEF) -> pathlib.Path:
    gj = json.loads(SINIR.read_text(encoding="utf-8"))

    # 1200x630 -- Open Graph'ın önerdiği oran
    fig = plt.figure(figsize=(12.0, 6.3), dpi=100, facecolor=ZEMIN)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.set_facecolor(ZEMIN)
    # Başlık ülke şeklinin İÇİNE alındığı için harita artık kenara
    # çekilmiyor; sınır kutusunun merkezine oturtulup büyütülüyor. En/boy
    # oranı öncekiyle aynı tutuldu (24,8/10,2 = 19,8/8,15), yoksa ülke
    # sadece büyümez, biçim de değiştirir.
    ax.set_xlim(25.34, 45.14)
    ax.set_ylim(34.885, 43.035)
    ax.set_axis_off()

    # 0,25° ızgara -- SEYREK çizilir; her çizgi konsa doku gürültüye döner
    for lon in [LON0 + i * ADIM for i in range(int((LON1 - LON0) / ADIM) + 1)]:
        ax.plot([lon, lon], [LAT0, LAT1], color=CIZGI, lw=0.35, zorder=1,
                alpha=0.55 if abs(lon % 1) < 1e-9 else 0.22)
    for lat in [LAT0 + i * ADIM for i in range(int((LAT1 - LAT0) / ADIM) + 1)]:
        ax.plot([LON0, LON1], [lat, lat], color=CIZGI, lw=0.35, zorder=1,
                alpha=0.55 if abs(lat % 1) < 1e-9 else 0.22)

    # ülke sınırı
    for halka in _halkalar(gj):
        xs = [p[0] for p in halka]
        ys = [p[1] for p in halka]
        ax.fill(xs, ys, facecolor=PANEL, edgecolor="none", zorder=2)
        ax.plot(xs, ys, color="#9BA8B5", lw=1.3, zorder=3)

    # Perde KALDIRILDI: başlık ülke dolgusunun üzerinde duruyor ve
    # kontrastı oradan alıyor. Perde, yazı kıyı çizgisine bindiği için
    # gerekmişti; artık binmiyor.

    # --- yazı ------------------------------------------------------------
    ax.text(0.5, 0.560, "depremrapor.com", transform=ax.transAxes,
            fontsize=42, color=METIN, weight="bold",
            ha="center", va="center", zorder=6)
    ax.text(0.5, 0.470, "Türkiye Deprem Olasılık ve Tahmin Haritası",
            transform=ax.transAxes, fontsize=20, color=METIN,
            ha="center", va="center", alpha=0.94, zorder=6)
    ax.text(0.5, 0.410,
            "ETAS · 1, 7 ve 30 gün · M≥4,5 · üç saatte bir yenilenir",
            transform=ax.transAxes, fontsize=12, color=SOLUK,
            ha="center", va="center", zorder=6)

    # Sınırı söyleyen cümle görselin İÇİNDE durur: kart çoğu zaman
    # metinsiz paylaşılır ve tek başına dolaşır.
    ax.text(0.048, 0.105, "Olasılık yayımlar, uyarı yayımlamaz.",
            transform=ax.transAxes, fontsize=8.5, color=VURGU, va="bottom",
            weight="bold", zorder=6)
    ax.text(0.048, 0.062,
            "Her sayı, hangi kod ve hangi katalogla üretildiğini künyesinde taşır.",
            transform=ax.transAxes, fontsize=6.5, color=SOLUK, va="bottom",
            zorder=6)

    # --- renk ölçeği: LEJANT, veri değil ---------------------------------
    x0, y0, gen, yuk = 0.70, 0.115, 0.245, 0.030
    for i, renk in enumerate(OLCEK):
        ax.add_patch(Rectangle((x0 + i * gen / len(OLCEK), y0),
                               gen / len(OLCEK), yuk,
                               transform=ax.transAxes, facecolor=renk,
                               edgecolor="none", zorder=6))
    ax.text(x0, y0 + yuk + 0.022, "düşük", transform=ax.transAxes,
            fontsize=11.5, color=SOLUK, zorder=6)
    ax.text(x0 + gen, y0 + yuk + 0.022, "yüksek", transform=ax.transAxes,
            fontsize=11.5, color=SOLUK, ha="right", zorder=6)
    ax.text(x0 + gen / 2, y0 - 0.035, "normalin kaç katı",
            transform=ax.transAxes, fontsize=11.5, color=SOLUK,
            ha="center", va="top", zorder=6)

    hedef.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(hedef, facecolor=ZEMIN, dpi=100)
    plt.close(fig)
    return hedef


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    y = uret()
    print(f"-> {y}  ({y.stat().st_size / 1024:.0f} KB)")
