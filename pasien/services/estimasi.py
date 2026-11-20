"""Mesin estimasi waktu pemeriksaan dokter (BL-05).

Satu-satunya implementasi rumus PRD:

    T_periksa = T_mulai + ((N - 1) x D_rata) + Delta_geser
    T_tiba    = T_periksa - buffer_tiba, dengan batas bawah T_buka_rs

Dipakai oleh kiosk, portal mobile, struk thermal, dan WhatsApp. Jangan menyalin
rumus ini di tempat lain — ubah di sini.
"""
import datetime
from dataclasses import dataclass

BATAS_HARI = 1


class EstimasiError(ValueError):
    """Parameter estimasi tidak masuk akal."""


class EstimasiOverflow(EstimasiError):
    """Hasil estimasi melewati batas hari (mis. praktik lewat tengah malam)."""


@dataclass(frozen=True)
class Estimasi:
    mulai_praktik: datetime.time
    nomor_antrean: int
    durasi_menit: int
    delta_geser_menit: int
    t_periksa: datetime.time
    t_tiba: datetime.time
    tiba_di_clamp: bool
    versi: int = 0

    def as_dict(self):
        return {
            't_periksa': self.t_periksa.strftime('%H:%M'),
            't_tiba': self.t_tiba.strftime('%H:%M'),
            'tiba_di_clamp': self.tiba_di_clamp,
            'nomor_antrean': self.nomor_antrean,
            'durasi_menit': self.durasi_menit,
            'delta_geser_menit': self.delta_geser_menit,
            'versi': self.versi,
        }


def _tanggal_acuan():
    return datetime.date(2026, 1, 1)


def hitung_estimasi(*, t_mulai, n, d_rata, delta_geser=0, t_buka_rs=None, buffer_tiba=30, versi=0):
    """Hitung estimasi jam pemeriksaan dan anjuran tiba.

    Args:
        t_mulai: jam mulai praktik (``datetime.time``).
        n: nomor urut antrean pasien pada jadwal dokter tersebut (>= 1).
        d_rata: rata-rata durasi konsultasi per pasien dalam menit (>= 1).
        delta_geser: penyesuaian dinamis jadwal dalam menit (boleh negatif).
        t_buka_rs: jam buka pendaftaran RS; dipakai sebagai batas bawah ``t_tiba``.
        buffer_tiba: menit penyangga sebelum pemeriksaan (baku 30).
        versi: versi estimasi (naik setiap kali dihitung ulang).

    Raises:
        EstimasiError: parameter tidak valid.
        EstimasiOverflow: hasil melewati batas hari.
    """
    if not isinstance(t_mulai, datetime.time):
        raise EstimasiError('t_mulai harus datetime.time.')
    if not isinstance(n, int) or isinstance(n, bool) or n < 1:
        raise EstimasiError('n (nomor antrean) minimal 1.')
    if not isinstance(d_rata, int) or isinstance(d_rata, bool) or d_rata < 1:
        raise EstimasiError('d_rata minimal 1 menit.')
    if not isinstance(delta_geser, int) or isinstance(delta_geser, bool):
        raise EstimasiError('delta_geser harus bilangan bulat menit.')
    if not isinstance(buffer_tiba, int) or buffer_tiba < 0:
        raise EstimasiError('buffer_tiba tidak boleh negatif.')

    acuan = _tanggal_acuan()
    mulai_dt = datetime.datetime.combine(acuan, t_mulai)
    periksa_dt = mulai_dt + datetime.timedelta(minutes=(n - 1) * d_rata + delta_geser)
    if periksa_dt.date() != acuan:
        raise EstimasiOverflow('Estimasi pemeriksaan melewati batas hari praktik.')
    if periksa_dt < mulai_dt and delta_geser >= 0:
        raise EstimasiError('Estimasi tidak boleh mendahului jam mulai praktik.')

    tiba_dt = periksa_dt - datetime.timedelta(minutes=buffer_tiba)
    tiba_di_clamp = False
    if t_buka_rs is not None:
        buka_dt = datetime.datetime.combine(acuan, t_buka_rs)
        if tiba_dt < buka_dt:
            tiba_dt = buka_dt
            tiba_di_clamp = True
    elif tiba_dt.date() != acuan:
        raise EstimasiOverflow('Waktu anjuran tiba jatuh sebelum hari praktik.')

    return Estimasi(
        mulai_praktik=t_mulai,
        nomor_antrean=n,
        durasi_menit=d_rata,
        delta_geser_menit=delta_geser,
        t_periksa=periksa_dt.time(),
        t_tiba=tiba_dt.time(),
        tiba_di_clamp=tiba_di_clamp,
        versi=versi,
    )


