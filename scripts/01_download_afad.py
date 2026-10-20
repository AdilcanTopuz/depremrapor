"""AFAD apiv2'den tarihsel deprem kataloğunu indirir.

Yıl yıl (aylik dilimlerle) sorgular; sonuçları data/raw/afad/ altına JSON olarak,
sonda tek bir CSV (data/raw/afad_catalog.csv) olarak kaydeder.

Kullanım:
    python scripts/01_download_afad.py --start 2003 --end 2026 --minmag 1.0
"""
import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

# BETİK OLARAK ÇALIŞTIRILDIĞINDA DEPO KÖKÜ sys.path'TE DEĞİLDİR.
# Hat bu dosyaları `python scripts/xx.py` diye çağırır (`-m` ile değil --
# modül adı rakamla başladığı için mümkün de değil), o zaman sys.path[0]
# `scripts/` olur ve `src` paketi görünmez. Kök elle eklenir.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))

from src.ingest.ham_yaz import guvenli_yaz  # noqa: E402

# KAYNAK DEĞİŞTİ (Ekim 2026).
#
# `deprem.afad.gov.tr/apiv2/event/filter` artık 302 ile
# `servisnet.afad.gov.tr/apigateway/...` adresine yönlendiriyor ve oradaki
# ağ geçidi YALNIZCA SON ~10 GÜNÜ veriyor; daha eski her ay için HTTP 200 ve
# `[]` döner. Hata yoktur, sadece veri yoktur. 19-20 Ekim 2026 koşuları bu
# yüzden afad_catalog.csv'yi 266.527 -> 196 satıra indirdi (monotonluk
# koruması yakaladı).
#
# Tam geçmiş, AFAD'ın KENDİ deprem arama sayfasının (event-service)
# kullandığı uçtadır. Ölçüldü (20 Eki 2026): 2003-2026 M>=2.0 toplamı
# 266.598 -- eski apiv2 dökümüyle (266.527) tutarlı. Kısıtı: sayfa başına
# EN FAZLA 20 kayıt (Take>20 sessizce totalCount=0 döndürür).
BASE = "https://deprem.afad.gov.tr/EventData/GetEventsByFilter"
SAYFA = 20
# AFAD'ın filtre türü numaraları (event-service paketindeki enum)
F_MIN_TARIH, F_MAX_TARIH, F_MIN_BUYUKLUK = 8, 9, 11
# Son N ayın önbelleği her koşuda TAZELENİR: içinde bulunulan ay hâlâ
# doluyor, bir önceki ay da AFAD'ın geç revizyonlarını alabilir. Önbellek
# kalıcı hâle gelince (V62) bu olmadan katalog o ayda DONARDI.
TAZE_AY = 2
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "afad"


BLOCK_HELP = """
  AFAD'a TLS bağlantısı reddedildi (bağlantı sıfırlandı).

  EN OLASI SEBEP: makinede çalışan bir DPI-atlatma aracı (GoodbyeDPI, Zapret,
  ByeDPI vb.). Bu araçlar giden TLS ClientHello paketlerini parçalara böler veya
  sahte paket enjekte eder; AFAD'ın önündeki F5 BigIP yük dengeleyici bu manipüle
  edilmiş el sıkışmayı kabul etmeyip bağlantıyı RST ile keser.

  Bu teşhis bu projede ölçülerek doğrulandı: GoodbyeDPI kapatıldığında AFAD,
  Türkiye IP'siyle ve VPN olmadan sorunsuz yanıt verdi.

  Ayırt edici belirtiler (VPN/IP engeliyle karıştırmayın):
    * Port 80 çalışır ama port 443 sıfırlanır — araçlar 443'e müdahale eder
    * SNI göndermeden, IP'ye doğrudan bağlanınca da başarısız olur — müdahale
      alan adına göre değil PORTA göredir
    * VPN üzerinden çalışır — WireGuard/OpenVPN trafiği kapsüller, içindeki
      TLS'e dokunulmaz

  ÇÖZÜM: DPI-atlatma aracını geçici olarak kapatıp bu scripti tekrar çalıştırın.
  İndirilen dosyalar data/raw/afad/ altında aylık olarak önbelleklenir; indirme
  bittikten sonra aracı geri açabilirsiniz.

  Bu değilse: kurumsal güvenlik duvarı / TLS denetimi veya gerçekten AFAD
  tarafında bir kısıt olabilir. VPN ile deneyin.
"""


