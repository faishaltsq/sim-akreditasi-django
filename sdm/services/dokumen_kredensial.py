"""Fase 3: generate credential supporting documents from system data.

Only identity data comes from the database. Anything a human must state
(sworn declarations, signatory names, letter numbers, target matrices) is
left blank for the signatory or the later numbering phase. Nothing here
invents a fact.
"""
from io import BytesIO

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

from akreditasi.models import RumahSakitProfile
from akreditasi.system_models import SystemConfig
from sdm.models import (
    DokumenPegawai, DrafDokumenKredensial, PenempatanPegawai, VersiDokumen,
)
from sdm.services.logbook import logbook_recap
from sdm.storage import store_document_version

BULAN = [
    'Januari', 'Februari', 'Maret', 'April', 'Mei', 'Juni', 'Juli',
    'Agustus', 'September', 'Oktober', 'November', 'Desember',
]

IDENTITY_FIELDS = [
    ('nama_lengkap', 'Pegawai.nama_lengkap'),
    ('nomor_pegawai', 'Pegawai.nomor_pegawai'),
    ('profesi', 'Pegawai.profesi'),
    ('jabatan', 'Pegawai.jabatan'),
    ('unit_kerja', 'PenempatanPegawai aktif, nama UnitKerja'),
    ('unit_kerja_kode', 'PenempatanPegawai aktif, UnitKerja.code'),
    ('rumah_sakit', 'RumahSakitProfile.get_default().name'),
    ('tanggal_cetak', 'tanggal sistem, format panjang Indonesia'),
]

# Documents whose body is a statement the signatory must sign. The statement
# text is never pre-filled: only an explicit blank line and a labelled block.
STATEMENT_FIELDS = [
    ('pernyataan', 'diisi dan ditandatangani penanda tangan'),
]

REGISTRY = {
    'CV': {
        'title': 'Daftar Riwayat Hidup',
        'auto_fields': IDENTITY_FIELDS,
        'manual_fields': [],
        'signatory_role': 'Pegawai yang bersangkutan',
        'sertifikat_jenis': 'CV',
        'sworn_statement': False,
    },
    'LOGBOOK_36BULAN': {
        'title': 'Logbook Tindakan Klinis 36 Bulan',
        'auto_fields': IDENTITY_FIELDS + [
            ('rekap_mandiri', 'logbook_recap().mandiri'),
            ('rekap_supervisi', 'logbook_recap().supervisi'),
            ('rekap_kolaborasi', 'logbook_recap().kolaborasi'),
            ('rekap_total', 'logbook_recap().total'),
            ('per_tindakan', 'logbook_recap().per_tindakan'),
            ('dari_tanggal', 'logbook_recap().dari_tanggal'),
        ],
        'manual_fields': [
            ('jenjang_klinis_diusulkan', 'diisi perawat/preseptor: jenjang klinis yang diajukan'),
            ('evaluasi_tahun_1', 'diisi preseptor: evaluasi adaptasi & keterampilan dasar Tahun I'),
            ('evaluasi_tahun_2', 'diisi preseptor: evaluasi kemandirian & kegawatdaruratan Tahun II'),
            ('evaluasi_tahun_3', 'diisi preseptor: evaluasi EBP & bimbingan peer Tahun III'),
            ('catatan_penilaian', 'dinilai dan diisi preseptor/kepala instalasi'),
            ('nama_preseptor', 'diisi nama dan gelar Clinical Preceptor / Mitra Bestari'),
            ('nama_kepala_instalasi', 'diisi nama dan gelar Kepala Instalasi / Ketua KSM'),
        ],
        'signatory_role': 'Kepala Instalasi/Unit',
        'sertifikat_jenis': 'LOGBOOK',
        'sworn_statement': False,
    },
    'PENGANTAR_KSM': {
        'title': 'Surat Pengantar/Rekomendasi KSM',
        'auto_fields': IDENTITY_FIELDS,
        'manual_fields': STATEMENT_FIELDS,
        'signatory_role': 'Ketua KSM/KBM',
        'sertifikat_jenis': 'PENGANTAR_KSM',
        'sworn_statement': False,
    },
    'KEANGGOTAAN': {
        'title': 'Surat Keterangan Keanggotaan Organisasi Profesi',
        'auto_fields': IDENTITY_FIELDS,
        'manual_fields': STATEMENT_FIELDS + [
            ('nama_organisasi', 'diisi pegawai sesuai kartu anggota'),
            ('nomor_anggota', 'diisi pegawai sesuai kartu anggota'),
        ],
        'signatory_role': 'Pegawai yang bersangkutan',
        'sertifikat_jenis': 'KEANGGOTAAN',
        'sworn_statement': True,
    },
    'MALPRACTICE_RECORD': {
        'title': 'Surat Pernyataan Riwayat Malpraktik',
        'auto_fields': IDENTITY_FIELDS,
        'manual_fields': STATEMENT_FIELDS,
        'signatory_role': 'Pegawai yang bersangkutan',
        'sertifikat_jenis': 'MALPRACTICE_RECORD',
        'sworn_statement': True,
    },
    'BEBAS_SANKSI': {
        'title': 'Surat Keterangan Bebas Sanksi Etik',
        'auto_fields': IDENTITY_FIELDS,
        'manual_fields': STATEMENT_FIELDS,
        'signatory_role': 'Ketua Komite Medik/Keperawatan',
        'sertifikat_jenis': 'BEBAS_SANKSI',
        'sworn_statement': True,
    },
    'SEHAT_PSIKOLOGIS': {
        'title': 'Formulir Asesmen Psikologis',
        'auto_fields': IDENTITY_FIELDS,
        'manual_fields': [
            ('nama_psikolog', 'diisi psikolog klinis'),
            ('nomor_sip_psikolog', 'diisi psikolog klinis'),
            ('hasil_asesmen', 'diisi psikolog klinis dari hasil tes'),
        ],
        'signatory_role': 'Psikolog Klinis',
        'sertifikat_jenis': 'PSIKOLOGIS',
        'sworn_statement': False,
    },
}

