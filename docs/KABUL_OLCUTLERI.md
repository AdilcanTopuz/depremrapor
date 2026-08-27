# Kabul ölçütleri — SONUÇLARDAN ÖNCE ilan edilir

Bu dosyanın amacı tek bir riski ortadan kaldırmaktır: "yeterince yakın" kararını
sonuca bakarak esnetmek. Bu projede jeofizik katmanlar tam bu yüzden reddedildi
(tohum saçılımı ölçütü sonradan seçilseydi "katkı var" denecekti); aynı disiplin
sayısal yöntem doğrulamasında da geçerlidir.

Kural: bir ölçüt karşılanmazsa sonuç "yakın sayılır" diye yazılmaz. Ya kaynak
bulunur ya da sapma açıkça raporlanır.

---

## Ö1 — Analitik yöntem ile simülasyonun tutarlılığı (pencere başına)

Karşılaştırma: aynı başlangıçlarda toplam beklenen olay sayısı oranı
`simülasyon / analitik`.

| ölçüt | eşik |
|---|---|
| ortanca oran | 1,00 ± 0,03 |
| sistematik yön | log(oran) için tek örneklem t-testi p > 0,05 |
| aykırı değer | oranların en az %90'ı [0,80, 1,25] içinde |

Saçılmanın kendisi bir kusur DEĞİLDİR: simülasyon sonlu sayıda denemeden
kestirir ve dallanma süreci aşırı dağılımlıdır (over-dispersed), dolayısıyla
%10 mertebesinde saçılma beklenir. Sınanan şey ORTALAMANIN kayması ve
sapmanın YÖNÜDÜR.

**Dürüstlük notu:** bu ölçüt yazılırken 36 başlangıcın 16'sının tek tek oranları
görülmüştü (özet istatistikler değil). Dolayısıyla Ö1 için "önceden ilan" tam
anlamıyla geçerli değildir. Ö2 ve Ö3 için geçerlidir.

## Ö2 — Aylık CSEP çapraz doğrulaması

Aynı 36 aylık başlangıç, 30 günlük pencere, M≥5,0. Simülasyonla üretilmiş
tahminlerin verdiği T-testi bilgi kazancı: **+2,399 nat/olay, %95 GA
[+2,110, +2,689]**. Analitik yolla üretilen tahminler için:

| ölçüt | eşik |
|---|---|
| nokta tahmini farkı | \|ΔIG\| < 0,05 nat |
| güven aralıkları | örtüşmeli |
| N-testi sonucu | aynı karar (tüm pencerelerde RED, Şubat hariç uyumlu) |
| S-testi sonucu | aynı karar (ETAS uyumlu, Poisson RED) |

**Bu testin kanıt gücü sınırlıdır ve raporda öyle yazılacaktır.** İki yol aynı
`_calculation_at` durumunu, aynı parametreleri ve aynı kataloğu paylaşır; ortak
bir hata (parametre dönüşümü, katalog hazırlığı, Mc seçimi) ikisinde birden aynı
yönde yaşar ve bu karşılaştırma onu YAKALAYAMAZ. Doğru ifade:

> İki yöntemin birbiriyle tutarlı olduğunun ve aradaki farkın Monte Carlo
> gürültüsünden ibaret olduğunun kanıtıdır. DOĞRULUK iddiası buradan gelmez;
> doğruluk ancak gözlenen olaylara karşı puanlamadan (CSEP testlerinin kendisi,
> arşiv puanlaması) gelir.

Uyuşmazlık çıkarsa değeri şudur: elde simülasyondan bağımsız bir referans
bulunması teşhisi kolaylaştırır.

## Ö3 — "Ayrışan taraf simülasyon" iddiasının kanıtı

Hücre bazlı korelasyonun ~0,88'de kalması şu an bir HİPOTEZDİR. Rapora kanıt
olarak girmesi için iki testin de beklenen yönde çıkması gerekir:

**Ö3a — beklentiye göre katmanlama.** Hücreler, simülasyonun o hücrede beklediği
sentetik olay sayısına göre katmanlanır (n_sim × oran). Beklenti:

| katman (beklenen sentetik olay) | korelasyon eşiği |
|---|---|
| > 10 | r > 0,95 |
| 1 – 10 | r > 0,85 |
| < 1 | r < 0,80 (yani belirgin biçimde düşük) |

