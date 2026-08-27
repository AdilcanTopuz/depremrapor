"""Geçmiş görünümü — sızıntıyı YAPI GEREĞİ imkânsız kılar.

NEDEN. Sızıntı tespiti iki yolla yapılabilir:

* **performans üzerinden** — model şüpheli derecede iyi mi? Ölçüldü ve BU
  REJİMDE ÇALIŞMIYOR: `min_child_samples=200` ve 212 pozitifle, 200 satırdan az
  etkileyen hiçbir sızıntı skoru değiştirmiyor. Hedefin YARISINI doğrudan veren
  bir öznitelik AUC'yi +0,0000 değiştirdi (bkz. `docs/KANARYA_BULGUSU.md`).
* **yapı üzerinden** — öznitelik, referans tarihinden sonraki veriyi GÖREMEZ.

Bu modül ikincisidir.

TASARIM İLKESİ: erişim denetimi değil, VERİNİN YOKLUĞU. `HistoryView` kurulurken
katalogu `t < ref` ile keser ve yalnızca kesilmiş kısmı saklar. Gelecek veriye
"erişim izni yok" değil, **gelecek veri nesnenin içinde yok.** Bir öznitelik
fonksiyonu ne kadar yanlış yazılırsa yazılsın, olmayan bir şeyi okuyamaz.

Böylece sızıntı "yakalanacak bir hata" olmaktan çıkıp "yazılamayacak bir kod"
hâline gelir -- disiplin değil, yapı.

KURAL 9. Bu engelin çalıştığının kanıtı, REDDETTİĞİ bir deneydir:
`tests/test_history_view.py` ref sonrasına erişmeye çalışan bir öznitelik yazar
ve başarısız olduğunu gösterir.
"""
import numpy as np
import pandas as pd

from src.ingest.catalog_io import epoch_seconds


class LookaheadError(Exception):
    """Referans tarihinden sonrasına erişim denendi."""


class HistoryView:
    """Bir referans anında GÖRÜLEBİLİR olan katalog.

    Kurulduğu anda `t < ref` ile kesilir. Nesne, ref sonrasındaki hiçbir veriyi
    TAŞIMAZ; dolayısıyla hiçbir metot onu döndüremez.

    Kullanım:
        hv = HistoryView(catalog, ref, history_years=5.0)
        n30 = hv.count_within(days=30)          # son 30 gün (ref'e kadar)
        hv.count_within(days=-1)                # LookaheadError
    """

    __slots__ = ("_t", "_lat", "_lon", "_mw", "_ref_s", "_ref", "_n_dropped")

    def __init__(self, catalog: pd.DataFrame, ref: pd.Timestamp,
                 history_years: float | None = None, mc: float | None = None):
        if not isinstance(ref, pd.Timestamp):
            ref = pd.Timestamp(ref)
        df = catalog
        if mc is not None:
            df = df[df.mw >= mc]

        t_all = epoch_seconds(df["time"])
        ref_s = float(epoch_seconds(pd.DatetimeIndex([ref]))[0])

        keep = t_all < ref_s          # KESİN: ref DAHİL DEĞİL
        if history_years is not None:
            keep &= t_all >= ref_s - history_years * 365.25 * 86400.0

        self._n_dropped = int((~keep).sum())
        order = np.argsort(t_all[keep], kind="stable")
        self._t = t_all[keep][order]
        self._lat = df.lat.to_numpy()[keep][order]
        self._lon = df.lon.to_numpy()[keep][order]
        self._mw = df.mw.to_numpy()[keep][order]
        self._ref_s = ref_s
        self._ref = ref

    # --- temel bilgiler -----------------------------------------------------

    @property
    def ref(self) -> pd.Timestamp:
        return self._ref

    def __len__(self) -> int:
        return len(self._t)

    @property
    def n_dropped(self) -> int:
        """Kesilen olay sayısı — görünürlüğün gerçekten daraldığının kanıtı."""
        return self._n_dropped

    @property
    def max_time_seconds(self) -> float:
        """Görünen en geç olayın zamanı. TANIM GEREĞİ ref'ten küçüktür."""
        return float(self._t[-1]) if len(self._t) else float("-inf")

    # --- öznitelik yapı taşları --------------------------------------------

    def _window(self, days: float) -> tuple[int, int]:
        """[ref - days, ref) aralığının indeks sınırları.

        `days` pozitif olmak zorundadır: negatif bir değer "ref'ten sonrası"
        demektir ve bu nesnede öyle bir veri YOKTUR. İstek, sessizce boş sonuç
        döndürmek yerine HATA verir -- sessiz boş sonuç, sızıntı denemesini
        gizler.
        """
        if days <= 0:
            raise LookaheadError(
                f"days={days}: referans tarihinden sonrasına ya da tam üstüne "
                "bakılamaz. HistoryView yalnızca t < ref verisini taşır.")
        lo = int(np.searchsorted(self._t, self._ref_s - days * 86400.0, "left"))
        hi = len(self._t)
        return lo, hi

    def count_within(self, days: float, min_mw: float | None = None) -> int:
        """Son `days` günde (ref hariç) olay sayısı."""
        lo, hi = self._window(days)
        if min_mw is None:
            return hi - lo
        return int((self._mw[lo:hi] >= min_mw).sum())

    def magnitudes_within(self, days: float) -> np.ndarray:
        lo, hi = self._window(days)
        return self._mw[lo:hi]

    def years_since_last(self, min_mw: float) -> float:
        """Son `min_mw` üstü olaydan bu yana geçen yıl; yoksa NaN."""
        idx = np.flatnonzero(self._mw >= min_mw)
        if not len(idx):
            return float("nan")
        return (self._ref_s - self._t[idx[-1]]) / (365.25 * 86400.0)

    def moment_rate(self, days: float) -> float:
        """log10(kümülatif moment / yıl), son `days` günde."""
        lo, hi = self._window(days)
        if hi <= lo:
            return float("nan")
        m = 10 ** (1.5 * self._mw[lo:hi] + 9.1)
        return float(np.log10(m.sum() / (days / 365.25)))

    # --- kasıtlı olarak YOK -------------------------------------------------
    #
    # Bu sınıfta şunlar BULUNMAZ ve bulunmamalıdır:
    #   * ham katalog erişimi (`.catalog`, `.df`, `.raw` ...)
    #   * ileri pencere sorgusu
    #   * ref'i değiştiren bir metot
    #
    # `__slots__` kullanılmasının sebebi budur: sonradan nesneye ham veri
    # iliştirmek (hv._full = catalog gibi) mümkün olmasın.