def _is_connection_block(exc: Exception) -> bool:
    """Bağlantının TLS düzeyinde reddedilip reddedilmediğini anlar."""
    text = f"{exc}"
    return ("ConnectionResetError" in text or "10054" in text
            or "reset by peer" in text.lower())


def _apiv2_bicimi(e: dict) -> dict:
    """Arama ucunun kaydını eski apiv2 alan adlarına çevirir.

    Önbellekteki aylık JSON'lar ve aşağı akış (rename, 34_hucre_yer_adlari)
    apiv2 adlarını bekler; kaynak değişti diye önbellek biçimi değişmez.
    `id` apiv2'deki `eventID` ile aynıdır (ölçüldü). İl/ilçe bu uçta boş
    gelir; `location`'daki "İlçe (İl)" kalıbından çıkarılır.
    """
    yer = e.get("location") or ""
    il = ilce = None
    if yer.endswith(")") and "(" in yer:
        il = yer[yer.rindex("(") + 1:-1].strip() or None
        ilce = yer[:yer.rindex("(")].split("]")[-1].strip() or None
    return {
        "eventID": str(e.get("id")),
        "date": e.get("eventDate"),
        "latitude": e.get("latitude"),
        "longitude": e.get("longitude"),
        "depth": e.get("depth"),
        "type": e.get("magnitudeType"),
        "magnitude": e.get("magnitude"),
        "location": yer,
        "rms": e.get("rms"),
        "country": None,
        "province": e.get("province") or il,
        "district": e.get("district") or ilce,
    }


def fetch_month(year: int, month: int, minmag: float, retries: int = 3,
                oturum=None):
    """Bir ayın olaylarını döndürür; ALINAMAZSA None (boş liste DEĞİL).

    Ayrım önemlidir: `[]` "o ay olay yok" demektir ve önbelleğe yazılır;
    None "bilmiyoruz" demektir ve yazılmaz. Önceden başarısızlık da `[]`
    dönüyordu ve kalıcı olarak "olaysız ay" diye önbelleğe giriyordu.
    """
    oturum = oturum or requests.Session()
    end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
    filtre = [
        {"FilterType": F_MIN_TARIH, "Value": f"{year}-{month:02d}-01T00:00:00.000Z"},
        {"FilterType": F_MAX_TARIH, "Value": f"{end_year}-{end_month:02d}-01T00:00:00.000Z"},
        {"FilterType": F_MIN_BUYUKLUK, "Value": str(minmag)},
    ]
    for attempt in range(retries):
        try:
            olaylar: dict = {}
            toplam = None
            skip = 0
            while True:
                r = oturum.post(BASE, timeout=60, json={
                    "EventSearchFilterList": filtre, "Skip": skip, "Take": SAYFA,
                    # artan sıra: sayfalama sürerken gelen yeni olay baştaki
                    # sayfaları kaydırmasın
                    "SortDescriptor": {"field": "eventDate", "dir": "asc"},
                }, headers={"User-Agent": "deprem-tahmin-research/0.1"})
                r.raise_for_status()
                d = r.json()
                liste = d.get("eventList") or []
                if toplam is None:
                    toplam = d.get("totalCount") or 0
                for e in liste:
                    olaylar[e["id"]] = e
                skip += SAYFA
                if not liste or skip >= toplam:
                    break
                time.sleep(0.2)  # nazik ol
            # Sayfalama yarıda boş döndüyse ay ALINMAMIŞ sayılır -- kırpılmış
            # ay önbelleğe yazılmaz.
            if len(olaylar) < toplam:
                raise ValueError(f"eksik sayfalama: {len(olaylar)}/{toplam}")
            return [_apiv2_bicimi(e) for e in
                    sorted(olaylar.values(), key=lambda e: e["eventDate"])]
        except Exception as e:  # noqa: BLE001
            if _is_connection_block(e):
                raise SystemExit(BLOCK_HELP) from e
            print(f"  ! {year}-{month:02d} deneme {attempt+1}/{retries} hata: {e}")
            time.sleep(5 * (attempt + 1))
    return None


