/* ORTAK VERİ VE DİL KATMANI — tasarım adayları 31-40 için.
 *
 * NEDEN TEK DOSYA. On sayfa aynı veriyi okuyor ve aynı dürüstlük metinlerini
 * gösteriyor: "olasılık sıfır değil", "bir uyarı değil", "ölçemedik demektir".
 * Bunları her sayfaya kopyalamak, V42'nin tam kalıbıdır: iki kopya er ya da
 * geç ayrışır ve ayrışma SESSİZDİR. Metin burada bir kez durur; sayfalar
 * yalnızca BİÇİMLENDİRİR.
 *
 * SAYFALARIN YAPMADIĞI ŞEY: hesap. Bu dosya da hesap yapmaz -- yayımlanan
 * JSON'da olmayan hiçbir sayı üretilmez. Tek istisna, hücre olasılıklarının
 * bölge düzeyinde birleştirilmesidir ve o da hattın kendisi tarafından
 * yapılıp `bolge_kartlari.json` içinde yayımlanır; burada yalnızca okunur.
 */
"use strict";

/* ---- ÖLÇEK: ColorBrewer YlOrRd ----------------------------------------
 * Renk körlüğüne güvenli ve parlaklığı monoton artan bir sıralı ölçek.
 * Sitenin ilk sürümündeki mavi->yeşil->amber->kırmızı ölçeği CVD-güvenli
 * DEĞİLDİ: yeşil/amber çifti deuteranopide ayırt edilemez.
 *
 * RENK TEK BAŞINA BİLGİ TAŞIMAZ. Her banda bir SÖZCÜK eşlik eder ve her
 * yerde sayı da yazılır.
 */
const OLCEK = [
  { k: 2,  r: "#ffffb2", s: "normalin biraz üstünde" },
  { k: 5,  r: "#fecc5c", s: "artmış" },
  { k: 10, r: "#fd8d3c", s: "belirgin artmış" },
  { k: 25, r: "#f03b20", s: "yüksek" },
  { k: 60, r: "#bd0026", s: "çok yüksek" },
];

/* Gece temaları için sönümlenmiş varyant: aynı sıra, düşük parlaklık. */
const OLCEK_GECE = [
  { k: 2,  r: "#8a8455", s: "normalin biraz üstünde" },
  { k: 5,  r: "#9a7c3a", s: "artmış" },
  { k: 10, r: "#a05f2c", s: "belirgin artmış" },
  { k: 25, r: "#993326", s: "yüksek" },
  { k: 60, r: "#7a1a20", s: "çok yüksek" },
];

const PENCERELER = [
  { gun: 1,  dosya: "data/forecast_1d_m45.geojson",  ad: "1 gün",  uzun: "Yarına kadar" },
  { gun: 7,  dosya: "data/forecast_7d_m45.geojson",  ad: "7 gün",  uzun: "Bir hafta" },
  { gun: 30, dosya: "data/forecast_30d_m45.geojson", ad: "30 gün", uzun: "Bir ay" },
];

const HAZIRLIK_ESIGI = 20;
const AFAD_URL = "https://www.afad.gov.tr/afet-oncesi-hazirlik";

/* ---- veri ---- */
const al = async (u) => {
  const r = await fetch(u);
  if (!r.ok) throw new Error(u + " okunamadı (" + r.status + ")");
  return r.json();
};

async function veriYukle() {
  const [kunye, kartlar, gj, yerAdlari] = await Promise.all([
    al("data/kunye.json"),
    al("data/bolge_kartlari.json"),
    al("data/forecast_7d_m45.geojson"),
    al("data/hucre_yer_adlari.json"),
  ]);
  return { kunye, kartlar, gj, yerAdlari };
}

/* ---- biçimlendirme ---- */
function yuzde(p) {
  if (p == null) return "—";
  if (p >= 0.01)  return "%" + (p * 100).toFixed(1);
  if (p >= 0.001) return "%" + (p * 100).toFixed(2);
  return "%" + (p * 100).toFixed(3);
}

/* "%0,010" bir insana bir şey söylemez; "10.000'de 1" söyler. */
function bindeKac(p) {
  if (p == null || p <= 0) return "—";
  const n = Math.round(1 / p);
  const y = n >= 1000 ? Math.round(n / 100) * 100
          : n >= 100  ? Math.round(n / 10) * 10
          : n;
  return y.toLocaleString("tr-TR") + "'de 1";
}

