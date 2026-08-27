# Vaka defteri — kod tabanının hafızası

Bu projede en pahalı hatalar sessiz olanlardı: istisna fırlatmayan, çıktı üreten,
makul görünen hatalar. Her biri bir örüntüye ait ve o örüntü bir daha
tekrarlanabilir.

Sözlü gelenekte kalan vakalar ilk unutulanlardır. Bu defter onları yazıya
geçirir; `docs/DENETIM_MIRASI.md` buradan beslenir.

Kayıt biçimi: **ne oldu / nasıl bulundu / hangi örüntü / ne kaldı geriye.**

---

## V1 — Zaman birimi 1000 kat yanlış (denetim ÖNCESİ)

**Ne oldu.** Öznitelik pencerelerinde `astype("int64") / 1e9` kullanılıyordu;
nanosaniye varsayımı. pandas bu kataloglarda çözünürlüğü MİKROSANİYE seçiyor,
dolayısıyla bölme 1000 kat yanlış ölçek üretiyordu: 30 günlük pencereler 30.000
gün olarak uygulanıyordu.

**Nasıl bulundu.** Hedef etiketlerde `target_30d` ile `target_90d` TAM OLARAK
aynı çıktı. İki farklı pencere aynı sonucu veriyorsa pencere uygulanmıyor
demektir.

**Örüntü.** Kütüphanenin örtük varsayımına güvenmek. Hiçbir hata verilmedi;
sayılar makul göründü.

**Geriye kalan.** `catalog_io.epoch_seconds` tek dönüşüm noktası oldu ve
`test_epoch_seconds_is_real_seconds` bunu sabitliyor. Bu denetimde blok
bootstrap düzeltilirken aynı kanal (`astype("int64")`) bir kez daha görüldü ve
takvim tabanlı hesapla tamamen kapatıldı (bkz. V9).

## V2 — Tekilleştirme zinciri kataloğu kesti (denetim ÖNCESİ)

**Ne oldu.** Yakın olayları eleyen kural zincirleme çalışıyordu: A, B'yi eledi,
B C'yi eledi... 6-7 Şubat 2023'te 580 olay 69'a düştü ve M7,5 Elbistan
kayboldu.

**Nasıl bulundu.** Dizi günlerinde olay sayısının fizik dışı düşük olması.

**Örüntü.** Yerel olarak doğru bir kuralın küresel etkisinin ölçülmemesi.

**Geriye kalan.** Tekilleştirme yalnızca kaynaklar ARASI, bire bir ve
`|dMw| <= 1` koşuluyla yapılıyor.

## V3 — `consumed` bayrağı bloklar arası taşındı (denetim ÖNCESİ)

