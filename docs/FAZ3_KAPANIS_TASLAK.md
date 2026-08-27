# FAZ 3 KAPANIŞ — İKİ DAL, SONUÇ GÖRÜLMEDEN YAZILDI

**Bu belge NPP koşusu sürerken yazılmıştır** (commit tarihi kanıttır).
Sonuç geldiğinde ilgili dal **olduğu gibi** kullanılır; cümleler sonuca göre
ayarlanmaz. Boş bırakılan yerler yalnızca sayılardır.

Faz 3'ün sorusu tekti:

> **Tetiklenme, veriden öğrenilebilir mi?**

İki model sınıfından cevap arandı: tablosal GBM (LightGBM) ve toplamsal nöral
nokta süreci (NPP). LightGBM'in cevabı ölçüldü ve kayıtlı
(`docs/FAZ3_SONUC.md`): **hayır** — arka planı biraz daha iyi kuruyor,
tetiklenmeyi hiç öğrenmiyor (`n30` SHAP payı %1,7; dizi penceresinde 19,8'e
karşı gözlenen 59; kalibrasyon 1,82).

---

## DAL X — NPP tetiklenmeyi ÖĞRENDİYSE

**Tetikleyen koşullar (ikisi birden):** H2 geçer — dizi penceresi beklentisi
19,8'i belirgin aşar VE kalibrasyon oranı [0,80; 1,25] bandına girer.

### Faz 3'ün ortak cevabı

> **Tetiklenme veriden öğrenilebilir, ama model sınıfı buna izin vermelidir.**
> Tablosal GBM, geçmişi özet istatistiklere (n30, n90, …) sıkıştırdığı için
> tetiklenmeyi ifade edemedi. Olay-düzeyinde toplamsal yapı (λ = μ + Σ g)
> verildiğinde aynı veriden öğrenilebildi.

Bu, "veri yetersiz" ile "temsil yetersiz" arasındaki ayrımın **ölçülmüş**
cevabıdır: aynı katalog, aynı bölümleme, aynı 436.800 satır, aynı 252 olay —
değişen tek şey model sınıfı.

### README §3.5

NPP'nin ETAS'ı **geçip geçmediğine** göre iki alt durum:

* **NPP ETAS'ı GEÇTİYSE** (GA tümüyle sıfırın üstünde): §3.5 ölçütü
  **KARŞILANDI**. Bu, projenin ilk "başarı" beyanıdır ve künyesiyle birlikte
  yazılır — tek kurulum, tek pencere (7 gün), tek büyüklük eşiği (M≥4,5),
  tek test dönemi.
* **NPP EŞDEĞER ÇIKTIYSA** (Ö5 bandı içinde): §3.5 **KARŞILANMADI**, ama
  bulgu LightGBM'inkinden farklıdır: eşdeğerlik bu kez **tetiklenmeyi
  öğrenerek** elde edilmiştir, eksik tahminin ödülüyle değil. Ayrıntı IG
  ayrıştırmasında görünür (olay terimi ile maruziyet terimi ayrı).

### Site şartnamesi

Ürün kapısı ([0,80; 1,25]) H2'nin parçasıdır; H2 geçtiyse **kapı da
geçilmiştir.** Bu durumda:

    operasyonel katman  ETAS (birincil) + NPP (ikincil/karşılaştırma)
    yayımlanan sayı     ETAS kalır -- NPP'nin operasyonel katmana ALINMASI
                        ayrı bir karardır ve ayrı ölçütler gerektirir
                        (kararlılık, güncelleme maliyeti, açıklanabilirlik)

**Neden ETAS birincil kalır.** Bir modelin araştırma ölçütünü geçmesi, onu
üretime sokmak için yeterli değildir. NPP'nin operasyonel adayı olması için
en az şunlar gerekir: (a) haftalık yeniden eğitim maliyeti ölçülmüş, (b)
tahminin neden değiştiği açıklanabilir, (c) katalog gecikmesine dayanıklılığı
sınanmış. Hiçbiri Faz 3'ün kapsamında değildir.

---

## DAL Y — NPP tetiklenmeyi ÖĞRENEMEDİYSE

