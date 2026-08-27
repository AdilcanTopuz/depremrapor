# KANARYA KÜNYESİ — hangi sızıntıyı kim yakalar

Bir korumanın "kurulu" olduğunu söylemek yetmez; **neyi yakaladığı ve neyi
kaçırdığı** ölçülmüş olmalıdır (kural 10, korumaya uygulanmış hâli).

Bu belge iki koruma katmanının **işbölümünü** beyan eder.

---

## Katman 1 — YAPISAL ENGEL (`src/features/history_view.py`)

Sızıntıyı yakalamaz; **imkânsız kılar.**

| sınıf | garanti | güç |
|---|---|---|
| `HistoryView` | ref sonrası veri nesnede YOKTUR | tam (veri yokluğu) |
| `CellHistory` | veri dizide durur, açık API'de ona ulaşan parametre YOKTUR | daha zayıf (sabitlenmiş tavan) |

**Sorumluluk alanı:** her ölçekte ileri bakış — 1 saniyeden 10 yıla.
Yakalama tabanı yoktur çünkü tespit değil, engelleme yapar.

---

## Katman 2 — KANARYALAR (`src/eval/leakage_canary.py`)

Yapısal engelin dışından gelen sızıntıyı (öznitelik üretimi dışındaki
kanallar, birleştirme hataları, bölünme sızıntısı) performans üzerinden arar.

**Ölçüt (İLAN EDİLMİŞ, sonuca göre değiştirilmedi):**

    mutlak eşik   AUC > 0,90
    sıçrama       AUC > temiz taban + 0,10

**Taban:** aynı tabloda, aynı bölümde ölçülen temiz model. 2026-08-25'e kadar
sabitti (0,7909, ETAS TEST dönemi) ve eşleşmemiş bir karşılaştırmaydı.

### Kanarya 1 — KABA (hedefin kendisi öznitelik olarak)

**KÖRLÜK KOŞULU HESAPLANABİLİR:**

    eğitim pozitifi < min_child_samples  =>  KABA KANARYA KÖRDÜR

Sebep: hedefi izole eden yaprak, asgari yaprak büyüklüğü kuralınca yasaklanır;
model mükemmel özniteliği KULLANAMAZ.

Ölçülmüş iki kurulum:

| kurulum | eğitim pozitifi | min_child_samples | alarm |
|---|---|---|---|
| aylık (`target_30d_m50_all`) | 212 | 200 | **YOK — kör** |
| haftalık (`target_7d_m45_all`) | 753 | 200 | **VAR** |

Aynı kanarya, iki tabloda farklı davranarak V17'nin kök neden teşhisini
DENEYLE teyit etti: körlük modelin yapısından değil, **pozitif/eşik
oranından** geliyor.

**Kullanım kuralı:** her yeni kurulumda kanarya koşulmadan ÖNCE bu oran
kontrol edilir. Kör çıkıyorsa kanarya "temiz" raporu veremez — koşmadan önce
`min_child_samples` düşürülür ya da kanarya "bu kurulumda uygulanamaz"
etiketiyle raporlanır.

### Kanarya 2 — ZAMANSAL (ref+N gün penceresi)

**SAPTAMA TABANI ÖLÇÜLDÜ** (haftalık kurulum, 7 günlük hedef):

| ileri bakış | AUC | temiz tabana fark | alarm |
|---|---|---|---|
| 1 gün | 0,8135 | +0,0284 | yok |
| 2 gün | 0,8244 | +0,0393 | yok |
| 3 gün | 0,8442 | +0,0591 | yok |
| 5 gün | 0,9633 | +0,1782 | **VAR** |
| 7 gün | 0,9989 | +0,2138 | **VAR** |

*(temiz taban 0,7851; ölçüm TEST bölümündeydi — doğrulama bölümündeki tekrarı
aşağıda)*

**Taban 3 ile 5 gün arasındadır.**

Büyüme DOĞRUSAL DEĞİLDİR: günlük artış +0,028 · +0,011 · +0,020 · +0,060 ·
+0,011 şeklinde seyredip 3→5 gün arasında keskin hızlanır. Doğrusal
ekstrapolasyonla yapılan taban tahmini (2-3 gün) ölçümle tutmadı; taban 3-5
gün çıktı. **Koruma duyarlılığı hakkındaki tahminler ölçümün yerini tutmaz.**

**KAPSAM BEYANI:**

> 3 günden kısa ileri-bakış sızıntısını bu kanarya GÖRMEZ. O bölge
> **katman 1'in (yapısal engel) sorumluluğundadır.** Kanarya, yapısal engelin
> tamamen atlandığı iri sızıntılar için bir ikinci hat, ince sızıntılar için
> bir güvence DEĞİLDİR.

