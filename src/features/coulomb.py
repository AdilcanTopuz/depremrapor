"""Coulomb gerilim değişimi (ΔCFS) — projenin ZAMANLA DEĞİŞEN jeofizik katmanı.

Fay ve gerinim katmanları ablasyonda katkı vermedi ve nedeni yapısaldı: ikisi de
zamandan bağımsız, yani yalnızca hücreleri birbirinden ayırabiliyorlar. O işi
yumuşatılmış geçmiş sismisite (poisson_rate) zaten yapıyor.

Coulomb farklıdır. Büyük bir deprem çevresindeki fayların üzerindeki gerilmeyi
yeniden dağıtır: bazı bölgeler yüklenir (kırılmaya yaklaşır), bazıları boşalır.
Bu, "burası genelde aktiftir" demez — "şu an, şu depremden sonra, burası
yüklendi" der. Katalog tabanlı hiçbir öznitelik bu bilgiyi taşımaz.

    ΔCFS = Δτ + μ' · Δσn

Δτ alıcı fayın kayma yönündeki kayma gerilmesi değişimi, Δσn normal gerilme
değişimi (pozitif = kilidin gevşemesi), μ' etkin sürtünme katsayısı.
Pozitif ΔCFS depremi teşvik eder.

UYGULAMA
  Kaynak : Global CMT odak mekanizması (doğrultu/eğim/kayma + moment).
           Kırık boyutları Wells & Coppersmith (1994) ölçekleme bağıntılarından,
           ortalama atım D = M0 / (mu · L · W).
  Çözüm  : cutde (Nikkhoo & Walter 2015 üçgen dislokasyon, elastik yarı-uzay).
  Alıcı  : hücreye en yakın GEM fayının geometrisi — doğrultu iz azimutundan,
           eğim ve kayma açısı veritabanı alanlarından. "Optimal yönelimli
           düzlem" varsayımı yerine gerçek fay geometrisi kullanılır.

DOĞRULAMA
  17 Ağustos 1999 İzmit depremi, 3 ay sonra kırılan Düzce fayında POZİTİF
  ΔCFS üretmeliydi — literatürdeki en bilinen örnek (Stein ve ark. 1997;
  Parsons ve ark. 2000). `validate()` bunu sınar. Bu test tutmuyorsa
  koordinat kabulünde ya da işarette hata var demektir.

Çıktı: data/processed/coulomb_features.csv
       (cell_id, ref_date, cfs_cum, cfs_last, cfs_max_event)
"""
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from src.ingest.catalog_io import epoch_seconds, read_catalog

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"

LAT0, LON0, STEP = 35.0, 25.0, 0.25
DEG_KM = 111.19492664455873

MU = 32e9              # kayma modülü (Pa)
NU = 0.25              # Poisson oranı
FRICTION = 0.4         # etkin sürtünme μ' (literatürde 0.0-0.8; 0.4 yaygın)
RECEIVER_DEPTH_KM = 10.0
MIN_MW = 6.0           # bu büyüklüğün altındaki olaylar ihmal edilir
MAX_DIST_KM = 300.0    # bu uzaklığın ötesinde katkı ihmal edilebilir


def rupture_size(mw: float) -> tuple[float, float]:
    """Wells & Coppersmith (1994) — yüzey-altı kırık uzunluğu ve genişliği (km)."""
    length = 10 ** (-2.44 + 0.59 * mw)
    width = 10 ** (-1.01 + 0.32 * mw)
    return length, width


def unit_vectors(strike_deg: float, dip_deg: float):
    """(doğu, kuzey, yukarı) çerçevesinde doğrultu ve eğim-aşağı birim vektörleri.

    Doğrultu kuzeyden saat yönünde ölçülür; eğim doğrultunun SAĞINA doğrudur
    (sağ el kuralı) — sismolojinin standart kabulü.
    """
    phi, delta = np.radians(strike_deg), np.radians(dip_deg)
    strike_vec = np.array([np.sin(phi), np.cos(phi), 0.0])
    down_dip = np.array([np.cos(phi) * np.cos(delta),
                         -np.sin(phi) * np.cos(delta),
                         -np.sin(delta)])
    normal = np.cross(strike_vec, down_dip)      # asma bloğa doğru
    return strike_vec, down_dip, normal / np.linalg.norm(normal)