class CellHistory:
    """Bir hücrenin olay dizisi üzerinde ÇOK REFERANSLI geçmiş sorguları.

    NEDEN AYRI BİR SINIF. `HistoryView` her (katalog, ref) çifti için kurulur ve
    gelecek veriyi hiç taşımaz -- en güçlü garanti. Ama öznitelik üretimi
    ~2100 hücre x ~250 referans ölçeğindedir; her çift için ayrı nesne kurmak
    Python düzeyinde yüz binlerce yineleme demektir.

    `CellHistory` hızlı yoldur: kuruluşta HER referans için görünürlük tavanı
    (`hi = searchsorted(t, ref, "left")`) hesaplanır ve TÜM sorgular bu tavanla
    sınırlıdır.

    GARANTİ FARKI -- açıkça yazılır:

        HistoryView  : gelecek veri nesnede YOKTUR (veri yokluğu)
        CellHistory  : gelecek veri dizide durur, ama AÇIK API'de ona ulaşacak
                       hiçbir parametre yoktur (sabitlenmiş tavan)

    İkincisi biraz daha zayıftır: `_t`'ye doğrudan erişen biri tavanı aşabilir.
    Buna karşılık öznitelik YAZARI, ileri bakışı İFADE EDEMEZ -- `days` pozitif
    olmak zorundadır ve tavan kuruluşta sabitlenmiştir.

    İki yolun aynı sonucu verdiği testle bağlanır
    (`test_cell_history_matches_history_view`).
    """

    __slots__ = ("_t", "_mw", "_refs", "_hi")

    def __init__(self, times_s: np.ndarray, mags: np.ndarray,
                 refs_s: np.ndarray):
        order = np.argsort(times_s, kind="stable")
        self._t = np.asarray(times_s)[order]
        self._mw = np.asarray(mags)[order]
        self._refs = np.asarray(refs_s, dtype=float)
        # GÖRÜNÜRLÜK TAVANI: side="left" -> ref anındaki olay DAHİL DEĞİL
        self._hi = np.searchsorted(self._t, self._refs, side="left")

    def _lo(self, days: float) -> np.ndarray:
        if days <= 0:
            raise LookaheadError(
                f"days={days}: ileri ya da sıfır pencere istenemez.")
        return np.searchsorted(self._t, self._refs - days * 86400.0, "left")

    def count_within(self, days: float) -> np.ndarray:
        """Her referans için son `days` gündeki olay sayısı."""
        return self._hi - self._lo(days)

    def sum_magnitude_within(self, days: float) -> np.ndarray:
        c = np.concatenate([[0.0], np.cumsum(self._mw)])
        return c[self._hi] - c[self._lo(days)]

    def moment_sum_within(self, days: float) -> np.ndarray:
        mom = 10 ** (1.5 * self._mw + 9.1)
        c = np.concatenate([[0.0], np.cumsum(mom)])
        return c[self._hi] - c[self._lo(days)]

    def seconds_since_last(self, min_mw: float) -> np.ndarray:
        """Her referans için son `min_mw` üstü olaydan geçen saniye; yoksa inf."""
        t_sel = np.where(self._mw >= min_mw, self._t, -np.inf)
        last = np.concatenate([[-np.inf], np.maximum.accumulate(t_sel)])
        return self._refs - last[self._hi]