# Sworn statements are intentionally empty: the signatory writes the claim.
STATEMENT_BODY = (
    'Yang bertanda tangan di bawah ini menyatakan hal-hal berikut. '
    'Bagian pernyataan sengaja dikosongkan dan wajib diisi serta '
    'ditandatangani oleh pihak yang berwenang.'
)
DECLARATION_NOTICE = (
    'PERNYATAAN DIISI DAN DITANDATANGANI OLEH '
    'PENANDA TANGAN, BUKAN OLEH SISTEM'
)


def _today():
    return timezone.localdate()


def _format_tanggal_panjang(tanggal):
    return f'{tanggal.day} {BULAN[tanggal.month - 1]} {tanggal.year}'


def _current_placement(pegawai, *, today=None):
    today = today or _today()
    return (
        PenempatanPegawai.objects.filter(
            pegawai=pegawai,
            unit_kerja__is_active=True,
            tanggal_mulai__lte=today,
        )
        .filter(Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today))
        .select_related('unit_kerja')
        .order_by('-tanggal_mulai', '-pk')
        .first()
    )


def _hospital_name():
    profile = RumahSakitProfile.get_default()
    return profile.name or ''


def auto_fields(pegawai, *, as_of=None):
    """Identity data rendered into every generated document."""
    today = as_of or _today()
    placement = _current_placement(pegawai, today=today)
    unit = placement.unit_kerja if placement is not None else None
    return {
        'nama_lengkap': pegawai.nama_lengkap,
        'nomor_pegawai': pegawai.nomor_pegawai,
        'profesi': pegawai.profesi,
        'jabatan': pegawai.jabatan,
        'unit_kerja': unit.name if unit is not None else '',
        'unit_kerja_kode': unit.code if unit is not None else '',
        'rumah_sakit': _hospital_name(),
        'tanggal_cetak': _format_tanggal_panjang(today),
    }


def _kop_text():
    config = SystemConfig.objects.first()
    kop = (config.kop_surat_text if config is not None else '') or ''
    return [line.strip() for line in kop.splitlines() if line.strip()]


