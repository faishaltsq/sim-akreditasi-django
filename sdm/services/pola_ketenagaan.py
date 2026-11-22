"""Analisis Pola Ketenagaan lintas rumpun (Medis, Keperawatan, Nakes Lain, Non-Medis).

Melengkapi :func:`sdm.services.dashboard.build_hc_dashboard` yang sudah menyajikan
baris formasi per unit/profesi. Modul ini menambahkan pengelompokan per rumpun
sesuai STARKES 2024 (KPS & TKRS) beserta klasifikasi kecukupan yang dipakai
dasbor dan pemicu eskalasi risiko.
"""
from decimal import Decimal

from django.db.models import Count
from django.utils import timezone

from sdm.akses import visible_employees, visible_units
from sdm.models import MasterProfesiPegawai, RencanaFormasi

RUMPUN_ORDER = ['MEDIS', 'KEPERAWATAN_KEBIDANAN', 'NAKES_LAIN', 'NON_KLINIS']
RUMPUN_LABEL = dict(MasterProfesiPegawai.KELUARGA_CHOICES)


def klasifikasi_gap(gap_fte):
    """Kembalikan (status, badge) dari selisih FTE standar - eksisting."""
    gap = Decimal(str(gap_fte or 0))
    if gap > Decimal('0.00'):
        return ('Surplus', 'info')
    if gap == Decimal('0.00'):
        return ('Sesuai Standar', 'success')
    if gap >= Decimal('-1.00'):
        return ('Defisit Ringan', 'warning')
    return ('Defisit Kritis', 'danger')


def hitung_gap_ketenagaan(user, *, unit=None):
    """Baris gap per unit/profesi dari rencana formasi berstatus APPROVED.

    Hanya membaca hasil kalkulasi yang sudah disetujui (immutable) sehingga
    angka pada laporan tidak berubah ketika asumsi direvisi.
    """
    scope_units = visible_units(user)
    if unit is not None:
        scope_units = scope_units.filter(pk=getattr(unit, 'pk', unit))

    rencana_qs = (
        RencanaFormasi.objects.filter(unit_kerja__in=scope_units, status='APPROVED')
        .select_related('unit_kerja', 'result')
        .order_by('unit_kerja__code', 'profesi')
    )

    rumpun_map = {
        (m.nama or '').strip().lower(): m.keluarga
        for m in MasterProfesiPegawai.objects.all()
    }

    baris = []
    for rencana in rencana_qs:
        hasil = getattr(rencana, 'result', None)
        if hasil is None:
            continue
        rumpun = rumpun_map.get((rencana.profesi or '').strip().lower(), 'NON_KLINIS')
        # HasilFormasi.gap_fte = required - actual, sehingga nilai POSITIF berarti
        # kekurangan tenaga. Dokumen sumber (dan pembaca laporan) memakai arah
        # sebaliknya: eksisting - standar, negatif = defisit. Konversi dilakukan
        # di sini sekali, bukan di setiap template.
        gap_tampil = (hasil.actual_fte or Decimal('0')) - (hasil.required_fte or Decimal('0'))
        status, badge = klasifikasi_gap(gap_tampil)
        baris.append({
            'formasi_id': rencana.pk,
            'unit_id': rencana.unit_kerja_id,
            'unit_nama': rencana.unit_kerja.name if rencana.unit_kerja else '',
            'unit_kode': rencana.unit_kerja.code if rencana.unit_kerja else '',
            'rumpun': rumpun,
            'rumpun_label': RUMPUN_LABEL.get(rumpun, rumpun),
            'profesi': rencana.profesi,
            'standar_fte': hasil.required_fte,
            'standar_headcount': hasil.required_headcount,
            'eksisting_fte': hasil.actual_fte,
            'gap_fte': gap_tampil,
            'gap_repo_fte': hasil.gap_fte,
            'sufficiency_pct': hasil.sufficiency_pct,
            'status': status,
            'badge': badge,
        })
    return baris


def ringkasan_per_rumpun(user, *, unit=None):
    """Agregat jumlah pegawai aktif per rumpun untuk kartu distribusi dasbor."""
    karyawan = visible_employees(user, unit=unit).filter(
        status='AKTIF', profesi_master__isnull=False,
    )
    # Pegawai.Meta.ordering would otherwise join the GROUP BY and split every
    # employee into its own group, so the count collapses to 1 per rumpun.
    agregat = {
        row['profesi_master__keluarga']: row['jumlah']
        for row in karyawan.order_by().values('profesi_master__keluarga').annotate(
            jumlah=Count('pk')
        )
    }
    total = sum(agregat.values()) or 0
    hasil = []
    for kode in RUMPUN_ORDER:
        jumlah = agregat.get(kode, 0)
        hasil.append({
            'kode': kode,
            'label': RUMPUN_LABEL.get(kode, kode),
            'jumlah': jumlah,
            'persen': round(jumlah / total * 100, 1) if total else 0.0,
        })
    return hasil


