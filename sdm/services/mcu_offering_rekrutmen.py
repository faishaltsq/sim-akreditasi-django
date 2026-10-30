"""Fase C6: MCU pra-kerja, surat penawaran, dan konfirmasi kandidat.

Aturan yang dijaga:
- Hanya FIT dan FIT WITH NOTE yang boleh melanjutkan ke penawaran; UNFIT
  berhenti di tahap MCU dan tidak pernah menghasilkan surat.
- Nomor surat tidak pernah dikarang: kalau pola belum ditetapkan admin, kolom
  nomor dibiarkan kosong dan surat bertanda "(tanpa nomor)".
- Konfirmasi kandidat memakai token, bukan login; yang dicatat adalah siapa,
  kapan, dan dari IP mana.
"""
from io import BytesIO

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib import colors

from sdm.models import HasilMCU, KonfirmasiOffering, Lamaran


# ── MCU ────────────────────────────────────────────────────────────────────
def catat_mcu(*, lamaran, status, tanggal_periksa=None, penyelenggara='',
              catatan='', berkas=None, actor=None):
    """Record or update the MCU outcome for one application."""
    if status not in dict(HasilMCU.STATUS_CHOICES):
        raise ValidationError({'status': 'Status MCU tidak dikenal.'})
    obj, _ = HasilMCU.objects.update_or_create(
        lamaran=lamaran,
        defaults={
            'status': status,
            'tanggal_periksa': tanggal_periksa,
            'penyelenggara': penyelenggara,
            'catatan': catatan,
            'diperiksa_oleh': actor,
        },
    )
    if berkas is not None:
        obj.berkas = berkas
        obj.save(update_fields=['berkas', 'updated_at'])
    return obj


def boleh_menawarkan(lamaran):
    """True only when a MCU result exists and permits continuation.

    Reads the row fresh rather than the reverse one-to-one cache: the stage
    transition may have replaced an UNFIT result with FIT in the same request,
    and a cached relation would still report the old verdict.
    """
    mcu = HasilMCU.objects.filter(lamaran=lamaran).first()
    return mcu is not None and mcu.boleh_lanjut


# ── Surat penawaran ────────────────────────────────────────────────────────
def _kop_lines():
    from akreditasi.models import SystemConfig
    config = SystemConfig.objects.first()
    kop = (config.kop_surat_text if config is not None else '') or ''
    return [line.strip() for line in kop.splitlines() if line.strip()]


def _build_offering_pdf(lamaran, nomor_surat, posisi, unit_nama):
    """Render the offering letter to bytes using the official letterhead."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=20 * mm, rightMargin=20 * mm,
        topMargin=16 * mm, bottomMargin=16 * mm,
        title='Surat Penawaran Kerja',
    )
    story = []
    for line in _kop_lines():
        story.append(Paragraph(
            f'<para alignment="center"><b>{line}</b></para>',
            _style(fontSize=10, leading=13),
        ))
    story.append(Spacer(1, 6))
    story.append(_rule())
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        '<para alignment="center"><b>SURAT PENAWARAN KERJA</b></para>',
        _style(fontSize=13, leading=16),
    ))
    story.append(Paragraph(
        f'<para alignment="center">Nomor: {nomor_surat or "(tanpa nomor)"}</para>',
        _style(fontSize=9, leading=12),
    ))
    story.append(Spacer(1, 12))

    nama = lamaran.nama_pelamar
    rows = [
        ['Dengan hormat,', ''],
        ['', ''],
        [
            'Berdasarkan hasil seleksi yang telah Anda lalui, kami menawarkan '
            'Anda posisi berikut:', '',
        ],
        ['Posisi', posisi],
        ['Unit Kerja', unit_nama],
        ['Nama Kandidat', nama],
        ['Tanggal Surat', timezone.localdate().strftime('%d %B %Y')],
    ]
    table = Table(rows, colWidths=[45 * mm, 105 * mm])
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), 'Helvetica', 9),
        ('FONT', (0, 3), (0, -1), 'Helvetica-Bold', 9),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('SPAN', (0, 0), (1, 0)),
        ('SPAN', (0, 2), (1, 2)),
    ]))
    story.append(table)
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        'Kami tunggu konfirmasi Anda melalui tautan yang dikirim bersamaan '
        'dengan surat ini. Apabila Anda menyetujui penawaran, tahap berikutnya '
        'adalah penerbitan surat keputusan dan orientasi.',
        _style(fontSize=9, leading=13),
    ))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        'Hormat kami,<br/>Tim Rekrutmen',
        _style(fontSize=9, leading=13),
    ))
    doc.build(story)
    return buffer.getvalue()


def _style(**kw):
    from reportlab.lib.styles import ParagraphStyle
    base = dict(fontName='Helvetica', fontSize=9, leading=12,
                textColor=colors.HexColor('#0f172a'))
    base.update(kw)
    return ParagraphStyle('offering', **base)


def _rule():
    from reportlab.platypus import HRFlowable
    return HRFlowable(width='100%', thickness=1, color=colors.HexColor('#cbd5e1'))


def buat_offering(*, lamaran, nomor_surat='', actor=None):
    """Create the offering record and render its PDF.

    Blocked unless the MCU result permits continuation: an UNFIT candidate must
    never receive an offer.
    """
    if not boleh_menawarkan(lamaran):
        raise ValidationError({
            'mcu': 'Hasil MCU belum mengizinkan penawaran kerja.',
        })
    existing = getattr(lamaran, 'konfirmasi_offering', None)
    if existing is not None:
        return existing

    vacancy = lamaran.lowongan
    pdf = _build_offering_pdf(
        lamaran, nomor_surat, vacancy.judul,
        vacancy.unit_kerja.name if vacancy.unit_kerja else '',
    )
    offering = KonfirmasiOffering.objects.create(
        lamaran=lamaran, nomor_surat=nomor_surat, created_by=actor,
    )
    nama_file = f'offering-{lamaran.pk}.pdf'
    offering.berkas.save(nama_file, ContentFile(pdf), save=True)
    return offering


def konfirmasi_offering(*, token, setuju, ip=None, catatan=''):
    """Record the candidate's decision on the offering letter."""
    if not isinstance(setuju, bool):
        raise ValidationError({'keputusan': 'Pilih keputusan penawaran yang valid.'})
    offering = KonfirmasiOffering.objects.filter(token=token).first()
    if offering is None:
        raise ValidationError({'token': 'Tautan konfirmasi tidak dikenal.'})
    if offering.disetujui is not None:
        raise ValidationError({
            'token': 'Penawaran ini sudah dikonfirmasi sebelumnya.',
        })
    offering.disetujui = setuju
    offering.disetujui_at = timezone.now()
    offering.ip_pemersetujui = ip
    offering.catatan_kandidat = catatan
    offering.save(update_fields=[
        'disetujui', 'disetujui_at', 'ip_pemersetujui', 'catatan_kandidat',
    ])
    return offering