def check_schema(df: pd.DataFrame) -> None:
    """Beklenen kolonların gerçekten geldiğini doğrular.

    AFAD apiv2 alan adlarını haber vermeden değiştirebilir. Sessizce boş bir
    katalog üretmektense burada durup ham alan adlarını göstermek daha iyidir.
    """
    required = ("time", "lat", "lon", "mag")
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise SystemExit(
            f"\n  AFAD yanıtında beklenen alanlar yok: {missing}\n"
            f"  Gelen ham alan adları: {sorted(df.columns)}\n"
            f"  01_download_afad.py içindeki `rename` eşlemesini buna göre güncelleyin."
        )
    n_bad = int(df[list(required)].isna().any(axis=1).sum())
    if n_bad:
        print(f"  ! {n_bad} kayıtta zorunlu alanlar eksik/çözümlenemedi (atlanacak).")


def read_cached(path: Path):
    """Önbellek dosyasını okur; okunamıyorsa None döner (o ay yeniden indirilir).

    İki gerçek durumu karşılar: (1) scriptin ilk sürümü dosyaları sistem varsayılan
    kodlamasıyla yazıyordu — böyle bir dosya okunup UTF-8 olarak yeniden yazılır,
    indirme tekrarlanmaz; (2) indirme ortasında kesilirse yarım/boş bir dosya kalır —
    bu sessizce "0 olaylı ay" gibi davranmamalı, yeniden indirilmelidir.
    """
    for encoding in ("utf-8", "cp1254"):
        try:
            data = json.loads(path.read_text(encoding=encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        if encoding != "utf-8":
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    print(f"  ! {path.name} okunamadı (yarım/bozuk) — yeniden indiriliyor")
    path.unlink(missing_ok=True)
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=2003)
    ap.add_argument("--end", type=int, default=datetime.now().year)
    ap.add_argument("--minmag", type=float, default=1.0)
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    oturum = requests.Session()
    simdi = datetime.now()
    all_rows: list[dict] = []
    alinamayan: list[str] = []
    for year in range(args.start, args.end + 1):
        for month in range(1, 13):
            if datetime(year, month, 1) > simdi:
                break
            out = RAW_DIR / f"afad_{year}_{month:02d}.json"
            yas_ay = (simdi.year - year) * 12 + simdi.month - month
            cached = read_cached(out) if out.exists() else None
            data = cached if yas_ay >= TAZE_AY else None
            if data is None:
                data = fetch_month(year, month, args.minmag, oturum=oturum)
                if data is None:
                    # Tazelenemeyen son ay: eldeki (biraz eski) önbellek
                    # kullanılır. O da yoksa ay ALINAMADI sayılır.
                    data = cached
                else:
                    # encoding açıkça verilmeli: Path.write_text sistem varsayılanını kullanır ve
                    # Türkçe Windows'ta (cp1254) AFAD yer adlarındaki bazı karakterler
                    # (ör. U+017D) kodlanamayıp indirmeyi ortasında düşürür.
                    out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                time.sleep(0.5)  # nazik ol
            if data is None:
                print(f"{year}-{month:02d}: ALINAMADI")
                alinamayan.append(f"{year}-{month:02d}")
                continue
            print(f"{year}-{month:02d}: {len(data)} olay")
            all_rows.extend(data)

    # KISMİ İNDİRME BAŞARI SAYILMAZ (KOERI'deki V59 dersiyle aynı): eksik
    # aylarla toplu CSV yazılmaz. Alınan aylar önbellekte kalır; bir sonraki
    # koşu yalnızca eksikleri çeker.
    if alinamayan:
        raise SystemExit(
            f"! AFAD: {len(alinamayan)} ay alınamadı: {alinamayan[:12]}"
            + (" ..." if len(alinamayan) > 12 else "")
            + "\n  Kırpılmış katalog YAZILMADI.")

    if not all_rows:
        print("Hiç veri alınamadı — API şemasını/bağlantıyı kontrol edin.")
        return

    df = pd.DataFrame(all_rows)
    # AFAD alan adları zamanla değişebilir; esnek kolon eşleme
    rename = {"eventID": "event_id", "date": "time", "latitude": "lat",
              "longitude": "lon", "depth": "depth_km", "magnitude": "mag",
              "type": "mag_type", "location": "place"}
    df = df.rename(columns={k: v for k, v in rename.items() if k in df.columns})
    for col in ("lat", "lon", "depth_km", "mag"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    check_schema(df)
    df["source"] = "AFAD"
    out_csv = RAW_DIR.parent / "afad_catalog.csv"
    guvenli_yaz(df, out_csv, ad="afad_catalog.csv")
    print(f"Toplam {len(df)} olay -> {out_csv}")


if __name__ == "__main__":
    main()
