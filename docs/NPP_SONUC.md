# NPP SONUCU — toplamsal nöral ETAS, ETAS'a karşı

**Künye.** Haftalık kurulum · hedef `target_7d_m45_all` (7 gün, M≥4,5) ·
test dönemi 2021-01-01 .. 2024-12-20 · 436.800 hücre-pencere · 252 olay ·
toplamsal nöral ETAS `gizli=32 · katman=2 · lr=1e-3 · 80 tur`, 1794 parametre,
3 tohum ortalaması · girdi dizini `sha256 5bbd69fd166ac4fe…` (K=256, R=200 km,
öncül çekirdek) · ilan paketi `36701dc` + 4 zeyilname · kod `2afda81`.

---

## 0. DETERMİNİZM ZİNCİRİ — ayrı gün, ayrı süreç, değişen işletim koşulları

Test setine dokunmadan önceki ön şart (`docs/TEST_DOKUNUSLARI.md`, Dokunuş 3):

| tohum | aramada | yeniden eğitimde | birebir |
|---|---|---|---|
| 1 | 0,00244171 (76 tur) | 0,00244171 (76 tur) | **EVET** |
| 2 | 0,00244111 (79 tur) | 0,00244111 (79 tur) | **EVET** |
| 3 | 0,00244086 (76 tur) | 0,00244086 (76 tur) | **EVET** |

Arada geçenler: farklı gün, farklı süreç, makine yeniden yüklenmiş, öncelik
sınıfı üç kez değişmiş (`Normal → Idle → BelowNormal`), 3,36 GB'lık dizin
memmap'ten yeniden okunmuş.

> Künyedeki "deterministik" beyanı artık **fiilî üretim koşullarını** kapsıyor.
> Şimdiye kadar yalnızca aynı süreç içindeki eşitlik gösterilmişti (V16'nın
> tam döngüsü).

---

## 1. İLAN EDİLMİŞ HÜKÜM — ve ondan ayrılamayacak ayrıştırma

İki önceden kayıtlı kural bu pakette **karşı karşıya geldi**:

* **Ö5 ölçütü:** aralık tümüyle sıfırın üstündeyse geçti.
* **Metrik notu:** *IG tek başına okunmaz — yanında gözlenen/beklenen oranı
  ve OLAY/MARUZİYET ayrışması bulunur.*

İkisi de ilan edilmişti; ikisi de uygulanır. Hüküm ile ayrıştırma **tek blok**
hâlinde yazılır ve ayrılmaz.

