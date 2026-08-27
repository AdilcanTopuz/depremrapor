# Jeofizik katman verileri — indirme talimatları

Bu katmanlar Faz 3'te (ML covariate) kullanılacak. Hepsi açık erişim.

## 1. GEM Global Strain Rate Model (GSRM v2.1)
- Kaynak: GEM Foundation / Kreemer et al. 2014
- Ara: "GSRM v2.1 download" — GEM hazard sitesi veya UNAVCO/EarthScope arşivi.
- İhtiyaç: Türkiye bölgesi için gerinim hızı tensörü (2. invaryant hesaplanacak).
- Kaydet: `data/raw/gsrm/`

## 2. COMET-LiCSAR (Sentinel-1 InSAR)
- https://comet.nerc.ac.uk/comet-lics-portal/ — Türkiye frame'leri, işlenmiş
  deformasyon hızı haritaları ve Anadolu gerinim hızı ürünleri.
- Kaydet: `data/raw/insar/`

## 3. MTA Diri Fay Haritası
- MTA Yerbilimleri Portalı (yerbilimleri.mta.gov.tr) — diri fay shapefile.
- Alternatif: GEM Global Active Faults Database (github: GEMScienceTools/gem-global-active-faults)
  — Türkiye faylarını içerir, doğrudan shapefile/GeoJSON indirilebilir (başlangıç için yeterli).
- Kaydet: `data/raw/faults/`

## 4. TUSAGA-Aktif GPS (opsiyonel, kurumsal)
- Ham veri için TKGM/HGM başvurusu gerekebilir. Başlangıçta gerek yok:
  GSRM + LiCSAR gerinim haritaları yeterli. İleride yayınlardan türetilmiş
  Anadolu GPS hız alanları (ör. Reilinger et al. 2006 ekleri) kullanılabilir.

## 5. Paleosismoloji / segment tekrarlama aralıkları
- Literatürden manuel derleme gerekir (KAF/DAF segment tabloları).
- `data/raw/paleoseismic/segments.csv` olarak elle oluşturulacak şema:
  `segment_id,name,last_rupture_year,mean_recurrence_yr,recurrence_sigma_yr,slip_rate_mm_yr`
