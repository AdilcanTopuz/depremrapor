# Yayın tetikleyicisi — Cloudflare Worker

Yayın koşusunu başlatan taraf. İş akışı yine GitHub Actions üzerinde koşar;
bu Worker yalnızca "şimdi koş" der.

## Neden

GitHub Actions `schedule` tetiği **garantili değildir** ve bu ölçüldü:
28 Ağustos 2026 sabahı 00:30 yuvası ~1 saat 45 dakika gecikmeyle başladı,
03:30 ve 06:30 yuvaları hiç çalışmadı. Sonuç: "üç saatte bir yenilenir"
diye ilan edilen bir sistemde yayın yaşı 5,4 saate çıktı.

Bir vaadin tutulmadığı yerde iki seçenek vardır: vaadi düşürmek ya da
mekanizmayı güvenilir kılmak. Bu Worker ikincisidir.

## Ne yapar

On dakikada bir uyanır. **Uyanmak tetiklemek değildir** — her seferinde
şu sırayla bakar:

1. **Koşu sürüyor mu?** GitHub'a sorar; koşan ya da kuyrukta bekleyen bir
   koşu varsa çıkar. Kuyruğa yığmak anlamsız iş üretir.
2. **Son yayın ne kadar eski?** `depremrapor.com/data/kunye.json` okunur.
   `TABAN_SAAT` dolduysa tetikler.
3. **Yeni bir olay var mı?** Yayımlanmış katalogun gördüğü son olaydan
   sonra `ESIK_MW` üzerinde bir olay olduysa tetikler (asgari ara
   korunarak). Kaynak: AFAD birincil, EMSC yedek.

Sakin bir günde günde 144 kez uyanır, 8 kez tetikler.

**Durum tutmaz.** "En son ne zaman yayımlandı" ve "katalog nereye kadar
görüyor" sorularının cevabı zaten yayımlanmış künyededir. Ayrı bir yerde
durum tutmak, o durumun künyeden ayrışması riskini yaratırdı.

## Neden olay tetiği

Projenin kendi ölçümü: olay teriminin **%98,8'i** 120 başlangıç içindeki
en yüksek **10 olaylı başlangıçtan** geliyor (`docs/MANSET.md`). Modelin
değeri düzgün aralıklara yayılmaz, olay anında yoğunlaşır. Sabit aralık
sakin haftada boşuna koşar, dizi başlayınca geciktirir.

## Kurulum

### 1. Token üret (GitHub)

Settings → Developer settings → Personal access tokens → **Fine-grained**

    Repository access : Only select repositories -> depremrapor
    Permissions       : Actions -> Read and write
                        (BAŞKA HİÇBİR ŞEY)
    Expiration        : bir süre seç ve takvime not al

Bu yetki sınırı önemlidir. Token sızarsa yapabileceği tek şey koşu
tetiklemektir; koda da `yayin` dalına da yazamaz.

### 2. Worker'ı yayımla

    cd cloudflare/tetikleyici
    npx wrangler deploy
    npx wrangler secret put GITHUB_TOKEN     # token'ı buraya yapıştır

### 3. Doğrula — kural 9

Worker'ın `GET /` ucu **kararı gösterir ama tetiklemez**:

    curl https://depremrapor-tetikleyici.<alt-alan>.workers.dev/

Beklenen çıktı, o anki duruma göre şunlardan biri:

    {"tetikle": false, "gerekce": "taban dolmadı (1.2/3 saat), yeni olay yok"}
    {"tetikle": true,  "sebep": "taban: son yayın 3.1 saat önce"}

`"künye okunamadı"` görüyorsan site erişilemiyordur; `"koşu sürüyor"`
görüyorsan zaten bir koşu vardır.

Tetiklemenin gerçekten çalıştığı ise ancak **koştuğu görülünce** kurulu
sayılır: cron'un ilk tetiklemesinden sonra Actions sekmesinde koşunun
`workflow_dispatch` ile başladığı ve `kosu_ozeti.json` içindeki `sebep`
alanının Worker'ın yazdığı gerekçeyi taşıdığı görülmelidir.

## Sessizce durma riski

Token'ın süresi dolduğunda tetikleme **sessizce** durur: Worker uyanmaya
devam eder, GitHub 401 döner, hiçbir şey olmaz. Bu riskin karşılığı
sitededir — yayın yaşı her zaman görünür ve bayatlık eşiği aşılınca arayüz
uyarır. Yani tetikleyicinin ölümü, ürünün kendi göstergesinden okunur.

GitHub'ın kendi `schedule` tetiği de **yedek olarak duruyor** (altı saatte
bir). Worker ölürse yayın büsbütün durmaz, yavaşlar.

## Ayarlar

`wrangler.toml` içindeki `[vars]` bloğu. `GITHUB_TOKEN` orada **yazmaz**,
secret olarak girilir.
