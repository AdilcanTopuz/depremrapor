# FAZ 3 SONUCU — ML, ETAS'a karşı

**Künye.** Haftalık kurulum · hedef `target_7d_m45_all` (7 gün, M≥4.5) ·
test dönemi 2021-01-01 .. 2024-12-20 · 436.800 hücre-pencere · 252 olay ·
LightGBM (`lr=0,02 · yaprak=7 · min_child=200 · l2=10`, 3 tohum ortalaması) ·
commit `cac2862` sonrası kod.

---

## 0. ARAMA — 36'lık dağılım ve seçim

Sabit formatın dört satırı (ilan: `docs/FAZ3_PLAN.md`, "36'lık dağılımın
okunması"):

    108/108 koşu · 36/36 bileşim
    bileşimler arası yayılım (ss)   0,000009826
    tohum içi saçılım (ort ss)      0,000004058
    ORAN yayılım/saçılım            2,42
    genişlik/saçılım                7,80

    SEÇİLEN   lr=0,02 · yaprak=7 · min_child=200 · l2=10
              doğrulama logloss 0,002414729 +- 0,000001046 (3 tohum)
    EN YAKIN RAKİP  0,002414928   fark +0,000000199

### Hangi dal? — İKİSİ DE, ve bu ilanın kendi eksiğidir

İlan iki dal bağlamıştı (DAR: yayılım ≈ saçılım · GENİŞ: yayılım >> saçılım)
ve aralarında **eşik ilan etmemişti.** Ölçülen 2,42 ikisinin arasındadır.
Sonradan eşik uydurmak yerine, dalları ayıran varsayımın kendisi sınandı: ilan,
**tek bir sayının** karar vereceğini varsayıyordu. Ölçüm bunun yanlış olduğunu
gösteriyor — uzayın yapısı **ölçeğe bağlı**:

**KÜRESEL OLARAK YAPILI** (GENİŞ dalının olumlu yarısı geçerli). Dört eksenden
ikisinin etkisi tohum gürültüsünün çok üstünde:

| eksen | en iyi değer | etki | tohum saçılımının katı |
|---|---|---|---|
| `lambda_l2` | 10 | 0,0000158 | **3,9×** |
| `num_leaves` | 7 | 0,0000131 | **3,2×** |
| `learning_rate` | 0,02 | 0,0000014 | 0,3× |
| `min_child_samples` | 200 | 0,0000006 | **0,1×** |

Düzenlileştirme seçimi sonucu gerçekten etkiliyor: güçlü ceza (l2=10) ve küçük
ağaç (7 yaprak) sistematik olarak kazanıyor. Az pozitifli gürültülü bir
problemde beklenen davranış.

**YEREL OLARAK DÜZ** (DAR dalının her iki yarısı da geçerli). Optimumun civarı
tohum gürültüsünün altında:

    ilk 2 bileşim yayılımı  0,000000199   AYIRT EDİLEMEZ
    ilk 3 bileşim yayılımı  0,000000736   AYIRT EDİLEMEZ
    ilk 4 bileşim yayılımı  0,000003691   ayırt edilebilir

İlk üç bileşim **yalnızca `min_child_samples`'ta** ayrışıyor — ve o eksenin
ölçülen etkisi tohum saçılımının 0,1 katı. İki ölçüm birbirini doğruluyor:
üstteki üçlünün ayrışamamasının sebebi, ayrıştıkları eksenin etkisiz olması.

### DAR dalının ikinci yarısı — beyan

**SEÇİM NEREDEYSE KEYFÎDİR.** İlk üç bileşim ayırt edilemez; hangisinin
seçildiği tohum gürültüsü düzeyinde bir tesadüftür. Test sonucu **tek bir özel
bileşimin değil, bu düz bölgenin temsilcisi** olarak okunmalıdır.

**V23 EKİ.** İlan edilen kuralı uygulamak seçimi `mcs=20`'den `mcs=200`'e
taşımıştı. Şimdi ölçüldü: bu, **ölçülen etkisi en küçük eksendir** (0,1×).
Düzeltme usulen zorunluydu — kural doğru uygulanmalıydı — ama sayısal olarak
sonuçsuzdur. İkisi birden yazılır: usul gerekliliği, sonucun küçüklüğüyle
gerekçelendirilmez.

### DAR dalının birinci yarısı — beyan

**"YETERİNCE ARANMADI" İTİRAZI KAPALIDIR.** 36 bileşimin tamamı, her biri 3
tohumla koşuldu; uzayın üst bölgesi düzdür ve iki anlamlı eksen (l2, yaprak)
zaten uçlarında en iyi değeri veriyor. Uzayı genişletmek bu düzlüğü
değiştirmez.

---

## 1. İLAN EDİLMİŞ HÜKÜM

    AUC   Poisson 0,6503 | ETAS 0,7909 | ML 0,7869
    ML AUC tohum saçılımı  0,7874 · 0,7856 · 0,7872

    IG (Poisson'a karşı, nat/olay)   ETAS +1,068 | ML +1,086

    ML - ETAS   +0,018 nat/olay   [-0,164, +0,196]   MDE 0,256

**Ö5: EŞDEĞER** — aralık ilan edilmiş ±0,515 bandının içinde ve bandı
dolduracak kadar geniş değil.

**README §3.5 (ML, ETAS'ı GEÇMELİ): KARŞILANMADI.**

Bu, Faz 3'ün resmî sonucudur. Aşağıdakiler bu hükmü değiştirmez; **nerede** ve
**neden** ayrıştıklarını gösterir.

---

## 2. MEKANİZMA — ölçüldü, çıkarsanmadı

### 2a. ML KALİBRE DEĞİL

    gözlenen / beklenen     Poisson 1,24 | ETAS 1,09 | ML 1,82

ML, test döneminde 252 olay gözlenirken **138,8** bekliyor: toplamı %45 eksik
tahmin ediyor. ETAS 231,5 (oran 1,09) ile iyi kalibre.

**Operasyonel sonuç:** ML bu hâliyle kullanılamaz. Bir risk kartında "%X
olasılık" yazan sayı sistematik olarak 1,8 kat düşük olurdu.

### 2b. BAŞA BAŞLIK, EKSİK TAHMİNİN ÖDÜLÜNDEN GELİYOR

IG iki terimden oluşur; ayrıştırıldığında:

| kesit | olay | OLAY terimi | MARUZİYET terimi | TOPLAM |
|---|---|---|---|---|
| genel | 252 | **−0,350** | +0,368 | +0,018 |
| dizi-dışı | 193 | +0,039 | +0,146 | +0,185 |
| dizi-içi | 59 | **−1,621** | +1,092 | −0,529 |

ML, **gerçekleşen olaylarda ETAS'tan kötüdür** (−0,350) ve toplam başa başlığı
yalnızca eksik tahminin maruziyet terimindeki ödülünden alır.

Bağımsız teyit: gerçekleşen 252 olayın yalnızca **%45,2'sinde** ML daha yüksek
oran verdi (işaret testi p = 0,147).

### 2c. ŞEKİL İLE SEVİYE AYRILDIĞINDA

ML oranları ETAS toplamına ölçeklenerek kalibrasyon farkı kaldırıldı; geriye
yalnızca **şekil** (mekânsal-zamansal dağılım) kalır.

| kesit | olay | OLAY | MARUZİYET | TOPLAM | %95 GA | MDE |
|---|---|---|---|---|---|---|
| genel | 252 | +0,161 | −0,000 | **+0,161** | [−0,021, +0,340] | 0,256 |
| dizi-dışı | 193 | +0,550 | −0,265 | **+0,285** | [+0,110, +0,452] | 0,246 |
| dizi-içi | 59 | −1,110 | +0,868 | −0,241 | *(ölçülemez — ilan edilmiş kural)* | |

Saf bir ölçek kaymasının teorik bedeli −0,111 nat/olay olurdu; ML +0,018
aldığına göre şekli, kalibrasyonunun izin verdiğinden iyidir.

> **UYARI — BU ANALİZ İLAN PAKETİNDE YOKTU.** Ölçek düzeltmesi, sonuçlar
> görüldükten SONRA tasarlandı. Keşfedicidir, doğrulayıcı değildir. Hükme
> dayanak oluşturmaz; yalnızca bir sonraki adımın önceden ilan edilecek
> sorusunu belirler. Bu ayrımın yazılması V13 dersinin uygulanmasıdır: makul
> hikâye, ilan edilmiş ölçümün yerine geçemez.

### 2d. ML ARTÇI TETİKLENMESİNİ ÖĞRENMEMİŞ

SHAP (test dönemi, 50.000 satırlık örneklem, tohum 1):

    poisson_rate    %52,5      lon_c  %13,7      lat_c  %9,5
    moment_rate      %7,4      tmax_since_m5  %5,5      n365  %4,5
    quiescence_z     %2,5      n30    %1,7      n3650 %1,5      n90 %1,0
    bval             %0,3      bval_trend %0,1

Modelin yarısından fazlası **arka plan oranı**, dörtte biri **coğrafya**.
ETAS'ın çekirdeği olan kısa vadeli tetiklenme (`n30`) yalnızca **%1,7**.

Bu, dizi-içi ölçümle bağımsız olarak aynı yöne işaret ediyor:

    dizi penceresinde (59 olay)   ML bekliyor 19,8  |  ETAS bekliyor 84,3

ML, bir artçı dizisinin ortasında bile arka plana yakın tahmin veriyor.

**İki ölçüm, iki farklı yoldan, aynı sonuç.** Bu bir teyittir, ama ikisi de
aynı veriden gelir; bağımsız veri üzerinde sınanmamıştır.

---

## 3. KESİT SONUÇLARI — hüküm değil, tarif

### Rejim

    dizi-dışı  193 olay   +0,185 [+0,010, +0,352]   MDE 0,246
    dizi-içi    59 olay   ÖLÇÜLEMEZ (13 blok — V9, ilan edilmiş kural)

### Bölge (ML − ETAS)

| bölge | olay | IG | %95 GA | MDE |
|---|---|---|---|---|
| Batı Anadolu (Ege grabenleri) | 17 | +0,316 | [−0,157, +0,751] | 0,699 |
| Doğu Anadolu (Maraş-Malatya) | 105 | −0,054 | [−0,349, +0,224] | 0,420 |
| Ege denizi / Yunanistan | 13 | −0,527 | [−1,043, −0,021] | 0,785 |
| Kuzey Anadolu batı (Marmara) | 6 | +0,482 | [+0,098, +1,072] | 0,901 |
| Kuzey Anadolu doğu (Erzincan-Erzurum) | 10 | +0,354 | [−0,174, +0,822] | 0,787 |
| diğer | 101 | +0,052 | [−0,169, +0,265] | 0,306 |

**KAPSAM BEYANI.** Yedi kesit (6 bölge + 1 rejim) aynı 252 olayı böler.
Bağımsız sınamalar değildir ve **çoklu karşılaştırma düzeltmesi
UYGULANMAMIŞTIR**. %5 düzeyde rastgele beklenen yanlış pozitif sayısı ~0,35;
gözlenen "sıfırı dışlayan" kesit sayısı 3. Üç kesitin de MDE'si kendi
etkisinden BÜYÜKTÜR (Marmara 6 olayla, Ege 13 olayla) — yani aralıklar dar
değil, sadece kaymış olabilir.

Bu satırlar **hüküm değildir.** Bir sonraki adımın nereye bakacağını söylerler.

---

## 4. KAPSAM VE SINIRLAR

* Karşılaştırma, iki modelin de tanımlı olduğu **436.800** hücre-pencere
  üzerindedir (252 olayın tamamı içeridedir). Dışarıda kalan tek hücre (4037),
  Poisson temel modelinde ana şok bulunmadığı için tanımsızdır.
* Test dönemi bir kez değerlendirilmiştir; tekrar yoktur
  (`docs/TEST_DOKUNUSLARI.md`).
* Seçilen bileşim, ilk üç bileşimden **ayırt edilemez** (fark 2,0e-7, tohum
  saçılımı 1,0e-6). Sonuç, tek bir bileşimin değil düz bir bölgenin
  temsilcisidir.
* Bütün sayılar TEST dönemine, haftalık kuruluma ve M≥4.5 hedefine aittir.
  Başka pencere/büyüklük için geçerli değildir.
* §2c (ölçek düzeltmesi) ve §2d ile §2b'nin birlikte okunması KEŞFEDİCİDİR;
  önceden ilan edilmemiştir.

---

## 5. NE ÖĞRENİLDİ

**ML, ETAS'ı geçmedi ve bu bir başarısızlık değil, bir ölçümdür.** Ölçüm şunu
söylüyor: katalog özniteliklerinden öğrenen bir ağaç modeli, ETAS'ın
**arka plan** bileşenini biraz daha iyi kuruyor (dizi-dışı şekil +0,285) ama
**tetiklenme** bileşenini hiç öğrenmiyor (n30 payı %1,7; dizi penceresinde
19,8'e karşı 59 olay).

Bu, "yeterince aranmadı" itirazına da kapalıdır: 36 bileşimin tamamı denendi ve
uzayın üst bölgesi düzdür.

**Bir sonraki adımın önceden ilan edilecek sorusu buradan çıkar:** eksik olan
şey hiperparametre değil, **tetiklenmeyi ifade edebilen bir model sınıfı**.
Nöral nokta süreci (adım 4) tam bu boşluğu hedefler.
