# Sonuçlar — ETAS vs zamandan bağımsız model

> Bu bölüm `docs/MANSET_TASLAK.md` yapısına göre doldurulmuştur. Her sayı bir
> kurulum künyesine bağlıdır; künyesiz sayı yayımlanmaz. Geçersiz sayıların
> listesi ve gerekçeleri: `docs/SAYI_HARITASI.md`.

## ANA BULGU

Kazancın **iki katmanı ve bir sınırı** var:

**(a) Dizi dönemlerinde büyük.** Kahramanmaraş dizisi penceresinde olay başına
bilgi kazancı **+3,81** (30 gün) ile **+2,47** (365 gün) arasında.

**(b) Dizi dışında küçük ama anlamlı — 180 güne kadar.** Dizi penceresi
çıkarıldığında kazanç 30/90/180 günlük pencerelerde pozitif ve sıfırdan anlamlı
biçimde ayrık: **+0,550 / +0,313 / +0,287**, alt sınırlar sırasıyla **+0,245 /
+0,031 / +0,007**. 365 günlük pencerede belirsizliğe geçiyor: **+0,218**,
%95 GA [−0,049; +0,506], MDE **0,404**.

> Alt sınırlar okunmalıdır: 180 günlük pencerede sınır **+0,007**, yani sıfırı
> kıl payı dışlıyor. "Anlamlı" etiketi kurala göre doğrudur; kazancın büyüklüğü
> ise pencere uzadıkça hızla küçülmektedir.

**(c) Kazanç zamanda aşırı yoğun.** Olay teriminin **%98,8'i** en yüksek **10
olaylı başlangıçtan** geliyor (toplam 120 olaylı başlangıç içinde). ETAS,
olaylı başlangıçların **%50,8'inde (61/120)** Poisson'a kaybediyor.

**Bunun anlamı:** ETAS'ın değeri "her gün biraz daha iyi olmak" değil, **kritik
günlerde çok daha iyi olmak**. Bu, bir kusur değil modelin doğasıdır — ETAS bir
tetikleme modelidir ve tetikleme yokken söyleyecek fazla sözü yoktur.

---

## 1. Aylık CSEP değerlendirmesi

**Kurulum:** `aylik-1000` ve `aylik-analitik` · 2021-01-01 – 2023-12-31 ·
36 aylık başlangıç · 30 günlük pencere · M≥5,0 · **gözlenen 102 olay**

### T-testi — projenin çıtası

    yol                          bilgi kazancı   %95 güven aralığı
    simülasyon (n_sim=1000)         +2,399       [+2,110; +2,689]
    simülasyon + analitik taban     +2,378       [+2,090; +2,667]
    ANALİTİK (taban gereksiz)       +2,398       [+2,104; +2,692]

**Ö2 çapraz doğrulaması geçti:** |ΔIG| = 0,001 (eşik < 0,05), aralıklar
örtüşüyor, N ve S testleri aynı kararı veriyor.

> **Kanıt gücü sınırı.** Bu, iki yöntemin BİRBİRİYLE tutarlı olduğunun ve
> farkın Monte Carlo gürültüsünden ibaret olduğunun kanıtıdır — doğruluğunun
> değil. İki yol aynı `_calculation_at` durumunu, aynı parametreleri ve aynı
> kataloğu paylaşır; ortak bir hata ikisinde birden yaşar.

### S-testi (mekânsal) — ETAS geçiyor, Poisson reddediliyor

    model     gözlenen olabilirlik   sim. ortanca   z        kuantil   sonuç
    ETAS            −205,75            −277,35    +4,71     1,000     uyumlu
    Poisson         −455,13            −350,75   −10,93     0,000     RED

Uç kuantiller dejenere değildir; z değerleri testin iki ucu da ayırt ettiğini
gösterir.

**Yan bulgu:** ETAS'ın z'si pozitif ve büyük — olaylar, modelin kendi
simülasyonlarının ürettiğinden daha yüksek oranlı hücrelere düşüyor. Tek yönlü
testi geçer, ama modelin mekânsal dağılımının gereğinden dağınık olduğunu ve
keskinleştirilebileceğini söyler.

### N-testi (olay sayısı) — başarısız, ve sebebi ölçüldü

    kurulum                  gözlenen   ETAS beklenen   oran     delta1   sonuç
    tüm 36 pencere              102          40,4      2,53x    0,0000   RED
    Şubat 2023 hariç (35)        45          39,6      1,14x    0,2162   uyumlu

102 olayın **57'si (%56)** tek pencerede. O pencere çıkarıldığında sayı
kalibrasyonu kabul bandının içindedir; eksik tahmin **yapısal değildir**.

> **Aylık güncelleme sıklığı, dizi başlangıçlarını yapısal olarak ıskalar;
> operasyonel sistem günlük güncellenecektir ve bu değerlendirme o sistemin alt
> sınırıdır.**

---

## 2. Kazanç nereden geliyor?

