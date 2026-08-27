# Denetim mirası — ne ters gidebilir ve nereden anlarım?

Bu belge bir araç listesi DEĞİLDİR. Araç listesi "ne kurulu?" sorusunu
yanıtlar; bu belge **"ne ters gidebilir ve nereden anlarım?"** sorusunu
yanıtlar. Faz 3'e giren kişi — insan ya da sistem — buradan
başlar.

## Neden var

Jeofizik katman ablasyonunda ölçüt "fark, tohumlar arası saçılımın iki katından
büyük mü?" idi. Coulomb bu ölçüte göre **KATKI VAR** çıktı; 15 tohumla Welch
p = 1,4e-13. Sonuç yayına bir adım uzaktaydı.

O p-değeri yalnızca TEKRARLANABİLİRLİĞİ ölçüyordu. Asıl belirsizlik test
setindeki 66 olaydan geliyordu ve olay bazlı bootstrap yapıldığında aralık
sıfırı içeriyordu.

**Araçların neden var olduğunun en somut kanıtı, yokluklarında neredeyse
yapılacak olan hatadır.** O gün elimizde bu belgedeki hiçbir şey yoktu.

## Ana fikir: vaka → örüntü → otomatik kontrol

Bir hata üç aşamada kalıcı korumaya dönüşür:

1. **Vaka** — ne oldu, nasıl bulundu (`docs/VAKA_DEFTERI.md`, 14 vaka)
2. **Örüntü** — bu hata hangi SINIFA ait; hangi başka hatalar aynı sınıftan
3. **Otomatik kontrol** — o sınıfı yakalayan, hatırlamaya bağlı olmayan bir test
   ya da hook

İlk örneği `cell_id` düzeltmesinde görüldü: V4'ün dersi ("aynı kuralın iki
yerde kurulması") bir hatıra değil, **çalışan bir test** hâline geldi — kaynak
ağacında `// STEP` kalıbını arayıp kopya bulursa patlıyor.

**Faz 3'ün ölçütü budur:** yeni bir hata bulunduğunda iş, hatayı düzeltmekle
bitmez; örüntüsü adlandırılana ve bir kontrole bağlanana kadar sürer.

---

## HATA SINIFI → NASIL YAKALANIR → HANGİ ARAÇ

| # | hata sınıfı | nasıl yakalanır | araç | durum |
|---|---|---|---|---|
| 1 | **Sessiz birim/ölçek hatası** (V1: zaman 1000 kat) | İki farklı hesabın TAM AYNI çıkması bir hata belirtisidir | `test_epoch_seconds_is_real_seconds`; tek dönüşüm noktası `catalog_io.epoch_seconds` | ✅ otomatik |
| 2 | **Aynı kuralın iki yerde kurulması** (V4: `mc="positive"`; cell_id kopyaları) | Değişmesi beklenen bir şey değişmiyorsa değişiklik uygulanmamıştır; kaynak ağacında kalıp taraması | `test_etas_config_is_single_source`, `test_no_module_duplicates_the_cell_id_formula` | ✅ otomatik |
| 3 | **Yerel doğru kuralın küresel etkisi** (V2: tekilleştirme zinciri; V3: bayrak taşması) | Fizik dışı sayı; "aynı saniyede kaç olay?" gibi ham veri kontrolleri | EDA defteri kontrolleri | ⚠️ elle |
| 4 | **Yanlış belirsizlik kaynağını ölçmek** (V5: tohum p-değeri) | "Bu p-değeri NEYİ ölçüyor?" sorusu | Olay bazlı bootstrap; `KAPSAM_BEYANI` | ✅ kural + kod |
| 5 | **Bayat sayı** (V6: STAI öncesi CSEP) | Dosya zaman damgası; parametre hash'i | `SAYI_HARITASI.md` + pre-commit hook + 7 test | ✅ otomatik |
| 6 | **Sonucu belirleyen keyfî düzeltme** (V7: 3,42x şişik taban) | Aynı sorunun iki kurulumda FARKLI YÖNDE cevap vermesi | Analitik taban — keyfîliğin kaldırılması | ✅ yapısal |
| 7 | **Toplamı koruyan hücre hatası** (V8: kaynak konumu) | Toplam testleri geçer, hücre bazlı korelasyon düşer | — | ❌ **AÇIK** |
| 8 | **Kuruluma bağlı sessiz hata** (V9: blok indisleme) | "Bu parametre otomatik mi sabit mi?" sorusu; koda bakmak | `test_block_bootstrap` (5 test) | ✅ otomatik |
| 9 | **Neredeyse doğru mutlaklık** (V10: "hiçbir hücrede") | "ilk/tek/hiç/tamamen" taraması + iddianın ölçülmesi | — | ❌ **elle** |
| 10 | **Sayıya gerekçe uydurma** (V13: 202 vs 208) | Beyan edilen her doğrulamanın TAKİBİ | — | ❌ **elle** |
| 11 | **Gürültünün işareti yok etmesi** (V14: AUC maskelemesi) | "Ölçüm aracının çözünürlüğü yeterli mi?" | MDE kuralı + `test_mde` (5 test) | ✅ kural + kod |
| 12 | **Kontrolün kendini denetlememesi** (V11/V12) | Kontrol kendi yazarını durduruyor mu? | `test_number_map_guard` (9 test); künye kirli-ağaç damgası | ✅ otomatik |
| 12b | **Kontrol kurulu ama KÖR** (V15: izleme listesi ↔ mekanizma örtüşmüyor) | "Listede mi?" değil "GÖREBİLİYOR MU?" -- reddettiğini gösteren deney | `test_every_watched_path_is_git_tracked` | ✅ otomatik |
| 12d | **Dedektörün kendisi kör** (V17: performans tabanlı sızıntı tespiti kısmi sızıntıyı göremiyor) | Dedektöre bilinen bir sızıntı verilir; yakalamazsa dedektör kördür | yapısal engel: `HistoryView` + `test_history_view` (6 test) | ✅ otomatik |
| 12c | **Beyan, testin kapsamından geniş** (V16: künye "deterministik" derken EM adımı tohumsuz) | Beyanın TAM kapsamı sınanıyor mu, alt kümesi mi? | `test_local_params_is_deterministic` (uçtan uca) | ✅ otomatik |