Korelasyon beklentiyle birlikte artmıyorsa gürültünün kaynağı simülasyon
değildir ve başka bir ayrışma aranmalıdır.

**Ö3b — 2x2 uzaysal toplama.** Komşu hücreler 2x2 toplanır; toplama simülasyon
gürültüsünü ortalar. Beklenti: korelasyon en az 0,04 artmalı.

İkisi de karşılanırsa "kusur değil, kanıt" ifadesi raporda kalır. Karşılanmazsa
hücre düzeyi ayrışmanın başka bir kaynağı vardır ve bu, OPERASYONEL GEÇİŞTEN
ÖNCE bulunmalıdır.

---

## Kayıt

Bu dosya, ilgili koşular tamamlanmadan commit edilmiştir. Sonuçlar
`docs/MANSET_TASLAK.md` doldurulurken bu ölçütlere atıfla raporlanır.

---

## Ö3a SONUCU: KALDI — ve ölçütün kendisi kusurluydu

Ölçülen (8 başlangıç, ortanca korelasyon):

    katman (beklenen sentetik olay)   hücre    r        eşik      sonuç
    > 10                                 32   0,8190   > 0,95    KALDI
    1 - 10                               81   0,6488   > 0,85    KALDI
    < 1                                2467   0,4145   < 0,80    geçti

Yön DOĞRU: korelasyon beklentiyle birlikte tekdüze artıyor (0,41 -> 0,65 ->
0,82). Ama ilan edilen eşiklere ulaşmıyor. Eşik sonradan değiştirilmez; Ö3a
KALDI olarak kayda geçer.

**Ölçütün kusuru:** katmanlama, katman içindeki gerçek oran çeşitliliğini
bastırır ve korelasyonu mekanik olarak düşürür (aralık daraltma / range
restriction). ">10" katmanında yalnızca ~32 hücre var ve hepsi benzer oranlı;
böyle bir küme için 0,95 beklemek istatistiksel olarak temelsizdi. Ölçüt
yazılırken bu gözden kaçtı.

## Ö3c — SONRADAN EKLENEN test (Ö3a kaldıktan sonra tanımlandı)

Bu testin sonradan eklendiği açıkça kaydedilir. Ö3a'nın yerini almaz; onun
başarısızlığını ortadan kaldırmaz. Amacı, aynı hipotezi aralık daraltmasından
etkilenmeyen ve KESKİN bir sayısal öngörü taşıyan bir ölçüyle sınamaktır.

**Öngörü.** Fark yalnızca simülasyonun sonlu-örneklem gürültüsündense, bir
hücrede beklenen sentetik olay sayısı `lambda = n_sim * oran` iken simülasyon
oranının bağıl saçılması

    sd[(sim - analitik) / analitik]  =  sqrt(phi / lambda)

biçiminde, yani `lambda^(-1/2)` ile ölçeklenmelidir. `phi` aşırı dağılım
(over-dispersion) çarpanıdır ve dallanma süreci nedeniyle 1'den büyüktür ama
lambda'dan BAĞIMSIZ olmalıdır.

**Ölçüt:** log-log eğimin -0,5'e yakınlığı.

| ölçüt | eşik |
|---|---|
| log(saçılma) ~ log(lambda) eğimi | -0,5 ± 0,1 |
| phi'nin katmanlar arası kararlılığı | en büyük/en küçük < 3 |

Eğim -0,5'ten belirgin sapıyorsa (örneğin -0,2), fark örnekleme gürültüsüyle
açıklanamaz ve sistematik bir mekânsal ayrışma vardır.

## Ö3c SONUCU: KALDI

    lambda_ort      n   saçılma    phi
        0,064   23377    3,2463   0,675
        0,156    4408    3,8068   2,253
        0,492    1795    2,0461   2,058
        1,597     699    0,9983   1,592
        4,898     283    0,6319   1,956
       16,378     103    0,3896   2,486
       50,751      55    0,3007   4,589

    log-log eğim : -0,4086   (eşik -0,5 ± 0,1)  -> geçti
    phi oranı    : 6,80      (eşik < 3)          -> KALDI

## KARAR: iddia geri çekiliyor

