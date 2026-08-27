# Neden bu kurulum bırakıldı?

**Tarih:** 24 Ağustos 2026
**Bırakılan kurulum:** günlük başlangıçlı, örtüşen 7 günlük pencereler,
başlangıç başına 500 simülasyon (1096 başlangıç, 2022-2024).

## Kök neden: Monte Carlo çözünürlüğü

Simülasyondan kestirilen hücre oranı, `1/n_sim` çözünürlüğünün altında sıfır
görünür. Ölçüldü: **pozitif hücrelerin %53'ünde (799/1496) oran sıfır çıkıyor.**
Log-olabilirlik sıfırda tanımsız olduğu için bir "taban" koymak zorunlu hâle
geldi — ve sonuç tabanın seçimine bağlı kaldı:

    taban                                  bilgi kazancı
    yok                                       -8.927
    ETAS arka plan düzeyine ölçeklenmiş        +0.678
    ayrıştırma ana şok oranı (şişik)           +1.071

Üç seçim üç farklı sonuç veriyor. Bu, ölçümün modelin değil TABANIN başarısını
ölçtüğü anlamına gelir ve kabul edilemez.

## Ne değişti

1. **Analitik taban.** Alt sınır artık ETAS'ın koşullu yoğunluğunun hücre x
   pencere integralinden hesaplanıyor (birincil kuşak: arka plan + geçmişin
   doğrudan tetiklemesi). İkincil kuşaklar yalnızca eklediği için bu kesin alt
   sınırdır ve modelin kendi parametrelerinden çıkar. Bkz.
   `src/models/etas_analytic.py`.
2. **Örtüşmeyen haftalık pencereler.** Günlük başlangıçlı 7 günlük pencereler
   birbirini örtüyordu; bağımsızlık varsayımı bozuluyor ve blok bootstrap
   zorunlu hâle geliyordu. Haftalık örtüşmeyen başlangıçlarda bu sorun yok.
3. **Simülasyon sayısı 500 -> 5000.** Çözünürlük 10 kat; taban çok daha az
   bağlayıcı.

## Kapsam değişikliği (kayıt için)

Yeni kurulumda değerlendirilen ürün **7 günlük tahmindir**. 1 günlük panel için
ayrı bir başarı iddiası ileri sürülmeyecektir; o pencere bu kurulumda
ölçülmüyor.

## Yeniden üretilebilirlik uyarısı

Buradaki çıktılar, simülasyon tohumlaması düzeltilmeden ÖNCE üretildi
(`etas` paketi argümansız `np.random.seed()` çağırıp dışarıdan verilen tohumu
siliyordu). Dolayısıyla bu dosyalar birebir yeniden üretilemez. `manifest.json`
parametreleri, dosya SHA-256 özetlerini ve git commit'ini içerir.

## Taban düzeltmesinin ara adımı (kayıt için)

Operasyonel arşiv puanlaması önce **0,68x** (ETAS çok tahmin ediyor) raporlandı,
sonra **0,94x**'e döndü. Aynı arşiv, aynı dönem (2025-08 – 2026-08), aynı eşik
(M>=4,5), aynı 52 tahmin dosyası; gözlenen 46 hiç değişmedi. Değişen tek şey
tabandı.

**0,68x bir ölçüm değil, taban hatasının çıktısıydı.**

    taban                              beklenen   gözlenen/beklenen
    artçı dahil oran (yanlış)            67,5           0,68x
    arka plan oranı                      49,1           0,94x
    analitik alt sınır (nihai)            -              -

## CSEP T-testi: eski ve yeni kalibrasyon yan yana

STAI-dayanıklı yeniden kalibrasyonun CSEP sonucunu bozmadığının kaydı:

    kalibrasyon                       bilgi kazancı   %95 GA
    eski (23 Ağu 02:41, STAI öncesi)     +2,287      [+1,999, +2,575]
    yeni (24 Ağu, mc="positive")         +2,399      [+2,110, +2,689]
    yeni + analitik taban                +2,378      [+2,090, +2,667]

Aralıklar geniş biçimde örtüşüyor. Yeniden kalibrasyon parametreleri değiştirdi
(dallanma 0,839 -> 0,821, b 1,157 -> 1,274) ama ETAS'ın Poisson karşısındaki
üstünlüğünü değiştirmedi.

## N-testi başarısızlığının kaynağı ölçüldü

    kurulum                  gözlenen   ETAS beklenen    oran    sonuç
    tüm 36 pencere              102          40,4       2,53x    RED
    Şubat 2023 hariç (35)        45          39,6       1,14x    uyumlu

102 olayın 57'si tek pencerede. Eksik tahmin YAPISAL DEĞİLDİR; tamamı, aylık
güncellemeli bir sistemin ay ortasında başlayan diziyi ıskalamasından gelir.

**Aylık güncelleme sıklığı, dizi başlangıçlarını yapısal olarak ıskalar;
operasyonel sistem günlük güncellenecektir ve bu değerlendirme o sistemin alt
sınırıdır.**
