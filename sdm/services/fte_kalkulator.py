"""Kalkulator FTE satu halaman: aritmetika murni di atas data yang belum
disimpan. Rumusnya identik dengan calculate_formasi — lihat
sdm/models/formasi.py:320 — dan tidak boleh menyimpang."""
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

FTE_QUANTUM = Decimal('0.01')
MINUTES_PER_HOUR = Decimal('60')

# Nilai awal ilustratif per preset; pengguna dapat mengeditnya bebas.
PRESET_UNIT = {
    'PERAWAT_IGD': {
        'label': 'Perawat IGD',
        'profesi': 'Perawat',
        'unit_hint': 'IGD',
        'activities': [
            ('Triase & asesmen awal', '12000.00', '12.00'),
            ('Tindakan emergensi', '6500.00', '35.00'),
            ('Pemberian obat & infus', '9000.00', '10.00'),
            ('Monitoring pasien kritis', '5400.00', '45.00'),
            ('Pendokumentasian & serah terima', '12000.00', '8.00'),
        ],
    },
    'PERAWAT_RANAP': {
        'label': 'Perawat Rawat Inap',
        'profesi': 'Perawat',
        'unit_hint': 'Rawat Inap',
        'activities': [
            ('Asuhan keperawatan harian', '26000.00', '30.00'),
            ('Pemberian obat & infus', '31000.00', '9.00'),
            ('Pemantauan tanda vital', '62000.00', '6.00'),
            ('Edukasi pasien & keluarga', '9000.00', '15.00'),
            ('Pendokumentasian asuhan', '26000.00', '12.00'),
        ],
    },
    'FARMASI': {
        'label': 'Farmasi',
        'profesi': 'Apoteker',
        'unit_hint': 'Instalasi Farmasi',
        'activities': [
            ('Review resep & screening', '48000.00', '5.00'),
            ('Penyalisan obat racikan', '15000.00', '20.00'),
            ('Pelayanan informasi obat', '8000.00', '12.00'),
            ('Pengelolaan stok & kadaluarsa', '9000.00', '25.00'),
            ('Farmasi klinik & TPN', '4000.00', '40.00'),
        ],
    },
    'DOKTER': {
        'label': 'Dokter',
        'profesi': 'Dokter',
        'unit_hint': 'Poliklinik',
        'activities': [
            ('Pemeriksaan & anamnesis', '22000.00', '18.00'),
            ('Tindakan poliklinik', '7000.00', '30.00'),
            ('Pendokumentasian rekam medis', '22000.00', '7.00'),
            ('Konsultasi & edukasi pasien', '11000.00', '10.00'),
            ('Koordinasi multidisiplin', '5000.00', '20.00'),
        ],
    },
    'ADMIN_HRD': {
        'label': 'Admin HRD',
        'profesi': 'Admin SDM',
        'unit_hint': 'Bagian SDM',
        'activities': [
            ('Pengolahan data kepegawaian', '6000.00', '22.00'),
            ('Verifikasi berkas & kredensial', '4500.00', '18.00'),
            ('Penggajian & benefit', '6000.00', '15.00'),
            ('Rekrutmen & onboarding', '900.00', '180.00'),
            ('Pelaporan regulasi SDM', '240.00', '300.00'),
        ],
    },
}


def _quantize(value):
    return value.quantize(FTE_QUANTUM, rounding=ROUND_HALF_UP)


def jke_minutes(hari_kerja, cuti_tahunan, hari_sakit_rata2, libur_nasional,
                pendidikan_pelatihan_hari, jam_kerja_per_hari):
    """Menit efektif per tahun dari enam input mentah.

    `pendidikan_pelatihan_hari` adalah hari (kosakata spec); model
    JamKerjaEfektif menyimpan jam, jadi dikonversi lebih dulu.
    """
    hari_produktif = (
        int(hari_kerja) - int(cuti_tahunan)
        - int(hari_sakit_rata2) - int(libur_nasional)
    )
    jam_pelatihan = Decimal(str(pendidikan_pelatihan_hari)) * Decimal(
        str(jam_kerja_per_hari)
    )
    jam_efektif = (
        Decimal(hari_produktif) * Decimal(str(jam_kerja_per_hari))
        - jam_pelatihan
    )
    return (jam_efektif * MINUTES_PER_HOUR).quantize(Decimal('0.01'))


def compute_fte(activities, effective_minutes, allowance_pct, *,
                existing_fte=Decimal('0.00')):
    """activities: iterable of (nama, volume, standard_minutes) tuples."""
    total_minutes = Decimal('0.00')
    for nama, volume, standard_minutes in activities:
        total_minutes += Decimal(volume) * Decimal(standard_minutes)
    allowance = Decimal('1.00') + (Decimal(allowance_pct) / Decimal('100.00'))
    quotient = total_minutes * allowance / Decimal(effective_minutes)
    required_fte = _quantize(quotient)
    required_headcount = int(quotient.to_integral_value(rounding=ROUND_CEILING))
    actual_fte = _quantize(Decimal(existing_fte))
    gap_fte = _quantize(required_fte - actual_fte)
    sufficiency_pct = None
    if required_fte > 0:
        sufficiency_pct = (actual_fte / required_fte * Decimal('100.00')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
    return {
        'total_minutes': total_minutes,
        'allowance_pct': Decimal(allowance_pct),
        'required_fte': required_fte,
        'required_headcount': required_headcount,
        'actual_fte': actual_fte,
        'gap_fte': gap_fte,
        'sufficiency_pct': sufficiency_pct,
    }


def band_gap(gap_fte):
    """UNDERSTAFFED / OPTIMAL / OVERSTAFFED — kosakata badge spec."""
    if gap_fte > 0:
        return 'UNDERSTAFFED'
    if gap_fte < 0:
        return 'OVERSTAFFED'
    return 'OPTIMAL'


def existing_fte_for(unit_id, profesi, as_of):
    """Satu-satunya definisi "eksisting staf": salinan persis queryset
    calculate_formasi (sdm/models/formasi.py:353-361) dengan as_of
    menggantikan plan.periode_selesai."""
    from decimal import Decimal as _Decimal

    from django.db.models import Q

    from sdm.models import PenempatanPegawai

    assignments = PenempatanPegawai.objects.filter(
        unit_kerja_id=unit_id,
        pegawai__profesi__iexact=profesi,
        tanggal_mulai__lte=as_of,
    ).filter(
        Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=as_of)
    )
    total = _Decimal('0.00')
    for assignment in assignments:
        total += assignment.alokasi_fte
    return _quantize(total)