def _styles():
    def style(name, **kw):
        base = dict(
            fontName='Helvetica', fontSize=9, leading=12,
            textColor=colors.HexColor('#0f172a'), alignment=TA_LEFT,
        )
        base.update(kw)
        return ParagraphStyle(name, **base)

    return {
        'kop': style('kop', fontName='Helvetica-Bold', fontSize=11, leading=14,
                     alignment=TA_CENTER),
        'title': style('title', fontName='Helvetica-Bold', fontSize=13, leading=17,
                       alignment=TA_CENTER),
        'body': style('body'),
        'label': style('label', fontName='Helvetica-Bold'),
        'cell': style('cell', fontSize=8, leading=10),
        'cell_title': style('cell_title', fontName='Helvetica-Bold', fontSize=8,
                            leading=10),
        'footnote': style('footnote', fontSize=7.5, leading=9,
                          textColor=colors.HexColor('#64748b')),
    }


def _identity_table(identity, styles, extra_rows=None):
    rows = [
        ('Nama Lengkap', identity['nama_lengkap']),
        ('Nomor Pegawai', identity['nomor_pegawai'] or '-'),
        ('Profesi', identity['profesi'] or '-'),
        ('Jabatan', identity['jabatan'] or '-'),
        ('Unit Kerja', ' '.join(filter(None, [
            identity['unit_kerja'],
            f"({identity['unit_kerja_kode']})" if identity['unit_kerja_kode'] else '',
        ])) or '-'),
        ('Rumah Sakit', identity['rumah_sakit'] or '-'),
    ]
    if extra_rows:
        rows.extend(extra_rows)
    data = [
        [Paragraph(label, styles['label']), Paragraph(f': {value}', styles['body'])]
        for label, value in rows
    ]
    table = Table(data, colWidths=[45 * mm, 115 * mm])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return table


def _logbook_tables(employee, styles):
    """Realization columns from logbook_recap(); target stays an empty cell."""
    recap = logbook_recap(employee)
    summary = Table([
        [Paragraph('<b>Mandiri</b>', styles['cell_title']),
         Paragraph('<b>Supervisi</b>', styles['cell_title']),
         Paragraph('<b>Kolaborasi</b>', styles['cell_title']),
         Paragraph('<b>Total</b>', styles['cell_title'])],
        [Paragraph(str(recap['mandiri']), styles['cell']),
         Paragraph(str(recap['supervisi']), styles['cell']),
         Paragraph(str(recap['kolaborasi']), styles['cell']),
         Paragraph(str(recap['total']), styles['cell'])],
    ], colWidths=[40 * mm] * 4)
    summary.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#64748b')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))

    rows = [[
        Paragraph('Kompetensi / Tindakan', styles['cell_title']),
        Paragraph('Target 3 tahun', styles['cell_title']),
        Paragraph('Realisasi', styles['cell_title']),
        Paragraph('Status', styles['cell_title']),
    ]]
    for item in recap['per_tindakan']:
        realization = item['mandiri'] + item['supervisi'] + item['kolaborasi']
        # Target and status stay blank: the target matrix is not configured.
        rows.append([
            Paragraph(item['label'], styles['cell']),
            Paragraph('', styles['cell']),
            Paragraph(str(realization), styles['cell']),
            Paragraph('', styles['cell']),
        ])
    table = Table(rows, colWidths=[70 * mm, 30 * mm, 30 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#64748b')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    return summary, table, recap


def _signature_block(role, styles):
    return [
        Spacer(1, 10 * mm),
        Table(
            [[Paragraph(f'Penanda tangan: {role}', styles['label'])],
             [Paragraph('Nama dan tanda tangan: '
                        '........................................................',
                        styles['body'])],
             [Paragraph('Tanggal: ......................................',
                        styles['body'])]],
            colWidths=[100 * mm],
            style=TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 0),
            ]),
        ),
    ]


def _manual_answers(draf):
    return {
        key: value for key, value in (draf.isian or {}).items()
        if isinstance(value, str) and value.strip()
    }


