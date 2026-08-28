/* YAYIN TETİKLEYİCİSİ — Cloudflare Worker
 *
 * NEDEN VAR. Yayın GitHub Actions üzerinde koşar, ama koşuyu BAŞLATAN şeyin
 * GitHub'ın kendi `schedule` tetiği olması ölçülerek elendi: 28 Ağustos 2026
 * sabahı 00:30 yuvası ~1 saat 45 dakika gecikmeyle başladı, 03:30 ve 06:30
 * yuvaları hiç çalışmadı. Actions `schedule` sözleşme gereği "en iyi çaba"
 * niteliğindedir; kamuya açık depolarda yoğunlukta gecikir ve koşu düşürür.
 *
 * Bu Worker o kararı dışarı alır. İş akışı yine GitHub'da koşar; yalnızca
 * "şimdi koş" diyen taraf değişir.
 *
 * İKİ TETİK, TEK MANTIK:
 *
 *   TABAN    Son yayının üzerinden TABAN_SAAT geçtiyse koş. Sakin dönemde
 *            sistemin nabzı budur.
 *
 *   OLAY     Eşik büyüklüğün üzerinde, yayımlanmış katalogda HENÜZ OLMAYAN
 *            bir olay görülürse hemen koş. Gerekçesi projenin kendi
 *            ölçümünde: olay teriminin %98,8'i 120 başlangıç içindeki en
 *            yüksek 10 olaylı başlangıçtan geliyor (docs/MANSET.md). Modelin
 *            değeri düzgün aralıklara yayılmaz, OLAY ANINDA yoğunlaşır. Sabit
 *            aralık, sakin haftada boşuna koşar; dizi başlayınca geciktirir.
 *
 * DURUM TUTULMAZ. Worker'ın hafızası yoktur ve olmasına gerek de yoktur:
 * "en son ne zaman yayımlandı" sorusunun cevabı zaten yayımlanmış künyededir
 * (`/data/kunye.json`), "katalog nereye kadar görüyor" da öyle. Ayrı bir
 * depoda durum tutmak, o durumun künyeden ayrışması riskini yaratırdı --
 * bu projede tekrar tekrar görülen kusur ailesi (V42).
 *
 * KUYRUK YAPMAZ. Tetiklemeden önce GitHub'a sorulur: bu iş akışının koşan
 * ya da kuyrukta bekleyen bir örneği varsa çıkılır. Actions tarafındaki
 * `concurrency` grubu zaten üst üste binmeyi engeller, ama kuyruğa
 * yığmak da anlamsız iş üretir.
 *
 * YETKİ. Kullanılan token YALNIZCA bu depoya ve YALNIZCA `Actions:
 * Read and write` yetkisine sahip olmalıdır (fine-grained). Sızması hâlinde
 * yapabileceği tek şey koşu tetiklemektir; koda da `yayin` dalına da
 * yazamaz.
 */

const UA = "depremrapor-tetikleyici/1.0 (+https://depremrapor.com)";

export default {
  async scheduled(_olay, env, ctx) {
    ctx.waitUntil(calis(env));
  },

  // Elle deneme için: GET /  -> ne yapacağını söyler ama TETİKLEMEZ.
  // Tetiklemeyi bir HTTP ucuna bağlamak, o ucu bilen herkese tetik
  // düğmesi vermek olurdu.
  async fetch(istek, env) {
    const karar = await kararVer(env);
    return new Response(JSON.stringify(karar, null, 2), {
      headers: { "content-type": "application/json; charset=utf-8" },
    });
  },
};

async function calis(env) {
  const karar = await kararVer(env);
  if (!karar.tetikle) {
    console.log("tetiklenmedi:", karar.gerekce);
    return;
  }
  const sonuc = await tetikle(env, karar.sebep);
  console.log("tetiklendi:", karar.sebep, "->", sonuc);
}

/* ---- karar ------------------------------------------------------------ */

