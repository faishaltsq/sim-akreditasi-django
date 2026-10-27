"""Sinkronisasi data objektif ke butir penilaian kinerja (siklus ARIMA).

Pilar A (TARGET): capaian INM/IMRS dari ``IndikatorMutu`` via
``agregat_capaian_rentang``; skor otomatis polaritas-aware, tidak pernah
menimpa skor manual. Pilar B (RISIKO): snapshot konteks risiko unit
(insiden, penyelesaian risiko) — skor tetap dinilai manusia karena insiden
tidak memiliki atribusi pelapor. Pilar C (PERILAKU): kerangka butir manual.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q

from akreditasi.mutu_laporan import agregat_capaian_rentang
from akreditasi.models import IndikatorMutu, InsidenKeselamatan, RisikoUnit
from sdm.akses import require_hc_capability
from sdm.models import (
    ButirPenilaian,
    PenempatanPegawai,
    PeristiwaSDM,
    TahapPenilaian,
)
from sdm.services.workflow_kinerja import current_stage

SKOR_ATAS = Decimal('5.00')
SKOR_BAWAH = Decimal('1.00')
BOBOT_BUTIR = Decimal('10.00')
MAX_BUTIR_A = 4

# Kerangka butir B: realisasi = snapshot data unit, skor dinilai manusia
# (insiden tidak punya atribusi pelapor per-orang).
BUTIR_RISIKO = [
    ('Partisipasi pelaporan & tindak lanjut insiden keselamatan unit', 'Terlaporkan / selesai'),
    ('Penyelesaian risiko unit (PDCA / mitigasi)', 'Berjalan / selesai'),
    ('Mitigasi & FMEA atas indikator belum tercapai', 'Terlaksana'),
]

BUTIR_PERILAKU = [
    'Kepatuhan SOP & keselamatan pasien',
    'Kolaborasi & komunikasi tim',
    'Inisiatif perbaikan & disiplin',
]


def _bulan_rentang(tanggal_mulai, tanggal_selesai):
    """Daftar (tahun, bulan) inklusif antara dua tanggal."""
    bulan = []
    tahun, b = tanggal_mulai.year, tanggal_mulai.month
    while (tahun, b) <= (tanggal_selesai.year, tanggal_selesai.month):
        bulan.append((tahun, b))
        b += 1
        if b > 12:
            tahun, b = tahun + 1, 1
    return bulan


def _skor_dari_capaian(indikator, capaian):
    """Skor 0-5 dari capaian vs target, polaritas-aware; None tanpa data."""
    if capaian is None:
        return None
    target = float(indikator.target_nilai)
    if target <= 0:
        return SKOR_ATAS
    if indikator.arah_target == 'MAX':
        if capaian <= 0:
            return SKOR_BAWAH
        rasio = target / capaian
    else:
        rasio = capaian / target
    skor = Decimal(str(rasio)) * SKOR_ATAS
    return max(SKOR_BAWAH, min(SKOR_ATAS, skor))


def _teks_nilai(nilai, satuan):
    if nilai is None:
        return ''
    return f'{nilai:g}{satuan or ""}'


def _capaian_teragregat(indikator, bulan_list):
    """Σ numerator / Σ denominator × faktor atas seluruh bulan berdata."""
    num_total = 0
    den_total = 0
    terisi = 0
    for (tahun, bln) in bulan_list:
        agg = agregat_capaian_rentang(indikator, tahun, bln, bln)
        num_total += agg['num'] or 0
        den_total += agg['den'] or 0
        terisi += agg['bulan_terisi']
    if den_total <= 0:
        return None, 0
    if indikator.tipe_pengukuran == 'persen':
        faktor = Decimal('100')
    else:
        faktor = Decimal(str(indikator.faktor_pengali or 100))
    capaian = round(float((Decimal(num_total) / Decimal(den_total)) * faktor), 2)
    return capaian, terisi


def _pilar_a(appraisal, units, bulan_list):
    """Butir A: indikator INM/IMRS unit penempatan atau RS-wide (maks 4)."""
    dibuat, diperbarui = 0, 0
    kandidat = list(
        IndikatorMutu.objects.filter(
            Q(unit__in=units) | Q(unit__isnull=True),
            aktif=True,
            jenis__in=('INM', 'IMRS', 'IMP_RS', 'NASIONAL'),
        )
        .order_by('unit_id', 'jenis', 'kode_indikator')[:MAX_BUTIR_A]
    )
    existing = {
        row.indikator_id: row
        for row in appraisal.items.filter(kategori='TARGET', indikator__isnull=False)
    }
    for ind in kandidat:
        capaian, terisi = _capaian_teragregat(ind, bulan_list)
        refs = [{
            'type': 'indikator_mutu',
            'id': str(ind.pk),
            'kode': ind.kode_indikator,
            'capaian': capaian,
            'bulan_terisi': terisi,
        }]
        target_teks = _teks_nilai(float(ind.target_nilai), ind.satuan)
        realisasi_teks = _teks_nilai(capaian, ind.satuan)

        row = existing.get(ind.pk)
        if row is None:
            row = ButirPenilaian.objects.create(
                appraisal=appraisal,
                kategori='TARGET',
                nama=ind.nama_indikator[:200],
                weight=BOBOT_BUTIR,
                target=target_teks,
                realisasi=realisasi_teks,
                sumber_refs=refs,
                indikator=ind,
            )
            dibuat += 1
        else:
            row.realisasi = realisasi_teks
            row.sumber_refs = refs
            if not row.target:
                row.target = target_teks
            row.save(update_fields=['realisasi', 'sumber_refs', 'target'])
            diperbarui += 1
        if row.score is None and capaian is not None:
            row.score = _skor_dari_capaian(ind, capaian)
            row.save(update_fields=['score'])
    return dibuat, diperbarui, len(kandidat)


def _pilar_b(appraisal, units, bulan_list, rentang):
    """Butir B: snapshot risiko unit; skor manual (tanpa atribusi pelapor)."""
    mulai, selesai = rentang
    dibuat = 0
    existing = {
        row.nama: row
        for row in appraisal.items.filter(kategori='RISIKO')
    }
    insiden_count = InsidenKeselamatan.objects.filter(
        unit__in=units,
        tanggal_kejadian__range=(mulai, selesai),
    ).count()
    risiko_total = RisikoUnit.objects.filter(unit__in=units).count()
    risiko_proses = RisikoUnit.objects.filter(
        unit__in=units, status__in=('DO', 'EVALUASI', 'SELESAI'),
    ).count()
    snapshot = [{
        'type': 'risiko_unit',
        'insiden_terlapor': insiden_count,
        'risiko_total': risiko_total,
        'risiko_proses': risiko_proses,
    }]
    realisasi_map = {
        BUTIR_RISIKO[0][0]: (
            f'{insiden_count} insiden terlapor' if insiden_count else 'Tanpa insiden terlapor'
        ),
        BUTIR_RISIKO[1][0]: f'{risiko_proses}/{risiko_total} risiko berproses',
        BUTIR_RISIKO[2][0]: 'Lihat snapshot risiko unit',
    }
    refs_map = {
        BUTIR_RISIKO[0][0]: [{'type': 'insiden_unit', 'count': insiden_count}],
        BUTIR_RISIKO[1][0]: snapshot,
        BUTIR_RISIKO[2][0]: snapshot,
    }
    for nama, target_teks in BUTIR_RISIKO:
        row = existing.get(nama)
        if row is None:
            ButirPenilaian.objects.create(
                appraisal=appraisal,
                kategori='RISIKO',
                nama=nama,
                weight=BOBOT_BUTIR,
                target=target_teks,
                realisasi=realisasi_map[nama][:60],
                sumber_refs=refs_map[nama],
            )
            dibuat += 1
        else:
            row.realisasi = realisasi_map[nama][:60]
            row.sumber_refs = refs_map[nama]
            row.save(update_fields=['realisasi', 'sumber_refs'])
    return dibuat


def _pilar_c(appraisal):
    """Butir C: kerangka perilaku, skor manual atasan."""
    dibuat = 0
    existing = set(
        appraisal.items.filter(kategori='PERILAKU').values_list('nama', flat=True)
    )
    for nama in BUTIR_PERILAKU:
        if nama in existing:
            continue
        ButirPenilaian.objects.create(
            appraisal=appraisal,
            kategori='PERILAKU',
            nama=nama,
            weight=BOBOT_BUTIR,
        )
        dibuat += 1
    return dibuat


def sinkronkan_data(appraisal, *, actor):
    """Tarik data mutu & risiko ke butir; idempoten, atomic, tanpa override skor.

    Return ``(butir_dibuat, butir_diperbarui)``. Re-run memperbarui
    realisasi/sumber data, bukan membuat duplikat.
    """
    require_hc_capability(actor, 'can_manage_hc_appraisals', employee=appraisal.employee)
    if appraisal.status == 'FINAL':
        raise ValueError('Penilaian sudah final; tidak dapat disinkronkan.')

    periode = appraisal.periode
    bulan_list = _bulan_rentang(periode.tanggal_mulai, periode.tanggal_selesai)
    units = list(
        PenempatanPegawai.objects.filter(pegawai=appraisal.employee)
        .exclude(unit_kerja_id=None)
        .values_list('unit_kerja_id', flat=True)
        .distinct()
    )
    rentang = (periode.tanggal_mulai, periode.tanggal_selesai)

    with transaction.atomic():
        buat_a, perbarui_a, total_a = _pilar_a(appraisal, units, bulan_list)
        buat_b = _pilar_b(appraisal, units, bulan_list, rentang)
        buat_c = _pilar_c(appraisal)
        dibuat = buat_a + buat_b + buat_c

        if current_stage(appraisal) is None:
            TahapPenilaian.objects.create(
                appraisal=appraisal,
                tahap='DATA_TERKUMPUL',
                aktor=actor,
                catatan=f'Sinkronisasi {total_a} indikator, {buat_b} butir risiko',
            )
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='appraisal_sync',
            target_tipe='appraisal',
            target_id=str(appraisal.pk),
            status_sebelum=appraisal.status,
            status_sesudah=appraisal.status,
            alasan=f'butir dibuat={dibuat} diperbarui={perbarui_a + buat_b}',
        )
    return dibuat, perbarui_a + buat_b
