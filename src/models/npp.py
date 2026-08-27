"""Toplamsal nöral ETAS — öğrenilen tetiklenme çekirdeği.

    lambda(hücre, hafta) = softplus(mu_theta(statik))
                           + SUM_i softplus(g_theta(dt_i, dr_i, m_i))

`g_theta` küçük bir MLP'dir: ETAS'ın parametrik çekirdeğinin yerini alır.
Toplam havuzlama (permütasyona duyarsız) seçildi çünkü ETAS'ın koşullu
yoğunluğu tanım gereği geçmiş üzerinde bir TOPLAMDIR — sıra taşımaz. Bu, ETAS'ı
**özel durum olarak içeren** bir model sınıfıdır (bkz. `docs/NPP_ILAN.md` §1).

Girdi dizini `src/models/npp_index.py` tarafından ÖNCÜL çekirdekle üretilir;
uydurulmuş ETAS parametreleri bu yola hiç girmez (V24).

DETERMİNİZM. `docs/NPP_ILAN.md` §6: aynı tohum + aynı veri -> BİREBİR aynı
doğrulama NLL. `hazirla()` bunu kuran tek yerdir; testle bağlanır.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import torch
import torch.nn as nn

from src.models.npp_index import GECMIS_YIL, K, MC, ONCUL, R_KM  # noqa: F401

IS_PARCACIGI = 8          # SABİT — toplama sırası ve kayan nokta birleşmezliği
NEG_ORAN = 0.05           # ilan edilmiş negatif alt örnekleme oranı


def hazirla(tohum: int) -> None:
    """Determinizm protokolü — tek yer, tek çağrı."""
    torch.manual_seed(tohum)
    torch.use_deterministic_algorithms(True)
    torch.set_num_threads(IS_PARCACIGI)


class NoralETAS(nn.Module):
    """Toplamsal nöral ETAS.

    ÇIKIŞ YANLILIKLARI TABAN ORANA İLKLENDİRİLİR. Ölçüldü (V28): rastgele
    ilklendirmede başlangıç lambda'sı gerçek taban oranın **558.000 katı**
    çıkıyor (182,6 vs 0,000327). Model 40 turun tamamını 5,7 büyüklük
    mertebesi inmekle geçiriyor ve doğrulama NLL'i 40. turda hâlâ TEKDÜZE
    düşüyor -- yani bileşimler yakınsamış modeller olarak değil, "40 turda ne
    kadar hızlı indi" olarak karşılaştırılırdı.

    Düzeltme nadir-olay Poisson modellerinde standarttır: son katman
    yanlılıkları, başlangıçta lambda ~ taban oran verecek şekilde ayarlanır.
    Arka plan başı taban oranı, tetiklenme başı ~0 verir; model sıfırdan
    başlamak yerine "olay yok" varsayımından başlar.
    """

    def __init__(self, n_statik: int, gizli: int = 32, katman: int = 2,
                 taban_oran: float | None = None):
        super().__init__()
        self.mu = nn.Sequential(
            nn.Linear(n_statik, gizli), nn.ReLU(), nn.Linear(gizli, 1))
        kat: list[nn.Module] = [nn.Linear(3, gizli), nn.ReLU()]
        for _ in range(katman - 1):
            kat += [nn.Linear(gizli, gizli), nn.ReLU()]
        kat += [nn.Linear(gizli, 1)]
        self.g = nn.Sequential(*kat)
        if taban_oran is not None:
            self._ilklendir(taban_oran)

    def _ilklendir(self, taban_oran: float) -> None:
        """softplus(b) = hedef  ->  b = log(exp(hedef) - 1)."""
        import math

        def ters_softplus(v: float) -> float:
            return math.log(math.expm1(v)) if v > 1e-6 else math.log(v)

        with torch.no_grad():
            # arka plan: taban oranın tamamı
            self.mu[-1].weight.mul_(0.1)
            self.mu[-1].bias.fill_(ters_softplus(taban_oran))
            # tetiklenme: olay başına taban oranın 1/(10K)'sı -> toplam ~%10
            self.g[-1].weight.mul_(0.1)
            self.g[-1].bias.fill_(ters_softplus(taban_oran / (10.0 * K)))

    def forward(self, statik: torch.Tensor, olay: torch.Tensor,
                maske: torch.Tensor) -> torch.Tensor:
        """statik (B,F) · olay (B,K,3) · maske (B,K) -> lambda (B,)"""
        arka = nn.functional.softplus(self.mu(statik)).squeeze(-1)
        katki = nn.functional.softplus(self.g(olay)).squeeze(-1)
        return arka + (katki * maske).sum(1)


class Yigin:
    """Satır indekslerinden (statik, olay, maske, y) üretir — bellek dostu."""

    def __init__(self, tablo: str, hedef: str, ozellikler: list[str],
                 olcek_satirlari: np.ndarray | None = None):
        from src.config import cell_center
        from src.ingest.catalog_io import epoch_seconds, read_catalog
        from src.models.npp_index import PROC, load

        self.idx, self.kunye = load()
        df = pd.read_parquet(PROC / tablo)
        df["ref_date"] = pd.to_datetime(df.ref_date, utc=True)
        self.ref_s = epoch_seconds(pd.DatetimeIndex(df.ref_date)).astype(
            np.float64)
        merkez = {int(c): cell_center(int(c)) for c in df.cell_id.unique()}
        self.cla = np.array([merkez[int(c)][0] for c in df.cell_id],
                            dtype=np.float64)
        self.clo = np.array([merkez[int(c)][1] for c in df.cell_id],
                            dtype=np.float64)

        # POISSON ORANI — lgbm.load_dataset ile AYNI yoldan eklenir.
        # Sütun öznitelik tablosunda YOKTUR; Faz 3'te birleştirme sırasında
        # ekleniyordu. Aynı yolu kurmadan NPP farklı bir öznitelik kümesiyle
        # eğitilmiş olurdu (taşıma denetimi, V27).
        if "poisson_rate" in ozellikler and "poisson_rate" not in df.columns:
            rate_col = ("rate_all_m5.0_yr" if hedef.endswith("_all")
                        else "rate_m5.0_yr")
            base = pd.read_csv(PROC / "baseline_poisson.csv")[
                ["cell_id", rate_col]]
            df = df.merge(base, on="cell_id", how="left")
            df["poisson_rate"] = df[rate_col].fillna(0.0)

        x = df[ozellikler].to_numpy(dtype=np.float32)

        # EKSİKLİK GÖSTERGELERİ — "hesaplanamıyor" ile "sıfır" ayrı kalsın.
        #
        # LightGBM NaN'ı YERLİ olarak işler: bölme yönünü öğrenir, eksiklik
        # bilgi taşır. Nöral ağın böyle bir yeteneği yoktur ve ilk sürüm
        # nan_to_num(0) kullanıyordu -- bu, satırların %96,6'sında "b-değeri
        # SIFIR" demektir (fiziksel olarak saçma; b ~ 1).
        #
        # İlan edilen doldurma kuralı "tanımsız istatistikler NaN; sıfırla
        # doldurulmuyor" diyordu. Aynı ANLAMI nöral yolda korumak için
        # TEMSİL değişmek zorunda: eksiklik ayrı bir gösterge sütunu olur,
        # değer eğitim medyanıyla doldurulur (nötr).
        eksik = np.isnan(x)
        self.eksik_sutunlar = [ozellikler[i] for i in range(x.shape[1])
                               if eksik[:, i].any()]
        os_ = slice(None) if olcek_satirlari is None else olcek_satirlari
        with np.errstate(all="ignore"):
            medyan = np.nanmedian(x[os_], axis=0)
        medyan = np.nan_to_num(medyan, nan=0.0)
        x = np.where(eksik, medyan[None, :], x)
        x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
        gostergeler = eksik[:, [ozellikler.index(c)
                                for c in self.eksik_sutunlar]].astype(
            np.float32)
        # ÖLÇEKLEME İSTATİSTİKLERİ YALNIZCA VERİLEN SATIRLARDAN.
        #
        # İlk sürüm bunları TÜM tablodan (eğitim+doğrulama+test) hesaplıyordu.
        # Ağaç modellerinde bu zararsızdı (monoton dönüşüme duyarsızlık) ama
        # nöral modelde GERÇEK BİR SIZINTI KANALIDIR -- kanarya 3'ün aradığı
        # şeyin ta kendisi. Kanarya koşucusu yazılırken kodda bulundu.
        #
        # `olcek_satirlari=None` verilirse tüm tablo kullanılır; bu YALNIZCA
        # kanarya 3'ün sızıntılı kolunu kurmak içindir.
        self.mu_s = x[os_].mean(0, keepdims=True)
        self.sd_s = np.maximum(x[os_].std(0, keepdims=True), 1e-6)
        self.olcek_kapsami = ("TÜM TABLO (sızıntılı)" if olcek_satirlari is None
                              else f"{len(x[os_]):,} satır")
        # gösterge sütunları ölçeklenmez: zaten 0/1
        self.statik = np.concatenate(
            [(x - self.mu_s) / self.sd_s, gostergeler], axis=1)
        self.ozellik_adlari = list(ozellikler) + [
            f"eksik_{c}" for c in self.eksik_sutunlar]
        self.y = df[hedef].to_numpy(dtype=np.float32)
        self.ref_date = df.ref_date.to_numpy()
        self.cell_id = df.cell_id.to_numpy()

        cat = read_catalog(PROC / self.kunye["katalog"])
        cat = cat.dropna(subset=["lat", "lon", "mw"]).sort_values("time")
        cat = cat[cat.mw >= MC].reset_index(drop=True)
        self.et = epoch_seconds(cat["time"]).astype(np.float64)
        self.ela = cat.lat.to_numpy(np.float64)
        self.elo = cat.lon.to_numpy(np.float64)
        self.emw = cat.mw.to_numpy(np.float64)

    def __call__(self, satir: np.ndarray):
        ii = np.asarray(self.idx[satir])
        maske = ii >= 0
        gi = np.where(maske, ii, 0)
        dt = (self.ref_s[satir][:, None] - self.et[gi]) / 86400.0
        dx = (self.elo[gi] - self.clo[satir][:, None]) * 111.32 * np.cos(
            np.radians(self.cla[satir][:, None]))
        dy = (self.ela[gi] - self.cla[satir][:, None]) * 110.57
        dr = np.sqrt(dx * dx + dy * dy)
        olay = np.stack([
            np.log(np.maximum(dt, 0.0) + ONCUL["c_gun"]),
            np.log(dr + ONCUL["d_km"]),
            self.emw[gi] - MC], axis=-1).astype(np.float32)
        olay[~maske] = 0.0
        return (torch.from_numpy(self.statik[satir]),
                torch.from_numpy(olay),
                torch.from_numpy(maske.astype(np.float32)),
                torch.from_numpy(self.y[satir]))


def nll(lam: torch.Tensor, y: torch.Tensor,
        w: torch.Tensor | None = None) -> torch.Tensor:
    """Poisson NLL (sayım biçimi): lambda - y*log(lambda)."""
    l = lam.clamp_min(1e-12)
    kayip = l - y * l.log()
    return (kayip * w).sum() / w.sum() if w is not None else kayip.mean()


def egit(yigin: Yigin, tr: np.ndarray, va: np.ndarray, *, tohum: int,
         gizli: int = 32, katman: int = 2, lr: float = 1e-3,
         tur: int = 40, sabir: int = 8, yigin_boyu: int = 16384,
         weight_decay: float = 1e-5, quiet: bool = True) -> dict:
    """Bir koşu. Doğrulama NLL'i TAM doğrulama kümesinde (ağırlıksız) ölçülür."""
    hazirla(tohum)
    # taban oran YALNIZCA EĞİTİM satırlarından (doğrulama/test görülmez)
    taban = float(max(yigin.y[tr].mean(), 1e-8))
    m = NoralETAS(yigin.statik.shape[1], gizli, katman, taban_oran=taban)
    opt = torch.optim.Adam(m.parameters(), lr=lr, weight_decay=weight_decay)
    rng = np.random.default_rng(tohum)

    poz = tr[yigin.y[tr] > 0]
    neg = tr[yigin.y[tr] == 0]
    en_iyi, en_iyi_tur, bekle = float("inf"), -1, 0
    gecmis = []

    for t in range(tur):
        sec_neg = neg[rng.random(len(neg)) < NEG_ORAN]
        satir = np.concatenate([poz, sec_neg])
        w_all = np.concatenate([np.ones(len(poz), np.float32),
                                np.full(len(sec_neg), 1.0 / NEG_ORAN,
                                        np.float32)])
        sira = rng.permutation(len(satir))
        satir, w_all = satir[sira], w_all[sira]
        m.train()
        for b in range(0, len(satir), yigin_boyu):
            s = satir[b:b + yigin_boyu]
            st, ol, mk, y = yigin(s)
            kayip = nll(m(st, ol, mk), y,
                        torch.from_numpy(w_all[b:b + yigin_boyu]))
            opt.zero_grad(); kayip.backward(); opt.step()

        m.eval()
        with torch.no_grad():
            tot, n = 0.0, 0
            for b in range(0, len(va), yigin_boyu):
                s = va[b:b + yigin_boyu]
                st, ol, mk, y = yigin(s)
                lam = m(st, ol, mk).clamp_min(1e-12)
                tot += float((lam - y * lam.log()).sum()); n += len(s)
        v = tot / n
        gecmis.append(v)
        if not quiet:
            print(f"  tur {t + 1:2d}  doğrulama NLL {v:.8f}")
        if v < en_iyi - 1e-12:
            en_iyi, en_iyi_tur, bekle = v, t, 0
            durum = {k: p.detach().clone() for k, p in m.state_dict().items()}
        else:
            bekle += 1
            if bekle >= sabir:
                break

    m.load_state_dict(durum)
    return {"model": m, "val_nll": en_iyi, "en_iyi_tur": en_iyi_tur + 1,
            "gecmis": gecmis,
            "n_par": sum(p.numel() for p in m.parameters())}
