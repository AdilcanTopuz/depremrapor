"""KABA sızıntı kanaryası + boru hattı sağlık kontrolü.

KAPSAM UYARISI (V16'nın dersi: beyan, kanıtın kapsamını aşmasın).

Bu modül bir "sızıntı dedektörü" DEĞİLDİR. Ölçüldü: performans tabanlı tespit
bu rejimde kısmi sızıntıya KÖRDÜR -- hedefin yarısını doğrudan veren bir
öznitelik AUC'yi +0,0000 değiştirdi (`docs/KANARYA_BULGUSU.md`). Kök neden:
`min_child_samples=200` ve eğitimde 212 pozitif; 200 satırdan az etkileyen
sızıntı yaprak oluşturamıyor.

NE YAPAR: (a) KABA sızıntıyı (hedefin kendisi ya da tam pencere) yakalar,
(b) boru hattının sağlığını kontrol eder -- temiz skorun beklenen aralıkta
olması.

NE YAPMAZ: kısmi sızıntıyı yakalamaz. Onun için YAPISAL engel vardır:
`src/features/history_view.py`.

NEDEN. `grid_features`'ın "yalnızca geçmişe bakar" garantisi kodda vardı
(`searchsorted(t, refs, side="left")`) ve OKUNARAK doğrulanmıştı. V15'in dersi
tam buraya oturur: bir satırı okuyarak doğrulamak, izleme listesini okuyarak
"korunuyor" demekle aynı işlemdir. **Beyan var, mekanizma yok.**

ML koşuları başladıktan sonra sızıntı bulunursa bütün koşular çöpe gider.

KANARYANIN ÖLMESİ BAŞARIDIR. Bu modül KASTEN sızıntı üretir ve boru hattının
onu yakalayıp yakalamadığını sınar. Testler "yakalandığında geçer" mantığıyla
yazılmıştır. Sonradan okuyan biri "neden kasten sızıntı ekliyoruz?" diye sorup
silmemelidir: silinen şey sızıntı değil, sızıntı DEDEKTÖRÜDÜR.

ÜÇ SEVİYE

1. KABA      hedefin kendisi öznitelik olarak. En kaba sızıntı; asıl sınanan,
             boru hattının "imkânsız derecede iyi skor"u ALARM olarak
             raporlayıp raporlamadığıdır -- sessizce kutlamak yerine.
2. ZAMANSAL  referans tarihinden SONRASININ verisiyle hesaplanmış öznitelik.
             `side="left"` garantisinin uçtan uca testi.
3. DOLAYLI   ölçekleme istatistiklerine test dönemini karıştırmak. Hiçbir
             öznitelik "geleceğe bakmaz"; yalnızca normalizasyon sabiti bilir.
             V5 sınıfının (yanlış belirsizlik kaynağı) sızıntı karşılığı.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROC = ROOT / "data" / "processed"

# --- ALARM EŞİĞİ ------------------------------------------------------------
#
# GEREKÇE (ölçülmüş değerlerle):
#
#   Poisson temel model (haftalık analitik kurulum) : AUC 0,6503
#   ETAS (analitik, fizik temelli, tam katalog)     : AUC 0,7909
#   LightGBM (önceki denemeler, aylık kurulum)      : AUC ~0,77
#
# En iyi ölçülmüş model 0,79 civarındadır. Deprem oluşumu büyük ölçüde
# öngörülemezdir; nadir olayların neredeyse kusursuz ayrıştırılması fiziksel
# olarak makul değildir.
#
# 0,90 eşiği, ölçülmüş en iyinin 0,11 üstünde ve hiçbir meşru modelin
# yaklaşmadığı bir düzeydedir. Bu eşiği aşan bir sonuç YANLIŞ olmayabilir --
# ama İNANILMADAN ÖNCE İNCELENMELİDİR. Alarm bir hüküm değil, durma işaretidir.
#
# İkinci kural (sıçrama): bilinen en iyi modeli 0,10'dan fazla geçmek de
# alarmdır. Gerçek ilerleme bu ölçekte tek adımda gelmez.
ALARM_AUC = 0.90
ALARM_JUMP = 0.10
BEST_KNOWN_FALLBACK = 0.7909   # taban verilmezse; ETAS dondurulmuş değeri

# KARŞILAŞTIRMA TABANI. Eskiden sabitti (0,7909 = ETAS, TEST dönemi). İki sorun
# vardı: (a) test döneminden geliyordu, oysa kanaryanın test setine dokunması
# gereksizdir -- sızıntı doğrulama setinde de aynı derecede görünür; (b) farklı
# bir bölümden gelen sabitle kıyaslamak eşleşmemiş bir karşılaştırmaydı.
#
# Artık taban, AYNI tabloda AYNI bölümde ölçülen TEMİZ MODELDİR. Eşleşmiş
# karşılaştırma daha duyarlıdır ve tablo değiştiğinde kendini günceller.
#
# EŞİKLER DEĞİŞTİRİLMEDİ (0,90 ve 0,10). Sonuç görüldükten sonra eşik oynatmak
# ölçütü sonuca göre seçmek olurdu; değişen yalnızca tabanın NEREDEN geldiğidir.
_TEMIZ_TABAN: float | None = None


def temiz_taban(target: str) -> float:
    """Sızıntısız modelin DOĞRULAMA AUC'si — karşılaştırma tabanı.

    Bir kez ölçülür ve süreç boyunca yeniden kullanılır.
    """
    global _TEMIZ_TABAN
    if _TEMIZ_TABAN is None:
        _TEMIZ_TABAN = _fit_auc(_load(target), [], target)
    return _TEMIZ_TABAN


class LeakageAlarm(Exception):
    """Sızıntı şüphesi. Skor kutlanmadan önce incelenmelidir."""


def check_alarm(auc: float, label: str = "", raise_on_alarm: bool = True,
                taban: float | None = None) -> dict:
    """Skor 'şüpheli derecede iyi' mi?

    Bu fonksiyonun kendisi de kural 9'a tabidir: alarmın çalıştığının kanıtı,
    alarmın ÇALMASIDIR. `tests/test_leakage_canary.py` bunu sınar.
    """
    taban = BEST_KNOWN_FALLBACK if taban is None else taban
    reasons = []
    if auc > ALARM_AUC:
        reasons.append(
            f"AUC {auc:.4f} > mutlak eşik {ALARM_AUC}: bu problemde hiçbir "
            f"meşru model bu düzeye yaklaşmadı (temiz taban: "
            f"{taban:.4f})")
    if auc > taban + ALARM_JUMP:
        reasons.append(
            f"AUC {auc:.4f}, temiz tabanı ({taban:.4f}) "
            f"{auc - taban:+.4f} geçiyor: bu ölçekte tek adımlık "
            f"ilerleme beklenmez")
    out = {"auc": float(auc), "alarm": bool(reasons), "reasons": reasons,
           "label": label}
    if reasons and raise_on_alarm:
        raise LeakageAlarm(
            f"SIZINTI ALARMI [{label}]: " + " | ".join(reasons))
    return out


# --- veri ------------------------------------------------------------------

def _load(target: str) -> dict:
    """lgbm.load_dataset ile AYNI yoldan okur — kanarya boru hattını sınamalı.

    TEST BÖLÜMÜ SİLİNİR. Kanaryanın işi sızıntı tespitidir, test performansı
    değil; sızıntı doğrulama setinde de aynı derecede görünür. Test setine
    dokunmak gereksiz bir dokunuştu (bkz. docs/TEST_DOKUNUSLARI.md).

    Silme, "kullanmayacağız" sözü değil VERİNİN YOKLUĞUDUR -- `HistoryView` ve
    arama betiğiyle aynı ilke. Kanarya kodu ne kadar yanlış yazılırsa yazılsın
    olmayan bölümü okuyamaz.
    """
    from src.models.lgbm import load_dataset

    data = load_dataset(target)
    data.pop("test", None)
    return data


def _fit_auc(data: dict, extra: list, target: str, seed: int = 0) -> float:
    """GERÇEK eğitim yolunu kullanır ve test AUC'sini döndürür.

    Kanaryanın kendi modelini kurması yanlıştı: ilk sürümde oyuncak bir
    LightGBM (lr 0,1, 31 yaprak, erken durdurma yok) kullanılıyordu ve TEMİZ
    model 0,4584 -- şanstan kötü -- veriyordu. Kanarya o hâlde boru hattını
    değil oyuncağı sınıyordu.

    Gerçek yol: `lgbm.train` (lr 0,02, 15 yaprak, min_child_samples 200,
    lambda_l2 10, doğrulama setinde erken durdurma).
    """
    from sklearn.metrics import roc_auc_score
    from src.models.lgbm import CATALOG_FEATURES, train

    r = train(target, seed=seed, quiet=True, data=data, extra_features=extra)
    feats = list(CATALOG_FEATURES) + list(extra)
    va = data["val"]          # TEST DEĞİL -- bkz. _load
    p = r["model"].predict(va[feats], num_iteration=r["model"].best_iteration)
    return float(roc_auc_score(va[target].astype(int), p))


# --- KANARYA 1: KABA -------------------------------------------------------

def canary_gross(target: str = "target_30d_m50_all") -> dict:
    """Hedefin KENDİSİ öznitelik olarak eklenir.

    Beklenen: AUC ~1,0 ve ALARM. Alarm çalmazsa, boru hattı bir sonraki gerçek
    sızıntıyı da sessizce mükemmel skor olarak raporlar.
    """
    from src.models.lgbm import CATALOG_FEATURES

    data = _load(target)
    # ÜÇ bölmeye de eklenir: gerçek eğitim yolu erken durdurma için "val"i
    # kullanır ve orada öznitelik yoksa KeyError verir. İlk sürümde bu atlandı.
    for split in [x for x in ("train", "val", "test") if x in data]:
        data[split] = data[split].copy()
        data[split]["SIZINTI_hedef"] = data[split][target]
    auc = _fit_auc(data, ["SIZINTI_hedef"], target)
    return check_alarm(auc, "kaba: hedef öznitelik olarak",
                       raise_on_alarm=False, taban=temiz_taban(target))


# --- KANARYA 2: ZAMANSAL ---------------------------------------------------

def canary_temporal(target: str = "target_30d_m50_all",
                    days_ahead: int = 1) -> dict:
    """Referans tarihinden SONRASININ verisiyle bir öznitelik üretilir.

    `side="left"` garantisinin uçtan uca testi: pencere sınırı gerçekten kapalı
    mı? Öznitelik, ref ile ref+days_ahead arasındaki olay sayısıdır -- yani
    tanım gereği geleceğe bakar.
    """
    from src.config import cell_id
    from src.ingest.catalog_io import epoch_seconds, read_catalog
    from src.models.lgbm import CATALOG_FEATURES

    data = _load(target)
    cat = read_catalog(PROC / "catalog_declustered.csv")
    cat = cat.dropna(subset=["lat", "lon", "mw"]).sort_values("time")
    cat["cell_id"] = cell_id(cat.lat, cat.lon)
    t = epoch_seconds(cat["time"])

    for split in [x for x in ("train", "val", "test") if x in data]:
        d = data[split].copy()
        refs = epoch_seconds(pd.to_datetime(d["ref_date"], utc=True))
        # ref ile ref+days_ahead arasi: GELECEK
        out = np.zeros(len(d))
        for cid, g in cat.groupby("cell_id", sort=False):
            m = (d.cell_id == cid).to_numpy()
            if not m.any():
                continue
            tt = t[cat.cell_id.to_numpy() == cid]
            r = refs[m]
            lo = np.searchsorted(tt, r, side="left")
            hi = np.searchsorted(tt, r + days_ahead * 86400.0, side="left")
            out[m] = hi - lo
        d["SIZINTI_gelecek"] = out
        data[split] = d

    auc = _fit_auc(data, ["SIZINTI_gelecek"], target)
    return check_alarm(auc, f"zamansal: ref+{days_ahead} gün penceresi",
                       raise_on_alarm=False, taban=temiz_taban(target))


# --- KANARYA 3: DOLAYLI ----------------------------------------------------

def canary_indirect(target: str = "target_30d_m50_all") -> dict:
    """ÖLÇEKLEME SIZINTISI — ağaç modellerinde YAPISAL OLARAK ETKİSİZ.

    ÖLÇÜLDÜ (2026-08-24, haftalık tablo): temiz 0,7847 · sızıntılı 0,7847 ·
    fark -0,0000.

    Sebep boru hattının sağlığı DEĞİL, kanalın yokluğudur: ağaç bölmeleri
    monoton dönüşümlere duyarsızdır, standardizasyon LightGBM'i hiç etkilemez.
    "Koştu, etki yok" diye raporlamak var olmayan bir korumanın varlığını ima
    ederdi (V16 dersi: beyan, kanıtın kapsamını aşamaz).

    Bu kanarya NÖRAL adıma taşınmıştır; orada ölçekleme gerçek bir kanaldır ve
    kanarya ilk kez anlamlı olacaktır. Ağaç modellerinde çağrılırsa hata verir.
    """
    raise NotImplementedError(
        "DOLAYLI kanarya ağaç modelleri için yapısal olarak etkisizdir "
        "(ağaçlar monoton dönüşümlere duyarsız). Nöral adıma taşındı; "
        "bkz. docs/FAZ3_PLAN.md ve bu fonksiyonun açıklaması.")


def _canary_indirect_neural(target: str = "target_30d_m50_all") -> dict:
    """Nöral adım için saklanan özgün gövde (o adımda etkinleştirilecek)."""

    from src.models.lgbm import CATALOG_FEATURES

    feats = list(CATALOG_FEATURES)
    data = _load(target)

    def standardize(d: dict, stats_from: str) -> dict:
        src = pd.concat([d[s] for s in stats_from.split("+")])
        mu = src[feats].mean()
        sd = src[feats].std().replace(0, 1.0)
        out = {}
        for s in ("train", "val", "test"):
            x = d[s].copy()
            x[feats] = (x[feats] - mu) / sd
            out[s] = x
        return out

    temiz = standardize(data, "train")
    sizintili = standardize(data, "train+val+test")
    return {
        "auc_temiz": _fit_auc(temiz, [], target),
        "auc_sizintili": _fit_auc(sizintili, [], target),
        "label": "dolaylı: ölçekleme istatistiklerine test dönemi karıştı",
    }


def main() -> None:
    import json

    print("SIZINTI KANARYALARI — kanaryanın ölmesi BAŞARIDIR\n")
    sonuc = {}

    r1 = canary_gross()
    sonuc["kaba"] = r1
    print(f"1) KABA      AUC {r1['auc']:.4f}  alarm: {r1['alarm']}")
    for x in r1["reasons"]:
        print(f"     - {x}")

    r2 = canary_temporal()
    sonuc["zamansal"] = r2
    print(f"2) ZAMANSAL  AUC {r2['auc']:.4f}  alarm: {r2['alarm']}")
    for x in r2["reasons"]:
        print(f"     - {x}")

    r3 = canary_indirect()
    sonuc["dolayli"] = r3
    print(f"3) DOLAYLI   temiz {r3['auc_temiz']:.4f} | "
          f"sızıntılı {r3['auc_sizintili']:.4f} | "
          f"fark {r3['auc_sizintili'] - r3['auc_temiz']:+.4f}")

    (PROC / "leakage_canary.json").write_text(
        json.dumps(sonuc, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n-> {PROC / 'leakage_canary.json'}")


if __name__ == "__main__":
    main()
