# NÖRAL NOKTA SÜRECİ — İLAN PAKETİ

**Bu belge koşudan ÖNCE commit'lenir.** Sonuç görüldükten sonra hiçbir maddesi
değiştirilmez. Faz 3'ün usulü aynen uygulanır.

---

## 0. SORU

Faz 3 şunu ölçtü: LightGBM, ETAS'ın **arka plan** bileşenini biraz daha iyi
kuruyor ama **tetiklenme** bileşenini hiç öğrenmiyor (`n30` SHAP payı %1,7;
dizi penceresinde 19,8 olay bekliyor, gözlenen 59; kalibrasyon 1,82).

> **Tetiklenmeyi ifade edebilen bir model sınıfı, o boşluğu dolduruyor mu?**

---

## 1. MODEL SINIFI — toplamsal nöral ETAS

    lambda(hücre, hafta) = mu_theta(statik)  +  SUM_i  g_theta(dt_i, dr_i, m_i)

`g_theta`: küçük bir MLP — **öğrenilen tetiklenme çekirdeği**.
`mu_theta`: statik özniteliklerden arka plan.

**Neden toplam havuzlama (Deep Sets), dizi kodlayıcı (GRU/dikkat) değil.**

ETAS'ın koşullu yoğunluğu tanım gereği geçmiş olaylar üzerinde bir
**toplamdır**; sıra bilgisi taşımaz. Permütasyona duyarsız toplam havuzlama
bu yapının doğru tümevarım önyargısıdır — ve ETAS'ın parametrik çekirdeği
optimal ise `g_theta` onu temsil edebilir, değilse geçebilir. Bu, ETAS'ı
**özel durum olarak içeren** bir model sınıfıdır.

**Dürüstlük notu — hız da bir kısıttı.** Ölçüldü (`scripts/23`):

    toplam havuzlama  K=16 d=32  ->   5,1 sn/tur
    GRU               K=16 d=32  ->  64,3 sn/tur
    dikkat            K=16 d=32  -> 110,0 sn/tur

CPU-only ortamda (torch 2.13.0+cpu, GPU yok) GRU ile ilan edilebilir bir arama
zaten koşulamazdı. Mimari seçimi yapısal gerekçeyle savunulur, **ama hızın da
kısıt olduğu gizlenmez.** İki gerekçe birden yazılır.

---

## 2. GİRDİ — K ve R ÖLÇÜLEREK seçildi

Keyfî bir K/R, modelin başarısızlığını "mimari yetersiz" ile "girdi kırpılmış"
arasında ayırt edilemez kılardı. Bu yüzden ETAS'ın kendi tetiklenme kütlesi
ölçü olarak kullanıldı (`scripts/24`, 800 hücre-başlangıç, EĞİTİM dönemi).

**Ölçüt (önce ilan edildi, sonra ölçüldü):** K ve R, ETAS kütlesinin
**%5 diliminde bile ≥ 0,95'ini** taşıyan en küçük değerler.

| K | ortalama pay | %5 dilim | | R km | ortalama | %5 dilim |
|---|---|---|---|---|---|---|
| 16 | 0,9615 | 0,8212 | | 50 | 0,8462 | 0,0237 |
| 32 | 0,9843 | 0,9267 | | 100 | 0,9436 | 0,6240 |
| **64** | **0,9944** | **0,9774** | | **200** | **0,9855** | **0,9601** |
| 128 | 0,9983 | 0,9928 | | 400 | 0,9986 | 0,9987 |

    SEÇİLDİ:  K = 64 olay   ·   R = 200 km   ·   geçmiş penceresi 10 yıl

Her olay için girdi: `(log(dt+c), log(dr+d), m - mc)` ve maskeleme bayrağı.

Statik dal: Faz 3'ün 12 katalog özniteliği (aynı tablo, aynı doldurma kuralı).

---

## 3. KAYIP — kalibrasyon artık kaybın içinde

    Poisson NLL:   lambda  -  y * log(lambda)

Faz 3'te ikili logloss kullanılmıştı ve model **1,82 kat eksik kalibre**
çıktı. Poisson NLL doğrudan oranı hedefler; kalibrasyon bir yan ürün değil,
en aza indirilen şeyin parçasıdır.

**NEGATİF ALT ÖRNEKLEME + AĞIRLIK.** 2,3 milyon satırın 753'ü pozitif. Her tur
tüm negatifleri dolaşmak CPU'da gereksizdir. İlan:

    her turda TÜM pozitifler + negatiflerden p = 0,05 oranında örneklem
    negatif satırların maruziyet terimi 1/p ile AĞIRLIKLANIR

Ağırlıklandırma tahmin ediciyi yansız bırakır. **Kural 9 gereği bu bir testle
bağlanır** (`tests/test_npp_ornekleme.py`): ağırlıklı kayıptan kestirilen
toplam oran, tam veriyle kestirilenle uyuşmalıdır. Test yazılmadan koşu
başlamaz.