function katSozcuk(k, olcek) {
  if (k == null) return "";
  let s = (olcek || OLCEK)[0].s;
  for (const o of (olcek || OLCEK)) if (k >= o.k) s = o.s;
  return s;
}

function katRenk(k, olcek) {
  const O = olcek || OLCEK;
  let r = O[0].r;
  for (const o of O) if (k >= o.k) r = o.r;
  return r;
}

function renkIfadesi(olcek) {
  const O = olcek || OLCEK;
  return ["interpolate", ["linear"], ["get", "times_normal"],
          ...O.flatMap(o => [o.k, o.r])];
}

/* ---- dürüstlük metinleri: TEK KAYNAK ---- */

const METIN = {
  soyler: [
    "Hangi alanlarda olasılığın <b>normalin üstüne</b> çıktığını",
    "Artçı etkisiyle <b>geçici olarak</b> kabaran bölgeleri",
    "Her alan için: olasılık ve normalin kaç katı",
  ],
  soylemez: [
    "<b>Bir sonraki sarsıntının yeri ve zamanı</b> — bunu hiçbir yöntem söyleyemez",
    "Boş alanların <b>güvenli olduğunu</b>; Türkiye'nin her yeri deprem bölgesidir",
    "Bir tarih ya da bir büyüklük",
  ],
  esikNotu:
    "Yalnızca normalin <b>2 katı ve üzerindeki</b> alanlar renklendirilir. " +
    "<b>Boş alanlarda olasılık sıfır değildir</b> — kendi normal düzeyindedir.",
  olasilikNotu:
    "Yüksek gösterilen bir alanda hiçbir şey görülmeyebilir; düşük gösterilen " +
    "bir alanda büyük bir sarsıntı görülebilir. İkisi de yöntemin yanıldığı " +
    "anlamına gelmez — olasılık zaten budur.",
  ikiKatman:
    "Her bölge için iki ayrı bilgi var: <b>bu pencerede ne olduğu</b>, ve " +
    "<b>yöntemin o bölgede ne kadar sınanabildiği</b>. Bunlar farklı " +
    "sorulardır ve birbirine karıştırılmaz.",
  hazirlik:
    "Bu site olasılık yayımlar, tavsiye vermez. Deprem hazırlığı, olasılık " +
    "yüksek ya da düşük olsun, her zaman geçerli bir iştir.",
  /* ZORUNLU AÇIKLAMA. Bu iki liste ürünün beyanıdır, süslemesi değil:
     harita ne iddia ediyor ve neyi iddia ETMİYOR. Tasarım yenilemesinde
     sayfadan düşmüştü; buraya alındı ki bir sonraki yenilemede sayfa
     şablonuyla birlikte kaybolmasın. Testle sınanır. */
  gosterir: [
    "Hangi bölgelerde deprem olasılığının <b>normalden yüksek</b> olduğunu",
    "Geçmiş depremlerin artçı etkisiyle <b>geçici olarak</b> kabaran alanları",
    "Her karede sayıyla: olasılık ve normalin kaç katı",
  ],
  gostermez: [
    "<b>Bir sonraki depremin yerini ve zamanını</b> — bunu hiçbir yöntem söyleyemez",
    "Boş kalan yerlerde <b>deprem olmayacağını</b>; Türkiye'nin her yeri deprem bölgesidir",
    "Belirli bir tarih ya da büyüklük",
  ],
  kaynaklar:
    "Kaynaklar: AFAD · Kandilli Rasathanesi (KOERI) · USGS · EMSC · " +
    "harita altlığı © OpenStreetMap katkıcıları.",
};

function katCumlesi(k) {
  if (k == null) return "";
  if (k >= 25) return "Bu alanda hareketlilik çok yüksek: yakın zamanda büyük bir sarsıntı olmuş ve artçıları sürüyor olabilir.";
  if (k >= 10) return "Bu alanda hareketlilik belirgin biçimde artmış.";
  if (k >= 5)  return "Bu alanda hareketlilik artmış.";
  return "Bu alanda hareketlilik normalin biraz üstünde.";
}

/* "Ne yapmalıyım?" sorusunun cevapsız kalması ya paniğe ya kayıtsızlığa
 * götürür. Site TAVSİYE ÜRETMEZ; yetkili kaynağa YÖNLENDİRİR. Eşik (20 kat)
 * bir ürün kararıdır ve lejantın "yüksek" bandına denk gelir. */
