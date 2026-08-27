"""BELGE SAYFALARI — Markdown belgeleri siteye, TEK KAYNAKTAN.

Vaka defteri ve denetim mirası sitede yayımlanır (şeffaflık kararı).
ELLE HTML'E ÇEVRİLMEZ: kopya, kaynakla ayrışır ve ayrışma sessizdir --
V42'de tam bu oldu (uyarı metni elle kopyalanmış, kaynakla ayrışmıştı).

Sayfalar her site kurulumunda belgelerden YENİDEN üretilir.

Bağımlılık yok: küçük bir Markdown alt kümesi yeterli (başlık, tablo,
liste, kalın, kod, alıntı, yatay çizgi).
"""
from __future__ import annotations

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

BELGELER = {
    "vaka-defteri.html": (ROOT / "docs" / "VAKA_DEFTERI.md",
                          "Vaka defteri", "Bulunan her hatanın kaydı"),
    "denetim-mirasi.html": (ROOT / "docs" / "DENETIM_MIRASI.md",
                            "Denetim ilkeleri",
                            "Vakalardan çıkarılan kalıcı kurallar"),
}


from src.operational.pipeline import YAYIN_ADRESI


def _satir_ici(t: str) -> str:
    t = html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", t)
    return t


def md_to_html(md: str) -> str:
    out, i = [], 0
    satir = md.split("\n")
    while i < len(satir):
        s = satir[i]
        if s.startswith("```"):
            blok = []
            i += 1
            while i < len(satir) and not satir[i].startswith("```"):
                blok.append(html.escape(satir[i])); i += 1
            out.append("<pre>" + "\n".join(blok) + "</pre>"); i += 1; continue
        if re.match(r"^ {4,}\S", s):            # girintili kod bloğu
            blok = []
            while i < len(satir) and (re.match(r"^ {4,}", satir[i])
                                      or not satir[i].strip()):
                blok.append(html.escape(satir[i][4:])); i += 1
            out.append("<pre>" + "\n".join(blok).rstrip() + "</pre>"); continue
        if s.startswith("|") and i + 1 < len(satir) and re.match(
                r"^\|[\s:|-]+\|$", satir[i + 1]):
            basliklar = [c.strip() for c in s.strip("|").split("|")]
            i += 2
            govde = []
            while i < len(satir) and satir[i].startswith("|"):
                govde.append([c.strip() for c in satir[i].strip("|").split("|")])
                i += 1
            t = ["<table><tr>" + "".join(
                f"<th>{_satir_ici(b)}</th>" for b in basliklar) + "</tr>"]
            for r in govde:
                t.append("<tr>" + "".join(
                    f"<td>{_satir_ici(c)}</td>" for c in r) + "</tr>")
            out.append("".join(t) + "</table>"); continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            n = len(m.group(1))
            out.append(f"<h{n}>{_satir_ici(m.group(2))}</h{n}>"); i += 1; continue
        if re.match(r"^---+$", s):
            out.append("<hr>"); i += 1; continue
        if s.startswith("> "):
            blok = []
            while i < len(satir) and satir[i].startswith(">"):
                blok.append(_satir_ici(satir[i].lstrip("> ").rstrip())); i += 1
            out.append("<blockquote>" + " ".join(blok) + "</blockquote>"); continue
        if re.match(r"^\s*[-*]\s+", s):
            blok = []
            while i < len(satir) and re.match(r"^\s*[-*]\s+", satir[i]):
                blok.append("<li>" + _satir_ici(
                    re.sub(r"^\s*[-*]\s+", "", satir[i])) + "</li>"); i += 1
            out.append("<ul>" + "".join(blok) + "</ul>"); continue
        if s.strip():
            blok = []
            while i < len(satir) and satir[i].strip() and not re.match(
                    r"^(#{1,4}\s|\||>|\s*[-*]\s|---+$|```| {4,}\S)", satir[i]):
                blok.append(_satir_ici(satir[i].strip())); i += 1
            out.append("<p>" + " ".join(blok) + "</p>"); continue
        i += 1
    return "\n".join(out)


