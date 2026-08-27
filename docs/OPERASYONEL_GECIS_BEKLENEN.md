# 4. iş: operasyonel üretimin analitiğe geçişi — BEKLENEN ETKİ

Kural 8: beklenen etki değişiklikten ÖNCE yazılır, sonra gerçekleşen ölçülür,
sapma açıklanır.

## Ne değişiyor

`src/operational/forecast_now.py` şu an ETAS SİMÜLASYONU çalıştırıyor
(`ETASSimulation` + `simulate_to_df`, varsayılan n_sim=2000). Analitik dallanma
hesabına geçirilecek.

## Beklenen etki

### 1. Toplam beklenen olay sayısı
Ö1'de ölçülmüştü: 36 başlangıçta sim/analitik oranının ortancası **1,0119**,
aralık [0,812; 1,120], log(oran) t-testi p = 0,63 (sistematik sapma yok).

**Beklenen:** aynı gün için iki yöntemin toplamı **Monte Carlo varyansı
mertebesinde** farklı olacak — tipik olarak %10 içinde, sistematik bir yön
olmadan.

### 2. Hücre bazlı
Ö1'de hücre korelasyonu ortancası **0,936**. Kalan fark gürültü tavanıyla
açıklandı (analitik yöntem tavanın %98,2'sinde).

**Beklenen:** hücre sıralaması büyük ölçüde aynı; "en yüksek 10 hücre"
listesinde birkaç sıra değişimi olabilir, üst sıralarda değişim beklenmez.

### 3. Sıfır oranlı hücre
Simülasyon 500 denemede hücrelerin çoğunda sıfır veriyor (ölçüldü: pozitif
hücrelerin %65,9'u 1/n_sim eşiğinin altında). Analitik hesapta sıfır YOK
(ölçüldü: 1.064.960 satırda 0 sıfır).

**Beklenen:** yayımlanan GeoJSON'da hücre sayısı ARTACAK — simülasyonun
göremediği düşük oranlı hücreler artık görünür olacak. Bugünkü canlı tahminde
191 hücre vardı; analitik hesapta binlerce olması beklenir.

**Bu bir ürün kararı doğurur:** binlerce hücreyi haritada göstermek anlamsız.
Yayımlanan dosyaya bir alt eşik konmalı (örneğin normalin 2 katı ya da mutlak
olasılık eşiği) ve eşik AÇIKÇA yazılmalı.

### 4. Maliyet
Simülasyon (n_sim=2000, 7 gün): ölçülmedi ama n_sim=500'de ~2,5 dk.
Analitik: `local_params` (~2 dk) + dallanma (~18 sn).

**Beklenen:** benzer ya da daha hızlı.

### 5. Tekrarlanabilirlik
**Beklenen:** simülasyonda tohum protokolü gerekiyordu; analitikte rastgelelik
yok, aynı girdi bit düzeyinde aynı çıktı.

## Ölçülecekler

* aynı gün, aynı başlangıç: iki yöntemin toplamı ve oranı
* hücre bazlı korelasyon
* hücre sayısı (eşiksiz)
* en yüksek 10 hücrenin sıralaması
* çalışma süresi
* iki kez çalıştırma: analitik çıktı birebir aynı mı

## Otomasyon sorusu (ayrıca sınanacak)

Operasyonel üretim cron'la çalışacaksa künye "çalışma ağacı" alanı ne diyecek?
Otomatik üretim temiz ağaçtan mı çalışıyor? Değilse künye "KİRLİ — güvenilmez"
damgası basar ve her yayımlanan tahmin güvenilmez görünür.

**Beklenen:** cron temiz ağaçtan çalışır (git deposu değişmez), damga "temiz"
olur. Ama bu SINANMADAN kabul edilmez (kural 9).


---

# GERÇEKLEŞEN ETKİ (2026-08-24, aynı gün yan yana)

    #  ölçüt                      beklenen              gerçekleşen        sonuç
    1  toplam oranı (sim/an)      MC varyansı içinde    0,9452             TUTTU
    2  hücre korelasyonu          ~0,936                0,7353             SAPMA
    3  sıfır oranlı hücre         0                     0                  TUTTU
       hücre sayısı               artacak               180 -> 2560        TUTTU
    4  maliyet                    benzer ya da daha az  263 sn -> 127 sn   TUTTU
    5  tekrarlanabilirlik         bit düzeyinde aynı    FARKLI             SAPMA

## SAPMA 1 — hücre korelasyonu 0,7353 (beklenen ~0,936)

**Açıklama:** 0,936 değeri Ö1'in 36 aylık başlangıç üzerindeki ORTANCASIYDI ve o
küme aktif dönemleri de içeriyordu. Bu karşılaştırma tek bir SAKİN günde ve
n_sim=500 ile yapıldı (Ö1'de n_sim=1000). Sakin başlangıçlarda Ö1 zaten daha
düşük değerler vermişti (örn. 2022-04-01: 0,7642).

Gürültü tavanı hesabı da bunu doğrular: düşük oranlı hücrelerde simülasyonun
çözünürlüğü yetersizdir ve korelasyon mekanik olarak sınırlanır. Beklentiyi
"ortanca" yerine "tek sakin gün" için yazmak hataydı; kusur tahminde.

En yüksek 10 hücrenin 6'sı ortak -- üst sıralarda değişim beklenmiyordu, oldu.
Bu da aynı sebeple: sakin günde tepe hücreler arası fark küçük ve simülasyon
gürültüsü sıralamayı karıştırıyor.

## SAPMA 2 — tekrarlanabilirlik: BEYAN EKSİKMİŞ

İki çalıştırma farklı çıktı verdi. Kaynak ikiye ayrılarak bulundu:

    expected_counts, AYNI parametrelerle : birebir aynı ✓
    local_params, iki çağrı              : log10_mu FARKLI
        -6.54154000821231 vs -6.5415908942714065  (oranlarda bağıl 1,2e-04)

Rastgelelik dallanma hesabında değil, ETAS **durumunu kuran** adımdaydı.
Künyedeki "rastgelelik YOK" beyanı bu düzeltme olmadan EKSİKTİ.

**Düzeltildi:** `local_params` artık `deterministic_simulation` bağlamında
çalışıyor, tohum aynı kuraldan (başlangıç tarihinden) geliyor. Doğrulandı:
log10_mu birebir aynı, uçtan uca çıktı birebir aynı. Yeni test:
`test_local_params_is_deterministic`. Vaka: V16.

## Ürün kararı — alt eşik

Beklendiği gibi hücre sayısı 180'den 2560'a çıktı (ızgaranın tamamı). Binlerce
hücreyi haritada göstermek yanıltıcı olur: arka plan düzeyindeki hücreler
"tahmin" gibi görünür.

`to_geojson` artık `min_times_normal` eşiği alıyor (varsayılan 2,0) ve çıktıya
şunları yazıyor: eşiğin kendisi, eşik öncesi hücre sayısı, yayımlanan hücre
sayısı. **Eşik gizlenmiyor.**