**Ne oldu.** Tekilleştirmede kullanılan bayrak zaman blokları arasında
sıfırlanmıyordu; 39.495 kopya (kataloğun %11,5'i) elenmeden kaldı.

**Nasıl bulundu.** EDA defterindeki "aynı saniyede birden çok olay" kontrolü.

**Örüntü.** Döngü değişkeninin yaşam süresini yanlış varsaymak.

## V4 — `mc="positive"` yanlış fonksiyona yazıldı (denetim ÖNCESİ)

**Ne oldu.** STAI-dayanıklı kip `invert()` içine eklendi, ama paralel işçiler
`_build_calc()` kullanıyordu. İki saatlik kalibrasyon HATA VERMEDEN eski
ayarla çalıştı ve **birebir aynı** sayıları üretti.

**Nasıl bulundu.** Sonuçların değişmemesi. Değişmesi beklenen bir şey
değişmiyorsa değişiklik uygulanmamıştır.

**Örüntü.** Aynı yapılandırmanın iki yerde kurulması.

**Geriye kalan.** `etas_config()` tek kaynak oldu; `test_etas_config_is_single_source`
kaynak kodunu tarayıp iki kurulum olmadığını doğruluyor.

## V5 — Tohum saçılımı ölçütü Coulomb'u "anlamlı" gösterdi (denetim ÖNCESİ)

**Ne oldu.** Jeofizik katman ablasyonunda ölçüt "fark, tohumlar arası
saçılımın iki katından büyük mü?" idi. Coulomb bu ölçüte göre KATKI VAR çıktı;
15 tohumla Welch p = 1,4e-13.

**Nasıl bulundu.** p-değerinin neyi ölçtüğü sorgulandı: tohum p-değeri yalnızca
TEKRARLANABİLİRLİĞİ ölçer. Asıl belirsizlik test setindeki 66 olaydan gelir.
Olay bazlı bootstrap yapıldığında aralık sıfırı içeriyordu.

**Örüntü.** Yanlış belirsizlik kaynağını ölçmek.

**Geriye kalan.** Ablasyonun asıl sınaması olay bazlı bootstrap. Bu vaka,
denetim mirası belgesinin gerekçesidir: araçların neden var olduğunun en somut
kanıtı, yokluklarında neredeyse yapılacak olan hatadır.

---

## V6 — CSEP sonuçları bayatladı (denetim İÇİNDE)

**Ne oldu.** `csep_results.json` 23 Ağustos 02:41'de üretilmişti; STAI yeniden
kalibrasyonu aynı gün 18:58'de yapıldı. README'de duran +2,287 eski
parametrelere aitti.

**Nasıl bulundu.** Dosya zaman damgalarının karşılaştırılması.

**Geriye kalan.** `docs/SAYI_HARITASI.md` ve onu bayatlamaktan koruyan
pre-commit hook.

## V7 — Monte Carlo tabanı 3,42 kat şişikti (denetim İÇİNDE)

**Ne oldu.** Taban, Zaliapin ayrıştırmasından gelen ana şok oranıydı; o oran
olayların %61,3'ünü ana şok sayıyor, oysa ETAS'ın arka plan payı %17,9.
Pozitif hücrelerin %53'ünde simülasyon oranı sıfır olduğu için raporlanan
kazancın büyük kısmını bu şişik taban taşıyordu.

**Nasıl bulundu.** İki bağımsız kurulumun (arşiv ve günlük) farklı yönlerde
kalibrasyon hatası göstermesi.

**Örüntü.** Bir düzeltmenin (taban) sonucu belirleyecek kadar büyük olması.

## V8 — Kaynak konumu hücre merkezine oturtuluyordu (denetim İÇİNDE)

**Ne oldu.** Hücre düzeyinde ortanca %20, uçta %121 sapma. Toplamda %0,3 —
çünkü kütleyi koruyordu.

**Nasıl bulundu.** Toplam testlerinin HEPSİ geçti (Ö1, Ö2, kütle, yakınsama);
yalnızca ölçüt bile olmayan hücre korelasyonu gösterdi.

**Örüntü.** Toplam-düzeyi testler hücre-düzeyi kusurlara kördür.

## V9 — Blok bootstrap kuruluma bağlı olarak sessizce yanlış (denetim İÇİNDE)

**Ne oldu.** Bloklar takvim zamanından değil, benzersiz gün dizisindeki
İNDİSTEN kuruluyordu. Günlük başlangıçlarda doğru (37 blok); haftalık
başlangıçlarda 202 başlangıç 7 BLOĞA düşüyordu.

**Nasıl bulundu.** "Blok uzunluğu otomatik mi, sabit mi?" sorusu koda bakmayı
gerektirdi. Sayıya bakarak bulunamazdı.

**Örüntü — BU PROJEDEKİ EN TEHLİKELİ SINIF: beklentiyle uyuşan hatalı sonuç.**
Yedi bloklu bootstrap geniş aralık verirdi; ben de o aralığı "az bağımsız
bilgi" diye yorumlayacaktım. Doğru anlatıya sahte kanıt. Öngörüyle uyuştuğu
için kimse ikinci kez bakmazdı.

**Geriye kalan.** Blok kimliği takvimden türetiliyor; 5 test. Doğrulandı:
günlük kurulumda bölümleme BİREBİR AYNI (37 blok), yani eski günlük sonuçlar
bu hatadan etkilenmemiştir.

## V10 — Neredeyse doğru mutlaklık (denetim İÇİNDE)

**Ne oldu.** "Hiçbir hücrede oran sıfır değil" yazıldı. 378.880 satırda sıfır
oran YOKTU (doğru), ama değerlendirme ızgarasının 2 hücresi tahmin ızgarasının
dışındaydı.

**Örüntü.** İddia %99,9 doğruydu ve tehlike tam olarak o %99,9'daydı:
neredeyse-doğru bir mutlaklık, yanlış olandan daha uzun yaşar çünkü kimse
sınamaz.

## V11 / V12 — Koruyucunun kendi vakaları (denetim İÇİNDE)

Sayı haritası koruyucusu kurulumundan 3 dakika sonra kendi yazarını durdurdu;
ertesinde `config.py` değişikliğinde bir kez daha. Künye üreteci de ilk
çalıştırmada kendisini "kirli ağaç" diye damgaladı.

**Ortak ders.** Her üç vakada da cevap "etki yok" çıktı ve her üçünde de bunu
ÖLÇEREK öğrendik. Bir kontrolün değeri yakaladığı hatalar değil, zorunlu
kıldığı ölçümlerdir — ve kendi yazarını durdurması, gerçekten çalıştığının en
ucuz kanıtıdır.

## V13 — Ara duruma uydurulan tasarım gerekçesi (denetim İÇİNDE)

**Ne oldu.** Haftalık üretim sürerken ara sayım 202 gösterdi. Bu sayı,
"208 başlangıcın 202'si; ilk 7'si beş yıllık geçmiş penceresi nedeniyle
değerlendirmeye girmiyor" diye açıklandı. **Böyle bir dışlama yoktu.** 202,
üretimin o anki ara durumuydu; nihai sayı 208 ve eksik başlangıç yok.

**Nasıl bulundu.** "Bu açıklama şu an beyan durumunda, doğrula" denmesi
üzerine sayının kaynağına bakıldı.

**ÖRÜNTÜNÜN ADI: SAYIYA GEREKÇE UYDURMA.** Bir tutarsızlık görüldüğünde zihin
ölçmek yerine makul bir hikâye üretir; hikâye makul olduğu için kimse sınamaz.
Bu bir ölçüm hatası bile DEĞİLDİR -- var olmayan bir tasarım kuralının,
açıklanamayan bir sayıyı açıklamak için icat edilmesidir. V9'da hata koddaydı;
burada doğrudan anlatıdaydı.

**NASIL YAKALANDI -- kayda değer.** Bir kontrol mekanizması yakalamadı. Yakalayan
şey, "teslimde ayrıca doğrulayacağım" diye BEYAN EDİLEN bir doğrulamanın takip
edilmesiydi. Beyan edilen her doğrulamanın takibi, uydurulan gerekçelerin doğal
avcısıdır: gerekçe uyduran kişi, onu doğrulamayı da vaat eder ve o vaat
tutulduğunda gerekçe çöker.

**Ne kadar yakındı.** Bu cümle teslim paketine girseydi, "dışlama kuralı"
diye var olmayan bir tasarım kararı belgeye geçecekti ve sonraki her okuyucu
onu gerçek sanacaktı.

**Geriye kalan.** Sayı üreten her ifade için tek kural: sayının nereden
geldiği gösterilmeden gerekçesi yazılmaz. Ara durumlar özellikle tehlikeli --
çünkü nihai sonuç gibi görünürler ve makul bir açıklamayı davet ederler.

## V14 — Gürültünün gerçek etkiyi MASKELEMESİ (V9'un ayna görüntüsü)

**Ne oldu.** Günlük kurulumda ETAS ile Poisson arasındaki AUC farkı +0,0545
[−0,038; +0,127] ile anlamsızdı ve "modeller ayrıştırılamıyor" diye
yorumlanmaya hazırdı. Analitik kurulumda aynı fark **+0,1407 [+0,076; +0,214]**
çıktı: anlamlı ve iki buçuk kat büyük.

**Neden.** Günlük kurulumda pozitif hücrelerin 799/1496'sında simülasyon oranı
sıfırdı; analitik kurulumda 0/252. Sıralama, Monte Carlo gürültüsü tarafından
bozuluyordu.

**Örüntü — V9'UN AYNASI.** V9'da beklentiyle uyuşan SAHTE bir sonuç vardı;
burada beklentiyi ÇÜRÜTEN gerçek bir sonuç var ve gürültü temizlenince
göründü.

İkisi birlikte tek dersi veriyor: **gürültü yalnızca belirsizlik eklemez, işaret
de üretir ve işareti yok da eder.** Bir "fark gösterilemedi" sonucu, ölçüm
aracının çözünürlüğü sorgulanmadan kabul edilemez -- nitekim bu projede
"ayrıştırılamıyor" anlatısı iki kez kurulmaya çalışıldı ve ikisinde de sebep
modelin kendisi değil, ölçüm aracıydı.

**Geriye kalan.** MDE kuralı bu dersin kurumsallaşmış hâlidir: "fark
gösterilemedi" asla tek başına raporlanmaz.

## V15 — Koruyucunun en kritik izlemesi BOŞTU (dondurma sonrası 1b)

**Ne oldu.** Sayı haritası koruyucusu `etas_params.json`'ı izleme listesinde
tutuyordu -- künyedeki sha'nın kaynağı, bayat sayı vakasının (V6) çıkış noktası,
listedeki en kritik dosya. Ama o dosya **gitignore edilmişti ve izlenmiyordu.**

Koruyucu `git diff --name-only` çıktısına bakar. Git, izlenmeyen bir dosyayı o
çıktıda **hiçbir zaman** listelemez. Yani parametre dosyası değiştiğinde
koruyucu tetiklenmiyordu.

**Nasıl bulundu.** Dondurma sonrası 1b işi (çıktı json'larının künye zinciri)
için `git ls-files` ile hangi json'ların izlendiğine bakıldı. `etas_params.json`
listede yoktu.

Sonra DENEY yapıldı: dosya değiştirildi, koruyucu çalıştırıldı, **0 (geç)**
döndü. Düzeltmeden sonra aynı deney **1 (reddet)** döndü.

**Örüntü — ÜÇ DOĞRU İFADE VE BİR BOŞ KORUMA.** Şunların üçü de doğruydu:

* `etas_params.json` izleme listesindeydi (`WATCHED`)
* `test_params_file_is_watched` geçiyordu
* pre-commit hook kuruluydu

Ve koruma yine de boştu. Çünkü hiçbiri LİSTE ile MEKANİZMANIN fiilen örtüştüğünü
sınamıyordu. Bu, V10'un ("neredeyse doğru mutlaklık") kontrol mekanizmalarındaki
karşılığıdır: **bir korumanın kurulu olması, çalıştığı anlamına gelmez.**

**Ne kadar yakındı.** Koruyucu 24 Ağustos'ta kuruldu ve iki kez tetiklendi
(V11/V12) -- ikisi de KOD dosyalarındaydı. Parametre dosyası o gün
değişmediği için boşluk görünmedi. Faz 3'te yeniden kalibrasyon yapılacak ve
tam o an koruma olmayacaktı; yani boşluk, en çok ihtiyaç duyulacağı anda ortaya
çıkacaktı.

**Geriye kalan.** Yedi sonuç/parametre json'ı artık izleniyor. İki yeni test:
`test_every_watched_path_is_git_tracked` (liste ile mekanizmanın örtüşmesi) ve
`test_result_jsons_are_tracked` (künye zinciri). Toplam koruyucu testi: 9.

**Genel ders:** bir kontrolün testleri, kontrolün KENDİSİNİ değil VARLIĞINI
sınıyorsa boştur. "Listede mi?" sorusu "görebiliyor mu?" sorusunun yerine
geçemez.

**ZAMANLAMA DERSİ.** Boşluğun ne zaman patlayacağı ÖNGÖRÜLEBİLİRDİ:
`etas_params.json` denetim boyunca sabitti, bu yüzden koruma hiç sınanmadı.
Faz 3'te yeniden kalibrasyon yapılacak ve dosya değişecekti; boşluk tam o an
ortaya çıkacaktı.

**İzlenmeyen bir dosya, en çok değişeceği dönemde en tehlikelidir** -- çünkü
sessiz kaldığı dönemde koruma da sınanmaz. Bu, "1b'yi 3'ten önce yap" kararının
beklenmedik gerekçesi oldu: açık uçlu araştırmaya girmeden mekanizma
boşluklarını kapatmak, boşluğun en kötü anda patlamasını engelledi.

Bu dersten doğan kural: **zorunlu kural 9 -- kurulum kanıtı değil, ÇALIŞMA
kanıtı.** Bir koruyucu, bir şeyi REDDETTİĞİNİ gösteren bir deney olmadan
"kurulu" sayılmaz.

## V16 — "Rastgelelik YOK" beyanı EKSİKTİ (operasyonel geçiş)

**Ne oldu.** Künye "rastgelelik: YOK — analitik hesap deterministik" diyordu ve
`test_result_is_bit_identical_across_runs` geçiyordu. Operasyonel geçişte aynı
gün iki kez çalıştırıldı: **çıktılar farklı çıktı.**

**Nasıl bulundu.** Beklenen etki belgesinde (kural 8) "iki kez çalıştırma:
analitik çıktı birebir aynı mı" ölçülecekler listesindeydi. Ölçüldü ve tutmadı.

**Kaynak.** İkiye ayırınca görüldü:

    expected_counts, AYNI parametrelerle    : birebir aynı ✓
    local_params, iki çağrı                  : log10_mu FARKLI
        -6.54154000821231  vs  -6.5415908942714065
    sonuç: oranlarda bağıl 1,2e-04 fark

Rastgelelik dallanma hesabında DEĞİL, ETAS **durumunu kuran** adımdaydı
(`_calculation_at` -> paketin EM adımı).

**Örüntü.** Testin sınadığı şey ile beyanın kapsadığı şey ayrışmıştı: test
`expected_counts`'u sınıyordu (deterministik), beyan ise UÇTAN UCA hesabı
kapsıyordu (değil). V15'in ("kontrol kurulu ama kör") kardeşi: **test doğruydu,
beyan testin kapsamından genişti.**

**Ne kadar yakındı.** Değerlendirme yolunda `local_params` yalnızca bir kez
çağrılıyor ve sonucu tüm hesapta kullanılıyor; o yüzden Ö1/Ö2'de görünmedi.
Operasyonel üretim her gün yeniden çalışacaktı ve yayımlanan tahminler
yeniden üretilemez olacaktı -- künye "deterministik" derken.

**Geriye kalan.** `local_params` artık `deterministic_simulation` bağlamında
çalışıyor; tohum aynı kuraldan (başlangıç tarihinden) geliyor. Uçtan uca
doğrulandı: `log10_mu` birebir aynı, çıktı birebir aynı.


## V17 — Kanaryanın kendisi kanaryalandı (Faz 3, kurulmadan ÖNCE)

**Ne oldu.** Sızıntı tespiti için performans tabanlı bir alarm kuruldu (skor
şüpheli derecede iyiyse dur). Alarma bilinen sızıntılar verildi:

    temiz                              0,7665
    ref+1 gün, M>=Mc (zayıf)           0,7697  (+0,0032)  alarm YOK
    ref+15 gün, M>=5,0 (YARIM pencere) 0,7665  (+0,0000)  alarm YOK
    ref+30 gün, M>=5,0 (TAM pencere)   1,0000  (+0,2335)  alarm VAR

Yarım pencere sızıntısı hedefin YARISINI doğrudan veriyor ve hiçbir iz
bırakmıyor.

**Kök neden.** `min_child_samples=200`, eğitimde 212 pozitif. 200 satırdan az
etkileyen sızıntı yaprak oluşturamıyor, skoru değiştirmiyor, alarm çalmıyor.
Tam pencere 212 satırla eşiği KIL PAYI geçtiği için görünüyor; bagging 0,8
eklendiğinde 212 bile ~170'e düşüyor ve o da görünmez oluyor.

**Örüntü — V15 ailesinin üçüncüsü, ama bir FARKLA.** V11/V12'de koruyucu
kurulmuş ve kendi yazarını durdurmuştu; V15'te koruma listedeydi ama mekanizma
kördü; burada dedektörün KENDİSİ kör çıktı. Fark şu: **bu kez körlük,
mekanizma kurulmadan ÖNCE bulundu.** Kanarya dağıtılsaydı "alarmımız var"
sanılacaktı.

Sıralamayı değiştirip sızıntı işini 1. sıraya almak (Faz 3 planı) kendini
burada amorti etti.

**Genel ders.** Düzenlileştirme sızıntıyı gizler: aşırı öğrenmeye karşı her
önlem, az satırı etkileyen sinyali bastırır ve kısmi sızıntı tam olarak odur.
Model ne kadar iyi korunursa performans tabanlı tespit o kadar kör olur.

**Geriye kalan.** Yapısal engel: `src/features/history_view.py`. `HistoryView`
kurulurken katalogu `t < ref` ile keser ve YALNIZCA kesilmiş kısmı taşır --
erişim denetimi değil, verinin yokluğu. `__slots__` ile sonradan ham veri
iliştirmek de engellenir. Kural 9 gereği reddettiği deneylerle mühürlendi
(6 test). Performans kanaryası kaldırılmadı ama etiketi değişti: "kaba sızıntı
+ boru hattı sağlık kontrolü".

## V18 — Hizasız zaman ızgarası: karşılaştırmayı sessizce boşa çıkaran tuzak

**Ne oldu (yakalandı, yaşanmadı).** LightGBM'in ETAS'la aynı başlangıçlarda
yarışması için öznitelikler haftalık referanslarla üretilecekti. Doğal seçim
`pd.date_range('1995-01-01', ..., freq='7D')` idi.

Ölçüldü: o ızgaranın ETAS'ın 208 başlangıcıyla **ORTAK NOKTASI SIFIR**.
1995-01-01 ile 2021-01-01 arası 9497 gün ve 7'nin katı değil; iki haftalık
ızgara birbirinden 3-4 gün kayık ilerliyor ve hiç kesişmiyor.

    naif ızgara  (1995-01-01 başlangıçlı): 1565 referans, ETAS ile ortak   0/208
    hizalı ızgara (1995-01-06 başlangıçlı): 1564 referans, ETAS ile ortak 208/208

**Ne olurdu.** LightGBM eğitilir, test edilir, makul bir AUC verirdi. ETAS ile
karşılaştırılırdı. Ve iki model **hiçbir ortak başlangıçta ölçülmemiş**
olurdu -- karşılaştırma hatasız görünüp anlamsız olurdu.

**Nasıl yakalandı.** "Eşit bilgi" maddesi plana yazılırken "aynı başlangıç
kümesi" satırı vardı; üretime geçerken o satırı ÖLÇTÜM (kesişim sayısı) --
varsaymadım.

**Örüntü.** İki ızgaranın "aynı sıklıkta" olması, "aynı noktalarda" olması
demek değildir. Sıklık eşitliği hizalama eşitliği sanılır; kayma sessizdir
çünkü her iki ızgara da kendi içinde kusursuzdur.

**Geriye kalan.** Referans ızgarası ETAS başlangıcına DEMİRLENEREK üretilir
(`end=anchor, periods=N, freq='7D'` ile geriye doğru). Üretim sonrası zorunlu
doğrulama: LightGBM tablosundaki pozitif hücre-pencere KÜMESİ, ETAS
değerlendirmesindekiyle birebir aynı olmalı -- sayı eşitliği değil, KÜME
eşitliği.

## V19 — Değerlendirme asimetrisi: "geçmişi yok" bilginin yokluğu sanıldı

**Ne oldu (yakalandı, yaşanmadı).** Haftalık öznitelik tablosu üretildi ve
zorunlu doğrulama koşuldu: LightGBM tablosundaki pozitif hücre-pencere kümesi,
ETAS değerlendirmesindekiyle **birebir aynı olmalı**.

    ETAS pozitif    : 252
    LightGBM pozitif: 248
    fark            : 4 pozitif, hepsi ETAS'ta var LightGBM'de YOK

**Kök neden.** `grid_features`, bir hücrede İLK olaydan önceki referansları
atlıyordu ("bilgisizdir"). O dört pozitifin hücrelerinde Mc üstü ilk olay TAM
DA HEDEF PENCERESİNDEYDİ; dolayısıyla o (hücre, referans) çiftlerinin öznitelik
satırı yoktu ve ML orada hiç puanlanmayacaktı.

ETAS ise onları puanlıyor -- arka plan oranı her hücrede vardır.

**Ne olurdu.** ML, dört ZOR pozitifin çıkarıldığı daha kolay bir alt kümede
ölçülürdü. AUC farkı ML lehine kayardı ve karşılaştırma sessizce yanlı olurdu.

**Örüntü.** "Geçmişi yok" BİR BİLGİDİR, bilginin yokluğu değildir. Eğitimde
boş satırları atlamak makul bir tasarruftur; DEĞERLENDİRMEDE aynı tasarruf,
iki modeli farklı kümelerde ölçmek demektir.

**Nasıl yakalandı.** Küme eşitliği doğrulaması koşu ÖNCESİ zorunlu kılınmıştı
(sayı eşitliği değil, KÜME eşitliği -- sayı eşit olsaydı da fark
görülebilirdi).

**Geriye kalan.** `grid_features` artık `--all-refs` ve
`--cells-from-baseline` kiplerini destekliyor; değerlendirme tablosu ETAS'ın
ızgarasının aynısını kapsıyor. Doğrulandı: 252 = 252, kümeler birebir.

**Kalan küçük fark:** LightGBM tablosunda bir fazla hücre var (4037,
36,12K 34,38D) -- katalogda olayı var ama `baseline_poisson`'da yok, ve SIFIR
pozitif taşıyor. Karşılaştırma ETAS'ın ızgarasıyla (2100 hücre) sınırlanır;
gerekçe budur ve kayda geçmiştir.

---

## V20 — V17 tamamlandı: vaka → örüntü → **hesaplanabilir koşul**

**Ne oldu.** V17'de kaba kanarya kördü: hedefin yarısını doğrudan veren bir
öznitelik AUC'yi +0,0000 değiştirmişti. Teşhis, `min_child_samples=200` ile
212 pozitifin oranıydı — ama teşhis **çıkarsamaydı**, ölçüm değil.

**Nasıl teyit edildi.** Kanarya haftalık tabloda yeniden koşuldu. Aynı kanarya,
aynı kod, farklı tablo:

    aylık    212 pozitif  min_child 200  ->  alarm YOK  (kör)
    haftalık 753 pozitif  min_child 200  ->  alarm VAR

Teşhis deneyle doğrulandı. Kanarya, iki tabloda farklı davranarak kendi körlük
mekanizmasını gösterdi.

**Kazanılan şey — asıl olan bu.** Körlük artık bir vaka değil, **koşulmadan
önce kontrol edilebilir bir eşitsizlik**:

    eğitim pozitifi < min_child_samples  =>  KABA KANARYA KÖRDÜR

Vaka → örüntü → **öngörülebilir koşul**. Gelecekteki her kurulumda kanarya
koşulmadan önce bu oran bakılır; kör çıkıyorsa kanarya "temiz" raporu VEREMEZ.

**Genellenen ilke.** Bir korumanın kör noktası, o körlüğü ÜRETEN büyüklük
cinsinden yazılabiliyorsa, koruma artık kendi geçerlilik alanını beyan
edebilir. "Bu kanarya çalışıyor" yerine "bu kanarya şu koşulda çalışır."

---

## V21 — Programlı metin değişimi SESSİZCE uygulanmadı

**Ne oldu.** `scripts/19_kanarya_duyarlilik.py`'de üç satırlık bir değişiklik
`str.replace` ile yapıldı; desen tutmadı ve **hiçbir şey olmadı.** `replace`
eşleşme bulamayınca metni aynen döndürür — hata vermez. Betik eski hâliyle
koştu, koşu çöktü, ~2 dakika kayboldu.

**Neden tehlikeli.** Kayıp süre değil. Değişiklik "yapıldı" sanılıp
doğrulanmasaydı, sonuçlar **eski kod yoluyla** üretilmiş olurdu ve künye
yanlış olurdu — V15 ile aynı sınıf: iddia var, uygulama yok.

**Düzeltme.** Her programlı değişimden önce `assert old in s`. Uygulanmayan
değişiklik artık gürültüsüzce geçemez; hemen patlar.

**Genellenen ilke.** Sessizce başarısız olabilen her işlem, başarısızlığı
GÜRÜLTÜLÜ hâle getirilmeden kullanılmaz. `str.replace`, `dict.get`, boş
`groupby`, boş maske — hepsi aynı sınıf.

---

**V21 İKİNCİ TETİKLENME — 25 Ağu 2026, maliyet SIFIR.** Aynı hata sınıfı
(heredoc `
` kaçışını yutuyor) NPP arama betiğinde tekrar geldi: kabuk
tırnaklaması yüzünden beş satırdan üçü uygulanmadı ve geriye `c['lr']`
referansı kaldı — koşuda `KeyError` verecekti.

Fark, korumanın **nerede** durduğuydu:

    ilk vaka  : bozuk dosya DİSKE İNDİ, hata bir sonraki koşuda çıktı
    ikinci    : ast.parse YAZIMDAN ÖNCE yakaladı, bozuk içerik diske değmedi

Koruma evrimi burada da görünüyor: aynı sınıf iki kez geldi, ikincisinde
maliyet sıfıra indi. Kaçış bu kez elle kuruldu (`chr(92) + "n"`).

## V22 — Veri-yokluğu deseni, aşağı akıştaki bir varsayımla tıkandı

**Ne oldu.** Kanarya test bölümünü yükler yüklemez silecek şekilde düzeltildi
(doğru desen). Ama `lgbm.train`, tahmin üretirken `("val", "test")` bölümlerini
**koşulsuz** dolaşıyordu; test yoksa `KeyError`.

**Neden kayda değer.** Hata `train`'de değil, İLKENİN UYGULANABİLİRLİĞİNDE.
"Veriyi sil" koruması, veriyi zorunlu sayan tek bir aşağı-akış varsayımıyla
kullanılamaz hâle geliyordu. Koruma reddedilmiş olsaydı, gerekçe "işe yaramadı"
olurdu — oysa gerçek gerekçe "başka bir yer onu varsayıyordu".

**Düzeltme.** `train` yalnızca VAR OLAN bölümler için tahmin üretir.

**Genellenen ilke.** Bir koruma deseni (veri yokluğu) benimsenecekse, o desenin
geçtiği BÜTÜN yol boyunca "veri var" varsayımları aranmalıdır. Aksi hâlde
koruma, kendi altyapısı tarafından reddedilir.

**V21 EKİ — vakanın maddi izi.** İlk düzenlemede assert yoktu; iki değişimden
biri tuttu, biri tutmadı ve dosya **yarım uygulanmış hâlde yazıldı.** Artık
kalan satır sonraki koşuda sözdizimi hatası verdi. Yani sessiz başarısızlık,
yalnızca "değişiklik olmadı" değil **tutarsız bir dosya** üretebiliyor.

İki kural eklendi:

    1. Her programlı değişimde  assert old in s
    2. Yazmadan ÖNCE  ast.parse(src)  -- bozuk dosya diske hiç inmesin

Kök neden ayrıca öğreticidir: heredoc, `\n` kaçışlarını tüketiyordu; desendeki
`\n` gerçek satır sonuna dönüşüyor ve eşleşme sessizce kayboluyordu. Ortamın
metin işleme davranışı, kodun doğruluğu kadar sonucu etkileyebiliyor.

---

## V23 — Yuvarlama, ilanda olmayan bir "beraberlik" uydurdu ve SEÇİMİ DEĞİŞTİRDİ

**Ne oldu.** İlan edilen seçim kuralı: *"doğrulama logloss'unun 3 tohum
ortalaması en küçük olan; BERABERLİKTE daha az yapraklı."* Kod ise sıralamayı
`round(ortalama, 6)` üzerinden yapıyordu.

Sonuç: ilk üç bileşim 6 hanede yapay olarak eşitlendi.

    ham sıralama (yuvarlamasız)
      1. 0,002414729 +- 0,000001046   yap=7 mcs=200
      2. 0,002414928 +- 0,000001557   yap=7 mcs=50
      3. 0,002415465 +- 0,000000831   yap=7 mcs=20   <- KOD BUNU SEÇMİŞTİ

Üçünün de yaprak sayısı 7 olduğu için beraberlik kuralı ayırt edemedi ve seçim
**eklenme sırasına** düştü. Kod, ham üçüncü sıradaki bileşimi seçti.

**Nasıl yakalandı.** Raporda "en yakın rakip farkı **−0,000001**" yazıyordu.
Fark tanımı gereği negatif olamaz; seçilenin rakibinden kötü olduğunu söylüyordu.
Tutarsızlık, sayıya bakınca görüldü.

**Düzeltme sonuca göre ayar DEĞİLDİR.** Kod, önceden ilan edilmiş kuralı
uygulamıyordu; yuvarlama ilanda yoktu, kodda uydurulmuştu. Düzeltme kodu
ilana uydurur. Seçim `mcs=200`'e taşındı ve **bu değişiklik açıkça
raporlanır** — sessizce düzeltilip "zaten bu seçilmişti" denmez.

**Ama asıl bulgu şu: fark ayırt edilemez.**

    1. ile 2. arası fark   0,000000199
    1.nin tohum saçılımı   0,000001046
    fark saçılımı aşıyor mu   HAYIR

İlk üç bileşim **tohum gürültüsünün altında** ayrışıyor. Önceden yazılmış
hüküm burada geçerlidir: **"seçildi ama ayırt edilemedi."** Test sonucu, tek
bir özel bileşimin değil, bu düz bölgenin temsilcisi olarak okunmalıdır.

**Genellenen ilke.** Sıralama, karşılaştırma ya da eşitlik içeren her kodda
**yuvarlama bir ölçüt tanımıdır.** İlan edilmemiş bir yuvarlama, ilan
edilmemiş bir ölçüttür. "Görsel düzen için" yapılan yuvarlama, sıralama
anahtarına girdiğinde artık biçim değil hükümdür.

---

## V24 — Kapsam ölçümünün KENDİ seçim kuralı, cevabı girdiye sızdırıyordu

**Ne oldu.** NPP ilan paketinde girdi tasarımı ölçümle gerekçelendirilmişti:
"ETAS kütlesinin %5 diliminde bile ≥ 0,95'ini taşıyan en küçük K". Ölçüm
doğruydu, ölçüt doğruydu — ama ölçümün **sıralama kuralı** uydurulmuş ETAS
çekirdeğiydi.

O kural girdi seçimine uygulansaydı, nöral modele "hangi olaylar önemli"
bilgisi **ETAS'ın kendi cevabından** verilmiş olurdu.

**Neden kanaryalar yakalayamazdı.** Hedef sızıntısı yok, ileri bakış yok,
ölçekleme sızıntısı yok. Üç kanarya da temiz raporlardı. Bu, **tasarım
düzeyinde bir haksız avantaj**tır ve yalnızca tasarımı okuyarak görülür.

**Nasıl bulundu.** Veri kurucusunu yazmadan önce "bu diziyi neye göre
sıralayacağım?" sorusu soruldu ve cevap "ETAS'ın çekirdeğine göre" çıktı.
Soru, kodu yazma anında kendiliğinden geldi — ölçüm aşamasında gelmemişti,
çünkü ölçüm bağlamında sıralama yalnızca bir *analiz aracıydı*.

**Genellenen ilke — iki katmanlı.**

1. **Bir analiz aracı, tasarım kuralına dönüştüğü anda denetlenmelidir.**
   Aynı formül, ölçüm bağlamında masum, girdi bağlamında sızıntıdır. Aracın
   kendisi değil, **nereye bağlandığı** belirler.

2. **Kanaryalar tasarımı denetlemez.** Sızıntı kanaryaları çalışma zamanı
   sızıntısını arar (hedef, ileri bakış, ölçekleme). "Karşılaştırılan iki
   modelden birinin cevabı diğerinin girdisine giriyor mu?" sorusu, ancak
   tasarım okunarak cevaplanır. Bu soru kontrol listesine eklendi.

**Sonuç.** Sıralama, literatürden alınmış ve bu veriye uydurulmamış bir
öncül çekirdeğe taşındı (p=1,10 · c=0,01g · d=5km · rho=0,75 · alpha10=1,00).
Kapsam ölçütü değişmedi; ölçütü karşılamak için K 64'ten 256'ya çıktı.
Zeyilname 1, `docs/NPP_ILAN.md`.

---

## V25 — Test, modelin değil KENDİ SAHTESİNİN rastgeleliğini ölçüyordu

**Ne oldu.** NPP determinizm testi ilk koşuda düştü: aynı tohumla iki eğitim
farklı NLL verdi (6,497186 vs 6,505884). İlk okuma "model deterministik değil"
olurdu ve protokol yeniden yazılırdı.

**Gerçek sebep testteydi.** Sahte `Yigin` sınıfı, olay verisini **paylaşılan
bir RNG'den** üretiyordu. İkinci eğitim çağrıldığında RNG ilerlemiş
olduğundan, model **farklı veri** görüyordu. Model deterministikti; test
değildi.

**Neden V15 ailesinden.** Kontrol kuruluydu ve çalışıyordu — ama ölçtüğü şey
iddia ettiği şey değildi. V15'te koruyucunun izlemesi boştu; burada testin
girdisi kararsızdı. İkisi de "kurulu ama iddia ettiğini ölçmüyor" sınıfı.

**Nasıl ayırt edildi.** Model tarafında değişebilecek tek şey tohumdu ve tohum
sabitti; geriye girdinin kendisi kalıyordu. Sahtenin RNG'si tek şüpheliydi.

**Genellenen ilke.**

> **Sahte veri üreticilerinin determinizmi, determinizm testlerinin ÖN
> KOŞULUDUR.** Bir testin girdisi kararsızsa, test çıktının kararlılığını
> ölçemez.

Uygulama: sahte üreticiler **çağrı sırasına değil, istenen satıra göre**
tohumlanır (`default_rng(sabit + satir_no)`), böylece kaçıncı kez çağrıldığı
sonucu değiştirmez.

**Ayrıca:** düşüşün ilk yorumu yanlış olurdu ve protokolü gereksiz yere
değiştirirdi. Bir test düştüğünde ilk soru "kod mu yanlış?" değil, **"test ne
ölçüyor?"** olmalı.

---

## V26 — Kanarya, KOŞULMADAN önce hedefini buldu

**Ne oldu.** Kanarya 3 (ölçekleme sızıntısı) NPP için etkinleştirilecekti.
Koşucuyu yazmak için `npp.Yigin`'in nasıl ölçeklediğine bakıldı ve görüldü:

    self.mu_s = x.mean(0, keepdims=True)      # TÜM tablo: eğitim+doğrulama+TEST

Sızıntı **kanaryanın sınayacağı şeyin ta kendisiydi** ve üretim kodunda,
varsayılan davranış olarak duruyordu.

**Neden fark edilmemişti.** Bu satır Faz 3'ün ağaç yolundan taşınmıştı ve
orada **zararsızdı**: ağaç bölmeleri monoton dönüşümlere duyarsızdır, ölçek
istatistiği sonucu değiştirmez (ölçüldü: fark −0,0000). Aynı satır nöral
modelde gerçek bir kanaldır.

**Genellenen ilke — iki katmanlı.**

1. **Zararsız bir kalıp, model sınıfı değişince zararlı olur.** "Bu daha önce
   sorun çıkarmadı" bir güvence değildir; hangi model sınıfında sorun
   çıkarmadığı sorulmalıdır.

2. **Bir dedektörü İNŞA ETMEK, onu koşturmaktan önce iş görebilir.** Kanaryayı
   yazmak, sınayacağı kod yolunu okumayı zorunlu kıldı ve kusur orada
   bulundu — kanarya hiç koşmadan. Dedektör yazmanın maliyeti yalnızca koşma
   süresi değil; getirisi de yalnızca alarm değil.

**Düzeltme.** `Yigin(..., olcek_satirlari=...)` — istatistikler yalnızca
verilen satırlardan. `None` verilmesi artık YALNIZCA kanarya 3'ün sızıntılı
kolunu kurmak içindir ve nesne `olcek_kapsami` alanında bunu "TÜM TABLO
(sızıntılı)" diye beyan eder.

**Kanarya yine de koşulacak** (kural 9): kusur düzeltildi diye kanarya
gereksiz olmaz — korumanın çalıştığı, REDDETTİĞİ bir deneyle gösterilir.

---

## V27 — Taşıma denetimi: V26'nın SINIFINDA iki kusur daha

**Ne oldu.** V26 tekil bir düzeltmeydi. "Bu bulgunun sınıfı nedir ve başka
örneği var mı?" sorusu sorulunca Faz 3'ten NPP'ye taşınan kalıplar tek tek
denetlendi. İki kusur daha çıktı, biri de temiz çıktı.

**(a) `poisson_rate` özniteliği YOKTU.** Sütun öznitelik tablosunda
bulunmuyor; `lgbm.load_dataset` onu `baseline_poisson.csv` ile birleştirerek
ekliyordu. `npp.Yigin` tabloyu doğrudan okuduğu için sütun eksikti — NPP,
Faz 3'ün SHAP'te %52,5 pay alan özniteliği olmadan eğitilecekti. Aynı
öznitelik kümesiyle karşılaştırma iddiası çökerdi.

**(b) NaN işleme sessizce değişmişti.** LightGBM NaN'ı yerli işler; nöral ağ
işlemez ve kod `nan_to_num(0)` yapıyordu. `bval` satırların %96,6'sında
NaN — yani model "b-değeri sıfır" bilgisi alıyordu. b ≈ 1'dir; sıfır fiziksel
olarak imkânsızdır. İlan edilen doldurma kuralı tam bunu yasaklıyordu.

**(c) Poisson temel modelin dönemi TEMİZ ÇIKTI.** 1990-2016, doğrulama
başlangıcında bitiyor. Bu da denetimin parçasıdır: **temiz çıkan bir kalem,
denetlenmemiş bir kalemle aynı şey değildir.**

**Genellenen ilke.**

> Tekil bir kusur kapatıldığında sorulacak soru düzeltmenin doğruluğu değil,
> **"bu bulgunun sınıfı nedir ve o sınıfın başka örneği var mı?"**dır.
> Sınıf taranmadan kapatılan bulgu, aynı sınıfın diğer örneklerini görünmez
> kılar — çünkü "o sorun çözüldü" duygusu aramayı durdurur.

Ayrıca: taşınan kod, **taşındığı bağlamda yeniden denetlenmelidir.** Kalıbın
zararsızlığı bağlama bağlıdır ve bağlam model sınıfıdır.

---

## V28 — Bütçe yetersiz değildi, BAŞLANGIÇ NOKTASI yanlıştı

**Ne oldu.** İlan şartı gereği tek koşu zamanlandı. İki sonuç çıktı:

    süre                24,1 dk/koşu -> 24 koşu 9,6 saat (ilan tahmini ~1,5 sa)
    doğrulama NLL       40. turda HÂLÂ tekdüze düşüyor; erken durdurma
                        hiç tetiklenmedi

**İlk okuma yanlış olurdu.** İlan, "tahmin tutmuyorsa arama uzayı KÜÇÜLTÜLÜR"
diyordu ve bu kural uygulanabilirdi: 8 bileşim 4'e indirilir, süre yarılanır,
koşu başlar. **Ama sorun bütçe değildi.**

**Ölçülen kök neden.** Rastgele ilklendirmede başlangıç lambda'sı:

    başlangıç lambda   182,63
    gerçek taban oran    0,00032731
    ORAN               557.966 kat

Model 40 turun tamamını **5,7 büyüklük mertebesi inmekle** geçiriyordu.
Öğrenmesi gereken şey şekildi; seviyeye takılıyordu.

**Bu neden sonucu geçersiz kılardı.** 40 turda kesilen bir karşılaştırma,
model kalitesini değil **"kim daha hızlı indi"yi** ölçer. Büyük öğrenme oranı
kazanır, düzenlileştirme kaybeder — ve bu, modelin tahmin gücüyle ilgisiz bir
sıralamadır. Arama koşulsaydı 9,6 saat harcanır ve **cevap yanlış soruya**
verilirdi.

**Düzeltme.** Son katman yanlılıkları taban orana ilklendirilir (nadir-olay
Poisson modellerinde standart): arka plan başı taban oranı, tetiklenme başı
olay başına taban/(10K) verir.

    ilklendirme sonrası oran   1,07 kat

Taban oran **yalnızca eğitim satırlarından** hesaplanır; doğrulama ve test
görülmez.

**Genellenen ilke.**

> Bir bütçe kısıtı göründüğünde ilk soru "bütçeyi mi kısayım, kapsamı mı?"
> değil, **"bütçe neye harcanıyor?"**dur. Harcamanın kendisi kusurluysa,
> bütçeyi kısmak kusuru gizler; kapsamı kısmak da öyle.

Ayrıca: **erken durdurmanın hiç tetiklenmemesi bir uyarı işaretidir.** Sabır
parametresi bir güvenlik ağıdır; hiç devreye girmiyorsa model yakınsamamış
demektir ve "en iyi tur" aslında "son tur"dur.

**İlan şartının değeri.** "Koşu başlamadan önce tek bir koşu zamanlanır"
maddesi buraya kadar bir süre kontrolü sanılıyordu. Asıl işi bu oldu:
**yakınsama kontrolü.** Madde ilan pakette olmasaydı, arama doğrudan koşardı.

**V28 EKİ — düzeltme NEDEN işliyor.** Poisson NLL'in ön-aktivasyona göre
gradyanı kabaca `(lambda - y)`'dir. `lambda ~ 182`, `y ~ 0` iken gradyan
büyüktür ama parametre `softplus`'ın içindedir ve iniş ön-aktivasyonda
yaklaşık **doğrusaldır**: her adım `lr` mertebesinde ilerler. 5,7 büyüklük
mertebesi (~13 doğal log birimi) inmek, `lr=1e-3` ile on binlerce adım
demektir — 40 tur tam olarak buna gidiyordu.

Yanlılık ilklendirmesi bu yolculuğu **tamamen ortadan kaldırır**: model
"olay yok" varsayımından başlar ve ilk adımdan itibaren SEKLİ öğrenir.

**BELİRTİ EŞLEŞMESİ.** Gelecekte şu belirti görülürse doğrudan bu vakaya
bakılsın:

    ilk turlarda kayıp hızla ve TEKDÜZE düşüyor, sonlara doğru hâlâ düşüyor,
    erken durdurma hiç tetiklenmiyor

Bu, "model öğreniyor" değil **"model hâlâ seviyeyi arıyor"** demektir.
Kontrol tek satırdır: ilklendirilmiş modelin başlangıç `lambda` ortalamasını
hedefin taban oranıyla karşılaştır.

---

## V29 — Sonda, ölçmek istediği şeyi ölçemeyecek biçimde tasarlanmıştı

**Ne oldu.** Kanarya 3 (ölçekleme sızıntısı) NPP'de gerçek sızıntıyı
yakalamadı (+0,0003). "Kör mü, kanal mı boş?" ayrımı için kasıtlı bozulma
taraması yapıldı: özniteliklere 0,05 · 0,15 · 0,50 · 1,50 sd'lik kayma
eklendi.

    0,05 sd -> +0,0005      0,50 sd -> +0,0059
    0,15 sd -> +0,0022      1,50 sd -> +0,0038   <- DAHA KÜÇÜK

**Etki tekdüze değil.** 1,5 sd'lik bozulma, 0,5 sd'linkinden daha az etki
yaptı. Tekdüze olmayan bir "etki" sinyal değil **gürültüdür**.

**Betiğin otomatik hükmü YANLIŞTI.** Kod ikili bir mantık kuruyordu —
yakaladı / yakalamadı → kör — ve "DEDEKTÖR KÖR" yazdı. Üçüncü ihtimal
gözden kaçmıştı:

> **Sondanın kendisi bilgi taşımıyor olabilir.**

Standartlaştırma istatistiklerindeki fark, girdilere **tüm satırlara aynı
uygulanan afin bir dönüşüm** olarak yansır. Nöral ağın ilk katmanı bunu
ağırlık ve yanlılığıyla **soğurur**; dönüşüm hipotez sınıfını değiştirmez,
yalnızca eniyileme koşullarını değiştirir. Satır başına ayırt edici bilgi
taşımayan bir bozulma, hiçbir dedektör tarafından yakalanamaz — çünkü
yakalanacak bir şey yoktur.

**Bu, kendi ilan cümlemi yanlışlar.** `docs/NPP_ILAN.md` §7'de yazmıştım:

> *"Kanarya 3 ilk kez anlamlı. Ağaçlarda kanal yoktu; nöral modelde ölçekleme
> gerçek bir kanaldır."*

Yanlış. Kanal **her iki model sınıfında da** neredeyse boştur, ama farklı
sebeplerle:

| model sınıfı | neden boş |
|---|---|
| ağaç | monoton dönüşüme **duyarsızlık** |
| nöral | afin dönüşümü **soğurabilme** |

**Genellenen ilke — iki katmanlı.**

1. **"Alarm yok" üç şey olabilir, iki değil:** dedektör kör · kanal boş ·
   **sonda bilgisiz.** Üçüncüsü ilk ikisinden ayrılmadan hüküm verilemez.
   Ayıran ölçüm: bozulma büyütüldükçe etki **tekdüze artıyor mu?**

2. **Bir sondayı tasarlarken sorulacak soru:** *"bu bozulma, model sınıfının
   temsil edemeyeceği bir fark yaratıyor mu?"* Model sınıfının soğurabildiği
   bir dönüşümle sonda yapmak, termometreyi sıcaklığı ölçmeyen bir yere
   koymaktır.

**Sonuç — kanarya 3 EMEKLİ EDİLİR.** Tanımlandığı biçimiyle (standartlaştırma
istatistiklerinin kapsamı) hiçbir model sınıfı için anlamlı bir dedektör
değildir. Yerine ne konabileceği ilan edildi (Zeyilname 4) ama **bu koşuda
kullanılmaz** — sonuç görüldükten sonra yeni dedektör tanımlamak, ölçütü
sonuca göre seçmek olurdu.

**V26 DÜZELTMESİ YERİNDE KALIR** ve gerekçesi güçlenerek durur: sızıntı
gerçektir, bu veri setinde zararsızdır çünkü dağılım bölümler arasında
durağandır (ölçüldü: ortalama kayma 0,0125 sd). **Durağanlık bir varsayımdır,
garanti değildir** — katalog genişlediğinde, Mc değiştiğinde ya da bölümler
farklı sismik rejimlere düştüğünde aynı sızıntı zararlı olur. Bugün boş olan
kanal, yarın dolu olabilir.

---

## V30 — `git commit && uzun_koşu`: temiz ağaç zinciri kırdı

**Ne oldu.** Ana koşu şöyle başlatıldı: `git commit -m ... && python arama.py`.
Commit edilecek bir şey yoktu (uçuş öncesi kontrol bir **ölçümdü**, dosya
değişikliği değil), `git commit` **1 döndürdü**, `&&` zinciri kırıldı ve
**koşu hiç başlamadı.**

**Neden tehlikeli.** Komut sessizce "başarısız" oldu ama görünürde bir hata
yoktu — çıktı yalnızca `nothing to commit, working tree clean` diyordu.
Bildirim gelmeseydi, dokuz saat sonra "koşu bitti mi?" diye bakıldığında
**hiç başlamamış** olduğu görülecekti.

**Aile.** V21 (heredoc `\n` yutması) ile aynı sınıf: **kabuk semantiğinin
sessiz kırılması.** Üçüncü üye. Ortak özellik: komut "çalıştı", sonuç yanlış.

**Kural — ucuz ve kalıcı.**

    1. Uzun koşular AYRI komutla başlatılır; hiçbir şeye zincirlenmez.
    2. Başladığı ÇIKTIDAN DOĞRULANIR. "Başlattım" bir gözlem değildir.

İkinci madde bu vakada işledi: koşu yeniden başlatıldıktan sonra ilk 90
saniyelik çıktı okundu ve dört satır doğrulandı (satır sayıları, 16 sütun,
ölçekleme kapsamı, dizin künyesi). Boş çıktıya güvenilseydi hata yine
gizlenirdi.

**Yan kazanç.** O dört satır, koşu-öncesi denetimlerin **fiilen yürürlükte**
olduğunu tek ekranda gösterdi:

    16 sütun                -> V27 (eksiklik göstergeleri)
    2.300.595 satır kapsam  -> V26 (ölçekleme yalnızca eğitimden)
    dizin künyesi           -> V6'nın veri tarafındaki karşılığı
    12 koşu                 -> Zeyilname 3 (küçültülmüş uzay)

"Koruma kurulu" ile "koruma yürürlükte" arasındaki fark, açılış çıktısında
kapandı.

---

## V31 — Saçılım-tabanlı seçim kuralı, saçılımın kendi belirsizliğini saymıyor

**Ne oldu.** NPP aramasında seçim kuralı şuydu: *en yakın rakiple fark, tohum
saçılımını aşıyor mu?* Kod bunu **seçilenin kendi standart sapmasıyla**
karşılaştırıyor ve "EVET" bastı.

    en yakın rakiple fark        0,000001599
    SEÇİLENİN kendi ss           0,000000439  -> aşıyor: EVET
    HAVUZLANMIŞ ortalama ss      0,000005763  -> aşıyor: HAYIR

**Seçilen bileşimin saçılımı, diğer üçünün on altıda biri.** Karar, o
olağandışı küçük sayıya dayanıyor.

**Kural DEĞİŞTİRİLMEDİ.** İlan edilmişti ve sonuç görüldükten sonra
değiştirmek kural 1 ihlali olurdu. Değişen şey **raporun içeriğidir**:
kararın kırılganlığı beyan edilir.

> Seçim, tek bir bileşimin **şans eseri kararlı çıkmasına** dayanıyor olabilir.

**Kök neden — genellenebilir.** Standart sapma **3 gözlemden** kestirildi.
3 tohumlu bir kestirimde ss'nin kendi bağıl belirsizliği çok büyüktür
(kabaca %40 mertebesinde); 16 katlık bir oran farkı bu belirsizlikle
rahatlıkla üretilebilir. Yani "bu bileşim daha kararlı" ifadesi, ölçülen
şeyin kendisi kadar gürültülüdür.

**Genellenen ilke.**

> **Saçılım-tabanlı bir seçim ya da hüküm kuralı, saçılımın KENDİ
> belirsizliğini hesaba katmalıdır.** Az sayıda tekrarla kestirilen bir
> standart sapmayı eşik olarak kullanmak, gürültüyü ölçüt yapar.

**Uygulama (gelecek kurulumlara).** Kural, tek bileşimin ss'siyle değil
**havuzlanmış** ss ile kurulur; ya da tohum sayısı ss'yi kestirecek düzeye
çıkarılır. Bu değişiklik **bu koşuya uygulanmaz** — sonuç görüldükten sonra
ölçüt değiştirilmez; bir sonraki ilan paketinde yazılır.

---

## V32 — İkili ilan yapısı, üçüncü kez üçlü gerçeklikle karşılaştı

**Ne oldu.** Faz 3'ün kapanış taslağı iki dal bağlamıştı: **X** (NPP
tetiklenmeyi öğrendi) · **Y** (öğrenemedi). Sonuç ikisinin de tam karşılığı
değildi:

    tetiklenme  KISMEN öğrenildi   (19,8 -> 41,8; ETAS 84,3, gözlenen 59)
    şekil       ETAS'tan İYİ       (H1: +0,316, MDE üstünde)
    seviye      ÖĞRENİLEMEDİ       (kalibrasyon 1,52)

Dal X'in *"öğrenilebilir"* yarısı ve Dal Y'nin *"geçemedi"* yarısı **aynı anda
doğru.**

**Üçüncü kez.** Aynı yapısal eksik daha önce iki kez çıktı:

| # | ikili kuruluş | üçlü gerçeklik |
|---|---|---|
| 1 | arama dağılımı DAR / GENİŞ | küresel yapılı + yerel düz (Faz 3) |
| 2 | kanarya: yakaladı / kör | dedektör kör · kanal boş · **sonda bilgisiz** (V29) |
| 3 | kapanış: X / Y | öğrenildi + öğrenilmedi, **farklı bileşenlerde** |

**Ortak kök.** İkili kuruluş, ölçülen şeyin **tek boyutlu** olduğunu
varsayar. Üçü de çok bileşenli çıktı: uzayın yapısı ölçeğe bağlıydı;
"alarm yok" üç ayrı sebepten olabiliyordu; "öğrendi" birden fazla bileşene
ayrılıyordu.

**Genellenen ilke.**

> **Bir dal yapısı kurulurken sorulacak soru: ölçtüğüm şey tek boyutlu mu?**
> Değilse dallar **bileşen başına** kurulur; tek eksende kurulan dallar,
> bileşenlerin ayrıştığı durumu öngöremez.

**Ne YAPILMADI.** Dal zorlanmadı. DAR/GENİŞ emsalindeki gibi, **uygulanabilir
beyanlar ayrı ayrı işletildi** ve uymayan varsayımlar açıkça "gerçekleşmedi"
diye işaretlendi. İlanın eksiği, sonucu eğip bükmek yerine **ilanın eksiği
olarak** kaydedildi.

**Uygulama (gelecek ilan paketlerine).** Kapanış dalları, hükmün dayandığı
**her bileşen için ayrı** yazılır. NPP örneğinde bu, üç dal demekti:
tetiklenme (öğrenildi / kısmen / hayır) × şekil × seviye. İkili kuruluş
üç bileşeni tek eksene sıkıştırdığı için yetersiz kaldı.

---

## V33 — Yasak kelime taraması, TÜRKÇE büyük harfe kördü

**Ne oldu.** Veri hattının "kesinlik dili" koruması `str.lower()` ile
karşılaştırma yapıyordu. Kural 9 gereği yazılan ret testi bunu ilk koşuda
düşürdü:

    "Bu bölgede KESİNLİKLE hareket bekleniyor."   -> ALARM VERMEDİ

**Sebep.** Türkçe büyük `İ`, Unicode kurallarına göre `i` + **birleşen nokta**
(U+0307) verir. `"KESİNLİKLE".lower()` çıktısı `"kesi̇nli̇kle"`dir ve
`"kesinlikle"` ile **eşleşmez**.

Ölçüldü: çıktı `cp1254`'e kodlanamıyor bile — birleşen noktanın varlığının
maddi kanıtı.

**Neden özellikle kötü.** Koruma, ihlalin **en yüksek sesle yazılmış hâlini**
kaçırıyordu. Büyük harf, kesinlik iddiasının en olası biçimidir
("KESİNLİKLE", "DEPREM OLACAK"). Yani tarama tam da yakalaması gereken yerde
kördü.

**Düzeltme.** Küçültmeden ÖNCE Türkçeye özgü iki eşleme:

    İ -> i        I -> ı

**Nasıl yakalandı — kural 9'un doğrudan getirisi.** Koruma yazıldıktan sonra
"reddettiği bir deney" zorunluydu; o deney yazılırken körlük çıktı. Koruma
teste tabi tutulmasaydı, **yayına kör hâlde girecekti** ve hiçbir çıktı hata
vermeyeceği için de fark edilmeyecekti.

**Genellenen ilke.**

> **Metin tabanlı korumalar, çalışacakları DİLİN kurallarına göre
> sınanmalıdır.** `lower()`, `upper()`, `title()`, alfabetik sıralama ve
> karşılaştırma — hepsi dile bağlıdır ve varsayılan davranış İngilizce'dir.

Bu, "zararsız kalıp, bağlam değişince zararlı olur" (V26) ailesinin dil
katmanındaki örneğidir: `str.lower()` İngilizce metinde doğru, Türkçe metinde
yanlıştır.

**Kapsam taraması (V27 kuralı: sınıf taranmadan kapatılmaz).** Kod tabanında
`lower()` / `upper()` kullanan başka **kullanıcıya görünen metin** işlemi var
mı — bu sorunun cevabı arayüz aşamasında, yayımlanan metinler yazıldığında
yeniden sorulacaktır. Şu an yayımlanan tek metin GeoJSON künyesidir.

---

## V37 — Dondurulmuş sonucun DONDURULMAMIŞ ZEMİNİ

**Ne oldu.** Site veri hattının eşik teyidi sırasında, dondurulmuş
değerlendirme tablosunun (`etas_analytic_weekly`, 24 Ağu 2026 21:22) bugünkü
kodla **yeniden üretilemediği** görüldü.

    eval ~ 1,061 x hat + 6,41e-05      eğim ~1 -> TETİKLEME AYNI
    eval μ oranı 0,3691 · hat μ oranı 0,0968   -> 3,81 kat, ARKA PLANDA

**Teşhis zinciri — beş kontrol.** Farkın yeri kesin olarak daraltıldı, sebebi
bulunamadı:

| kontrol | sonuç |
|---|---|
| parametre sha256 | **aynı** — künye zinciri işini yaptı |
| katalog kırpması | **etkisiz** → ileri bakış YOK |
| EM adımı | **kararlı** (6 tekrar, 1,000 kat) → V16 değil |
| `history_years` | açıklamıyor (2-20 yıl → 0,084-0,127) |
| `cell_id` düzeltmesi | 1,00005 kat |

**Kalan aday sınanamadı.** Katalogun geriye dönük içerik değişimi tek olası
sebepti ama `catalog_merged.csv` gitignore'daydı ve **sha'sı hiçbir yere
yazılmamıştı**. Karşılaştırılacak bir kayıt yoktu.

**KÖK BULGU.**

> Künye zinciri **parametreleri** kapsıyordu (`etas_params_sha256`) ama
> **veriyi** kapsamıyordu. Mühür sayıları koruyordu; **zeminin kendisi
> künyesizdi.**

Dondurulmuş bir sonuç, dondurulmamış bir zemin üzerinde duruyordu. V6'nın
(bayat eser) veri tarafındaki karşılığı budur ve dört ay boyunca görünmedi —
çünkü zemin hiç yeniden üretilmemişti. **Bir eserin bayat olup olmadığı,
ancak yeniden üretilmeye çalışıldığında anlaşılır.**

**Nasıl bulundu.** Site veri hattının bir kabul testi olarak eşik teyidi
istendi: "hat ile değerlendirme aynı sayıları veriyor mu?" Bu soru
sorulmasaydı, cron yeniden üretilemeyen bir zemin üzerinde yayına başlayacak
ve fark hiç görünmeyecekti.

**Düzeltme (pazarlıksız, sonuçtan bağımsız).** Künyeye iki alan eklendi ve
şema koruması ikisini de **zorunlu** kıldı:

    catalog_sha256        katalog dosyasının sha256'sı
    catalog_last_event    kataloğun son olay zamanı

**Genellenen ilke.**

> **Künye zinciri, sonucu üreten HER girdiyi kapsamalıdır — kodu,
> parametreleri VE veriyi.** Kapsamayan bir zincir, kapsamadığı yerden
> kopar; ve kopuş, ancak yeniden üretim denendiğinde görünür.

**Açık uç.** Yeniden üretim koşusu ve okuma kuralları:
`docs/ZEMIN_YENIDEN_URETIM.md` (koşudan önce yazıldı).

---

## V38 — Veri hattı KENDİ GİRDİSİNİ imha etti

**Ne oldu.** Site veri hattı sınanırken `update_catalog()` çağrıldı. Üç
kaynağın ham CSV dosyaları **yalnızca 2026 verisiyle üzerine yazıldı**:

| kaynak | öncesi | sonrası | kurtarıldı |
|---|---|---|---|
| AFAD | 265.572 | **4.713** | 265.572 |
| KOERI | 71.865 | **608** | 71.865 |
| EMSC | 51.149 | **724** | 51.149 |

Birleşik katalog 302.767'den ~278.000'e düştü ve arka plan oranı μ **3,81 kat**
yanlış hesaplandı (0,0968 yerine 0,3689).

**Kök neden — iki doğru parçanın yanlış birleşimi.**

    update_catalog  ->  "--start latest.year"   (niyet: yalnızca son yılı tazele)
    indirme betiği  ->  df.to_csv(out_csv)      (davranış: TÜM dosyayı yeniden yaz)

Her iki parça kendi içinde doğruydu. **Artımlı güncelleme niyeti,
tam-yeniden-yazma davranışıyla çakıştı.** V18/V19 ailesinin en pahalı örneği:
tablo doğru, yükleyici doğru, birleşim veri imha ediyor.

**Neden hiçbir koruma yakalamadı.**

> Bugüne kadar bütün korumalar **YAYIN yönüne** bakıyordu: kirli ağaç, dil,
> şema, künye, hücre bandı. Hattın **KENDİ GİRDİSİNİ** imha edebileceği
> senaryo haritada yoktu.

Koruma taksonomisinin eksik yüzü buydu. Çıktı denetleniyordu; **girdinin
tahrip edilmediğini kimse denetlemiyordu.**

**Nasıl bulundu.** V37'nin teşhis zinciri: dondurulmuş tablo yeniden
üretilemedi → beş kontrol farkın yerini μ'ye daralttı → dönem-bazlı olay
sayıları loglandı → 2010-2019'da 4,5 kat düşüş görüldü → ham dosyalara
bakıldı. **Teşhis notu olmasaydı sebep bulunamayacaktı.**

**Kurtarma — tesadüf, tasarıma çevrildi.** AFAD'ın aylık (284 dosya) ve
KOERI'nin yıllık (57 dosya) JSON/TXT önbellekleri dokunulmamıştı ve **fiilî
yedek** işlevi gördü. Kimse onları yedek diye tasarlamamıştı.

> **Önbellek dizinleri artık resmî kurtarma katmanıdır.** Ağdan çekilen her
> şey önce önbelleğe, oradan birleştirmeye. EMSC'nin önbelleği yoktu ve ağdan
> yeniden çekilmek zorunda kalındı — bir sonraki sürümde o da önbelleğe alınır.

**Düzeltme — iki katmanlı.**

1. **Kök neden:** her kaynak KENDİ TAM ARALIĞIYLA çağrılır (AFAD 2003+,
   KOERI 1970+, EMSC 1998+). Maliyet düşük: betikler önbelleği kullanır.
2. **Monotonluk koruması:** güncelleme sonrası ham dosya **%5'ten fazla
   küçülürse DURULUR** (`KatalogKuculdu`). Bilinçli temizlik `izin_kucultme`
   bayrağıyla geçer.

**Kural 9 — reddettiği deney.** `tests/test_pipeline.py`: kasten hasar veren
sahte bir indirme (1000 → 10 satır) korumayı tetikliyor; bilinçli bayrak
geçiyor; %2'lik dalgalanma durdurmuyor. 31 test.

**Genellenen ilke.**

> **Bir hat, çıktısı kadar GİRDİSİNİN bütünlüğünden de sorumludur.** Veriyi
> tazeleyen her işlem, tazeleme sonrası verinin küçülmediğini ölçmelidir.
> Monotonluk ucuz bir korumadır ve imhayı yakalar.

**Ve bir kayıt daha:** bu hasarı ben verdim — hattı sınarken. Sınama, sınadığı
şeyi bozabilir; bu yüzden sınama da geri alınabilir olmalıdır. Kurtarmayı
mümkün kılan şey, tasarlanmamış bir önbellekti. Şansa bırakılmayacak.

---

## V39 — Karşılaştırma, YUVARLANMIŞ YAYIN DEĞERİYLE kuruldu

**Ne oldu.** Zemin yeniden üretimi karşılaştırılırken betik "DAL B" bastı:
kalibrasyon 1,09'dan 1,0885'e "değişmiş" görünüyordu (fark −0,00146,
tolerans 0,001).

**Ama eski tablo da 1,0885 veriyordu.** İki tablo birbiriyle **tam
uyuşuyordu**; aşan fark, tabloların değil, **yayımlanmış yuvarlanmış değerle**
olan farktı. Manşette `1,09` yazıyor — iki ondalıkta — ve 1,0885 → 1,09 doğru
yuvarlamadır.

**İki tasarım kusuru.**

1. **Yanlış çift.** Asıl soru "zemin yeniden üretilebiliyor mu?" idi; yani
   **eski tablo ↔ yeni tablo**. Betik yeni tabloyu **yayın değerleriyle**
   kıyaslıyordu. Yuvarlama, tablonun değil **sunumun** özelliğidir.

2. **Tek tolerans, farklı hassasiyetler.** Toleransı "manşet üç ondalıkta
   yazılmış" diye gerekçelendirmiştim; kalibrasyon **iki** ondalıkta yazılmış.
   Beş sayının yayımlanma hassasiyeti aynı değildi.

**Düzeltilmiş ölçüm.**

    tablo <-> tablo, en büyük BAĞIL fark   1,2e-04  (%0,012)
    yayımlanmış hassasiyette               5 sayıdan 4'ü örtüşüyor
    sapan                                  auc_etas 0,7909 -> 0,7910 (4. ondalık)

**Genellenen ilke.**

> **Yeniden üretilebilirlik, ARTEFAKTLAR arasında ölçülür; yayımlanmış
> değerler arasında değil.** Yayın değeri yuvarlanmış bir sunumdur ve
> yuvarlama, üretim sürecinin değil raporlamanın özelliğidir.

> **Bir tolerans, karşılaştırılan her sayının KENDİ yayımlanma hassasiyetine
> göre kurulur.** Tek eşik, farklı hassasiyetlerde yazılmış sayılara
> uygulanınca yanlış alarm üretir.

**Kural değiştirilmedi.** İlan edilen tolerans sonuç görüldükten sonra
gevşetilmedi; **yanlış olan ölçüt değil, ölçütün uygulandığı ÇİFTTİ.** Doğru
çift ölçüldü ve iki sonuç da ayrı ayrı raporlandı.

---

## V40 — DOĞRULAMA BETİĞİ, doğruladığı sistemi İKİ KEZ haksız yere suçladı

**Ne oldu.** Eşik teyidi betiği (`scripts/29_esik_teyidi.py`), canlı hat ile
değerlendirme yolunun aynı sayıları verip vermediğini sınıyordu. İki kez
**"AYRIŞMA — CRON BAŞLAMAZ"** hükmü verdi:

    1. koşu (hasarlı katalogla)   YOL1 774-934 · YOL2 126-258
    2. koşu (temiz zeminde)       YOL1 774-934 · YOL2 314-474

**Ayrışma yoktu.** Fark tam olarak açıklandı:

    774 - 314 = 460 = temel modelde BULUNMAYAN hücre sayısı

Izgara 2560 hücre, uzun vadeli Poisson temel modeli 2100 hücre. Kalan 460
hücrede `normal = 0` ve *"normalin kaç katı"* **TANIMSIZDIR**.

    to_geojson (DOĞRU)   normal=0 -> NaN -> `NaN >= eşik` False -> ELENİR
    benim betiğim (YANLIŞ) normal=0 -> np.inf -> eşiği OTOMATİK GEÇER

Düzeltmeden sonra **beş başlangıçta beşi de birebir örtüştü.**

**Kusurun anatomisi — `TANIMSIZ ≠ SONSUZ`.**

> Bölen sıfırken sonucu `inf` yapmak, "değeri çok büyük" demektir. Oysa
> anlamı **"değer yok"**tur. İkisi karşılaştırmada zıt davranır: `inf` her
> eşiği geçer, `NaN` hiçbirini.

Bu, projede daha önce iki kez çıkan ayrımın üçüncü yüzü: **"hesaplanamıyor"
ile "sıfır" farklı ifadelerdir** (doldurma kuralı, V27'nin NaN göstergeleri) —
burada da *"tanımsız"* ile *"sonsuz"*.

**İki kez yanlış hüküm vermesinin sebebi.** İlk koşuda gerçek bir sorun
(V38 katalog hasarı) vardı ve betiğin kendi kusuru onun **arkasına gizlendi**;
katalog düzeltilince kusur tek başına kaldı ve ancak o zaman görülebildi.

> **Bir hata, başka bir hatanın arkasına gizlenebilir.** İlk hata
> düzeltildiğinde "sorun çözülmedi" sonucu, ikinci bir hatanın işareti
> olabilir — ve o an sorulacak soru "düzeltme işe yaramadı mı?" değil,
> **"kaç hata vardı?"**dır.

**Genellenen ilke.**

> **Doğrulama betiği de doğrulanmalıdır.** Bir denetim aracının verdiği
> olumsuz hüküm, aracın kendisi sınanmadan kabul edilmez. Burada araç, iki
> kez "sistem bozuk" dedi ve iki kez de kendisi bozuktu.

**Sonuç.** `299` sorusu da kendiliğinden kapandı: ölçülmüş eşik tablosu 2100
hücrelik temel modele göre kuruluydu; hat 2560 hücrelik ızgarada çalışıp
tanımsızları eliyor. Bugünkü 146 ile bu 314-474 arasındaki fark **rejimdir.**

---

## V44 — Teknik olarak doğru bir cümle, okuyucuyu YANLIŞ YERE götürüyordu

**Ne oldu.** Metodoloji sayfasında şu cümle vardı:

> *"Üç bölgede üstünlük gösterilemedi — Marmara, Batı Anadolu, Kuzey Anadolu
> doğusu. **Olay sayısı düşük**, ölçüm gücü yetersiz."*

Sayı doğruydu: değerlendirme döneminde (2021-2024, M≥4,5) Marmara'da **6
olay** var. Ama okuyucu bundan *"Marmara'da deprem az oluyor"* sonucunu
çıkarır — ve bu **yanlıştır.**

**Ölçüldü.**

| Marmara'da M≥4,5 olay | sayı |
|---|---|
| 2021-2024 (değerlendirme penceresi) | **6** |
| 2010-2024 | 30 |
| 1990-2024 | **142** |
| kayıtlı tüm dönem | 227 |

Uzun vadeli yoğunluk (olay/derece²/yıl, 1990-2024): Marmara **0,523** —
Batı Anadolu (0,533) ile aynı düzeyde, **Kuzey Anadolu doğusundan (0,441)
yüksek.**

**Marmara düşük sismisiteli bir bölge değildir.** Cümledeki "olay sayısı",
bölgenin tehlikesi değil **testin örneklemidir**: dört yıllık bir pencerede
M≥4,5 eşiğinin üstünde kaç olay düştüğü.

**Hata sınıfı.** Bu bir sayı hatası değil, **bağlam hatası**: doğru sayı,
yanlış çerçevede. Teknik okuyucu "6 olay = düşük güç" der; sıradan okuyucu
"6 olay = güvenli bölge" der. **Sayının doğruluğu, cümlenin doğruluğunu
garanti etmez.**

**Genellenen ilke.**

> **Bir sayı, hangi soruyu cevapladığı yazılmadan yayımlanmaz.** "6 olay"
> tek başına iki farklı soruyu cevaplayabilir — *bölgede ne kadar deprem
> oluyor?* ve *testimizin örneklemi ne kadar?* — ve ikisi zıt sonuçlara
> götürür.

**Düzeltme.** Cümle yeniden yazıldı ve sayfaya ayrı bir bölüm eklendi:
*"'Az olay' ne demek — ve ne demek DEĞİL"*, dört dönemin sayıları ve
bölgeler arası yoğunluk tablosuyla. Açık cümle: *"Yalnızca şu doğrudur:
dört yıllık bir pencerede 6 olayla iki modeli ayırt edecek istatistiksel güç
yoktur. Bu, modelin o bölgede kötü olduğunu da iyi olduğunu da göstermez —
ölçemedik demektir."*

**Nasıl bulundu.** Kullanıcı sayfayı okudu ve *"Marmara Türkiye'nin en çok
konuşulan deprem bölgesi, nasıl olur da olay sayısı düşük olur?"* diye sordu.

> **Hiçbir ölçüm bu hatayı yakalayamazdı** — sayı doğruydu, künye doğruydu,
> kapsam beyanı doğruydu. Yakalayan şey, **metnin bir okuyucu gözüyle
> okunmasıydı.**

Kanarya taksonomisine ek bir eksen: **anlam ekseni.** Veri doğru, ölçüm
doğru, cümle yanlış.

---

## V45 — Dil koruması, YAZILMASI ZORUNLU cümleyi engelledi

**Ne oldu.** V44'ün düzeltmesi yazıldı ve dil koruması onu **reddetti**:

    "deprem TEHLİKESİNİN düşük olduğu anlamına gelmez"   -> ihlal sayıldı

Sebep: `tehlikesinin` kelimesi `kesin` alt dizisini içeriyor
(teh-li-**kesin**-in). Tarama **sözcük sınırı gözetmiyordu.**

**Neden kaçınılmazdı.** Türkçe eklemeli bir dildir; kök+ek birleşmeleri
tesadüfi alt diziler üretir. Naif `in` kontrolü bu dilde yanlış pozitif
üretmeye mahkûmdur.

**Düzeltme.** Kalıp **sözcüğün başında** aranır; sonrasına ek gelebilir:

    \bkesin  ->  "kesin", "kesinlikle", "kesindir"   YAKALANIR
                 "tehlikesinin", "eksiksiz"          yakalanmaz

**Bu bir GEVŞETME DEĞİL, DÜZELTMEDİR** — ve ayrımı testle sabitledim:
altı gerçek ihlal (büyük harfliler dâhil) hâlâ yakalanıyor, dört masum
kelime artık geçiyor. Koruma zayıflamadı, **doğrulandı.**

**İlke.**

> Bir korumanın yanlış pozitifi düzeltilirken, **aynı commit'te gerçek
> ihlallerin hâlâ yakalandığı gösterilmelidir.** Aksi hâlde "düzeltme"
> ile "gevşetme" ayırt edilemez.

---

## V46 — Çıplak "olacak" yasağı, meşru Türkçeyi engelledi

**Ne oldu.** Vaka defteri ve denetim mirası sayfa olarak yayımlanınca dil
koruması onları reddetti. Eşleşen kalıp `olacak`, geçtiği yerler:

    "her tekil bulgunun sınıfı taranmış olacak"
    "koruyucular var derken lazım olacak satır budur"

İkisi de sıradan Türkçe; depremle ilgisi yok.

**Kalıp SİLİNMEDİ, KOŞULA BAĞLANDI.** İki sınıf tanımlandı:

    KOŞULSUZ  kesin · kesinlikle · garanti · bekleniyor ki
              -> kesinlik iddiasının KENDİSİ; nerede geçerse geçsin ihlal

    KOŞULLU   olacak · olacağ · gerçekleşecek · vuracak · bekliyoruz
              -> sıradan yardımcı fiiller; ihlal olmaları için DEPREM
                 BAĞLAMINDA (±60 karakter) geçmeleri gerekir

**Gevşetme olmadığı testle sabitlendi:** dört meşru cümle geçiyor, beş
deprem-bağlamlı cümle (büyük harfli dâhil) hâlâ yakalanıyor.

---

## V47 — Desen tabanlı denetim, İDDİA ile REDDİ ayırt edemez

**Ne oldu.** V46'nın düzeltmesinden hemen sonra koruma **arayüz sayfasını**
reddetti. Eşleşen cümle:

> *"**Nerede deprem olacağını** — bunu hiçbir yöntem söyleyemez"*

Bu, kesinlik iddiası değil, **kesinliğin açık reddidir** — hem de sayfanın
en dürüst cümlesi.

**Üçüncü kez aynı yapı.** Aynı sorun daha önce iki kez çıktı:

| # | reddedilen cümle | ne yapıyordu |
|---|---|---|
| V35 | *"kesin deprem tahmini **değildir**"* | kesinliği reddediyor |
| V44/45 | *"deprem **tehlikesinin** düşük olduğu anlamına gelmez"* | yanlış anlamayı reddediyor |
| V47 | *"nerede deprem **olacağını** söyleyemez"* | öngörülebilirliği reddediyor |

**KÖK SINIR — kabullenilir, kapatılamaz.**

> **Desen eşleşmesi, bir cümlenin bir şeyi İDDİA mı ettiğini yoksa REDDİ mi
> ettiğini ayırt edemez.** Olumsuzlama, dilbilgisel olarak kalıptan
> uzaktadır ("değildir", "-mez", "söyleyemez", "anlamına gelmez") ve
> ±N karakterlik bir pencereyle güvenilir biçimde yakalanamaz.

Bir olumsuzlama sezgiselliği yazmak **daha kötüdür**: ihlali gizlemenin yolu
açılır (*"kesinlikle olacak, değil mi?"*), yani muafiyet mekanizmasının
kendisi bir bypass kanalı olur.

**MİTİGASYON — düzeltme değil, KAPSAM BEYANI.**

    dil koruması, KAZARA eklenen kesinlik dilini yakalayan bir ARKA DURAKTIR
    kesinliği REDDEDEN cümleleri ayırt EDEMEZ
    bu yüzden yayımlanan her sayfa AYRICA insan gözüyle okunur

Koruma, insan okumasının yerine geçmez; onu **unutulmaya karşı** korur.

**Uygulama.** Reddedilen cümleler, anlamı korunarak kalıptan kaçınacak
biçimde yazılır (*"bir sonraki depremin yerini ve zamanını"*). Bu bir
kaçınmadır ve **öyle olduğu yazılıdır** — korumanın sınırı gizlenmiyor.

**Genellenen ilke.**

> Bir korumanın kapatılamayan sınırı varsa, çare onu gizlemek ya da
> gevşetmek değil, **sınırı ilan edip yanına ikinci bir katman koymaktır.**
> Burada ikinci katman insan okumasıdır — ve beşinci eksen (anlam) zaten
> onu gerektiriyordu.

---

## V48 — KULLANIM ile ANMA: defter, korumanın kendisini belgeleyince reddedildi

**Ne oldu.** Vaka defteri sayfa olarak yayımlanınca dil koruması onu
reddetti — ve haklı görünüyordu, çünkü sayfa şunları içeriyordu:

    "kesin", "kesinlikle", "garanti", "bekleniyor ki"     (yasak kalıp LİSTESİ)
    "deprem olacak", "DEPREM OLACAK"                       (örnek İHLALLER)

Ama bunların hiçbiri bir **iddia** değil; korumanın **belgelenmesi**.

**Kaçınarak çözülemez.** Defter, yakaladığı ihlalleri **örneklemek
zorundadır**; örneksiz bir vaka kaydı, kaydın kendisini işe yaramaz kılar.

**Kök ayrım — KULLANIM / ANMA.**

> Bir metnin bir kalıbı **kullanması** ile **anması** farklı şeylerdir ve
> desen eşleşmesi bunu ayırt edemez.

V47'nin kardeşidir: orada **iddia / ret**, burada **kullanım / anma**. İkisi
de aynı kökten gelir — desen, bağlamı görmez.

**Çözüm: KAPSAM İLANI, muafiyet değil.**

    dil denetimi   TAHMİN SUNAN sayfalara uygulanır
                   (index.html, metodoloji.html)
    kapsam dışı    BELGE sayfaları (vaka-defteri, denetim-mirasi)

Gerekçe: belge sayfaları **tahmin sunmaz** — sayı, harita, olasılık
içermezler. İçerikleri kaynak belgelerden gelir ve o belgeler zaten insan
gözüyle yazılır.

**Muafiyet SAYFAYA verilir, CÜMLEYE değil** — ve bu kasıtlıdır. Yayın
sayfasında bir ihlali "örneklemek" için meşru sebep yoktur; belge sayfasında
vardır. Test bunu sabitler: yayın sayfasında **anma da ihlal sayılır.**

**Kapsam dışı sayfalar AÇIKÇA LİSTELİDİR** ve site kurulumunda *"KAPSAM DIŞI
(belge — kalıpları anar, kullanmaz)"* satırıyla basılır. Sessiz atlama yok.

**Dört yanlış pozitifin bilançosu.** Dil koruması dört kez meşru metni
reddetti: büyük harf (V33), sözcük sınırı (V45), bağlam (V46), kullanım/anma
(V48) — artı bir kapatılamaz sınır (iddia/ret, V47).

> **Ders: metin denetimi, dilin kendisi kadar karmaşıktır.** Her düzeltme
> yeni bir sınır açtı ve hiçbiri korumayı gereksiz kılmadı — koruma hâlâ
> kazara eklenen kesinlik dilini yakalıyor. Ama **tek başına yeterli
> olmadığı ölçülerek görüldü**: yanında insan okuması gerekiyor, ve bu
> artık ilan edilmiş bir kapsamdır, bir umut değil.

---

## V49 — sessiz varsayılana düşme: kalibre b değeri depoda yoktu

**Nasıl bulundu.** Actions koşusu 35 dakika boyunca yayın dalı üretmedi.
Günlüğe erişimim yok, bu yüzden **en olası sebebi ölçerek** daraltmaya
çalıştım: hattın gerçek import zincirini `ast` ile çıkardım ve depodaki
eserleri `git ls-tree` ile saydım. Aradığım şey kurulum hatasıydı; bulduğum
şey daha kötüsü oldu.

**Bulgu.** `.gitignore` istisnası `!data/processed/mc_b.csv` yazıyordu.
**Böyle bir dosya yok.** Gerçek ad `mc_by_period.csv`. Yani istisna hiçbir
şeyi kapsamıyordu ve dosya depoya hiç girmemişti.

**Neden bu, düşen koşudan daha kötü.** `config.load_mc_and_b()` dosya yoksa
**sessizce varsayılana döner**: mc=3,3 ve **b=1,0**. Bu katalogda kalibre
değer **1,045**'tir ve kodun kendi yorumu şunu söylüyordu:

> *"b=1.0 yaygın bir kısayoldur ama bu katalogda b=1.045 ölçüldü; küçük
> görünen fark M4.5 hedefinde normal oranı ~%5 kaydırır."*

Taze checkout'lu bir bulut koşusu **düşmezdi** — çalışırdı. Künye doğru
olurdu, `worktree: clean` yazardı, yedi koruma da geçerdi. Ve
"normalin kaç katı" alanı ~%5 kaymış olurdu. **Çıktı normal görünür, künye
doğrudur, sayı yanlıştır** — V38 ailesinin en tehlikeli biçimi.

**Dersin genel hâli.** *Bir dosyanın varlığını istisna satırı değil, ölçüm
kanıtlar.* `.gitignore`'a yazılmış bir istisna, dosyanın depoda olduğunu
göstermez; yalnızca birinin öyle sandığını gösterir. Yerelde fark edilemezdi
çünkü dosya yereldeydi — hatanın görünür olduğu tek yer taze bir ortamdı.

**Ve daha genel hâli:** *bir yedek değer (fallback) sessizse, bir hata
değil bir tuzaktır.* `load_mc_and_b` araştırma için doğru davranıyordu
(eksik veriyle çalışabilmek). Yayımda aynı davranış kabul edilemez.

**Düzeltme (üç parça).**
1. `.gitignore` istisnası doğru ada çevrildi; dosya depoya alındı.
2. **Yeni koruma: `kontrol_kalibre_parametreler()`** — dosya yoksa ya da
   b tam 1,0 ise `ParametreHatasi` ile yayım reddedilir. Sessiz düşüş
   yayımda YASAK. (Korumalar 7 → 8.)
3. Üretim bağımlılıkları `requirements-yayin.txt`'e ayrıldı: hattın gerçek
   import zinciri ÖLÇÜLDÜ (`etas`, `numpy`, `pandas`, `scipy`) ve
   `pycsep`, `cutde`, `shap`, `lightgbm`, `matplotlib` üretimden çıkarıldı.
   Bunlar kırılgan derlemelerdir ve hattın kullanmadığı bir bileşenin
   kurulumu koşuyu düşürebilir.

**Kural 9 deneyi — yapıldı.** Üç test:

| deney | beklenen | sonuç |
|---|---|---|
| dosya yok | `ParametreHatasi` | **reddetti** |
| dosya var ama b=1,0 | `ParametreHatasi` | **reddetti** |
| gerçek kalibre dosya | geçer, b≈1,045 | **geçti** |

Üçüncü test gevşetme kontrolüdür: yalnızca ret deneyi yapılsaydı, *her şeyi*
reddeden bir koruma da testi geçerdi. İkinci deney de ayrıca gereklidir —
sadece dosya varlığına bakan bir koruma, boş ya da bozuk bir dosyayı sessizce
geçirirdi.

Ölçülen kalibre değer testte doğrulandı: **b = 1,045**.

---

## V50 — geri çekme kalıcı değildi: geri çekilen yayın ikinci işlemde geri geliyordu

**Nasıl bulundu.** Geri çekme protokolünün kural-9 deneyini yazarken,
deneylerden birini *iki* geri çekmeyle kurdum — amacım eski kaydın
ezilmediğini görmekti. Test kırmızı döndü ve kırdığı şey kayıt değil,
protokolün kendisiydi.

**Bulgu.** `geri_cek()` yalnızca `_arsiv/latest/` dizinini taşıyordu.
Yayının arşivdeki **kendi dizini yerinde kalıyordu.** İkinci bir geri
çekmede "önceki geçerli yayın" araması, az önce geri çekilen sürümü
adayların başında buluyor ve **onu geri getiriyordu.**

    1. geri çekme  ->  latest = B taşındı, latest := A   (arşivde B hâlâ var)
    2. geri çekme  ->  latest = A taşındı, latest := B   <-- B GERİ GELDİ

Yani geri çekme geçiciydi ve bunu hiçbir tek-işlemli test göremezdi.

**Dersin genel hâli.** *Bir kaldırma işlemi, kaldırdığı şeyin bütün
kopyalarını bilmiyorsa kaldırma değildir.* Protokol "yayını çek" diye
tasarlanmıştı; oysa yayının sistemde iki temsili vardı — `latest/` (hangi
yayın yürürlükte) ve arşiv dizini (hangi yayınlar var oldu). Biri
kaldırılıp diğeri bırakıldığında sistem tutarsız kaldı.

**Ve yöntemsel ders:** *bir işlemin idempotent olmadığı yerde tek bir
çağrıyla sınamak yetmez.* Hata ancak ikinci çağrıda görünüyordu. Kural 9
"koruma reddediyor mu" diye sorar; buna bir de **"işlem tekrarlandığında
hâlâ doğru mu"** sorusu eklenir.

**Düzeltme.** Geri çekilen yayının arşiv kopyaları da `_geri_cekilen/`
altına taşınır. Eşleştirme **künyeyle** yapılır (üretim zamanı + katalog
sha256), dizin adıyla değil: bir yayının kimliği künyesidir, klasörünün adı
değil.

**Kural 9 deneyi.** `tests/test_geri_cek.py`, beş deney:

| deney | beklenen | sonuç |
|---|---|---|
| geri çek | `latest` bir öncekine döner | **düştü** |
| aynı deney | dosyalar `_geri_cekilen/` altında | **silinmedi** |
| yerine geçen yok | `null` olarak beyan edilir | **beyan etti** |
| gerekçe 40 karakterden kısa | `GeriCekmeHatasi`, hiçbir şey değişmez | **reddetti** |
| künyesiz yayın | `GeriCekmeHatasi` | **reddetti** |
| iki kez geri çek | ilk çekilen GERİ GELMEZ | **gelmedi** (düzeltmeden sonra) |

---

## V51 — site kurucusu kendi ağacını kirletiyordu (V42'nin HTML tarafı)

**Nasıl bulundu.** Yasal metin sayfasının gerçek yapı içinde dil
denetiminden geçtiğini doğrulamak için siteyi yerelde kurdum. Kurulum
başarılıydı; ama hemen ardından baktığım `git status` temiz değildi:

    M web/vaka-defteri.html

**Bulgu.** Vaka defteri ve denetim mirası sayfaları `docs/*.md`'den **her
kurulumda yeniden üretilir** (V42'nin dersi: tek kaynak). Ama üretilmiş
HTML'ler git'te izleniyordu. Defter büyüdükçe sayfa değişiyor, kurulum
ağacı kirletiyor ve **bir sonraki hat koşusu kirli-ağaç korumasınca
reddediliyordu.**

**Neden V42'nin tekrarı değil, kardeşi.** V42'de çözüm `web/data/` ve
`data/publish/` dizinlerini izlemeden çıkarmaktı — *veri* çıktısı. Aynı
kural *belge* çıktısına uygulanmamıştı. Üretilmiş bir şeyin veri mi HTML mi
olduğu fark etmez; **üretilmiş her şey aynı sınıftandır.**

**Dersin genel hâli.** *Bir ilke, bir dosya türü için değil bir özellik için
konur.* "Üretilmiş çıktı izlenmez" kuralı `web/data/` diye değil
"üretilmiş" diye yazılmalıydı; dizin adına bağlandığı için yeni bir
üretilmiş çıktı sınıfı ortaya çıktığında kural onu kapsamadı.

**Düzeltme.** `web/vaka-defteri.html` ve `web/denetim-mirasi.html`
izlemeden çıkarıldı. `yayin` dalına iş akışı tarafından üretilmiş
hâlleriyle girerler; `main` yalnızca kaynağı (`docs/*.md`) taşır.

**Not — Actions'ta zararsızdı.** Bulut koşusunda hat, site kurucusundan
ÖNCE çalışır ve checkout tazedir; orada bu sıra hiç kirlenmeye yol açmazdı.
Hata yalnızca **yerel** koşuyu engelliyordu. Yine de düzeltildi: yerel koşu
hâlâ desteklenen bir yoldur ve iki ortamın davranışının ayrışması başlı
başına bir risktir.

---

# GERİYE DÖNÜK KAYITLAR

**Bu bölümdeki altı vaka, olduğu sırada düzeltildi ama deftere
GİRİLMEDİ.** Boşluk 26 Ağustos 2026'da bulundu: metodoloji sayfasındaki
"38 kayıt" ifadesini kaynağına bağlarken defteri saydım — 44 başlık vardı
ama numaralar V51'e kadar gidiyordu. Aradaki fark rastgele değildi:
V34, V35, V36, V41, V42, V43 kod yorumlarında ve diğer belgelerde
atıflanıyordu, ama defterde karşılıkları yoktu.

**Neden gizlenmeden yazılıyor.** Bu kayıtları araya sessizce sokmak,
defterin baştan eksiksiz tutulduğu izlenimi verirdi. Defterin değeri
tam da böyle bir izlenim vermemesindedir. Kayıtlar buradadır ve
**geriye dönük oldukları yazılıdır.**

**Dersin kendisi bir vaka.** *Bir sicilin eksiksizliği, sicilin kendisine
bakarak anlaşılmaz.* Defter kendi kendine "tamam" görünüyordu; boşluk
ancak **dışarıdan bir sayımla** — numaralar ile başlıkların
karşılaştırılmasıyla — ortaya çıktı. Bundan sonra bu sayım `site_kur`
içinde yapılır ve sayı künyeye yazılır.

---

## V34 — şema koruması geçerli bir çıktıyı reddetti (yanlış pozitif)

**Bulgu.** Şema koruması, yayımlanan GeoJSON'un taşıması gereken alan
adlarını **varsayarak** yazılmıştı: `kunye`, `p`. Üretilen dosyada bu adlar
yoktu; koruma **geçerli bir çıktıyı reddetti.**

**Neden önemli.** Yanlış pozitif, yanlış negatiften daha az tehlikelidir
ama daha çok aşındırıcıdır: her koşuda öten bir alarm, kapatılan bir alarma
dönüşür. Bir koruma güvenilirliğini yanlış alarmla kaybederse, gerçek
alarmı da kimse dinlemez.

**Dersin genel hâli.** *Bir koruma, koruduğu şeyin ölçülmüş hâline
yazılır — hayal edilmiş hâline değil.* Şema kafadan yazılmıştı; oysa dosya
zaten üretilmişti ve okunabilirdi.

**Düzeltme.** Alan adları üretilen dosyadan **okunarak** yazıldı
(`UST_ALANLAR`, `HUCRE_ALANLARI`, `KUNYE_ALANLARI`) ve kaynağı yorumda
belirtildi: "ÖLÇÜLMÜŞ ŞEMA".

---

## V35 — dil koruması kendi uyarı metnimizi yasakladı

**Bulgu.** Zorunlu uyarı metni, kesinliği **reddeden** bir metindir ve bu
yüzden yasak kelimeleri **zorunlu olarak** içerir:
*"kesin deprem tahmini değildir."* Naif kelime taraması bunu bir ihlal
sandı — koruma **kendi uyarımızı** reddetti.

**İki çözüm vardı ve biri seçildi.**

| seçenek | değerlendirme |
|---|---|
| (a) olumsuzlama sezgiselliği yaz | KIRILGAN — dilbilgisine bağlı, ve **ihlali "değildir" ekleyerek gizlemek kolaylaşır** |
| (b) onaylı metni KİMLİĞİYLE muaf tut | DENETLENEBİLİR — muafiyet tek bir metne ait |

**(b) seçildi.** Onaylı metnin sha256'sı kodda sabittir. Metin bir karakter
değişirse hash tutmaz ve **hat durur**; yeni metin insan tarafından gözden
geçirilip yeniden sabitlenene kadar yayım olmaz.

**Dersin genel hâli.** *Muafiyet desene değil kimliğe verilir.* Desene
verilen bir muafiyet, deseni taklit eden her şeye açılır. Kimliğe verilen
muafiyet yalnızca o şeye aittir ve genişletilemez.

**Not.** Bu ilke sonradan V47'de (iddia/ret) ve V48'de (kullanım/anma)
yeniden sınandı; ikisinde de dil korumasının **desenle çözülemeyecek**
sınırlarına çarpıldı ve çözüm yine kapsam beyanı oldu, sezgisellik değil.

---

## V36 — hat kendi çalışma ağacını kirletiyordu

**Bulgu.** Hat, ürettiği yayını `data/publish/` altına yazıyordu ve bu dizin
git'te izleniyordu. Sonuç: **hat çalıştıktan sonra çalışma ağacı kirli
oluyordu** ve bir sonraki koşu, kirli-ağaç korumasınca reddediliyordu.

**Neden bu bir tuzak.** Koruma doğru çalışıyordu — kirli ağaçta üretilen bir
künye güvenilmez, çünkü kodun hangi hâliyle üretildiği belirsizdir. Ama
kirliliği **korumanın koruduğu sürecin kendisi** üretiyordu. Bir koruma,
kendi ihlalini üreten bir sistemde işe yaramaz hâle gelir: ya kapatılır ya
da her koşudan önce elle temizlik yapılır.

**Dersin genel hâli.** *Üretilmiş çıktı, üretimin girdisiyle aynı yerde
durmaz.* Kaynak izlenir, çıktı izlenmez.

**Düzeltme.** `data/publish/` izlemeden çıkarıldı.

**Sonraki tekrarları.** Aynı kalıp iki kez daha ortaya çıktı — V42'de
`web/data/` ile, V51'de üretilmiş belge sayfalarıyla. Üçüncüsünde dersin
neden iki kez kaçtığı da anlaşıldı: kural **dizin adına** bağlanmıştı,
"üretilmiş olma" özelliğine değil.

---

## V41 — zamanlanmış görev günlüğü yazamadan ölüyordu

**Bulgu.** Yerel günlük koşuyu saran PowerShell betiği başarısız oluyordu
ve **günlükte yalnızca başlık satırı** vardı. Çıkış kodu 1 idi, sebep
görünmüyordu.

**Kök sebep.** `$ErrorActionPreference = "Stop"`. PowerShell 5.1'de yerel
bir programın stderr çıktısı boru hattında `ErrorRecord`'a çevrilir;
"Stop" altında bu, betiği **anında** sonlandırır. Python hattı stderr'e ilk
satırını yazdığı anda sarmalayıcı ölüyordu — ve öldüğü için o satırı
günlüğe geçiremiyordu.

**Neden en kötü hata sınıfı.** Sessiz başarısızlık, yanlış sonuçtan daha
tehlikelidir: yanlış sonuç incelenebilir, olmayan sonuç incelenemez. Site
sessizce eskir ve kimse fark etmez.

**Dersin genel hâli.** *Kaydedicinin işi durdurmak değil, olan biteni
kaydetmektir.* Sarmalayıcı bir koruma değildi; korumalar zaten hattın
içindeydi ve yayımı durduruyorlardı. Sarmalayıcı yalnızca tanıktı — ve
tanığın kendi kendini susturan bir ayarı vardı.

**Düzeltme.** `$ErrorActionPreference = "Continue"` ve gerekçesi yorumda.

**Yapısal kapanış.** GitHub Actions'a taşınmayla bu sınıf **yapısal olarak
kapandı**: günlüğü platformun kendisi saklar ve başarısız koşu bildirim
üretir. Sarmalayıcı yine de kalır — yerel koşu hâlâ desteklenen bir yoldur.

---

## V42 — metodoloji sayfası uyarı metnini ELLE kopyalamıştı

**Bulgu.** Metodoloji sayfası, zorunlu uyarı metnini kendi HTML'ine
kopyalamıştı. Kopya, onaylı metinle **birebir aynı değildi** ve bu yüzden
V35'te kurulan sha256 muafiyetini **kaybetti**: dil koruması sayfayı
reddetti.

**Korumanın haklı olduğu yer.** Koruma burada bir yanlış pozitif üretmedi.
Gerçekten bir sorun vardı: sitede, onaylı olmayan bir uyarı metni
duruyordu. Kopya ile kaynak **sessizce ayrışmıştı**.

**Yanlış çözüm ve doğru çözüm.**

    yanlış  ->  kopyayı düzelt, muafiyeti geri kazandır
    doğru   ->  KOPYAYI KALDIR; sayfa metni künyeden yükler

Kopyayı düzeltmek, ayrışmayı bir kez geri alırdı; ayrışmanın **sebebini**
bırakırdı. Bir sonraki metin değişikliğinde aynı şey tekrar olurdu.

**Dersin genel hâli.** *İki kopya, er ya da geç ayrışır ve ayrışma
sessizdir.* Tek çare kopyayı kaldırmaktır.

**Kapsam.** Aynı ilke `web/data/` için de uygulandı (izlemeden çıkarıldı,
V36'nın kardeşi) ve belge sayfaları `docs/*.md`'den her kurulumda yeniden
üretilir hâle geldi. Metodoloji sayfasındaki "38 kayıt" ifadesi ise
**bu ilkenin gözden kaçmış bir örneğiydi** ve ancak geriye dönük sayımda
bulundu (yukarıdaki giriş).

---

## V43 — yayımlanan hücrelerin yarısı Türkiye dışındaydı

**Bulgu.** Izgara ilan edilmiş bir dikdörtgendir ([35–43] K × [25–45] D) ve
Yunanistan, Bulgaristan, Gürcistan, Suriye, Irak ve İran'ın bir kısmını
içine alır. Yayımlanan **309 hücrenin %50'si Türkiye dışındaydı** ve en
yüksek oranlı hücre — **normalin 82,4 katı** — Irak'taydı.

**Sorun sunum değil, GEÇERLİLİK.** Katalog tamlığı ölçüldü:

| eşik | dış/iç olay oranı |
|---|---|
| M ≥ 3,3 | 0,346 |
| M ≥ 5,5 | 0,639 |

Gerçek sismisite oranı büyüklüğe göre **sabit kalmalıdır.** Artıyorsa küçük
olaylar kaydedilmiyor demektir: sınır dışında küçük olayların **~%46'sı
katalogda yok.**

**Zincir.**

    katalog eksik  ->  uzun vadeli temel oran DÜŞÜK kestiriliyor
                       (medyan 0,00180 vs içeride 0,00411)
                   ->  "normalin kaç katı" ŞİŞİYOR
                   ->  Kerkük'teki 82,4 kat gerçek bir sinyal değil,
                       eksik katalogun ürettiği YAPAY bir değer

**Karar (kullanıcı onayı ile, seçenek A).** Yayın Türkiye sınırlarıyla
kısıtlanır. Gerekçe projenin kendi ilkesidir: **ölçemediğimiz yerde
konuşmayız.** "Yayımla ama işaretle" seçeneği, bilinen yanlış bir sayıyı
uyarıyla süslemek olurdu.

**Dersin genel hâli.** *Bir modelin geçerli olduğu alan, ızgarasının
kapladığı alan değildir.* Izgara bir hesaplama kolaylığıdır; geçerlilik
alanı verinin nerede yeterli olduğuyla belirlenir ve bu **ölçülür**.

**Açık bırakılan.** Bölgesel Mc ölçüp temel oranı düzeltmek (seçenek C) daha
doğrusudur ama ayrı bir ölçüm işidir; bir sonraki ilan paketinin önceden
kayıtlı sorusu olarak yazıldı.

**Kaynak.** Natural Earth 10m admin-0 (kamu malı), künyeli:
`data/processed/tr_sinir.geojson`. Kıyı hücreleri için tampon **0,125
derece** = yarım ızgara adımı, açıkça ilan edilmiştir.

---

## V52 — künyedeki koruma listesi elle yazılmıştı ve üç koruma eksikti

**Nasıl bulundu.** Metodoloji sayfasındaki sabit "38 kayıt" sayısını
kaynağına bağladıktan sonra, aynı ilkeyi bir adım ileri götürüp koruma
listesini de siteye taşımak istedim: kullanıcı, yayımın hangi denetimlerden
geçtiğini görebilmeli. Listeyi künyeden okuttum ve çıktıya baktım —
**altı koruma** yazıyordu.

**Bulgu.** Sistemde dokuz koruma vardı. Künyedeki liste elle yazılmış bir
dizindi ve üçü hiç girmemişti:

| eksik olan | nerede çalışır |
|---|---|
| katalog monotonluğu | `forecast_now.update_catalog` |
| yayın kapsamı (V43) | `kapsam.hucre_maskesi` |
| kalibre parametreler (V49) | `pipeline.kontrol_kalibre_parametreler` |

İlk ikisi `pipeline.py` dışında yaşadığı için listeye yazılması unutulmuştu;
üçüncüsü ise **aynı gün** eklenmişti ve listeye eklenmesi atlanmıştı.

**Neden yakalandığı an önemli.** Liste o âna kadar yalnızca künye
dosyasındaydı — kimse okumuyordu, bu yüzden yanlış olması bir şey
değiştirmiyordu. Siteye taşımaya karar verdiğim anda **yanlış bir koruma
listesi yayımlanacaktı**: kullanıcıya sistemin altı denetimden geçtiği
söylenecekti, oysa dokuz vardı ve üçünün adı hiç geçmeyecekti.

Beyanın bir okuyucusu olmadığı sürece yanlışlığı sonuçsuz kalır; okuyucu
kazandığı anda beyan bir iddiaya dönüşür. **Doğruluğu, okunmaya
başlamadan önce sağlanmalıdır.**

**Dersin genel hâli.** *Bir sistemin kendi hakkındaki beyanı, sistemden
türetilmelidir.* Elle yazılan her beyan — sayı, liste, sürüm, tarih —
kaynağından ayrışır. V42 bunu iki kopya metin için söylemişti; burada aynı
şey bir **liste** için geçerli oldu. Kalıbın genel adı: *ikinci temsil.*

**Düzeltme (ayrışma yapısal olarak kapatıldı).**

1. `pipeline.KORUMALAR` tek kaynak oldu: `(ad, istisna, nerede)` üçlüleri.
   Künye listeyi buradan yazar; site künyeden okur.
2. `test_koruma_listesi_KODLA_AYNI` — ilan edilen istisna kümesinin,
   modüllerde tanımlı koruma istisnalarının kümesine **eşit** olduğunu
   doğrular. Yeni bir koruma eklenip listeye yazılmazsa **test kırılır.**

**Küme, sayı değil.** Eşit sayıda ama farklı elemanlı iki liste bir sayı
kontrolünden geçerdi. Bu projede tekrar tekrar aynı yere geliniyor:
*sayı eşitliği, küme eşitliğinin yerini tutmaz.*

**Testin kendi kural-9 deneyi.** Listeden `KapsamHatasi` yapay olarak
çıkarıldı; test kırıldı ve gerekçeyi doğru yazdı:

    kodda olup ilan edilmeyen : ['KapsamHatasi']

**Açık kalan.** Sitedeki künye, **yayımlanmış** manifestten gelir; bu
düzeltme bir sonraki başarılı koşuda yayına yansır. O ana kadar sitede
eski (altı maddelik) liste durur — bu, düzeltmenin gecikmesi değil,
yayının künyeye bağlı olmasının doğal sonucudur.

---

## V53 — bölge kartları DÜNÜN tahmininden üretiliyordu

**Nasıl bulundu.** İlk bulut koşusu düştü. Günlük okundu: kurulum
sorunsuzdu, katalog çekildi, üç pencerenin tahmini de üretildi — ve hat
bölge kartlarına gelince çöktü:

    FileNotFoundError: data/publish/latest/forecast_7d_m45.geojson yok
                       — önce hat çalıştırılmalı

Bu, ilk bakışta bir soğuk-başlangıç sorunudur: taze checkout'ta önceki
yayın yoktur. Ama sorunun neden orada olduğuna bakınca durum tersine
döndü.

**Bulgu — çökme, sorunun kendisi değil BELİRTİSİYDİ.** Hattın sırası:

    satır 445   bugünün tahminleri GÜN DİZİNİNE yazılır
    satır 454   bölge kartları üretilir   <-- `latest/` OKUR
    satır 498   `latest`, gün dizininden GÜNCELLENİR

Yani kartlar üretilirken `latest/` hâlâ **bir önceki yayındır.** Kartlar
koşunun kendi çıktısını değil, **dünkü tahmini** okuyordu.

**Sonuç: aynı sayfada iki farklı güne ait sayı.** Harita bugünün
olasılıklarını gösteriyor, yanındaki bölge kartları dünün tahmininden
üretilmiş "bölge olasılığı" ve "en yüksek kat" değerlerini gösteriyordu.
Kullanıcı bunları tek bir yayının parçaları sanırdı.

**Neden yerelde hiç görülmedi.** `latest/` yerel makinede her zaman
doluydu. Eksik dosya hatası hiç oluşmadı; yanlış dosya sessizce okundu.
**Hata, doğru çalışıyor gibi görünmesini sağlayan koşulun kendisi
tarafından gizleniyordu.**

**Taşımanın kazandırdığı.** Taze checkout, sessiz bir ayrışmayı gürültülü
bir çökmeye çevirdi. GitHub Actions'a taşımanın gerekçesi hız ya da
otomasyon değildi — **her koşunun bilinen bir durumdan başlaması**ydı. Bu
vaka, o gerekçenin ilk somut karşılığıdır: taşıma daha ilk koşusunda,
yerelde ne kadar koşulursa koşulsun görünmeyecek bir hatayı buldu.

**Dersin genel hâli.** *Bir varsayılan yol, "hangi dosyayı okuduğumu
düşünmedim" demenin sessiz biçimidir.* `guncel()` fonksiyonunun
`geojson_yolu=None → latest/` varsayılanı, çağıranı düşünmekten muaf
tutuyordu. Muafiyet, yanlış cevabı da kapsıyordu.

**İkinci ders — sessizliğin koşulu.** Bir hatanın görülmemesi, olmadığı
anlamına gelmez; çoğu zaman **hatayı görünmez kılan bir koşul** vardır.
Burada o koşul "`latest/` her zaman dolu"ydu. Böyle koşullar aranmalıdır:
*bu hata hangi durumda kendini gösterirdi?* — ve o durum kasten
kurulmalıdır.

**Düzeltme (üç parça).**

1. `guncel()` ve `kartlar()` artık **zorunlu** bir yol alır; varsayılan
   YOKTUR. Çağıran, hangi tahmini okuduğunu söylemek zorundadır.
2. Hat, kartlara **kendi çıktısını** verir:
   `_kartlar(gun_dizini / "forecast_7d_m45.geojson")`.
3. **Yeni koruma — kart-tahmin tutarlılığı** (`KartTutarsizligi`).
   Yolu zorunlu kılmak hatayı düzeltir ama tekrarını engellemez: biri
   yarın yanlış yolu geçirebilir. Koruma iki sha256'yı karşılaştırır —
   kartların okuduğu dosya ile bu koşunun yayımladığı dosya aynı olmak
   zorundadır. Karşılaştırma **yol** üzerinden değil **içerik**
   üzerindendir.

**Kural 9 deneyleri.**

| deney | beklenen | sonuç |
|---|---|---|
| kartlar başka sha taşıyor | `KartTutarsizligi` | **reddetti** |
| kartlarda `kaynak_sha256` yok | `KartTutarsizligi` | **reddetti** |
| kartlar bu koşunun dosyasından | geçer | **geçti** |
| `guncel`/`kartlar` ilk parametresi | varsayılansız | **varsayılansız** |

Dördüncü deney, düzeltmenin **geri alınamamasını** sınar: biri varsayılanı
geri koyarsa test kırılır.

**Yan bulgu — kayma denetçisinin kendisi kaydı.** Yeni koruma eklenince
V52'de kurulan `test_koruma_listesi_KODLA_AYNI` testi kırıldı; ama beklenen
yönde değil. Test, koruma istisnalarını **ad ekiyle** tanıyordu
("...Hatasi", "...Kuculdu") ve `KartTutarsizligi` bu desene uymuyordu.
Yani denetçi, denetlediği şeyin yeni bir örneğini göremiyordu.

Düzeltme, V35'in dersinin doğrudan tekrarı oldu: **tanıma desene değil
kimliğe bağlanır.** Kimlik burada taban sınıftır — `YayimHatasi`'nın
alt sınıfları. Ad ne olursa olsun görülür.

---

## V54 — ölçüm aracı ölçtüğü şeyi bozdu

**Nasıl bulundu.** Kural-9 bulut deneyi için bir şey eksikti: koşu düştüğünde
gerekçeyi okuyamıyordum. Actions günlüğüne token olmadan erişilemiyor,
başarısız koşu da `yayin` dalına yazmıyor (yazmamalı da). Bu yüzden hattın
çıktısını bir dosyaya alıp ayrı bir dala itmeyi ekledim:

    python -u -m src.operational.pipeline 2>&1 | tee hat_cikti.log

Deney koştu ve düştü — ama **beklenen gerekçeyle değil.** `ParametreHatasi`
bekliyordum; günlükte `KirliAgacHatasi` vardı.

**Bulgu.** `tee hat_cikti.log` günlüğü **depo köküne** yazıyor. Takipsiz bir
dosya çalışma ağacını kirletir; hattın **ilk** koruması (kirli ağaç) daha
katalog çekilmeden reddediyor. Yerelde ölçtüm:

    hat_cikti.log VARKEN   worktree = dirty
    hat_cikti.log YOKKEN   worktree = clean

**Bu bir regresyondu.** Deney olmasaydı bile sonraki **her** koşu düşecekti —
üretim, eklendiği andan itibaren durmuştu. Deney onu ilk çalıştırmada
yakaladı; kural 9'un varlık sebebi tam olarak budur. Bir koruma "kurulu"
sayılmadan önce reddettiği gösterilir; burada gösterilen şey, *korumanın
yanlış sebeple reddettiğiydi.*

**Dersin genel hâli.** *Ölçüm aracı, ölçtüğü sistemin içine konmaz.*
Gözlemci gözlenen sistemi değiştirdi. Bu, V36/V42/V51 ailesinin yeni bir
üyesidir ("üretilmiş çıktı, üretimin girdisiyle aynı yerde durmaz") ama bir
farkla: orada kirleten şey **üretilmiş sonuçtu**, burada **günlüğün
kendisiydi**. Sonucu saklamamaya dikkat ettim, tanığı saklamayı unuttum.

**İkinci ders.** *Bir deneyin yanlış sebeple başarılı görünmesi mümkündür.*
Deneyin birinci beklentisi ("koşu düşer") karşılandı, üçüncüsü de ("yayın
dalı değişmez"). Yalnızca beşinci beklenti — gerekçenin ne olduğu —
tutmadı. Eğer gerekçeyi yazmamış olsaydım, deney "başarılı" sayılacak ve
regresyon üretimde kalacaktı. **Beklentiyi önceden ve ayrıntılı yazmak,
deneyi kendi yanılgısından koruyan şeydir.**

**Düzeltme.** Günlük `$RUNNER_TEMP` altına yazılıyor — depo ağacının
dışında. Düzeltmeden sonraki koşu beklenen gerekçeyi verdi:

    ParametreHatasi: mc_by_period.csv YOK -- kalibre Mc/b olmadan yayım
    yapılmaz. Dosya yoksa load_mc_and_b sessizce mc=3.3, b=1.0 döner ve
    'normalin kaç katı' alanı ~%5 kayar.

---

## V55 — `.gitignore` satır içi yorum desteklemez; istisna hiç çalışmamış

**Nasıl bulundu.** Kural-9 deneyinin temizlik yarısında kaldırdığım kalibre
dosyasını geri koymaya çalıştım. `git add` reddetti:

    The following paths are ignored by one of your .gitignore files:
    data/processed/mc_by_period.csv

**Bulgu.** V49'da istisnayı "düzeltmiş" ve şöyle yazmıştım:

    !data/processed/mc_by_period.csv   # DOĞRU AD -- 'mc_b.csv' diye
                                       # yazılmıştı ve dosya depoya girmemişti

`.gitignore` **satır içi yorum desteklemez.** Yalnızca satırın BAŞINDAKİ `#`
yorumdur. Buradaki metin desenin **parçası** olmuş; ortaya `mc_by_period.csv`
diye bitmeyen, hiçbir dosyayla eşleşmeyen bir desen çıkmış.

**Yani V49'un düzeltmesinin yarısı hiç çalışmamış.** Dosya depoya yalnızca
`git add -f` sayesinde girmişti — ve `-f`, tam da "yok sayılıyor ama zorla
ekle" demek olduğu için, istisnanın çalışmadığını *gizlemişti*.

**Neden dört ay değil dört saat sonra bulundu.** Çünkü dosyayı bir kez daha
eklemek gerekti. İzlenen bir dosya için `.gitignore` sonuçsuzdur; kural
ancak dosya yeniden eklenirken sınanır. Kural-9 deneyi bunu tesadüfen
zorunlu kıldı: dosyayı kaldırıp geri koymak, istisnayı ilk kez gerçekten
sınadı.

**Dersin genel hâli.** *Bir beyanın çalıştığı, beyanı okuyarak anlaşılmaz.*
İstisna doğru görünüyordu — doğru dosya adı, doğru sözdizimi görünümü. Onu
yanlış yapan şey, göze görünmeyen bir dil kuralıydı. V52'nin ("bir sistemin
kendi hakkındaki beyanı sistemden türetilmelidir") ve V49'un ("bir dosyanın
varlığını istisna satırı değil ölçüm kanıtlar") doğrudan devamı.

**Düzeltme.** Yorum kendi satırına alındı. **Kanıt:** artık `git add`
dosyayı `-f` olmadan alıyor.

**Açık kalan risk.** Aynı hata `.gitignore`'daki diğer istisna satırlarında
da olabilir. Bu dosyada başka satır içi yorum kalmadığı görüldü; ama genel
bir denetim yazılmadı. Yazılırsa, "her istisna satırının gerçekten bir
dosyayla eşleştiği" sınanmalıdır — desenin varlığı değil, **eşleşmesi**.

---

## V57 — kilitli metin değişti; kilit de değişti

**Olay, hata değil işleyiştir.** Uyarı metninin sonundaki `docs/ROADMAP.md`
göndermesi, sitede karşılığı olmayan bir depo yoluydu; `metodoloji.html`
ile değiştirildi.

Bu metin V35'ten beri **sha256 ile sabittir**: dil koruması kesinlik ifadesi
içeren her çıktıyı reddeder, uyarı metni ise zorunlu olarak "kesin deprem
tahmini değildir" der ve muafiyeti **kimliğinden** alır. Metin değişince
hash tutmaz ve hat durur — tasarım gereği. Bu yüzden `ONAYLI_UYARI_SHA` da
yenilendi:

    d742ca8e...fb85752  ->  b824f0f1...ff5ad83b

**Testteki kopya kaldırıldı.** `tests/test_pipeline.py` metnin ikinci bir
kopyasını tutuyordu. Kaynaktaki metin değişip hash güncellenmeseydi, test
kendi kopyasıyla çalışacağı için **yine geçerdi** — yani korumanın
bozulduğunu göstermezdi. Test artık metni `forecast_now.DISCLAIMER`'dan
içe aktarır. V52'nin ("beyan sistemden türetilir") doğrudan devamı.