def estimasi_kunjungan(kunjungan, *, konfigurasi=None, urutan=None):
    """Estimasi untuk satu kunjungan berdasarkan jadwal dokternya."""
    from pasien.models import JadwalDokterPoli, KonfigurasiApm

    konf = konfigurasi or KonfigurasiApm.get_solo()
    jadwal = JadwalDokterPoli.objects.filter(
        nama_dokter=kunjungan.dpjp, poliklinik=kunjungan.poliklinik,
    ).first()
    if jadwal is None:
        if not kunjungan.estimasi_pelayanan:
            raise EstimasiError(
                f'Jadwal dokter "{kunjungan.dpjp}" untuk poli {kunjungan.poliklinik} tidak ditemukan.'
            )
        return hitung_estimasi(
            t_mulai=kunjungan.estimasi_pelayanan,
            n=1,
            d_rata=1,
            delta_geser=0,
            t_buka_rs=konf.t_buka_rs,
            buffer_tiba=konf.buffer_tiba_menit,
            versi=kunjungan.estimasi_versi,
        )

    if urutan is None:
        urutan = _posisi_antrean(kunjungan, jadwal)
    return hitung_estimasi(
        t_mulai=jadwal.jam_mulai,
        n=urutan,
        d_rata=jadwal.durasi_per_pasien_menit,
        delta_geser=kunjungan.delta_geser_menit,
        t_buka_rs=konf.t_buka_rs,
        buffer_tiba=konf.buffer_tiba_menit,
        versi=kunjungan.estimasi_versi,
    )


def _posisi_antrean(kunjungan, jadwal):
    tanggal = kunjungan.tanggal_kunjungan or kunjungan.tanggal_masuk.date()
    sejenis = list(
        type(kunjungan).objects.filter(
            tanggal_kunjungan=tanggal, jenis_kunjungan='RAJAL',
            dpjp=jadwal.nama_dokter, poliklinik=jadwal.poliklinik,
        ).exclude(status='BATAL').order_by('id').values_list('pk', flat=True)
    )
    if kunjungan.pk in sejenis:
        return sejenis.index(kunjungan.pk) + 1
    return len(sejenis) + 1


def recompute_for_schedule(jadwal, tanggal, delta_geser, *, alasan='', notifier=None):
    """Hitung ulang estimasi seluruh pasien yang belum dipanggil pada satu jadwal.

    Returns:
        list[dict]: ringkasan perubahan ``{kunjungan, lama, baru, notifikasi}``.
    """
    from pasien.models import KunjunganPasien, KonfigurasiApm

    konf = KonfigurasiApm.get_solo()
    kunjungan_qs = (
        KunjunganPasien.objects.filter(
            tanggal_kunjungan=tanggal, jenis_kunjungan='RAJAL',
            dpjp=jadwal.nama_dokter, poliklinik=jadwal.poliklinik,
            status_antrean='MENUNGGU',
        ).exclude(status='BATAL').order_by('id')
    )
    kirim_notifikasi = abs(delta_geser) >= konf.ambang_geser_notif_menit
    perubahan = []

    for posisi, kunjungan in enumerate(kunjungan_qs, start=1):
        lama = kunjungan.estimasi_pelayanan
        estimasi = hitung_estimasi(
            t_mulai=jadwal.jam_mulai,
            n=posisi,
            d_rata=jadwal.durasi_per_pasien_menit,
            delta_geser=delta_geser,
            t_buka_rs=konf.t_buka_rs,
            buffer_tiba=konf.buffer_tiba_menit,
            versi=kunjungan.estimasi_versi + 1,
        )
        berubah = (
            kunjungan.estimasi_pelayanan != estimasi.t_periksa
            or kunjungan.delta_geser_menit != delta_geser
        )
        if not berubah:
            perubahan.append({
                'kunjungan': kunjungan, 'lama': lama, 'baru': lama,
                'notifikasi': False, 'versi': kunjungan.estimasi_versi,
            })
            continue

        kunjungan.estimasi_pelayanan = estimasi.t_periksa
        kunjungan.delta_geser_menit = delta_geser
        kunjungan.estimasi_versi = estimasi.versi
        kunjungan.save(update_fields=['estimasi_pelayanan', 'delta_geser_menit', 'estimasi_versi'])

        terkirim = False
        if kirim_notifikasi and notifier is not None:
            terkirim = bool(notifier(kunjungan, lama, estimasi, alasan))
        perubahan.append({
            'kunjungan': kunjungan, 'lama': lama, 'baru': estimasi.t_periksa,
            'notifikasi': terkirim, 'versi': estimasi.versi,
        })
    return perubahan


__all__ = [
    'Estimasi', 'EstimasiError', 'EstimasiOverflow', 'estimasi_kunjungan',
    'hitung_estimasi', 'recompute_for_schedule',
]