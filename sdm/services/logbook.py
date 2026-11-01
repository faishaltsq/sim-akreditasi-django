"""Logbook aggregation for the 3-year re-credential requirement (C-2)."""
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import OuterRef, Q, Subquery, Sum
from django.utils import timezone

from sdm.akses import require_hc_capability, visible_units
from sdm.models import EntriLogbookKlinis, KoreksiLogbookTahunan, VerifikasiLogbook

CAPABILITY_VERIFIKASI = 'can_review_hc_credentials'


def logbook_recap(employee, *, months=36):
    """Aggregate one employee's logbook within the trailing window (default 36 months, or 60 months for 5-year).

    Returns ``{'mandiri', 'supervisi', 'kolaborasi', 'total', 'dari_tanggal', 'per_tindakan'}``;
    ``per_tindakan`` rows carry ``{'label', 'mandiri', 'supervisi', 'kolaborasi'}``.
    One grouped aggregate query; totals are summed from the grouped results.
    """
    today = timezone.localdate()
    years, months_left = divmod(months, 12)
    month_index = today.month - 1 - months_left
    year, month_index = today.year - years + month_index // 12, month_index % 12
    month = month_index + 1
    day = min(today.day, 28)  # clamp: month lengths and Feb 29 vary
    dari_tanggal = today.replace(year=year, month=month, day=day)
    rows = (
        EntriLogbookKlinis.objects.filter(
            employee=employee, tanggal__gte=dari_tanggal
        )
        .values('katalog_tindakan__nama', 'tindakan')
        .annotate(
            mandiri=Sum('jumlah_mandiri'),
            supervisi=Sum('jumlah_supervisi'),
            kolaborasi=Sum('jumlah_kolaborasi'),
        )
        .order_by('katalog_tindakan__nama', 'tindakan')
    )
    per_tindakan = []
    mandiri_total = 0
    supervisi_total = 0
    kolaborasi_total = 0
    for row in rows:
        label = row['katalog_tindakan__nama'] or row['tindakan'] or '-'
        m = row['mandiri'] or 0
        s = row['supervisi'] or 0
        k = row['kolaborasi'] or 0
        mandiri_total += m
        supervisi_total += s
        kolaborasi_total += k
        per_tindakan.append({'label': label, 'mandiri': m, 'supervisi': s, 'kolaborasi': k})
    return {
        'mandiri': mandiri_total,
        'supervisi': supervisi_total,
        'kolaborasi': kolaborasi_total,
        'total': mandiri_total + supervisi_total + kolaborasi_total,
        'dari_tanggal': dari_tanggal,
        'per_tindakan': per_tindakan,
    }


