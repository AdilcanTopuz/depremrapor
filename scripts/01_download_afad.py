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

from src.ingest.ham_yaz import guvenli_yaz

BASE = "https://deprem.afad.gov.tr/apiv2/event/filter"
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


def fetch_month(year: int, month: int, minmag: float, retries: int = 3) -> list:
    start = f"{year}-{month:02d}-01T00:00:00"
    end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = f"{end_year}-{end_month:02d}-01T00:00:00"
    params = {
        "start": start,
        "end": end,
        "limit": 100000,
        "orderby": "timedesc",
        "minmag": minmag,
    }
    for attempt in range(retries):
        try:
            r = requests.get(BASE, params=params, timeout=60,
                             headers={"User-Agent": "deprem-tahmin-research/0.1"})
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            if _is_connection_block(e):
                raise SystemExit(BLOCK_HELP) from e
            print(f"  ! {year}-{month:02d} deneme {attempt+1}/{retries} hata: {e}")
            time.sleep(5 * (attempt + 1))
    return []


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
    all_rows: list[dict] = []
    for year in range(args.start, args.end + 1):
        for month in range(1, 13):
            if datetime(year, month, 1) > datetime.now():
                break
            out = RAW_DIR / f"afad_{year}_{month:02d}.json"
            data = read_cached(out) if out.exists() else None
            if data is None:
                data = fetch_month(year, month, args.minmag)
                # encoding açıkça verilmeli: Path.write_text sistem varsayılanını kullanır ve
                # Türkçe Windows'ta (cp1254) AFAD yer adlarındaki bazı karakterler
                # (ör. U+017D) kodlanamayıp indirmeyi ortasında düşürür.
                out.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
                time.sleep(1.0)  # nazik ol
            print(f"{year}-{month:02d}: {len(data)} olay")
            all_rows.extend(data)

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
