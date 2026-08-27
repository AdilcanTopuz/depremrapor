"""ETAS parametre uzayları arasındaki TEK dönüşüm noktası.

Bu projede üç ayrı parametre uzayı dolaşıyor:

* **paket** (`etas`, Mizrahi/ETH): log10_mu, log10_k0, a, log10_c, omega,
  log10_tau, log10_d, gamma, rho, beta
* **literatür**: mu, K, alpha, c, p, d, q, b
* **analitik modülün kullandıkları**: uzaysal üstel alpha_s = a - rho*gamma,
  efektif tamlık mc_eff = mc - delta_m/2, efektif üst kesim m_max + delta_m/2

Aynı dönüşümün üç yerde elle yapılması, bu projedeki en pahalı hata sınıfının
(sessiz ayrışma) en olası kaynağıdır. Nitekim iki tanesi zaten yaşandı:

1. Üretkenliğin büyüklük üsteli `a` sanılmıştı; doğrusu `a - rho*gamma`, çünkü
   uzaysal çekirdeğin alan integrali D^(-rho) = (d e^(gamma dm))^(-rho) çarpanını
   getirir. Paketin kendi branching_ratio'su bunu kullanır.
2. `etas_params.json`'daki dallanma oranı KESİMSİZ Gutenberg-Richter ile
   hesaplanır (`dm_max=None`), oysa simülasyon büyüklükleri `m_max + delta_m/2`
   ile keser. Bu iki sayı AYNI DEĞİLDİR ve hangisinin kastedildiği her atıfta
   açık yazılmalıdır: `branching_nominal` (kesimsiz, raporlanan) ve
   `branching_effective` (kesimli, simülasyonun fiilen davrandığı).

Kural: parametre dönüşümü gerektiren her yer buradan okur. Elle çevirme yok.
"""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARAMS_PATH = ROOT / "data" / "processed" / "etas_params.json"

LN10 = math.log(10.0)


class EtasParams:
    """Eğitilmiş ETAS parametrelerinin tek okuma noktası."""

    def __init__(self, blob: dict):
        self.raw = blob
        self.p = blob["params"]
        self.mc = float(blob["mc"])
        self.beta = float(blob["beta"])
        self.delta_m = float(blob.get("delta_m", 0.1))
        self.m_max = float(blob.get("m_max", 8.0))

    @classmethod
    def load(cls, path: Path | None = None) -> "EtasParams":
        return cls(json.loads((path or PARAMS_PATH).read_text()))

    # --- paket -> literatür ------------------------------------------------
    @property
    def omori_p(self) -> float:
        """p = 1 + omega. Paketin zaman çekirdeği (t+c)^-(1+omega) biçimindedir."""
        return 1.0 + float(self.p["omega"])

    @property
    def alpha_base10(self) -> float:
        """Literatürdeki alfa: 10^(alfa*dm) biçimi. Paket exp(a*dm) kullanır."""
        return float(self.p["a"]) / LN10

    @property
    def b_value(self) -> float:
        """b = beta / ln(10)."""
        return self.beta / LN10

    @property
    def c_days(self) -> float:
        return 10 ** float(self.p["log10_c"])

    @property
    def tau_days(self) -> float:
        return 10 ** float(self.p["log10_tau"])

    @property
    def d_km(self) -> float:
        """Uzaysal ölçek: d parametresi km^2 boyutundadır, karekökü km verir."""
        return math.sqrt(10 ** float(self.p["log10_d"]))

    @property
    def rho(self) -> float:
        return float(self.p["rho"])

    @property
    def mu_per_km2_day(self) -> float:
        """Arka plan oranı; bu kurulumda uzaysal olarak DÜZGÜNdür."""
        return 10 ** float(self.p["log10_mu"])

    # --- analitik modülün kullandıkları ------------------------------------
    @property
    def alpha_spatial(self) -> float:
        """Uzay-integralli üretkenlik üsteli: a - rho*gamma.

        Bir olayın TÜM UZAYDA beklenen doğrudan artçı sayısı
        k0 e^(a dm) * (pi/rho) (d e^(gamma dm))^(-rho) * T
        olduğundan, büyüklüğe bağımlılık e^((a - rho*gamma) dm)'dir. Üretkenliği
        `a` ile ölçeklemek uzaysal yayılmanın etkisini iki kez saymak olur.
        """
        return float(self.p["a"]) - self.rho * float(self.p["gamma"])

    @property
    def mc_eff(self) -> float:
        """Simülasyonun büyüklük üretiminde kullandığı alt sınır: mc - delta_m/2."""
        return self.mc - self.delta_m / 2

    @property
    def m_max_eff(self) -> float:
        """Simülasyonun üst kesimi: m_max + delta_m/2."""
        return self.m_max + self.delta_m / 2

    @property
    def dm_max(self) -> float:
        return self.m_max_eff - self.mc_eff

    # --- dallanma oranı: İKİ AYRI SAYI -------------------------------------
    def _theta(self):
        from etas.inversion import parameter_dict2array

        d = dict(self.p)
        d.setdefault("log10_iota", -float("inf"))
        return parameter_dict2array(d)

    @property
    def branching_nominal(self) -> float:
        """KESİMSİZ Gutenberg-Richter ile. etas_params.json'da raporlanan budur.

        Bu sayı bir idealizasyondur: sonsuz büyüklüğe kadar entegre eder.
        Simülasyonun fiili davranışı bu değildir.
        """
        from etas.inversion import branching_ratio

        return float(branching_ratio(self._theta(), self.beta, None))

    @property
    def branching_effective(self) -> float:
        """KESİMLİ GR ile — simülasyonun fiilen davrandığı dallanma oranı.

        Analitik yöntemin kütle korunumu testi BU değeri hedeflemelidir; nominal
        değeri beklemek testi haksız yere başarısız gösterir ve hata yanlış yerde
        aranır.
        """
        from etas.inversion import branching_ratio

        return float(branching_ratio(self._theta(), self.beta, self.dm_max))

    def magnitude_tail(self, target_mw: float) -> float:
        """P(M >= target | M >= mc_eff), kesimli GR ile."""
        norm = 1.0 - math.exp(-self.beta * self.dm_max)
        return ((math.exp(-self.beta * (target_mw - self.mc_eff))
                 - math.exp(-self.beta * self.dm_max)) / norm)

    def summary(self) -> dict:
        return {
            "p (Omori)": round(self.omori_p, 4),
            "alfa (10 tabanı)": round(self.alpha_base10, 4),
            "alfa (uzay-integralli)": round(self.alpha_spatial, 4),
            "b": round(self.b_value, 4),
            "c (gün)": self.c_days,
            "tau (gün)": round(self.tau_days, 1),
            "d (km)": round(self.d_km, 2),
            "rho": round(self.rho, 4),
            "mc / mc_eff": (self.mc, self.mc_eff),
            "m_max / m_max_eff": (self.m_max, self.m_max_eff),
            "dallanma (nominal, kesimsiz)": round(self.branching_nominal, 4),
            "dallanma (efektif, kesimli)": round(self.branching_effective, 4),
        }


if __name__ == "__main__":
    ep = EtasParams.load()
    for k, v in ep.summary().items():
        print(f"{k:32s} {v}")