def logbook_recap_5tahun(employee, *, years=5, end_date=None):
    """5-year trailing recap untuk PMK 13/2025.

    Mengumpulkan entri logbook karyawan dalam window 5 tahun trailing.
    Mengembalikan ``{'tahun_labels', 'total_5tahun', 'mandiri', 'supervisi',
    'kolaborasi', 'per_tindakan', 'terverifikasi', 'tahunan'}``.

    Bucket tahunan: T1 paling tua hingga T5 (terbaru); tiap bucket 365 hari
    dihitung mundur dari tanggal akhir.
    """
    today = end_date or timezone.localdate()
    start_date = today - timedelta(days=years * 365 + 5)
    # Bucket terindeks tahun kalender relatif terhadap tahun terakhir (T5 = tahun
    # berjalan). Perbedaan indeks 365 hari = 1 tahun, jadi T5 = tahun berjalan,
    # T1 = empat tahun sebelumnya.
    tahun_terakhir = today.year
    daftar_tahun = [tahun_terakhir - (years - 1) + i for i in range(years)]

    recap = {
        'tahun_labels': [f'T{i}' for i in range(1, years + 1)],
        'daftar_tahun': daftar_tahun,
        'tahun_kalender': daftar_tahun,
        'total_5tahun': 0,
        'total': 0,
        'mandiri': 0,
        'supervisi': 0,
        'kolaborasi': 0,
        'grand_total_mandiri': 0,
        'grand_total_kolaborasi': 0,
        'grand_total_supervisi': 0,
        'total_semua': 0,
        'per_tindakan': [],
        'terverifikasi': 0,
        'tahunan': [0] * years,
    }

    entries = (
        EntriLogbookKlinis.objects.filter(
            employee=employee, tanggal__gte=start_date
        )
        .select_related('katalog_tindakan')
        .prefetch_related('verifikasi')
        .order_by('tanggal')
    )

    for entry in entries:
        th = entry.tanggal.year
        idx = th - tahun_terakhir + (years - 1)
        if not 0 <= idx < years:
            continue
        m = entry.jumlah_mandiri or 0
        s = entry.jumlah_supervisi or 0
        k = entry.jumlah_kolaborasi or 0
        total = m + s + k

        recap['mandiri'] += m
        recap['supervisi'] += s
        recap['kolaborasi'] += k
        recap['total_5tahun'] += total
        recap['tahunan'][idx] += total

        label = entry.katalog_tindakan.nama if entry.katalog_tindakan else entry.tindakan
        kode = entry.katalog_tindakan.kode if entry.katalog_tindakan else '-'
        is_verified = any(v.status == VerifikasiLogbook.VERIFIED for v in entry.verifikasi.all())

        row = next(
            (item for item in recap['per_tindakan'] if item['label'] == label), None,
        )
        if row is None:
            row = {
                'label': label,
                'kode': kode,
                'katalog_id': entry.katalog_tindakan_id,
                'tindakan_teks': entry.tindakan if not entry.katalog_tindakan else '',
                'mandiri': 0, 'supervisi': 0, 'kolaborasi': 0,
                'total': 0, 'tahunan': [0] * years,
                'per_tahun': {
                    yr: {'m': 0, 'k': 0, 's': 0, 'total': 0, 'koreksi_id': None}
                    for yr in daftar_tahun
                },
                'verified_count': 0,
                'status_verifikasi': 'Menunggu',
            }
            recap['per_tindakan'].append(row)
        row['mandiri'] += m
        row['supervisi'] += s
        row['kolaborasi'] += k
        row['total'] += total
        row['tahunan'][idx] += total

        if th in row['per_tahun']:
            row['per_tahun'][th]['m'] += m
            row['per_tahun'][th]['k'] += k
            row['per_tahun'][th]['s'] += s
            row['per_tahun'][th]['total'] += total

        if is_verified:
            recap['terverifikasi'] += total
            row['verified_count'] += total

    # Perhitungkan KoreksiLogbookTahunan (penyesuaian portofolio historis PMK 13/2025)
    koreksi_list = KoreksiLogbookTahunan.objects.filter(
        pegawai=employee, tahun__in=daftar_tahun,
    ).select_related('katalog_tindakan')

    for kor in koreksi_list:
        th = kor.tahun
        idx = th - tahun_terakhir + (years - 1)
        if not 0 <= idx < years:
            continue
        km = kor.koreksi_mandiri or 0
        kk = kor.koreksi_kolaborasi or 0
        ks = kor.koreksi_supervisi or 0
        ktot = km + kk + ks

        label = kor.katalog_tindakan.nama if kor.katalog_tindakan else kor.tindakan
        kode = kor.katalog_tindakan.kode if kor.katalog_tindakan else '-'

        row = next(
            (item for item in recap['per_tindakan'] if item['label'] == label), None,
        )
        if row is None:
            row = {
                'label': label,
                'kode': kode,
                'katalog_id': kor.katalog_tindakan_id,
                'tindakan_teks': kor.tindakan if not kor.katalog_tindakan else '',
                'mandiri': 0, 'supervisi': 0, 'kolaborasi': 0,
                'total': 0, 'tahunan': [0] * years,
                'per_tahun': {
                    yr: {'m': 0, 'k': 0, 's': 0, 'total': 0, 'koreksi_id': None}
                    for yr in daftar_tahun
                },
                'verified_count': 0,
                'status_verifikasi': 'Koreksi Portofolio',
            }
            recap['per_tindakan'].append(row)

        row['mandiri'] += km
        row['kolaborasi'] += kk
        row['supervisi'] += ks
        row['total'] += ktot
        row['tahunan'][idx] += ktot

        if th in row['per_tahun']:
            row['per_tahun'][th]['m'] += km
            row['per_tahun'][th]['k'] += kk
            row['per_tahun'][th]['s'] += ks
            row['per_tahun'][th]['total'] += ktot
            row['per_tahun'][th]['koreksi_id'] = str(kor.pk)

        recap['mandiri'] += km
        recap['kolaborasi'] += kk
        recap['supervisi'] += ks
        recap['total_5tahun'] += ktot
        recap['tahunan'][idx] += ktot

    for item in recap['per_tindakan']:
        if item.get('verified_count', 0) > 0:
            item['status_verifikasi'] = 'Terverifikasi'
        elif item.get('status_verifikasi') != 'Koreksi Portofolio':
            item['status_verifikasi'] = 'Menunggu'

        item['tahunan_items'] = [
            {
                'tahun': th,
                'm': item['per_tahun'][th]['m'],
                'k': item['per_tahun'][th]['k'],
                's': item['per_tahun'][th]['s'],
                'total': item['per_tahun'][th]['total'],
                'koreksi_id': item['per_tahun'][th]['koreksi_id'],
            }
            for th in daftar_tahun
        ]

    recap['tahunan_totals'] = [
        {
            'tahun': th,
            'm': sum(r['per_tahun'][th]['m'] for r in recap['per_tindakan']),
            'k': sum(r['per_tahun'][th]['k'] for r in recap['per_tindakan']),
            's': sum(r['per_tahun'][th]['s'] for r in recap['per_tindakan']),
            'total': sum(r['per_tahun'][th]['total'] for r in recap['per_tindakan']),
        }
        for th in daftar_tahun
    ]

    recap['grand_total_mandiri'] = recap['mandiri']
    recap['grand_total_kolaborasi'] = recap['kolaborasi']
    recap['grand_total_supervisi'] = recap['supervisi']
    recap['total_semua'] = recap['total_5tahun']
    recap['total'] = recap['total_5tahun']
    return recap