**Kurulum:** `haftalik-analitik` · 208 haftalık örtüşmeyen başlangıç
(2021-01-01 – 2024-12-20) · 7 günlük pencere · M≥4,5 · 2100 hücre ·
436.800 satır · **252 pozitif hücre-pencere**

**Değerlendirilen ürün: 7 GÜNLÜK TAHMİN.** 1 günlük panel için ayrı bir başarı
iddiası ileri sürülmez; o pencere bu kurulumda ölçülmemektedir.

### Genel

    olay başına toplam bilgi kazancı : +1,068 nat
      olay terimi +1,181 | maruziyet terimi −0,112
      ETAS 231,5 bekliyor | Poisson 203,2 | gözlenen 252
      -> ETAS 1,09x, Poisson 1,24x (ikisi de eksik tahmin, ETAS daha yakın)

    AUC : Poisson 0,6503   ETAS 0,7909   fark +0,1407
      blok bootstrap: L = 7 takvim günü, 208 blok, her blok TEK başlangıç
      %95 GA [+0,0761; +0,2144]  -> ETAS anlamlı biçimde daha iyi

> Blok yapısı ölçülmüştür, varsayılmamıştır: başlangıçlar 7 gün aralıklı ve
> pencereler örtüşmüyor, dolayısıyla her blok tek başlangıç içerir ve yeniden
> örnekleme sıradan bootstrap'a döner.

### Kahramanmaraş dahil / hariç

    dizi penceresi  n(içi)  IG(içi)  n(dışı)  IG(dışı)   %95 GA             MDE     sonuç
       30 gün          40   +3,814     212     +0,550  [+0,245; +0,887]      —     ETAS daha iyi
       90 gün          59   +3,540     193     +0,313  [+0,031; +0,633]      —     ETAS daha iyi
      180 gün          71   +3,061     181     +0,287  [+0,007; +0,593]      —     ETAS daha iyi
      365 gün          95   +2,473     157     +0,218  [−0,049; +0,506]    0,404   fark gösterilemedi

> **KAPSAM:** güven aralıkları yalnızca gözlenen olay sayısından gelen
> belirsizliği kapsar. ETAS parametre belirsizliğini ve model
> yanlış-belirlemesini kapsamaz. Model oranları deterministiktir (analitik
> hesap), dolayısıyla oranlarda örnekleme gürültüsü yoktur; ama parametrelerin
> kendisi bir kalibrasyondan gelir ve o belirsizlik buraya girmez.

### Zaman ve yığılma

    yıl    olay   ortalama kazanç   toplam payı
    2021     40       +0,438           %5,9
    2022     29       −0,447          −%4,4
    2023    148       +1,900          %94,5
    2024     35       +0,334           %3,9

    en yüksek  1 olaylı başlangıç: olay teriminin %31,1'i
    en yüksek  5 olaylı başlangıç: %78,5
    en yüksek 10 olaylı başlangıç: %98,8
    ETAS'ın kaybettiği olaylı başlangıç: 61/120 (%50,8)

**Payda tanımı:** "olaylı başlangıç" = en az bir gözlenen M≥4,5 olayı olan
tahmin başlangıcı. 208 başlangıcın 120'si böyledir; kalan 88'inde hiç olay yok
ve olay terimine katkı vermezler.

---

## 3. Bölgesel dağılım

    bölge                                 olay      IG     %95 GA             MDE     sonuç
    Doğu Anadolu (Maraş-Malatya)           105   +1,559  [+0,952; +2,166]      —     ETAS daha iyi
    diğer                                  101   +0,826  [+0,407; +1,265]      —     ETAS daha iyi
    Ege denizi / Yunanistan                 13   +1,319  [+0,254; +2,442]      —     ETAS daha iyi
    Batı Anadolu (Ege grabenleri)           17   +0,567  [−0,106; +1,295]    1,106   fark gösterilemedi
    Kuzey Anadolu doğu (Erzincan-Erzurum)   10   −0,257  [−0,918; +0,515]    1,173   fark gösterilemedi
    Kuzey Anadolu batı (MARMARA)             6   −0,345  [−1,053; +0,186]    1,136   fark gösterilemedi

> **KAPSAM:** (yukarıdaki kapsam beyanı bu tablo için de geçerlidir)

**Marmara: BELİRSİZLİK, zayıflık DEĞİL.** Altı olay var ve bu kurulum Marmara'da
±1,14 nat'tan küçük farkları saptayamıyor. Nokta tahmini negatif olsa da aralık
sıfırı içeriyor; "ETAS Marmara'da kötü" denemez, "bu veriyle karar verilemiyor"
denir.

Aynı okuma Batı Anadolu ve Kuzey Anadolu doğusu için de geçerlidir.

**Kazanç en çok Doğu Anadolu'dan geliyor** (105 olay, +1,559) ama tek kaynak
değil: "diğer" kategorisi de 101 olayla anlamlı kazanç veriyor (+0,826).

### Site tasarımına çevirisi