export async function kararVer(env) {
  const tabanSaat = Number(env.TABAN_SAAT ?? 3);
  const asgariAraDk = Number(env.ASGARI_ARA_DK ?? 25);
  const esikMw = Number(env.ESIK_MW ?? 4.5);
  const simdi = Date.now();

  // 1. GitHub'a sorulabiliyor mu, ve koşan/kuyrukta koşu var mı?
  const gh = await kosuDurumu(env);
  if (!gh.ok) {
    // KÖRLEMESİNE TETİKLENMEZ: soramadıysak muhtemelen tetikleyemeyiz de.
    // Uzun süren bir kesinti, sitedeki yayın yaşı göstergesinden okunur.
    return { tetikle: false, gerekce: `GitHub sorulamadı — ${gh.hata}`, github: gh };
  }
  if (gh.acik) {
    return { tetikle: false, gerekce: `koşu sürüyor (${gh.acik})`, github: gh };
  }

  // 2. Yayımlanmış künye: son üretim ve katalogun gördüğü son olay
  const kunye = await kunyeAl(env);
  if (!kunye) {
    return { tetikle: false, gerekce: "künye okunamadı — kör tetikleme yapılmaz" };
  }
  const uretim = Date.parse(kunye.uretim_zamani);
  const yasSaat = (simdi - uretim) / 3.6e6;

  // 3. TABAN
  if (yasSaat >= tabanSaat) {
    return {
      tetikle: true,
      sebep: `taban: son yayın ${yasSaat.toFixed(1)} saat önce`,
      yasSaat, github: gh,
    };
  }

  // 4. OLAY — çok sık tetiklememek için asgari ara korunur
  if (yasSaat * 60 < asgariAraDk) {
    return {
      tetikle: false,
      gerekce: `son yayın ${(yasSaat * 60).toFixed(0)} dk önce, asgari ara ${asgariAraDk} dk`,
      yasSaat, github: gh,
    };
  }
  const olay = await yeniOlay(esikMw, kunye.katalog_son_olay);
  if (olay) {
    return {
      tetikle: true,
      sebep: `olay: M${olay.mag} ${olay.zaman} (${olay.kaynak})` +
             ` — yayımlanmış katalog ${kunye.katalog_son_olay} tarihine kadar görüyor`,
      yasSaat, github: gh,
    };
  }

  return {
    tetikle: false,
    gerekce: `taban dolmadı (${yasSaat.toFixed(1)}/${tabanSaat} saat), yeni olay yok`,
    yasSaat, github: gh,
  };
}

/* ---- GitHub ----------------------------------------------------------- */

function ghBaslik(env) {
  return {
    "authorization": `Bearer ${env.GITHUB_TOKEN}`,
    "accept": "application/vnd.github+json",
    "x-github-api-version": "2022-11-28",
    "user-agent": UA,
  };
}

/* "SORAMADIM" İLE "KOŞU YOK" AYNI ŞEY DEĞİLDİR.
 *
 * İlk yazımda bu işlev, API'ye ulaşamadığında da `null` döndürüyordu ve
 * `null` "koşan koşu yok" anlamına geliyordu. Sonuç: girilmemiş ya da
 * geçersiz bir token, sağlıklı bir kurulumdan AYIRT EDİLEMİYORDU --
 * karar ucu "tetikle" diyor, tetikleme 401 ile sessizce düşüyordu.
 *
 * Nitekim ilk kurulumda tam bu oldu: süren bir koşu varken uç "koşu yok"
 * dedi. Kusur token'da değil, kusuru görünmez kılan bu satırdaydı.
 */
async function kosuDurumu(env) {
  if (!env.GITHUB_TOKEN) {
    return { ok: false, hata: "GITHUB_TOKEN secret'ı girilmemiş" };
  }
  const u = `https://api.github.com/repos/${env.DEPO}/actions/workflows/` +
            `${env.IS_AKISI}/runs?per_page=5`;
  let r;
  try {
    r = await fetch(u, { headers: ghBaslik(env) });
  } catch (e) {
    return { ok: false, hata: `GitHub'a ulaşılamadı: ${e}` };
  }
  if (!r.ok) {
    const ek = r.status === 401 ? " — token geçersiz ya da süresi dolmuş"
             : r.status === 403 ? " — token bu depoya yetkili değil (Actions izni?)"
             : r.status === 404 ? " — depo ya da iş akışı adı yanlış, veya token"
                                  + " bu depoyu görmüyor"
             : "";
    return { ok: false, hata: `GitHub API ${r.status}${ek}` };
  }
  const d = await r.json();
  const acik = (d.workflow_runs || []).find(
    (x) => x.status === "in_progress" || x.status === "queued");
  const son = (d.workflow_runs || [])[0];
  return {
    ok: true,
    acik: acik ? `${acik.status} #${acik.id}` : null,
    sonKosu: son ? { tetik: son.event, durum: son.status,
                     sonuc: son.conclusion, zaman: son.created_at } : null,
  };
}