Ö3a ve Ö3c kaldı, Ö3b geçti. İki ön-ilanlı testin kalması karşısında **"hücre
düzeyinde ayrışan taraf simülasyondur" iddiası kanıtlanmamıştır ve rapordan
çıkarılır.**

Üçüncü bir istatistiksel ölçüt İCAT EDİLMEYECEKTİR. Biri geçene kadar test
denemek, bu projede jeofizik katmanlar için reddedilen örüntünün aynısıdır.

Bunun yerine somut bir MEKANİZMA şüphesi sınanır: analitik yöntem kaynak
olayları kendi HÜCRE MERKEZLERİNE yerleştiriyor (uzaysal çekirdeği evrişime
indirgemek için), simülasyon ise gerçek koordinata göre üretiyor. Hücre ~25 km,
çekirdek ölçeği sqrt(D) ~ 11 km; yaklaşıklık hücre boyutuyla karşılaştırılabilir
büyüklükte. Toplamı korur, hücre düzeyinde kütleyi farklı dağıtır.

Bu yaklaşıklık "taban" kullanımında zararsız diye belgelenmişti; analitik hesap
artık TAHMİNİN KENDİSİ olduğu için doğrudan sonuca girer.

**Mekanizma testi:** kaynaklar gerçek konumlarına yerleştirildiğinde simülasyonla
korelasyon yükseliyor mu? Yükseliyorsa yaklaşıklık düzeltilir. Yükselmiyorsa
ayrışmanın kaynağı hâlâ bilinmiyordur ve operasyonel geçiş YAPILMAZ.

---

# Ö4 — OKUMA ÇERÇEVESİ (sonuçlardan önce bağlanmıştır)

Sayı geldikten sonra yorum çerçevesi kurmak, bu projede baştan beri kaçınılan
şeydir. Aşağıdaki kurallar haftalık analitik kurulumun sonuçları GELMEDEN
yazılmıştır; sonuç hangi duruma düşerse o durumun yorumu devreye girer ve
raporda hangi kuralın işlediği açıkça işaretlenir.

## Ö4a — Dizi-dışı bilgi kazancı (kilit sonuç)

Kahramanmaraş dizisi penceresi çıkarıldığında kalan olaylar için tam bilgi
kazancı ve %95 güven aralığı:

| durum | yorum (önceden bağlanmış) | sonuç |
|---|---|---|
| GA tamamen sıfırın ÜSTÜNDE | "ETAS sakin dönemde de küçük ama gerçek kazanç sağlıyor" — manşete girer | — |
| GA sıfırı İÇERİYOR | "sakin dönemde fark gösterilemedi" — ne üstünlük ne kötülük iddia edilir; site tasarımında sakin dönem paneli uzun vadeli oranlara yaslanır | — |
| GA tamamen sıfırın ALTINDA | "sakin dönemde ETAS zamandan bağımsız modelden kötü" — hibrit/ensemble kararı (Marmara bulgusuyla birlikte) Faz 3 önceliğine yükselir | — |

**Önceki günlük kurulumdan gelen −0,281 / −0,380 değerleri GEÇERSİZDİR**
(bkz. docs/SAYI_HARITASI.md). Haftalık analitik kurulum bu soruya ilk kez
güvenilir cevap verecektir.

## Ö4b — Bölge tablosu

**Kural: her bölge satırı ARALIĞIYLA okunur. Aralıksız hiçbir bölgesel iddia
manşete çıkmaz.**

Marmara satırı için özel olarak:

| durum | nasıl yazılır |
|---|---|
| ortalama negatif VE aralık sıfırı dışlıyor | README "bilinen ZAYIFLIKLAR" bölümü doldurulur; arayüz bölge bazında uyarır |
| aralık sıfırı içeriyor | "zayıflık" DEĞİL, **"belirsizlik"** diye yazılır; veri bu bölgede karar vermeye yetmiyor |
| ortalama pozitif VE aralık sıfırı dışlıyor | zayıflık iddiası geri çekilir |

Aynı kural diğer bölgeler için de geçerlidir. "Ortalama negatif" tek başına
zayıflık kanıtı sayılmaz; bölge başına olay sayısı düşüktür ve aralıklar
geniştir.

