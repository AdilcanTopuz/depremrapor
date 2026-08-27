# Mekanizma bulgusu: kaynak konumu yaklaşıklığı

**Tarih:** 24 Ağustos 2026
**Etki:** hücre düzeyinde ortanca %20, en yüksek oranlı hücrelerde %70'e varan
sapma. Toplamda görünmez (%0,3).

## 1. Kusurun tanımı

Kusur hücre içi integralde DEĞİLDİ. Her hücre baştan beri 20 noktalı
Gauss-Legendre ile entegre ediliyordu (mertebe ayrıca yakınsama ölçülerek
seçilmişti: 5 nokta kütleyi %3,7 şişiriyordu, 20 nokta 1,00000'a yakınsıyor).

Kusur **integralin merkezindeydi**. Uzaysal çekirdeği bir evrişime indirgemek ve
tabloları (büyüklük kutusu × enlem satırı) başına önbelleklemek için, her kaynak
olayı **kendi hücresinin merkezine** oturtuluyordu. Yani:

    gerçek kaynak : 37,18°K 37,04°D  (hücrenin kenarına yakın)
    kullanılan    : 37,125°K 37,125°D (hücre merkezi)

Etkilenen çekirdek, tetikleme çekirdeğinin uzaysal bileşeni:

    f(r²; m) = 1 / (r² + D)^(1+rho),   D = d · exp(gamma·(m − mc))

Bu çekirdeğin ölçeği sqrt(D) ≈ 11,4 km (m = mc için). Hücre boyutu 0,25° ≈ 25 km.
**Yaklaşıklık hücre boyutundan küçük değil, onunla karşılaştırılabilir** — bu
yüzden ihmal edilebilir değildi.

## 2. Hatanın hangi hücrelerde büyüdüğü

Öngörü doğru çıktı: hata, kaynağa yakın ve yoğunluğun hücre içinde hızla
değiştiği hücrelerde en büyük. Ölçüm (2023-03-01, Kahramanmaraş dizisi sürerken):

    hücre     merkez ile    gerçek konumla    değişim
     8047      0,179210        0,302588        +68,8%
     8048      0,167251        0,290430        +73,6%
    12047      0,241324        0,153855        −36,2%
    12049      0,250098        0,336559        +34,6%
    10048      0,214905        0,128715        −40,1%
     9048      0,528525        0,440725        −16,6%

Değişim iki yönlüdür: kaynağı kendi hücresinin merkezine çekmek, kütleyi o
hücreye ve simetrik komşularına yığar; gerçek konum kütleyi kaynağın bulunduğu
tarafa kaydırır. Kaybeden ve kazanan hücreler birbirini dengeler.

Katmanlara göre ortanca bağıl değişim:

    hücre oranı >= 0,01    ( 81 hücre): %20,6   (en büyük %121,6)
    hücre oranı >= 0,001   (234 hücre): %20,5   (en büyük %701)
    hücre oranı >= 0,0001  (850 hücre): %19,2   (en büyük %1171)

**Toplamda fark yalnızca %0,3.** Kusur bu yüzden toplam kıyaslarında (Ö1)
görünmüyordu ve yalnızca hücre bazlı korelasyonda ortaya çıktı.

## 3. Düzeltme

Alt-ızgara entegrasyonu değil (o zaten vardı): **integrasyon merkezinin
düzeltilmesi**. Yakın alan (5×5 hücre), kaynağın gerçek koordinatına göre
yeniden hesaplanır:

    cy = (di + u − fy)·dy_km,   cx = (dj + v − fx)·dx_km

burada (fy, fx) kaynağın hücre içindeki kesirli konumudur. Uzak alanda
hücre-merkezi yaklaşıklığı korunur: orada mesafe hücre boyutundan çok büyüktür
ve kaydırma etkisizdir. Bu, önbelleklemenin kazancını korurken hatayı kaldırır.

Kod: `src/models/etas_branching.exact_near_field`. Eski davranış
`USE_EXACT_POSITION = False` ile yeniden üretilebilir (yalnızca ölçüm için).

### Sayısal etki

    toplam beklenen oran : 7,84774 -> 7,82460   (%−0,295, kütle korunuyor)
    hücre düzeyi         : ortanca %20 değişim
    maliyet              : 12 -> 18 sn / başlangıç
    simülasyonla korelasyon (8 başlangıç): HEPSİNDE arttı, ortanca +0,0218

## 4. Ö1 ne zaman geçti?

**Ö1 önce düzeltilmemiş kodla koşuldu ve geçti; bu damga geçersizdi.** Güncel
kodla yeniden koşuldu ve yine geçti:

    ölçüt              düzeltme öncesi    düzeltme sonrası    eşik
    ortanca oran        1,0085 ✓           1,0119 ✓          1,00 ± 0,03
    log(oran) t-testi   p = 0,2495 ✓       p = 0,6305 ✓      p > 0,05
    aralık              [0,802; 1,109]     [0,812; 1,120]    %90'ı [0,80; 1,25]
    hücre korelasyonu   0,905              0,9358            (ölçüt değil)

Toplam ölçütleri kusurdan neredeyse etkilenmedi (beklendiği gibi); değişen,
ölçüt olmayan hücre korelasyonu oldu.

## 5. Ders

Kusur, analitik hesap **taban** olarak kullanılırken belgelenmiş ve "zararsız"
sayılmıştı — çünkü taban yalnızca simülasyonun sıfır verdiği düşük oranlı
hücrelerde bağlayıcıydı. Hesap **tahminin kendisi** hâline geldiği anda aynı
yaklaşıklık doğrudan sonuca girdi.

Bir yaklaşıklığın zararsızlığı, kullanıldığı BAĞLAMA bağlıdır; bağlam değişince
yeniden değerlendirilmelidir. Bu, kodda yorum olarak da işaretlenmiştir.

## 6. DOĞRULAMA HİYERARŞİSİ DERSİ

Bu bulgunun en önemli sonucu kusurun kendisi değil, **nasıl gizlendiğidir.**

Hücre bazında ortanca %20, uçta %121 sapma yaratan bir hata, toplamda yalnızca
%0,3 fark üretti. Sebebi yapısaldır: kusur kütleyi KORUYORDU, yalnızca yanlış
dağıtıyordu.

**Toplam-düzeyi tutarlılık testleri, hücre-düzeyi kusurlara karşı KÖRDÜR.**
Kütleyi koruyan her hata bu testlerden geçer. Bu, aşağıdakilerin hepsi için
geçerlidir:

* Ö1 (analitik/simülasyon toplam oranı) — geçti, kusur oradaydı
* Ö2 (aylık CSEP çapraz doğrulaması) — geçti, kusur oradaydı
* Kütle korunumu testi — geçti, kusur oradaydı
* Yakınsama testleri — geçti, kusur oradaydı

Kusuru yalnızca hücre bazlı korelasyon gösterdi ve o bile bir ölçüt değil, yan
gözlemdi.

**Ö2 geçtiğinde "her şey doğrulandı" diye okunmamalıdır.** Ö2'nin gösterdiği
şey, iki yöntemin aynı TOPLAM beklentiyi ürettiğidir. Mekânsal dağılımın doğru
olduğunu göstermez; ortak bir hata ikisinde birden yaşayabilir (zaten iki yol
aynı `_calculation_at` durumunu, aynı parametreleri ve aynı kataloğu paylaşır).

Mekânsal doğruluğun tek gerçek sınavı gözlenen olaylara karşı puanlamadır:
CSEP S-testi ve arşiv puanlamasındaki hücre sırası. Bunlar model doğruluğunu
sınar, sayısal yöntem doğruluğunu değil -- ve ikisi ayrı sorulardır.

## 7. AÇIK KALEM: ikinci mekanizma

Düzeltme sonrası Ö3a ve Ö3c belirgin biçimde iyileşti (Ö3a ">10" katmanı
0,819 -> 0,952; Ö3c phi oranı 6,80 -> 3,62). Bu, bulunan kusurun gerçek ve
ilgili olduğunun BAĞIMSIZ teyididir ve raporda düzeltmenin doğrulaması olarak
kullanılır.

Ama ikisi de eşiklere ulaşmadı. Bu, **ikinci ve muhtemelen daha küçük bir
mekanizmanın hâlâ açıkta olduğu** anlamına gelir.

Karar: bu kalem KAYITLIDIR ve haftalık üretimi bloke etmez. Gerekçe: geri
çekilen iddia ("hücre düzeyinde ayrışan taraf simülasyondur") artık hiçbir
sonuca dayanak değildir ve hücre düzeyi kıyas raporda yansız dille yer alır:

> İki yöntem hücre düzeyinde 0,94 korelasyonla uyumludur; kalan fark
> açıklanmamıştır.

**Koşul:** ileride hücre-bazlı bir belirsizlik modeli kurulursa (örneğin hücre
başına güven aralığı), bu kalem oraya girmeden ÇÖZÜLMEK ZORUNDADIR. phi oranı
3,62 hâlâ büyüktür ve aşırı-dağılım parametresinin kararsızlığı doğrudan o
modele siner.


## 8. BELİRSİZLİĞİN BÜYÜMESİ ÜZERİNE (metodoloji)

Bu denetim boyunca belirsizlik sürekli BÜYÜDÜ: güven aralıkları genişledi,
iddialar geri çekildi, MDE beyanları eklendi, "kanıtlandı" diyen cümleler
"gösterilemedi" ile değiştirildi.

**Her büyüme, gerçeğe bir yaklaşmaydı.**

Somut örnek: Marmara bölgesi için günlük kurulum −1,367 gibi keskin bir değer
veriyordu. O sayı 35 olaydan geliyordu ama örtüşen pencereler yüzünden aynı
deprem ardışık yedi pencerede bağımsız gözlem gibi sayılıyordu. Haftalık
örtüşmeyen kurulumda aynı bölge daha az ama gerçekten bağımsız olayla ölçülür
ve aralık genişler.

Sonucun daha az kesin görünmesi bir GERİLEME DEĞİL, önceki kesinliğin sahte
olduğunun ortaya çıkmasıdır.

Okuyucunun bunu bir zaaf değil, denetimin ÜRÜNÜ olarak okuması gerekir. Bir
modelin ne kadar bildiğini abartmak, bilmediğini itiraf etmekten çok daha
tehlikelidir -- özellikle çıktısı kamuya deprem olasılığı olarak sunulacak bir
sistemde.


## 9. KAPANIŞ: gürültü ve anlatı

Bu denetimde "ETAS ile Poisson ayrıştırılamıyor" anlatısı İKİ KEZ kurulmaya
çalışıldı. İkisinde de suçlu modelin kendisi değil, ölçüm aracıydı.

* **Birinci deneme (V9).** Blok bootstrap haftalık kurulumda 202 başlangıcı 7
  bloğa düşürüyordu. Geniş aralık çıkacaktı ve "az bağımsız bilgi" diye
  yorumlanacaktı -- beklentiyle uyuştuğu için ikinci kez bakılmayacaktı.
* **İkinci deneme (V14).** Günlük kurulumda AUC farkı +0,0545 [-0,038; +0,127]
  ile anlamsızdı. Sebep, pozitif hücrelerin 799/1496'sında simülasyon oranının
  sıfır olmasıydı. Analitik kurulumda aynı fark +0,1407 [+0,076; +0,214].

**Gürültü yalnızca belirsizlik eklemez: işaret üretir ve işareti yok da eder.**
Birincisinde sahte bir "fark yok" üretecekti, ikincisinde gerçek bir farkı yok
ediyordu.

Bu yüzden bir "fark gösterilemedi" sonucu, ÖLÇÜM ARACININ ÇÖZÜNÜRLÜĞÜ
sorgulanmadan kabul edilemez. MDE kuralı -- "fark gösterilemedi" asla tek başına
raporlanmaz, yanında asgari saptanabilir etki durur -- bu dersin
kurumsallaşmış hâlidir.
