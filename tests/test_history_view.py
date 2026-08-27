"""HistoryView — yapısal sızıntı engelinin testleri.

KURAL 9: bir engelin çalıştığının kanıtı, REDDETTİĞİ bir deneydir. Bu dosyanın
ilk testleri kasten sızıntı denemesi yapar ve engelin durdurduğunu gösterir.

Performans tabanlı kanaryanın (docs/KANARYA_BULGUSU.md) bu rejimde kör olduğu
ölçüldü: hedefin YARISINI veren bir öznitelik AUC'yi +0,0000 değiştirdi. Bu
yüzden tespit yapıya taşındı: gelecek veri nesnenin İÇİNDE YOK.
"""
import numpy as np
import pandas as pd
import pytest

from src.features.history_view import HistoryView, LookaheadError

from tests.conftest import veri_gerekir

# Bu modülün tamamı türetilmiş kataloğa bağlıdır (bkz. conftest).
pytestmark = veri_gerekir


@pytest.fixture(scope="module")
def catalog():
    from src.ingest.catalog_io import read_catalog
    from src.config import PROC
    c = read_catalog(PROC / "catalog_declustered.csv")
    return c.dropna(subset=["lat", "lon", "mw"])


REF = pd.Timestamp("2023-02-06", tz="UTC")


# --- KURAL 9: reddettiğini göster ------------------------------------------

def test_forward_window_is_refused(catalog):
    """İleri pencere isteği HATA vermeli — sessiz boş sonuç DEĞİL.

    Sessiz boş sonuç, sızıntı denemesini gizler: yazan kişi "öznitelik hep 0"
    diye düşünüp devam eder.
    """
    hv = HistoryView(catalog, REF)
    with pytest.raises(LookaheadError):
        hv.count_within(days=-1)
    with pytest.raises(LookaheadError):
        hv.count_within(days=0)


def test_object_carries_no_future_data(catalog):
    """Nesnenin TAŞIDIĞI en geç olay, ref'ten önce olmalı.

    Bu, erişim denetimi değil veri yokluğu testidir: gelecek veri nesnede
    olmadığı için hiçbir metot onu döndüremez.
    """
    hv = HistoryView(catalog, REF)
    from src.ingest.catalog_io import epoch_seconds
    ref_s = float(epoch_seconds(pd.DatetimeIndex([REF]))[0])
    assert hv.max_time_seconds < ref_s
    assert hv.n_dropped > 0, "hiçbir olay kesilmediyse test anlamsız"


def test_no_raw_catalog_attribute(catalog):
    """Ham katalog nesnede BULUNMAMALI ve sonradan iliştirilememeli.

    __slots__ bunu zorunlu kılar; aksi hâlde bir öznitelik fonksiyonu
    hv._full = catalog yazıp engeli aşabilirdi.
    """
    hv = HistoryView(catalog, REF)
    for ad in ("catalog", "df", "raw", "_df", "_catalog"):
        assert not hasattr(hv, ad), f"ham veri sızdıran nitelik: {ad}"
    with pytest.raises(AttributeError):
        hv._full = catalog          # __slots__ engellemeli


def test_ref_cannot_be_moved(catalog):
    """ref sonradan değiştirilememeli — pencere kaydırılarak sızıntı olmasın."""
    hv = HistoryView(catalog, REF)
    with pytest.raises(AttributeError):
        hv.ref = pd.Timestamp("2024-01-01", tz="UTC")


# --- doğruluk: mevcut boru hattıyla AYNI sonucu vermeli ---------------------

def test_matches_existing_feature_computation(catalog):
    """HistoryView ile hesaplanan öznitelik, mevcut grid_features ile uyuşmalı.

    Engel kullanılabilir olmalı: doğru sonucu vermeyen bir engel, kullanılmaz
    ve kullanılmayan engel korumaz.
    """
    from src.config import cell_id
    from src.ingest.catalog_io import epoch_seconds

    c = catalog.copy()
    c["cell_id"] = cell_id(c.lat, c.lon)
    hedef = int(c.cell_id.value_counts().index[0])      # en yoğun hücre
    alt = c[c.cell_id == hedef]

    hv = HistoryView(alt, REF)
    for gun in (30, 90, 365):
        # bağımsız referans hesap (grid_features ile aynı kural: t < ref)
        t = epoch_seconds(alt["time"])
        ref_s = float(epoch_seconds(pd.DatetimeIndex([REF]))[0])
        beklenen = int(((t >= ref_s - gun * 86400.0) & (t < ref_s)).sum())
        assert hv.count_within(gun) == beklenen, f"{gun} gün"


def test_history_window_limits_visibility(catalog):
    """history_years verildiğinde görünürlük gerçekten daralmalı."""
    genis = HistoryView(catalog, REF, history_years=50.0)
    dar = HistoryView(catalog, REF, history_years=1.0)
    assert len(dar) < len(genis)
    assert dar.n_dropped > genis.n_dropped


# --- hızlı yol ile güçlü yolun bağlanması ----------------------------------

def test_cell_history_matches_history_view(catalog):
    """CellHistory (hızlı) ile HistoryView (güçlü) AYNI sonucu vermeli.

    İki garanti düzeyi var: HistoryView gelecek veriyi hiç taşımaz,
    CellHistory tavanı kuruluşta sabitler. İkincisi hız için vardır ve
    birincisiyle aynı sonucu vermek ZORUNDADIR -- yoksa hızlı yol, güçlü yolun
    garantisini taşımıyor demektir.
    """
    from src.config import cell_id
    from src.features.history_view import CellHistory
    from src.ingest.catalog_io import epoch_seconds

    c = catalog.copy()
    c["cell_id"] = cell_id(c.lat, c.lon)
    hedef = int(c.cell_id.value_counts().index[0])
    alt = c[c.cell_id == hedef].sort_values("time")

    refs = pd.date_range("2018-01-01", "2024-01-01", freq="6MS", tz="UTC")
    refs_s = epoch_seconds(refs)
    ch = CellHistory(epoch_seconds(alt["time"]), alt.mw.to_numpy(), refs_s)

    for gun in (30, 365, 3650):
        hizli = ch.count_within(gun)
        guclu = np.array([HistoryView(alt, r).count_within(gun) for r in refs])
        assert np.array_equal(hizli, guclu), f"{gun} gün: yollar ayrışıyor"


def test_cell_history_refuses_forward_window(catalog):
    """Hızlı yol da ileri pencereyi REDDETMELİ (kural 9)."""
    from src.features.history_view import CellHistory
    from src.ingest.catalog_io import epoch_seconds

    ch = CellHistory(epoch_seconds(catalog["time"].head(100)),
                     catalog.mw.head(100).to_numpy(),
                     epoch_seconds(pd.DatetimeIndex([REF])))
    with pytest.raises(LookaheadError):
        ch.count_within(-5)


def test_grid_features_uses_the_barrier():
    """Öznitelik üretimi engelden GEÇMELİ.

    Engelin kurulu olması yetmez; üretim yolu ondan geçmiyorsa engel
    "kurulu ama devrede değil"dir -- V15'in tam olarak uyardığı durum.
    """
    import inspect

    from src.features import grid_features

    src = inspect.getsource(grid_features)
    assert "CellHistory" in src, "grid_features engeli kullanmıyor"
    assert "hist.count_within" in src, "pencere sorguları engelden geçmiyor"
