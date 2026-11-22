"""Kalkulator kebutuhan tenaga keperawatan: Gillies dan Douglas.

Kedua rumus dipakai untuk rumpun Keperawatan & Kebidanan sesuai dokumen
Pola Ketenagaan Komprehensif. Keduanya menerima input yang sama sehingga hasil
keduanya bisa dibandingkan, dan keduanya menolak input yang tidak masuk akal
alih-alih mengembalikan angka nol yang terlihat wajar.

Rumus (Gillies, 1994):

    jam_perawatan_harian = BOR x TT x rata_rata_jam_per_pasien
    kebutuhan_harian    = jam_perawatan_harian / jam_kerja_efektif_per_hari
    faktor_koreksi      = (hari_kerja + hari_libur_cuti) / hari_kerja
    kebutuhan_fte       = kebutuhan_harian x faktor_koreksi

Douglas menambahkan tiga komponen kegiatan non-asuhan (administrasi,
pendidikan, istirahat) sebagai persentase dari jam asuhan langsung.
"""
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

FTE_QUANTUM = Decimal('0.01')
HARI_PER_TAHUN = Decimal('365')


def _desimal(nilai, nama):
    if nilai is None:
        raise ValidationError({nama: 'Wajib diisi; nilai kosong bukan nol.'})
    hasil = Decimal(str(nilai))
    if hasil < 0:
        raise ValidationError({nama: 'Tidak boleh negatif.'})
    return hasil


def _kuantisasi(nilai):
    return nilai.quantize(FTE_QUANTUM, rounding=ROUND_HALF_UP)


def hitung_gillies(
    *, bor, tempat_tidur, jam_perawatan_per_pasien, jam_kerja_efektif_per_hari,
    hari_kerja_per_tahun, hari_libur_cuti_per_tahun,
):
    """Kembalikan dict kebutuhan FTE perawat memakai rumus Gillies.

    ``bor`` adalah rasio 0–1 (bukan persen). ``jam_kerja_efektif_per_hari``
    adalah jam produktif satu perawat dalam satu shift, bukan jam dinas.
    """
    bor = _desimal(bor, 'bor')
    tt = _desimal(tempat_tidur, 'tempat_tidur')
    jam_asuhan = _desimal(jam_perawatan_per_pasien, 'jam_perawatan_per_pasien')
    jam_kerja = _desimal(jam_kerja_efektif_per_hari, 'jam_kerja_efektif_per_hari')
    hari_kerja = _desimal(hari_kerja_per_tahun, 'hari_kerja_per_tahun')
    hari_libur = _desimal(hari_libur_cuti_per_tahun, 'hari_libur_cuti_per_tahun')

    if bor > 1:
        raise ValidationError({'bor': 'BOR harus berupa rasio 0–1, bukan persen.'})
    if jam_kerja <= 0:
        raise ValidationError({'jam_kerja_efektif_per_hari': 'Harus lebih dari nol.'})
    if hari_kerja <= 0:
        raise ValidationError({'hari_kerja_per_tahun': 'Harus lebih dari nol.'})
    if hari_kerja + hari_libur > HARI_PER_TAHUN:
        raise ValidationError({
            'hari_libur_cuti_per_tahun': 'Hari kerja + libur/cuti melebihi 365 hari.'
        })

    jam_perawatan_harian = bor * tt * jam_asuhan
    kebutuhan_harian = jam_perawatan_harian / jam_kerja
    faktor_koreksi = (hari_kerja + hari_libur) / hari_kerja
    kebutuhan_fte = kebutuhan_harian * faktor_koreksi

    return {
        'metode': 'GILLIES',
        'jam_perawatan_harian': _kuantisasi(jam_perawatan_harian),
        'kebutuhan_harian': _kuantisasi(kebutuhan_harian),
        'faktor_koreksi': faktor_koreksi.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP),
        'kebutuhan_fte': _kuantisasi(kebutuhan_fte),
        'kebutuhan_dibulatkan': int(kebutuhan_fte.to_integral_value(rounding=ROUND_HALF_UP)),
    }


def hitung_douglas(
    *, bor, tempat_tidur, jam_perawatan_per_pasien, jam_kerja_efektif_per_hari,
    hari_kerja_per_tahun, hari_libur_cuti_per_tahun,
    persen_administrasi=Decimal('15'), persen_pendidikan=Decimal('5'),
    persen_istirahat=Decimal('10'),
):
    """Rumus Douglas: Gillies + kegiatan non-asuhan sebagai persentase.

    Total persentase kegiatan tidak boleh mencapai 100% — kalau mencapai,
    perawat tidak lagi punya waktu untuk asuhan langsung dan hasilnya bukan
    angka yang bisa dipertahankan saat survei.
    """
    dasar = hitung_gillies(
        bor=bor, tempat_tidur=tempat_tidur,
        jam_perawatan_per_pasien=jam_perawatan_per_pasien,
        jam_kerja_efektif_per_hari=jam_kerja_efektif_per_hari,
        hari_kerja_per_tahun=hari_kerja_per_tahun,
        hari_libur_cuti_per_tahun=hari_libur_cuti_per_tahun,
    )

    komponen = {
        'administrasi': _desimal(persen_administrasi, 'persen_administrasi'),
        'pendidikan': _desimal(persen_pendidikan, 'persen_pendidikan'),
        'istirahat': _desimal(persen_istirahat, 'persen_istirahat'),
    }
    total_persen = sum(komponen.values(), Decimal('0'))
    if total_persen >= Decimal('100'):
        raise ValidationError({
            'persen_administrasi': (
                'Total kegiatan non-asuhan mencapai '
                f'{total_persen}%; harus di bawah 100%.'
            )
        })

    faktor_non_asuhan = Decimal('1') + total_persen / Decimal('100')
    kebutuhan_fte = dasar['kebutuhan_fte'] * faktor_non_asuhan

    return {
        'metode': 'DOUGLAS',
        'dasar_gillies_fte': dasar['kebutuhan_fte'],
        'persen_non_asuhan': total_persen,
        'faktor_non_asuhan': faktor_non_asuhan.quantize(
            Decimal('0.0001'), rounding=ROUND_HALF_UP
        ),
        'rincian_persen': komponen,
        'kebutuhan_fte': _kuantisasi(kebutuhan_fte),
        'kebutuhan_dibulatkan': int(kebutuhan_fte.to_integral_value(rounding=ROUND_HALF_UP)),
    }
