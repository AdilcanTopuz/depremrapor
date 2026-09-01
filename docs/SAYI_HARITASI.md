# Sayı haritası: hangi sayı hangi kuruluma ait, hangileri geçersiz

Bu projede bir sayı bir kez bayatladı ve bunu geç fark ettik (CSEP sonuçları
STAI yeniden kalibrasyonundan önceki parametrelerle üretilmişti ve README'de
duruyordu). Aynısının tekrarlanmaması için dolaşımdaki her sayının kurulumu
burada kayıtlıdır.

**Kural 1: bu tabloda "GEÇERSİZ" işaretli bir sayı hiçbir yerde alıntılanmaz.**

**Kural 2 (MEKANİZMA, süreç değil): her kurulum ya da yöntem değişikliğinde bu
dosya AYNI commit'te güncellenir.** Bu kural bir pre-commit hook ile ZORUNLU
kılınmıştır (`scripts/check_number_map.py`): izlenen dosyalardan biri değişmiş
ama bu dosya değişmemişse commit reddedilir.

Gerekçe: "sürece güvenme, mekanizmaya güven". Statik kalırsa belgenin kendisi
bayatlar ve amacını yitirir -- ki bu belge tam olarak bayat sayıları önlemek
için var. Koruyucunun kendisi de 7 testle sınanır (tests/test_number_map_guard.py):
bir koruyucu, koruduğu sanılıp korumuyorsa korumamaktan kötüdür.

Aşağıdaki "son güncelleme" sütunu, her satırın hangi olayla son kez
değerlendirildiğini taşır.

**Son güncelleme:** 28 Ağustos 2026 — **hiçbir sayı etkilenmedi.**
`forecast_now.py`'deki tek değişiklik, indirici başarısızlığında ekrana
hangi satırın basılacağıdır (V61 yan bulgusu: hata mesajı hatayı
göstermiyordu). Model, katalog, parametre ve eşiklerde değişiklik yok.

Not: 28 Ağustos'ta koşu #43–#63 arası yayın yapılamadı (V60, V61).
Yayımlanmış hiçbir sayı geçersiz olmadı; yalnızca yenisi üretilemedi ve
site bu süre boyunca yayın yaşını doğru şekilde gösterdi.

daha önce: — **YAYIMLANAN OLASILIKLAR
DEĞİŞTİ; bir önceki kayıt bunu erken ilan etmişti.**

Üçüncü güncellemede değişikliğin yürürlüğe girdiği yazılmıştı, ama girmemişti:
`forecast_now` tarafındaki yuvarlama kaldırılmıştı, `pipeline.calistir`
ise `origin`'i kendisi hesaplayıp geçiriyordu ve orada yuvarlama duruyordu.
Hat gerçekten çalıştırılınca görüldü (yayın dizini `2026-08-27T0000`).
Kural artık `forecast_now.saate_yuvarla` içinde tek yerde ve iki testle
sabitlendi. **Değişiklik bu kayıttan itibaren yürürlüktedir.**
 Tahmin başlangıcı artık gece yarısına yuvarlanmıyor, koşunun kendi
anından başlıyor (`forecast_now._simdi`), ve hat günde bir yerine üç saatte
bir koşuyor.

Etkilenen: yayımlanan `probability` ve `times_normal` değerlerinin **tamamı**.
Sayılar yanlış değildi; **pencereleri** farklıydı. Eskiden "bugün 00:00'dan
itibaren N gün" deniyordu ve koşu 06:30'da yapıldığı için pencerenin 6,5 saati
üretim anında çoktan geçmişti. Şimdi pencere üretim anından başlıyor, yani
"önümüzdeki N gün" ifadesi harfiyen doğru.

Geçersiz kılınan bir ölçüm YOK: geriye dönük değerlendirmeler
(`csep_results*.json`, `daily_backtest.json`, `gain_breakdown.json`,
FAZ3/NPP sonuçları) kendi ilan edilmiş başlangıçlarıyla üretildi ve bu
değişiklikten etkilenmez. Değişen şey CANLI yayının pencere tanımıdır.

Tazelik sözleşmesi de değişti: `YAYIN_ARALIGI_SAAT` 24 -> 3,
`BAYAT_YAYIN_ESIGI_SAAT` 36 -> 7.