def render_pdf(draf):
    """Render one draft to PDF bytes. Never fills a claim it cannot verify."""
    spec = REGISTRY.get(draf.jenis)
    if spec is None:
        raise ValidationError({'jenis': 'Jenis dokumen tidak dapat digenerate.'})
    employee = draf.pegawai
    identity = auto_fields(employee)
    styles = _styles()
    story = []

    for line in _kop_text():
        story.append(Paragraph(line, styles['kop']))
    story.append(HRFlowable(width='100%', thickness=1, color=colors.HexColor('#64748b'),
                            spaceBefore=2, spaceAfter=6))
    story.append(Paragraph(spec['title'], styles['title']))
    story.append(Paragraph(
        f"Dicetak: {identity['tanggal_cetak']}", styles['footnote'],
    ))
    story.append(Spacer(1, 6 * mm))

    answers = _manual_answers(draf)
    extra_rows = []
    if draf.jenis == 'LOGBOOK_36BULAN' and answers.get('jenjang_klinis_diusulkan'):
        extra_rows.append(('Jenjang Klinis Diusulkan', answers['jenjang_klinis_diusulkan']))

    story.append(Paragraph('Identitas', styles['label']))
    story.append(Spacer(1, 2 * mm))
    story.append(_identity_table(identity, styles, extra_rows=extra_rows))
    story.append(Spacer(1, 6 * mm))

    if draf.jenis == 'LOGBOOK_36BULAN':
        summary, detail, recap = _logbook_tables(employee, styles)
        story.append(Paragraph('Rekap Tindakan', styles['label']))
        story.append(Spacer(1, 2 * mm))
        story.append(summary)
        story.append(Spacer(1, 4 * mm))
        story.append(detail)
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(
            'Catatan: matriks target tindakan per kompetensi belum dikonfigurasi, '
            'sehingga kolom Target 3 tahun dan Status sengaja dikosongkan. '
            f"Rekap dihitung dari {_format_tanggal_panjang(recap['dari_tanggal'])} "
            'sampai tanggal cetak.',
            styles['footnote'],
        ))
        story.append(Spacer(1, 4 * mm))

        # Evaluasi Siklus Berkala
        eval_t1 = answers.get('evaluasi_tahun_1')
        eval_t2 = answers.get('evaluasi_tahun_2')
        eval_t3 = answers.get('evaluasi_tahun_3')
        if eval_t1 or eval_t2 or eval_t3:
            story.append(Paragraph('Catatan Evaluasi Siklus Berkala (36 Bulan)', styles['label']))
            story.append(Spacer(1, 2 * mm))
            eval_rows = []
            if eval_t1:
                eval_rows.append([
                    Paragraph('<b>Tahun I (Bulan 1–12)</b><br/><font color="#64748b" size="7.5">Adaptasi & Dasar</font>', styles['cell']),
                    Paragraph(eval_t1, styles['body']),
                ])
            if eval_t2:
                eval_rows.append([
                    Paragraph('<b>Tahun II (Bulan 13–24)</b><br/><font color="#64748b" size="7.5">Kemandirian & Kasus</font>', styles['cell']),
                    Paragraph(eval_t2, styles['body']),
                ])
            if eval_t3:
                eval_rows.append([
                    Paragraph('<b>Tahun III (Bulan 25–36)</b><br/><font color="#64748b" size="7.5">EBP & Mutu</font>', styles['cell']),
                    Paragraph(eval_t3, styles['body']),
                ])
            eval_table = Table(eval_rows, colWidths=[45 * mm, 115 * mm])
            eval_table.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#64748b')),
                ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f8fafc')),
                ('TOPPADDING', (0, 0), (-1, -1), 3),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ]))
            story.append(eval_table)
            story.append(Spacer(1, 4 * mm))

        if 'catatan_penilaian' in answers:
            story.append(Spacer(1, 2 * mm))
            story.append(Paragraph(f'<b>Catatan Penilaian:</b> {answers["catatan_penilaian"]}', styles['body']))

        # Tanda Tangan Validasi 3 Pihak
        preseptor = answers.get('nama_preseptor') or '........................................................'
        kepala = answers.get('nama_kepala_instalasi') or '........................................................'
        story.append(Spacer(1, 6 * mm))
        sig_data = [
            [Paragraph('<b>Perawat Pemohon</b>', styles['cell_title']),
             Paragraph('<b>Clinical Preceptor / Mitra Bestari</b>', styles['cell_title']),
             Paragraph('<b>Kepala Instalasi / KSM</b>', styles['cell_title'])],
            [Spacer(1, 12 * mm), Spacer(1, 12 * mm), Spacer(1, 12 * mm)],
            [Paragraph(employee.nama_lengkap, styles['cell']),
             Paragraph(preseptor, styles['cell']),
             Paragraph(kepala, styles['cell'])],
            [Paragraph(f'NIP: {employee.nomor_pegawai or "-"}', styles['footnote']),
             Paragraph('Tanda Tangan & Cap', styles['footnote']),
             Paragraph('Tanda Tangan & Cap', styles['footnote'])],
        ]
        sig_table = Table(sig_data, colWidths=[53 * mm, 54 * mm, 53 * mm])
        sig_table.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ]))
        story.append(sig_table)

    elif spec['sworn_statement']:
        story.append(Paragraph(DECLARATION_NOTICE, styles['label']))
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(STATEMENT_BODY, styles['body']))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph('Pernyataan:', styles['label']))
        for _ in range(4):
            story.append(Paragraph(
                '................................................................'
                '........................................................',
                styles['body'],
            ))

        for key, _source in spec['manual_fields']:
            if key not in answers:
                continue
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(f'{key.replace("_", " ").title()}: {answers[key]}',
                                   styles['body']))

        story.extend(_signature_block(spec['signatory_role'], styles))

    else:
        for key, _source in spec['manual_fields']:
            if key not in answers:
                continue
            story.append(Spacer(1, 3 * mm))
            story.append(Paragraph(f'{key.replace("_", " ").title()}: {answers[key]}',
                                   styles['body']))

        story.extend(_signature_block(spec['signatory_role'], styles))

    buffer = BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=spec['title'],
        author=identity['rumah_sakit'] or '',
    )
    document.build(story)
    return buffer.getvalue()