Eşik bu ölçüme bakılarak DÜŞÜRÜLMEDİ: ölçütü sonuca göre seçmek kural 1'in
ihlali olurdu. Değişen tek şey, kanaryanın kapsamının artık ölçülmüş olmasıdır.

#### Doğrulama tabanında tekrar (yürürlükteki kurulum)

Kanarya 25 Ağu 2026'da doğrulama tabanına geçti; kural 9 gereği koruma **yeni
yolda yeniden gösterildi.**

    temiz taban (doğrulama)  0,8529
    KABA kanarya             1,0000   alarm VAR

| ileri bakış | AUC | fark | alarm | tetikleyen ölçüt |
|---|---|---|---|---|
| 1 gün | 0,8736 | +0,0207 | yok | — |
| 2 gün | 0,8933 | +0,0405 | yok | — |
| 3 gün | 0,9131 | +0,0602 | **VAR** | yalnızca mutlak (>0,90) |
| 5 gün | 0,9548 | +0,1020 | **VAR** | mutlak + sıçrama |
| 7 gün | 0,9992 | +0,1463 | **VAR** | mutlak + sıçrama |

**İKİ ÖLÇÜT, İKİ AYRI TABAN — ayrı yazılır:**

    mutlak eşik (>0,90)          taban 2 ile 3 gün arasında
    sıçrama (>taban+0,10)        taban 3 ile 5 gün arasında

#### MUTLAK EŞİĞİN GEREKÇESİ BU TABANDA YANLIŞLANDI

Mutlak eşiğin gerekçesi şuydu: *"hiçbir meşru model 0,90'a yaklaşmadı; en iyi
ölçülmüş 0,79."* Doğrulama bölümünde temiz model **0,8529** veriyor — meşru
bir model, eşiğe yalnızca **+0,047** uzakta. Gerekçe bu bölüm için ölçümle
yanlışlanmıştır.

**Eşik yine de DEĞİŞTİRİLMEDİ.** Sonuç görüldükten sonra eşik oynatmak kural 1
ihlalidir. Doğru çıkarım eşiği değil KAPSAMI düzeltmektir:

> Doğrulama bölümünde **yalnızca mutlak eşiği** tetikleyen bir alarm
> SONUÇSUZDUR. İncelenmeyi gerektirir, sızıntı kanıtı sayılmaz. Bağlayıcı
> ölçüt sıçrama kriteridir (taban + 0,10 = 0,9529).

Bu, alarmın ilk tanımıyla tutarlıdır: *"alarm bir hüküm değil, durma
işaretidir."* Ölçüm, hangi ölçütün ne kadar ağırlık taşıdığını gösterdi.

**Bölüm değişince taban da değişir** — kanaryanın duyarlılığı kuruluma
bağlıdır ve her kurulumda yeniden ölçülmelidir:

| bölüm | temiz taban | mutlak ölçüt tabanı |
|---|---|---|
| test | 0,7851 | 3-5 gün |
| doğrulama | 0,8529 | 2-3 gün |

#### NPP kurulumu — üçüncü ölçüm, kural genelleşti

    temiz taban (doğrulama, nöral)   0,8542
    KABA kanarya                     1,0000   alarm VAR

| ileri bakış | AUC | fark | alarm |
|---|---|---|---|
| 1 gün | 0,8485 | **−0,0057** | yok |
| 2 gün | 0,8718 | +0,0176 | yok |
| 3 gün | 0,8936 | +0,0393 | yok |
| 5 gün | 0,9467 | +0,0925 | **VAR** |
| 7 gün | 0,9937 | +0,1394 | **VAR** |

**SAPTAMA TABANI, (BÖLÜM × MODEL SINIFI) ÇİFTİ BAŞINA ÖLÇÜLÜR.**
Üç ölçüm, kuralı genelleştirdi:

| bölüm | model sınıfı | temiz taban | saptama tabanı |
|---|---|---|---|
| test | ağaç | 0,7851 | 3-5 gün |
| doğrulama | ağaç | 0,8529 | 2-3 gün |
| doğrulama | **nöral** | 0,8542 | **3-5 gün** |

Hiçbir taban başka çifte taşınmaz. Kanarya, kalibre edilen bir ölçüm
cihazıdır ve kalibrasyonu iki boyutludur.

**1 GÜNDE NEGATİF FARK — tabanın NEDEN orada olduğunu taşır.** Bir günlük
ileri bakış AUC'yi **düşürdü** (−0,0057): sinyal yok, gürültü var. Taban
yalnızca "yakalanamıyor" değil, **"orada yakalanacak şey öğrenilemedi"**
bölgesidir.

