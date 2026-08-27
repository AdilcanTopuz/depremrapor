"""NPP determinizmi — kural 9, koşudan ÖNCE.

İLAN (`docs/NPP_ILAN.md` §6): "TEKRARLANABİLİR" = aynı tohum + aynı veri ->
BİREBİR aynı doğrulama NLL.

Bu beyan test geçmeden künyeye yazılmaz. "Aynı tohum verdim" yetmez: iş
parçacığı sayısı toplama sırasını değiştirir ve kayan nokta toplaması
birleşmeli değildir — aynı tohumla farklı sonuç çıkabilir (V16'nın nöral
karşılığı).
"""
import numpy as np
import pytest

torch = pytest.importorskip("torch")


def _kucuk_yigin(n=4000, f=6, k=12, seed=0):
    """Gerçek dizin dosyasına bağımlı olmayan küçük bir sahte Yigin."""
    rng = np.random.default_rng(seed)

    class Sahte:
        statik = rng.normal(size=(n, f)).astype(np.float32)
        y = (rng.random(n) < 0.01).astype(np.float32)

        def __call__(self, satir):
            # SATIRA GÖRE deterministik: paylaşılan bir RNG kullanılsaydı iki
            # koşu farklı olay verisi görürdü ve test, modelin değil kendi
            # sahtesinin rastgeleliğini ölçerdi. (İlk sürümde tam bu oldu.)
            s = np.asarray(satir)
            r2 = np.random.default_rng(1000 + int(s[0]) * 7919 + len(s))
            olay = r2.normal(size=(len(s), k, 3)).astype(np.float32)
            mk = (r2.random((len(s), k)) < 0.7).astype(np.float32)
            return (torch.from_numpy(self.statik[s]), torch.from_numpy(olay),
                    torch.from_numpy(mk), torch.from_numpy(self.y[s]))

    return Sahte()


def test_ayni_tohum_birebir_ayni_nll():
    """İki bağımsız eğitim, aynı tohumla BİREBİR aynı NLL vermeli."""
    from src.models import npp

    yg = _kucuk_yigin()
    tr = np.arange(3000)
    va = np.arange(3000, 4000)
    kw = dict(tohum=7, gizli=16, katman=2, tur=3, sabir=3, yigin_boyu=1024)

    a = npp.egit(yg, tr, va, **kw)
    b = npp.egit(yg, tr, va, **kw)
    assert a["val_nll"] == b["val_nll"], (
        f"aynı tohum farklı NLL: {a['val_nll']!r} vs {b['val_nll']!r}")
    assert a["gecmis"] == b["gecmis"], "tur tur geçmiş ayrışıyor"


def test_farkli_tohum_farkli_sonuc():
    """Test bir şey ölçüyor mu: tohum değişince sonuç DEĞİŞMELİ.

    Değişmiyorsa eğitim tohuma bağlı değildir ve determinizm testi boştur.
    """
    from src.models import npp

    yg = _kucuk_yigin()
    tr, va = np.arange(3000), np.arange(3000, 4000)
    kw = dict(gizli=16, katman=2, tur=3, sabir=3, yigin_boyu=1024)
    a = npp.egit(yg, tr, va, tohum=7, **kw)
    b = npp.egit(yg, tr, va, tohum=8, **kw)
    assert a["val_nll"] != b["val_nll"], "tohum sonucu etkilemiyor"


def test_is_parcacigi_sabitlenmis():
    """Protokol iş parçacığı sayısını SABİTLER — beyanın maddi karşılığı."""
    from src.models import npp

    npp.hazirla(1)
    assert torch.get_num_threads() == npp.IS_PARCACIGI
    assert torch.are_deterministic_algorithms_enabled()
