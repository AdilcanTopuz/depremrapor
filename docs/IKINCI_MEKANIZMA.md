# 3. iş: Ö3a/Ö3c'nin açık kalan ikinci mekanizması

**ZAMAN SINIRI:** iki oturumluk keşif turu. Mekanizma adayı çıkmazsa
**"açık, sınırı ölçülü"** etiketiyle kapatılır ve Faz 3'e taşınır. "Bulunamadı"
meşru bir kapanıştır; "aranmaya devam" değildir.

## Bilinen kısıt

Kaynak konumu düzeltmesinden sonra:

    Ö3a ">10" katmanı : 0,819 -> 0,952   (eşik 0,95; kıl payı geçti)
    Ö3a "1-10" katmanı: 0,649 -> 0,697   (eşik 0,85; KALDI)
    Ö3c log-log eğim  : -0,409 -> -0,476 (eşik -0,5±0,1; geçti)
    Ö3c phi oranı     : 6,80 -> 3,62     (eşik <3; KALDI)

İkisi de belirgin iyileşti ama eşiğe ulaşmadı. Yani **ikinci mekanizma
birinciden küçük** ve muhtemelen aynı aileden: "toplamı korur, hücreyi kaydırır".

## Üç aday (sırayla ele alınacak)

### A. Uzak-alan önbelleğinin çözünürlüğü
Yakın alan (5x5) kaynağın gerçek konumuna göre hesaplanıyor; UZAK alan hâlâ
hücre merkezine oturtulmuş önbellekli tablodan geliyor. Uzakta kaydırmanın
etkisiz olduğu varsayıldı ama ÖLÇÜLMEDİ. Ayrıca tablolar (büyüklük kutusu x
enlem satırı) başına önbellekli; enlem çözünürlüğü satır düzeyinde.

**Sınama:** NEAR yarıçapını 2 -> 4, 6 yapıp korelasyonun artıp artmadığına bak.
Artıyorsa mekanizma budur ve yarıçap ölçülerek seçilmelidir.

### B. Zaman ayrıklaştırmasının olay-yakını davranışı
Geometrik zaman kutuları c = 9,8 saniyeden başlıyor. Çok yeni bir olayın
(pencerenin ilk saatlerinde) tetiklemesi ilk kutulara sıkışıyor olabilir.

**Sınama:** n_bins 32 -> 128 ve t0'ı küçültüp hücre korelasyonuna bak. Toplam
yakınsamıştı (%0,5) ama HÜCRE düzeyinde yakınsama ayrıca ölçülmedi.

### C. Zamansal kümelenme (pencere sınırları) -- EN UMUT VERİCİ
Ö3c'nin phi'si hücre içi varyans ölçüsüdür. Kalan aşırı dağılım MEKÂNSAL değil
ZAMANSAL kümelenmeden geliyorsa -- aynı hücrede ardışık pencereler arası
korelasyon -- aradığımız şey hücre geometrisinde değil PENCERE SINIRLARINDA
olur.

**Sınama:** aynı hücrenin ardışık pencerelerindeki (sim - analitik) artıklarının
otokorelasyonu. Sıfırdan farklıysa mekanizma zamansaldır ve mekânsal aday
aramak boşunadır.

## Kural

İlk POZİTİF izde derinleş; negatif çıkan adayı kapat ve kaydet. Üç aday da
negatifse zaman sınırı dolmadan "açık, sınırı ölçülü" etiketi konur.

---

## ADAY A — KAPANDI (negatif)

Yakın-alan yarıçapı (NEAR) 2, 3, 4, 6 ile denendi; hücre bazlı korelasyon:

    başlangıç    NEAR=2  NEAR=3  NEAR=4  NEAR=6
    2021-01-01   0,9465  0,9465  0,9465  0,9465
    2022-01-01   0,9471  0,9472  0,9472  0,9472
    2023-02-01   0,9837  0,9837  0,9837  0,9837
    2023-11-01   0,9591  0,9590  0,9590  0,9590

Değişim en fazla 0,0001 ve işareti tutarsız (bazı başlangıçlarda hafif DÜŞÜYOR).

**Sonuç: uzak-alan önbelleğinin hücre-merkezi yaklaşıklığı ikinci mekanizma
DEĞİLDİR.** Yakın alanın 5x5 seçilmesi yeterliydi; kaydırmanın uzakta etkisiz
olduğu varsayımı ölçülerek doğrulandı.

Yan kazanç: bu, `NEAR = 2` seçiminin de gerekçesini ölçüye bağlar. Daha büyük
yarıçap hesap maliyetini artırır ve hiçbir şey kazandırmaz.

## ADAY B — KAPANDI (negatif)

Zaman kutusu sayısı 16, 32, 64, 128 ile denendi; hücre bazlı korelasyon:

    başlangıç        16      32      64     128
    2021-01-01   0,9465  0,9465  0,9465  0,9466
    2022-01-01   0,9471  0,9471  0,9472  0,9472
    2023-02-01   0,9837  0,9837  0,9837  0,9837
    2023-11-01   0,9591  0,9591  0,9591  0,9591

