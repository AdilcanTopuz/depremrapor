# Faz 3 açılış planı — ML modelleri

Her adımın ölçütü, adım BAŞLAMADAN ilan edilir (kural 1). Her yeni eşiğin
ulaşılabilirliği önceden gösterilir (kural 10). Denetim mirasının tamamı
yürürlüktedir: `docs/DENETIM_MIRASI.md`.

---

## ÇITA — dondurulmuş sayılar

ML modeli bu sayıları **aynı kurulumda** geçmek zorundadır.

| kurulum | sayı | rol |
|---|---|---|
| `haftalik-analitik` (M≥4,5, 252 pozitif) | AUC farkı **+0,1407** [+0,0761; +0,2144]; IG **+1,068** | **ANA SINAV** |
| dizi-dışı (30/90/180 gün) | **+0,550 / +0,313 / +0,287** | ana sınavın alt kırılımı |
| `aylik-analitik` (M≥5,0, 102 olay) | T-testi **+2,398** [+2,104; +2,692] | **İKİNCİ SINAV** |

**Ana sınav neden haftalık:** daha çok pozitif (252 vs 102), pencereler
örtüşmüyor, ve ETAS tarafı deterministik (analitik hesap). Aylık CSEP ikinci
sınav olarak saklanır.

## EŞİT BİLGİ MADDESİ

ML modeli, ETAS'la **aynı bilgiyle** yarışır:

* aynı katalog ve aynı tekilleştirme
* aynı Mc kesmesi (3,3)
* aynı 5 yıllık geçmiş penceresi
* aynı başlangıç kümesi (208 haftalık, örtüşmeyen)
* aynı hedef tanımı (7 gün, M≥4,5, artçı dahil)

Farklı bilgi rejimleri karşılaştırmayı anlamsızlaştırır. Bir modelin daha çok
veri görüp daha iyi skor alması bir bulgu değildir.

---

## (0) Arşiv kapanışı  ✅

Operasyonel geçişin yan yana arşivi:
`results/archive/2026-08-24_operasyonel_gecis/`

## (1) SIZINTI KANARYASI — Faz 3'ün İLK işi

**Gerekçe.** `grid_features`'ın "yalnızca geçmişe bakar" garantisi şu an bir
testle sabitlenmiş DEĞİL; kodda `searchsorted(t, refs, side="left")` var ve
okunarak doğrulandı. V15'in dersi tam buraya oturur: **searchsorted satırını
okuyarak doğrulamak, izleme listesini okuyarak "korunuyor" demekle aynı
işlemdir. Beyan var, mekanizma yok.**

ML koşuları başladıktan sonra sızıntı bulunursa bütün koşular çöpe gider.

### Üç seviye kanarya

Hepsi **"yakalandığında test geçer"** mantığıyla yazılır: **kanaryanın ölmesi
başarıdır.**

1. **KABA** — hedefin kendisi öznitelik olarak eklenir. Model AUC ~1,0
   vermelidir ve boru hattı bunu **ALARM** olarak raporlamalıdır, sessizce
   mükemmel skor olarak değil. Sınanan: "imkânsız derecede iyi skor" bir
   uyarı üretiyor mu?
2. **ZAMANSAL** — referans tarihinden ε SONRASININ verisiyle hesaplanmış bir
   öznitelik (örneğin "ref+1 gündeki olay sayısı"). Bu, `side="left"`
   garantisinin uçtan uca testidir. Sınanan: pencere sınırı gerçekten kapalı mı?
3. **DOLAYLI** — normalizasyon/ölçekleme istatistiklerine test dönemini
   karıştıran bir sürüm. V5 sınıfının (yanlış belirsizlik kaynağı) sızıntı
   karşılığı. Sınanan: eğitim-dışı bilgi, ölçekleme üzerinden sızıyor mu?

### Ne zaman koşar — mekanizmaya bağlı

**Öznitelik üreten modüle dokunan HER commit'te kanarya seti koşar.** Koruyucu
deseninin Faz 3 versiyonu; sızıntı tespiti tek seferlik değildir.

İzlenecek modüller: `src/features/*`, `src/models/lgbm.py`,
`src/models/neural_intensity.py`.

### Ölçüt