def fault_triangles(x0, y0, z0, strike, dip, length, width):
    """Dikdörtgen fay düzlemini iki üçgene böler (cutde üçgen bekler)."""
    s_vec, d_vec, _ = unit_vectors(strike, dip)
    c = np.array([x0, y0, z0])
    half_l, half_w = length / 2.0, width / 2.0
    p1 = c - half_l * s_vec - half_w * d_vec
    p2 = c + half_l * s_vec - half_w * d_vec
    p3 = c + half_l * s_vec + half_w * d_vec
    p4 = c - half_l * s_vec + half_w * d_vec
    # Derinlik yarı-uzayda negatif olmalı; yüzeyi delen fayları biraz aşağı it
    tris = np.array([[p1, p2, p3], [p1, p3, p4]])
    top = tris[:, :, 2].max()
    if top > -0.1:
        tris[:, :, 2] -= (top + 0.1)
    return tris


def stress_at(obs_xyz: np.ndarray, tris: np.ndarray, slip_vec: np.ndarray):
    """Gözlem noktalarında gerilme tensörü (Pa). obs ve tris km cinsinden.

    `cutde.strain` İKİLİ modda çalışır: üçgen başına bir gözlem noktası bekler.
    Bize her nokta için tüm üçgenlerin toplam katkısı gerektiğinden, üçgenler
    tek tek çağrılıp gerinimler toplanır (elastisite doğrusal olduğu için
    üst üste binme geçerlidir).
    """
    import cutde.halfspace as hs

    obs = obs_xyz.astype(np.float64)
    total = np.zeros((len(obs), 6))
    for tri in tris:
        tiled_tri = np.tile(tri.astype(np.float64), (len(obs), 1, 1))
        tiled_slip = np.tile(slip_vec.astype(np.float64), (len(obs), 1))
        total += np.asarray(hs.strain(obs, tiled_tri, tiled_slip, NU))
    return hs.strain_to_stress(total, MU, NU)


def resolve_cfs(stress6: np.ndarray, rec_strike, rec_dip, rec_rake,
                friction: float = FRICTION) -> np.ndarray:
    """Gerilme tensörünü alıcı fay üzerine çözüp ΔCFS verir (Pa).

    stress6 sırası (xx, yy, zz, xy, xz, yz) — cutde'nin kabulü.
    """
    s = np.empty((len(stress6), 3, 3))
    s[:, 0, 0], s[:, 1, 1], s[:, 2, 2] = stress6[:, 0], stress6[:, 1], stress6[:, 2]
    s[:, 0, 1] = s[:, 1, 0] = stress6[:, 3]
    s[:, 0, 2] = s[:, 2, 0] = stress6[:, 4]
    s[:, 1, 2] = s[:, 2, 1] = stress6[:, 5]

    out = np.empty(len(stress6))
    for i in range(len(stress6)):
        s_vec, d_vec, n_vec = unit_vectors(rec_strike[i], rec_dip[i])
        rake = np.radians(rec_rake[i])
        slip_dir = np.cos(rake) * s_vec - np.sin(rake) * d_vec   # -d_vec = eğim-yukarı
        traction = s[i] @ n_vec
        shear = float(traction @ slip_dir)
        normal = float(traction @ n_vec)      # pozitif = çekme = kilidin gevşemesi
        out[i] = shear + friction * normal
    return out


def to_local_km(lat, lon, lat_ref):
    """Coğrafi koordinatı yerel düzlem km'ye çevirir (eşdikdörtgen yaklaşımı)."""
    x = (np.asarray(lon) - LON0) * np.cos(np.radians(lat_ref)) * DEG_KM
    y = (np.asarray(lat) - LAT0) * DEG_KM
    return x, y


