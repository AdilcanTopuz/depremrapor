# Manşet taslağı — YAPI ONAYI İÇİN, SAYILAR BOŞ

Bu dosya README §3.6'nın yerine geçecek bölümün iskeletidir. Sayılar haftalık
kurulum bitince doldurulacak. Amaç, sonuçlar geldiğinde "hangi sayı nereye"
tartışması yaşanmamasıdır.

Doldurma kuralı: `<...>` işaretli her yer bir ölçümle dolar. Ölçüm yoksa satır
SİLİNMEZ, "ölçülmedi" yazılır. Boş bırakılan bir satır, sonradan sessizce
atlanmış bir iddiaya dönüşür.

---

## 1. Aylık CSEP değerlendirmesi (ETAS vs Poisson)

**Kurulum kimliği:** `<kurulum-id>`
**Dönem:** 2021-01-01 – 2023-12-31, 36 aylık başlangıç, 30 günlük pencere, M≥5,0
**Gözlenen:** 102 olay

### T-testi — projenin çıtası

    yol                        bilgi kazancı        %95 güven aralığı
    simülasyon (n_sim=1000)        <IG_sim>          [<lo>, <hi>]
    simülasyon + analitik taban    <IG_taban>        [<lo>, <hi>]
    ANALİTİK (taban gereksiz)      <IG_an>           [<lo>, <hi>]

Üç yolun da aynı sonucu vermesi, aylık kurulumun Monte Carlo çözünürlük
sorunundan muaf olduğunu gösterir. (Günlük kurulumda taban sonucu belirliyordu;
bu yüzden o kurulum bırakıldı — bkz.
`results/archive/2026-08-24_daily_setup/NEDEN.md`.)

**Ö2 çapraz doğrulaması** önceden ilan edilmiş eşikle: |ΔIG| < 0,05 nat, güven
aralıkları örtüşmeli, N ve S testleri aynı kararı vermeli
(bkz. docs/KABUL_OLCUTLERI.md). Kanıt gücü sınırı: bu, iki yöntemin BİRBİRİYLE
tutarlı olduğunun kanıtıdır, doğruluğunun değil — iki yol aynı
`_calculation_at` durumunu, aynı parametreleri ve aynı kataloğu paylaşır.

### S-testi (mekânsal) — GEÇİYOR

    model     gözlenen olabilirlik   simülasyon ortanca   z        kuantil  sonuç
    ETAS            <..>                   <..>          <..>      <..>    uyumlu
    Poisson         <..>                   <..>          <..>      <..>    RED

Uç kuantiller dejenere değildir; z değerleri testin iki ucu da ayırt ettiğini
gösterir.

**Yan bulgu:** ETAS'ın z'si pozitif ve büyük — olaylar, modelin kendi
simülasyonlarının ürettiğinden daha yüksek oranlı hücrelere düşüyor. Tek yönlü
testi geçer ama modelin mekânsal dağılımının gereğinden dağınık olduğunu, yani
keskinleştirilebileceğini söyler.

### N-testi (olay sayısı) — BAŞARISIZ, ve sebebi ölçüldü

    kurulum                  gözlenen   ETAS beklenen   oran     sonuç
    tüm 36 pencere              <..>        <..>        <..>     RED
    Şubat 2023 hariç (35)       <..>        <..>        <..>     uyumlu

102 olayın <..>'i tek pencerede (6 Şubat 2023 M7,8 dizisi). O pencere
çıkarıldığında sayı kalibrasyonu kabul bandının içindedir; eksik tahmin
**yapısal değildir**.

> **Aylık güncelleme sıklığı, dizi başlangıçlarını yapısal olarak ıskalar;
> operasyonel sistem günlük güncellenecektir ve bu değerlendirme o sistemin alt
> sınırıdır.**

---

## 2. Kazanç nereden geliyor? — dizi içi / dışı ayrıştırması

**Kurulum kimliği:** `haftalik-analitik` (haftalık, örtüşmeyen 7 günlük pencere,
ANALİTİK hesap — simülasyon yok)
**Değerlendirilen ürün: 7 GÜNLÜK TAHMİN.** 1 günlük panel için ayrı bir başarı
iddiası ileri sürülmez; o pencere bu kurulumda ölçülmemektedir.

    dizi penceresi   n(içi)  IG(içi)   n(dışı)  IG(dışı)   %95 GA          sonuç
    30 gün            <..>    <..>      <..>     <..>     [<..>, <..>]    <..>
    90 gün            <..>    <..>      <..>     <..>     [<..>, <..>]    <..>
    365 gün           <..>    <..>      <..>     <..>     [<..>, <..>]    <..>

Sonuç sütunu yalnızca üç değerden birini alır ve aralığa göre belirlenir:
**"ETAS daha iyi"** (GA tamamen sıfırın üstünde), **"Poisson daha iyi"** (GA
tamamen altında), **"fark gösterilemedi"** (GA sıfırı içeriyor).