daha önce (aynı gün): **hiçbir sayı etkilenmedi.** `pipeline.py`'ye `YAYIN_ADRESI` sabiti ve manifeste `yayin_adresi` alanı eklendi; alan adı (depremrapor.com) künyeye, sayfaların canonical/og etiketlerine ve üretilen sitemap'e oradan gider. Model, katalog, parametre ve eşiklerde değişiklik yok; yayımlanan tüm sayılar geçerliliğini korur.
daha önce (aynı gün): **hiçbir sayı etkilenmedi.** `forecast_now.py`'deki tek değişiklik, uyarı metninin sonundaki gönderme yolunun `docs/ROADMAP.md` yerine `metodoloji.html` olmasıdır (V57). Metin sha256 ile kilitli olduğu için `ONAYLI_UYARI_SHA` da yenilendi; model, katalog, parametre ya da eşiklerde değişiklik yok. Yayımlanan tüm sayılar geçerliliğini korur. Aynı toplu değişiklikte harita altlığı ve ölçüm betiği değişti (V56) — bunlar sunum katmanındadır ve hiçbir sayıyı üretmez;
daha önce: **grid_features yapısal engelden geçirildi
(CellHistory); çıktı BİREBİR AYNI: 694.328 satır, 61 kolon, hiçbir fark yok**;
daha önce: **yapısal sızıntı engeli (HistoryView) kuruldu; lgbm.train enjeksiyon kabul ediyor** (sayı değişikliği YOK; kanarya
bulgusu ablasyon sonuçlarını KURTARIR, bkz. docs/KANARYA_BULGUSU.md yan bulgu);
daha önce: **yayımlanan tahmine künye gömüldü,
kirli ağaçtan yayım reddediliyor, alt eşik gerekçesi ölçüldü** (sayı değişikliği
YOK; yayım kuralları ve şeffaflık); daha önce: **operasyonel üretim analitiğe
geçti**
(4. iş; V16: local_params tohumlandı, oranlarda bağıl 1,2e-04 kayma; manşet
sayıları ETKİLENMEZ çünkü değerlendirme yolunda local_params zaten tek çağrıydı
ve o çağrının sonucu tüm hesapta kullanılıyordu); daha önce:
**sonuç/parametre json'ları git-izlemeli
yapıldı** (dondurma sonrası 1b; koruyucunun etas_params.json izlemesi BOŞTU,
bkz. VAKA_DEFTERI V15); daha önce: **cell_id üst sınır düzeltmesi**
(dondurma sonrası 1. iş, aşağıda); daha önce: analitik dallanma yöntemine geçiş,
kaynak konumu düzeltmesi, Ö2 çapraz doğrulaması, MDE raporlamasının eklenmesi
ve küçük-örneklem (t) düzeltmesi (gain_breakdown; sayıları etkilemez,
raporlamaya güç beyanı ekler); ızgara sınır durumunun belgelenmesi
(config.cell_id; 2 hücre ayıklanıyor, mevcut sayılara etkisi ölçülen SIFIR);
blok bootstrap'ın takvim tabanlı yeniden kurulması; yığılma paydasının
tanımlanması ("gün" -> "olaylı başlangıç") ve %100'ü aşabilen 30+ satırının
kaldırılması.

**Yığılma paydası düzeltmesinin etkisi:** yüzdeler DEĞİŞMEDİ (aynı payda zaten
kullanılıyordu); değişen yalnızca etiket ve tanımın çıktıda basılması. 30 ve
üstü satır artık yazılmıyor -- negatif başlangıçlar toplamı aşağı çektiği için
pay %100'ü aşabiliyordu (%130,7 ölçüldü) ve yüzde olarak sunmak yanıltıcıydı.

**Blok bootstrap düzeltmesinin etkisi — ÖLÇÜLDÜ, çıkarsanmadı.** Eski ve yeni
bloklama günlük kurulumda BİREBİR AYNI bölümlemeyi veriyor (37 blok, aynı
bölümler; dizi karşılaştırmasıyla doğrulandı). Haftalık kurulumda eski kod 202
başlangıcı 7 bloğa düşürüyordu.

Sonuç: **blok hatası yalnızca haftalık kurulumu etkiliyordu.** Günlük kurulum
sonuçları -- ki zaten BAŞKA bir gerekçeyle geçersiz (örtüşen pencereler, Monte
Carlo çözünürlüğü) -- bu hatadan bağımsızdır. İki geçersizlik gerekçesi
karışmamalıdır; aksi hâlde ileride "hangi düzeltme neyi düzeltti" izlenemez
olur.

## Bilgi kazancı sayıları

| sayı | kurulum | taban rejimi | durum | son güncelleme / olay |
|---|---|---|---|---|
| **+2,287** [1,999; 2,575] | aylık CSEP, simülasyon | 1e-6 sembolik | **GEÇERSİZ** — STAI öncesi parametreler | 24 Ağu, bayat tespiti |
| **−8,927** | günlük, örtüşen, n_sim=500 | taban YOK | **GEÇERSİZ** | 24 Ağu, kurulum bırakıldı |
| **+1,071** | günlük, örtüşen, n_sim=500 | ayrıştırma ana şok oranı | **GEÇERSİZ** — taban 3,42 kat şişik | 24 Ağu, taban düzeltmesi |
| **+0,678** | günlük, örtüşen, n_sim=500 | ETAS arka plan düzeyine ölçekli | **GEÇERSİZ** — kurulum bırakıldı | 24 Ağu, çözünürlük ölçümü |
| **+2,399** [2,110; 2,689] | aylık CSEP, simülasyon | 1e-6 sembolik | GEÇERLİ | 24 Ağu, STAI sonrası yeniden üretim |
| **+2,378** [2,090; 2,667] | aylık CSEP, simülasyon | analitik alt sınır | GEÇERLİ (taban varyantı) | 24 Ağu |
| **+2,398** [2,104; 2,692] | aylık CSEP, **analitik** | taban yok (gereksiz) | GEÇERLİ | 24 Ağu, Ö2 geçti |

Manşette kullanılacak olan **+2,398 / +2,399**; ikisi arasındaki 0,001 fark
Ö2 çapraz doğrulamasının konusudur.

## Kalibrasyon oranları (gözlenen / beklenen)

| sayı | kurulum | durum |
|---|---|---|
| **2,14x** eksik tahmin | ilk kalibrasyon, STAI öncesi | GEÇERSİZ |
| **1,68x** toplam / **0,96x** tahmin edilebilir kısım | günlük, STAI sonrası, ham simülasyon | tarihsel kayıt |
| **0,68x** (arşiv) | operasyonel arşiv, artçı dahil oran taban | **GEÇERSİZ** — ölçüm değil, taban hatasının çıktısı |
| **0,94x** (arşiv) | operasyonel arşiv, arka plan oranı taban | GEÇERLİ |
| **1,14x** (Şubat 2023 hariç) | aylık CSEP | GEÇERLİ |
| **2,53x** (tüm pencereler) | aylık CSEP | GEÇERLİ |

## Bölgesel bilgi kazancı değerleri

| sayı | kurulum | durum | son güncelleme / olay |
|---|---|---|---|
| Marmara **−1,367** | günlük, örtüşen 7g pencere | **GEÇERSİZ** — 35 olay, örtüşme nedeniyle bağımsız sayılmış, **sahte kesinlik** | 24 Ağu, haftalık kuruluma geçiş |
| Batı Anadolu **−1,167** | günlük, örtüşen 7g pencere | **GEÇERSİZ** — aynı gerekçe | 24 Ağu |
| Doğu Anadolu **+2,520** | günlük, örtüşen 7g pencere | **GEÇERSİZ** — aynı gerekçe | 24 Ağu |

