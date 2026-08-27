# Operasyonel geçiş — yan yana arşiv ve fark raporu

**Tarih:** 24 Ağustos 2026 · **Başlangıç:** 2026-08-24 · 7 gün · M≥4,5 · eşik 2,0x

Bu dizin, operasyonel üretimin simülasyondan analitiğe geçtiği gün AYNI
başlangıç için iki yöntemin çıktısını yan yana saklar. Amaç: yayımlanmış eski
tahminlerle sürekliliğin denetlenebilir kalması.

    analitik.geojson       yeni yol (analitik dallanma)
    simulasyonlu.geojson   eski yol (n_sim=500), YALNIZCA karşılaştırma için

## Sayılar

    analitik   : 311 hücre yayımlandı (2560 eşik öncesi)
    simülasyon : 129 hücre yayımlandı ( 180 eşik öncesi)
    ortak      : 52    yalnız analitik: 259    yalnız simülasyon: 77

    ortak hücrelerde korelasyon : 0,7455
    toplam (ortak hücreler)     : analitik 0,1868 | simülasyon 0,2460

## Bulgu: yöntemler BÖLGEDE anlaşıyor, HÜCREDE anlaşmıyor

En yüksek "normalin kaç katı" değerine sahip hücreler listesi neredeyse tamamen
farklı. Ama hücre numaraları komşu görünüyordu; ölçüldü:

    analitik ilk 5            -> simülasyonun ilk 10'undaki en yakın hücre
    78    (35,12K 44,62D)     -> 78       0,0 km
    73    (35,12K 43,38D)     -> 2076    88,0 km
    1078  (35,38K 44,62D)     -> 1078     0,0 km
    12048 (38,12K 37,12D)     -> 11048   27,8 km
    12049 (38,12K 37,38D)     -> 12050   21,9 km

    karşılaştırma: rastgele iki hücre arası ortalama mesafe = 648 km

İki tam eşleşme (0 km), iki komşu hücre (~22-28 km = bir hücre), biri 88 km.
Ortanca ~22 km; rastgele beklenti 648 km.

**Yorum:** sakin bir günde, HANGİ HÜCRE sorusunun cevabı iki yöntem arasında
kararlı değil; HANGİ BÖLGE sorusunun cevabı kararlı. Bu beklenen bir sonuçtur --
sakin dönemde hücre oranları arka plan düzeyine yakındır ve simülasyonun 500
denemelik çözünürlüğü hücreler arasını ayırt edemez.

### ÜRÜN SONUCU

**Sakin dönemde "en riskli hücre" gösterimi yanıltıcıdır.** Arayüz, sakin
dönemlerde hücre değil BÖLGE düzeyinde konuşmalı ya da hücre gösterimini
belirsizlik işaretiyle sunmalıdır.

Bu, manşetteki (c) bulgusuyla tutarlı: ETAS'ın değeri kritik günlerdedir ve
sakin dönemde iki yöntem arasındaki hücre düzeyi fark, ikisinin de gerçek
bilgisinin sınırını gösterir.

## Not

Analitik yol 2560 hücrenin tamamını üretir (hiçbirinde sıfır oran yok);
simülasyon yalnızca olay ürettiği 180 hücreyi verir. Eşik sonrası fark
(311 vs 129) bunun sonucudur -- eski çıktının "azlığı" bir bilgi değil,
çözünürlük sınırıydı.