def hitung_ringkasan_pola(user, *, unit=None):
    """Paket konteks siap-render untuk bagian Pola Ketenagaan pada dasbor HC."""
    baris = hitung_gap_ketenagaan(user, unit=unit)
    total_standar = sum((b['standar_fte'] for b in baris), Decimal('0'))
    total_eksisting = sum((b['eksisting_fte'] for b in baris), Decimal('0'))
    kritis = [b for b in baris if b['badge'] == 'danger']
    return {
        'pola_baris': baris,
        'pola_ada_data': bool(baris),
        'pola_total_standar': total_standar,
        'pola_total_eksisting': total_eksisting,
        'pola_total_gap': total_eksisting - total_standar,
        'pola_jumlah_kritis': len(kritis),
        'pola_distribusi_rumpun': ringkasan_per_rumpun(user, unit=unit),
    }


def render_sk_pola_pdf(user, *, unit=None, as_of=None):
    """Render dokumen SK Pola Ketenagaan (PDF) siap tanda tangan Direktur.

    Isi: kop rumah sakit, judul, dasar hukum, tabel per unit/profesi/rumpun
    beserta status kecukupan, ringkasan distribusi rumpun, dan blok tanda
    tangan. Angka diambil dari hasil formasi yang disetujui sehingga cetakan
    hari ini tetap sama dengan angka yang disetujui.
    """
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    from sdm.services.orientasi import _pdf_kop, _pdf_styles

    hari_ini = as_of or timezone.localdate()
    ringkasan = hitung_ringkasan_pola(user, unit=unit)
    baris = ringkasan['pola_baris']
    distribusi = ringkasan['pola_distribusi_rumpun']

    styles = _pdf_styles()
    buffer = BytesIO()
    dokumen = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=12 * mm, bottomMargin=12 * mm,
        title='SK Pola Ketenagaan',
    )

    story = []
    _pdf_kop(story, styles)
    story.append(Paragraph('KEPUTUSAN DIREKTUR TENTANG POLA KETENAGAAN', styles['title']))
    story.append(Paragraph(
        f'Periode penilaian: tahun {hari_ini.year}', styles['body']
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        'Dasar: Standar Akreditasi STARKES 2024 Bab KPS (Kualifikasi dan Pendidikan '
        'Staf) dan TKRS (Tata Kelola Rumah Sakit), serta hasil perhitungan beban kerja '
        'yang telah disetujui.',
        styles['body'],
    ))
    story.append(Spacer(1, 4 * mm))

    if baris:
        kepala = ['Unit', 'Rumpun', 'Profesi', 'Standar', 'Eksisting', 'Gap', 'Status']
        data = [kepala]
        for row in baris:
            data.append([
                row['unit_kode'],
                row['rumpun_label'],
                Paragraph(row['profesi'], styles['body']),
                f"{row['standar_fte']}",
                f"{row['eksisting_fte']}",
                f"{row['gap_fte']}",
                row['status'],
            ])
        tabel = Table(
            data, repeatRows=1,
            colWidths=[22 * mm, 42 * mm, 62 * mm, 20 * mm, 22 * mm, 18 * mm, 30 * mm],
        )
        tabel.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#94a3b8')),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('ALIGN', (3, 1), (5, -1), 'RIGHT'),
        ]))
        story.append(tabel)
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(
            f"Total standar: {ringkasan['pola_total_standar']} FTE · "
            f"Total eksisting: {ringkasan['pola_total_eksisting']} FTE · "
            f"Selisih: {ringkasan['pola_total_gap']} FTE · "
            f"Unit defisit kritis: {ringkasan['pola_jumlah_kritis']}",
            styles['body'],
        ))
    else:
        story.append(Paragraph(
            'Belum ada hasil formasi yang disetujui pada periode ini, sehingga pola '
            'ketenagaan belum dapat ditetapkan.',
            styles['body'],
        ))

    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph('Distribusi pegawai aktif per rumpun', styles['title']))
    dist_data = [['Rumpun', 'Jumlah', 'Porsi']]
    for item in distribusi:
        dist_data.append([item['label'], str(item['jumlah']), f"{item['persen']}%"])
    tabel_dist = Table(dist_data, colWidths=[80 * mm, 25 * mm, 25 * mm])
    tabel_dist.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2e8f0')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#94a3b8')),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
    ]))
    story.append(tabel_dist)

    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f'Ditetapkan di: ____________________  ·  Tanggal: '
        f'{hari_ini:%d-%m-%Y}',
        styles['body'],
    ))
    story.append(Spacer(1, 12 * mm))
    story.append(Paragraph('Direktur Rumah Sakit', styles['body']))
    story.append(Spacer(1, 14 * mm))
    story.append(Paragraph('(_____________________________)', styles['body']))

    dokumen.build(story)
    return buffer.getvalue()