Üç kanarya da yakalanmadan hiçbir ML sonucu raporlanmaz. Kanarya seti
geçmiyorsa **sızıntı tespit mekanizmamız yok** demektir.

## (2) KURAL 10 — MDE hesabı, koşudan ÖNCE

**Soru:** "LightGBM Poisson'u geçiyor mu?" DEĞİL.
**Doğru soru:** "LightGBM ile **ETAS** arasındaki farkı bu veriyle
saptayabilir miyiz?"

Elimizde 252 pozitif var ve dizi-dışı MDE'ler 0,4 mertebesindeydi. ETAS ile bir
ML modeli arasındaki fark muhtemelen bundan küçük olacaktır.

### Sonuca göre iki yol

* **MDE < beklenen fark** → ana soru "ETAS'ı geçmek" olarak kalır.
* **MDE > beklenen fark (saptanamaz)** → ana soru YENİDEN YAZILIR:
  **"ETAS'a eşdeğerlik bandı + niteliksel farklar"** — hangi rejimde/bölgede
  farklılaşıyor, SHAP ne söylüyor, kalibrasyon nasıl.

**Cevaplanamayacak bir soruyu koşmamak da bir karardır ve koşudan ÖNCE
verilir.**

## (3) LightGBM

Tablosal, hızlı, SHAP'la yorumlanabilir. Poisson oranı öznitelik olarak verilir
(soru: uzun vadeli oranın üstüne bir şey eklenebiliyor mu).

Ölçütü adım başlamadan ilan edilir; MDE hesabına göre "geçmek" ya da
"eşdeğerlik + niteliksel fark" biçiminde.

## (4) Nöral nokta süreci

RECAST-tarzı. Önceki denemede ızgara üzerinde LGBM'i geçememişti; sürekli
zamanlı bir kurulum farklı sonuç verebilir.

## (5) Covariate'lar