---

## 4. ARAMA UZAYI (SABİT, genişletilmez)

    gizli boyut (g_theta ve mu_theta)   32 · 64
    katman sayısı (g_theta)              2 · 3
    öğrenme oranı                      1e-3 · 3e-3
    ağırlık cezası (weight decay)      1e-5   (sabit)
    yığın                              16384  (sabit)
    tur sayısı                            40, doğrulama NLL'inde erken durdurma (8)

**8 bileşim × 3 tohum (1, 2, 3) = 24 koşu.**

Ölçülen süreye göre boyutlandırıldı: toplam havuzlama K=64 için tur başına
~20-40 sn beklenir; 40 turla koşu ~15-25 dk, 24 koşu ~6-10 saat. Alt örnekleme
(§3) bunu ~20 kat düşürür. **Koşu başlamadan önce tek bir koşu zamanlanır ve
tahmin doğrulanır** — tutmuyorsa arama uzayı KÜÇÜLTÜLÜR, süre uydurulmaz.

## 5. SEÇİM KURALI

1. Her bileşim 3 tohumla eğitilir.
2. Ölçüt: **doğrulama dönemi Poisson NLL'inin 3 tohum ORTALAMASI**
   (2016-01-01 .. 2020-12-31; test dönemine DOKUNULMAZ).