def cfs_from_event(event: pd.Series, obs_lat, obs_lon, rec_strike, rec_dip,
                   rec_rake) -> np.ndarray:
    """Tek bir depremin gözlem noktalarında ürettiği ΔCFS (bar)."""
    lat_ref = float(event.lat)
    ex, ey = to_local_km(event.lat, event.lon, lat_ref)
    ox, oy = to_local_km(obs_lat, obs_lon, lat_ref)

    mw = float(event.mw)
    length, width = rupture_size(mw)
    m0_nm = float(event.m0_dyncm) * 1e-7          # dyn-cm -> N·m
    slip_m = m0_nm / (MU * length * 1e3 * width * 1e3)
    # BİRİM TUTARLILIĞI: geometri km cinsinden verildiği için atım da km olmalı.
    # Gerinim = atım/uzunluk olduğundan metre kullanmak sonucu 1000 kat şişirir
    # (doğrulamada 110 km mesafede 154 bar gibi fiziksel olarak imkânsız değerler).
    slip_km = slip_m / 1000.0

    depth = max(float(event.depth_km), width * np.sin(np.radians(event.dip1)) / 2 + 1.0)
    tris = fault_triangles(ex, ey, -depth, event.strike1, event.dip1, length, width)

    rake = np.radians(float(event.rake1))
    # cutde kayma bileşenleri: [doğrultu-atımı, eğim-atımı, açılma].
    # DOĞRULTU-ATIMI İŞARETİ TERSTİR: cutde'nin üçgen yerel çerçevesindeki pozitif
    # doğrultu-atımı, sismolojideki rake kabulünün tersine karşılık geliyor.
    # Ampirik olarak belirlendi: D-B doğrultulu sağ yanal sentetik bir kırıkta
    # ss=-D*cos(rake) ile uç loblar POZİTİF (+2.96 bar), yanal loblar NEGATİF
    # (-0.25 bar) çıkıyor — doğrultu atımlı kırığın bilinen Coulomb deseni budur.
    slip_vec = np.array([-slip_km * np.cos(rake), slip_km * np.sin(rake), 0.0])

    obs = np.column_stack([ox, oy, np.full(len(ox), -RECEIVER_DEPTH_KM)])
    stress = stress_at(obs, tris, slip_vec)
    return resolve_cfs(stress, rec_strike, rec_dip, rec_rake) / 1e5   # Pa -> bar


def pick_source_plane(event: pd.Series) -> tuple[float, float, float]:
    """İki düğüm düzleminden gerçekte kırılanı seçer.

    Odak mekanizması iki matematiksel olarak eşdeğer düzlem verir; hangisinin
    kırıldığını mekanizma tek başına söylemez. Ama Coulomb deseni buna bağlıdır:
    yanlış düzlem, uç loblarını yanal loblarla yer değiştirir.

    Seçim ölçütü: bölgedeki haritalanmış diri fayların doğrultusuna daha yakın
    olan düzlem. İzmit 1999'da düzlem1 (182 derece, K-G) yerine düzlem2
    (91 derece, D-B) seçilir — Kuzey Anadolu Fayı'nın gerçek doğrultusu budur.
    """
    ref = event.get("ref_strike")
    if ref is None or pd.isna(ref):
        return float(event.strike1), float(event.dip1), float(event.rake1)

    def sep(a: float) -> float:
        d = abs((a - float(ref) + 180.0) % 360.0 - 180.0)
        return min(d, 180.0 - d)      # 180 derece belirsizliği (iz yönü)

    if sep(float(event.strike2)) < sep(float(event.strike1)):
        return float(event.strike2), float(event.dip2), float(event.rake2)
    return float(event.strike1), float(event.dip1), float(event.rake1)


def receiver_geometry(cells: pd.DataFrame) -> pd.DataFrame:
    """Her hücre için alıcı fay geometrisi: en yakın haritalanmış fayın
    doğrultusu (iz azimutundan), eğimi ve kayma açısı (GEM alanlarından).

    "Optimal yönelimli düzlem" varsayımı yerine GERÇEK fay geometrisi kullanılır:
    Coulomb, gerilmenin hangi düzleme çözüldüğüne duyarlıdır ve Türkiye'de baskın
    yapılar bellidir (KAF sağ yanal, DAF sol yanal, Ege normal).
    """
    import json
    from src.features.fault_features import parse_slip, point_to_polyline_km

    path = RAW / "faults" / "turkey_faults.geojson"
    data = json.loads(path.read_text(encoding="utf-8"))
    faults = []
    for f in data["features"]:
        geom, props = f["geometry"], f["properties"]
        lines = ([geom["coordinates"]] if geom["type"] == "LineString"
                 else geom["coordinates"] if geom["type"] == "MultiLineString" else [])
        dip = parse_slip(props.get("average_dip")) or 90.0
        rake = parse_slip(props.get("average_rake"))
        if rake is None or pd.isna(rake):
            # slip_type'tan kaba kayma açısı: adlandırma sismolojinin standardı
            t = (props.get("slip_type") or "").lower()
            rake = (0.0 if "sinistral" in t else 180.0 if "dextral" in t
                    else -90.0 if "normal" in t else 90.0)
        for line in lines:
            pts = np.array([(x, y) for x, y, *_ in line], dtype=float)
            if len(pts) < 2:
                continue
            faults.append({"lon": pts[:, 0], "lat": pts[:, 1],
                           "dip": float(dip), "rake": float(rake)})

    out = []
    for _, c in cells.iterrows():
        d = np.array([point_to_polyline_km(c.lat_c, c.lon_c, f) for f in faults])
        f = faults[int(d.argmin())]
        # Doğrultu: hücreye en yakın parçanın azimutu (kuzeyden saat yönünde)
        seg = np.argmin((f["lon"] - c.lon_c) ** 2 + (f["lat"] - c.lat_c) ** 2)
        j = min(max(seg, 0), len(f["lon"]) - 2)
        dlon = (f["lon"][j + 1] - f["lon"][j]) * np.cos(np.radians(c.lat_c))
        dlat = f["lat"][j + 1] - f["lat"][j]
        strike = float(np.degrees(np.arctan2(dlon, dlat)) % 360.0)
        out.append({"cell_id": int(c.cell_id), "rec_strike": strike,
                    "rec_dip": f["dip"], "rec_rake": f["rake"],
                    "rec_fault_dist_km": float(d.min())})
    return pd.DataFrame(out)


