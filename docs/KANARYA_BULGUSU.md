# Sızıntı kanaryası bulgusu: performans tabanlı tespit BU REJİMDE ÇALIŞMAZ

**Tarih:** 25 Ağustos 2026 · Faz 3, 1. iş

## Kurulan şey

Üç seviyeli sızıntı kanaryası (`src/eval/leakage_canary.py`) ve bir alarm
mekanizması: skor "şüpheli derecede iyi" ise dur.

Alarm eşiği gerekçesiyle yazıldı: mutlak 0,90 (ölçülmüş en iyi model 0,7909) ve
sıçrama +0,10 (bu ölçekte tek adımlık ilerleme beklenmez).

## Bulunan şey — alarm çalışıyor ama YETMEZ

Aynı tohumla ölçüldü (`target_30d_m50_all`, eğitimde 212 pozitif):

    kurulum                              test AUC   temizden fark   alarm
    temiz                                 0,7665          —           —
    ref+1 gün, M>=Mc (zayıf)              0,7697      +0,0032        YOK
    ref+15 gün, M>=5,0 (YARIM pencere)    0,7665      +0,0000        YOK
    ref+30 gün, M>=5,0 (TAM pencere)      1,0000      +0,2335        VAR

**Yarım pencere sızıntısı hiçbir etki yaratmıyor.** O öznitelik hedefin yarısını
DOĞRUDAN veriyor: ilk 15 günde M>=5 olayı olan hücre kesinlikle pozitiftir.

## Kök neden: min_child_samples = 200, pozitif sayısı 212

Üretimdeki LightGBM yapılandırması `min_child_samples=200` kullanıyor ve eğitim
setinde yalnızca **212 pozitif** var.

    sızıntı, kaç satırı etkiliyor    yaprak oluşabilir mi   sonuç
    ~106 (yarım pencere)             HAYIR (106 < 200)      görünmez
    212  (tam pencere)               evet, KIL PAYI         görünür
    212 + bagging 0.8 = ~170         HAYIR                  görünmez

Doğrudan sınandı:

    min_child=200, bagging=0.8 : AUC 0,7665 | sızıntı özniteliğinin önemi     0,0
    min_child=200, bagging=1.0 : AUC 0,7571 | önem                            0,0
    min_child= 50, bagging=0.8 : AUC 1,0000 | önem                       71.533
    min_child= 20, bagging=1.0 : AUC 1,0000 | önem                       89.021

## SONUÇ: performans tabanlı sızıntı tespiti bu rejimde çalışmaz

Bir alarm, yalnızca modelin KULLANABİLDİĞİ sızıntıyı yakalar. Bu kurulumda
model, 200 satırdan az bir grubu yalıtamaz; dolayısıyla **200 satırdan az
etkileyen hiçbir sızıntı skoru değiştirmez ve hiçbir alarm çalmaz.**

Gerçek sızıntılar kısmi olur. Tam sızıntı (hedefin kendisi) zaten kod
incelemesiyle görülür; tehlikeli olan kısmi olandır ve performans tabanlı
dedektör tam da onu göremez.

**Bu, kanaryanın başarısızlığı değil, kanaryanın ÜRÜNÜDÜR.** Kanarya kurulmasa
"alarmımız var" sanılacaktı.

## Yapılacak: yapısal tespit

Sızıntı tespiti **öznitelik kökeni** üzerinden yapılmalı, model performansı
üzerinden değil:

* her özniteliğin hangi zaman aralığından hesaplandığı kayıtlı olmalı
* öznitelik üretimi, ref tarihinden sonraki veriye ERİŞEMEMELİ (yapı gereği,
  disiplinle değil)
* bu kısıt bir testle sabitlenmeli

Performans tabanlı kanarya KALDIRILMAZ -- kaba sızıntıyı yakalar ve alarm
eşiğinin gerekçesi kayıtlıdır. Ama tek dedektör olamaz.

## Yan bulgu: temiz model düzenlileştirmeye DUYARSIZ

    min_child    val logloss   test AUC
        200        0,002870     0,7618
        100        0,002871     0,7618
         50        0,002872     0,7614
         20        0,002872     0,7612
          5        0,002872     0,7612

Gerçek veride öğrenilecek keskin yapı yok; düzenlileştirmeyi gevşetmek hiçbir
şey kazandırmıyor. **Bu, önceki katman ablasyonlarını KURTARIR:** "katkı yok"
sonucu, modelin aşırı düzenlileştirilmiş olmasından kaynaklanmıyor.

Aynı zamanda kendi başına bir bulgu: bu öznitelik kümesinde sinyal geniş ve
yumuşak (önem sıralamasında `poisson_rate` baskın), yerel değil.
