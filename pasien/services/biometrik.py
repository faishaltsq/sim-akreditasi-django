"""Gerbang validasi biometrik (BL-08 / BL-09, RSK-APM-03).

Protokol perangkat biometrik BPJS bersifat vendor/RS-spesifik dan belum
terdokumentasi di PRD. Karena itu modul ini adalah **adapter**:

- ``mode='SIMULASI'`` (default): keputusan diambil dari parameter ``simulasi_valid``
  dan hasilnya SELALU ditandai simulasi — tidak boleh dipakai sebagai bukti
  kepatuhan biometrik pada UAT.
- ``mode='DEVICE'``: memanggil driver perangkat; sampai dokumen vendor tersedia,
  memanggil mode ini melempar ``BiometricUnavailable`` (fail-closed), bukan
  mengarang hasil.
"""
import hashlib

from pasien.models import KonfigurasiApm, KonfigurasiBiometrikPoli, LogBiometrik


class BiometricUnavailable(RuntimeError):
    """Driver perangkat biometrik belum tersedia/dikonfigurasi."""


class BiometricGateway:
    """Adapter verifikasi biometrik; satu-satunya pintu penulisan LogBiometrik."""

    def __init__(self, mode='SIMULASI'):
        self.mode = mode

    def verify(self, *, kunjungan, percobaan, metode='FINGERPRINT', simulasi_valid=True, perangkat_id=''):
        if self.mode == 'DEVICE':
            raise BiometricUnavailable(
                'Driver perangkat biometrik belum tersedia. Lengkapi dokumen protokol '
                'vendor/BPJS sebelum mengaktifkan mode DEVICE.'
            )
        skor = self._skor_simulasi(kunjungan, percobaan)
        hasil = 'VALID' if simulasi_valid else 'GAGAL'
        log = LogBiometrik.objects.create(
            kunjungan=kunjungan,
            percobaan_ke=percobaan,
            metode=metode,
            hasil=hasil,
            skor=skor,
            perangkat_id=perangkat_id,
            mode='SIMULASI',
            detail={'catatan': 'Hasil simulasi — bukan verifikasi biometrik BPJS.'},
        )
        return {'valid': simulasi_valid, 'skor': float(skor), 'mode': 'SIMULASI', 'log_id': log.id}

    @staticmethod
    def _skor_simulasi(kunjungan, percobaan):
        dasar = hashlib.sha256(f'{kunjungan.pasien_id}:{percobaan}'.encode()).hexdigest()
        return round(60 + (int(dasar[:4], 16) % 40), 2)


def konfigurasi_biometrik(poliklinik):
    return KonfigurasiBiometrikPoli.objects.filter(poliklinik=poliklinik).first()


def wajib_biometrik(kunjungan):
    """True bila poli mewajibkan biometrik untuk pasien ini (usia/status dikecualikan)."""
    konf = konfigurasi_biometrik(kunjungan.poliklinik)
    if not konf:
        return False
    lahir = getattr(kunjungan.pasien, 'tanggal_lahir', None)
    usia = None
    if lahir:
        from django.utils import timezone

        hari_ini = timezone.localdate()
        usia = hari_ini.year - lahir.year - ((hari_ini.month, hari_ini.day) < (lahir.month, lahir.day))
    return konf.mewajibkan(usia=usia)


def batas_percobaan():
    return KonfigurasiApm.get_solo().biometrik_maks_percobaan


def nomor_tiket_helpdesk():
    from django.utils import timezone

    hari_ini = timezone.localdate()
    urutan = LogBiometrik.objects.filter(hasil='ESKALASI', created_at__date=hari_ini).count() + 1
    return f'HSD-{hari_ini:%Y%m%d}-{urutan:04d}'