**Tetikleyen koşul:** H2 kalır — dizi penceresi beklentisi arka plana yakın
kalır ya da kalibrasyon bandın dışında.

### Faz 3'ün ortak cevabı

> **İki farklı model sınıfı, aynı veriden tetiklenmeyi öğrenemedi.** Sorun
> tek bir mimarinin kısıtı değil; **veri veya kurulum** düzeyindedir.

Bu, DAL X'ten daha güçlü bir ifadedir ve dikkatle yazılmalıdır. Elenen
açıklamalar (hepsi ölçülmüş):

    "yeterince aranmadı"     -> LightGBM'de 36 bileşimin tamamı, NPP'de
                                kapasite eksenleri korunarak 4 bileşim;
                                uzayın üstü düz
    "girdi kırpılmış"        -> K=256, R=200 km; ETAS kütlesinin %5 diliminde
                                bile %97,9'u içeride (ölçüldü)
    "temsil edemiyor"        -> NPP, ETAS'ı ÖZEL DURUM olarak içeriyor
                                (λ = μ + Σ g, öğrenilen çekirdek)
    "kalibrasyon dışlanmış"  -> Poisson NLL, kalibrasyon kaybın İÇİNDE

Geriye kalan adaylar — ve hiçbiri Faz 3'te sınanmadı:

1. **Örneklem yetersizliği.** 753 eğitim pozitifi, bir tetiklenme çekirdeğini
   serbest biçimde öğrenmek için az olabilir. ETAS'ın avantajı, çekirdeğin
   **biçimini varsayıp** yalnızca birkaç parametre kestirmesidir.
2. **Zaman çözünürlüğü.** Haftalık pencere, Omori azalımının en bilgili
   kısmını (ilk saatler-günler) tek bir kutuya sıkıştırıyor olabilir.
3. **Katalog tamlığı.** Mc=3,3 altındaki olaylar tetiklenmenin büyük kısmını
   taşır ve katalogda yoktur.

### İkinci adayın keskinleştirilmiş hâli — Faz 4'ün en verimli sorusu

Zaman çözünürlüğü adayı, "öğrenilemedi" ile karıştırılmaması gereken bir
ayrım taşıyor:

    "tetiklenme ÖĞRENİLEMEDİ"
        vs
    "tetiklenmenin YAŞANDIĞI ÖLÇEK GÖSTERİLMEDİ"

Omori azalımının en dik kısmı **ilk saatler ve günlerdedir**; haftalık kutu
onu tek bir sayıya sıkıştırır. Hedef "önümüzdeki 7 günde olay var mı?" olduğu
sürece, tetiklenmenin en bilgili kısmı **ölçülen büyüklüğün içinde
kaybolur** — model onu öğrense bile hedef onu göstermez.

Bu, DAL Y gerçekleşirse **Faz 4'ün ilk sorusudur** ve önceden ilan edilerek
sınanır:

    aynı model sınıfı, GÜNLÜK pencerede (1 gün, M>=4,5) sınanır
    H2'nin karşılığı: dizi penceresinde günlük beklenti, ETAS'ınkine yaklaşıyor mu

Günlük pencere pozitif sayısını düşürür (753 -> daha az) ve birinci adayla
(örneklem yetersizliği) **çakışır**; bu yüzden iki aday ayrı ayrı değil,
birlikte tasarlanmış bir deneyle ayrılmalıdır. O deney Faz 3'ün kapsamında
DEĞİLDİR ve burada yalnızca kaydedilir.

### README §3.5

**KARŞILANMADI** — ve bu kez iki model sınıfından. §3.5'in hükmü şöyle
kesinleşir:

> Bu kurulumda hiçbir ML yaklaşımı ETAS'ı geçmedi. ETAS, ürünün tahmin
> motoru olarak kalır. Bu bir başarısızlık değil, **ölçülmüş bir sınırdır**:
> fizik-temelli modelin varsaydığı çekirdek biçimi, bu veri hacminde
> öğrenilebilir olandan daha fazla bilgi taşıyor.

### Site şartnamesi

    operasyonel katman  ETAS (birincil) + uzun vadeli Poisson (ikincil)
    ML                  araştırma kolunda kalır; ürüne GİRMEZ
    metodoloji sayfası  "ML denendi ve ETAS'ı geçmedi" AÇIKÇA yazılır,
                        sayılarıyla ve künyesiyle