Kazancın zamansal yoğunluğu (%98,8'i en yüksek 10 olaylı başlangıçtan) doğrudan
bir tasarım kararı doğurur:

* **ETAS panelinin asıl işi kriz dönemleridir.** Büyük bir depremden sonraki
  günlerde artçı olasılıkları en çok ihtiyaç duyulan ve modelin en iyi verdiği
  bilgidir.
* **Sakin dönem kartları uzun vadeli model + küçük ETAS düzeltmesiyle
  sunulabilir.** Dizi dışı kazanç pozitif ama küçüktür; kartın omurgası
  zamandan bağımsız orandır.
* **Üstünlüğün gösterilemediği bölgelerde arayüz bunu söylemelidir.** Marmara,
  Batı Anadolu ve Kuzey Anadolu doğusunda "bu bölgede iki model arasında fark
  gösterilemedi" bilgisi gizlenmez.

---

## 4. Sayısal yöntem: ne doğrulandı, ne doğrulanmadı

    DOĞRULANAN                                     nasıl
    analitik ile simülasyon aynı TOPLAM beklenti   Ö1 (36 başlangıç), Ö2 (CSEP)
    kütle korunumu (dallanma oranı)                %0,0001 fark
    zaman/yarıçap yakınsaması                       eşikler karşılandı
    determinizm                                     bit düzeyinde, testle sabit

    DOĞRULANMAYAN                                  durum
    hücre düzeyi mekânsal dağılımın doğruluğu      Ö3a, Ö3c KALDI
                                                   (ölçüt ulaşılamazlığı ÖLÇÜLDÜ)
    kalan hücre farkının kaynağı                    AÇIKLANDI — gürültü tavanı

> **Toplam-düzeyi tutarlılık testleri hücre-düzeyi kusurlara kördür.** Kütleyi
> koruyan her hata onlardan geçer — nitekim kaynak konumu kusuru Ö1, Ö2, kütle
> ve yakınsama testlerinin hepsinden geçti ve yalnızca hücre bazlı korelasyonda
> göründü. **"Ö2 geçti" ifadesi "her şey doğrulandı" diye okunmamalıdır.**
> Ayrıntı: `docs/MEKANIZMA_BULGUSU.md` §6.

İki yöntem hücre düzeyinde **0,936** korelasyonla uyumludur; kalan fark
**gürültü tavanıyla açıklanmıştır** — analitik yöntem, simülasyon gürültüsünün
izin verdiği korelasyonun %98,2'sindedir. Ayrıntı: `docs/IKINCI_MEKANIZMA.md`.

---

## 5. Yeniden üretilebilirlik künyesi

    kurulum kimliği   : haftalik-analitik
    tanım             : haftalık örtüşmeyen 7g pencere, analitik
    ETAS parametreleri: sha256 5ab1f75edccd7c968858fcf5e72371a267130853f383035820b6095ba0f5281a
    kalibrasyon       : 1992-01-01 .. 2016-01-01, mc="positive"
    dallanma          : 0,8209 nominal (kesimsiz) / 0,8125 efektif (kesimli)
    b (ETAS beta'dan) : 1,2736
    mu                : başlangıç başına yerel kestirim (n_hat / alan / süre)
    tahmin çıktısı    : etas_analytic_weekly/ (8 parça)
    tahmin sha256     : c82db090e741ecb04ecfbae62caa9fc101c2d4ce9fa2c98b49dff62f2e292fc8
    rastgelelik       : YOK — analitik hesap deterministik
    üreten commit     : (aşağıdaki mühür tazelemesine bakınız)
    çalışma ağacı     : temiz

**MÜHÜR TAZELEMESİ.** İlk mühür `8222fdd`. Bu belge bir kez tazelendi:
metin düzeltmesi, **sayı değişikliği yok** (bkz. `docs/SAYI_HARITASI.md`).
Mühür sayıları korur, hataları değil: "kalan fark açıklanmamıştır" ifadesi
3. iş tamamlandıktan sonra yanlış bir beyan hâline geldi ve düzeltildi.

Aylık CSEP sayıları için künye: `python scripts/17_fingerprint.py --setup
aylik-analitik` (ve `aylik-1000`).

---

## Bilinen sınırlar

* Değerlendirme tek bir diziye ağır bağımlı: 252 pozitifin 148'i 2023'te.
  Bu, veri miktarıyla değil ancak on yıllara yayılan bir dönemle çözülür.
* Bölge başına olay sayısı düşük; üç bölgede karar verilemiyor.
* Güven aralıkları parametre belirsizliğini kapsamıyor.
* Hücre düzeyi mekânsal doğruluk ölçütlerle GÖSTERİLEMEDİ (Ö3a, Ö3c KALDI);
  ancak başarısızlıkların kaynağı ölçüldü: Ö3a'nın "1-10" eşiği gürültü
  tavanının üstündeydi, Ö3c düşük oranda referansın dejenereliğini ölçüyordu.
  İkinci bir mekanizmaya dair kanıt yoktur.
* Aylık CSEP kurulumu dizi başlangıçlarını yapısal olarak ıskalar.
* GSRM v2.2 verisi **CC-BY-NC-SA** — ticari kullanıma kapalı.