## Ö4c — Kapsam beyanı zorunluluğu

Ö4a ve Ö4b tablolarının ikisi de, güven aralığı içerdikleri için, altlarında
kapsam beyanını taşımak zorundadır (kod düzeyinde zorunlu kılınmıştır:
`src/eval/gain_breakdown.KAPSAM_BEYANI`).

## Ö4d — DURUM 2 İÇİN EK KURAL: asgari saptanabilir etki (MDE)

"Aralık sıfırı içeriyor" tek başına yeterli bir rapor DEĞİLDİR. İki çok farklı
şeye işaret edebilir:

  (a) fark yok ya da ihmal edilebilir
  (b) veri, var olan bir farkı görecek GÜÇTE değil

Bunları ayırt etmeden yazılan "fark gösterilemedi", okuyucuyu (a)'ya iter.
Bu yüzden durum 2 gerçekleştiğinde **asgari saptanabilir etki** hesaplanır ve
aralıkla BİRLİKTE raporlanır:

    MDE = (z_0.975 + z_0.80) * SE = 2.80 * sd(olay terimleri) / sqrt(n)

yani mevcut olay sayısı ve varyansla %80 güçte saptanabilecek en küçük IG farkı.

Doğru okuma biçimi:

> dizi-dışı IG = +0,08, %95 GA [−0,15; +0,31]; bu kurulum ±0,25 nat'tan küçük
> farkları saptayamaz.

Böylece okuyucu "ETAS ile Poisson sakin dönemde eşdeğerdir" değil, **"0,25
nat'a kadar olası farklar bu veriyle dışlanamıyor"** diye anlar.

### Site tasarımına bağlanması

Güç yetmiyorsa sakin dönem paneli uzun vadeli (zamandan bağımsız) modele
yaslanır. Gerekçe basitlik ve kalibrasyon avantajıdır. Bu karar kayda
**"ETAS kötü" bulgusu olarak DEĞİL, "kanıt yetersiz, muhafazakâr seçim"**
olarak geçer. İkisi farklı cümlelerdir ve farklı sonuçlar doğurur: birincisi
modeli dışlar, ikincisi veri biriktikçe yeniden değerlendirilir.

### Bölge tablosu

Aynı kural bölge satırları için de geçerlidir. **Durum 2'ye düşen hiçbir bölge
satırı MDE'siz bırakılmaz** -- özellikle Marmara. "Belirsizlik" yazan bir satır,
belirsizliğin ne kadar büyük olduğunu da söylemek zorundadır.

---

# DONDURMA PROTOKOLÜ

Dondurma tek turda yapılır. Üç kontrol sırayla uygulanır; geçmeyen madde varsa
TEK listede toplu döner, parça parça düzeltme turu açılmaz.

1. **Ö4 işaretleri.** Her sonucun yanında hangi önceden bağlı kuralın devreye
   girdiği yazılı mı? İşaretlenen kural sayının kendisiyle tutarlı mı?
   (Çerçevenin amacı yorum tartışması değil, kural uygulamasıydı.)
2. **Çapraz tutarlılık.** Manşetteki her sayı, `docs/SAYI_HARITASI.md`'deki
   GEÇERLİ kurulum künyelerinden birine bağlanıyor mu? Künyesiz ya da
   geçersiz-rejim sayısı kalmış mı?
3. **Fazlalık taraması** (eksiklik değil). Manşette, dayanağı teslimde olmayan
   hiçbir iddia kalmamalı -- özellikle bölgesel cümleler ve site tasarım
   kararlarına dair ifadeler.

# DONDURMA SONRASI İŞLER (sıralı)

## 1. Izgara üst sınırının kapatılması (kök neden)

`cell_id` yarı-açık aralık kullanıyor; tam 43,0000 K / 45,0000 D'deki olaylar
ızgara dışına düşüyor. Bölge filtresi kapalı aralık olduğu için bu olaylar
filtreyi geçiyor. Etkisi bugün SIFIR (2 olay, ikisi de M<4,5 ve test dönemi
dışında) ve semptom ayıklamayla çözüldü.

Kök neden çözümü: üst sınırı kapat, tam sınır değerini son hücreye ata.
Beraberinde `baseline_poisson.csv` yeniden üretilmeli ve iki olayın doğru
hücreye girdiği doğrulanmalı. Dondurmaya dakikalar kala kanonik bir fonksiyonu
değiştirmemek için ertelendi.