3. **Yuvarlama YOK.** Ham ortalama karşılaştırılır (V23 dersi).
4. Beraberlikte daha AZ parametreli model.
5. Seçilen bileşim test setinde **BİR KEZ** değerlendirilir.
6. Sonuca bakıldıktan sonra yeniden seçim YOK.
7. **8 bileşimin tamamı** yayımlanır; ayrıca yayılım/saçılım oranı ve
   eksen bazlı etki tablosu (Faz 3'ün sabit formatı).

---

## 6. DETERMİNİZM PROTOKOLÜ — beyan, kanıtın kapsamıyla örtüşsün (V16)

NPP eğitimi stokastiktir. "Aynı sonuç" ifadesinin ne demek olduğu ÖNCEDEN
tanımlanır:

    "TEKRARLANABİLİR" = aynı tohum + aynı veri -> BİREBİR aynı doğrulama NLL

Uygulanacaklar:

    torch.manual_seed(tohum) · numpy default_rng(tohum) · DataLoader shuffle
    tohumu ayrıca sabitlenir
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads SABİT (8) — iş parçacığı sayısı toplama sırasını
    değiştirebilir ve kayan nokta toplaması birleşmeli değildir

**Kural 9:** bu beyan bir testle bağlanır (`tests/test_npp_determinizm.py`):
aynı tohumla iki eğitim birebir aynı NLL vermelidir. Test geçmeden künyeye
"deterministik" yazılmaz.

**Tohum saçılımı raporlanır**, gizlenmez: 3 tohumun ortalaması VE standart
sapması, her bileşim için. Bileşimler arası fark, tohum saçılımını aşmıyorsa
hüküm **"seçildi ama ayırt edilemedi"** olur (Faz 3'ün kuralı).

---

## 7. SIZINTI KANARYALARI — biri ilk kez anlamlı

| kanarya | NPP'de durumu |
|---|---|
| 1 KABA | koşulur; körlük koşulu (`eğitim pozitifi < min_child`) ağaçlara özgüydü, NPP'de yok — ama alarm yine gösterilmelidir |
| 2 ZAMANSAL | koşulur; saptama tabanı NPP kurulumunda YENİDEN ölçülür (duyarlılık bölüme ve modele bağlıdır) |
| 3 DOLAYLI | **ilk kez anlamlı.** Ağaçlarda kanal yoktu (monoton dönüşüme duyarsızlık); nöral modelde ölçekleme gerçek bir kanaldır. `_canary_indirect_neural` etkinleştirilir ve **saptama tabanı ölçülür** |

Üçü de koşudan önce koşulur ve **reddettikleri bir deneyle** gösterilir.
Kanarya kalibre edilmeden ana koşu başlamaz.

---

## 8. BİRİNCİL KESİTLER — önceden kayıtlı hipotezler

### H1 — ölçek düzeltilmiş dizi-dışı fark

Faz 3'te KEŞFEDİCİ olarak ölçüldü (ML−ETAS, ölçek düzeltilmiş, dizi-dışı:
**+0,285 [+0,110; +0,452]**) ve hükme dayanak SAYILMADI. Burada **birincil
kesit olarak önceden ilan edilir** ve hükme dayanak OLUR.

    ölçüt: NPP - ETAS, ölçek düzeltilmiş, dizi-dışı, %95 GA + MDE

### H2 — tetiklenme boşluğu

    ölçüt: NPP'nin dizi penceresindeki (90 gün) BEKLENEN olay sayısı

Bu kesit "ölçülemez" DEĞİLDİR: dizi-içi yasağı 13 bloklu **bootstrap**'a
aitti; beklenen sayı bir toplamdır, yeniden örnekleme gerektirmez.

    referanslar:  ML 19,8  ·  ETAS 84,3  ·  GÖZLENEN 59

    H2 GEÇER : NPP beklentisi 19,8'i belirgin aşıyor VE kalibrasyon oranı
               [0,80; 1,25] bandına giriyor
    H2 KALIR : beklenti arka plana yakın -> tetiklenme yine öğrenilmemiş;
               sorun model sınıfı değil, öznitelik/veri

---

## 9. HÜKÜM ÖLÇÜTLERİ

    README §3.5   NPP, ETAS'ı GEÇMEDİKÇE başarı sayılmaz
    Ö5 bandı      +-0,515 nat/olay (Faz 3 ile AYNI, değiştirilmedi)
    ÜRÜN KAPISI   gözlenen/beklenen [0,80; 1,25] dışındaysa operasyonel
                  katmana ALINMAZ (docs/SITE_SARTNAME.md)

Üç ölçüt de sonuçtan bağımsızdır ve sonuca bakılarak gevşetilmez.

---

## 10. KÜME EŞİTLİĞİ

Değerlendirme, Faz 3 ile **AYNI** 436.800 hücre-pencere üzerindedir.
`(cell_id, ref_date)` kümeleri karşılaştırılır; sayı eşitliği yeterli
sayılmaz (V19). Fark çıkarsa sebebi bulunur ve kapsam beyanına yazılır.

---

## 11. KOŞU ÖNCESİ KONTROL LİSTESİ

Hepsi tamamlanmadan ana koşu başlamaz:

    [ ] tests/test_npp_ornekleme.py    ağırlıklı kayıp yansız mı
    [ ] tests/test_npp_determinizm.py  aynı tohum -> birebir aynı NLL
    [ ] kanarya 1, 2, 3 NPP kurulumunda koşuldu ve REDDETTİ
    [ ] kanarya 3'ün saptama tabanı ölçüldü
    [ ] tek koşu zamanlandı, arama süresi tahmini doğrulandı
    [ ] küme eşitliği uçuş öncesi kontrolü
    [ ] bu belge commit'lendi

---

# ZEYİLNAME 1 — GİRDİ TEMSİLİ DEĞİŞTİ (koşudan ÖNCE, 25 Ağu 2026)

**§2 yürürlükten kalktı. Yerine bu bölüm geçer.** Değişiklik sessizce
yapılmadı; sebebi, elenen seçenekler ve ölçümleri aşağıdadır.

## Neden — ilk tasarım ETAS'ın CEVABINI girdiye sızdırıyordu

§2'deki kapsam ölçümü olayları **uydurulmuş ETAS çekirdeğinin kütlesine göre**
sıralıyordu. Bu sıralama girdi seçimine uygulansaydı, nöral modele "hangi
olaylar önemli" bilgisi **ETAS'ın kendi cevabından** verilmiş olurdu.

NPP'nin ETAS'ı geçmesi durumunda bu itiraz kapatılamazdı: *"girdiyi ETAS
seçtiyse, karşılaştırma adil mi?"*

Sızıntı kanaryalarının yakalayacağı bir sızıntı DEĞİLDİR — hedef sızıntısı
yok, ileri bakış yok. Tasarım düzeyinde bir haksız avantajdır ve yalnızca
tasarımı okuyarak görülür.

## Elenen seçenekler — hepsi ÖLÇÜLDÜ

**(a) Tarafsız "en yeni K olay".** ELENDİ.

    K=64: gerçek tetiklenme kütlesinin ort %35'i, %5 diliminde %0,06'sı

Sebep fiziksel: kütleyi taşıyan büyük olay zamanda geride kalabilir; yakın
geçmiş küçük artçılarla dolar.

**(b) Tam çift değerlendirmesi (seçim yok).** ELENDİ.

    başlangıç başına 2,1 milyon (hücre, olay) çifti
    eğitim turu başına 2,3 MİLYAR çift -> CPU'da koşulamaz

**(c) (Δt, Δr, m) histogramı (seçim yok, özet).** ELENDİ.

Kutu başına EN İYİ sabit değer (negatif olmayan en küçük kareler ile
kestirildi) kullanılsa bile:

    300 kutu  -> bağıl hata medyanı %62
    672 kutu  -> %49
    1600 kutu -> %33   (10,5 GB bellek)

Kutu içinde çekirdek büyüklük mertebeleri değişiyor ve satırlar arası bileşim
farklı; sayım tek başına yeterli istatistik değil.

## Seçilen — ÖNCÜL çekirdekle sıralama

Olaylar, **literatürden alınmış, bu veriye uydurulmamış** bir çekirdekle
sıralanır:

    p = 1,10 · c = 0,01 gün · d = 5 km · rho = 0,75 · alpha10 = 1,00

Uydurulmuş değerlerle karşılaştırma (kasten farklı):

    uydurulmuş: p=1,097 · c=9,8 sn · d=1,45 km · rho=0,591 · alpha10=0,922

Bu bir **tasarım öncülüdür**, veriden öğrenilmiş bir cevap değil. Aynı öncül,
ETAS kurulmamış olsaydı da yazılabilirdi.

### Kapsam ölçümü (ölçüt DEĞİŞMEDİ: %5 diliminde ≥ 0,95)

Öncülle seçilen ilk K olayın, **gerçek** ETAS kütlesindeki payı:

| K | ortalama | %5 dilim | %1 dilim |
|---|---|---|---|
| 64 | 0,9390 | 0,7116 | 0,3242 |
| 128 | 0,9791 | 0,8962 | 0,7180 |
| **256** | **0,9947** | **0,9794** | 0,9130 |

    SEÇİLDİ:  K = 256  ·  R = 200 km  ·  geçmiş 10 yıl

**Denenen ve İŞE YARAMAYAN ek kural.** "En büyük b olayı her zaman dâhil et"
(b = 8, 16) kapsama **hiçbir şey eklemedi** (0,9390 -> 0,9390). Sebep ölçüldü:
büyük olaylar öncül sıralamada zaten üst sıralarda. Kuyruk kaybı kaçırılmış
tek bir büyük olaydan değil, **çok sayıda orta katkıdan** geliyor. Bu negatif
sonuç da kayda geçer — denendi, işe yaramadı, atıldı.

## Değişen ve DEĞİŞMEYEN

    DEĞİŞTİ : K 64 -> 256 · sıralama uydurulmuş çekirdek -> ÖNCÜL çekirdek
    AYNI    : ölçüt (%5 dilim >= 0,95) · R = 200 km · geçmiş 10 yıl
              mimari · kayıp · seçim kuralı · determinizm protokolü
              H1/H2 · Ö5 bandı · ürün kapısı · kontrol listesi

Ölçüt değişmedi; ölçütü karşılayan tasarım değişti. **Sonuç görülmeden.**

## Maliyet — ölçüldü

    dizin dosyası   3,29M satır x 256 int32 = 3,37 GB (diskte, memmap)
    dizin kurma     ~1,5-2,5 saat (bir kez)
    eğitim turu     ~4 sn (negatif alt örneklemeyle)
    24 koşu         ~1,5 saat

Ana koşudan önce tek koşu zamanlanır (kontrol listesi maddesi).

## Zeyilname 1 eki — BAĞIMSIZLIK BEYANI (künyeye girer)

Öncül ve uydurulmuş parametreler yan yana yayımlanır ki bağımsızlık iddiası
denetlenebilsin:

| parametre | ÖNCÜL (literatür, uydurulmamış) | UYDURULMUŞ (bu katalog) |
|---|---|---|
| p | 1,10 | 1,097 |
| c | 0,01 gün (864 sn) | 9,8 sn |
| d | 5 km | 1,45 km |
| rho | 0,75 | 0,591 |
| alpha10 | 1,00 | 0,922 |

**BENZERLİK KOPYA DEĞİLDİR — çerçeve.** Öncül değerler literatürün tipik
aralıklarından seçildi (Omori p ~ 0,9-1,2; GR-üretkenlik alpha10 ~ 0,8-1,2);
uydurulmuş değerler aynı fiziksel havuzdan geldiği için **benzer çıkması
kaçınılmazdır.** Benzerlik, öncülün uydurulmuş değerden türetildiğini
göstermez.

Denetlenebilir kanıt **sıra**dır: öncül değerler, kalibre değerlere
BAKILMADAN yazılabilirdi ve `docs/NPP_ILAN.md` Zeyilname 1'de bu iddia
commit'lenmiştir. Ayrıca ikisi arasındaki farklar küçük değildir:
c 88 kat, d 3,4 kat ayrışıyor.

**Okuyucuya:** benzerliği kopya sanmayın; farkı da "yanlış öncül" sanmayın.
Öncülün işi doğru olmak değil, **ETAS'tan bağımsız olmaktır.** Kapsam ölçümü
(K=256'da %5 dilimi 0,9794) zaten öncülün yeterli olduğunu gösteriyor.

---

# ZEYİLNAME 2 — TAŞIMA DENETİMİ (koşudan ÖNCE, 25 Ağu 2026)

V26 tekil bir bulguydu: ağaç yolunda zararsız olan bir kalıp (ölçekleme
kapsamı) nöral yolda sızıntıydı. **Sınıfın tamamı denetlendi:** Faz 3'ten
taşınan her kalıba tek soru soruldu —

> Bu, HANGİ model sınıfında zararsızdı? Nöral yolda da öyle mi?

| taşınan kalıp | ağaç yolunda | nöral yolda | sonuç |
|---|---|---|---|
| ölçekleme istatistiklerinin kapsamı | zararsız (ölçüldü: −0,0000) | **SIZINTI** | düzeltildi (V26) |
| `poisson_rate` özniteliği | `load_dataset` birleştirmeyle ekliyor | **YOKTU** | eklendi (V27) |
| eksik değer (NaN) işleme | **yerli**: bölme yönü öğrenilir | `nan_to_num(0)` | düzeltildi (V27) |
| Poisson temel modelin dönemi | 1990-2016 | aynı | **TEMİZ** — ölçüldü |
| hedef etiketi ve değerlendirme kümesi | aynı | aynı | değişiklik yok |
| doldurma kuralı (sayımlar 0) | aynı | aynı | değişiklik yok |

## Poisson temel modelin dönemi — TEMİZ, ve ölçülerek

`src/models/baseline_poisson.py`: `TRAIN_START = 1990-01-01`,
`TRAIN_END = 2016-01-01`. Doğrulama dönemi 2016-01-01'de başlıyor; temel
model **test dönemini görmüyor.** Varsayılmadı, koda bakılarak doğrulandı.

Bu, Faz 3'ün sonuçları için de geçerlidir: `poisson_rate` özniteliği
(SHAP payı %52,5) test döneminden bilgi taşımıyor.

## Eksik değer işleme — TEMSİL değişti, ANLAM korundu

Eğitim bölümündeki NaN oranları:

    bval           %96,6        tmax_since_m5  %73,5
    bval_trend     %98,9        moment_rate    %32,8

LightGBM NaN'ı **yerli** işler: eksiklik bir bilgidir, bölme yönü öğrenilir.
Nöral ağın böyle bir yeteneği yok ve ilk sürüm `nan_to_num(0)` kullanıyordu —
bu, satırların %96,6'sında **"b-değeri sıfır"** demektir. Fiziksel olarak
saçmadır (b ≈ 1) ve ilan edilen doldurma kuralının ("tanımsız istatistikler
NaN; sıfırla doldurulmuyor") tam tersidir.

**Düzeltme:** eksiklik ayrı bir **gösterge sütunu** olur (0/1, ölçeklenmez),
değer **eğitim medyanıyla** doldurulur.

    statik girdi: 12 öznitelik + 4 eksiklik göstergesi = 16 sütun

**İlan değişti mi?** §2 "Faz 3'ün 12 katalog özniteliği (aynı tablo, aynı
doldurma kuralı)" diyordu. Öznitelik kümesi ve doldurma kuralının **anlamı**
aynı; **temsili** değişti — çünkü aynı anlamı yerli NaN desteği olmayan bir
model sınıfında korumanın başka yolu yok. Değişiklik sonuç görülmeden
yapıldı ve burada yazılıdır.

## Denetimin kendisi hakkında

Bu tablo, V26'nın tekil düzeltmesinden sonra **sınıfın tamamı için**
istendi ve iki yeni kusur daha çıkardı. Tekil bir bulgu kapatıldığında
sorulacak soru: *"bu bulgunun sınıfı nedir ve o sınıfın başka örneği var mı?"*

## Zeyilname 2 eki — EKSİKLİK GÖSTERGELERİ AYRI ÖZNİTELİKTİR

Gösterge sütunları (`eksik_bval`, `eksik_bval_trend`, `eksik_tmax_since_m5`,
`eksik_moment_rate`) modelin gördüğü **gerçek özniteliklerdir** ve
farklılaşma analizinde **ayrı satır olarak** raporlanır — asıl sütunlarıyla
toplanmaz.

Bu, NPP'de **ilk kez ölçülebilir** olan bir soruyu açar:

> Eksikliğin KENDİSİ ne kadar bilgi taşıyor?

LightGBM'de bu soru sorulamıyordu: NaN'ı yerli işlediği için "eksiklik bilgisi"
ile "değer bilgisi" tek bir öznitelik payının içinde birleşiktir. Nöral yolda
ikisi ayrı sütun olduğu için payları ayrı ölçülür.

Bu, iki model sınıfı arasındaki **meşru bir kesittir** ve farklılaşma
analizine eklenir. Hükme dayanak değildir; tarif eder.

---

# KANARYA 3'ÜN İLK GERÇEK SINAVI — okuma kuralları, KOŞUDAN ÖNCE

Kanarya 3, ağaçlarda **kanalsız** olduğu için hiç anlamlı sınanamadı
(ölçüldü: fark −0,0000, sebep monoton dönüşüme duyarsızlık). Nöral modelde
ölçekleme gerçek bir kanaldır; bu, dedektörün **ilk gerçek sınavıdır.**

İki sonucun da ne anlama geldiği önceden bağlanır.

## (1) Kanarya sızıntılı `Yigin`'i YAKALARSA

    dedektör doğrulandı
    V26 düzeltmesinin gerekliliği BAĞIMSIZ olarak kanıtlandı

Çifte kazanç: hem koruma kurulu sayılır (kural 9), hem de tasarım okumasıyla
bulunan kusur ikinci bir yoldan teyit edilir.

## (2) YAKALAMAZSA

**V26 düzeltmesi yerinde KALIR.** Sızıntı tasarım okumasıyla kanıtlandı —
ölçekleme istatistikleri test dönemini görüyordu, bu bir ölçüm sorusu değil
bir olgu. Düzeltme kanaryaya muhtaç değildir.

Değişen tek şey **dedektörün künyesidir**:

> Kanarya 3, nöral kanalda da saptama gösteremedi. Ölçekleme ekseninin
> koruması **yalnızca yapısaldır** (`Yigin.olcek_satirlari` + nesnenin
> `olcek_kapsami` beyanı). Dedektörsüz, ama beyansız değil.

## Kural

**Kanarya sonucu, düzeltmenin kaderini değil dedektörün künyesini belirler.**
Bir kusurun varlığı, onu yakalayan bir dedektörün varlığından bağımsızdır.

## Saptama tabanı

Kanarya 2 dersi (duyarlılık bölüme ve kuruluma bağlıdır) burada da geçerlidir:
kanarya 3 alarm verirse **saptama tabanı** — ne kadar kısmi bir ölçekleme
sızıntısını görebildiği — bu kurulumda ölçülür ve künyeye **hangi bölümde
ölçüldüğü** yazılır.

---

# ZEYİLNAME 3 — YAKINSAMA ÖLÇÜTÜ (sonuç görülmeden, 25 Ağu 2026)

V28, ilklendirmeyi düzeltti. Yeni zamanlama koşusu **hâlâ sürüyor** ve erken
durdurmanın tetiklenip tetiklenmeyeceği bilinmiyor. Karar bu yüzden şimdi
bağlanır.

## Neden şimdi

Erken durdurma yine tetiklenmezse iki okuma mümkün:

    (a) model platoya oturdu, kalan iniş önemsiz  -> 40 tur YETERLİ
    (b) model hâlâ ilerliyor                      -> 40 tur BAĞLAYICI KISIT

Sonuç görüldükten sonra hangisinin seçildiği, seçimin sonuca göre yapıldığı
şüphesini doğurur. Ölçüt önce yazılır.

## Ölçüt

    p = (son 5 turdaki iyileşme) / (1. turdan itibaren TOPLAM iyileşme)

    p < 0,02   -> PLATO. 40 tur yeterlidir; karşılaştırma geçerlidir.
    p >= 0,02  -> HÂLÂ İLERLİYOR. Tur sayısı ve sabır ARTIRILIR
                  (tur 40 -> 80, sabır 8 -> 12) ve tek koşu YENİDEN zamanlanır.

%2 eşiği şu gerekçeyle: son 5 tur, 40 turun %12,5'idir. Kalan iniş, toplam
inişin %2'sinin altındaysa, tur sayısını iki katına çıkarmak beklenen kazancı
toplamın ~%4'ünün altında bırakır — bileşimler arası farkların ölçüleceği
mertebenin altında.

## Erken durdurma TETİKLENİRSE

Güvenlik ağının çalıştığı **ilk kez gösterilmiş** olur (kural 9 — ağın doğum
kanıtı). Bu, hem yakınsama kanıtıdır hem de "hiç tetiklenmeyen koruma,
tetiklenemeyen korumadan ayırt edilmemiştir" ilkesinin bu koşuda kapandığı
anlamına gelir.

## Her durumda raporlanır

    erken durdurma tetiklendi mi / hangi turda
    p oranı (yukarıdaki ölçüt)
    en iyi tur = son tur mu

## Zeyilname 3 eki — UZAY KÜÇÜLTÜLECEKSE NASIL (sonuç görülmeden)

İlan "tahmin tutmuyorsa arama uzayı küçültülür" diyordu ama **hangi eksenin
düşeceğini** söylemiyordu. Seçim sonuca bakılarak yapılırsa, düşen eksen
"istenmeyen sonucu veren eksen" olabilir. Kural şimdi yazılır.

**Düşecek eksen: `learning_rate`. Sabitlenecek değer: 1e-3.**

Gerekçe — soruya bağlı, sonuca değil:

> H2 şunu soruyor: *tetiklenmeyi ifade edebilen bir model sınıfı, o boşluğu
> dolduruyor mu?* Bu bir **temsil kapasitesi** sorusudur. `gizli` ve `katman`
> kapasiteyi belirler; `learning_rate` yalnızca o kapasiteye **ne kadar
> hızlı** ulaşıldığını belirler ve tur sayısıyla telafi edilebilir.

Yani öğrenme oranı, sorulan sorunun cevabını değiştirmesi beklenen eksen
değildir. Kapasite eksenleri korunur.

    KÜÇÜLTÜLMÜŞ UZAY:  gizli (32·64) x katman (2·3) = 4 bileşim x 3 tohum
                       lr = 1e-3 SABİT · tur 80 · sabır 12

1e-3 seçimi de sonuca bağlı değildir: zamanlama koşusunun kullandığı değerdir
ve Adam için literatürün varsayılanıdır.

**Sıra:** önce yakınsama ölçütü uygulanır (p < 0,02 ise uzay HİÇ küçülmez,
40 turla 8 bileşim koşar). Küçültme yalnızca `p >= 0,02` çıkarsa devreye
girer.

**Raporlanacak:** uzay küçültüldüyse, hangi eksenin neden düştüğü ve
küçültmenin **sonuç görülmeden** kararlaştırıldığı (bu commit).

---

# ZEYİLNAME 4 — §7'deki KANARYA 3 CÜMLESİ YANLIŞTI (düzeltme)

## Yanlışlanan cümle

§7'de şöyle yazıyordu:

> *"3 DOLAYLI — **ilk kez anlamlı.** Ağaçlarda kanal yoktu (monoton dönüşüme
> duyarsızlık); nöral modelde ölçekleme gerçek bir kanaldır."*

**Bu cümle ölçümle yanlışlandı** (V29). Kanal nöral modelde de neredeyse
boştur.

## Ölçüm

Gerçek sızıntı: temiz 0,8542 → sızıntılı 0,8546, **fark +0,0003**.
Kasıtlı büyütme taraması:

| kayma (sd) | AUC | fark |
|---|---|---|
| 0,05 | 0,8547 | +0,0005 |
| 0,15 | 0,8564 | +0,0022 |
| 0,50 | 0,8602 | +0,0059 |
| **1,50** | **0,8581** | **+0,0038** |

**Etki tekdüze değil**: 1,5 sd, 0,5 sd'den az etki yaptı. Ölçülen şey sinyal
değil gürültüdür.

## Sebep — ve iki model sınıfının FARKLI sebepleri

Standartlaştırma farkı, girdilere **tüm satırlara aynı uygulanan afin bir
dönüşüm** olarak yansır. Nöral ağın ilk katmanı bunu soğurur; hipotez sınıfı
değişmez.

    ağaç : monoton dönüşüme DUYARSIZLIK  -> kanal boş
    nöral: afin dönüşümü SOĞURABİLME     -> kanal boş

Aynı sonuç, farklı mekanizma.

## Sonuç

**Kanarya 3 emekli edilir.** Tanımlandığı biçimiyle hiçbir model sınıfı için
anlamlı bir dedektör değildir. `canary_indirect` zaten `NotImplementedError`
veriyor; `_canary_indirect_neural` de aynı duruma alınır.

**Yerine ne konabilir — İLAN EDİLİR ama BU KOŞUDA KULLANILMAZ.** Gerçek bir
ölçekleme-tipi sızıntı, **satıra bağlı** ya da **afin olmayan** bir dönüşüm
gerektirir; örneğin tüm veriden hesaplanan nicelik (quantile) dönüşümü ya da
satır başına ileri istatistikle normalleştirme. Bu, kanaryanın **tanımını**
değiştirir; sonuç görüldükten sonra yeni dedektör tanımlamak ölçütü sonuca
göre seçmek olurdu. Gelecekteki bir kurulumda, koşudan önce ilan edilerek
kullanılır.

## V26 düzeltmesi — YERİNDE, ve koşuluyla

Sızıntı gerçekti ve düzeltildi. Bu veri setinde zararsız olmasının sebebi
ölçüldü: **dağılım bölümler arasında durağan** (ortalama kayma 0,0125 sd;
`lat_c`, `lon_c`, `poisson_rate` için tam sıfır).

> **Durağanlık bir varsayımdır, garanti değildir.** Katalog genişlediğinde,
> Mc değiştiğinde ya da bölümler farklı sismik rejimlere düştüğünde aynı
> sızıntı zararlı olur. Bugün boş olan kanal, yarın dolu olabilir.

Koruma bu eksende **yapısaldır** (`Yigin.olcek_satirlari` + `olcek_kapsami`
beyanı) ve dedektöre bağlı değildir.

---

# KOŞU ÖNCESİ KONTROL LİSTESİ — KAPANDI (25 Ağu 2026)

    [x] tests/test_npp_ornekleme.py    3 test; ağırlık kaldırılınca >5 kat
                                       yanlılık GÖRÜNÜYOR (korumanın reddi)
    [x] tests/test_npp_determinizm.py  3 test; aynı tohum -> birebir aynı NLL
    [x] kanarya 1 KABA                 AUC 1,0000  alarm VAR
    [x] kanarya 2 ZAMANSAL             taban 3-5 gün (doğrulama x nöral)
    [x] kanarya 3 DOLAYLI              EMEKLİ -- sonda bilgisiz (V29)
    [x] kanarya 3 saptama tabanı       ölçüldü: YOK; 1,5 sd bile tekdüze değil
    [x] tek koşu zamanlandı            p=0,0344 -> uzay küçüldü (ilan gereği)
    [x] küme eşitliği                  436.800 kesişim, 252 pozitifin tamamı
    [x] ilan paketi commit'li          36701dc + 4 zeyilname

## Küme eşitliği — ölçüm kaydı

    1. DİZİN HİZASI    satır sayısı · cell_id · ref_date -> ÜÇÜ DE BİREBİR
                       (varsayılmadı, ölçüldü)
    2. İLERİ BAKIŞ     test döneminden 2000 satır örneği ->
                       referans SONRASI olay içeren satır: 0
    3. KÜME EŞİTLİĞİ   NPP 437.008 · ETAS 436.800 · kesişim 436.800
                       yalnız NPP 208 (hücre 4037, SIFIR pozitif)
                       yalnız ETAS 0 · KÜMELER EŞİT: HAYIR
                       252 pozitifin TAMAMI kesişimde

Fark, Faz 3'tekiyle **birebir aynıdır**. Bunun bir yan kazancı var:

> NPP ile LightGBM **aynı 436.800 satırda** değerlendiriliyor. Dolayısıyla
> NPP↔ETAS ve LGBM↔ETAS karşılaştırmaları **birbiriyle de** kıyaslanabilir;
> üçlü karşılaştırma aynı zemindedir.

## Ana koşu

    4 bileşim (gizli 32·64 x katman 2·3) x 3 tohum x 80 tur
    lr = 1e-3 sabit · sabır 12 · yığın 16384 · weight_decay 1e-5
    tahmini süre ~9 saat · her koşu anında jsonl'a yazılır

---

# AŞAMA 1'İN ÜÇ ÇIKTISI — teşhis protokolü, sonuç görülmeden

Determinizm zinciri sınanırken "tuttu / tutmadı" ikili mantığı yetersizdir
(V29 dersi). Üç çıktı ve her birinin teşhis adresi:

| çıktı | anlam | sonraki adım |
|---|---|---|
| üçü de birebir | beyan üretim koşullarına genişledi | test'e geçilir |
| üçü de farklı | **sistematik** kırılma: makine/kütüphane düzeyinde değişken | kütüphane sürümü, iş parçacığı, BLAS arka ucu karşılaştırılır |
| **bazıları tutuyor** | kırılma **tohuma bağlı** | aşağıdaki protokol |

## Üçüncü durumun mekanizması

En iyi tur, doğrulama NLL'lerinin **argmin**'idir. İki tur birbirine çok
yakınsa, makine epsilonu mertebesinde bir fark **seçilen turu** değiştirir ve
NLL o zaman belirgin biçimde sapar.

> Kırılan şey **hesap** değil, **seçimin eşiğe yakınlığıdır.** Aynı hesap,
> kararsız bir argmin'den geçince kaotikleşir. Determinizm zincirinin en zayıf
> halkası toplama sırası değil, "hangi tur en iyi" karşılaştırmasının
> keskinliği olabilir.

Bu koşuda üç koşunun en iyi turları 76 · 79 · 76 idi — yani en iyi tur,
sonun yakınında ve komşu turlarla farkı küçük olabilir.

## Teşhis protokolü (gerçekleşirse)

    1. tutmayan tohumun tur-bazlı NLL geçmişi basılır
    2. en iyi tur ile komşu adayların farkı ölçülür
    3. fark makine epsilonu mertebesindeyse teşhis "EŞİĞE-YAKIN SEÇİM"
       olarak kapanır
    4. çare: beraberlik kuralı -- eşit-yakın turlardan DETERMİNİSTİK seçim
       (örn. daha ERKEN olan). Bu, bir sonraki ilan paketine yazılır;
       bu koşuda uygulanmaz.

## BİLİNEN EKSİK — şimdi beyan edilir

`npp_arama.jsonl` yalnızca `val_nll` ve `en_iyi_tur` sakladı; **tur-bazlı
geçmiş (`gecmis`) kaydedilmedi.** Dolayısıyla üçüncü durum gerçekleşirse
**arama koşusunun** tur-bazlı NLL'leri elde yoktur; yalnızca yeni koşunun
geçmişi incelenebilir.

Teşhis bu yüzden **tek taraflı** olur: yeni koşuda argmin'in eşiğe yakın olup
olmadığı görülür, ama arama koşusunda da öyle olup olmadığı görülemez.

**Düzeltme (gelecek kurulumlara):** arama günlüğü `gecmis` listesini de
saklar. Maliyeti ihmal edilebilir (80 kayan nokta), getirisi bu teşhisin
iki taraflı yapılabilmesidir.

Eksik, gerçekleşmeden önce yazılmıştır — sonradan "elimizde yoktu" demek
yerine.
