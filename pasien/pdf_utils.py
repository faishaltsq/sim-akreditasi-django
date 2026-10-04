"""PDF generation for Resume Medis / Discharge Summary."""
from io import BytesIO
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


# ── Colours ──────────────────────────────────────────────────────────────────
TEAL      = colors.HexColor('#0d9488')
TEAL_LITE = colors.HexColor('#ccfbf1')
DARK      = colors.HexColor('#0f172a')
MUTED     = colors.HexColor('#64748b')
WHITE     = colors.white
LIGHT_BG  = colors.HexColor('#f8fafc')

# ── Style helpers ─────────────────────────────────────────────────────────────
def _style(name, parent='Normal', **kw):
    return ParagraphStyle(name, fontName=kw.pop('fontName', 'Helvetica'),
                          fontSize=kw.pop('fontSize', 9),
                          leading=kw.pop('leading', 12),
                          textColor=kw.pop('textColor', DARK), **kw)


def _section_header(text, styles):
    """Teal-background section title row inside a Table."""
    p = Paragraph(f'<b>{text}</b>', styles['sec_head'])
    t = Table([[p]], colWidths=[165 * mm])
    t.setStyle(TableStyle([
        ('BACKGROUND',  (0, 0), (-1, -1), TEAL),
        ('TOPPADDING',  (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _kv_table(rows, styles, col_w=(55 * mm, 110 * mm)):
    """Two-column label: value table with a light border box."""
    data = []
    for label, value in rows:
        data.append([
            Paragraph(label, styles['label']),
            Paragraph(str(value) if value is not None else '-', styles['value']),
        ])
    t = Table(data, colWidths=list(col_w))
    t.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, MUTED),
        ('INNERGRID',    (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('BACKGROUND',   (0, 0), (0, -1), LIGHT_BG),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING',  (0, 0), (-1, -1), 5),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _text_box(text, styles):
    """Single-cell box for free-text fields."""
    p = Paragraph(str(text or '-').replace('\n', '<br/>'), styles['value'])
    t = Table([[p]], colWidths=[165 * mm])
    t.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, MUTED),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    return t


def _fmt_date(d, fmt='%d/%m/%Y'):
    if d is None:
        return '-'
    if hasattr(d, 'strftime'):
        return d.strftime(fmt)
    return str(d)


def _fmt_rupiah(amount):
    try:
        return f'Rp {int(amount):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return '-'


# ── Main generator ────────────────────────────────────────────────────────────
def generate_resume_pdf(kunjungan_pk: int) -> bytes:
    """
    Generate A4 Resume Medis PDF for a KunjunganPasien.
    Returns raw bytes suitable for HttpResponse.
    """
    # Import here so this module is importable without Django setup
    from pasien.models import KunjunganPasien

    k = KunjunganPasien.objects.select_related(
        'pasien', 'bed__ruangan', 'created_by'
    ).prefetch_related('billing').get(pk=kunjungan_pk)

    d  = k.discharge          # DischargeRecord (guaranteed to exist by view)
    p  = k.pasien
    billing_qs = k.billing.all()

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    # ── Styles ────────────────────────────────────────────────────────────────
    styles = {
        'hospital': _style('hospital', fontName='Helvetica-Bold', fontSize=16,
                           textColor=TEAL, alignment=TA_CENTER, spaceAfter=2),
        'subtitle':  _style('subtitle', fontName='Helvetica-Bold', fontSize=10,
                            textColor=DARK, alignment=TA_CENTER, spaceAfter=1),
        'sub2':      _style('sub2', fontName='Helvetica', fontSize=8,
                            textColor=MUTED, alignment=TA_CENTER),
        'sec_head':  _style('sec_head', fontName='Helvetica-Bold', fontSize=9,
                            textColor=WHITE),
        'label':     _style('label', fontName='Helvetica-Bold', fontSize=8.5,
                            textColor=MUTED),
        'value':     _style('value', fontName='Helvetica', fontSize=8.5,
                            textColor=DARK),
        'footer':    _style('footer', fontName='Helvetica', fontSize=7.5,
                            textColor=MUTED, alignment=TA_CENTER),
        'footer_r':  _style('footer_r', fontName='Helvetica', fontSize=7.5,
                            textColor=MUTED, alignment=TA_RIGHT),
    }

    story = []
    SP = lambda n=4: Spacer(1, n * mm)

    # ── Header ────────────────────────────────────────────────────────────────
    story.append(Paragraph('RS MonsisKami', styles['hospital']))
    story.append(Paragraph('RESUME MEDIS / DISCHARGE SUMMARY', styles['subtitle']))
    story.append(Paragraph(
        f'Dicetak: {datetime.now().strftime("%d/%m/%Y %H:%M")} &nbsp;|&nbsp; '
        f'No. Kunjungan: <b>{k.no_kunjungan}</b>',
        styles['sub2']
    ))
    story.append(HRFlowable(width='100%', thickness=1.2, color=TEAL, spaceAfter=6))

    # ── 1. Data Pasien ────────────────────────────────────────────────────────
    story.append(_section_header('1. DATA PASIEN', styles))
    alergi = ' | '.join(filter(None, [p.alergi_obat, p.alergi_lain])) or '-'
    story.append(_kv_table([
        ('No. Rekam Medis', p.no_rm),
        ('Nama Lengkap',    p.nama_lengkap),
        ('NIK',             p.nik or '-'),
        ('Tanggal Lahir',   _fmt_date(p.tanggal_lahir)),
        ('Jenis Kelamin',   p.get_jenis_kelamin_display()),
        ('Golongan Darah',  p.golongan_darah),
        ('Alergi',          alergi),
        ('No. BPJS',        p.no_bpjs or '-'),
    ], styles))
    story.append(SP(3))

    # ── 2. Data Kunjungan ─────────────────────────────────────────────────────
    story.append(_section_header('2. DATA KUNJUNGAN', styles))
    story.append(_kv_table([
        ('No. Kunjungan',    k.no_kunjungan),
        ('Jenis Kunjungan',  k.get_jenis_kunjungan_display()),
        ('Tanggal Masuk',    _fmt_date(k.tanggal_masuk, '%d/%m/%Y %H:%M')),
        ('Tanggal Keluar',   _fmt_date(k.tanggal_keluar, '%d/%m/%Y %H:%M')),
        ('DPJP',             k.dpjp or '-'),
        ('Penjamin',         k.get_penjamin_display()),
        ('Diagnosa Masuk',   k.diagnosa_masuk or '-'),
        ('Diagnosa Keluar',  k.diagnosa_keluar or '-'),
    ], styles))
    story.append(SP(3))

    # ── 3. Resume Medis ───────────────────────────────────────────────────────
    story.append(_section_header('3. RESUME MEDIS (DISCHARGE SUMMARY)', styles))
    story.append(_text_box(d.resume_medis, styles))
    story.append(SP(3))

    # ── 4. Edukasi & Instruksi Pulang ─────────────────────────────────────────
    story.append(_section_header('4. EDUKASI & INSTRUKSI PULANG', styles))
    story.append(_text_box(d.edukasi_pulang or '-', styles))
    story.append(SP(3))

    # ── 5. Obat Pulang ────────────────────────────────────────────────────────
    story.append(_section_header('5. OBAT PULANG', styles))
    story.append(_text_box(d.obat_pulang or '-', styles))
    story.append(SP(3))

    # ── 6. Jadwal Kontrol Ulang ───────────────────────────────────────────────
    story.append(_section_header('6. JADWAL KONTROL ULANG', styles))
    story.append(_kv_table([
        ('Tanggal Kontrol', _fmt_date(d.jadwal_kontrol) if d.jadwal_kontrol else 'Tidak ada'),
    ], styles))
    story.append(SP(3))

    # ── 7. Billing Summary ────────────────────────────────────────────────────
    story.append(_section_header('7. RINGKASAN TAGIHAN', styles))
    bill_data = [[
        Paragraph('<b>Kategori</b>', styles['label']),
        Paragraph('<b>Nama Item</b>', styles['label']),
        Paragraph('<b>Qty</b>', styles['label']),
        Paragraph('<b>Harga Satuan</b>', styles['label']),
        Paragraph('<b>Subtotal</b>', styles['label']),
    ]]
    total = 0
    for b in billing_qs:
        sub = b.subtotal
        total += sub
        bill_data.append([
            Paragraph(b.get_kategori_display(), styles['value']),
            Paragraph(b.nama_item, styles['value']),
            Paragraph(str(b.kuantitas), styles['value']),
            Paragraph(_fmt_rupiah(b.harga_satuan), styles['value']),
            Paragraph(_fmt_rupiah(sub), styles['value']),
        ])
    if not billing_qs:
        bill_data.append([
            Paragraph('-', styles['value']), Paragraph('-', styles['value']),
            Paragraph('-', styles['value']), Paragraph('-', styles['value']),
            Paragraph('-', styles['value']),
        ])
    # Total row
    bill_data.append([
        Paragraph('', styles['value']),
        Paragraph('', styles['value']),
        Paragraph('', styles['value']),
        Paragraph('<b>TOTAL</b>', styles['label']),
        Paragraph(f'<b>{_fmt_rupiah(total)}</b>', styles['label']),
    ])

    col_w = [30 * mm, 68 * mm, 12 * mm, 27 * mm, 28 * mm]
    bt = Table(bill_data, colWidths=col_w)
    bt.setStyle(TableStyle([
        ('BOX',          (0, 0), (-1, -1), 0.5, MUTED),
        ('INNERGRID',    (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('BACKGROUND',   (0, 0), (-1, 0), LIGHT_BG),
        ('BACKGROUND',   (0, -1), (-1, -1), TEAL_LITE),
        ('TOPPADDING',   (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 3),
        ('LEFTPADDING',  (0, 0), (-1, -1), 4),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
    ]))
    story.append(bt)
    story.append(SP(3))

    # ── 8. Kondisi Pulang & Status Clearance ──────────────────────────────────
    story.append(_section_header('8. KONDISI PULANG & STATUS CLEARANCE', styles))
    story.append(_kv_table([
        ('Kondisi Pulang',   d.get_kondisi_pulang_display()),
        ('Status Clearance', d.get_status_clearance_display()),
        ('Tanggal Discharge', _fmt_date(d.tanggal_discharge, '%d/%m/%Y %H:%M')),
        ('Total Tagihan',    _fmt_rupiah(d.total_tagihan)),
    ], styles))
    story.append(SP(6))

    # ── Footer / Signature ────────────────────────────────────────────────────
    dpjp_name = k.dpjp or 'DPJP'
    footer_data = [[
        Paragraph(
            f'Dicetak: {datetime.now().strftime("%d/%m/%Y %H:%M")}<br/>'
            'Dokumen ini sah tanpa tanda tangan basah jika dicetak dari sistem ARIMA.',
            styles['footer']
        ),
        Paragraph(
            f'Hormat kami,<br/><br/><br/>'
            f'<b>({dpjp_name})</b><br/>Dokter Penanggung Jawab Pasien',
            styles['footer_r']
        ),
    ]]
    ft = Table(footer_data, colWidths=[110 * mm, 55 * mm])
    ft.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'BOTTOM'),
        ('TOPPADDING', (0, 0), (-1, -1), 0),
    ]))
    story.append(HRFlowable(width='100%', thickness=0.5, color=MUTED, spaceAfter=4))
    story.append(ft)

    doc.build(story)
    return buf.getvalue()
