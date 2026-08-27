# KURAL 9 — BULUT KOŞUSUNDA RET DENEYİ

**Kural 9:** bir koruma, bir şeyi *reddettiği gösterilene* kadar "kurulu"
sayılmaz. Korumaların ret deneyleri yerelde yapıldı (`tests/`). Bu belge,
aynı şeyi **üretim ortamında** gösterir: bulut koşusu düştüğünde gerçekten
hiçbir şey yayımlanmıyor mu?

---

## Deney öncesi durum (ölçüldü)

    yayin dalı        97b6a180db6a7eae7d93f77b50a9c3ffda030fae
    kosu-gunlugu dalı  (yok)
    son başarılı koşu  33002771839 · üretim 2026-08-26T19:17:44Z
    korumalar          10, hepsi geçti
    çalışma ağacı      clean

---

## Bozulan girdi

`data/processed/mc_by_period.csv` izlemeden çıkarılır. Bu, **V49'un tam
olarak bulduğu durumdur**: dosya yoksa `config.load_mc_and_b()` sessizce
mc=3,3 ve **b=1,0**'a döner; kalibre değer 1,045'tir ve fark "normalin kaç
katı" alanını ~%5 kaydırır.

**Neden bu koruma seçildi.** `kontrol_kalibre_parametreler()`,
`update_catalog()`'tan **önce** çalışır. Yani koşu, AFAD'a tek bir istek
göndermeden düşer: deney ~2 dakika sürer ve kaynak kurumu yormaz.

---

## ÖNCEDEN İLAN EDİLEN BEKLENTİ

Aşağıdakiler koşudan **önce** yazılmıştır. Gerçekleşmeyen her madde,
düzeltilecek bir kusurdur ve bu belgeye öyle yazılacaktır.

| # | beklenti |
|---|---|
| 1 | Koşu **kırmızıya düşer**, "Üretim hattı" adımında |
| 2 | Düşüş **~2-3 dakika** içinde olur (AFAD indirmesine geçmeden) |
| 3 | `yayin` dalı **değişmez** — sha `97b6a180…` aynı kalır |
| 4 | `kosu-gunlugu` dalı **oluşur**; içinde `DUSTU.md` ve `hat_cikti.log` bulunur |
| 5 | `hat_cikti.log` gerekçeyi taşır: `ParametreHatasi` ve `mc_by_period.csv` |
| 6 | Site, bir önceki yayını göstermeye devam eder (dal değişmediği için) |

**Beklenti 4 yeni bir şeyi sınar.** Başarısızlık kaydını ayrı bir dala
yazan adım bu koşuyla birlikte eklendi; o da ilk kez çalışacak. Adım
`continue-on-error: true` taşır — kaydı yazamamak, koşunun düşme
gerekçesini değiştirmemelidir.

---

## SONUÇ — üç koşu, iki kusur

Deney tek koşuda bitmedi. Üç koşu gerekti ve **ikisi kusur ortaya çıkardı.**

### Koşu A — 33008849630 · 2 dakika · DÜŞTÜ

| # | beklenti | sonuç |
|---|---|---|
| 1 | koşu kırmızıya düşer | **evet** |
| 2 | ~2-3 dakika | **2 dakika** |
| 3 | `yayin` dalı değişmez | **evet** — `97b6a180…` aynı |
| 4 | `kosu-gunlugu` dalı oluşur | **evet** |
| 5 | log `ParametreHatasi` taşır | **HAYIR — `KirliAgacHatasi`** |
| 6 | site önceki yayını gösterir | **evet** |

Beşinci beklenti tutmadı ve sebebi **kendi eklediğim ölçüm aracıydı**:
gerekçeyi okuyabilmek için koyduğum `tee hat_cikti.log`, günlüğü depo
köküne yazıyor ve çalışma ağacını kirletiyordu. Hattın ilk koruması onu
hemen reddediyordu.

**Bu bir regresyondu.** Deney olmasaydı da sonraki her koşu düşecekti.
Ayrıntı: vaka defteri **V54**.

### Koşu B — 33009111687 · 2 dakika · DÜŞTÜ (beklenen gerekçeyle)

Günlük `$RUNNER_TEMP` altına alındı. Koşu yine düştü ve gerekçe artık
doğruydu:

    ParametreHatasi: mc_by_period.csv YOK -- kalibre Mc/b olmadan yayım
    yapılmaz. Dosya yoksa load_mc_and_b sessizce mc=3.3, b=1.0 döner ve
    'normalin kaç katı' alanı ~%5 kayar.

`yayin` dalı **yine değişmedi**: iki düşen koşu boyunca `97b6a180…`.

### Koşu C — 33009353266 · 45 dakika · BAŞARILI (temizlik)

Kalibre dosyası geri kondu. Koşu yeşile döndü ve `yayin` dalı ilerledi:

    97b6a180…  ->  6a7c4bf5…
    hat_sonucu     success
    çalışma ağacı  clean
    korumalar      10, hepsi geçti
    katalog yaşı   3,36 saat
    ürün kapısı    1,0885 ∈ [0,80; 1,25] · geçti
    1g 95 · 7g 110 · 30g 128 hücre

**Kart-tahmin tutarlılığı da doğrulandı:** bölge kartlarının okuduğu
`051da621…`, yayımlanan 7 günlük dosyanın sha256'sıyla aynı.

Dosyayı geri koyarken **ikinci kusur** çıktı: `.gitignore` istisnası satır
içi yorum yüzünden hiç çalışmıyormuş (**V55**).

---

## NE GÖSTERİLDİ

1. **Bir koruma reddettiğinde hiçbir şey yayımlanmıyor.** İki düşen koşu
   boyunca `yayin` dalı bir bit değişmedi.
2. **Düşme gerekçesi okunabilir.** `kosu-gunlugu` dalı, Actions arayüzüne ya
   da bir token'a gerek kalmadan gerekçeyi taşıyor.
3. **Koruma her şeyi reddetmiyor.** Girdi düzeltildiğinde koşu yeşile döndü.
   Bu ikinci yarı olmasaydı, "her zaman reddet" diye yazılmış bir koruma da
   deneyi geçerdi.
4. **Beklentiyi önceden yazmak deneyi kendi yanılgısından korudu.** Koşu A,
   beş beklentiyi karşılayıp bir tanesini karşılamadı. Sadece "düştü mü"
   diye baksaydım, deney başarılı sayılacak ve V54 üretimde kalacaktı.

---

## Temizlik

Deney bittikten sonra dosya geri alınır ve bir sonraki koşunun `yayin`
dalını yeniden yazdığı doğrulanır. **Geri alma da deneyin parçasıdır:**
bir korumanın reddettiğini göstermek yeterli değildir; düzeltildiğinde
tekrar geçtiği de gösterilmelidir. Aksi hâlde "her şeyi reddeden" bir
koruma da deneyi geçerdi.