def validate() -> bool:
    """İzmit 1999 -> Düzce fayı üzerinde POZİTİF ΔCFS beklenir."""
    # parse_dates KULLANILMAZ: karışık zaman biçimlerinde kolonu sessizce
    # str bırakır (bkz. src/ingest/catalog_io).
    gcmt = read_catalog(RAW / "gcmt" / "turkey_gcmt.csv")
    izmit = gcmt[(gcmt.time.dt.strftime("%Y-%m-%d") == "1999-08-17")
                 & (gcmt.mw > 7.0)]
    if izmit.empty:
        print("! İzmit olayı bulunamadı, doğrulama atlandı")
        return False
    ev = izmit.iloc[0]

    # Düzce depreminin kendi merkez üssü ve mekanizması alıcı olarak kullanılır
    duzce = gcmt[(gcmt.time.dt.strftime("%Y-%m-%d") == "1999-11-12")
                 & (gcmt.mw > 6.5)]
    if duzce.empty:
        print("! Düzce olayı bulunamadı, doğrulama atlandı")
        return False
    d = duzce.iloc[0]

    cfs = cfs_from_event(ev, np.array([d.lat]), np.array([d.lon]),
                         np.array([d.strike1]), np.array([d.dip1]),
                         np.array([d.rake1]))[0]
    ok = cfs > 0
    print(f"DOGRULAMA - Izmit 1999 (Mw {ev.mw:.2f}) -> Duzce "
          f"({d.lat:.2f}, {d.lon:.2f})")
    print(f"  dCFS = {cfs:+.3f} bar  ->  "
          + ("POZITIF, beklendigi gibi (Duzce 3 ay sonra kirildi)" if ok
             else "NEGATIF - kabul/isaret hatasi olabilir, incelenmeli"))
    return bool(ok)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", nargs="?", default="validate",
                    choices=["validate", "build"])
    ap.add_argument("--freq", default="MS", help="MS=aylık, D=günlük")
    ap.add_argument("--start", default=None)
    ap.add_argument("--end", default=None)
    ap.add_argument("--out", default="coulomb_features.csv")
    args = ap.parse_args()
    if args.stage == "validate":
        validate()
    else:
        build(args.freq, args.start, args.end, args.out)