**Metodoloji sayfasına yazılacak cümle:** *"İki makine öğrenmesi yaklaşımı
(gradyan artırmalı ağaçlar ve nöral nokta süreci) aynı veride ETAS'a karşı
sınandı; ikisi de geçemedi. Sonuçlar ve ölçüm koşulları
`docs/FAZ3_SONUC.md` ve `docs/NPP_SONUC.md` içindedir."*

Bu cümle, "yapay zekâ kullanıyoruz" iddiasının yerine geçer — ve daha
dürüsttür.

---

## KAPSAM KİLİDİ — her iki dalda da geçerli

Hüküm ne olursa olsun, **şu künyeyle** kayıtlıdır ve genişletilmez:

    7 günlük pencere · M >= 4,5 hedefi · haftalık kurulum
    test dönemi 2021-01-01 .. 2024-12-20 · 436.800 hücre-pencere · 252 olay
    iki model sınıfı: tablosal GBM ve toplamsal nöral nokta süreci

**Yasak genelleme.** DAL Y gerçekleşirse şu cümleye genişletilemez:

    YANLIŞ:  "Makine öğrenmesi deprem tahmininde işe yaramıyor."
    YANLIŞ:  "Tetiklenme veriden öğrenilemez."
    DOĞRU :  "Bu hedef tanımında (7 gün, M>=4,5) ve bu veri hacminde, iki
              model sınıfı da ETAS'ı geçemedi."

Cazibe büyük olacak: birinci başlık ikincisinden çok daha çekici ve çok daha
yanlıştır. V16'nın (beyan, kanıtın kapsamını aşamaz) hüküm katmanındaki son
uygulaması budur.

**Neden özellikle bu kurulumda kritik.** Yukarıda kaydedilen ayrım —
"tetiklenme öğrenilemedi" ile "tetiklenmenin yaşandığı ölçek gösterilmedi" —
mevcut ölçümlerle **ayırt edilmiyor.** Ayırt edilmemiş iki açıklamadan
birini seçip başlığa taşımak, ölçümün söylemediğini söylemektir.

### Faz 4'ün sorusu: deney değil, DENEY TASARIMI

Çözünürlük ve örneklem adayları **aynı yönde** hareket eder (pencere
daraldıkça pozitif sayısı düşer), dolayısıyla tek kollu bir deney ikisini
ayıramaz. Gereken, çapraz bir tasarımdır:

    pencere SABİT · örneklem BÜYÜR   (katalog genişletme, Mc indirme)
    örneklem SABİT · pencere DARALIR (aynı pozitif sayısıyla günlük hedef)

İki kolun sonuçları ancak birlikte okunduğunda hangi adayın bağlayıcı olduğu
görülür. Bu, Faz 3'ün kapsamında **değildir** ve burada yalnızca kaydedilir.

---

## HER İKİ DALDA DA YAZILACAKLAR

* **Ürün kapısı sonucu** (gözlenen/beklenen oranı), bandın içinde mi dışında
  mı — model kazansa da kaybetse de.
* **Güvenlik ağı raporu**: erken durdurma her koşuda tetiklendi mi, hangi
  turda; tetiklenmediyse gerekçesi.
* **Eksiklik göstergelerinin payı** — "eksikliğin kendisi ne kadar bilgi
  taşıyor" sorusunun ilk ölçülü cevabı (tarif, hüküm değil).
* **NPP ↔ LightGBM karşılaştırması**: aynı 436.800 satırda değerlendirildiler,
  dolayısıyla doğrudan kıyaslanabilirler.
* **Kanarya künyeleri**: hangi dedektör hangi tabanla kurulu, hangisi emekli.

---

## BU BELGENİN KENDİSİ HAKKINDA

İki dalın da sonuç görülmeden yazılması, "hangi cevap gelirse gelsin ne
diyeceğiz" sorusunu koşudan önce kapatır. Sonuç geldiğinde yapılacak iş
**okumaktır, yorumlamak değil.**

Yazılmayan tek şey sayılardır. Cümleler yerinde duruyor.