async function tetikle(env, sebep) {
  const u = `https://api.github.com/repos/${env.DEPO}/actions/workflows/` +
            `${env.IS_AKISI}/dispatches`;
  const r = await fetch(u, {
    method: "POST",
    headers: { ...ghBaslik(env), "content-type": "application/json" },
    body: JSON.stringify({
      ref: env.DAL || "main",
      inputs: { sebep: sebep.slice(0, 200) },
    }),
  });
  return r.status === 204 ? "ok" : `HTTP ${r.status} ${await r.text()}`;
}

/* ---- yayımlanmış künye ------------------------------------------------ */

async function kunyeAl(env) {
  const site = env.SITE || "https://depremrapor.com";
  const r = await fetch(`${site}/data/kunye.json`, {
    headers: { "user-agent": UA },
    cf: { cacheTtl: 0, cacheEverything: false },
  });
  if (!r.ok) return null;
  const k = await r.json();
  const t = k.tazelik || {};
  if (!t.uretim_zamani) return null;
  return {
    uretim_zamani: t.uretim_zamani,
    katalog_son_olay: (k.katalog && k.katalog.son_olay) || null,
  };
}

/* ---- olay kaynakları --------------------------------------------------
 *
 * Tetik için AFAD birincil, EMSC yedektir. Hattın kendisi AFAD'ı birincil
 * katalog olarak kullanır; buradaki tek soru "yeni bir şey oldu mu",
 * dolayısıyla hangi kaynağın önce haber verdiği önemli değildir. İkisi de
 * yanıt vermezse tetiklenmez -- kaynak susunca körlemesine koşmak, boşuna
 * koşmaktır.
 */

async function yeniOlay(esikMw, katalogSonOlay) {
  // Künyedeki biçim: "2026-08-27 11:21:29.760000+00:00". Date.parse bunu
  // her ortamda aynı okumaz; araya boşluk yerine T konur ve saat dilimi
  // yoksa UTC varsayılır.
  const sinir = katalogSonOlay ? zamanCoz(katalogSonOlay) : null;
  const taban = sinir ?? (Date.now() - 6 * 3.6e6);
  // 24 saatten eskiye bakılmaz: tetik "yeni bir şey oldu mu" sorusudur,
  // katalog boşluğu doldurma işi değildir.
  const bas = new Date(Math.max(taban, Date.now() - 24 * 3.6e6));
  return (await afadOlay(esikMw, bas)) || (await emscOlay(esikMw, bas));
}

async function afadOlay(esikMw, bas) {
  const bit = new Date(Date.now() + 60_000);
  const u = "https://deprem.afad.gov.tr/apiv2/event/filter" +
            `?start=${iso(bas)}&end=${iso(bit)}&minmag=${esikMw}` +
            "&orderby=timedesc&limit=20";
  try {
    const r = await fetch(u, { headers: { "user-agent": UA } });
    if (!r.ok) return null;
    const d = await r.json();
    if (!Array.isArray(d) || d.length === 0) return null;
    const e = d[0];
    return { mag: Number(e.magnitude), zaman: e.date, kaynak: "AFAD" };
  } catch {
    return null;
  }
}

async function emscOlay(esikMw, bas) {
  const u = "https://www.seismicportal.eu/fdsnws/event/1/query" +
            `?format=json&minmagnitude=${esikMw}&starttime=${iso(bas)}` +
            "&minlatitude=35&maxlatitude=43&minlongitude=25&maxlongitude=45" +
            "&limit=20&orderby=time";
  try {
    const r = await fetch(u, { headers: { "user-agent": UA } });
    if (!r.ok) return null;
    const d = await r.json();
    const f = (d.features || [])[0];
    if (!f) return null;
    return {
      mag: Number(f.properties.mag),
      zaman: f.properties.time,
      kaynak: "EMSC",
    };
  } catch {
    return null;
  }
}

export function zamanCoz(m) {
  let t = String(m).trim().replace(" ", "T");
  if (!/[Zz]|[+-]\d{2}:?\d{2}$/.test(t)) t += "Z";
  const v = Date.parse(t);
  return Number.isFinite(v) ? v : null;
}


export function iso(d) {
  return d.toISOString().slice(0, 19);
}
