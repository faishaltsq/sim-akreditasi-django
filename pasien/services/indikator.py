"""Indikator mutu modul APM (BL-12).

Dipakai oleh management command ``apm_indikator`` dan dasbor staf agar angka
yang dilaporkan ke unit mutu berasal dari satu perhitungan.
"""
import datetime
import statistics

from django.utils import timezone

from pasien.models import KunjunganPasien, LogBiometrik, LogRisikoApm, WhatsAppLog


def _persentil(nilai, q):
    if not nilai:
        return None
    if len(nilai) == 1:
        return round(nilai[0], 2)
    return round(statistics.quantiles(nilai, n=100)[q - 1], 2)


def _ringkas_durasi(kunjungan_qs):
    durasi = [
        (item.registrasi_selesai_at - item.registrasi_mulai_at).total_seconds()
        for item in kunjungan_qs
        if item.registrasi_mulai_at and item.registrasi_selesai_at
    ]
    return {
        'jumlah_terukur': len(durasi),
        'median_detik': round(statistics.median(durasi), 2) if durasi else None,
        'p90_detik': _persentil(durasi, 90),
        'maks_detik': round(max(durasi), 2) if durasi else None,
    }


def hitung_indikator(tahun=None, bulan=None):
    hari_ini = timezone.localdate()
    tahun = tahun or hari_ini.year
    bulan = bulan or hari_ini.month
    mulai = datetime.date(tahun, bulan, 1)
    akhir = datetime.date(tahun + (bulan == 12), (bulan % 12) + 1, 1)

    kunjungan = KunjunganPasien.objects.filter(tanggal_masuk__gte=mulai, tanggal_masuk__lt=akhir)

    sep_live = kunjungan.filter(sep_mode='LIVE').count()
    sep_simulasi = kunjungan.filter(sep_mode='SIMULASI').count()
    sep_gagal = kunjungan.filter(sep_mode='GAGAL').count()

    biometrik = {
        hasil: LogBiometrik.objects.filter(created_at__gte=mulai, created_at__lt=akhir, hasil=hasil).count()
        for hasil in ('VALID', 'GAGAL', 'ESKALASI', 'ERROR')
    }
    total_biometrik = biometrik['VALID'] + biometrik['GAGAL'] + biometrik['ESKALASI']
    kepatuhan = round(biometrik['VALID'] / total_biometrik * 100, 2) if total_biometrik else None

    rujukan_blokir = {}
    for log in LogRisikoApm.objects.filter(
        created_at__gte=mulai, created_at__lt=akhir, kode_risiko='RSK-APM-02',
    ):
        rujukan_blokir[log.pemicu] = rujukan_blokir.get(log.pemicu, 0) + 1

    risiko = {}
    for log in LogRisikoApm.objects.filter(created_at__gte=mulai, created_at__lt=akhir):
        risiko[log.kode_risiko] = risiko.get(log.kode_risiko, 0) + 1

    wa = {}
    for log in WhatsAppLog.objects.filter(created_at__gte=mulai, created_at__lt=akhir):
        kunci = f'{log.jenis_pesan}:{log.status}'
        wa[kunci] = wa.get(kunci, 0) + 1

    return {
        'periode': {'tahun': tahun, 'bulan': bulan},
        'kunjungan': {
            'total': kunjungan.count(),
            'igd': kunjungan.filter(jenis_kunjungan='IGD').count(),
            'rajal': kunjungan.filter(jenis_kunjungan='RAJAL').count(),
            'apm': kunjungan.filter(is_apm=True).count(),
        },
        'registrasi': {
            'semua': _ringkas_durasi(kunjungan),
            'igd': _ringkas_durasi(kunjungan.filter(jenis_kunjungan='IGD')),
            'rajal': _ringkas_durasi(kunjungan.filter(jenis_kunjungan='RAJAL')),
        },
        'sep': {
            'live': sep_live, 'simulasi': sep_simulasi, 'gagal': sep_gagal,
            'catatan': 'Simulasi tidak dihitung sebagai SEP BPJS sah.',
        },
        'biometrik': {**biometrik, 'kepatuhan_persen': kepatuhan},
        'rujukan_blokir': rujukan_blokir,
        'risiko': risiko,
        'whatsapp': wa,
    }