> "Fark gösterilemedi" ile "model daha kötü" AYNI ŞEY DEĞİLDİR. Dizi dışında
> olay sayısı düştüğü için aralıklar genişler; nokta tahmininin işaretine
> bakarak sonuç yazılmaz.

**KAPSAM — bu cümle güven aralığı içeren HER tablonun altında yer alır:**

> Güven aralıkları yalnızca gözlenen olay sayısından gelen belirsizliği kapsar.
> ETAS parametre belirsizliğini ve model yanlış-belirlemesini kapsamaz. Model
> oranları deterministiktir (analitik hesap), dolayısıyla oranlarda örnekleme
> gürültüsü yoktur; ama parametrelerin kendisi bir kalibrasyondan gelir ve o
> belirsizlik buraya girmez. Parametre belirsizliğinin eklenmesi (kalibrasyon
> Hessian'ı ya da profil olabilirlik) Faz 3 sonrasına ertelenmiştir.

### Zaman ve mekânda yığılma

    yıl        olay   ortalama kazanç   toplam payı
    <..>       <..>       <..>            <..>

    en yüksek 10 gün: toplam olay teriminin %<..>'i
    ETAS'ın kaybettiği gün oranı: %<..>

---

## 3. Bölgesel zayıflıklar ve hibrit plan

    bölge                                   olay   ortalama   %95 GA         sonuç
    Doğu Anadolu (Maraş-Malatya)            <..>     <..>    [<..>, <..>]   <..>
    Kuzey Anadolu batı (Marmara)            <..>     <..>    [<..>, <..>]   <..>
    Batı Anadolu (Ege grabenleri)           <..>     <..>    [<..>, <..>]   <..>
    Kuzey Anadolu doğu                      <..>     <..>    [<..>, <..>]   <..>
    Ege denizi / Yunanistan                 <..>     <..>    [<..>, <..>]   <..>

**Ürün sonucu (gizlenmeyecek):** ETAS'ın üstünlüğünün gösterilemediği
bölgelerde, o bölgede büyük bir deprem olmadığı sürece ETAS tabanlı tahmin
zamandan bağımsız modelden daha iyi değildir. Arayüz bunu bölge bazında
göstermek zorundadır.

**Hibrit plan:** bölgeye göre model seçimi değil, bölgeye göre AĞIRLIK.
Tetikleme sinyali güçlüyken (yakın geçmişte büyük olay) ETAS, sakin dönemde
zamandan bağımsız model ağırlık kazanır. Ağırlık, veriye bakılarak değil
tetikleme durumundan türetilir — aksi hâlde bölge bazlı aşırı uydurma olur.
Bu bileşim ancak kendi CSEP T-testinden geçerse ürüne girer.

---

## 3b. Sayısal yöntem: ne doğrulandı, ne doğrulanmadı

    doğrulanan                                        nasıl
    analitik ile simülasyon aynı TOPLAM beklenti      Ö1 (36 başlangıç), Ö2 (CSEP)
    kütle korunumu (dallanma oranı)                   %0,0001 fark
    zaman/yarıçap yakınsaması                          ölçüldü, eşikler karşılandı
    determinizm                                        bit düzeyinde, testle sabit

    DOĞRULANMAYAN                                     durum
    hücre düzeyi mekânsal dağılımın doğruluğu         Ö3a, Ö3c KALDI
    kalan hücre farkının kaynağı                       açıklanmadı

> **Toplam-düzeyi tutarlılık testleri hücre-düzeyi kusurlara karşı kördür.**
> Kütleyi koruyan her hata onlardan geçer -- nitekim kaynak konumu kusuru Ö1,
> Ö2, kütle ve yakınsama testlerinin hepsinden geçti ve yalnızca hücre bazlı
> korelasyonda göründü. "Ö2 geçti" ifadesi "her şey doğrulandı" diye
> okunmamalıdır. Ayrıntı: docs/MEKANIZMA_BULGUSU.md §6.

Hücre düzeyi kıyas yansız dille raporlanır: iki yöntem hücre düzeyinde <r>
korelasyonla uyumludur; kalan fark açıklanmamıştır.

## 4. Yeniden üretilebilirlik künyesi

Her sayı bloğunun altında bulunur; künyesiz sayı yayımlanmaz.

    kurulum kimliği   : <ad>
    ETAS parametreleri: sha256 <hash>
    dallanma / b      : <..> / <..>
    tahmin çıktısı    : <dosya> sha256 <hash>
    simülasyon tohumu : başlangıç tarihinden türetilir (deterministik)
    üreten commit     : <git sha>
    üretim tarihi     : <tarih>

Tohumlama düzeltmesinden ÖNCE üretilmiş çıktılar bu künyeyi taşıyamaz ve
manşette kullanılmaz; arşivdedirler.
