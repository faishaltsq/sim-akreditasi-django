"""Eskalasi defisit pola ketenagaan ke Risk Register rumah sakit.

Defisit FTE yang tidak ditindaklanjuti adalah risiko operasional dan
keselamatan pasien (STARKES KPS & TKRS). Service ini membuat satu entri
:class:`akreditasi.RisikoUnit` per unit + profesi + tahun, idempoten: menekan
tombol dua kali tidak menggandakan risiko yang sama.
"""
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

MARKER = 'Defisit pola ketenagaan'


def _periode_untuk(tanggal):
    bulan = tanggal.month
    if bulan <= 3:
        return 'TRIWULAN_1'
    if bulan <= 6:
        return 'TRIWULAN_2'
    if bulan <= 9:
        return 'TRIWULAN_3'
    return 'TRIWULAN_4'


def _skor_probabilitas(gap_fte):
    """Defisit makin dalam, makin sering dampaknya muncul."""
    gap = abs(Decimal(str(gap_fte or 0)))
    if gap >= Decimal('4'):
        return 5
    if gap >= Decimal('2'):
        return 4
    return 3


def _skor_dampak(gap_fte):
    """Defisit kritis menyentuh keselamatan pasien, bukan sekadar beban kerja."""
    gap = abs(Decimal(str(gap_fte or 0)))
    if gap >= Decimal('2'):
        return 5
    return 4


@transaction.atomic
def eskalasi_gap_ke_risiko(baris, *, user, as_of=None):
    """Buat (atau ambil) entri Risk Register untuk satu baris gap.

    ``baris`` adalah satu dict hasil :func:`sdm.services.pola_ketenagaan.
    hitung_gap_ketenagaan`. Kembalikan ``(risiko, created)``.
    """
    from akreditasi.models import RisikoUnit, UnitKerja
    from sdm.models import RencanaFormasi

    if not baris.get('formasi_id'):
        raise ValidationError('Baris gap tidak memiliki rencana formasi.')

    rencana = RencanaFormasi.objects.select_related('unit_kerja').filter(
        pk=baris['formasi_id']
    ).first()
    if rencana is None:
        raise ValidationError('Rencana formasi tidak ditemukan.')

    unit = rencana.unit_kerja
    if not isinstance(unit, UnitKerja):
        raise ValidationError('Unit kerja rencana formasi tidak valid.')

    gap = Decimal(str(baris.get('gap_fte') or 0))
    if gap >= Decimal('0'):
        raise ValidationError(
            'Eskalasi hanya untuk defisit; baris ini tidak menunjukkan kekurangan tenaga.'
        )

    hari_ini = as_of or date.today()
    tahun = hari_ini.year
    label_risiko = (
        f'{MARKER}: {baris.get("profesi", "")} — {unit.code} ({tahun})'
    )

    risiko, created = RisikoUnit.objects.get_or_create(
        unit=unit,
        tahun=tahun,
        kategori_risiko='OPERASIONAL',
        jenis_risiko=label_risiko,
        defaults={
            'periode': _periode_untuk(hari_ini),
            'deskripsi_risiko': (
                f'Kekurangan tenaga {baris.get("profesi", "")} di {unit.name}: '
                f'standar {baris.get("standar_fte")} FTE, eksisting '
                f'{baris.get("eksisting_fte")} FTE, selisih {gap} FTE.'
            ),
            'masalah': (
                'Pemenuhan pola ketenagaan belum tercapai berdasarkan hasil '
                'perhitungan beban kerja yang disetujui.'
            ),
            'data_pendukung': (
                f'Rencana formasi {rencana.pk} periode '
                f'{rencana.periode_mulai:%d-%m-%Y} s/d {rencana.periode_selesai:%d-%m-%Y}; '
                f'kecukupan {baris.get("sufficiency_pct") or "belum dapat dihitung"}%.'
            ),
            'tujuan': (
                'Menjaga rasio tenaga terhadap beban kerja agar risiko kelelahan '
                'staf dan insiden keselamatan pasien terkendali.'
            ),
            'dampak': _skor_dampak(gap),
            'probabilitas': _skor_probabilitas(gap),
            'pengendalian_ada': (
                'Pengaturan ulang jadwal shift dan rotasi internal pada unit terkait.'
            ),
            'strategi_mitigasi': 'KURANGI',
            'rencana_aksi': (
                '1. Pengaturan ulang jadwal shift/rotasi internal; '
                '2. Pengajuan rekrutmen prioritas ke Direktur; '
                '3. Evaluasi ulang beban kerja pada periode berikutnya.'
            ),
            'pj_mitigasi': 'Kepala Unit bersama Bagian SDM',
            'target_selesai': date(tahun, 12, 31),
        },
    )
    return risiko, created
