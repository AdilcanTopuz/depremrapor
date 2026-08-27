/* CLOUDFLARE WEB ANALYTICS — çerezsiz ziyaret ölçümü.
 *
 * NEDEN BU ARAÇ. Ölçüm yapılacaksa yasal.html §5'teki beyanı bozmayan bir
 * araçla yapılmalıdır: o beyan "çerez kullanılmaz, tarayıcıda oturum
 * bilgisi saklanmaz" der. Cloudflare Web Analytics çerez yazmaz, yerel
 * depolamaya dokunmaz ve parmak izi çıkarmaz; sayfa görüntüleme sayısını
 * sunucu tarafında toplar. Google Analytics bu beyanı bozardı — bu yüzden
 * seçilmedi.
 *
 * NEDEN AYRI DOSYA. Beacon etiketi yedi sayfaya (beşi elle yazılmış, ikisi
 * belge_sayfa.py tarafından üretilen) elle gömülseydi yedi yerde tutulur ve
 * biri kaçınılmaz olarak unutulurdu. Tek yerde durur; sayfalar bu dosyayı
 * çağırır.
 *
 * ETİKET GİRİLENE KADAR HİÇBİR İSTEK YAPILMAZ. Aşağıdaki değer yer tutucu
 * kaldığı sürece bu dosya sessizce çıkar ve üçüncü taraf bir adrese
 * bağlanılmaz. Biçim sınaması (32 onaltılık hane) bunun için vardır:
 * "ölçülüyor sanmak ama ölçmemek" ile "ölçmüyoruz demek ama bağlanmak"
 * durumlarının ikisi de kapatılmıştır.
 *
 * ETİKET NEREDEN ALINIR: Cloudflare panosu → Web Analytics → siteyi ekle →
 * verilen JS parçacığındaki `token` değeri. Yalnızca aşağıdaki satır
 * değiştirilir; başka hiçbir dosyaya dokunulmaz.
 */
const ANALITIK_ETIKET = "ETIKET_GIRILMEDI";

(function () {
  if (!/^[0-9a-f]{32}$/.test(ANALITIK_ETIKET)) return;
  var s = document.createElement("script");
  s.defer = true;
  s.src = "https://static.cloudflareinsights.com/beacon.min.js";
  s.setAttribute("data-cf-beacon", JSON.stringify({ token: ANALITIK_ETIKET }));
  document.head.appendChild(s);
})();
