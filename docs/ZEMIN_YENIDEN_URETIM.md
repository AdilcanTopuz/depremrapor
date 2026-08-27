# DEĞERLENDİRME ZEMİNİNİN YENİDEN ÜRETİMİ — okuma kuralları, SONUÇ GÖRÜLMEDEN

**Bu belge yeniden üretim koşusu başlamadan yazılmıştır** (commit tarihi
kanıttır). Sonuç geldiğinde ilgili dal olduğu gibi uygulanır.

## Bulgu

Dondurulmuş değerlendirme tablosu (`data/processed/etas_analytic_weekly/`,
24 Ağu 2026 21:22) bugünkü kodla **yeniden üretilemiyor**.

    eval ~ 1,061 x hat + 6,41e-05      (eğim ~1: TETİKLEME AYNI)
    eval μ oranı  0,3691
    hat  μ oranı  0,0968               fark 3,81 kat -- ARKA PLANDA

## Teşhis zinciri — beş kontrol, farkın yeri daraltıldı, sebebi bulunamadı

| kontrol | sonuç |
|---|---|
| parametre sha256 | **aynı** (`5ab1f75e…`; MANSET ve arşiv manifestiyle birebir) |
| katalog kırpması | **etkisiz** (üç kesimde 0,5008) → **ileri bakış YOK** |
| EM adımı | **kararlı** (tohumsuz 6 tekrar, 1,000 kat) → V16 değil |
| `history_years` | **açıklamıyor** (2/3/5/10/20 → 0,084-0,127) |
| `cell_id` düzeltmesi | ölçülmüş etki **1,00005** kat |

**Kalan tek aday:** katalogun geriye dönük içerik değişimi (AFAD revizyonu,
tekilleştirme davranışı, Mc sınıflandırması). **Doğrudan sınanamaz:**
`catalog_merged.csv` gitignore'da ve sha'sı hiçbir yere yazılmamıştı.

## KÖK BULGU — mühür sayıları koruyordu, ZEMİN künyesizdi

Künye zinciri **parametreleri** kapsıyordu (`etas_params_sha256`) ama
**katalogu** kapsamıyordu. V6'nın (bayat eser) veri tarafındaki boşluğu tam
buradaydı: dondurulmuş bir sonucun, dondurulmamış bir zemini vardı.

Bu boşluk **pazarlıksız kapatılır** (adım 2), sonuç ne çıkarsa çıksın.

---

# OKUMA KURALLARI — iki dal, önceden bağlandı

## DAL A — yeni tablo eskiyle ÖRTÜŞÜRSE (μ dâhil)

Fark geçici bir durumdu (o günkü katalog hâli). Manşet **yerinde kalır**;
vaka "yeniden üretim doğrulandı" ile kapanır.

**Katalog-sha eksiği YİNE DE kapatılır.** Sorunun bu kez ortaya çıkmamış
olması, boşluğun var olmadığı anlamına gelmez.

## DAL B — yeni tablo FARKLIYSA (3,81× kalıcıysa)

1. **Manşet sayıları yeniden ölçülür ve mühür tazelenir** — bu kez "metin
   düzeltmesi" değil, **"sayı değişikliği, sebep: zemin yeniden üretildi"**
   gerekçesiyle. Eski manşet arşive, `SAYI_HARITASI.md`'ye tam kayıt.

2. **KRİTİK SORU — karşılaştırmalı hükümler değişiyor mu?**

   Karşılaştırmalar aynı tablo üzerinde yapıldı; **iç tutarlılık korunmuştur.**
   Ama ETAS'ın μ'sü değişince kalibrasyonu (1,09) ve IG zemini kayar.

   > **NPP−ETAS farkının işareti ve bandı yeniden ölçülmeden hiçbir hüküm
   > "korundu" sayılmaz.** Ö5, H1, H2 ve ürün kapısı tek tek yeniden ölçülür.

   * **Hükümler korunursa:** sonuçlar **sağlamlaşmış** olur — zemin değişti,
     hüküm değişmedi; güçlü bir dayanıklılık kanıtı.
   * **Korunmazsa:** hangi hükmün düştüğü **açıkça ilan edilir.** Bu, projenin
     dürüstlük cümlesinin ("sınadık ve sonucunu söylüyoruz") en zor ve en
     değerli sınavıdır.

## Her iki dalda da rapor cümlesi

> "Değerlendirme zemini [tarih]'te yeniden üretildi; [örtüştü / μ farkı
> doğrulandı]; etkilenen sayılar ve hükümler: [liste]."

---

# TEŞHİS NOTU — yeniden üretim koşusuna eklendi

μ arka plan oranıdır; 3,81×'lik fark katalogdan geliyorsa en olası kanal
**tarihsel dönemdeki olay sayısının değişmesidir** (tekilleştirme, Mc
sınıflandırması, AFAD revizyonu).

Koşuda **dönem-bazlı olay sayıları loglanır**; eski tablonun ima ettiği
sayılarla kabaca karşılaştırılabilir ve sebep adayı daraltılır.

**Kesin teşhis mümkün olmayabilir** (eski katalog yok). O durumda kapanış
şudur ve yeterlidir:

> "Sebep: katalog durumu; **doğrudan sınanamadı** (kayıt yok). Bundan sonrası
> için katalog sha256'sı künyededir."

---

**Cron, bu çözülmeden başlamaz.** Yeniden üretilemeyen bir zemin üzerinde
zamanlanmış yayına başlamak, bayat sayının otomatikleştirilmiş hâli olurdu.
