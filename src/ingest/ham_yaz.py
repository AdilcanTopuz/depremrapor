# -*- coding: utf-8 -*-
"""Ham katalog yazımı — var olan bir katalogun üzerine KÜÇÜĞÜ yazılmaz.

NEDEN BURADA BİR KORUMA VAR. V38'de hattın kendi girdisini imha edebildiği
görülmüş ve monotonluk koruması eklenmişti; ama o koruma HATTIN İÇİNDE,
yayım yolundadır. Yani şunu yapabiliyordu: yayımı durdurmak. Yapamadığı
şey, indiricinin iyi dosyanın üzerine kırpılmış bir dosya yazmasını
engellemekti.

28 Ağustos 2026'da tam bu oldu: KOERI indiricisi bazı yılları alamadı,
alamadıklarını sessizce atladı, elde kalan 19.339 satırı 72.473 satırlık
dosyanın ÜZERİNE yazdı ve 0 ile çıktı. Yayım korumadan döndü -- ama ham
dosya çoktan gitmişti.

Ders: bir kaynağı korumak, onu KULLANAN yolu korumakla olmaz; YAZAN yolu
korumakla olur. Koruma artık yazma anındadır ve bütün indiriciler buradan
geçer.

Bilinçli küçültme mümkündür (`izin_kucultme=True`) -- ama sessiz değildir.
"""
from __future__ import annotations

import pathlib


class HamKatalogKuculdu(Exception):
    """Var olan ham katalogun üzerine daha az satırla yazılmak istendi."""


def _satir_say(yol: pathlib.Path) -> int:
    """CSV veri satırı sayısı (başlık hariç). Dosyayı belleğe almaz."""
    with yol.open("rb") as f:
        n = sum(1 for _ in f)
    return max(n - 1, 0)


def guvenli_yaz(df, hedef, *, izin_kucultme: bool = False,
                ad: str | None = None) -> None:
    """`df`'i `hedef`e yazar; var olan dosyadan AZ satırla yazmayı reddeder.

    Eşitlik ve büyüme serbesttir: katalog güncellemesi doğal olarak büyür ya
    da (aynı aralık yeniden çekilirse) aynı kalır. Küçülme her zaman bir
    açıklama ister.
    """
    hedef = pathlib.Path(hedef)
    ad = ad or hedef.name
    if hedef.exists() and not izin_kucultme:
        eski = _satir_say(hedef)
        if len(df) < eski:
            raise HamKatalogKuculdu(
                f"! {ad}: {eski:,} -> {len(df):,} satır. Var olan ham katalogun\n"
                f"  üzerine daha AZ satır yazılmak istendi; yazılmadı.\n"
                f"  Olası sebep: kaynak sunucu kısmen yanıt vermedi ve indirici\n"
                f"  eksik sonucu tam sanarak yazmak üzereydi.\n"
                f"  Dosya OLDUĞU GİBİ bırakıldı. Yeniden çalıştırmak,\n"
                f"  önbellekteki parçalar sayesinde yalnızca eksikleri çeker.\n"
                f"  Bilinçli bir daraltmaysa: izin_kucultme=True"
            )
    hedef.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(hedef, index=False, encoding="utf-8")