**BİLİNEN ETKİ (şimdiden kaydedilir).** O commit'te koruyucu zaten tetiklenecek;
cevabı da şimdiden belli: `cell_id` değişimi `baseline_poisson.csv`'yi ve ondan
TÜREYEN HER SAYIYI etkiler — Poisson temel model oranları, karşılaştırma
tabanları, tüm bilgi kazancı değerleri. O commit'te sayı haritası "hangi sayılar
yeniden üretildi" listesiyle güncellenecektir.

Bilinen bir etkiyi önceden kaydetmek, dondurma sonrası ilk işin kendi denetimini
şimdiden hazırlar: iş yapıldığında "beklenen etki buydu, gerçekleşen etki bu"
karşılaştırması mümkün olur.

## 1b. Çıktı dosyalarının künye zinciri (KÜÇÜK, ama örüntü önemli)

cell_id düzeltmesinde bir boşluk göründü: kod ve parametreler mühürlü, ama sayı
üreten json çıktıları (`daily_backtest.json`, `gain_breakdown.json`,
`csep_results.json`) git tarafından izlenmiyor ve yeniden üretimde ÜZERİNE
yazılıyor. O seferde fark 5. ondalıktaydı ve önemsizdi; örüntü önemli --
bir sonraki değişiklikte fark 5. ondalıkta olmayabilir ve "önceki"yi kaybetmiş
oluruz.

Çözüm (iki seçenekten biri): çıktı json'ları git-izlemeli olsun, ya da her
yeniden üretimde eskisi zaman damgalı arşive kopyalansın. Künyedeki sha zaten
kimliğini taşıyor.

Bu, 4. maddedeki "yan yana arşiv" ilkesinin genelleştirilmiş hâlidir.

## 2. Denetim mirası belgesi

Ana kaynağı `docs/VAKA_DEFTERI.md` (14 vaka).

## 3. Ö3a/Ö3c'nin açık kalan ikinci mekanizması

Kaynak konumu düzeltmesi ikisini de belirgin iyileştirdi ama eşiklere
ulaşılamadı; ikinci ve muhtemelen daha küçük bir mekanizma açıkta.
Hücre-bazlı belirsizlik modeli kurulmadan ÖNCE çözülmeli.

## 4. Operasyonel üretimin analitiğe geçişi

Geçişte aynı gün için simülasyonlu ve analitik tahmin yan yana arşivlenir,
fark raporuyla. Yayımlanmış eski tahminlerle süreklilik denetlenebilir kalsın.

## 4b. GSRM lisans kısıtı (Faz 3 tasarımını etkiler)

GSRM v2.2 jeodezik gerinim verisi **CC-BY-NC-SA** lisanslıdır: TİCARİ KULLANIMA
KAPALI. Bu, "bilinen sınırlar" listesinde bir dipnot değil, tasarım kısıtıdır.

Site ticarileşecekse gerinim katmanı için iki seçenekten biri gerekir:

1. GSRM için lisans izni alınması — **TALEP GÖNDERİLDİ (24 Ağustos 2026)**,
   cevap bekleniyor (tipik 1-4 hafta). Cevap gelince üç yoldan hangisine
   girildiği `docs/SAYI_HARITASI.md`'ye işlenir. Ya da
2. Uygun lisanslı alternatif kaynak (akademik yayınlardan türetilmiş, yeniden
   dağıtılabilir gerinim haritası).

**FAZ 3 VARSAYILANI: (iii) — katman yalnızca araştırma kolunda.** İzin gelirse
varsayılan değişir; gelmezse ablasyon sonucu ne olursa olsun katman ürüne
girmez.

**Faz 3 tasarımı bu kısıtı BİLEREK yapılmalıdır.** Gerinim katmanı şu an
ablasyonda katkı vermiyor, dolayısıyla bugün bir kayıp değil; ama katkı verdiği
gösterilirse lisans sorunu ürünü bloke eder ve o noktada çözmek çok daha
pahalıdır.

## 5. Faz 3 — ML modelleri