function hazirlikMetni(k) {
  if (k == null || k < HAZIRLIK_ESIGI) return null;
  return {
    metin: "Bu alandaysanız: <b>genel deprem hazırlığınızı gözden geçirmek " +
           "için iyi bir zaman.</b> Ne yapılacağı için yetkili kaynak:",
    baglantiMetni: "AFAD afet öncesi hazırlık rehberi",
    url: AFAD_URL,
  };
}

/* Yöntemin o bölgede ne kadar sınanabildiği. 'fark gösterilemedi' ZAYIFLIK
 * DEĞİL BELİRSİZLİKTİR: o bölgede fark olmadığı değil, bu veriyle
 * GÖSTERİLEMEDİĞİ ölçülmüştür. */
function guvenCumlesi(d) {
  if (!d) return "Bu bölge için ölçüm yok.";
  if (d.ig === null)
    return `Değerlendirme döneminde bu bölgeden yalnızca <b>${d.olay} olay</b>
      düştü — yöntemin burada işe yarayıp yaramadığını ölçecek kadar veri yok.`;
  if (d.hukum === "ETAS üstün")
    return `Bu bölgede yöntem, uzun vadeli ortalamaya göre <b>ölçülebilir
      biçimde daha iyi</b> sonuç verdi (${d.olay} olayla sınandı).`;
  return `Bu bölgeden <b>${d.olay} olay</b> düştü ve yöntemin uzun vadeli
    ortalamadan farklı olup olmadığı <b>gösterilemedi</b>. Bu, bölgenin
    güvenli olduğu anlamına gelmez — ölçemedik demektir.`;
}

/* Rozetin ne demek olduğu, teknik olmayan bir dille. Rozet tek başına
 * ("ölçülemedi") yanlış anlaşılabilir: insan "model burada çalışmıyor" ya da
 * "burası güvenli" diye okuyabilir. İkisi de yanlıştır. */
const HUKUM_ACIKLAMA = {
  sinandi:
    "Bu bölgede yöntem geçmiş verilerle sınandı ve uzun vadeli ortalamaya " +
    "göre ölçülebilir biçimde daha iyi sonuç verdi. Yani buradaki sayıya " +
    "güvenmek için bir dayanak var.",
  olculemedi:
    "Bu bölgede yeterince deprem olmadığı için, yöntemin uzun vadeli " +
    "ortalamadan daha iyi olup olmadığı ÖLÇÜLEMEDİ. Dikkat: bu, bölgenin " +
    "güvenli olduğu ya da yöntemin burada çalışmadığı anlamına GELMEZ. " +
    "Fark yok demiyoruz — farkı gösterecek kadar veri yok diyoruz.",
  yetersiz:
    "Değerlendirme döneminde bu bölgeden çok az deprem düştü; yöntemin " +
    "burada işe yarayıp yaramadığını ölçecek kadar veri yok. Bu, bölgede " +
    "deprem olmayacağı anlamına GELMEZ — Türkiye'nin her yeri deprem " +
    "bölgesidir.",
};

function hukumEtiketi(h) {
  const e = h === "ETAS üstün"         ? { sinif: "sinandi",    metin: "yöntem sınandı" }
         : h === "fark gösterilemedi"   ? { sinif: "olculemedi", metin: "ölçülemedi" }
         : { sinif: "yetersiz", metin: "yeterli veri yok" };
  e.aciklama = HUKUM_ACIKLAMA[e.sinif];
  return e;
}

/* ---- tazelik ---- */
function tazelik(kunye) {
  const t = kunye.tazelik || {};
  const uretim = new Date(t.uretim_zamani || kunye.yayin_uretim);
  const saat = (Date.now() - uretim.getTime()) / 3.6e6;
  const esik = t.bayatlik_esigi_saat || 7;
  // KADANS KÜNYEDEN OKUNUR, SAYFAYA ELLE YAZILMAZ. Önceki sürümde metin
  // "sistem günde bir kez yenilenir" diye sabitti; kadans üç saate inince
  // sayfa YANLIŞ bir şey söylemeye devam ederdi ve bunu hiçbir şey haber
  // vermezdi (V42 kalıbı).
  const s_ara = t.yayin_araligi_saat || 3;
  const aralik = s_ara >= 24 ? `${Math.round(s_ara / 24)} günde bir`
                             : `${s_ara} saatte bir`;
  const yas = saat < 1  ? "az önce"
            : saat < 24 ? `${Math.round(saat)} saat önce`
            : `${Math.floor(saat / 24)} gün ${Math.round(saat % 24)} saat önce`;
  return {
    yas, esik, saat, bayat: saat > esik,
    metin: `${kunye.yayin_origin} tarihli tahmin · ${yas} üretildi · ` +
           `katalogdaki son olay ${kunye.katalog.son_olay.slice(0, 16)}`,
    bayatMetni: `${yas} üretildi; sistem ${aralik} yenilenir ve ${esik} ` +
      `saati aşan yayınlar güncel sayılmaz. Gösterilen sayılar o tarihteki ` +
      `duruma aittir — <b>bugünün durumu farklı olabilir.</b>`,
  };
}