def entries_to_verify(user):
    """Entries in the reviewer's units with no decision or a REJECTED latest one."""
    units = visible_units(user, capability=CAPABILITY_VERIFIKASI)
    latest = VerifikasiLogbook.objects.filter(entri=OuterRef('pk')).order_by(
        '-verified_at', '-created_at'
    )
    return EntriLogbookKlinis.objects.filter(
        unit_kerja__in=units,
    ).annotate(
        status_verifikasi=Subquery(latest.values('status')[:1]),
    ).filter(
        Q(status_verifikasi__isnull=True) | Q(status_verifikasi=VerifikasiLogbook.REJECTED)
    ).select_related('employee', 'unit_kerja', 'katalog_tindakan')


def require_verifikator(user, entry):
    """Raise PermissionDenied unless an HC review grant covers entry's unit
    or the user's own pegawai row is a jenjang-qualified preseptor there."""
    try:
        pegawai = user.pegawai_hc
    except AttributeError:
        pegawai = None
    if pegawai is not None and pegawai.status == 'AKTIF':
        from sdm.services.preseptor import eligible_preceptors
        if eligible_preceptors(entry.unit_kerja).filter(pk=pegawai.pk).exists():
            return
    require_hc_capability(user, CAPABILITY_VERIFIKASI, unit=entry.unit_kerja)


def verify_entry(*, user, entry, status, catatan=''):
    """Append one decision; the newest row decides the entry's locked state."""
    if status not in dict(VerifikasiLogbook.STATUS_CHOICES):
        raise ValueError(f'Status verifikasi tidak dikenal: {status}')
    require_verifikator(user, entry)
    return VerifikasiLogbook.objects.create(
        entri=entry, verifikator=user, status=status, catatan=catatan,
        verified_at=timezone.now(),
    )


