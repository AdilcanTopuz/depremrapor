# TEST SETİNE DOKUNUŞ DEFTERİ

**Bu belgenin tek işi:** "Test dönemine kaç kez bakıldı?" sorusunun cevabı
dağılmasın. Her dokunuş — kasıtlı ya da yan etki — buraya tam cümleyle yazılır.

**Test dönemi:** 2021-01-01 .. 2024-12-20 (haftalık kurulum, 437.008 satır,
252 pozitif).

**Neden defter tutulur.** Test seti bir kez kullanılabilir. "Kaç kez baktın?"
sorusuna sonradan hafızadan cevap verilemez; verilse de doğrulanamaz. Defter,
cevabı denetlenebilir kılar: her satırın yanında commit karşılığı vardır.

---

## Dokunuş 1 — 2026-08-24, tanılama (sızıntı kanaryası)

Temiz-model test AUC'si **0,7847** (varsayılan hiperparametrelerle, haftalık
tablo, `target_7d_m45_all`) 2026-08-24'te sızıntı kanaryası koşulurken
tanılama amacıyla görüldü.

**İlan paketi bu gözlemden ÖNCE commit'liydi** (`a49f84e`: arama uzayı, seçim
kuralı, ana metrik, Ö5 eşdeğerlik bandı). Gözlem sonrası commit `ad80770`
bunu bildirir. Zaman çizgisi, protokolün hiçbir maddesinin bu sayıya göre
ayarlanamayacağını gösterir.

**Sayının içeriği hakkında:** 0,7847, ETAS'ın dondurulmuş 0,7909'una yakındır.
Bu, Ö5 eşdeğerlik senaryosunun **ilk zayıf işaretidir** — ve yalnızca odur.
Doğrulama-öncesi, tek tohumlu, varsayılan-parametreli tek bir sayıdır; 36'lık
arama ve resmî test değerlendirmesi konuşana kadar hiçbir cümleye dayanak
oluşturmaz. Üzerine plan kurulmaz.

**Bundan sonra:** seçim tamamlanana kadar test setine dokunulmaz.

**Doğuran düzeltme:** kanarya betiği artık test skoru hesaplamaz
(bkz. Dokunuş kaydı yok — Düzeltme 1).

---

## Düzeltme 1 — kanarya doğrulama tabanına geçti

Kanaryanın işi **sızıntı tespitidir, test performansı değil.** Sızıntı,
doğrulama setinde de aynı derecede görünür; test setini kullanmak gereksiz bir
dokunuştu.

`src/eval/leakage_canary.py` artık **doğrulama** AUC'si ile çalışır ve
`_load` test bölümünü yükler yüklemez **siler** — arama betiğindeki desenin
aynısı (veri yokluğu, erişim denetimi değil).

Karşılaştırma tabanı da değişti ve bu bir İYİLEŞTİRMEDİR:

    ESKİ: sabit BEST_KNOWN_AUC = 0,7909 (ETAS, TEST dönemi)
    YENİ: aynı tabloda, aynı bölümde ölçülen TEMİZ MODEL doğrulama AUC'si

Eski taban farklı bir bölümden gelen sabitti; yeni taban eşleşmiştir. Mutlak
eşik (0,90) ve sıçrama eşiği (0,10) **DEĞİŞTİRİLMEDİ** — sonuç görüldükten
sonra eşik oynatmak kural 1'in ihlali olurdu.

**Kural 9 gereği:** yeni tabanda korumanın çalıştığı YENİDEN gösterilir; aksi
hâlde "kurulu" denemez (V15 dersi).

---

## Dokunuş 2 — 2026-08-25, RESMÎ DEĞERLENDİRME (seçim sonrası, tek)