Bu denetimde kurulan araçların TAMAMIYLA: koruyucu, sayı haritası, kapsam
beyanı, önceden bağlı yorum kuralları, MDE, kanarya testleri.

Bu denetim boyunca kalıcı altyapı üretildi ve şu an dağınık dosyalarda duruyor.
Faz 3'te ML modelleri AYNI disiplinle değerlendirilecek; araçların tek referans
noktasından taşınması gerekiyor.

`docs/DENETIM_MIRASI.md` içinde toplanacaklar:

* **Koruyucu + vaka defteri** — `scripts/check_number_map.py`, pre-commit hook,
  7 test; yakalama vakaları kaydı
* **Sayı haritası** — `docs/SAYI_HARITASI.md`, geçerli/geçersiz rejim ayrımı
* **Kapsam beyanı** — `gain_breakdown.KAPSAM_BEYANI`, koda gömülü zorunluluk
* **Ö4: önceden bağlı yorum kuralları** — sonuç gelmeden yorumu yazma disiplini
* **MDE kuralı** — "fark gösterilemedi" asla tek başına raporlanmaz;
  bootstrap SE + küçük-örneklem t düzeltmesi
* **Kanarya testleri** — paketin kendini yeniden tohumladığını sabitleyen test,
  t > z testi, koruyucunun kendisini sınayan testler
* **Doğrulama hiyerarşisi dersi** — toplam-düzeyi testler hücre-düzeyi
  kusurlara kördür (`docs/MEKANIZMA_BULGUSU.md` §6)
* **Kurulum arşivleme yordamı** — `results/archive/*/NEDEN.md` + manifest

Bu belge Faz 3'ün giriş kapısıdır: yeni bir model değerlendirmesi başlamadan
önce hangi araçların zorunlu olduğunu söyler.

---

# Ö5 — EŞDEĞERLİK ÖLÇÜTÜ (Faz 3, sonuçtan ÖNCE bağlanmıştır)

"Fark gösterilemedi"nin MDE'siz yazılamayacağını öğrendik. **"Eşdeğer" de
bantsız yazılamaz.** İkisi farklı iddialardır:

* *fark gösterilemedi* = veri karar vermeye yetmedi
* *eşdeğer* = fark VARSA bile şu bandın içindedir

İkincisi daha güçlü bir iddiadır ve daha fazla kanıt ister.

## Bir modelin ETAS'a "EŞDEĞER" sayılması için

Üç koşulun ÜÇÜ birden sağlanmalıdır:

1. **Nokta tahmini bandın içinde:** |IG_model − IG_ETAS| < MDE
2. **Aralık dar:** %95 GA genişliği < 2 × MDE
   (aksi hâlde aralık, "eşdeğer" demeye yetecek kadar dar değildir)
3. **Aralık bandı aşmıyor:** GA'nın her iki ucu da ±MDE içinde

**Yalnızca 1. koşul sağlanırsa "fark gösterilemedi" yazılır, "eşdeğer"
YAZILMAZ.** Aradaki fark, aralığın genişliğidir.

## Bant genişliği ilan edilir

Eşdeğerlik bandı = ölçülen MDE'dir; sonradan gevşetilmez. Raporlanan cümle
şu biçimi alır:

> Model X, ETAS'a bu kurulumda EŞDEĞERDİR: fark +0,0Z (%95 GA [a, b]),
> eşdeğerlik bandı ±MDE.

Band olmadan "eşdeğer" kelimesi kullanılmaz.

## MDE'nin YÖNÜ hakkında uyarı

Mevcut MDE'ler ETAS-Poisson karşılaştırmasından türetilir ve bir
**ÜST SINIRDIR**: benzer iki model (ETAS ile ML) arasındaki farkın varyansı,
farklı iki model arasındakinden KÜÇÜKTÜR (eşleşmiş karşılaştırmada ortak
bileşen sadeleşir).

Yani "bu MDE ile saptanamaz" sonucu, gerçek MDE ölçüldüğünde
YUMUŞAYABİLİR. Eşleşmiş varyans ancak iki model birden var olduğunda
ölçülebilir; o ölçüm yapıldığında MDE güncellenir ve cevaplanabilirlik
haritası yeniden çizilir.

Bu uyarı, "saptanamaz" sonucunu peşinen kesinleştirmemek içindir.
