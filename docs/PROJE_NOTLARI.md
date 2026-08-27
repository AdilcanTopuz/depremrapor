# Deprem Tahmin Platformu (Türkiye)

**Canlı site: [depremrapor.com](https://depremrapor.com)**

Türkiye odaklı, **olasılıksal** deprem tahmin (operational earthquake forecasting, OEF) platformu.
Amaç: geçmiş deprem kataloğu + jeofizik veri katmanlarını (gerinim, Coulomb, fay kilitleme)
birleştirip, ızgara bazlı "önümüzdeki 1 gün / 7 gün / 30 gün içinde bu hücrede M≥X deprem
olasılığı" tahminleri üretmek; bunu ETAS baseline'a karşı dürüstçe backtest etmek ve bir web
sitesi olarak sunmak.

> **Bilimsel çerçeve (önemli):** Deterministik tahmin ("15 Mart'ta Elazığ'da 6.4 olacak")
> bilimsel olarak mümkün değildir ve bu proje bunu iddia etmez. Ürettiğimiz şey zaman
> pencereli **olasılık** tahminidir — İtalya (INGV OEF), ABD (USGS artçı tahminleri) ve
> Yeni Zelanda'da (GNS) resmi olarak yapılanın Türkiye versiyonu + ML araştırma kolu.
> Sitede her tahminin yanında bu uyarı yer almalıdır.

---

## 1. Proje stratejisi (iki kol)

**Kol A — Ürün (her hâlükârda çalışır):**
- Canlı deprem haritası (AFAD API, 1-5 dk'da bir), tarihsel katalog arama
- Artçı tahmin paneli (ETAS/Omori — bilimsel olarak kanıtlanmış, gerçekten çalışan kısım)
- Bölge/segment bazlı uzun vadeli risk kartları (Gutenberg-Richter, tekrarlama periyotları)
- Fay hattı katmanları (MTA diri fay haritası)

**Kol B — Araştırma (ETAS'ı geçme denemesi):**
- Nöral nokta süreci (RECAST tarzı) + jeofizik covariate'lar (gerinim hızı, Coulomb,
  fay kilitleme, b-değeri trendi, sismik sessizlik)
- pyCSEP ile ETAS'a karşı zaman-bazlı backtest (Kahramanmaraş 2023 test setinde)
- Gözden kaçmış olması en muhtemel boşluk: mevcut nöral modeller (RECAST, neural point
  processes) **sadece katalog** kullanıyor; jeofizik katman ekleme + Türkiye kataloğuna
  uygulama literatürde yapılmamış kombinasyon.

Kol B kazanırsa: yayınlanabilir bulgu (CSEP'e model sokulabilir). Kaybederse: elde yine
de Kol A'nın dürüst, çalışan ürünü kalır.

## 2. Veri kaynakları

| Kaynak | Ne | Erişim | Rol |
|---|---|---|---|
| AFAD apiv2 | Türkiye kataloğu + canlı | `https://deprem.afad.gov.tr/apiv2/event/filter?start=...&end=...&limit=...&orderby=timedesc` (JSON). `apiv2/event/latest` son 500 deprem. Parametreler: start, end, limit, offset, orderby (timedesc/magnitude), minlat/maxlat/minlon/maxlon, lat/lon/maxrad/minrad, eventid | **Birincil** katalog + canlı besleme. Ticari kullanım için deprem@afad.gov.tr |
| USGS FDSN | Global katalog 1900+ | `https://earthquake.usgs.gov/fdsnws/event/1/query` (bbox: 25-45E, 35-43N) | Tarihsel derinlik + çapraz doğrulama |
| Kandilli (KOERI) | Türkiye kataloğu | Resmi API yok; text/XML parse (topluluk: emirkabal/deprem-api vb.) | İkincil/doğrulama |
| EMSC | Avrupa-Akdeniz | FDSN + WebSocket | Gerçek zamanlı yedek |
| Kaggle: ozgecinko/turkey-earthquake-data-1914-2023 | 1994-2023 statik | Kaggle | Prototip/EDA |
| Kaggle: ayyuce/turkey-earthquakes | 1991-2023 statik | Kaggle | Prototip/EDA, çapraz kontrol |
| GEM Global Strain Rate Model (GSRM v2.1) | Gerinim hızı | Açık | Mekânsal covariate omurgası |
| COMET-LiCSAR (Sentinel-1 InSAR) | Deformasyon | Açık | Gerinim haritası detayı |
| TUSAGA-Aktif (GPS) | ~150 istasyon deformasyon | Kurumsal başvuru gerekebilir; yayınlardan türetilmiş gerinim haritaları açık | Fay kilitleme |
| MTA diri fay haritası | Fay geometrisi | Açık (shapefile) | Harita katmanı + segment öznitelikleri |
| AFAD TADAS | Kuvvetli yer hareketi | tadas.afad.gov.tr | İleri analiz (opsiyonel) |

**Kullanılmayacaklar:** radon, kuyu suyu, elektromanyetik "öncüler" — tekrarlanabilir sonuç
yok, Türkiye için sistematik veri yok.

## 3. Metodoloji

### 3.1 Katalog hazırlama
1. AFAD (2003+) + USGS (1900+) çek, birleştir.
2. **Tekilleştirme:** aynı olay farklı kataloglarda → zaman (±30 sn) + konum (±50 km)
   eşleştirmesi; büyüklükleri Mw'ye normalize et (Md/Ml→Mw dönüşüm bağıntıları).
3. **Completeness (Mc) analizi:** dönem bazlı tamlık büyüklüğü (eski yıllarda küçük
   depremler kayıtlarda yok — model bunu bilmeli).
4. **Declustering (ana şok ayrımı):** Zaliapin nearest-neighbor veya Reasenberg.
   Hedef "ana şok" olduğu için bu adım zorunlu.

### 3.2 Izgara ve hedef değişken
- Türkiye + tampon: 25-45°E, 35-43°N, 0.25°×0.25° hücreler.
- Her hücre × zaman penceresi (1g / 7g / 30g / 90g) için: "M≥5.0 (ve M≥5.5) ana şok
  gerçekleşti mi?" ikili etiket + beklenen olay sayısı (rate) hedefi.

### 3.3 Öznitelikler (hücre bazlı)
- Katalogdan: son 30/90/365/3650 gün olay oranları, b-değeri ve trendi (maximum
  likelihood, Mc üstü), sismik sessizlik (Z-testi), derinlik dağılımı kayması,
  kümelenme oranı, moment birikimi/açığı, en büyük olaydan geçen süre.
- Jeofizikten: GSRM gerinim hızı (2. invaryant), fay segmentine uzaklık, segment son
  kırılma yaşı / tekrarlama oranı (paleosismoloji), Coulomb gerilim değişimi
  (son M≥6.5 olaylardan, Okada çözümü ile).

### 3.4 Modeller
1. **Baseline 1:** Uzun vadeli Poisson (smoothed seismicity).
2. **Baseline 2 (asıl rakip):** ETAS — açık implementasyon: `etas` (Mizrahi/ETH) veya
   pyCSEP uyumlu ETAS.
3. **ML-1:** LightGBM/XGBoost (tablosal öznitelikler; SHAP ile "hangi katman katkı
   veriyor?" sorusunun cevabı).
4. **ML-2:** Nöral nokta süreci — RECAST (github: dascher-cousineau/recast benzeri açık
   kod) + covariate koşullama. EarthquakeNPP benchmark kod tabanı şablon olarak.

### 3.5 Değerlendirme (projenin kalbi)
- **Zaman bazlı bölme:** eğitim 1990-2015, doğrulama 2016-2020, test 2021-2023
  (Kahramanmaraş 6 Şubat 2023 testte — model onu "görmeden" değerlendirilir).
- Metrikler: log-likelihood kazancı (ETAS'a göre bilgi kazancı/olay), Molchan diyagramı,
  ROC/AUC, alan-kaplama eğrisi; pyCSEP N-test, S-test, T-test.
- M≥5.5 olay sayısı az (~yüzler) → güven aralıkları ve istatistiksel güç raporlanmalı.
- Literatür dersi: 1994-2019 arası ANN-deprem makalelerinin çoğu baseline'sız/zayıf
  baseline'lı çıktı ve değersiz bulundu. **ETAS'ı geçmeyen hiçbir sonuç "başarı" olarak
  sunulmayacak.**

## 3.6 Sonuçlar (Ağustos 2026 itibarıyla)

### Veri
Dört kaynak birleştirildi (AFAD 265.572, Kandilli 72.473, EMSC, USGS) →
**304.168 olay, 1904-2026**. Tekilleştirmede %27 kopya düşürüldü.

Mw dönüşümü Türkiye verisiyle yeniden kalibre edildi (Kandilli'nin çoklu büyüklük
kayıtlarından, 16.848 ML+Mw çifti, ortogonal regresyon): literatürün ML bağıntısı
büyüklükleri M4 civarında **0,22 birim şişiriyormuş**.

Bağımsız fiziksel doğrulama: 6 Şubat 2023 sonrası artçı azalımı **Omori p = 1,01**
(literatürde tipik 0,9-1,2), 1-100 gün arasında üç kademe boyunca düz.

### Model sonuçları -> docs/MANSET.md

Sonuç sayılarının tamamı ve künyeleri **`docs/MANSET.md`** dosyasındadır.
Bu bölümde yalnızca özet durur; sayı çoğaltmak, birinin bayatlaması demektir.

**Ana bulgu — kazancın iki katmanı ve bir sınırı:**

* **Dizi dönemlerinde büyük.** Kahramanmaraş penceresinde olay başına bilgi
  kazancı +3,81 (30 gün) ile +2,47 (365 gün) arasında.
* **Dizi dışında küçük ama anlamlı, 180 güne kadar.** +0,550 / +0,313 / +0,287
  (30/90/180 gün), alt sınırlar +0,245 / +0,031 / +0,007. 365 günde
  belirsizliğe geçiyor (GA [-0,049; +0,506], MDE 0,404).
* **Kazanç zamanda aşırı yoğun.** Olay teriminin %98,8'i en yüksek 10 olaylı
  başlangıçtan; ETAS olaylı başlangıçların %50,8'inde Poisson'a kaybediyor.

**CSEP çıtası (aylık, M>=5,0, 102 olay):** T-testi +2,398 [+2,104; +2,692]
(analitik) — S-testini geçiyor, N-testinde aylık güncelleme sınırı nedeniyle
reddediliyor (Şubat 2023 hariç tutulduğunda 1,14x ile uyumlu).

**Haftalık kurulum (M>=4,5, 252 pozitif):** AUC farkı +0,1407
[+0,0761; +0,2144]; olay başına bilgi kazancı +1,068 nat.

### ML (Kol B) ilk sınavı: ETAS'ı GEÇMEDİ -> docs/FAZ3_SONUC.md

§3.5 kuralı uygulandı: **ETAS'ı geçmeyen hiçbir sonuç "başarı" olarak
sunulmuyor.** LightGBM, haftalık kurulumda (M>=4,5, 252 olay) ETAS'a
**EŞDEĞER** çıktı ve §3.5 ölçütünü **KARŞILAMADI**:

    AUC   ETAS 0,7909 | ML 0,7869
    ML - ETAS  +0,018 nat/olay  [-0,164; +0,196]  MDE 0,256

Protokol koşudan önce commit'lendi (arama uzayı, seçim kuralı, eşdeğerlik
bandı); 36 bileşim x 3 tohum arandı; test seti seçim sonrası bir kez
değerlendirildi (`docs/TEST_DOKUNUSLARI.md`).

**Sonuç bir başarısızlık değil, bir ölçüm:** ML, ETAS'ın **arka plan**
bileşenini biraz daha iyi kuruyor ama **tetiklenme** bileşenini hiç öğrenmiyor
(n30'un SHAP payı %1,7; dizi penceresinde 19,8 olay bekliyor, gözlenen 59).
Ayrıca kalibre değil (gözlenen/beklenen 1,82) ve bu hâliyle **operasyonel
katmana alınamaz.**

Eksik olan hiperparametre değil, tetiklenmeyi ifade edebilen bir **model
sınıfı**. Bir sonraki adımın sorusu bu ölçümden doğdu.

### NPP (Kol B, ikinci sınav): ÖLÇÜTÜ GEÇTİ, ürün kapısını GEÇMEDİ

Toplamsal nöral ETAS (λ = μ + Σ g, öğrenilen tetiklenme çekirdeği), aynı
436.800 hücre-pencerede sınandı. **Hüküm ve ayrıştırma ayrılmaz bir bloktur**
(metrik notu: IG tek başına okunmaz):

    NPP - ETAS   +0,174 nat/olay  [+0,032; +0,317]   MDE 0,204
                 = OLAY -0,088  +  MARUZİYET +0,262
    kalibrasyon  NPP 1,52  |  ETAS 1,09  |  Poisson 1,24
    AUC          NPP 0,7904  |  ETAS 0,7909   (berabere)

**§3.5 ölçütü KARŞILANDI** (aralık tümüyle sıfırın üstünde) — projenin ilk
"geçti" beyanı. Üç çekinceyle birlikte okunur:

1. Üstünlüğün çoğu **maruziyet teriminden** gelir: NPP toplamı %34 eksik
   tahmin ediyor ve IG bunu ödüllendiriyor. Gerçekleşen olaylarda NPP hâlâ
   ETAS'ın altında.
2. Etki **MDE'nin altında** (+0,174 < 0,204): anlamlı ama güçsüz; etki
   büyüklüğü abartılmış olabilir.
3. **Ürün kapısı GEÇİLMEDİ** (kalibrasyon 1,52, band [0,80; 1,25]).
   NPP operasyonel katmana ALINMAZ.

**Asıl bulgu, hükümlerin arasında:** tetiklenme **kısmen öğrenildi** (dizi
penceresi beklentisi LightGBM'in 19,8'inden 41,8'e çıktı; ETAS 84,3, gözlenen
59), **şekil ETAS'tan iyi** (önceden kayıtlı birincil kesit H1: dizi-dışı
+0,316 [+0,159; +0,469]), **seviye öğrenilemedi** (kalibrasyon 1,52).

> Model sınıfı tetiklenmeyi ifade edebiliyor ve kısmen öğreniyor; öğrenemediği
> şey seviyedir.

Ayrıntı ve kapsam kilidi: **`docs/NPP_SONUC.md`**.

**Üç bölgede karar verilemiyor** (Marmara, Batı Anadolu, Kuzey Anadolu doğusu):
olay sayısı düşük, MDE ~1,1 nat. Bu bir zayıflık bulgusu DEĞİL, belirsizliktir.

> Güven aralıkları yalnızca gözlenen olay sayısı belirsizliğini kapsar;
> parametre belirsizliğini ve model yanlış-belirlemesini kapsamaz.

**Geçersiz sayılar.** Bu bölümde daha önce +2,287, +1,071, %92, %84 gibi
değerler duruyordu. Hepsi geçersizdir ve gerekçeleri
`docs/SAYI_HARITASI.md` dosyasındadır. Denetim boyunca bulunan 14 vaka
`docs/VAKA_DEFTERI.md`'de kayıtlıdır.

## 4. Web sitesi mimarisi

**Karar (26 Ağu 2026): EN AZ BİLEŞEN.** Önceki plan (FastAPI + PostgreSQL +
PostGIS + Redis + Celery + Next.js) yazılmış ama üretilmemiş bir mimariydi;
fiilî profil ölçülünce teyide açıldı ve daraltıldı.

    ölçülen profil    günde bir üretilen GeoJSON · tek dosyalık katalog ·
                      bir zamanlanmış görev
    karar             statik yayın + cron + dosya tabanlı arşiv

- **Yayın:** cron'un ürettiği GeoJSON/JSON dosyaları, versiyonlu dizinde,
  künyeleriyle, sabit URL'lerden sunulur. İlk sürümde ayrı bir API katmanı
  YOKTUR — "API" dediğimiz şey bu dosyaların adresleridir.
- **Görevler:** cron (AFAD çekme + günlük tahmin + büyük deprem tetiklemeli
  yeniden üretim).
- **Frontend:** statik site + MapLibre GL (GeoJSON'u istemci tarafında okur,
  sunucu gerektirmez). Sayfaların çoğu zaten statiktir: metodoloji, kapsam
  beyanları, bölge kartları. Yalnızca harita dinamiktir.
- **Dağıtım:** statik barındırma; VPS gerekmez.

**"İhtiyaç doğduğunda" statüsündekiler** (reddedilmedi, ertelendi):
FastAPI ya da benzeri bir API katmanı (kurumsal kullanım gündeme gelirse),
PostgreSQL + PostGIS (mekânsal sorgu ihtiyacı ölçülürse), Redis (yük
ölçülürse), Celery (görev sayısı artarsa), Next.js (dinamik sayfa ihtiyacı
doğarsa).

İlke: **bileşen, gerekliliği ölçülmeden eklenmez**
(`docs/DENETIM_MIRASI.md`).

## 5. Klasör yapısı

```
deprem-tahmin/
├── README.md               ← bu dosya
├── requirements.txt
├── data/
│   ├── raw/                ← indirilen ham veriler (git'e girmez)
│   └── processed/          ← birleşik katalog, ızgara öznitelikleri
├── scripts/
│   ├── 01_download_afad.py     ← AFAD apiv2'den tarihsel katalog (yıl yıl sayfalı)
│   ├── 02_download_usgs.py     ← USGS FDSN 1900+ Türkiye bbox
│   └── 03_download_gsrm.md     ← gerinim/fay verisi indirme talimatları
├── src/
│   ├── ingest/merge_catalogs.py    ← birleştirme + tekilleştirme + Mw normalizasyonu
│   ├── ingest/declustering.py      ← Zaliapin nearest-neighbor declustering
│   ├── features/grid_features.py   ← ızgara + b-değeri + oran öznitelikleri
│   ├── models/baseline_poisson.py  ← smoothed seismicity baseline
│   ├── models/etas_notes.md        ← ETAS kurulum/kullanım notları
│   └── eval/backtest.py            ← zaman bazlı bölme + metrikler iskeleti
├── notebooks/              ← EDA defterleri
└── web/                    ← statik site (üretilmiş çıktı `yayin` dalında)
```

## 6. Hızlı başlangıç

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python scripts/01_download_afad.py --start 2003 --end 2026   # AFAD (erişim gerekiyor, aşağı bak)
python scripts/02_download_usgs.py  --start 1900 --end 2027   # USGS kataloğu
python scripts/02b_download_emsc.py --start 1998 --end 2027   # EMSC kataloğu
python -m src.ingest.merge_catalogs                          # birleşik katalog
python -m src.features.completeness                          # dönem bazlı Mc + b
python -m src.ingest.declustering                            # ana şok ayrımı
python -m src.features.grid_features                         # ızgara öznitelikleri
python -m src.models.baseline_poisson                        # ilk baseline
python -m src.eval.backtest                                  # zaman bazlı değerlendirme
```

> **AFAD erişimi — DPI atlatma araçlarına dikkat:** `deprem.afad.gov.tr` TLS
> bağlantısı bazı makinelerde sıfırlanır. Sebep genellikle AFAD veya ISP değil,
> makinede çalışan bir DPI-atlatma aracıdır (GoodbyeDPI, Zapret vb.): bunlar TLS
> ClientHello paketini parçalar, AFAD'ın önündeki F5 BigIP de bu el sıkışmayı
> reddeder. Ayırt edici belirti: port 80 çalışır, port 443 sıfırlanır ve SNI'siz
> IP bağlantısı bile başarısız olur. Aracı geçici kapatıp indirmeyi yapın —
> `data/raw/afad/` altına aylık önbelleklenir, sonra geri açabilirsiniz.

## 7. Yol haritası özeti

- **Faz 1 (2-3 hafta):** Veri altyapısı — katalog indirme/birleştirme/declustering, Mc analizi, EDA.
- **Faz 2 (3-4 hafta):** Baseline'lar (Poisson, ETAS) + pyCSEP backtest çerçevesi.
- **Faz 3 (3-4 hafta):** ML modelleri (LightGBM → nöral nokta süreci + covariate) ve karşılaştırma.
- **Faz 4 (3-4 hafta):** Web sitesi (FastAPI + Next.js + MapLibre), canlı AFAD beslemesi.
- **Faz 5:** Operasyon — bildirimler, izleme, (istenirse) CSEP'e model gönderimi.

## 8. Yasal/etik notlar

- Tahminler daima olasılık olarak, güven aralığı ve metodoloji linkiyle sunulur.
- Belirli tarih/şiddet iddiası taşıyan dil asla kullanılmaz (panik + hukuki risk).
- AFAD verisi ticari kullanım: deprem@afad.gov.tr'den izin.
- Kaynak gösterimi: AFAD, Kandilli/KOERI, USGS, GEM, COMET-LiCSAR, MTA.
