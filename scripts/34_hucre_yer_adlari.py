"""HÜCRE YER ADLARI — veriden, uydurmadan.

Haritadaki kare "Hücre 25014" diye görünüyordu; bir insana hiçbir şey
söylemiyor. Her hücreye bir yer adı gerekiyor — ama koordinat uydurmadan.

YÖNTEM: AFAD kataloğunda her olayın `province` ve `district` alanı var.
Hücreye düşen geçmiş olayların EN SIK il/ilçesi, o hücrenin adı olur.
Ad veriden gelir; hiçbir şey elle yazılmaz.

Hücreye hiç olay düşmemişse ad YOKTUR ve "adsız" kalır -- uydurulmaz.

Kullanım:  python scripts/34_hucre_yer_adlari.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
PROC = ROOT / "data" / "processed"


def main() -> None:
    from src.config import cell_id

    d = pd.read_csv(ROOT / "data" / "raw" / "afad_catalog.csv",
                    low_memory=False,
                    usecols=["lat", "lon", "province", "district", "country"])
    d = d.dropna(subset=["lat", "lon"])
    d = d[d.country.fillna("").str.strip().str.lower().isin(
        ["turkey", "türkiye", "turkiye", ""])]
    d["cell_id"] = cell_id(d.lat, d.lon)
    print(f"{len(d):,} olay · {d.cell_id.nunique():,} hücre")

    adlar = {}
    for c, g in d.groupby("cell_id"):
        il = Counter(g.province.dropna())
        if not il:
            continue
        en_il, n_il = il.most_common(1)[0]
        ilce = Counter(g[g.province == en_il].district.dropna())
        en_ilce = ilce.most_common(1)[0][0] if ilce else None
        adlar[int(c)] = {
            "il": en_il,
            "ilce": en_ilce,
            "ad": f"{en_ilce} ({en_il})" if en_ilce else en_il,
            "dayanak_olay": int(len(g)),
            "il_payi": round(n_il / len(g), 2),
        }

    dst = PROC / "hucre_yer_adlari.json"
    dst.write_text(json.dumps(adlar, indent=1, ensure_ascii=False),
                   encoding="utf-8")
    print(f"{len(adlar):,} hücreye ad verildi (veriden)")
    ornek = list(adlar.items())[:5]
    for c, v in ornek:
        print(f"  {c}: {v['ad']}  ({v['dayanak_olay']} olay, "
              f"il payı {v['il_payi']})")
    print(f"-> {dst}")


if __name__ == "__main__":
    main()