SABLON = """<!DOCTYPE html>
<html lang="tr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="description" content="{alt}">
<link rel="canonical" href="{adres}/{dosya}">
<meta property="og:type" content="article">
<meta property="og:locale" content="tr_TR">
<meta property="og:site_name" content="depremrapor.com">
<meta property="og:url" content="{adres}/{dosya}">
<meta property="og:title" content="{baslik} — depremrapor.com">
<meta property="og:description" content="{alt}">
<meta name="twitter:card" content="summary">
<title>{baslik} — Türkiye Deprem Olasılık Haritası</title>
<style>
 :root{{--bg:#0f1216;--kart:#171b21;--cizgi:#2a3038;--metin:#e6e9ee;--soluk:#9aa4b2}}
 *{{box-sizing:border-box}}
 body{{margin:0;background:var(--bg);color:var(--metin);
   font:15px/1.62 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}}
 .kap{{max-width:860px;margin:0 auto;padding:22px 20px 70px}}
 h1{{font-size:22px;margin:0 0 4px}} h2{{font-size:17.5px;margin:30px 0 8px;
   padding-top:13px;border-top:1px solid var(--cizgi)}}
 h3{{font-size:14.5px;margin:16px 0 6px;color:#cfd6e0}}
 h4{{font-size:13.5px;margin:12px 0 5px;color:var(--soluk)}}
 p,li{{color:#dbe0e8}} .soluk{{color:var(--soluk);font-size:13.5px}}
 table{{width:100%;border-collapse:collapse;margin:10px 0;font-size:13px}}
 th,td{{text-align:left;padding:6px 9px;border-bottom:1px solid var(--cizgi);
   vertical-align:top}}
 th{{color:var(--soluk);font-weight:500}}
 pre{{background:#11151a;border:1px solid var(--cizgi);border-radius:7px;
   padding:11px 13px;overflow-x:auto;font-size:12.5px;line-height:1.45}}
 code{{background:#11151a;padding:1px 5px;border-radius:4px;font-size:12.5px}}
 blockquote{{border-left:3px solid #b5843f;margin:12px 0;padding:8px 14px;
   background:var(--kart);border-radius:0 7px 7px 0}}
 hr{{border:0;border-top:1px solid var(--cizgi);margin:26px 0}}
 a{{color:#7fb3e8}} .geri{{display:inline-block;margin-bottom:14px}}
 .ust{{background:var(--kart);border:1px solid var(--cizgi);border-radius:9px;
   padding:12px 15px;margin:12px 0 20px;font-size:13.5px}}
</style>
<script defer src="analitik.js"></script></head><body><div class="kap">
<a class="geri" href="index.html">← haritaya dön</a>
<h1>{baslik}</h1>
<div class="soluk">{alt}</div>
<div class="ust">{onsoz}</div>
{govde}
<hr><div class="soluk">Bu sayfa <code>{kaynak}</code> belgesinden otomatik
üretilmiştir; elle düzenlenmez. <a href="metodoloji.html">Yöntem ve
sınırlılıklar</a> · <a href="index.html">Harita</a></div>
</div></body></html>"""

ONSOZ = {
    "vaka-defteri.html": (
        "Bu defter, sistem geliştirilirken bulunan hataların kaydıdır. "
        "Her kayıt şunu içerir: <strong>ne olduğu</strong>, "
        "<strong>nasıl bulunduğu</strong>, hangi ölçümle doğrulandığı ve "
        "aynı sınıftan başka hata olup olmadığı. Vakaların çoğu yayına "
        "çıkmadan yakalanmıştır; birkaçı yayımlanmış ve geri çekilmiştir. "
        "Teknik bir belgedir ve teknik dil kullanır."),
    "denetim-mirasi.html": (
        "Vakalardan çıkarılan kalıcı kurallar. Her kural bir ya da daha çok "
        "gerçek hataya dayanır; hiçbiri teorik değildir."),
}


def uret(quiet: bool = False) -> list[Path]:
    yazilan = []
    for dosya, (kaynak, baslik, alt) in BELGELER.items():
        if not kaynak.exists():
            raise SystemExit(f"! {kaynak} yok")
        govde = md_to_html(kaynak.read_text(encoding="utf-8"))
        hedef = WEB / dosya
        hedef.write_text(SABLON.format(
            baslik=baslik, alt=alt, onsoz=ONSOZ[dosya], govde=govde,
            kaynak=kaynak.name, adres=YAYIN_ADRESI, dosya=dosya),
            encoding="utf-8")
        yazilan.append(hedef)
        if not quiet:
            print(f"  {dosya:28s} {kaynak.name} -> "
                  f"{hedef.stat().st_size / 1024:.0f} KB")
    return yazilan


if __name__ == "__main__":
    uret()