def generate_logbook_5tahun_pdf(employee, buffer=None):
    """Membangkitkan dokumen PDF Portofolio Logbook 5 Tahun Lanskap A4 (PMK 13/2025)."""
    import io
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm

    if buffer is None:
        buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        alignment=1,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        alignment=1,
        textColor=colors.HexColor('#475569'),
        spaceAfter=10,
    )
    cell_style = ParagraphStyle(
        'GridCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9.5,
    )
    cell_bold = ParagraphStyle(
        'GridCellBold',
        parent=cell_style,
        fontName='Helvetica-Bold',
    )
    header_style = ParagraphStyle(
        'GridHeader',
        parent=cell_bold,
        alignment=1,
        textColor=colors.whitesmoke,
    )
    sub_header_style = ParagraphStyle(
        'GridSubHeader',
        parent=cell_bold,
        alignment=1,
        textColor=colors.HexColor('#0f172a'),
    )

    recap = logbook_recap_5tahun(employee, years=5)
    daftar_tahun = recap['daftar_tahun']

    story.append(Paragraph("<b>RS MONSISKAMI — ARIMA HOSPITAL CONTROL</b>", title_style))
    story.append(Paragraph(
        f"<b>REKAPITULASI PORTOFOLIO TINDAKAN KLINIS 5 TAHUN (PMK 13/2025)</b><br/>"
        f"Nama Pegawai: <b>{employee.nama_lengkap}</b> &nbsp;|&nbsp; "
        f"NIP: <b>{employee.nomor_pegawai or '-'}</b> &nbsp;|&nbsp; "
        f"Profesi: <b>{employee.profesi or '-'}</b> &nbsp;|&nbsp; "
        f"Periode Evaluasi: <b>{daftar_tahun[0]} s.d. {daftar_tahun[-1]}</b>",
        subtitle_style,
    ))

    # Header baris 1: No, Tindakan, Kode, [tahun span 3], Total 5 Th, Status
    header_row1 = ['No', 'Jenis Tindakan Klinis', 'Kode']
    for th in daftar_tahun:
        header_row1.extend([str(th), '', ''])
    header_row1.extend(['Total 5 Th', 'Status'])

    # Header baris 2: '', '', '', M, K, S ..., '', ''
    header_row2 = ['', '', '']
    for _ in daftar_tahun:
        header_row2.extend(['M', 'K', 'S'])
    header_row2.extend(['', ''])

    table_data = [
        [Paragraph(f'<b>{c}</b>', header_style) if c else '' for c in header_row1],
        [Paragraph(f'<b>{c}</b>', sub_header_style) if c else '' for c in header_row2],
    ]

    no = 1
    grand_th = {th: {'m': 0, 'k': 0, 's': 0, 'total': 0} for th in daftar_tahun}

    for item in recap['per_tindakan']:
        row = [
            Paragraph(str(no), cell_style),
            Paragraph(item['label'], cell_style),
            Paragraph(item.get('kode') or '-', cell_style),
        ]
        tot_5th = 0
        for th in daftar_tahun:
            th_data = item.get('per_tahun', {}).get(th, {'m': 0, 'k': 0, 's': 0, 'total': 0})
            m = th_data['m']
            k = th_data['k']
            s = th_data['s']
            row.extend([
                Paragraph(str(m) if m else '0', cell_style),
                Paragraph(str(k) if k else '0', cell_style),
                Paragraph(str(s) if s else '0', cell_style),
            ])
            grand_th[th]['m'] += m
            grand_th[th]['k'] += k
            grand_th[th]['s'] += s
            tot_5th += th_data['total']

        row.append(Paragraph(f"<b>{tot_5th}</b>", cell_bold))
        row.append(Paragraph(item.get('status_verifikasi', 'Menunggu'), cell_style))
        table_data.append(row)
        no += 1

    # Baris Total Akumulasi
    total_row = [
        Paragraph('', cell_bold),
        Paragraph('<b>TOTAL AKUMULASI TINDAKAN</b>', cell_bold),
        Paragraph('-', cell_bold),
    ]
    for th in daftar_tahun:
        total_row.extend([
            Paragraph(f"<b>{grand_th[th]['m']}</b>", cell_bold),
            Paragraph(f"<b>{grand_th[th]['k']}</b>", cell_bold),
            Paragraph(f"<b>{grand_th[th]['s']}</b>", cell_bold),
        ])
    total_row.append(Paragraph(f"<b>{recap['total_5tahun']}</b>", cell_bold))
    total_row.append(Paragraph(f"<b>{recap['terverifikasi']} Valid</b>", cell_bold))
    table_data.append(total_row)

    col_widths = [7 * mm, 65 * mm, 16 * mm] + [8 * mm] * (len(daftar_tahun) * 3) + [18 * mm, 22 * mm]

    table_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#f1f5f9')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (1, 2), (1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
        ('SPAN', (0, 0), (0, 1)),
        ('SPAN', (1, 0), (1, 1)),
        ('SPAN', (2, 0), (2, 1)),
        ('SPAN', (-2, 0), (-2, 1)),
        ('SPAN', (-1, 0), (-1, 1)),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e2e8f0')),
    ]

    for i in range(len(daftar_tahun)):
        start_col = 3 + (i * 3)
        table_styles.append(('SPAN', (start_col, 0), (start_col + 2, 0)))

    pdf_table = Table(table_data, colWidths=col_widths, repeatRows=2)
    pdf_table.setStyle(TableStyle(table_styles))
    story.append(pdf_table)

    # Signature Block
    story.append(Spacer(1, 15 * mm))
    today_str = timezone.localdate().strftime('%d %B %Y')
    ttd_data = [
        ['', Paragraph(f'Kebumen, {today_str}', styles['Normal'])],
        [Paragraph('<b>Pemilik Portofolio / DPJP,</b>', styles['Normal']),
         Paragraph('<b>Mengetahui, Ketua Komite / Tim Kredensial,</b>', styles['Normal'])],
        [Spacer(1, 12 * mm), Spacer(1, 12 * mm)],
        [Paragraph(f'<b>{employee.nama_lengkap}</b><br/><font size="7.5">NIP: {employee.nomor_pegawai or "-"}</font>', styles['Normal']),
         Paragraph('<b>........................................................</b><br/><font size="7.5">NIP: ................................................</font>', styles['Normal'])],
    ]
    ttd_table = Table(ttd_data, colWidths=[130 * mm, 130 * mm])
    ttd_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(ttd_table)

    doc.build(story)
    buffer.seek(0)
    return buffer
