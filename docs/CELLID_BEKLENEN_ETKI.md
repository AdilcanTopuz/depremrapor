# cell_id üst sınır düzeltmesi — BEKLENEN ETKİ (değişiklikten ÖNCE yazıldı)

Protokol: beklenen etki yazılır → değişiklik yapılır → gerçekleşen etki ölçülür
→ ikisi karşılaştırılır → fark varsa fark açıklanır.

## Kusur

`cell_id` yarı-açık aralık kullanıyor: `floor((x - x0) / adım)`. Bölge filtresi
`between(35, 43)` ise KAPALI aralık. Tam sınırdaki olay (43,0000 K ya da
45,0000 D) filtreyi geçiyor ama ızgaranın bir satır/sütun dışına düşüyor.

## Kapsam — ÖLÇÜLDÜ (değişiklikten önce)

    katalog                olay      ızgara dışı   Mc=3,3 üstü   M>=4,5
    birleşik              297.899        10             2          0
    ayrıştırılmış          47.402         2             2          0
    baseline_poisson       2.102 hücre    2             —          —

**Beklenen etki tahminim önce "2 olay" idi; ölçünce 10 çıktı.** Fark, 2'nin
`baseline_poisson`'daki HÜCRE sayısı olmasından geliyor: 10 sınır olayının 8'i
Mc altında ya da ayrıştırmada elendiği için modelleme boru hattına hiç girmiyor.
Bu, dondurma öncesi kayda "2 hücre" diye geçmişti ve o bağlamda doğruydu; ama
"2 olay" demek yanlış olurdu.

## Beklenen etki (sayısal)

1. **Birleşik katalogda 10 olay** doğru hücreye taşınır:

       43,0000K 26,6160D : 32006 -> 31006
       40,3667K 45,0000D : 21080 -> 21079
       41,3195K 45,0000D : 25080 -> 25079
       35,0000K 45,0000D :    80 ->    79   (3 olay)
       35,6130K 45,0000D :  2080 ->  2079
       42,8200K 45,0000D : 31080 -> 31079
       43,0000K 44,9800D : 32079 -> 31079
       43,0000K 44,9200D : 32079 -> 31079

2. **baseline_poisson**: 32006 ve 31080 hücreleri KAYBOLUR; oranları 31006 ve
   31079'a taşınır. Hücre sayısı 2102 -> 2100 veya 2101 (hedef hücreler zaten
   varsa 2100).

3. **Değerlendirme ızgarası**: taşma 2 -> 0. Ayıklama kodu artık hiçbir şey
   ayıklamaz (savunma amaçlı kalır).

4. **MANŞET SAYILARI DEĞİŞMEZ.** Gerekçe: sınır olaylarının hiçbiri M>=4,5
   değil (ölçüldü: 0), dolayısıyla hedef olaylara katkı vermiyorlar. Poisson
   temel model oranları en fazla 4 hücrede değişir (2 kaybeden, 2 kazanan) ve o
   hücrelerde M>=4,5 olayı yok.

## Ölçülecek (gerçekleşen etki)

* birleşik katalogda ızgara dışı olay sayısı: beklenen **0**
* baseline_poisson hücre sayısı ve iki hedef hücrenin oranları
* değerlendirme ızgarasında ayıklanan hücre: beklenen **0**
* manşetin üç ana sayısı (AUC farkı, toplam IG, dizi-dışı IG 90g): beklenen
  **değişmez**

Beklenenden sapma çıkarsa sapma açıklanır; "yakın sayılır" denmez.

---

# GERÇEKLEŞEN ETKİ (değişiklikten sonra ölçüldü)

    #  ölçüt                                 beklenen        gerçekleşen     sonuç
    1  birleşik katalogda ızgara dışı olay   0               0               TUTTU
    2  baseline_poisson hücre sayısı         2100 ya da 2101 2100            TUTTU
       kaybolan hücreler                     32006, 31080    32006, 31080    TUTTU
       yeni hücre                            —               yok             TUTTU
    3  değerlendirme ızgarasında taşma       0               0               TUTTU
    4  manşet sayıları                       değişmez        değişmedi       TUTTU

## SAPMA — ve açıklaması

**Beklenen:** "Poisson temel model oranları EN FAZLA 4 hücrede değişir."
**Gerçekleşen:** 2100 ortak hücrenin HEPSİNDE değişti.

Bu bir sapmadır ve "yakın sayılır" denmeden açıklanmıştır. Ölçüm:

    b/a oranı: ortanca 1,00004640 | min 1,00004640 | maks 1,00004640
               standart sapma 5,66e-14

Oran tüm hücrelerde SABİT. Yani mekânsal örüntü değişmedi; değişen
**normalizasyon sabiti**.

**Mekanizma.** `baseline_poisson` "nereden" bilgisini yumuşatılmış küçük
olaylardan, "kaç tane" bilgisini gözlenen M>=5 sayısından alır; yani toplam
gözlenen sayıya SABİTLENİR. Izgara dışı 2 hücre kaybolunca onların payı
(0,00071024 olay/yıl = toplamın %0,0046'sı) kalan hücrelere ORANTILI dağıtıldı:

    15,30849832 / 15,30778808 = 1,00004640   (beklenen)
    ölçülen ortanca oran      = 1,00004640   (fark 0,00e+00)

Beklentimin yanlış olmasının sebebi: "en fazla 4 hücre" tahmini, oranların
mutlak olduğunu varsayıyordu. Oysa bunlar normalize edilmiş oranlar ve payda
değişince hepsi değişir. Kusur tahminde, ölçümde değil.

## Manşet sayılarına etkisi — ölçüldü

Yeniden ölçüldü ve raporlanan hassasiyette (3 ondalık) HİÇBİRİ değişmedi:

    AUC       : Poisson 0,6503 | ETAS 0,7909 | fark +0,1407
    AUC farkı : +0,1433  %95 GA [+0,0761; +0,2144]  (blok L=7, 208 blok)
    IG        : +1,068  (olay +1,181 | maruziyet -0,112)
    Kahramanmaraş tablosu ve bölge tablosu: aynı değerler

Analitik beklenti de bunu doğruluyor:

    IG değişimi = -ln(k) + (k-1)*SUM(lambda_P)/N = -4,640e-05 + 3,741e-05
                = -8,98e-06     (raporlanan hassasiyetin binde 9'u)
    AUC değişimi = TAM OLARAK 0 (sıralamaya dayalı; tekdüze ölçekleme
                   sıralamayı değiştirmez)

**Sınır:** önceki `daily_backtest.json` git tarafından izlenmiyor (data/
yoksayılıyor) ve üzerine yazıldı; 5. ondalıktaki kaymayı DOĞRUDAN
karşılaştıramadım. Elde olan, analitik beklenti ile raporlanan hassasiyette
değişmezliğin ölçülmesi. Bu sınır kayda geçirilmiştir.

## Yan bulgu: cell_id formülü ÜÇ yerde kopyalanmıştı

Düzeltme kanonik `config.cell_id`'ye yapıldı, ama formül üç modülde elle
kopyalanmıştı (`daily_backtest`, `grid_features`, `etas_baseline`) ve düzeltmeden
habersiz kalacaklardı. Üçü de kanonik fonksiyona bağlandı; bir test artık
`// STEP` kalıbını tüm kaynak ağacında arıyor ve kopya bulursa patlıyor.

Bu, VAKA_DEFTERI V4'ün ("aynı kuralın iki yerde kurulması") bir başka örneğidir
ve kök neden düzeltmesinin yan getirisi oldu: semptom çözümüyle kalsaydı bu üç
kopya görülmeyecekti.