Seçilen bileşim (`lr=0,02 · yaprak=7 · min_child=200 · l2=10`) test döneminde
**bir kez** değerlendirildi. İlan edilen protokol uygulandı; sonuca bakıldıktan
sonra hiçbir yeniden seçim yapılmadı.

    AUC   Poisson 0,6503 | ETAS 0,7909 | ML 0,7869
    ML AUC tohum saçılımı: 0,7874 · 0,7856 · 0,7872
    IG (Poisson'a karşı)  ETAS +1,068 | ML +1,086
    ML - ETAS  +0,018 nat/olay  [-0,164, +0,196]  MDE 0,256

**Ö5 hükmü: EŞDEĞER.** README §3.5 ölçütü (ML, ETAS'ı GEÇMELİ):
**KARŞILANMADI.**

### Doğrulama-test yönü: hangi protokole düştü?

ML'nin test AUC'si (0,7869), doğrulama bölümündeki temiz taban ölçümünden
(0,8529) DÜŞÜK. Bu, **önceden yazılmış beklenen yön**dür
(`docs/SAYI_HARITASI.md`, "doğrulama-test farkı"): test dönemi 2023 dizisini
içerir ve sıralama problemi zorlaşır.

**Beklenmedik yön protokolü TETİKLENMEDİ** — test doğrulamayı geçmedi,
dolayısıyla sızıntı kanalı taraması gerekmiyor.

### Test seti bundan sonra

Bu değerlendirme tekrarlanmaz. Farklılaşma analizi (`scripts/22`) test dönemi
tahminlerini kullanır ama **yeni bir model eğitmez ve yeni bir seçim yapmaz**;
aynı tek değerlendirmenin ayrıştırılmasıdır, ikinci bir dokunuş değildir.

---

## Dokunuş 3 — NİYET VE KAPSAM (dokunuştan ÖNCE yazıldı)

**Bu kayıt, test tahminleri ÜRETİLMEDEN önce yazılmıştır.** Dokunuşun kendisi
değil, niyeti ve kapsamı önce kayda girer.

### Ne yapılacak

NPP aramasının seçtiği bileşim — `gizli=32 · katman=2`, 1794 parametre —
test döneminde **bir kez** değerlendirilecek.

### Kapsam

    model        toplamsal nöral ETAS, seçilen bileşim, 3 tohum (1,2,3)
    veri         436.800 hücre-pencere kesişimi, 252 olay
    ölçülecek    AUC · IG (Poisson'a karşı) · NPP-ETAS farkı + GA + MDE
                 H1 (ölçek düzeltilmiş dizi-dışı) · H2 (dizi beklentisi +
                 kalibrasyon) · Ö5 bandı · ürün kapısı

### ÖN ŞART — determinizm zinciri uçtan uca kanıtlanacak

Modeller arama sırasında kaydedilmemişti; seçilen bileşim **birebir aynı
protokolle** yeniden eğitilecek (aynı tohumlar, aynı tur/sabır, aynı veri
yolu, aynı dizin künyesi).

> Yeniden eğitimin doğrulama NLL'leri, `npp_arama.jsonl` içindeki değerlerle
> **BİREBİR** tutmalıdır. Tutmazsa **test değerlendirmesi BAŞLAMAZ** ve fark
> açıklanır.

Bu, determinizm protokolünün (`docs/NPP_ILAN.md` §6) uçtan uca kanıtıdır:
şimdiye kadar aynı süreç içinde iki eğitimin eşitliği gösterilmişti; burada
**ayrı süreç, ayrı gün, ayrı çağrı** ile gösterilecek.

### Yan kazanç

Modeller bu kez **kaydedilecek** (künyeleriyle). Gelecekteki her analiz —
farklılaşma, çekirdek incelemesi, olası yeniden değerlendirme — yeniden
eğitim maliyeti ödemeyecek.

### SONUÇ (2026-08-26 12:28)

**Ön şart karşılandı:** üç tohumun üçü de aramadaki değerlerle BİREBİR.

    AUC   Poisson 0,6503 | ETAS 0,7909 | NPP 0,7904
    NPP - ETAS  +0,174 [+0,032, +0,317]  MDE 0,204
    kalibrasyon  NPP 1,52  (ETAS 1,09)
    IG ayrışması  OLAY -0,088 + MARUZİYET +0,262

    Ö5 / README 3.5   NPP ETAS'I GEÇTİ / KARŞILANDI
    H1                DOĞRULANDI  (+0,316 [+0,159, +0,469], MDE 0,227)
    H2                KALDI -- beklenti geçti (19,8 -> 41,8), kalibrasyon kaldı
    ÜRÜN KAPISI       GEÇMEDİ (1,52)

Ayrıntı: `docs/NPP_SONUC.md`.

### Sonuç ne çıkarsa çıksın

Raporlanır; yeniden seçim yapılmaz. Kapanış cümleleri
`docs/FAZ3_KAPANIS_TASLAK.md`'de koşu görülmeden yazılmıştır.

---

## Sayaç

| dokunuş | tarih | amaç | sayı görüldü mü |
|---|---|---|---|
| 1 | 2026-08-24 | kanarya tanılaması | evet (0,7847) |
| 2 | 2026-08-25 | LightGBM resmî değerlendirmesi | evet — Ö5: EŞDEĞER, README 3.5: KARŞILANMADI |
| 3 | 2026-08-26 | NPP resmî değerlendirmesi (BİR KEZ) | evet — Ö5 GEÇTİ, ürün kapısı GEÇMEDİ |