### V15 + V16'nın ortak dersi

> **Bir beyanın kanıtı, beyanın TAM KAPSAMINI sınamalıdır — alt kümesini değil.**

V15'te koruma listedeydi ama mekanizma göremiyordu. V16'da test geçiyordu ama
künyenin "deterministik" beyanı testin sınadığından geniş bir iddiaydı:
`expected_counts` bit-özdeşti, oysa uçtan uca yol EM adımındaki tohumsuz
`local_params`'ı içeriyordu.

İkisi de "yanlış bir şey yapıldı" vakası değil; **doğru şeyin yanlış yeri
sınandığı** vakalar. Bu yüzden ikisi de testler geçerken var oldular.

**DÖRT sınıf hâlâ elle: 3, 7, 9, 10.** Bu, belgenin en dürüst satırıdır --
bu sınıflar için otomatik kontrolümüz YOK. Faz 3'te bunlardan bir hata gelirse,
onu yakalayacak olan disiplin, mekanizma değil.

(İlk yazımda "üç sınıf" demiştim ve sayınca dört çıktı: 3 numaralı sınıfı
atlamışım. Kendi belgemdeki sayının doğrulanması da aynı kurala tabi --
bkz. zorunlu kural 7.)

---

## Zorunlu kurallar (Faz 3 giriş kapısı)

Yeni bir model değerlendirmesi başlamadan önce bunların KURULU olması gerekir:

1. **Ölçüt sonuçtan önce ilan edilir** (`docs/KABUL_OLCUTLERI.md`, Ö1-Ö4).
   Sonuç geldikten sonra eşik değiştirilmez; ölçüt kusurluysa kusuru yazılır ama
   eşik yerinde kalır.
2. **Yorum kuralları sonuçtan önce bağlanır** (Ö4). Her sonucun yanında hangi
   kuralın devreye girdiği işaretlenir.
3. **"Fark gösterilemedi" asla tek başına yazılmaz** — yanında MDE durur.
   (`gain_breakdown._ig_ci`, küçük örneklemde t katsayısı.)
4. **Her güven aralığı tablosunun altında kapsam beyanı vardır**
   (`gain_breakdown.KAPSAM_BEYANI`, koda gömülü).
5. **Künyesiz sayı yayımlanmaz** (`scripts/17_fingerprint.py`).
6. **Sayı üreten her değişiklik sayı haritasını günceller** (pre-commit hook
   zorunlu kılar).
7. **Bir sayının nereden geldiği gösterilmeden gerekçesi yazılmaz** (V13).
8. **Beklenen etki değişiklikten ÖNCE yazılır**, sonra gerçekleşen ölçülür ve
   sapma açıklanır (`docs/CELLID_BEKLENEN_ETKI.md` örneği).