**KOŞUL — künyenin ayrılmaz parçası:** bu taban **kısa-eğitim protokolüyle**
ölçülmüştür (6 tur, tanılama amaçlı). Tam eğitimde (80 tur) 1-2 günlük
sinyalin öğrenilebilir hâle gelmesi mümkündür; taban o durumda düşebilir.
Ölçüm koşuluyla birlikte okunur.

#### Yan bulgu — TARİF, hüküm değil

İki tamamen farklı model sınıfı, aynı doğrulama bölümünde neredeyse aynı
AUC'ye oturuyor (ağaç 0,8529 · nöral 0,8542). Bu, LightGBM sınavındaki
"sinyal geniş ve yumuşak" teşhisinin nöral taraftan ilk yankısı olabilir:
**AUC ekseninde ayrım gücünü model sınıfı değil, verinin kendisi
sınırlıyor olabilir.**

Bu bir hüküm DEĞİLDİR — kanarya kurulumundan, kısa eğitimden ve doğrulama
bölümünden gelen bir gözlemdir. Ama H1/H2'nin neden AUC ekseninde değil,
**kalibrasyon** ve **dizi-beklentisi** eksenlerinde kurulduğunun erken bir
teyidi sayılabilir: fark oralarda aranacak, çünkü burada yok görünüyor.

### Kanarya 3 — DOLAYLI (ölçekleme) — **EMEKLİ**

**KÜNYE**

    saptama tabanı        YOK -- 1,50 sd'lik kasıtlı bozulma bile
                          yakalanmadı ve etki TEKDÜZE DEĞİL
                          (kasıtlı-büyütme ile ölçüldü,
                           doğrulama x nöral çiftinde)
    gerçek sızıntı        0,0125 sd  ->  AUC +0,0003
    koruma bu eksende     YALNIZCA YAPISAL (V26 düzeltmesi, her büyüklükte)
    dedektör              YOK -- emekli edildi

**Neden emekli.** Ölçülen şey dedektörün körlüğü değil, **sondanın
bilgisizliği**: standartlaştırma farkı tüm satırlara aynı uygulanan afin bir
dönüşümdür. Ağaçlar monoton dönüşüme duyarsız, nöral ağlar afin dönüşümü
soğurur — **her iki model sınıfında da kanal boştur**, farklı sebeplerle
(V29, `docs/NPP_ILAN.md` Zeyilname 4).

**Koşul.** Kanalın boşluğu bu kataloğun **durağanlığına** bağlıdır. Dağılım
kayması olan bir kurulumda aynı sızıntı zararlı olur; yapısal koruma bu yüzden
kaldırılmaz.

**Yerine ne gelir.** Satıra bağlı ya da afin olmayan bir dönüşüm (nicelik
dönüşümü, ileri istatistikle satır normalleştirmesi). Tanım değişikliği
olduğu için, kullanılacağı koşudan ÖNCE ilan edilir.

---

### (eski metin — tarihsel kayıt)

### Kanarya 3 — DOLAYLI (ölçekleme istatistiklerine test dönemi karışması)

**AĞAÇ MODELLERİNDE YAPISAL OLARAK ETKİSİZ — koşulmaz.**

Ölçüldü: temiz 0,7847 · sızıntılı 0,7847 · fark −0,0000. Sebep boru hattının
sağlığı değil, **kanalın yokluğudur**: ağaç bölmeleri monoton dönüşümlere
duyarsızdır.

"Koştu, etki yok" raporu var olmayan bir korumanın varlığını ima ederdi
(V16 dersi: beyan, kanıtın kapsamını aşamaz). Fonksiyon artık ağaç adımında
çağrılırsa `NotImplementedError` verir; özgün gövde nöral adım için saklıdır
(`_canary_indirect_neural`), orada ölçekleme **gerçek bir kanaldır.**

---

## Özet işbölümü

| sızıntı ölçeği | kim sorumlu | kanıt |
|---|---|---|
| < 3 gün ileri bakış | katman 1 (yapısal) | `tests/test_history_view.py` |
| >= 5 gün ileri bakış | katman 1 + kanarya 2 | ölçülen taban tablosu |
| hedefin doğrudan sızması | kanarya 1 (körlük koşulu sağlanmıyorsa) | AUC 1,0000, alarm VAR |
| ölçekleme | kanarya 3 — **yalnızca nöral adımda** | ağaçta kanal yok |

Hiçbir satırda "kanıtlandı" yazmaz: her satır, o korumanın **reddettiği bir
deneye** dayanır (kural 9).