### Hüküm

    AUC   Poisson 0,6503 | ETAS 0,7909 | NPP 0,7904
    NPP AUC tohum saçılımı  0,7906 · 0,7922 · 0,7876

    IG (Poisson'a karşı)   ETAS +1,068 | NPP +1,243

    NPP - ETAS   +0,174 nat/olay   [+0,032, +0,317]   MDE 0,204

**Ö5: NPP ETAS'I GEÇTİ** (aralık tümüyle sıfırın üstünde).
**README §3.5: KARŞILANDI.**

### Ayrıştırma — geçişin kaynağı

| kesit | olay | OLAY terimi | MARUZİYET terimi | TOPLAM |
|---|---|---|---|---|
| genel | 252 | **−0,088** | +0,262 | +0,174 |
| dizi-dışı | 193 | +0,113 | +0,123 | +0,236 |
| dizi-içi | 59 | −0,746 | +0,720 | −0,027 |

    kalibrasyon (gözlenen/beklenen)   Poisson 1,24 | ETAS 1,09 | NPP 1,52

**Üstünlüğün çoğu maruziyet teriminden gelir** — yani NPP'nin toplamı %34
eksik tahmin etmesinin ödülünden. Gerçekleşen olaylarda NPP hâlâ ETAS'ın
**altındadır** (−0,088).

Bağımsız teyitler aynı yönde: AUC berabere (0,7904 vs 0,7909); işaret testi
252 olayın %50,8'inde NPP daha yüksek (p = 0,850).

**Ama LightGBM'e göre belirgin ilerleme var:**

    LightGBM - ETAS  +0,018 = OLAY -0,350 + MARUZİYET +0,368
    NPP      - ETAS  +0,174 = OLAY -0,088 + MARUZİYET +0,262

Olay terimi **dörtte birine indi** (−0,350 → −0,088).

---

## 2. ÜÇ ÇEKİNCE — hükümle birlikte okunur

### 2a. Etki, MDE'nin ALTINDA — "anlamlı ama güçsüz"

    etki  +0,174        MDE  0,204

Aralık sıfırı dışlıyor, dolayısıyla hüküm geçerlidir. Ama çalışmanın bu
büyüklükteki bir etkiyi saptama gücü %80'in **altındadır**.

> Düşük güçte çıkan anlamlı sonuçlar, etki büyüklüğünü **abartma
> eğilimindedir** (winner's curse). Etki büyüklüğüne dair her cümle,
> **geniş aralığıyla birlikte** anılır: [+0,032, +0,317].

### 2b. Ham üstünlük, kalibrasyon kusurunun ödülünü içeriyor

Yukarıdaki ayrıştırma. Ölçek düzeltilerek şekil yalıtıldığında:

| kesit | olay | TOPLAM | %95 GA | MDE |
|---|---|---|---|---|
| genel | 252 | **+0,248** | [+0,106, +0,391] | 0,204 |
| dizi-dışı | 193 | **+0,316** | [+0,159, +0,469] | 0,227 |
| dizi-içi | 59 | +0,026 | [−0,276, +0,300] | 0,410 |

Ölçek çarpanı 1,400.

### 2c. Önceden yazılan iki dal da tam oturmuyor

`docs/FAZ3_KAPANIS_TASLAK.md` iki dal bağlamıştı: **X** (NPP tetiklenmeyi
öğrendi) ve **Y** (öğrenemedi). Gerçek **ikisinin arasındadır**. Dal
zorlanmaz; bkz. §4.

---

## 3. H1 ve H2 — önceden kayıtlı birincil kesitler

### H1 — DOĞRULANDI

> Ölçek düzeltilmiş dizi-dışı IG farkı, NPP kurulumunda birincil kesittir.

    NPP - ETAS  +0,316  [+0,159, +0,469]   MDE 0,227

Aralık sıfırı dışlıyor **ve** etki MDE'nin üstünde. Bu, paketin **en temiz
pozitif sonucudur.**

Faz 3'te aynı ölçüm LightGBM için KEŞFEDİCİ olarak +0,285 [+0,110; +0,452]
çıkmıştı ve hükme dayanak sayılmamıştı. Burada önceden ilan edilmişti ve
dayanak **oldu**. Keşfedici bulgunun meşru yolculuğu tamamlandı.

### H2 — KALDI, ama iki bileşeni AYRIŞTI

İlan edilen ölçüt bir **birleşimdi**: beklenti 19,8'i belirgin aşmalı **VE**
kalibrasyon [0,80; 1,25] bandına girmeli.

    dizi penceresi beklentisi   NPP 41,8 | ETAS 84,3 | GÖZLENEN 59
    Faz 3 referansı             ML  19,8

    birinci bileşen (beklenti)     GEÇTİ -- 19,8'in iki katından fazla
    ikinci bileşen (kalibrasyon)   KALDI -- 1,52, bandın dışında

**H2 bir bütün olarak KALDI**, çünkü birleşimdi. Ama **hangi yarısının
kaldığı** bu paketin asıl bulgusudur.

---

## 4. ASIL BULGU — hükümlerin arasında duruyor

Üç ölçüm birlikte okunduğunda:

    tetiklenme    KISMEN ÖĞRENİLDİ   dizi beklentisi 19,8 -> 41,8
                                     (ETAS'ın 84,3'üne hâlâ yarı yolda)
    şekil         ETAS'TAN İYİ       dizi-dışı +0,316, MDE üstünde
    seviye        ÖĞRENİLEMEDİ       kalibrasyon 1,52

> **Model sınıfı tetiklenmeyi ifade edebiliyor ve kısmen öğreniyor;
> öğrenemediği şey seviyedir.**

Dal X'in *"öğrenilebilir"* yarısı ve Dal Y'nin *"geçemedi"* yarısı aynı anda
doğrudur. İlanın iki-dallı kuruluşu bu üçüncü durumu öngörmemişti; DAR/GENİŞ
emsalindeki gibi, **uygulanabilir beyanlar ayrı ayrı işletilir** ve uymayan
varsayımlar açıkça "gerçekleşmedi" diye işaretlenir.

### Faz 3'ün ortak cevabı — iki model sınıfından

> Tetiklenme veriden **kısmen öğrenilebiliyor** ve bunun için model sınıfı
> uygun olmalıdır: tablosal GBM, geçmişi özet istatistiklere sıkıştırdığı için
> tetiklenmeyi neredeyse hiç öğrenemedi (dizi beklentisi 19,8); olay-düzeyinde
> toplamsal yapı (λ = μ + Σ g) verildiğinde beklenti iki katına çıktı (41,8).
> Öğrenilemeyen şey, bu kurulumda, **seviye kalibrasyonudur**.

Bu, "veri yetersiz" ile "temsil yetersiz" ayrımının ölçülmüş cevabıdır: aynı
katalog, aynı bölümleme, aynı 436.800 satır, aynı 252 olay — değişen tek şey
model sınıfı.

---

## 5. ÜRÜN — tartışmasız

    ÜRÜN KAPISI [0,80; 1,25]   NPP 1,52  ->  GEÇMEDİ

**NPP operasyonel katmana ALINMAZ.** Araştırma ölçütünü geçmiş olması bunu
değiştirmez: risk kartında yazan sayı sistematik olarak 1,5 kat düşük olurdu.

    operasyonel katman   ETAS (birincil) + uzun vadeli Poisson (ikincil)
    NPP                  araştırma kolunda kalır

### İleriye tek kayıt

Kalibrasyonun bilinen çareleri vardır (ölçek yeniden-kalibrasyonu, kayıp
ağırlıklaması, sonradan-kalibrasyon). **Hiçbiri bu koşuya uygulanmaz** —
sonuç görüldükten sonra model düzeltmek, ölçütü sonuca göre seçmektir.

Bir sonraki ilan paketinin **önceden kayıtlı sorusu** olur; H1'in
keşfedici → doğrulayıcı yolculuğunun aynısı.

---

## 6. KAPSAM KİLİDİ

Hüküm şu künyeyle kayıtlıdır ve genişletilmez:

    7 günlük pencere · M >= 4,5 · haftalık kurulum
    test 2021-01-01 .. 2024-12-20 · 436.800 satır · 252 olay
    tek model sınıfı, tek bileşim, 3 tohum

**Yasak genelleme:** *"Nöral ağlar ETAS'ı geçiyor."* Doğrusu: *bu hedef
tanımında ve bu veri hacminde, toplamsal nöral ETAS önceden kayıtlı IG
ölçütünü geçti; üstünlüğünün çoğu kalibrasyon kusurunun ödülünden geldi;
olay terimi hâlâ negatif; ürün kapısını geçmedi.*

### Diğer sınırlar

* Etki MDE'nin altında (§2a) — büyüklük abartılmış olabilir.
* Seçilen bileşim, arama uzayındaki diğerlerinden **havuzlanmış saçılımla
  ayırt edilemez** (V31); seçim tek bileşimin şans eseri kararlı çıkmasına
  dayanıyor olabilir.
* Arama uzayı DAR çıktı (yayılım/saçılım 0,35): *"yeterince aranmadı"*
  itirazı kapalı, ama seçim de neredeyse keyfî.
* Kanarya 3 (ölçekleme) emekli edildi; o eksende koruma **yalnızca
  yapısaldır** (V29).

---

## 7. GÜVENLİK AĞI RAPORU

    80 turdan ÖNCE duran koşu     6/12
    en iyi turlar                 35·35·54·54·64·64·76·76·76·77·79·79
    "en iyi tur = son tur" olan   0/12

Erken durdurma yarı koşuda fiilen tetiklendi ve hiçbir koşuda seçim son tura
düşmedi. V28'de kör olan ağ (hiç tetiklenmiyor, en iyi tur = son tur) artık
hem seçiyor hem durduruyor. **Koruyucu evriminin eğitim-döngüsü paraleli
tamamlandı:** kuruldu → kör çıktı → körlüğün sebebi ölçüldü (558.000 kat) →
düzeltildi → fiilen çalıştı.