**Teşhis:** günlük başlangıçlı 7 günlük pencereler birbirini örtüyordu; aynı
deprem ardışık yedi pencerede sayılıyor ve bağımsız gözlem gibi işleniyordu.
Bölge başına "35 olay" görünen sayı, gerçekte çok daha az bağımsız bilgi
taşıyordu. Aralıklar bu yüzden olduğundan dar, iddialar olduğunda kesin çıktı.

Haftalık örtüşmeyen kurulumda aynı bölgeler daha AZ ama gerçekten bağımsız
olayla ölçülür. Sonuçların "daha az kesin" görünmesi beklenir.

## Yığılma ifadeleri (manşette kullanılan cümleler)

| ifade | kurulum | durum | son güncelleme / olay |
|---|---|---|---|
| "kazancın **%92'si** 2023'ten" | günlük, örtüşen 7g | **GEÇERSİZ** — örtüşen pencereler aynı olayı yedi kez sayıyordu | 24 Ağu, haftalık kuruluma geçiş |
| "kazancın **%84'ü** tek bölgeden" | günlük, örtüşen 7g | **GEÇERSİZ** — aynı gerekçe; dayandığı +2,520 de geçersiz | 24 Ağu |
| "en yüksek **10 gün** toplamın %55'i" | günlük, örtüşen 7g | **GEÇERSİZ** — aynı gerekçe | 24 Ağu |
| "ETAS günlerin **%57'sinde** kaybediyor" | günlük, örtüşen 7g | **GEÇERSİZ** — aynı gerekçe | 24 Ağu |
| "günlerin %4,8'i kazancın **%61,5'ini** taşıyor" | günlük, örtüşen 7g, ŞİŞİK TABAN | **GEÇERSİZ** — hem örtüşme hem 3,42x şişik taban | 24 Ağu, README taramasında bulundu |
| "ETAS günlerin **%49,4'ünde** kaybediyor" | günlük, örtüşen 7g, ŞİŞİK TABAN | **GEÇERSİZ** — aynı gerekçe | 24 Ağu, README taramasında bulundu |

Son iki satır bu denetimin konuşmasında hiç geçmemişti; README'nin geçersiz
sayı taraması yakaladı. Kayıt sebebi: haritanın işlevi yalnızca tartışılan
sayıları izlemek değil, YAYIMLANMIŞ her sayıyı izlemektir. İkisi de manşetten
önceki (şişik taban dönemi) yığılma tablosundan geliyor ve yerlerine
%98,8 / %50,8 geçti.

Bu dört ifade manşet taslağında yer tutuyordu ve haftalık analitik kurulumun
yıl/gün/bölge tablolarından YENİDEN türetilecektir. Fazlalık taramasında
ayrıca kontrol edilir: dayanağı teslimde olmayan hiçbir yığılma ifadesi
manşette kalmaz.

## ETAS parametreleri

| sayı | anlam | durum |
|---|---|---|
| dallanma **0,839**, b **1,157** | STAI öncesi kalibrasyon | GEÇERSİZ |
| dallanma **0,821** (nominal, kesimsiz) | etas_params.json'da raporlanan | GEÇERLİ ama **efektif değil** |
| dallanma **0,8125** (efektif, kesimli) | simülasyonun fiilen davrandığı | GEÇERLİ — kütle testleri bunu hedefler |
| b **1,274** | ETAS beta'sından, STAI-dayanıklı | GEÇERLİ |
| b **1,045** | katalogdan klasik Aki-Utsu | GEÇERLİ (farklı soru; STAI aşağı yanlı) |
| mu **7,26e-07** | eğitim dönemi (1992-2016) | GEÇERLİ ama **tahminde kullanılmaz** |
| mu **~2,8e-07** | başlangıç başına yerel kestirim | GEÇERLİ — tahmin bunu kullanır |

## Kurulum kimlikleri

| kimlik | tanım | durum |
|---|---|---|
| `gunluk-500` | günlük başlangıç, örtüşen 7g pencere, n_sim=500 | BIRAKILDI (bkz. results/archive/2026-08-24_daily_setup/) |
| `aylik-1000` | aylık başlangıç, 30g pencere, n_sim=1000 | GEÇERLİ (CSEP) |
| `aylik-analitik` | aylık başlangıç, 30g pencere, analitik | GEÇERLİ (CSEP çapraz doğrulama) |
| `haftalik-analitik` | haftalık örtüşmeyen 7g pencere, analitik | ÜRETİLİYOR (ayrıştırma) |


## İki ızgara, iki satır sayısı (denetimin son kaydı)

Manşette iki farklı satır sayısı geçer ve ikisi de doğrudur:

    532.480 = 208 baslangic x 2560 hucre  -> TAHMIN izgarasi (analitik, 32x80)
    436.800 = 208 baslangic x 2100 hucre  -> DEGERLENDIRME izgarasi

Ölçüldü: değerlendirme ızgarası, tahmin ızgarasının **kesin alt kümesidir**
(degerlendirme - tahmin = 0 hücre; tahmin - degerlendirme = 460 hücre).
2100 = 2102 (baseline_poisson hücreleri) − 2 (ızgara dışına taşan sınır
hücreleri, bkz. config.cell_id yarı-açık aralık notu).

**Sıfır-oran kontrolü tahmin ızgarasının TAMAMINDA yapılmıştır**; değerlendirme
ızgarası bunun alt kümesi olduğundan beyan fazlasıyla kapsanmaktadır. 460
hücrelik fark, tahmin üretilen ama değerlendirmeye girmeyen (baseline_poisson'da
karşılığı olmayan, yani tarihsel sismisitesi hiç olmayan) hücrelerdir.


