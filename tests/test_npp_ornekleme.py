"""Negatif alt örnekleme YANSIZ mı — kural 9, koşudan önce.

İLAN (`docs/NPP_ILAN.md` §3): her turda tüm pozitifler + negatiflerden p
oranında örneklem; negatif satırların maruziyet terimi 1/p ile ağırlıklanır.

"Kâğıt üstünde yansız" yetmez: 1/p ağırlıklandırma tek satırlık bir hatayla
yanlı olur ve hata SESSİZDİR — model yakınsar, kalibrasyon kayar. Bu dosya,
ağırlıklı kaybın tam veriyle AYNI eniyileyiciye götürdüğünü sabitler.

Kayıp (Poisson NLL, sayım biçimi):   lambda - y * log(lambda)
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")


def poisson_nll(log_lam, y, w=None):
    """Ağırlıklı Poisson NLL. w=None -> hepsi 1."""
    kayip = log_lam.exp() - y * log_lam
    if w is not None:
        kayip = kayip * w
    return kayip.sum()


def _veri(n=200_000, oran=0.004, seed=0):
    """Sabit oranlı sentetik Poisson veri — analitik optimum bilinir."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < oran).astype(np.float64)
    return torch.tensor(y)


def _en_iyi_log_lam(y, w=None):
    """Sabit log(lambda) için kapalı çözüm: lambda* = sum(w*y) / sum(w)."""
    if w is None:
        return float(np.log(y.sum() / len(y)))
    return float(np.log((w * y).sum() / w.sum()))


def test_agirlikli_kayip_ayni_optimuma_goturur():
    """Alt örneklenmiş + ağırlıklı çözüm, tam veri çözümüyle uyuşmalı."""
    y = _veri()
    tam = _en_iyi_log_lam(y)

    p = 0.05
    rng = np.random.default_rng(1)
    poz = torch.nonzero(y > 0).squeeze(-1).numpy()
    neg = torch.nonzero(y == 0).squeeze(-1).numpy()
    sec_neg = neg[rng.random(len(neg)) < p]
    idx = np.concatenate([poz, sec_neg])
    w = torch.tensor(np.concatenate(
        [np.ones(len(poz)), np.full(len(sec_neg), 1.0 / p)]))
    alt = _en_iyi_log_lam(y[idx], w)

    # Bağıl fark, örnekleme gürültüsü mertebesinde olmalı
    bagil = abs(np.exp(alt) - np.exp(tam)) / np.exp(tam)
    assert bagil < 0.02, (
        f"ağırlıklı çözüm {np.exp(alt):.6g}, tam çözüm {np.exp(tam):.6g}, "
        f"bağıl fark {bagil:.4f}")


def test_agirliksiz_alt_orneklem_YANLIDIR():
    """Ağırlık UNUTULURSA sonuç yanlı olmalı — testin kendisi de sınanır.

    Bu, kural 9'un kanarya tarafı: koruma (ağırlık) kaldırıldığında hata
    GÖRÜNMELİ. Görünmüyorsa test bir şey ölçmüyordur.
    """
    y = _veri()
    tam = np.exp(_en_iyi_log_lam(y))

    p = 0.05
    rng = np.random.default_rng(1)
    poz = torch.nonzero(y > 0).squeeze(-1).numpy()
    neg = torch.nonzero(y == 0).squeeze(-1).numpy()
    sec_neg = neg[rng.random(len(neg)) < p]
    idx = np.concatenate([poz, sec_neg])
    agirliksiz = np.exp(_en_iyi_log_lam(y[idx]))     # ağırlık YOK

    assert agirliksiz > 5 * tam, (
        f"ağırlıksız {agirliksiz:.6g} ile tam {tam:.6g} arasında beklenen "
        "büyük sapma görülmedi — test yanlılığı yakalayamıyor")


def test_gradyan_yonu_de_ayni():
    """Yalnızca optimum değil, oradaki GRADYAN da uyuşmalı.

    Optimumda ikisi de sıfırlanıyorsa bu, kayıp yüzeylerinin aynı yerde
    düzleştiğini gösterir; eniyileyici aynı noktaya iner.
    """
    y = _veri()
    tam_log = _en_iyi_log_lam(y)

    p = 0.05
    rng = np.random.default_rng(2)
    poz = torch.nonzero(y > 0).squeeze(-1).numpy()
    neg = torch.nonzero(y == 0).squeeze(-1).numpy()
    sec_neg = neg[rng.random(len(neg)) < p]
    idx = np.concatenate([poz, sec_neg])
    w = torch.tensor(np.concatenate(
        [np.ones(len(poz)), np.full(len(sec_neg), 1.0 / p)]))

    z = torch.tensor(tam_log, requires_grad=True)
    poisson_nll(z.expand(len(idx)), y[idx], w).backward()
    grad_alt = float(z.grad) / w.sum()

    z2 = torch.tensor(tam_log, requires_grad=True)
    poisson_nll(z2.expand(len(y)), y).backward()
    grad_tam = float(z2.grad) / len(y)

    assert abs(grad_alt - grad_tam) < 2e-4, (
        f"gradyanlar ayrışıyor: alt {grad_alt:.3e}, tam {grad_tam:.3e}")