Fay, gerinim, Coulomb. **GSRM yalnızca ARAŞTIRMA KOLUNDA** (lisans; izin talebi
24 Ağustos 2026'da gönderildi, cevap bekleniyor). İzin gelmezse ablasyon sonucu
ne olursa olsun katman ürüne girmez.

---

## Yürürlükteki kurallar (özet)

1. Ölçüt sonuçtan önce ilan edilir · 2. Yorum kuralları önceden bağlanır ·
3. "Fark gösterilemedi" yanında MDE · 4. Kapsam beyanı her GA tablosunda ·
5. Künyesiz sayı yayımlanmaz · 6. Sayı haritası her değişiklikte ·
7. Sayının kaynağı gösterilmeden gerekçe yazılmaz · 8. Beklenen etki önce ·
9. Kurulum kanıtı değil çalışma kanıtı · 10. Eşiğin ulaşılabilirliği önce

Ve sınır kaydı: **koruyucular izledikleri şeyi korur, diff okumanın yerini
tutmaz.**

---

# (3) LightGBM — KOŞU ÖNCESİ İLAN PAKETİ

Bu bölüm koşu BAŞLAMADAN commit edilmiştir. Sonradan hiçbir maddesi
değiştirilmez.

## (a) Ana soru ve eşdeğerlik bandı

> **LightGBM, ETAS'a eşdeğer mi — ve eşdeğerse hangi rejimde, hangi öznitelikler
> üzerinden, ne yönde farklılaşıyor?**

"Kim kazandı" sorusu KAPALIDIR: ölçülen MDE 0,515 nat ve tipik bir ML-ETAS farkı
bunun altında kalır (`data/processed/mde_haritasi.json`).

**Eşdeğerlik bandı: ±0,515 nat.** Çift beyan zorunludur -- bu sayı tek başına
okuyucuya bir şey söylemez:

> ±0,515 nat = ETAS'ın Poisson'a üstünlüğünün (+1,068 nat) **%48'i**.
> Yani "eşdeğer" hükmü, **"Poisson-ETAS mesafesinin yarısından yakın"**
> anlamına gelir. Daha dar bir eşdeğerlik iddiası bu veriyle kurulamaz.

Ö5'in üç koşulu geçerlidir (`docs/KABUL_OLCUTLERI.md`).

## (b) Metrikler

| rol | metrik | gerekçe |
|---|---|---|
| **ANA** | AUC farkı, dizi-dışı 90g | en duyarlı kesit: MDE 0,0692 |
| ikincil | AUC farkı, genel | MDE 0,0919 |
| ikincil | IG, genel ve dizi-dışı | MDE 0,515 / 0,425 |
| ikincil | kalibrasyon (gözlenen/beklenen) | eşdeğerlik hükmünün ikinci ayağı |

**DİZİ-İÇİ KESİT: HÜKÜM VERİLMEZ.** AUC dizi-içi 90g yalnızca **13 blok**
içeriyor; 13 bloktan bootstrap anlamlı aralık üretmez (blok hatası vakasından
biliyoruz, V9). Rejim kırılımı raporlanırken dizi-içi satırı **"ölçülemez"**
etiketiyle gelir, sayıyla değil.

## (c) Hiperparametre arama protokolü

**GEREKÇE.** ML'de sonuca-göre-ölçüt riskinin ana kapısı eşik değil MODEL
SEÇİMİDİR. "En iyi denemeyi raporlamak" bir sızıntı sınıfıdır: 36 deneme
yapılıp test setinde en iyisi seçilirse, raporlanan skor o modelin değil
ARAMANIN skorudur.

### Arama uzayı (SABİT, sonradan genişletilmez)

    learning_rate      : 0,02 · 0,05
    num_leaves         : 7 · 15 · 31
    min_child_samples  : 20 · 50 · 200
    lambda_l2          : 1 · 10
    feature_fraction   : 0,8   (sabit)
    bagging_fraction   : 0,8   (sabit, freq=1)
    num_boost_round    : 3000, doğrulama setinde erken durdurma (150)

Toplam 36 bileşim.

### Seçim kuralı

1. Her bileşim **3 tohumla** (1, 2, 3) eğitilir.
2. Seçim ölçütü: **doğrulama dönemi logloss'unun 3 tohum ORTALAMASI**.
   Doğrulama dönemi = 2016-01-01 .. 2020-12-31 (test dönemine DOKUNULMAZ).
3. Beraberlikte daha AZ yapraklı (basit) model seçilir.
4. Seçilen bileşim test setinde **BİR KEZ** değerlendirilir; 3 tohumun
   ortalaması ve saçılımı raporlanır.
5. Test sonucuna bakıldıktan sonra **hiçbir yeniden seçim yapılmaz.** Sonuç ne
   olursa olsun raporlanır.

### Kayıt

36 bileşimin doğrulama skorları TAMAMI kaydedilir ve yayımlanır. "En iyi
deneme" değil, arama uzayının tamamı görünür olur.

## (d) Farklılaşma analizi — hangi kesitlerde

Eşdeğerlik çıksa da çıkmasa da yapılır:

* **SHAP**, test dönemi: hangi öznitelikler ETAS'ın veremediği bilgiyi taşıyor?
* **Rejim kırılımı**: dizi-dışı (ölçülebilir) · dizi-içi ("ölçülemez" etiketli)
* **Bölge kırılımı**: yalnızca olay sayısı >= 5 olan bölgeler; diğerleri
  "olay sayısı yetersiz"
* **Kalibrasyon**: gözlenen/beklenen oranı, iki model için yan yana
* **Anlaşmazlık haritası**: iki modelin en çok ayrıştığı hücre-pencereler ve
  orada ne olduğu

## (e) EŞİT BİLGİ — ön koşul

LightGBM'in gördüğü hiçbir bilgi, ETAS'ın erişemediği bir kaynaktan gelmez.

* aynı katalog, aynı tekilleştirme, aynı Mc (3,3)
* aynı 5 yıllık geçmiş penceresi
* **aynı başlangıçlar**: öznitelikler haftalık referanslarla (freq=7D) yeniden
  üretilecektir; mevcut `grid_features.parquet` aylık referanslıdır ve
  doğrudan kullanılamaz
* öznitelikler yalnızca katalogdan türetilir; covariate'lar (fay, gerinim,
  Coulomb) BU ADIMIN KONUSU DEĞİLDİR -- adım (5)
* öznitelik üretimi yapısal engelden geçer (`CellHistory`)