def build(freq: str = "MS", start: str | None = None, end: str | None = None,
          out_name: str = "coulomb_features.csv") -> None:
    """Izgara için ZAMANLA DEĞİŞEN Coulomb özniteliklerini üretir.

    Her (hücre, referans tarihi) için, o tarihe kadar gerçekleşmiş büyük
    depremlerin ürettiği Coulomb gerilim değişimleri toplanır. Elastik gerilme
    değişimi kalıcıdır (viskoelastik gevşeme bu ölçekte ihmal ediliyor), bu
    yüzden kümülatif toplam doğru büyüklüktür — ayrıca "son olaydan gelen katkı"
    ve "son olaydan geçen süre" de verilir, çünkü tetiklenmiş sismisite zamanla
    söner ve model bu ikisini birlikte kullanabilmelidir.
    """
    if not validate():
        raise SystemExit("! doğrulama başarısız — öznitelik üretilmeyecek.")

    gcmt = read_catalog(RAW / "gcmt" / "turkey_gcmt.csv")
    gcmt = gcmt[gcmt.mw >= MIN_MW].sort_values("time").reset_index(drop=True)
    feat = pd.read_parquet(PROC / "grid_features.parquet")
    cells = (feat[["cell_id", "lat_c", "lon_c"]].drop_duplicates()
             .sort_values("cell_id").reset_index(drop=True))
    print(f"{len(gcmt)} kaynak olay (Mw>={MIN_MW}), {len(cells)} hücre")

    print("alıcı fay geometrisi hesaplanıyor...")
    rec = receiver_geometry(cells)
    cells = cells.merge(rec, on="cell_id")

    # Kaynak düzlemi seçimi için hücrelerin ortalama fay doğrultusu referans alınır
    ref_strikes = []
    for _, ev in gcmt.iterrows():
        d = np.hypot((cells.lat_c - ev.lat) * DEG_KM,
                     (cells.lon_c - ev.lon) * np.cos(np.radians(ev.lat)) * DEG_KM)
        near = cells[d <= 30]
        ref_strikes.append(float(near.rec_strike.median()) if len(near) else np.nan)
    gcmt["ref_strike"] = ref_strikes

    print("olay başına ΔCFS hesaplanıyor...".replace("Δ", "d"))
    per_event = np.zeros((len(gcmt), len(cells)))
    for i, ev in gcmt.iterrows():
        strike, dip, rake = pick_source_plane(ev)
        e = ev.copy()
        e["strike1"], e["dip1"], e["rake1"] = strike, dip, rake
        cfs = cfs_from_event(e, cells.lat_c.to_numpy(), cells.lon_c.to_numpy(),
                             cells.rec_strike.to_numpy(), cells.rec_dip.to_numpy(),
                             cells.rec_rake.to_numpy())
        # Uzak alanda katkı ihmal edilir; sayısal artıkları da temizler
        dist = np.hypot((cells.lat_c - ev.lat) * DEG_KM,
                        (cells.lon_c - ev.lon) * np.cos(np.radians(ev.lat)) * DEG_KM)
        cfs[dist > MAX_DIST_KM] = 0.0
        per_event[i] = cfs
        if (i + 1) % 10 == 0:
            print(f"  {i+1}/{len(gcmt)}", flush=True)

    # Referans tarihleri: varsayılan olarak grid_features'ınkiler (aylık), ama
    # günlük değerlendirme için ayrı bir takvim verilebilir. Pahalı kısım olan
    # olay başına ΔCFS matrisi tarihlerden BAĞIMSIZ olduğu için günlük çözünürlük
    # yalnızca biriktirme adımını uzatır.
    if freq == "MS" and start is None:
        ref_dates = pd.DatetimeIndex(sorted(
            pd.to_datetime(feat.ref_date, utc=True).unique()))
    else:
        ref_dates = pd.date_range(start, end, freq=freq, tz="UTC")
    print(f"{len(ref_dates)} referans tarihi ({freq})")
    # Zaman karşılaştırmaları epoch saniyesi üzerinden yapılır: tz-farkındalıklı ve
    # tz-bilgisiz damgaları karşılaştırmak TypeError veriyor ve bu hata sınıfı bu
    # projede birden fazla kez çıktı (bkz. src/ingest/catalog_io).
    ev_secs = epoch_seconds(gcmt["time"])
    ref_secs = epoch_seconds(ref_dates)
    rows = []
    for ref, ref_s in zip(ref_dates, ref_secs):
        past = np.flatnonzero(ev_secs < ref_s)
        if not len(past):
            continue
        cum = per_event[past].sum(axis=0)
        last = per_event[past[-1]]
        days = float(ref_s - ev_secs[past[-1]]) / 86400.0
        rows.append(pd.DataFrame({
            "cell_id": cells.cell_id.to_numpy(), "ref_date": ref,
            "cfs_cum": cum, "cfs_last": last,
            "days_since_cfs_event": days,
        }))

    out = pd.concat(rows, ignore_index=True)
    dst = PROC / out_name
    out.to_csv(dst, index=False)
    print(f"{len(out)} satır -> {dst}")
    print(out[["cfs_cum", "cfs_last", "days_since_cfs_event"]].describe().round(3).to_string())


if __name__ == "__main__":
    main()