def generate_draft(pegawai, jenis, *, user):
    """Create or refresh the single draft for one employee and document type."""
    if jenis not in REGISTRY:
        raise ValidationError({'jenis': 'Jenis dokumen tidak dapat digenerate.'})
    draft, _created = DrafDokumenKredensial.objects.get_or_create(
        pegawai=pegawai,
        jenis=jenis,
        defaults={'created_by': user, 'isian': {}},
    )
    if draft.created_by_id is None and user is not None:
        draft.created_by = user
        draft.save(update_fields=['created_by', 'updated_at'])
    return draft


def finalize(draf, *, user):
    """Render the draft and store it as a PENDING document version.

    Regeneration reuses the employee's existing generated document for this
    kind, so consecutive finalizes extend one document's version history
    instead of piling up duplicates. ``store_document_version`` supersedes
    the previous versions itself.
    """
    pdf = render_pdf(draf)
    spec = REGISTRY[draf.jenis]
    employee = draf.pegawai

    with transaction.atomic():
        document = (
            DokumenPegawai.objects.select_for_update()
            .filter(
                employee=employee,
                document_type='CREDENTIAL',
                jenis_berkas=spec['sertifikat_jenis'],
            )
            .exclude(versions__status='SUPERSEDED')
            .distinct()
            .order_by('-created_at', '-pk')
            .first()
        )
        if document is None:
            document = DokumenPegawai.objects.create(
                employee=employee,
                document_type='CREDENTIAL',
                jenis_berkas=spec['sertifikat_jenis'],
                title=spec['title'],
                sensitivity='personnel',
                created_by=user,
            )
        upload = BytesIO(pdf)
        upload.name = f'{draf.jenis.lower()}-{employee.pk}.pdf'
        upload.content_type = 'application/pdf'
        version = store_document_version(upload, document=document, uploaded_by=user)
        draf.versi_dokumen = version
        draf.status = 'FINAL'
        draf.save(update_fields=['versi_dokumen', 'status', 'updated_at'])

    return version


__all__ = [
    'REGISTRY',
    'auto_fields',
    'finalize',
    'generate_draft',
    'render_pdf',
]