Dört ondalıkta değişim yok. **Zaman ayrıklaştırması ikinci mekanizma DEĞİLDİR**
ve hücre düzeyi yakınsama da (toplam gibi) 32 kutuda sağlanmış durumda.

## ADAY C — SINANAMADI (veri uygun değil) + ölçülen kısmı negatif

Eldeki artıklar AYLIK başlangıçlardan geliyor: ardışık başlangıçlar arasında
23 günlük boşluk var, yani hipotezin tarif ettiği BİTİŞİK pencereler değil.
Ölçülen gecikme-1 otokorelasyon her katmanda ihmal edilebilir ve işareti
tutarsız:

    analitik >= 1e-04: 22013 çift | r = +0,0251 | karıştırılmış -0,0082
    analitik >= 1e-03:  3036 çift | r = +0,0113 | karıştırılmış -0,0170
    analitik >= 1e-02:   397 çift | r = -0,0289 | karıştırılmış -0,0170

Bitişik pencere korelasyonu, haftalık kurulumda simülasyon çalıştırılmadığı için
sınanamaz. **Bu bir sınırdır ve kaydedilmiştir.**

---

# SONUÇ: İKİNCİ MEKANİZMA YOK — SORU YANLIŞ KURULMUŞ

Üç aday da negatif çıktıktan sonra ölçütlerin KENDİSİ incelendi ve iki
başarısızlığın da açıklaması bulundu.

## Ö3c'nin başarısızlığı: referans dejenere

φ kararsızlığı **tamamen en düşük λ kutusundan** geliyor:

    lambda      n     saçılma    phi    sim=0 oranı
    0,064   68650      2,943   0,558      96,9%
    0,155   14140      3,606   2,019      80,5%
    0,500    5753      1,851   1,713      57,2%
    1,600    2185      0,981   1,540      22,6%
    4,899     893      0,524   1,347       2,0%
   16,417     336      0,307   1,550       0,0%
   58,898     198      0,147   1,279       0,0%

    phi oranı, tüm kutular      : 3,62  (eşik <3, KALDI)
    phi oranı, ilk kutu HARİÇ   : 1,58

İlk kutuda simülasyon hücrelerin **%96,9'unda sıfır** veriyor; artık orada TAM
OLARAK -1 (nokta kütlesi) artı seyrek ağır kuyruk. Standart sapma böyle bir
dağılım için anlamlı bir saçılma ölçüsü değildir.

**Yani Ö3c, düşük λ'da analitik yöntemin hatasını değil, REFERANSIN
DEJENERELİĞİNİ ölçüyor** -- ve o dejenerelik, simülasyonu terk etmemizin
gerekçesiydi.

## Ö3a'nın başarısızlığı: eşik ULAŞILAMAZ

Simülasyon gürültüsü, gözlenebilecek korelasyona bir TAVAN koyar. Ölçülen aşırı
dağılımla (φ) hesaplandı:

    katman      n      phi   gözlenen r   TAVAN    eşik    ulaşılabilir mi
    > 10      539     1,31      0,9892   0,9892   0,95        EVET
    1 - 10   3078     1,37      0,6961   0,7086   0,85        HAYIR
    < 1     88543     1,30      0,4106   0,3185    —      (formül geçersiz)

* ">10" katmanında analitik yöntem **tavanda**: 0,9892 / 0,9892.
* "1-10" katmanında tavan **0,7086**, eşik ise 0,85 istiyordu. **Analitik
  yöntem ne kadar iyi olursa olsun o eşik geçilemezdi.** Gözlenen değer tavanın
  %98,2'sine ulaşıyor.
* "<1" katmanında zayıflama formülü geçerli değil (sıfırda nokta kütlesi);
  gözlenen tavanı aşıyor, o katman için sayı verilmez.

## Karar

**Ölçütler KALDI olarak kalır.** Ö3a ve Ö3c geriye dönük geçirilmez; eşik
sonuca bakarak değiştirilmez. Değişen şey ölçütlerin sonucu değil,
BAŞARISIZLIKLARININ AÇIKLAMASIDIR:

> Analitik yöntem, simülasyon gürültüsünün izin verdiği korelasyon tavanındadır.
> Ö3a'nın "1-10" eşiği o tavanın üstündeydi; Ö3c ise düşük λ'da referansın
> dejenereliğini ölçüyor. **İkinci bir mekanizmaya dair kanıt yoktur.**

Bu, "bulunamadı" değil "soru yanlış kurulmuştu" kapanışıdır ve zaman sınırı
dolmadan varılmıştır.

## Açık kalan (küçük)

Bitişik pencere korelasyonu (Aday C'nin asıl hâli) sınanmadı; haftalık kurulumda
simülasyon yok. Bunun için ~20 ardışık haftalık başlangıçta simülasyon
çalıştırmak gerekir (~50 dk). Şu an gerekçesi zayıf: A ve B negatif, Ö3a/Ö3c'nin
başarısızlıkları açıklandı ve ikinci mekanizma için pozitif iz kalmadı.
