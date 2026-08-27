# ETAS ve nöral modeller — kurulum notları (Faz 2-3)

## ETAS (asıl baseline)
Sıfırdan yazma — açık implementasyonlar:
- **`etas` (ETH Zürih / Leila Mizrahi):** `pip install etas` veya github: lmizrahi/etas.
  Katalog formatı: time, latitude, longitude, magnitude. Türkiye kataloğunu ver,
  parametreleri (mu, K, alpha, c, p, d, q, gamma) MLE ile kalibre et.
- **pyCSEP:** `pip install pycsep` — değerlendirme (N/S/T testleri, Molchan) için standart.
  Zenodo'daki CSEP Kaliforniya 10 yıllık tahmin arşivi format referansı olarak kullanılabilir.

Backtest kurgusu:
1. ETAS'ı 1990-2015 ile kalibre et.
2. 2016-2023 için günlük ızgara tahminleri simüle et (her gün, o güne kadarki katalogla).
3. pyCSEP ile gözlenen olaylara karşı puanla; log-likelihood/olay kaydet.

## Nöral nokta süreci (araştırma kolu)
- **RECAST** (Dascher-Cousineau et al. 2023, GRL): GRU tabanlı temporal point process.
  Kod: github "recast earthquake" ara. ~10k+ olayda ETAS'ı geçiyor — Türkiye kataloğu
  bu rejimde.
- **EarthquakeNPP** benchmark (arXiv 2410.08226): NPP modelleri + değerlendirme şablonu.
- **Özgün katkı hedefi:** modele hücre bazlı covariate ekle (grid_features.parquet +
  GSRM gerinim + Coulomb). Mevcut modeller sadece katalog kullanıyor; jeofizik
  koşullama + Türkiye uygulaması literatürde yapılmamış kombinasyon.

## Coulomb gerilim özniteliği (Faz 3)
- Son M>=6.5 olaylar için Okada (1985) dislokasyon çözümü: `okada_wrapper` veya
  `pyrocko` ile hücre merkezlerinde ΔCFS hesapla; zaman içinde kümülatif topla.
- Fay geometrisi: GCMT odak mekanizmaları + MTA/GEM fay doğrultuları.

## Başarı kriteri
Bir model ancak şu koşulla "ETAS'tan iyi" ilan edilir:
- Aynı test dönemi (2021-2023, Kahramanmaraş dahil), aynı ızgara, aynı büyüklük eşiği,
- pyCSEP T-testi ile istatistiksel olarak anlamlı log-likelihood kazancı,
- Sonuç, eğitimde hiç görülmemiş dönemde elde edilmiş olmalı (sızıntı kontrolü).
