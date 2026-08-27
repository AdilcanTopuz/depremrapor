# Site şartnamesi — ölçülmüş kurallar

Bu belge, arayüz tasarımına geçildiğinde ilk okunacak dosyadır. İçindeki her
madde bir ÖLÇÜME dayanır; tasarım tercihi değildir.

---

## 1. İKİ EKSENLİ ÇÖZÜNÜRLÜK KURALI  (ilk madde)

Sistemin ne söyleyebileceği, dönemin ve ölçeğin fonksiyonudur.

### Zaman ekseni

| dönem | panel neye yaslanır | gerekçe (ölçüm) |
|---|---|---|
| **sakin** | uzun vadeli (zamandan bağımsız) oran; ETAS küçük düzeltme | dizi-dışı kazanç +0,55 → +0,29 ve 365 günde belirsizliğe geçiyor; olay teriminin %98,8'i en yüksek 10 olaylı başlangıçtan |
| **kriz** | ETAS ön planda | dizi penceresinde kazanç +3,81 → +2,47 |

### Mekân ekseni

| dönem | panel hangi ölçekte konuşur | gerekçe (ölçüm) |
|---|---|---|
| **sakin** | BÖLGE; hücre gösterilirse belirsizlik işaretiyle | iki bağımsız yöntem sakin günde aynı bölgeyi gösteriyor ama farklı hücreyi: ortanca ayrım ~22 km (bir hücre), rastgele beklenti 648 km |
| **kriz** | HÜCRE anlamlıdır | artçı bölgesinde oranlar arka planın onlarca-yüzlerce katına çıkar; titreme kaybolur |

**Tek cümlede:** sakin dönemde zamanda ETAS'a değil uzun vadeli orana, mekânda
hücreye değil bölgeye yaslan. Kriz döneminde ikisi de tersine döner.

Kaynak: `docs/MANSET.md` (c) bulgusu ve
`results/archive/2026-08-24_operasyonel_gecis/FARK_RAPORU.md`.

## 2. Yayımlanan hücre eşiği

`min_times_normal = 2,0` (ölçülerek seçildi; tablo
`src/operational/forecast_now.py` içinde). Eşik, eşik öncesi ve sonrası hücre
sayısı yayımlanan dosyaya YAZILIR; gizlenmez.

## 3. Üstünlüğün gösterilemediği bölgeler

Marmara, Batı Anadolu, Kuzey Anadolu doğusu: iki model arasında fark
gösterilemedi (MDE ~1,1 nat). Arayüz bunu **"zayıflık" değil "belirsizlik"**
olarak gösterir ve gizlemez.

## 4. Her tahmin künyesini taşır

Yayımlanan GeoJSON: yöntem, parametre sha256, dallanma oranı (nominal ve
efektif), commit, çalışma ağacı durumu, rastgelelik beyanı. Kirli ağaçtan
yayım reddedilir.

## 5. Uyarı metni

Zorunlu; her tahminle birlikte dağıtılır (README §8).

---

## OPERASYONEL KATMANA GİRİŞ KAPISI — kalibrasyon şartı

**Bu şart Faz 3'ten doğdu ve araştırma sonucu ne olursa olsun geçerlidir.**

> Bir modelin **gözlenen / beklenen** oranı, değerlendirme döneminde
> **[0,80 · 1,25]** bandının DIŞINDA ise, o model operasyonel katmana
> (harita, risk kartı, GeoJSON yayını) **ALINMAZ.**

**Neden band, tek nokta değil.** Kalibrasyon hiçbir zaman tam 1,00 olmaz;
252 olayla Poisson dalgalanması bile ±%13 civarındadır. Band, gerçek sapmayı
örneklem gürültüsünden ayırır.

**Neden mutlak bir kapı.** Sıralama başarısı (AUC) ile kalibrasyon farklı
şeylerdir. Risk kartında "önümüzdeki 7 günde %X" yazan bir sayı, sıralaması
mükemmel olsa bile 1,8 kat düşükse **yanlış bilgidir**. Kullanıcı sıralama
görmez, sayı görür.

### Ölçülmüş durum (25 Ağu 2026)

| model | gözlenen/beklenen | kapıdan geçer mi |
|---|---|---|
| ETAS (analitik, haftalık) | 1,09 | **EVET** |
| Poisson temel | 1,24 | evet (sınırda) |
| LightGBM (Faz 3) | **1,82** | **HAYIR** |

LightGBM, AUC'de ETAS'a eşdeğer olmasına rağmen operasyonel katmana
alınamaz. Bu, "araştırma sonucu" ile "ürün" arasındaki ayrımın ilk somut
uygulamasıdır: eşdeğer bir araştırma sonucu, kullanılabilir bir ürün demek
değildir.

### Kapı, sonuç görülmeden bağlanır

Bu şart bir sonraki model sınıfı (nöral nokta süreci) için **koşudan önce**
ilan edilmiştir (`docs/FAZ3_PLAN.md`, adım 4). Sonuca bakıp band
genişletilmez.


---

## METODOLOJİ SAYFASINA YAZILACAK CÜMLE (kesinleşti, 26 Ağu 2026)

> "İki makine öğrenmesi yaklaşımı (gradyan artırmalı ağaçlar ve nöral nokta
> süreci) aynı veride ETAS'a karşı sınandı. Biri önceden kayıtlı araştırma
> ölçütünü geçti, ancak kalibrasyon şartını sağlamadı; operasyonel sistem
> ETAS ile çalışır. Sonuçlar ve ölçüm koşulları `docs/FAZ3_SONUC.md` ve
> `docs/NPP_SONUC.md` içindedir."

Bu cümle "yapay zekâ kullanıyoruz" iddiasının yerine geçer — ve daha
dürüsttür: kullanmıyoruz, **sınadık ve sonucunu söylüyoruz.**

### Kapının ölçülmüş durumu

| model | gözlenen/beklenen | kapı |
|---|---|---|
| ETAS (analitik, haftalık) | 1,09 | **GEÇER** |
| Poisson temel | 1,24 | geçer (sınırda) |
| LightGBM (Faz 3) | 1,82 | **GEÇMEZ** |
| **NPP (Faz 3)** | **1,52** | **GEÇMEZ** |

İki ML yaklaşımı da kapıda kaldı — ve ikisi de **aynı yönde** (eksik tahmin).
Bu, ortak bir sebebe işaret ediyor olabilir; bir sonraki ilan paketinin
önceden kayıtlı sorusudur.