## cell_id üst sınır düzeltmesi — YENİDEN ÜRETİLEN SAYILAR

Bu bölüm, dondurma sonrası 1. işin zorunlu muhasebesidir. Bilinen etki
değişiklikten ÖNCE yazılmıştı (`docs/CELLID_BEKLENEN_ETKI.md`); aşağıda ne
yeniden üretildiği ve ne değiştiği duruyor.

### Yeniden üretilen dosyalar

| dosya | değişti mi | nasıl |
|---|---|---|
| `grid_features.parquet` | evet | hücre kimliği kanonik fonksiyondan |
| `baseline_poisson.csv` | evet | 2102 -> 2100 hücre; tüm oranlar ×1,00004640 |
| `daily_backtest.json` | evet (5. ondalık) | Poisson oranları ölçeklendi |
| `gain_breakdown.json` | evet (5. ondalık) | aynı |

### Değişen sayılar

**Manşetteki hiçbir sayı raporlanan hassasiyette (3 ondalık) değişmedi.**
Ölçüldü ve yeniden koşuldu:

    AUC farkı  +0,1407  [+0,0761; +0,2144]   (aynı)
    IG         +1,068                        (aynı)
    Kahramanmaraş tablosu                    (aynı)
    bölge tablosu                            (aynı)

Analitik beklenti: IG -8,98e-06 (hassasiyetin binde 9'u), AUC tam 0.

**Manşet mührü GEÇERLİLİĞİNİ KORUYOR.** Sayılar değişmediği için yeniden
dondurma gerekmez; ama künyedeki commit ve `baseline_poisson` özeti değişmiştir
ve bu bölüm o değişikliğin kaydıdır.

### Değişmeyen ama etkilenebilecek olanlar

`etas_analytic_weekly/` ve `etas_analytic_monthly/` tahmin çıktıları
DEĞİŞMEDİ: analitik ETAS hesabı kendi ızgarasını kullanır ve
`baseline_poisson`'a bağlı değildir. CSEP sonuçları da yeniden üretilmedi --
Poisson karşılaştırma oranı ölçeklendiği için orada da 5. ondalık mertebesinde
bir kayma beklenir; gerekirse ayrıca ölçülecektir.


## MÜHÜR TAZELEMELERİ

Manşet mühürlendikten sonra yapılan her tazeleme, gerekçesiyle buraya yazılır.

**Kural: mühür tazelemenin MEŞRU tek gerekçesi, sayıya dokunmayan doğruluk
düzeltmesidir.** Mühür sayıları korur, hataları değil.

| # | eski mühür | yeni mühür | sebep | sayı değişti mi |
|---|---|---|---|---|
| 1 | `8222fdd` | `3b90b74` | "kalan fark açıklanmamıştır" ifadesi 3. iş tamamlanınca YANLIŞ beyan hâline geldi | **HAYIR** |

### Tazeleme 1 — kapsam

Değiştirilenler, üçü de metin:

1. §4'teki tek cümle: "kalan fark açıklanmamıştır" -> "kalan fark gürültü
   tavanıyla açıklanmıştır (analitik yöntem ulaşılabilir korelasyonun
   %98,2'sinde)"
2. §4 "DOĞRULANMAYAN" tablosunun iki satırı: "açıklanmadı" -> "AÇIKLANDI --
   gürültü tavanı"; Ö3a/Ö3c satırına "ölçüt ulaşılamazlığı ÖLÇÜLDÜ" notu
3. "Bilinen sınırlar" listesindeki ilgili madde: başarısızlığın kaynağının
   ölçüldüğü eklendi

**Dokunulmayanlar:** hiçbir sayı, hiçbir tablo değeri, hiçbir Ö4 işareti.
Doğrulandı: 20 anahtar sayı yerinde.

Ö3a ve Ö3c **KALDI olarak kalır**; geriye dönük geçirilmemiştir.

---

## FAZ 3 — SIZINTI KANARYALARI (25 Ağu 2026)

Kurulum künyesi: haftalık tablo `grid_features_weekly.parquet`, hedef
`target_7d_m45_all`, `src/models/lgbm.py` gerçek eğitim yolu.

| sayı | ne | üreten | geçerlilik |
|---|---|---|---|
| 753 | eğitim pozitifi (haftalık) | `lgbm.load_dataset` | haftalık kurulum |
| 173 | doğrulama pozitifi | aynı | aynı |
| 252 | test pozitifi | aynı | aynı |
| 212 | eğitim pozitifi (AYLIK — V17 körlüğünün sebebi) | aylık kurulum | **yalnızca aylık** |
| %34,5 | 10 yıllık geçmişi olmayan satır oranı | `grid_features.py` | haftalık tablo |

### Kanarya ölçümleri — TEST tabanında (25 Ağu 2026 öncesi taban)

| ölçüm | değer | alarm |
|---|---|---|
| temiz taban (test) | 0,7851 | — |
| KABA (hedef öznitelik) | 1,0000 | VAR |
| ZAMANSAL ref+1g | 0,8135 | yok |
| ZAMANSAL ref+2g | 0,8244 | yok |
| ZAMANSAL ref+3g | 0,8442 | yok |
| ZAMANSAL ref+5g | 0,9633 | VAR |
| ZAMANSAL ref+7g | 0,9989 | VAR |
| DOLAYLI (ölçekleme) | 0,7847 -> 0,7847 | yok (kanal yok) |

**Saptama tabanı: 3 ile 5 gün arasında.** Bkz. `docs/KANARYA_KUNYESI.md`.

**GEÇERSİZ SAYILAR.** Yukarıdaki tablo TEST bölümünde ölçüldü. Kanarya
25 Ağu 2026'da DOĞRULAMA tabanına geçti (`docs/TEST_DOKUNUSLARI.md`,
Düzeltme 1). Bu sayılar tarihsel kayıttır ve **yeni kurulumun künyesini
taşımaz**; yeni tabandaki ölçümler ayrı satırlarda verilir.

### Tanılama sırasında görülen test sayısı

| sayı | ne | not |
|---|---|---|
| 0,7847 | temiz LightGBM test AUC'si, VARSAYILAN hiperparametrelerle | protokol dışı, tanılama; ilan paketi bu gözlemden ÖNCE commit'liydi (`a49f84e`) |

Bu sayı seçim ölçütü DEĞİLDİR ve hiçbir hükme dayanak oluşturmaz. Kayıt:
`docs/TEST_DOKUNUSLARI.md`, Dokunuş 1.

### Kanarya ölçümleri — DOĞRULAMA tabanında (yürürlükteki kurulum)

Künye: `grid_features_weekly.parquet` · `target_7d_m45_all` · doğrulama bölümü
(2016-01-01 .. 2020-12-25, 548.361 satır, 173 pozitif) · commit `08735d8`
sonrası kanarya kodu.

| ölçüm | değer | alarm | tetikleyen |
|---|---|---|---|
| temiz taban (doğrulama) | 0,8529 | — | — |
| KABA | 1,0000 | VAR | ikisi de |
| ZAMANSAL ref+1g | 0,8736 | yok | — |
| ZAMANSAL ref+2g | 0,8933 | yok | — |
| ZAMANSAL ref+3g | 0,9131 | VAR | yalnızca mutlak |
| ZAMANSAL ref+5g | 0,9548 | VAR | mutlak + sıçrama |
| ZAMANSAL ref+7g | 0,9992 | VAR | mutlak + sıçrama |

Saptama tabanı ÖLÇÜTE GÖRE ayrı: mutlak eşik 2-3 gün, sıçrama 3-5 gün.

**0,8529 sayısının sonucu:** mutlak eşik (0,90) meşru bir modelin yalnızca
+0,047 üstünde. Eşiğin gerekçesi bu bölümde yanlışlandı; eşik değiştirilmedi,
kapsam düzeltildi — yalnızca mutlak eşiği tetikleyen alarm SONUÇSUZDUR.
Bkz. `docs/KANARYA_KUNYESI.md`.

### DOĞRULAMA - TEST FARKI — önceden yazılmış açıklama

Aynı temiz model, iki bölümde farklı skor veriyor:

    doğrulama (2016-2020)   AUC 0,8529
    test      (2021-2024)   AUC 0,7851
    fark                        -0,0678

Doğrulama dönemi test döneminden **sistematik olarak daha "kolay"** görünüyor.
Test dönemi 2023 Kahramanmaraş dizisini içerir: olayların büyük kısmı kısa bir
pencereye yığılır, sıralama problemi zorlaşır.

**Bu cümle sonuçtan ÖNCE yazılmıştır.** Seçilen bileşimin test skoru doğrulama
skorundan düşük çıkarsa bu sürpriz DEĞİLDİR ve "model bozuldu" diye
okunmamalıdır; iki bölümün zorluğu ölçülmüş şekilde farklıdır.

Ters yönü de bağlar: test skoru doğrulamayı GEÇERSE, o da açıklama gerektirir
ve **ilk bakılacak yer bellidir**: test kümesine herhangi bir kanaldan bilgi
sızıp sızmadığı. Beklenen yönde sapma kadar, beklenmedik yöndeki "iyi haber"
de sorgusuz geçmez.

Sıra: (1) kanaryalar bu kurulumda yeniden koşulur, (2) küme eşitliği ve
birleştirme yeniden bakılır, (3) doldurma kuralının test döneminde farklı
davranıp davranmadığı ölçülür. Üçü de temiz çıkmadan "test daha kolaymış"
açıklaması KABUL EDİLMEZ.

---

## FAZ 3 ML SONUÇLARI (25 Ağu 2026) — künye

**Kurulum künyesi.** `grid_features_weekly.parquet` · hedef
`target_7d_m45_all` · LightGBM `lr=0,02 · yaprak=7 · min_child=200 · l2=10` ·
3 tohum (1,2,3) ortalaması · test 2021-01-01..2024-12-20 · 436.800 satır ·
252 olay · ETAS kaynağı `etas_analytic_weekly` · kod commit `cac2862`.

| sayı | ne | geçerlilik |
|---|---|---|
| 0,7869 | ML test AUC (3 tohum ortalaması) | bu künye |
| 0,7874 / 0,7856 / 0,7872 | tohum başına ML AUC | bu künye |
| +1,086 | ML IG (Poisson'a karşı) | bu künye |
| +0,018 [-0,164, +0,196] | ML − ETAS IG, MDE 0,256 | bu künye |
| 1,82 | ML gözlenen/beklenen (kalibrasyon) | bu künye |
| 138,8 | ML toplam beklenen olay | bu künye |
| −0,350 / +0,368 | ML−ETAS IG'nin OLAY / MARUZİYET terimleri | bu künye |
| %45,2 | olayların ML'nin daha yüksek olduğu payı (p=0,147) | bu künye |
| %1,7 | `n30`'un SHAP payı | tohum 1, 50.000 satırlık örneklem |
| 19,8 / 84,3 / 59 | dizi penceresinde ML / ETAS beklentisi ve gözlenen | 90 günlük pencere |
| 0,000009826 / 0,000004058 | arama yayılımı / tohum saçılımı (ss) | 108 koşu |
| 2,42 / 7,80 | yayılım/saçılım · genişlik/saçılım | aynı |

**KEŞFEDİCİ — hükme dayanak DEĞİL.** Ölçek düzeltilmiş ML−ETAS:
genel +0,161 [-0,021, +0,340] · dizi-dışı +0,285 [+0,110, +0,452].
Bu analiz ilan paketinde yoktu; sonuçlar görüldükten sonra tasarlandı.
Adım 4'ün önceden kayıtlı hipotezi H1'e dönüştürüldü (`docs/FAZ3_PLAN.md`).

**GEÇERSİZ.** Bu satırların hiçbiri başka bir pencere (30 gün), başka bir
büyüklük eşiği (M≥5,0) ya da aylık tablo için geçerli değildir.

---

## NPP FİZİBİLİTE VE KAPSAM ÖLÇÜMLERİ (25 Ağu 2026)

Künye: torch 2.13.0+cpu · 8 iş parçacığı · GPU YOK · eğitim 2.300.595 satır.

### Kodlayıcı maliyeti (tur başına, yığın 16384)

| kodlayıcı | K | d | tur sn |
|---|---|---|---|
| toplam havuzlama | 16 | 32 | **5,1** |
| GRU | 16 | 32 | 64,3 |
| dikkat | 16 | 32 | 110,0 |

Bu sayılar mimari seçimini kısıtladı; gerekçe `docs/NPP_ILAN.md` §1'de
yapısal gerekçeyle BİRLİKTE yazılmıştır (hız tek gerekçe değildir, ama
gizlenmemiştir).

### Girdi kapsamı — K ve R seçimi

800 hücre-başlangıç (40 başlangıç × 20 hücre), EĞİTİM dönemi, ETAS çekirdeği
kütlesi ölçü.

| K | ortalama | %5 dilim | R km | ortalama | %5 dilim |
|---|---|---|---|---|---|
| 16 | 0,9615 | 0,8212 | 50 | 0,8462 | 0,0237 |
| 32 | 0,9843 | 0,9267 | 100 | 0,9436 | 0,6240 |
| **64** | **0,9944** | **0,9774** | **200** | **0,9855** | **0,9601** |
| 128 | 0,9983 | 0,9928 | 400 | 0,9986 | 0,9987 |

Ölçüt (**önce ilan edildi**): %5 diliminde bile ≥ 0,95 → **K=64, R=200 km**.

**GEÇERSİZ.** Bu paylar ETAS'ın kalibre çekirdeğine ve bu kataloğa özgüdür;
başka bir parametre kümesi ya da katalog için yeniden ölçülmelidir.

---

## V37 — DONDURULMUŞ SAYILAR ŞU AN SORGUDA (26 Ağu 2026)

**Bu bölüm, yeniden üretim koşusu bitene kadar yürürlüktedir.**

Dondurulmuş değerlendirme tablosu (`etas_analytic_weekly`, 24 Ağu 21:22)
bugünkü kodla yeniden üretilemiyor: arka plan oranı μ, **3,81 kat** farklı
(eval 0,3691 · bugün 0,0968). Tetikleme aynı (eğim ~1,061).

### Etkilenebilecek sayılar — TAMAMI o tablodan türüyor

| sayı | değer | durum |
|---|---|---|
| ETAS AUC (haftalık) | 0,7909 | **SORGUDA** |
| ETAS IG (Poisson'a karşı) | +1,068 | **SORGUDA** |
| ETAS kalibrasyonu | 1,09 | **SORGUDA** |
| AUC farkı ETAS−Poisson | +0,1407 | **SORGUDA** |
| LightGBM − ETAS | +0,018 | **SORGUDA** (zemin kaydı) |
| NPP − ETAS | +0,174 | **SORGUDA** (zemin kaydı) |
| H1 (ölçek düzeltilmiş dizi-dışı) | +0,316 | **SORGUDA** |
| H2 dizi beklentisi (ETAS) | 84,3 | **SORGUDA** |

**"Sorguda" ne demek DEĞİL:** bu sayıların yanlış olduğu anlamına gelmez.
Karşılaştırmalar **aynı tablo üzerinde** yapıldı; iç tutarlılık korunmuştur.
Anlamı şudur: **yeniden üretilemiyorlar**, ve yeniden üretilemeyen bir sayı
dondurulmuş sayılamaz.

### Etkilenmeyenler

| sayı | neden etkilenmez |
|---|---|
| ETAS parametreleri (`5ab1f75e…`) | sha256 birebir aynı |
| katalog istatistikleri (304.168 olay, %27 kopya) | tablodan bağımsız |
| Mw kalibrasyonu (0,22 birim) | tablodan bağımsız |
| Omori p = 1,01 | doğrudan katalogdan |
| ML arama dağılımları (36 ve 4 bileşim) | doğrulama NLL/logloss, ETAS tablosu kullanılmıyor |
| NPP determinizm zinciri | model içi, tablodan bağımsız |
| Kanarya künyeleri ve tabanları | ETAS tablosu kullanılmıyor |

### Bu commit'in sayılara etkisi

`forecast_now._fingerprint()` künyeye iki alan ekledi:

    catalog_sha256        catalog_last_event

**Hiçbir hesaplanan sayıyı değiştirmez** — yalnızca üretilen dosyaların
künyesine alan ekler. Bundan sonra üretilen her tahmin, hangi katalogla
üretildiğini taşır; V37'nin bir daha sınanamaz kalmasını önler.

Okuma kuralları ve yeniden üretim planı: `docs/ZEMIN_YENIDEN_URETIM.md`
(koşudan önce yazıldı).

---

## V38 — V37'NİN SEBEBİ BULUNDU: SAYILAR SORGUDAN ÇIKIYOR (26 Ağu 2026)

Yukarıdaki "SORGUDA" listesi **kalkıyor.** Sebep, dondurulmuş tabloda değil,
onu yeniden üretmeye çalıştığım günün katalogundaydı.

### Ne olmuştu

Veri hattını sınarken çağrılan `update_catalog`, üç kaynağın ham dosyalarını
yalnızca 2026 verisiyle üzerine yazdı (AFAD 265.572 → 4.713 vb.). Karşılaştırma
o **hasarlı katalogla** yapıldı.

### Katalog kurtarıldıktan sonra ölçüm

    μ oranı, kurtarılmış katalogla     0,3689
    dondurulmuş tablonun ima ettiği    0,3691
    fark                               %0,05

**Dondurulmuş değerlendirme tablosu doğrudur ve yeniden üretilebilir.**

### Katalog sayıları — kurtarma sonrası

| kaynak | sayı |
|---|---|
| AFAD | 265.572 |
| KOERI | 71.865 |
| EMSC | 51.149 |
| USGS | 18.623 |
| tekilleştirme | 104.442 kopya (%25,6) |
| **birleşik katalog** | **302.767** |

README'deki 304.168 ile fark (1.401), EMSC'nin önbelleği olmadığı için ağdan
yeniden çekilmesinden gelir; kaynak o tarihten bu yana kendi kayıtlarını
revize etmiş olabilir. **Ölçüldü, açıklandı, kayda geçti.**

### Hâlâ yapılacak

Tam yeniden üretim koşusu (208 başlangıç) **bekliyor**. μ örtüşmesi güçlü bir
işarettir ama **tablo örtüşmesi ölçülmeden** DAL A ilan edilmez
(`docs/ZEMIN_YENIDEN_URETIM.md`).

### Bu commit'in sayılara etkisi

`update_catalog` artık her kaynağı tam aralığıyla çağırıyor ve **monotonluk
koruması** ekledi (`KatalogKuculdu`). Hiçbir hesaplanan sayıyı değiştirmez;
gelecekte aynı hasarın oluşmasını engeller.

**GEÇERSİZ:** `data/publish/_geri_cekilen/2026-08-26/` içindeki üç tahmin
(124/146/158 hücre) — hasarlı katalogla üretildi, geri çekildi.

---

## ZEMİN YENİDEN ÜRETİLDİ — MÜHÜR TAZELEME (26 Ağu 2026)

**Gerekçe: SAYI DEĞİŞİKLİĞİ, sebep: zemin yeniden üretildi.**
(Önceki tazelemeler yalnızca metin düzeltmesiydi; bu ilk sayı değişikliğidir.)

### Değişen tek sayı

    ETAS AUC (haftalık, M>=4,5)   0,7909  ->  0,7910

Fark: `0,790941 → 0,790958`, bağıl **2,2e-05**. Dördüncü ondalıkta yuvarlama
sınırını geçti.

### Değişmeyen sayılar — tabloyla birlikte yeniden ölçüldü

| sayı | değer | durum |
|---|---|---|
| Poisson AUC | 0,6503 | aynı (birebir) |
| AUC farkı | 0,1407 | aynı |
| ETAS IG | +1,068 | aynı |
| ETAS kalibrasyonu | 1,09 (1,0885) | aynı |
| LightGBM − ETAS | +0,018 [−0,164, +0,196] MDE 0,256 | **aynı** |
| NPP − ETAS | +0,174 [+0,032, +0,317] MDE 0,204 | **aynı** |
| H1 | +0,316 [+0,159, +0,469] MDE 0,227 | **aynı** |
| H2 dizi beklentisi | ETAS 84,3 · NPP 41,8 · gözlenen 59 | **aynı** |
| NPP kalibrasyonu | 1,52 | aynı |

**Bütün karşılaştırmalı hükümler korundu.** Ö5 (NPP geçti), README §3.5
(karşılandı), H1 (doğrulandı), H2 (kaldı), ürün kapısı (geçilmedi) —
beşi de değişmedi.

> **Zemin değişti, hüküm değişmedi.** Bu bir dayanıklılık kanıtıdır: sonuçlar
> katalogun %0,01 mertebesindeki değişimine duyarsızdır.

### Yeni zeminin künyesi

    tablo            data/processed/etas_analytic_weekly_v2/  (208 başlangıç)
    katalog          302.767 olay · sha256 dde8e3c0…
                     (b1d6f46a… ARA DURUMDU: EMSC kurtarılmadan
                      önceki birleştirme; düzeltildi)
    parametreler     sha256 5ab1f75e… (DEĞİŞMEDİ)
    üretim           26 Ağu 2026, 4 parça paralel

### Zemin BİREBİR değil — sebebi kayıtlı

Eski katalog **birebir geri getirilemedi**: EMSC'nin önbelleği yoktu ve ağdan
yeniden çekildi; kaynak kendi kayıtlarını revize etmiş (302.767 vs README'deki
304.168). Kalan fark **%0,012** ve tamamı buradan gelir.

Bundan sonra bu belirsizlik doğmaz: künye zinciri artık `catalog_sha256`
taşıyor (V37) ve önbelleksiz kaynak bırakılmıyor (V38).

---

## ÜRÜN KAPISI ÖLÇÜMÜ (26 Ağu 2026)

Künye: `etas_analytic_weekly` (yeni kanonik tablo) · 2021-01-01 .. 2024-12-20
· 436.800 satır · 252 olay · 7 gün · M≥4,5.

| model | beklenen | oran | kapı [0,80; 1,25] |
|---|---|---|---|
| ETAS | 231,5 | **1,089** | **GEÇER** |
| Poisson | 203,2 | 1,240 | geçer (sınırda) |
| LightGBM | 138,8 | 1,816 | GEÇMEZ |
| NPP | 165,4 | 1,524 | GEÇMEZ |

Kapı artık **hatta bağlı** ve yayın öncesi otomatik kontrol ediliyor; ölçüm
dosyası (`kapi_olcumu.json`) yoksa **yayım yapılmaz** — varsayılan "geç"
değil "dur".

---

## V43 — YAYIN KAPSAMI TÜRKİYE İLE SINIRLANDI (26 Ağu 2026)

### Yeni ölçüm: katalog tamlığı sınır dışında DÜŞÜK

Gerçek sismisite oranı büyüklüğe göre sabit kalmalıdır; artıyorsa küçük
olaylar kaydedilmiyor demektir.

| büyüklük | dış/iç olay oranı |
|---|---|
| M≥3,3 | 0,346 |
| M≥4,0 | 0,549 |
| M≥4,5 | 0,559 |
| M≥5,0 | 0,584 |
| M≥5,5 | **0,639** (küresel saptama, tam kayıt) |

Sınır dışında küçük olayların **~%46'sı katalogda yok.**

    uzun vadeli temel oran (M>=5/yıl, medyan)
      Türkiye içi   0,00411
      dışı          0,00180      <- yarısından az

### Etkilenen sayılar

| sayı | eski | yeni | sebep |
|---|---|---|---|
| yayımlanan hücre (7 gün, 26 Ağu) | 309 | **110** | kapsam dışı 199 hücre elendi |
| yayımlanan hücre (1 gün) | 267 | ölçülecek | aynı |
| yayımlanan hücre (30 gün) | 358 | ölçülecek | aynı |
| hücre bandı | (50, 900) | **(20, 400) GEÇİCİ** | bant kapsam öncesi ölçülmüştü |

### GEÇERSİZ olan

**Eşik tablosu (616 / 412 / 299 / 179 / 97 / 44) tüm ızgara üzerinde
ölçülmüştür ve kapsam kısıtlamasından SONRAKİ yayına uygulanmaz.**
Karar (`min_times_normal = 2,0`) değişmedi — eşiğin *gerekçesi* hücre
sayısının yarıya inmesiydi ve o oran kapsamdan bağımsızdır — ama **tablodaki
mutlak sayılar artık yayımlanan hücre sayısını tarif etmiyor.**
Yeniden ölçüm bekliyor.

**Metodoloji sayfasındaki eşik tablosu da bu yüzden "tüm ızgara üzerinde
ölçüldü" notuyla verilmelidir.**

### Etkilenmeyen

Değerlendirme sonuçlarının **hiçbiri**: AUC, IG, kalibrasyon, ML
karşılaştırmaları, H1/H2, ürün kapısı. Bunlar 436.800 hücre-pencerede
ölçüldü ve kapsam kısıtlaması **yalnızca YAYINA** uygulanır, değerlendirmeye
değil. Değerlendirme, modelin ızgaranın tamamındaki başarısını ölçer;
yayın, hangi hücreler hakkında **konuşabileceğimizi** belirler.

> Bu ayrım korunur: kapsam bir **yayın kararıdır**, model kararı değil.

### Sınır künyesi

    kaynak       Natural Earth 10m admin-0 countries (KAMU MALI)
    kaynak sha   239eec57ac17f100a11e2536cffc5675...
    türev sha    6526abdc33181eedaafb4975d6873210...
    tampon       0,125 derece (yarım hücre) -- açıkça ilan edildi

---

## ACTIONS TAŞIMASI — ADIM 1 ve 3 (26 Ağu 2026)

### Adım 1: dondurulmuş bulgu JSON'a alındı

Bölge kartlarının 1. katmanı artık her koşuda hesaplanmıyor, künyeli bir
dosyadan okunuyor.

    değerlendirme tablosu bağımlılığı   109,2 MB  ->  2,2 KB

**Hiçbir sayı değişmedi** — aynı hesabın sonucu saklandı. Dosya künyesi
izlenebilirliği koruyor: kaynak tablo sha256 (`ff6af6e6…`), katalog sha256,
parametre sha256, üretim tarihi. Zemin değişirse künye değişir ve fark
görünür olur.

Künyesiz ya da eksik künyeli dosya **okunmaz** (test: `BulguYok`).

### Adım 3: monotonluk referansı yayın kaydına taşındı

Katalog küçülme koruması, "önceki durum"u yerel dosyadan okuyordu. Taze
checkout'lu bir ortamda (GitHub Actions) o dosya ancak önbellekten gelir ve
**önbellek boşsa koruma sessizce geçerdi** — V15'in uyardığı durum.

Referans artık **bir önceki yayının künyesindeki** ham satır sayıları.
Manifest'e yeni alan: `ham_satir_sayilari`.

**Hiçbir hesaplanan sayıyı etkilemez**; korumanın referans kaynağını
değiştirir. Yerel dosya da varsa **ikisinden büyüğü** alınır — koruma en sıkı
hâliyle çalışsın.

### Adım 2 ve 4 (26 Ağu 2026)

**Adım 2 — küçük eserler depoya alındı: 0,99 MB.** Gitignore istisnasıyla
(zorla ekleme değil, bildirimsel): `etas_params.json`, `baseline_poisson.csv`,
`mc_b.csv`, `tr_sinir.geojson`, `hucre_yer_adlari.json`, `kapi_olcumu.json`,
`bolge_bulgu_dondurulmus.json`.

Büyük eserler **depoda durmaz**: katalog her koşuda ham veriden üretilir, ham
veri önbellekten gelir, değerlendirme tablosu dondurulmuş bulguya indirgendi.

**Adım 4 — bayat yayın eşiği: 36 saat.**

    24 saat (günlük koşu) + 12 saat (tolerans) = 36 saat

Ürün kararıdır. Bir koşunun atlanması yayını geçersiz kılmaz; **iki** koşunun
atlanması yayının güncel sayılmaması demektir.

Manifest'e `tazelik` sözleşmesi eklendi — **makine-okunur**: `uretim_zamani`,
`sonraki_beklenen`, `bayatlik_esigi_saat`. Bir izleme aracı ya da kurumsal
kullanıcı da bayatlığı programatik görebilsin; "sessizce eskime" hiçbir
tüketici için olmasın.

Arayüz, yayının yaşını **her zaman** gösterir ("3 saat önce üretildi") ve
eşik aşılırsa kırmızı kutuyla uyarır.
