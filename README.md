# depremrapor.com

**Türkiye için olasılıksal deprem tahmini.** ETAS modeliyle üç saatte bir
üretilen, ölçülmüş ve künyelenmiş bir olasılık haritası.

**Canlı site: [depremrapor.com](https://depremrapor.com)**

---

## Bu proje neyi yapar

Türkiye'yi 0.25° × 0.25° hücrelere böler ve her hücre için üç zaman
penceresinde (1 gün, 7 gün, 30 gün) M≥4.5 bir olayın görülme olasılığını
hesaplar. Yöntem **ETAS**'tır (Epidemic-Type Aftershock Sequence): her
deprem, kendisinden sonra gelenlerin oranını geçici olarak yükseltir.
Hesap analitiktir; simülasyon kullanılmaz.

Sonuç üç saatte bir otomatik olarak yeniden üretilir ve siteye yayımlanır.
Pencere, koşunun kendi anından başlar: "önümüzdeki 1 gün" ifadesi
harfiyen o anlama gelir.

## Bu proje neyi yapmaz

Belirli bir tarih, yer ve büyüklükte bir deprem öngörmez; böyle bir
öngörü bilimsel olarak mümkün değildir. Ürettiği şey bir **oran**dır:
belirtilen pencerede, belirtilen hücrede, belirtilen eşiğin üzerinde bir
olay görülme olasılığı.

Bunun pratik karşılığı şudur: olasılığı yüksek gösterilen bir hücrede
hiçbir şey görülmeyebilir, düşük gösterilen bir hücrede büyük bir olay
görülebilir. Model bunu yanlış yapmış olmaz — olasılık zaten budur.

Resmî bir kurum değildir, resmî bir kurumu temsil etmez. Bir uyuşmazlıkta
[AFAD](https://www.afad.gov.tr) esastır.

## Yürütme ilkesi

Projenin tek kuralı şudur: **bulunan her hata yazılır.**

`docs/VAKA_DEFTERI.md` bugüne kadar bulunmuş 56 kusuru gerekçesiyle
birlikte taşır — ne yapıldığını değil, neyin yanlış yapıldığını ve
nasıl anlaşıldığını. Yayımlanmış bir sonuç yanlış çıkarsa silinmez,
**geri çekilmiş** olarak işaretlenir; yayımlanmış ve geri çekilmiş bir
sonuç, hiç yayımlanmamış bir sonuçtan farklı bir statüdedir.

Aynı ilkenin koddaki karşılığı **on korumadır**. Üretim hattı, bunlardan
biri reddederse yayımlamaz: kirli çalışma ağacı, bayat katalog, katalog
küçülmesi, kalibre edilmemiş parametreler, ürün kapısı, yayın kapsamı,
şema, dil, hücre sayısı bandı ve kart-tahmin tutarlılığı. Her koruma
kendi istisna tipiyle `src/operational/pipeline.py` içinde ilan edilir ve
listenin koddan türetildiği testle sınanır.

Bir koruma, **bir şeyi reddettiği gösterilene kadar kurulu sayılmaz.**

## Künye — bir sayı nereden geldiğini söyler

Yayımlanan her dosya bir künye taşır: üreten kodun commit'i, parametre
dosyasının sha256'sı, katalog sha256'sı ve çalışma ağacının temiz olup
olmadığı. Sitede görünen her sayının indirilebilir bir dosyada karşılığı
vardır ve o dosyanın sha256'sı künyededir.

Bu yüzden atıf künyesiz yapılmaz: künyesiz alıntılanan bir sayı, hangi
katalogla ve hangi kodla üretildiği bilinmediği için doğrulanamaz.
Önerilen atıf biçimi, o günün künyesiyle birlikte
[metodoloji sayfasında](https://depremrapor.com/metodoloji.html) gösterilir.

## Ölçüm

Model, ETAS'a karşı değil ETAS **ile** ölçülür; makine öğrenmesi kolunun
sonucu da aynı ölçütle verilir ve ETAS'ı geçmediği durumda geçmediği
yazılır. Ölçüt sonuçlar görülmeden ilan edilir ve sonradan değiştirilmez.
"Fark gösterilemedi" cümlesi, saptanabilir en küçük etki (MDE) verilmeden
kurulmaz — çünkü fark yokluğu ile ölçüm gücü yokluğu aynı şey değildir.

Ayrıntı: [yöntem ve sınırlılıklar](https://depremrapor.com/metodoloji.html).

## Belgeler

| belge | ne anlatır |
|---|---|
| [metodoloji.html](https://depremrapor.com/metodoloji.html) | model, ölçüm, sınırlar, kapsam |
| [vaka-defteri.html](https://depremrapor.com/vaka-defteri.html) | bulunmuş 56 kusur, gerekçeleriyle |
| [denetim-mirasi.html](https://depremrapor.com/denetim-mirasi.html) | denetim ilkeleri |
| [yasal.html](https://depremrapor.com/yasal.html) | sorumluluk reddi, veri hakları, kişisel veriler |
| `docs/SAYI_HARITASI.md` | hangi sayı hangi kurulumla üretildi, hangisi geçersiz |
| `DEVIR.md` | bu deponun özel arşivden devralınma kaydı |

## Çalıştırma

    pip install -r requirements-yayin.txt
    python scripts/check_number_map.py --install   # pre-commit kancası
    python -m src.operational.pipeline    # tahminleri üretir (korumalar dâhil)
    python -m src.operational.site_kur    # siteyi kurar
    pytest -q                             # testler

Kancayı `.git/hooks` taşıyamaz — git ile gelmez, her klonda bir kez
kurulur. Kurulmazsa sayı haritasının bayatlaması sessizce mümkün olur.

**Taze bir klonda bazı testler ATLANIR.** Ham katalogdan türetilen
dosyalar (`catalog_merged.csv`, `catalog_declustered.csv`) depoda durmaz;
onlara bağlı testler sebebi yazılarak atlanır ve hat bir kez
çalıştırıldıktan sonra kendiliğinden koşar. "Veri yok" ile "bozuk" ayrı
şeylerdir ve ayrı görünürler (`tests/conftest.py`).

Yayın GitHub Actions üzerinde üç saatte bir koşar
(`.github/workflows/yayin.yml`) ve sonucu `yayin` dalına yazar. Düşen bir
koşu `yayin` dalına dokunmaz: site bir önceki yayını göstermeye devam eder
ve **yayının yaşını her zaman gösterir**; bayatlık eşiği aşılırsa uyarır.
Eşik künyede makine-okunur biçimde taşınır (`tazelik.bayatlik_esigi_saat`);
buraya sayı yazılmaz, çünkü elle yazılan bir sayı kaynağından ayrışır.
Sessiz başarısızlık yoktur.

## Veri kaynakları

AFAD (ana katalog, 2003–) · Kandilli Rasathanesi/KOERI (tarihsel katalog,
1900–) · EMSC · USGS · Natural Earth · OpenStreetMap (harita altlığı).
Koşulları `NOTICE` dosyasında.

## Lisans

Kod **Apache-2.0** (`LICENSE`). Veriler kendi koşullarına tâbidir; kodun
lisansı verilerin lisansı değildir (`NOTICE`).

## Hata bildirimi

Sitede yayımlanmış bir sayının yanlış olduğunu düşünüyorsanız bildiriniz.
Doğrulanan bir hata düzeltilmekle kalmaz, vaka defterine gerekçesiyle
işlenir.