/* ---- özet: yayımlanan veriden türetilir, hesap yok ---- */
function ozet(kartlar, gj, gun) {
  const sirali = Object.entries(kartlar.bolgeler)
    .filter(([, v]) => v.guncel.bolge_olasiligi != null)
    .sort((a, b) => b[1].guncel.bolge_olasiligi - a[1].guncel.bolge_olasiligi);
  const esikUstu = Object.values(kartlar.bolgeler)
    .reduce((a, v) => a + (v.guncel.yayimlanan_hucre || 0), 0);
  const tepe = (gj ? gj.features : [])
    .reduce((a, f) => Math.max(a, f.properties.times_normal || 0), 0);
  if (!sirali.length || esikUstu === 0) {
    return {
      bos: true, esikUstu: 0, tepe: 0, gun,
      cumle: `Önümüzdeki <b>${gun} gün</b> için Türkiye'de normalin iki katını
        aşan <b>hiçbir alan yok</b>. Bu, olasılığın sıfır olduğu anlamına
        gelmez — her yer kendi normal düzeyinde.`,
    };
  }
  const [ad, v] = sirali[0], g = v.guncel;
  return {
    bos: false, esikUstu, tepe, gun,
    enYuksekBolge: ad, olasilik: g.bolge_olasiligi, kat: g.en_yuksek_kat,
    cumle: `Önümüzdeki <b>${gun} gün</b> içinde hareketliliğin en yüksek olduğu
      bölge <b>${ad}</b>. Orada M4,5 ve üzeri bir sarsıntı olasılığı
      <b>${yuzde(g.bolge_olasiligi)}</b> — kabaca ${bindeKac(g.bolge_olasiligi)}.
      Türkiye genelinde <b>${esikUstu} alanda</b> hareketlilik normalin en az
      iki katı.`,
  };
}

function bolgeSirali(kartlar) {
  return Object.entries(kartlar.bolgeler).sort((a, b) =>
    (b[1].guncel.bolge_olasiligi || 0) - (a[1].guncel.bolge_olasiligi || 0));
}

/* ---- künye satırları ---- */
function kunyeSatirlari(k) {
  const m = k.model_kunyesi, kp = k.urun_kapisi;
  return [
    ["yöntem", m.method],
    ["parametre sha256", m.etas_params_sha256.slice(0, 16) + "…"],
    ["katalog sha256", m.catalog_sha256.slice(0, 16) + "…"],
    ["katalogdaki son olay", k.katalog.son_olay.slice(0, 16)],
    ["commit", m.commit.slice(0, 12)],
    ["çalışma ağacı", m.worktree],
    ["yayımlama eşiği", "normalin " + k.min_times_normal + " katı"],
    ["kapsam", "Türkiye sınırları içi"],
    ["ürün kapısı", kp
      ? `kalibrasyon ${kp.oran.toFixed(3)} · band ${kp.band[0]}–${kp.band[1]} · geçti`
      : "ölçüm yok"],
  ];
}

/* ---- harita ---- */
/* ---- ALTLIK: "Google Maps görünümü" --------------------------------------
 * Google Maps KULLANILMAZ (lisansı buna izin vermez ve bir kilitlenme
 * yaratır). Görünüm olarak en yakın açık altlık CARTO "Voyager": açık
 * bej kara, mavi su, beyaz yollar, gri şehir adları.
 *
 * ÖNEMLİ: altlık artık FİLTRESİZ gösterilir. Önceki koyu tema, altlığı
 * kısıp doygunluğunu düşürüyordu; o zaman "hangi şehir" sorusu haritadan
 * okunamıyordu. Şimdi altlık kendi hâlinde, HÜCRELER yarı saydam.
 *
 * ATIF ZORUNLU: OpenStreetMap katkıcıları + CARTO. Kaynak satırı da
 * güncellendi (METIN.kaynaklar) -- atıfsız altlık kullanılmaz.
 */