10. **Eşik ilan edilmeden önce ULAŞILABİLİRLİĞİ gösterilir.** Bir ölçüt,
    verinin ve gürültünün izin verdiği en iyi değerin üstünde bir eşik
    koyuyorsa, yöntem ne kadar iyi olursa olsun geçilemez -- ve başarısızlık
    yöntemin kusuru sanılır.

    **Yöntem (φ'den korelasyon tavanı):** gözlenen korelasyon
    `r <= sqrt(Var(gerçek) / (Var(gerçek) + φ·E[gerçek]/n_sim))`. Burada φ
    ölçülen aşırı dağılımdır. Ö3a'nın "1-10" katmanında tavan 0,7086 çıktı;
    ilan edilen eşik 0,85'ti. Gözlenen 0,6961, yani tavanın %98,2'si --
    analitik yöntem ulaşılabilir en iyi performanstaydı ve ölçüt yine de
    KALDI verdi.

    Bu hesap sonuçtan ÖNCE yapılabilirdi. Faz 3'te her yeni ölçüt için ön
    koşuldur.

9. **Kurulum kanıtı değil, ÇALIŞMA kanıtı.** Yeni bir koruyucu ya da izleme
   eklendiğinde, bir şeyi REDDETTİĞİNİ gösteren bir deney yapılmadan "kurulu"
   sayılmaz. (V15: dosya listedeydi, testi geçiyordu, hook kuruluydu -- ve
   koruma boştu. Çalıştığının kanıtı, testlerinin geçmesi değil bir şeyi
   reddetmesidir.)

## Bilinen boşluklar

* Hücre düzeyi mekânsal doğruluk için otomatik kontrol yok (sınıf 7).
* Mutlaklık taraması ve beyan takibi elle (sınıf 9, 10).
* Çıktı json'ları izlenmiyor; künye zincirinde boşluk (dondurma sonrası 1b).
* Güven aralıkları parametre belirsizliğini kapsamıyor.

### KARŞILAŞTIRMA KURULURKEN (V18, V19)

**1. Ortaklık iddiası, ortak elemanların SAYILMASIYLA doğrulanır --
parametrelerin karşılaştırılmasıyla değil.** İki ızgaranın aynı SIKLIKTA
olması, aynı NOKTALARDA olması demek değildir. Kayma sessizdir çünkü her iki
ızgara da kendi içinde kusursuzdur. (V18: `freq="7D"` ile kurulmuş iki ızgaranın
kesişimi SIFIR çıktı.)

Bu, V4 ailesinin (aynı kuralın iki yerde kurulması) zamansal akrabasıdır: iki
sistem aynı parametreyle kurulmuş ama aynı ÇAPA NOKTASINDAN değil.

**2. Geçmişin yokluğu BİR BİLGİDİR, bilginin yokluğu değil.** Eğitimde boş
satır atlamak tasarruftur; DEĞERLENDİRMEDE satır atlamak KÜME DEĞİŞTİRMEKTİR.
(V19: atlanan 4 satır rastgele değil, sistematik olarak en ZOR pozitiflerdi --
geçmişi olmayan hücrede hedef penceresine düşen ilk olay.)

Karşılaştırmadan önce zorunlu doğrulama: iki modelin puanlandığı pozitif
KÜMESİ birebir aynı mı? Sayı eşitliği yetmez.

### İKİ TASARIM KURALI (kontrol yazarken)

**1. Sessiz başarısızlık her katmanda aynı düşmandır.** Bir engel, yasak bir
istek aldığında HATA vermeli; sessizce boş sonuç dönmemeli. Boş sonuç, yasak
denemesini gizler: yazan kişi "öznitelik hep sıfır çıkıyor" deyip devam eder ve
engel hiç görünmez. (`HistoryView.count_within(days<=0)` -> `LookaheadError`.)

**2. Kullanılabilirlik sınaması, güvenlik sınamasının PARÇASIDIR.** Doğru sonuç
vermeyen bir engel kullanılmaz; kullanılmayan engel korumaz. Bu yüzden her
engelin testleri arasında "mevcut hesapla aynı sonucu veriyor mu?" testi de
bulunur -- yoksa engel kurulur, kullanılmaz ve kurulu sanılır.

### TERS İLİŞKİ — düzenlileştirme sızıntıyı GİZLER

Aşırı öğrenmeye karşı alınan her önlem, aynı zamanda "az satırı etkileyen
sinyali" bastırır. Kısmi sızıntı tam olarak budur.

**Model ne kadar iyi korunursa, performans tabanlı sızıntı tespiti o kadar kör
olur.** Ölçüldü: `min_child_samples=200` ve 212 pozitifle, hedefin yarısını
doğrudan veren bir öznitelik AUC'yi +0,0000 değiştirdi
(`docs/KANARYA_BULGUSU.md`).

Sonuç: sızıntı tespiti performansa değil YAPIYA dayanmalıdır
(`src/features/history_view.py`). İki mekanizma birbirinin yerine geçmez;
düzenlileştirme arttıkça birincisi zayıflar, ikincisi etkilenmez.

### SINIR KAYDI — otomasyonun kapsamı sonludur

**Koruyucular izledikleri şeyi korur; diff okumanın yerini tutmaz.**

Somut örnek (24 Ağustos 2026): kirli-ağaç deneyinin temizlik adımı çalışmadı ve
deneyin artığı README'ye girdi, neredeyse commit'lendi. Sayı haritası koruyucusu
yakalayamazdı -- README izlenen dosya değil. Yakalayan şey, staged diff'in
okunmasıydı.

Bu satır, yukarıdaki dört elle-sınıfın beşincisi DEĞİLDİR; onların ortak
zeminini tarif eder: otomasyonun kapsamı her zaman sonludur ve kapsam dışı
insan gözüne kalır. Faz 3'te "koruyucular var, rahatız" moduna girildiği anda
lazım olacak satır budur.

**Ek kural (küçük ama tekrarlanabilir sınıf):** deney ve temizlik betiklerinde
`&&` zinciri kullanılmaz. Zincirin ortasındaki bir komut (örneğin eşleşmeyen
bir `grep`) başarısız olunca temizlik adımı SESSİZCE atlanır. Ayrı satırlar ya
da `trap cleanup EXIT` kullanılır.

## Faz 3'ten eklenenler — "koruma ile gerçeklik arasındaki boşluk" ailesi

V21, V22 ve kanıtsız atıf vakası aynı aileden: **bir koruma ya da beyan
mevcuttu, ama gerçeklikle arasında sessiz bir boşluk vardı.** Üçü de aynı
soruyla yakalanır: *"bu korumanın çalıştığını gösteren deney hangisi?"*

| formülasyon | nereden |
|---|---|
| **Eklenen koruma bir sonraki düzenlemede fiilen patladı — kural 9'un doğum kanıtı.** Koruma, kurulduğu turda değil, ilk gerçek kullanımında reddederek doğrulandı. | V21 |
| **Hata korumada değil, korumanın geçtiği yoldaydı.** Koruma reddedilseydi gerekçe "işe yaramadı" olurdu; gerçek gerekçe "başka bir yer onu varsayıyordu". | V22 |
| **Var olmayan bir teste atıf, kanıttan önce yazılmış iddiadır.** Açıklamada geçen her dosya adı, o dosyanın varlığıyla birlikte denetlenir. | `check_alarm` |
| **Uçtan uca prova, gerçek koşudan önce.** Sonuçlar üretilmişken çıkan bir çökme, üretilmiş sonuçları da götürür (NameError vakası). Sahte veriyle tam boru hattı provası bunu ucuza kapatır. | betik 22 |
| **Sayı eşitliği değil KÜME eşitliği.** İki kümede de 252 pozitif olması aynı 252 olduğunu göstermez; fark pozitifleri hiç etkilemese bile görülmelidir. "Etkisi yok ama görüldü ve gerekçelendi", "etkisi yok ve bilinmiyor"dan kategorik olarak farklıdır. | V19, hücre 4037 |
| **Bir koruma sabit bir alet değil, kalibre edilen bir ölçüm cihazıdır.** Kanaryanın saptama tabanı bölüme göre değişti (test 3-5 gün, doğrulama 2-3 gün); her kurulumda yeniden ölçülür. | kanarya künyesi |

## Güvenlik ağları ve kuralların uygulanması

### Hiç tetiklenmeyen koruma, TETİKLENEMEYEN korumadan ayırt edilmemiştir

Kural 9'un eğitim-döngüsü karşılığı. Erken durdurma, sabır parametresi,
gradyan kırpma, NaN koruması — hepsi **güvenlik ağıdır**. Bir ağ hiç devreye
girmiyorsa iki ihtimal vardır ve ayırt edilmemiştir:

    (a) gerek olmadı        (b) çalışmıyor / erişilemiyor

Ölçülmüş örnek (V28): erken durdurma 40 turun hiçbirinde tetiklenmedi.
Görünüşte "gerek olmadı"; gerçekte model yakınsamamıştı ve **"en iyi tur"
aslında "son tur"du.** Seçim mekanizması fiilen devre dışıydı: karşılaştırma
"kim yakınsadı"yı değil **"kim daha hızlı indi"yi** ölçüyordu.

Bu, V9 ailesinin (kuruluma bağlı sessiz hata) eğitim-dinamiği versiyonudur:
her parça doğru — sabır parametresi var, kayıp düşüyor, tur sayısı makul —
ama birleşim **yanlış soruyu** ölçüyor.

**Kural:** her koşuda güvenlik ağlarının tetiklenip tetiklenmediği
RAPORLANIR. Tetiklenmeyen ağ, raporda "hiç devreye girmedi" satırıyla görünür
ve gerekçesi sorulur.

### Kurallar teşhisin yerini TUTMAZ

> Bir kural, teşhis doğruysa doğru eylemi verir; **teşhissiz uygulanırsa
> yanlışı hızlandırır.**

Ölçülmüş örnek (V28): ilan paketinde "tahmin tutmuyorsa arama uzayı
küçültülür" maddesi vardı ve doğruydu — **bütçe kusurları için** yazılmıştı.
Buradaki kusur bütçede değil harcamanın içeriğindeydi (40 turun tamamı seviye
inişine gidiyordu). Maddeyi mekanik uygulamak, kusuru **yarı fiyatına satın
almak** olurdu.

**Kural:** bir kural uygulanmadan önce, kuralın varsaydığı teşhisin geçerli
olup olmadığı sorulur. "Kural böyle diyor" bir gerekçe değil, bir adımdır.

## Kurtarma kuralı — tesadüf tasarıma çevrilmelidir

> **Tesadüfen kurtaran şey, tasarıma çevrilmediği sürece bir sonraki sefer
> kurtarmaz.**

Ölçülmüş örnek (V38): veri hattı üç kaynağın ham dosyasını imha etti.
AFAD'ın 284 aylık ve KOERI'nin 57 yıllık önbellek dosyası dokunulmamıştı ve
**fiilî yedek** işlevi gördü — kimse onları yedek diye tasarlamamıştı.
EMSC'nin önbelleği yoktu ve ağa muhtaç kalındı.

**Aynı olayda iki kaynak önbellekten döndü, biri dönemedi.** Fark, tasarımda
değil tesadüfteydi.

Uygulama: önbellek dizinleri **resmî kurtarma katmanıdır**; ağdan çekilen her
şey önce önbelleğe, oradan birleştirmeye. Önbelleksiz kaynak bırakılmaz.

## Koruma yönü — çıktı kadar GİRDİ

Korumalar bir yöne bakar ve bakmadıkları yön uzun süre görünmez.

    YAYIN yönü   kirli ağaç · dil · şema · künye · hücre bandı
    GİRDİ yönü   (V38'e kadar BOŞTU)

V38'de hat kendi girdisini imha etti ve **hiçbir koruma yakalamadı** — çünkü
hepsi çıktıya bakıyordu.

> **Bir hat, çıktısı kadar girdisinin bütünlüğünden de sorumludur.** Veriyi
> tazeleyen her işlem, tazeleme sonrası verinin küçülmediğini ölçmelidir.

**Bir koruma seti tasarlarken sorulacak soru:** *bu korumalar hangi yöne
bakıyor, ve bakmadıkları yönde ne olabilir?*

## Altyapı kuralı — bileşen, gerekliliği ölçülmeden eklenmez

Denetim disiplininin **altyapı kararlarına** uygulanması.

> Bir bileşen (veritabanı, önbellek, görev kuyruğu, çatı) yalnızca
> **ölçülmüş bir ihtiyaç** varsa eklenir. "Standart mimari böyle" bir
> gerekçe değildir.

Ölçülmüş örnek: README §4'te FastAPI + PostgreSQL + PostGIS + Redis + Celery +
Next.js kayıtlıydı. Fiilî profil ölçüldü:

    yayımlanan çıktı   günde bir üretilen GeoJSON
    katalog            tek dosya, 304.168 satır
    zamanlanmış görev  bir tane

Bu profil için PostGIS, Redis ve Celery **gereklilik değil alışkanlıktır.**
Karar minimalist yığına çevrildi; reddedilen bileşenler **"ihtiyaç
doğduğunda"** statüsüne alındı — bu da ölçülebilir bir eşiktir.

**Bayat mimari kararı, bayat sayıdan farksızdır.** README §4 yazılmış ama
üretilmemiş bir mimariydi (`web/` klasörü `.gitkeep` dışında boştu);
dondurulmamış bir manşet gibi teyide açıldı.

## KATMAN AYRIMI — gözlemci gözler, koruyucu korur

> **Kayıt katmanının hata politikası, kaydettiği şeyin hata politikasından
> FARKLI olmalıdır.**

Ölçülmüş örnek (V41): zamanlanmış görevin sarmalayıcısı
`ErrorActionPreference = "Stop"` ile yazılmıştı. PowerShell 5.1'de yerel bir
programın stderr çıktısı ErrorRecord'a çevrilir ve "Stop" altında betiği
**anında sonlandırır**. Python'un hata mesajı stderr'e gitti, sarmalayıcı
öldü, **günlüğe hiçbir şey yazılmadı** — çıkış kodu 1, sebep görünmez.

**İroni:** sarmalayıcının var olma sebebi *"sessiz başarısızlık kalmasın"*dı.

**Doğru kuruluş:**

    koruyucu katman   DURDURUR   (pipeline'ın altı koruması)
    gözlemci katman   TANIKLIK EDER (sarmalayıcı: Continue, her şeyi kaydet)

Gözlemcinin durması, gözlemlenecek şeyi yok eder. Her katman kendi işini
yapar; gözlemci gözler, koruyucu korur.

**Genel uyarı.** Günlükleme/izleme altyapısı kuran her yerde aynı tuzak
vardır: aracın kendi hata politikası, izlediği sürecinkiyle karıştırılırsa
araç, en çok ihtiyaç duyulan anda susar.

## BEŞİNCİ EKSEN — ANLAM

Sızıntı taksonomisi dört eksenliydi (hedef · zaman · istatistik · rakip
cevabı). Beşincisi, hiçbirine benzemez ve sızıntı bile değildir:

| eksen | ne bozuk | kim yakalar |
|---|---|---|
| hedef · zaman · istatistik | **veri** | kanaryalar |
| rakip cevabı | **karşılaştırmanın kurgusu** | tasarımın okunması (V24) |
| **anlam** | **cümle** | **okuyucu gözüyle okuma** (V44) |

**Veri doğru, ölçüm doğru, künye doğru, kapsam beyanı doğru — cümle yanlış.**

Ölçülmüş örnek (V44): *"Marmara… olay sayısı düşük"* cümlesindeki sayı (6)
doğruydu ama okuyucu bundan *"Marmara'da deprem az oluyor"* sonucunu çıkarır.
Oysa Marmara'nın uzun vadeli olay yoğunluğu (0,523/derece²/yıl) Batı Anadolu
ile aynı düzeyde ve Kuzey Anadolu doğusundan yüksek. "Olay sayısı", bölgenin
tehlikesi değil **testin örneklemiydi.**

**Hiçbir otomatik ölçüm bu ekseni yakalayamaz.** Sayı doğru olduğu için
hiçbir kontrol ötmez.

    dördüncü eksen  ->  TASARIMIN okunmasıyla yakalanır
    beşinci eksen   ->  OKUYUCU gözüyle okumayla yakalanır

**Kural:** yayımlanan her sayının yanında **hangi soruyu cevapladığı** yazılır.
"6 olay" iki farklı soruyu cevaplayabilir — *bölgede ne kadar deprem oluyor?*
ve *testimizin örneklemi ne kadar?* — ve ikisi **zıt** sonuçlara götürür.

## YOKLUĞUN TEMSİLİ — aynı ayrımın dört yüzü

> **"Değer yok" bilgisi, sayısal bir değere çevrildiği anda bozulur.**

Aynı hata üç kez, üç ayrı kılıkta çıktı. Dördüncüsü de gelecek; eşleşme adresi
burasıdır.

| kılık | yanlış temsil | doğrusu | vaka |
|---|---|---|---|
| geçmişi olmayan hücre | sayım = 0 **ve** istatistik = 0 | sayım 0, istatistik **NaN** | doldurma kuralı |
| nöral ağa NaN girdi | `nan_to_num(0)` → "b-değeri sıfır" | **gösterge sütunu** + medyan | V27 |
| temel modelde olmayan hücre | `normal=0` → oran = **inf** | oran **NaN**, hücre elenir | V40 |
| *(dördüncüsü)* | | | |

**Neden tehlikeli.** Her seferinde yokluk, karşılaştırmada **uç bir değer**
gibi davranıyor: sıfır her eşiğin altında, sonsuz her eşiğin üstünde. `NaN`
ise hiçbir karşılaştırmayı geçmez — ve doğru davranış budur, çünkü tanımsız
bir değer hakkında hüküm verilemez.

**Kural:** yokluk bir sayıya çevrilecekse, çevrildiği yer **açıkça beyan
edilir** ve karşılaştırmada nasıl davrandığı ölçülür.

## "KAÇ HATA VARDI?" — teşhis protokolüne eklenti

Bir düzeltmeden sonra sorun sürüyorsa, ilk soru **"düzeltme işe yaramadı mı?"
DEĞİLDİR** — o soru **tek-hata varsayımı** taşır.

> Sorulacak soru: **"kaç hata vardı?"**

Ölçülmüş örnek (V37 → V38 → V40 zinciri): eşik teyidi iki kez "AYRIŞMA"
verdi. Birinci koşuda gerçek bir hata vardı (katalog imhası) ve **betiğin
kendi kusuru onun arkasına gizlendi**. Katalog düzeltilince kusur tek başına
kaldı ve ancak o zaman görülebildi.

> **Bir hata, başka bir hatanın arkasına gizlenebilir.** Büyük olan
> düzeltildiğinde küçük olan ortaya çıkar — ve o an "düzeltme başarısız"
> denirse, ikinci hata birincinin gölgesinde kalır.

## Negatif beyan kuralı — üç uygulaması

> **Her negatif beyan, aracın o beyanı yapabilecek güçte olduğu gösterilerek
> ya da gücünün sınırı yazılarak anlam kazanır.**

Aynı kural, üç ayrı katmanda:

| beyan | eksik olmadan anlamsız | ölçüm |
|---|---|---|
| "fark yok" | **MDE** | saptanabilir en küçük etki |
| "alarm yok" | **saptama tabanı** | dedektörün gördüğü en küçük sızıntı |
| "teşhis edilemedi" | **veri kapsamı** | teşhisin dayandığı kaydın sınırı |

Üçü de aynı hatayı önler: **aracın sessizliğini, dünyanın sessizliği sanmak.**

### Beyanın ZAMANI, statüsünü belirler

Aynı bilgi, ne zaman söylendiğine göre kategori değiştirir:

    SONRA söylenirse   -> savunma  ("elimizde yoktu")
    ÖNCE söylenirse    -> kapsam   ("teşhis şu sınırla yapılabilir")

Ölçülmüş örnek: `npp_arama.jsonl` tur-bazlı geçmişi saklamamıştı. Bu eksik,
teşhis gerekmeden **önce** yazıldı (`docs/NPP_ILAN.md`, "Aşama 1'in üç
çıktısı") ve böylece bir mazeret değil, teşhisin ilan edilmiş sınırı oldu.

Aynı ilke test-peek bildiriminden beri işliyor: görülen sayı, görüldüğü anda
beyan edilirse zaman çizgisi denetlenebilir kalır.

## İki kapanış ilkesi

### 1. Bir bulgu, SINIFI taranmadan kapatılmaz

> Tekil bir kusur düzeltildiğinde sorulacak soru düzeltmenin doğruluğu değil,
> **"bu bulgunun sınıfı nedir ve o sınıfın başka örneği var mı?"**dır.

Sınıf taranmadan kapatılan bulgu, aynı sınıfın diğer örneklerini **görünmez
kılar** — çünkü "o sorun çözüldü" duygusu aramayı durdurur.

Ölçülmüş örnek: V26 (ölçekleme kapsamı) tekil olarak kapatılsaydı, aynı
sınıftan iki kusur daha koşuya girecekti — eksik `poisson_rate` özniteliği ve
NaN→0 dönüşümü (V27). İkisi de **hata üretmeden** sonucu geçersiz kılardı.

**Kapanış şartı:** her tekil bulgunun sınıfı taranmış olacak.

### 2. Denetimin çıktısı, kusur listesi DEĞİL; kusur + TEMİZLİK KANITLARI

> Temiz çıkan bir kalem, denetlenmemiş bir kalemle aynı şey değildir.

Taşıma denetimi tablosunun beşinci satırı (Poisson temel modelin dönemi:
1990-2016, test görünmüyor) bir kusur değildir — ama tabloda durur, çünkü
ikisi birlikte **"neresi denetlendi" haritasını** verir. Yalnızca kusurları
listeleyen bir denetim, kapsamını gizler.

Bu satırın beklenmedik kazancı: `poisson_rate`'in test dönemi görmediğinin
doğrulanması, **Faz 3'ün sonuçlarını da geriye dönük sağlamlaştırdı** (SHAP
payı %52,5 olan öznitelik temiz).

## SIZINTI TAKSONOMİSİ — dört eksen

İlk üç eksen **veri** üzerindedir ve kanaryalarla aranır. Dördüncüsü
**karşılaştırmanın kurgusu** üzerindedir ve kanaryalara GÖRÜNMEZ.

| eksen | ne sızar | kim yakalar |
|---|---|---|
| hedef | cevabın kendisi bir öznitelikte | kanarya 1 (KABA) |
| zaman | referans sonrası veri | katman 1 (yapısal) + kanarya 2 |
| istatistik | ölçekleme/normalizasyon sabitleri | kanarya 3 (yalnızca ölçeğe duyarlı modellerde) |
| **rakip cevabı** | **karşılaştırılan modellerden birinin ÇIKTISI, diğerinin tasarımına** | **hiçbir kanarya — yalnızca tasarımın okunması** |

### Dördüncü eksen neden görünmez

Performans ölçümleri bunu göremez çünkü sızıntı **performansı artırır** ve
artış meşru bir iyileşmeden ayırt edilemez. Veri temizdir, zaman temizdir,
ölçek temizdir; kirli olan **karşılaştırmanın kurgusudur.**

**Kontrol listesi sorusu (her karşılaştırmadan önce):**

> Karşılaştırdığım iki modelden birinin cevabı, diğerinin girdisine, öznitelik
> seçimine, örnekleme kuralına ya da hiperparametre uzayına giriyor mu?

**Genelleme:** adillik ihlalleri performans testlerine görünmez. Onları
yakalayan tek şey, karşılaştırma tasarımının **bağımsız gözle okunmasıdır** —
ve bu okuma, kod yazma anında kendiliğinden gelen "bunu neye göre yapıyorum?"
sorusuyla tetiklenir (V24 böyle bulundu).

### Bir analiz aracı, tasarım kuralına dönüştüğü an denetlenmelidir

Aynı formül, ölçüm bağlamında masum, girdi bağlamında sızıntıdır. Aracın
kendisi değil, **nereye bağlandığı** belirler.

## Metrik notları — bir skorun tek başına ne söyleyemediği

### IG tek başına okunmaz; KALİBRASYON ORANIYLA birlikte okunur

Faz 3'te görüldü: ML'nin Poisson'a karşı toplam IG'si (+1,086) ETAS'ınkini
(+1,068) geçiyordu. Ayrıştırma tersini gösterdi:

    ML - ETAS  +0,018  =  OLAY -0,350  +  MARUZİYET +0,368

ML **gerçekleşen olaylarda daha kötüydü**; toplam üstünlüğü, toplamı 1,82 kat
eksik tahmin etmesinin maruziyet terimindeki ödülünden geliyordu.

Rhoades IG'nin maruziyet terimi `-(sum b - sum a)/N`, az tahmin edeni
ödüllendirir. Teoride optimum doğru kalibrasyondadır (saf ölçek kaymasının
bedeli `ln c + 1 - c < 0`), ama şekil farkı bu bedeli örtebilir. Sonuç:
**kalibre olmayan bir model toplam skorda önde görünebilir.**

**KURAL.** IG raporlanan her yerde, yanında şu ikisi bulunur:

    gözlenen / beklenen oranı  (her model için)
    IG'nin OLAY ve MARUZİYET terimlerine ayrışması

Yoksa "hangi model daha iyi" sorusuna verilen cevap, "hangi model daha az
tahmin ediyor" sorusunun cevabı olabilir.

### Bir ölçüt, tek bir sayıyla karar veremeyebilir

36'lık dağılımın "dar mı geniş mi" sorusu için tek bir oran (yayılım/saçılım)
ilan edilmişti. Ölçüm, uzayın **ölçeğe bağlı** olduğunu gösterdi: küresel
olarak yapılı (iki eksenin etkisi saçılımın 3-4 katı), yerel olarak düz (ilk üç
bileşim ayırt edilemez). Tek skaler ikisini birden ifade edemiyordu.

**KURAL.** Bir ölçüt ilan edilirken, ölçülen büyüklüğün **tek bir ölçekte**
tanımlı olup olmadığı sorulur. Değilse ölçüt ölçek başına ayrı ilan edilir.

## Belgeler

| belge | ne için |
|---|---|
| `VAKA_DEFTERI.md` | 14 vaka: ne oldu / nasıl bulundu / örüntü / geriye kalan |
| `SAYI_HARITASI.md` | her sayının kurulumu; geçerli/geçersiz ayrımı |
| `KABUL_OLCUTLERI.md` | önceden ilan edilen ölçütler, Ö4 yorum kuralları, dondurma sonrası liste |
| `MEKANIZMA_BULGUSU.md` | doğrulama hiyerarşisi dersi (§6), belirsizliğin büyümesi (§8), gürültü ve anlatı (§9) |
| `MANSET.md` | dondurulmuş sonuçlar, künyeli |
| `CELLID_BEKLENEN_ETKI.md` | beklenen/gerçekleşen karşılaştırmasının örneği |

## Sayılarla

    59 test          | 14 vaka (13 başlık; V11/V12 ortak)  | 1 pre-commit hook
    13 hata sınıfı   | 9 otomatik/yapısal | 4 elle ya da açık
    10 zorunlu kural | 4 bilinen boşluk

    (Bu sayılar doğrulanmıştır: test sayısı pytest --collect-only ile, vaka
    sayısı defterin başlıklarından, tablo sayıları satır sayımıyla.)

Bu belgenin başarı ölçütü, araç sayısı değil: **Faz 3'te bulunan bir hatanın,
buradaki bir satırla "bu sınıftan" diye eşleştirilebilmesi.** Eşleşmiyorsa yeni
bir sınıf bulunmuştur ve tabloya eklenmelidir.