### Geçmişsiz hücrelerde doldurma kuralı (ÖLÇÜLDÜ, ilan edilir)

Değerlendirme ızgarasının tamamı üretildiğinde satırların **%34,5'i** son 10
yılda hiç olayı olmayan hücrelere ait. O satırların öznitelikleri:

    n30 · n90 · n365 · n3650   -> 0        (olay yok; sıfır bir DEĞERDİR)
    bval · bval_trend          -> NaN      (tanımsız: b-değeri olaysız hesaplanamaz)
    moment_rate                -> NaN      (tanımsız)
    quiescence_z               -> 0        (beklenen de gözlenen de sıfır)
    tmax_since_m5              -> NaN (%85) ya da değer (10 yıldan eski M>=5 varsa)
    lat_c · lon_c              -> hücre koordinatı
    poisson_rate               -> uzun vadeli oran (baseline'dan)

**NaN kasıtlıdır ve sıfırla doldurulmaz.** "b-değeri hesaplanamıyor" ile
"b-değeri sıfır" farklı ifadelerdir; LightGBM NaN'ı ayrı bir dal yönü olarak
öğrenir ve bu, bilgiyi bozmadan taşımanın doğru yoludur.

Bu kural ilan paketinin parçasıdır: o satırların tahminleri modelin
parçasıdır ve doldurma kuralı sonucun bir bileşenidir.

---

## KOŞU ÖNCESİ KAYITLAR (şeffaflık)

### 1. Kanarya seti yeni tabloda yeniden koşuldu

Tablo değişti; garanti tablo-bağımsız ama DOĞRULAMASI tablo-bağımlıdır (V15).

    KABA     AUC 1,0000  alarm VAR    (aylık tabloda alarm YOKTU)
    DOLAYLI  temiz 0,7847 | sızıntılı 0,7847 | fark -0,0000

**KABA kanarya artık çalışıyor.** Aylık tabloda eğitimde 212 pozitif vardı ve
`min_child_samples=200` mükemmel bölmeyi yasaklıyordu. Haftalık tabloda eğitim
pozitifi **753**; yaprak oluşabiliyor ve alarm çalıyor.

Bu, V17'nin kök neden teşhisini bağımsız olarak DOĞRULAR: körlük modelin
yapısından değil, pozitif sayısı ile eşiğin oranından geliyordu.

### 2. DOLAYLI kanarya ağaç modelleri için ETKİSİZDİR — tasarım kusuru

Ölçekleme sızıntısı LightGBM'de +0,0000 etki yarattı. Sebep yapısal: **ağaç
bölmeleri monoton dönüşümlere DUYARSIZDIR**; standardizasyon ağaç modelini hiç
etkilemez.

Yani 3. kanarya, ağaçlar için VAR OLMAYAN bir sızıntı kanalını sınıyor.
Kusur kanaryada, boru hattında değil.

**Karar:** DOLAYLI kanarya, ölçeklemeye duyarlı olan NÖRAL modele (adım 4)
taşınır. Ağaç adımında koşulmaz; "koştu ve etki yok" diye raporlanması
yanıltıcı olurdu -- etkisizlik modelin sağlığından değil, kanalın yokluğundan
geliyor.

### 3. TEST SETİ SAYISI KANARYA SIRASINDA GÖRÜLDÜ — bildirim

Kanarya, temiz modelin test AUC'sini hesaplamayı gerektiriyor ve o sayı
görüldü: **0,7847** (varsayılan hiperparametrelerle, protokol dışı).

**Neden protokolü bozmaz:** ilan paketi (arama uzayı, seçim kuralı, ana metrik,
eşdeğerlik bandı) bu sayı görülmeden ÖNCE commit edilmiştir (`a49f84e`).
Dolayısıyla protokolün hiçbir maddesi bu gözleme göre ayarlanmış olamaz.

**Yine de kayda geçer:** "test setine tek dokunuş" ilkesi, tanılama amaçlı bir
kez kullanılmıştır. Arama ve seçim yalnızca DOĞRULAMA dönemiyle yapılacak;
seçilen bileşim test setinde bir kez değerlendirilecek ve sonuç ne olursa olsun
raporlanacaktır.

Bu bildirim, "gördüm ama etkilenmedim" iddiasını denetlenebilir kılmak içindir:
commit sırası bunu gösterir.

---

## UÇUŞ ÖNCESİ KONTROL — küme eşitliği, eğitim YAPILMADAN sınandı

V19 sınıfı bir uyumsuzluğun tek seferlik test değerlendirmesinde patlaması
kabul edilemezdi: o değerlendirme bir kez yapılır ve tekrarı yoktur. Bu yüzden
birleştirme, model eğitilmeden önce ayrıca koşuldu.

    ML   437.008 satır, 252 pozitif, 208 referans, 2101 hücre
    ETAS 436.800 satır, 252 pozitif, 208 referans, 2100 hücre

    yalnızca ML'de    208 satır
    yalnızca ETAS'ta    0 satır
    KÜMELER EŞİT      HAYIR
    kesişim           436.800 satır, 252 pozitif
    aynı satırda etiketler aynı mı   EVET

**Fark ÖLÇÜLDÜ ve SEBEBİ BULUNDU.** 208 satır = **1 hücre × 208 referans**:
hücre **4037** (36,12 K · 34,38 D). Bölge kutusunun içindedir ama Poisson
temel modelinde YOKTUR.

Sebep yapısaldır: temel model **ayrıştırılmış** katalogun ana şoklarından
kurulur; öznitelik tablosu **tam** katalogdan. 4037'de ana şok yok, dolayısıyla
Poisson oranı da yok. Öznitelik tablosunda ise hücre mevcut.

**Değerlendirmeye etkisi:** hiçbir pozitif kaybolmuyor (4037'de test döneminde
0 olay). Kesişim her iki modelin de tanımlı olduğu satırlardır; dışarıda kalan
208 satır boştur ve olay terimine katkısı sıfırdır.

**Kapsam beyanına yazılacak cümle:** *"Karşılaştırma, iki modelin de tanımlı
olduğu 436.800 hücre-pencere üzerindedir (252 olayın tamamı içeridedir).
Dışarıda kalan tek hücre (4037), Poisson temel modelinde ana şok bulunmadığı
için tanımsızdır."*

Sayı eşitliği (252 = 252) **tek başına yeterli olsaydı** bu fark hiç
görülmeyecekti — küme karşılaştırması onu gösterdi (V19 ilkesi).

---

## 36'LIK DAĞILIMIN OKUNMASI — İKİ YÖN DE ÖNCEDEN YAZILDI

Dağılım henüz görülmedi (arama koşuyor). Yalnızca "dar çıkarsa şu demektir"
yazmak yanlışlanamaz bir okuma olurdu; iki yön de burada bağlanır.

**Ölçü:** 36 bileşimin doğrulama logloss ortalamalarının yayılımı ile aynı
bileşimin 3 tohum arasındaki saçılımı kıyaslanır.

### DAR çıkarsa (bileşimler arası yayılım ≈ tohum saçılımı)

Problem, arama uzayındaki düzenlileştirme seçimlerine **duyarsızdır**.
Okunuşu: sinyal, hiperparametre ayarıyla çıkarılabilecek bir yerde değil.
Bu, ML'nin ETAS'ı geçememesi durumunda **"yeterince aranmadı" itirazını
kapatır** — uzayın tamamı aynı sonucu veriyorsa, uzayı genişletmek de
vermeyecektir.

Aynı zamanda bir SINIR beyanıdır: dar dağılım, "en iyi bileşim" seçiminin
neredeyse keyfî olduğunu söyler; seçilen bileşim tesadüfen en iyi görünmüş
olabilir. Bu yüzden en yakın rakiple fark ayrıca raporlanır.

### GENİŞ çıkarsa (bileşimler arası yayılım >> tohum saçılımı)

Model seçimi sonucu gerçekten etkiliyor. Okunuşu iki yönlüdür ve **ikisi de
yazılır**:

* Olumlu: uzayda bilgi var, seçim anlamlı.
* Uyarı: seçim riski büyür. 36 denemenin en iyisi, **seçim gürültüsü**
  içerebilir. Bu durumda seçilen bileşimin doğrulama üstünlüğünün tohum
  saçılımından büyük olup olmadığı ayrıca sorulur; değilse "seçildi ama
  ayırt edilemedi" denir.

### Her iki durumda da raporlanacaklar

    36 bileşimin TAMAMI (en iyi deneme değil, uzayın tamamı)
    seçilen bileşimin 3 tohum ortalaması ve standart sapması
    en yakın rakiple fark
    bileşimler arası yayılım / tohum içi saçılım oranı

Bu dört satır, hangi hücreye düşülürse düşülsün aynı biçimde yazılır.

---

## ADIM 1 SONUCU — 36'LIK DAĞILIM (ölçüldü)

    108/108 koşu, 36/36 bileşim tamam

    bileşimler arası yayılım (ss)   0,000009826
    aralık                          0,002414729 .. 0,002446403
    genişlik                        0,000031674
    tohum içi saçılım (ort ss)      0,000004058
    ORAN yayılım/saçılım            2,42

### Hangi dal?

**İlanda eşik yoktu.** DAR "yayılım ≈ saçılım", GENİŞ "yayılım >> saçılım"
diye yazılmıştı; 2,42 ikisinin arasındadır ve hangi dala düştüğünü söyleyecek
bir sayı ÖNCEDEN İLAN EDİLMEMİŞTİ. Bu, ilanın kendi boşluğudur ve sonradan
eşik uydurulmaz.

Onun yerine ÖLÇÜLEN iki şey ayrı ayrı yazılır — ikisi farklı şeyler söylüyor:

**Uzayın tamamı boş değil.** 36 bileşimin genişliği, tohum saçılımının
**7,8 katı**. Yapısal eğilimler görünür ve tutarlıdır:

    lambda_l2 = 10  ->  l2 = 1'den sistematik olarak daha iyi
    num_leaves = 7  ->  15 ve 31'den daha iyi
    lr = 0,02       ->  0,05'ten hafifçe daha iyi (ama daha çok yineleme)

Yani düzenlileştirme SEÇİMİ sonucu etkiliyor; problem hiperparametreye tümüyle
duyarsız değil. Bu yönde daha küçük/daha düzenli modelin kazanması, az
pozitifli gürültülü bir problemde beklenen davranıştır.

**Optimumun civarı DÜZ.** İlk üç bileşim tohum gürültüsünün altında ayrışıyor:

    1-2 farkı  0,000000199   |  1.nin tohum ss  0,000001046

**Hüküm: "seçildi ama ayırt edilemedi."** Test sonucu tek bir özel bileşimin
değil, bu düz bölgenin temsilcisi olarak okunur.

### Adım 2 — seçilen bileşim

    lr = 0,02 · num_leaves = 7 · min_child_samples = 200 · lambda_l2 = 10
    doğrulama logloss   0,002414729 +- 0,000001046  (3 tohum)
    en yakın rakip      0,002414928   (fark +0,000000199)

**DÜZELTME BİLDİRİMİ.** İlk koşuda kod `mcs=20` seçmişti; sebebi bir yuvarlama
hatasıydı ve seçim ham üçüncü sıraya düşmüştü (V23). Kod ilan edilen kurala
uyduruldu, seçim `mcs=200`'e taşındı. Değişiklik burada açıkça yazılıdır;
sessizce düzeltilmemiştir.

Kaldı ki üç bileşim de ayırt edilemez olduğu için bu düzeltme **sonucu
değiştirmesi beklenmeyen** bir düzeltmedir — ama kural doğru uygulanmalıdır,
sonucu değiştirsin ya da değiştirmesin.

---

## ADIM 4 (NÖRAL NOKTA SÜRECİ) — ÖNCEDEN KAYIT, açık uçlar

Faz 3'ün keşfedici bulgusu burada **doğrulayıcı soruya** dönüştürülür.
Keşfedicinin meşru hayatı budur: bir sonraki deneyin önceden ilan edilmiş
sorusu olmak.

### Önceden kayıtlı hipotez H1

> **Ölçek düzeltilmiş dizi-dışı IG farkı**, NPP kurulumunda **birincil
> kesitlerden biridir.**

Faz 3'te ölçüldü (KEŞFEDİCİ): ölçek düzeltilmiş ML − ETAS dizi-dışı
**+0,285 [+0,110, +0,452]**. Bu sayı Faz 3'te hükme dayanak DEĞİLDİ. NPP
kurulumunda aynı kesit **önceden ilan edilmiş** olarak ölçülür ve hükme
dayanak OLUR.

Ölçüt: NPP − ETAS, ölçek düzeltilmiş, dizi-dışı, %95 GA ve MDE ile.

### Önceden kayıtlı hipotez H2 — asıl soru

> Tetiklenmeyi ifade edebilen bir model sınıfı (NPP), tablosal GBM'in
> giremediği bölgeye girebiliyor mu?

Faz 3'ün ölçtüğü boşluk:

    n30'un SHAP payı            %1,7
    dizi penceresi beklentisi   ML 19,8 · ETAS 84,3 · gözlenen 59

Ölçüt: NPP'nin **dizi penceresindeki beklenen olay sayısı**. Bu, dizi-içi IG
gibi "ölçülemez" değildir — beklenen sayı bir toplamdır, bootstrap
gerektirmez.

    H2 geçer   : NPP'nin dizi beklentisi 19,8'den belirgin şekilde yüksek VE
                 kalibrasyon oranı ETAS'ınkine (1,09) yaklaşıyor
    H2 kalır   : beklenti arka plana yakın kalıyor -> tetiklenme yine
                 öğrenilmemiş; sorun model sınıfı değil, öznitelik/veri

### Kalibrasyon ölçütü — ürün katmanının şartı

    gözlenen / beklenen oranı, [0,8 · 1,25] bandının DIŞINDA ise
    model operasyonel katmana ALINMAZ

ML bu ölçütü karşılamıyor (1,82). Bu, Faz 3'ün ürün katmanı hükmüdür ve NPP
için de önceden geçerlidir.

### İlan tamamlanmadan koşulmaz

Arama uzayı, seçim kuralı, ana metrik ve eşdeğerlik bandı — dördü de
NPP koşusundan ÖNCE commit'lenir. Faz 3'ün usulü aynen uygulanır.

---

## SONRAKİ İLAN PAKETİNİN ÖNCEDEN KAYITLI HİPOTEZ ADAYI

**Gözlem (ölçülmüş).** İki farklı model sınıfı, iki farklı kayıp fonksiyonu,
**aynı yönde** kapıda kaldı:

    LightGBM (ikili logloss)   gözlenen/beklenen 1,82
    NPP      (Poisson NLL)     gözlenen/beklenen 1,52
    ETAS                       1,09

İkisi de **eksik tahmin** ediyor. Farklı mimari + farklı kayıp aynı yöne
sapıyorsa, sebep muhtemelen **model tarafında değil, hedef yapısındadır.**

**Hipotez (ÖLÇÜLMEDİ — bir sonraki paketin ön-kayıtlı sorusu).**

> 252 pozitif, 436.800 satıra aşırı kümelenmiş biçimde dağılmıştır. Kaybın
> ezici çoğunluğu **sakin dönemden** gelir ve sakin dönemi doğru tahmin
> etmenin en ucuz yolu **az tahmin etmektir**. Eniyileyici, dizi
> dönemlerindeki büyük ama seyrek cezayı, sakin dönemdeki küçük ama yaygın
> kazançla takas ediyor olabilir.

**Neden ETAS bundan etkilenmiyor.** ETAS'ın seviyesi kayıptan değil,
**dallanma oranından ve arka plan kestiriminden** gelir; bir eniyileyicinin
takas kararına tabi değildir.

**Sınama tasarımı (koşudan önce ilan edilecek).** En az iki kol gerekir,
çünkü tek kol hipotezi doğrulayamaz:

    (a) kayıpta dizi dönemlerinin ağırlığı artırılır -> kalibrasyon düzelir mi
    (b) hedef daha az kümelenmiş bir tanımla kurulur (ör. sayım hedefi ya da
        daha uzun pencere) -> aynı model sınıfı bandda kalır mı

Kalibrasyonun bilinen çareleri (sonradan-kalibrasyon, ölçek düzeltmesi)
**hipotezi sınamaz**, yalnızca belirtiyi örter. Ayrım korunur: **çare ile
teşhis aynı şey değildir.**