const ALTLIK = {
  /* ANAHTARSIZ VE KOTASIZ OLMAK ZORUNDA (V56).
   *
   * CARTO Voyager buraya bir daha yazılmaz: anonim kullanımda taşıyıcı,
   * görüntü alanı doldurulurken karoların yerine "API key required"
   * damgası veriyordu. Sunucudan tek tek çekilen karolar gerçek döndüğü
   * için yerel denemede görünmüyordu -- bir altlığın çalıştığı, tek karo
   * denemesiyle değil gerçek kullanım yoğunluğunda gösterilebilir.
   *
   * Vektör stiller (OpenFreeMap/liberty) da denendi ve GERİ ALINDI (V58):
   * etiketler zum eşiklerine bağlıdır, ülke ölçeğinde şehir adları hiç
   * çıkmaz. Bu harita ülke ölçeğinde okunur; okunmayan bir altlık,
   * anahtarsız olsa da işe yaramaz.
   *
   * ATIF ZORUNLUDUR: burası değişirse METIN.kaynaklar ve yasal.html §3
   * aynı kalemde güncellenir -- atıfsız altlık kullanılmaz. */
  osm: {
    tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
    atif: "© OpenStreetMap katkıcıları",
  },
};

function rasterStil(alt, a) {
  return { version: 8,
    sources: { osm: { type: "raster", tiles: alt.tiles, tileSize: 256,
                      attribution: alt.atif } },
    layers: [{ id: "osm", type: "raster", source: "osm",
      paint: { "raster-opacity": a.altlikOpaklik ?? 0.35,
               "raster-saturation": a.doygunluk ?? -0.9,
               "raster-contrast": a.kontrast ?? 0.2 } }] };
}

function haritaOlustur(kap, gj, ayar) {
  const a = ayar || {};
  const alt = ALTLIK[a.altlik || "osm"];
  const harita = new maplibregl.Map({
    container: kap,
    style: rasterStil(alt, a),
    center: a.merkez || [35.2, 39.0], zoom: a.zum ?? 4.9,
    attributionControl: { compact: true },
  });
  harita.addControl(new maplibregl.NavigationControl({ showCompass: false }),
                    a.denetimKonumu || "top-right");
  harita.on("load", () => {
    harita.addSource("t", { type: "geojson", data: gj });
    harita.addLayer({ id: "hucre", type: "fill", source: "t",
      paint: { "fill-color": renkIfadesi(a.olcek),
               "fill-opacity": a.dolguOpaklik ?? 0.85 } });
    harita.addLayer({ id: "kenar", type: "line", source: "t",
      paint: { "line-color": a.kenarRengi || "#16181a",
               "line-width": a.kenarKalinlik ?? 0.6,
               "line-opacity": a.kenarOpaklik ?? 0.55 } });
    if (a.tiklama) {
      harita.on("click", "hucre", e => a.tiklama(e.features[0].properties, e.lngLat));
      harita.on("mouseenter", "hucre", () => harita.getCanvas().style.cursor = "pointer");
      harita.on("mouseleave", "hucre", () => harita.getCanvas().style.cursor = "");
    }
  });
  return harita;
}

function hucreMerkezi(f) {
  const k = f.geometry.coordinates[0];
  return [k.reduce((a, c) => a + c[0], 0) / k.length,
          k.reduce((a, c) => a + c[1], 0) / k.length];
}

/* ---- Türkçe duyarlı arama ---- */
function trKucuk(s) {
  return (s || "").replace(/İ/g, "i").replace(/I/g, "ı").toLowerCase();
}
function sadelestir(s) {
  return trKucuk(s).replace(/[çğıöşü]/g, c =>
    ({ "ç": "c", "ğ": "g", "ı": "i", "ö": "o", "ş": "s", "ü": "u" }[c]));
}
function yerAra(yerAdlari, metin) {
  const q = sadelestir(metin.trim());
  if (q.length < 2) return [];
  const out = [];
  for (const [id, y] of Object.entries(yerAdlari))
    if (sadelestir(y.il).includes(q) || sadelestir(y.ilce).includes(q))
      out.push([+id, y]);
  return out;
}
