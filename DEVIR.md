# DEVİR KAYDI

Bu depo, **özel geliştirme arşivinin 27 Ağustos 2026 itibarıyla son
hâlidir.** Önceki künye ve commit atıfları arşiv deposuna aittir.

## Ne devredildi, ne devredilmedi

**Devredilen:** çalışan sistemin tamamı — üretim hattı ve on koruması,
ölçüm kodu ve dondurulmuş bulguları, site, belgeler, vaka defteri, testler.

**Devredilmeyen:** commit geçmişi. Arşiv depo, 185 commit'lik geliştirme
kaydını künyeleri ve hash'leriyle birlikte özel olarak saklar. Bu depodaki
belgeler zaman zaman geçmiş commit'lere atıf yapar (`V49`, `V53` gibi vaka
numaraları ve kısa hash'ler); **bu atıflar arşiv deposuna aittir ve burada
çözülemez.** Bilerek böyledir: bir atfın nereye baktığı, atfın kendisi
kadar açık yazılmalıdır.

## Künye zinciri kopmadı, devredildi

Yayımlanan her sayı bir künye taşır: kodun commit'i, parametre dosyasının
sha256'sı, katalog sha256'sı ve çalışma ağacının durumu. Bu zincirin amacı,
bir sayının hangi kodla ve hangi veriyle üretildiğinin sonradan
doğrulanabilmesidir.

**Devir noktasından sonraki künyeler bu deponun hash'leriyle üretilir.**
Devir öncesinde yayımlanmış sayıların künyeleri arşiv deposunun
hash'lerine bakar. İki dönem arasındaki sınır burasıdır ve gizlenmemiştir:

| dönem | künye kaynağı | doğrulanabilirlik |
|---|---|---|
| devir öncesi | arşiv depo (özel) | site sahibinde; kamuya açık değil |
| devir sonrası | bu depo (kamuya açık) | herkes doğrulayabilir |

Yayın arşivi (`yayin` dalındaki `_arsiv/`) devrolduysa, devir öncesi
günlerin **yayımlanmış dosyaları ve sha256'ları** kamuya açık kalmaya devam
eder — doğrulanamayan şey o dosyaları üreten kodun kendisidir, çıktısı
değil.

## Neden geçmiş taşınmadı

Geliştirme geçmişi, bir kamuya açık depoda bulunmaması gereken şeyler
taşıyabilir: yarım kalmış denemeler, silinmiş veri örnekleri, geliştirme
sırasında yazılmış ve sonradan yanlış olduğu anlaşılmış beyanlar. Bunların
her birini geçmişte tek tek temizlemek, temizlendiğini **göstermekten**
daha zordur. Tek commit'lik devir, o ispat yükünü ortadan kaldırır:
kamuya açılan şey, denetlenebilir tek bir durumdur.

Bu, geçmişin silindiği anlamına gelmez. Arşiv depo durur. Bir bulgunun
gerekçesi sorulursa, `docs/VAKA_DEFTERI.md` 56 vakanın hepsini gerekçesiyle
birlikte taşır ve o defter buradadır.
