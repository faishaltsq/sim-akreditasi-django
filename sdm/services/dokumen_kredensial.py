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
from sdm.services.logbook import logbook_recap, logbook_recap_5tahun
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
    'LOGBOOK_5TAHUN': {
        'title': 'Buku Kinerja Elektronik (Logbook 5 Tahunan)',
        'auto_fields': IDENTITY_FIELDS + [
            ('periode_siklus', 'diisi periode siklus 5 tahun'),
            ('rekap_5tahun', 'logbook_recap_5tahun()'),
        ],
        'manual_fields': [
            ('periode_siklus', 'diisi periode tahun (misal: 2021 s.d. 2026)'),
            ('jenjang_klinis_usulan', 'jenjang klinis yang diusulkan 5 tahun ke depan'),
            ('skp_pelayanan', 'Ranah 2: target & capaian SKP pelayanan langsung'),
            ('skp_pelatihan', 'Ranah 2: target & capaian SKP pelatihan & fellowship'),
            ('skp_seminar', 'Ranah 2: target & capaian SKP seminar/workshop/mentoring'),
            ('skp_publikasi', 'Ranah 2: target & capaian SKP publikasi ilmiah & inovasi'),
            ('target_skp_dirjen', 'Ranah 2: target total SKP Direktur Jenderal'),
            ('total_skp_diperoleh', 'Ranah 2: total akumulasi perolehan SKP 5 tahun'),
            ('etik_perundungan_t1', 'Ranah 3: Tahun 1 etik, disiplin & bebas perundungan'),
            ('etik_perundungan_t2', 'Ranah 3: Tahun 2 etik, disiplin & bebas perundungan'),
            ('etik_perundungan_t3', 'Ranah 3: Tahun 3 etik, disiplin & bebas perundungan'),
            ('etik_perundungan_t4', 'Ranah 3: Tahun 4 etik, disiplin & bebas perundungan'),
            ('etik_perundungan_t5', 'Ranah 3: Tahun 5 etik, disiplin & bebas perundungan'),
            ('checklist_kualifikasi_str_sip', 'Pasal 180: kualifikasi pendidikan, STR & SIP (MS/TMS)'),
            ('checklist_target_volume_pelayanan', 'Pasal 180: pemenuhan target volume pelayanan (MS/TMS)'),
            ('checklist_kecukupan_skp', 'Pasal 180: kecukupan Satuan Kredit Profesi (MS/TMS)'),
            ('checklist_kesehatan_fisik_mental', 'Pasal 180: kesehatan fisik dan mental (MS/TMS)'),
            ('checklist_etik_disiplin_perundungan', 'Pasal 180: etik, disiplin & bebas perundungan (MS/TMS)'),
            ('rekomendasi_tim_adhoc', 'Pasal 180: DIKABULKAN SEPENUHNYA / DIKABULKAN DENGAN PEMBATASAN / PENAMBAHAN KOMPETENSI'),
            ('catatan_rekomendasi_adhoc', 'Pasal 180: catatan rincian rekomendasi Tim Ad Hoc'),
            ('nama_ketua_tim_adhoc', 'diisi nama dan gelar Ketua Tim Ad Hoc Kredensial'),
            ('nip_ketua_tim_adhoc', 'diisi NIP/NUTR Ketua Tim Ad Hoc Kredensial'),
            ('nama_pimpinan_fasyankes', 'diisi nama dan gelar Direktur RS / Pimpinan Fasyankes'),
        ],
        'signatory_role': 'Tim Ad Hoc Kredensial & Direktur RS',
        'sertifikat_jenis': 'LOGBOOK',
        'sworn_statement': False,
        # Pengelompokan isian manual mengikuti 4 bagian Buku Kinerja
        # Elektronik PMK 13/2025, supaya editor tidak menyajikan 23 field
        # sebagai satu daftar datar.
        'field_groups': [
            ('periode', 'Bagian I — Profil & Periode Siklus', [
                'periode_siklus', 'jenjang_klinis_usulan',
            ]),
            ('skp', 'Bagian II Ranah 2 — Pengembangan Profesi Berkelanjutan', [
                'skp_pelayanan', 'skp_pelatihan', 'skp_seminar',
                'skp_publikasi', 'target_skp_dirjen', 'total_skp_diperoleh',
            ]),
            ('etik', 'Bagian II Ranah 3 — Etik, Disiplin & Bebas Perundungan', [
                'etik_perundungan_t1', 'etik_perundungan_t2',
                'etik_perundungan_t3', 'etik_perundungan_t4',
                'etik_perundungan_t5',
            ]),
            ('adhoc', 'Bagian III — Rekapitulasi & Penilaian Rekredensial (Pasal 180)', [
                'checklist_kualifikasi_str_sip',
                'checklist_target_volume_pelayanan',
                'checklist_kecukupan_skp',
                'checklist_kesehatan_fisik_mental',
                'checklist_etik_disiplin_perundungan',
                'rekomendasi_tim_adhoc',
                'catatan_rekomendasi_adhoc',
            ]),
            ('tanda_tangan', 'Bagian IV — Otentikasi & Tanda Tangan', [
                'nama_ketua_tim_adhoc', 'nip_ketua_tim_adhoc',
                'nama_pimpinan_fasyankes',
            ]),
        ],
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


# --- Buku Kinerja Elektronik (PMK 13/2025) -----------------------------------

RANAH_2_LABELS = [
    ('skp_pelayanan', 'Pelayanan Langsung / Kewenangan Klinis'),
    ('skp_pelatihan', 'Pelatihan & Fellowship Terakreditasi'),
    ('skp_seminar', 'Seminar / Workshop / Mentoring'),
    ('skp_publikasi', 'Publikasi Ilmiah & Inovasi IPTEK'),
]

CHECKLIST_PASAL_180 = [
    ('checklist_kualifikasi_str_sip', 'Kualifikasi pendidikan, STR & SIP'),
    ('checklist_target_volume_pelayanan', 'Pemenuhan target volume pelayanan'),
    ('checklist_kecukupan_skp', 'Kecukupan Satuan Kredit Profesi (SKP)'),
    ('checklist_kesehatan_fisik_mental', 'Kesehatan fisik dan mental'),
    ('checklist_etik_disiplin_perundungan', 'Etik, disiplin & bebas perundungan'),
]

REKOMENDASI_CHOICES = (
    'DIKABULKAN SEPENUHNYA',
    'DIKABULKAN DENGAN PEMBATASAN',
    'PENAMBAHAN KOMPETENSI',
)

BELUM_DINILAI = 'BELUM DINILAI'


def _boxed_table(rows, col_widths, styles, *, first_row_header=True):
    table = Table(rows, colWidths=col_widths)
    style = [
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#64748b')),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, colors.HexColor('#e2e8f0')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]
    if first_row_header:
        style.append(('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f1f5f9')))
    table.setStyle(TableStyle(style))
    return table


def _section_heading(number, title, styles):
    return Paragraph(
        f'<b>BAGIAN {number}. {title.upper()}</b>', styles['label'],
    )


def _ranah1_matrix(employee, styles, years=5):
    """Ranah 1: volume dan jenis pelayanan / tindakan keprofesian 10-kolom PMK 13/2025."""
    recap = logbook_recap_5tahun(employee, years=years)
    labels = recap['tahun_labels']
    header = [
        Paragraph('<b>No</b>', styles['cell_title']),
        Paragraph('<b>Jenis Tindakan Keprofesian</b>', styles['cell_title']),
        Paragraph('<b>Kode Standar</b>', styles['cell_title']),
    ]
    header += [Paragraph(f'<b>{label}</b>', styles['cell_title']) for label in labels]
    header += [
        Paragraph('<b>Total 5 Thn</b>', styles['cell_title']),
        Paragraph('<b>Status Verifikasi</b>', styles['cell_title']),
    ]
    rows = [header]
    for idx, item in enumerate(recap['per_tindakan'], start=1):
        row = [
            Paragraph(str(idx), styles['cell']),
            Paragraph(item['label'], styles['cell']),
            Paragraph(item.get('kode', '-'), styles['cell']),
        ]
        row += [Paragraph(str(v) or '0', styles['cell']) for v in item['tahunan']]
        row += [
            Paragraph(str(item['total']), styles['cell']),
            Paragraph(item.get('status_verifikasi', 'Menunggu'), styles['cell']),
        ]
        rows.append(row)

    total_row = [
        Paragraph('', styles['cell_title']),
        Paragraph('<b>Total Tindakan Klinis</b>', styles['cell_title']),
        Paragraph('-', styles['cell_title']),
    ]
    total_row += [Paragraph(f'<b>{v}</b>', styles['cell_title']) for v in recap['tahunan']]
    total_row += [
        Paragraph(f"<b>{recap['total_5tahun']}</b>", styles['cell_title']),
        Paragraph(
            f"<b>{recap['terverifikasi']}/{recap['total_5tahun']} Valid</b>"
            if recap['total_5tahun'] else '<b>-</b>',
            styles['cell_title'],
        ),
    ]
    rows.append(total_row)

    widths = [8 * mm, 44 * mm, 20 * mm] + [12 * mm] * years + [16 * mm, 22 * mm]
    return _boxed_table(rows, widths, styles), recap


def _ranah2_table(answers, styles):
    """Ranah 2: kecukupan SKP 4 kategori pengembangan profesi berkelanjutan."""
    rows = [[
        Paragraph('<b>Kategori Pengembangan Profesi</b>', styles['cell_title']),
        Paragraph('<b>Target &amp; Capaian SKP</b>', styles['cell_title']),
    ]]
    for key, label in RANAH_2_LABELS:
        rows.append([
            Paragraph(label, styles['cell']),
            Paragraph(answers.get(key, BELUM_DINILAI), styles['cell']),
        ])
    rows.append([
        Paragraph('<b>Target SKP Direktur Jenderal</b>', styles['cell_title']),
        Paragraph(f"<b>{answers.get('target_skp_dirjen', BELUM_DINILAI)}</b>",
                  styles['cell_title']),
    ])
    rows.append([
        Paragraph('<b>Total SKP Diperoleh</b>', styles['cell_title']),
        Paragraph(f"<b>{answers.get('total_skp_diperoleh', BELUM_DINILAI)}</b>",
                  styles['cell_title']),
    ])
    return _boxed_table(rows, [70 * mm, 90 * mm], styles)


def _ranah3_table(answers, styles):
    """Ranah 3: disiplin, etik, dan rekam jejak bebas perundungan per tahun."""
    rows = [[
        Paragraph('<b>Tahun</b>', styles['cell_title']),
        Paragraph('<b>Etik, Disiplin &amp; Bebas Perundungan</b>', styles['cell_title']),
    ]]
    for index in range(1, 6):
        rows.append([
            Paragraph(f'Tahun {index}', styles['cell']),
            Paragraph(
                answers.get(f'etik_perundungan_t{index}', BELUM_DINILAI),
                styles['cell'],
            ),
        ])
    return _boxed_table(rows, [25 * mm, 135 * mm], styles)


def _pasal180_table(answers, styles):
    """Pasal 180: checklist penilaian 5 aspek dan rekomendasi Tim Ad Hoc."""
    rows = [[
        Paragraph('<b>Aspek Penilaian Rekredensial</b>', styles['cell_title']),
        Paragraph('<b>Hasil</b>', styles['cell_title']),
    ]]
    for key, label in CHECKLIST_PASAL_180:
        rows.append([
            Paragraph(label, styles['cell']),
            Paragraph(answers.get(key, BELUM_DINILAI), styles['cell']),
        ])
    table = _boxed_table(rows, [115 * mm, 45 * mm], styles)

    rekomendasi = answers.get('rekomendasi_tim_adhoc', '').strip().upper()
    if not rekomendasi:
        rekomendasi = BELUM_DINILAI
    rows_rekomendasi = [[
        Paragraph('<b>Rekomendasi Tim Ad Hoc</b>', styles['cell_title']),
        Paragraph(f'<b>{rekomendasi}</b>', styles['cell_title']),
    ]]
    catatan = answers.get('catatan_rekomendasi_adhoc')
    if catatan:
        rows_rekomendasi.append([
            Paragraph('Catatan rincian rekomendasi', styles['cell']),
            Paragraph(catatan, styles['cell']),
        ])
    rekomendasi_table = _boxed_table(
        rows_rekomendasi, [70 * mm, 90 * mm], styles,
    )
    return table, rekomendasi_table


def _signature_three_parties(employee, answers, styles):
    """Bagian IV: tanda tangan elektronik tiga pihak + segel digital SATUSEHAT."""
    pemohon = employee.nama_lengkap
    ketua = answers.get('nama_ketua_tim_adhoc') or '........................................................'
    direktur = answers.get('nama_pimpinan_fasyankes') or '........................................................'
    nip_ketua = answers.get('nip_ketua_tim_adhoc') or '-'
    id_sdmk = auto_fields(employee).get('id_sdmk') or '-'
    rows = [
        [Paragraph('<b>SDMK Pemohon</b>', styles['cell_title']),
         Paragraph('<b>Pendamping / Ketua Tim Ad Hoc</b>', styles['cell_title']),
         Paragraph('<b>Direktur RS / Pimpinan Fasyankes</b>', styles['cell_title'])],
        [Spacer(1, 14 * mm), Spacer(1, 14 * mm), Spacer(1, 14 * mm)],
        [Paragraph(pemohon, styles['cell']),
         Paragraph(ketua, styles['cell']),
         Paragraph(direktur, styles['cell'])],
        [Paragraph(f'NIP: {employee.nomor_pegawai or "-"}<br/>'
                   f'ID SDMK: {id_sdmk}', styles['footnote']),
         Paragraph(f'NIP/NUTR: {nip_ketua}', styles['footnote']),
         Paragraph('Tanda Tangan Elektronik &amp; Cap RS', styles['footnote'])],
    ]
    table = Table(rows, colWidths=[53 * mm, 54 * mm, 53 * mm])
    table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
    ]))
    return table


def _build_logbook_5tahun_story(story, draf, employee, identity, answers, styles):
    """4 bagian Buku Kinerja Elektronik: profil, capaian 3 ranah, penilaian, otentikasi."""
    # Bagian I - Profil SDMK
    extra_rows = [
        ('ID SDMK / SATUSEHAT', identity.get('id_sdmk') or '-'),
        ('Periode Siklus', answers.get('periode_siklus') or BELUM_DINILAI),
        ('Jenjang Klinis Diusulkan', answers.get('jenjang_klinis_usulan') or BELUM_DINILAI),
    ]
    story.append(_section_heading('I', 'Profil SDMK', styles))
    story.append(Spacer(1, 2 * mm))
    story.append(_identity_table(identity, styles, extra_rows=extra_rows))
    story.append(Spacer(1, 6 * mm))

    # Bagian II - Rencana & Capaian 3 Ranah
    story.append(_section_heading('II', 'Rencana & Capaian Tiga Ranah', styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        '<b>Ranah 1 — Pelayanan / Kewenangan Klinis</b> '
        '<font color="#64748b" size="7.5">(volume tindakan per tahun, mandiri vs pelimpahan)</font>',
        styles['body'],
    ))
    story.append(Spacer(1, 2 * mm))
    matrix, recap = _ranah1_matrix(employee, styles)
    story.append(matrix)
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        f"Total {recap['total_5tahun']} tindakan dalam window 5 tahun "
        f"({recap['terverifikasi']} terverifikasi).",
        styles['footnote'],
    ))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        '<b>Ranah 2 — Pengembangan Profesi Berkelanjutan (SKP)</b>', styles['body'],
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(_ranah2_table(answers, styles))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph(
        '<b>Ranah 3 — Disiplin, Etik &amp; Bebas Perundungan</b>', styles['body'],
    ))
    story.append(Spacer(1, 2 * mm))
    story.append(_ranah3_table(answers, styles))
    story.append(Spacer(1, 6 * mm))

    # Bagian III - Lembar Rekapitulasi & Penilaian Rekredensial
    story.append(_section_heading('III', 'Rekapitulasi & Penilaian Rekredensial', styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        '<font color="#64748b" size="7.5">Dasar: Pasal 180 — penilaian 5 aspek '
        'dengan 3 kemungkinan rekomendasi.</font>',
        styles['body'],
    ))
    story.append(Spacer(1, 2 * mm))
    checklist_table, rekomendasi_table = _pasal180_table(answers, styles)
    story.append(checklist_table)
    story.append(Spacer(1, 3 * mm))
    story.append(rekomendasi_table)
    story.append(Spacer(1, 6 * mm))

    # Bagian IV - Shield & Otentikasi Digital
    story.append(_section_heading('IV', 'Otentikasi Digital & Pengesahan', styles))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        'Dokumen ini disahkan melalui tanda tangan elektronik tiga pihak dan '
        'diverifikasi terhadap <b>SATUSEHAT ID SDMK</b>.',
        styles['body'],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(_signature_three_parties(employee, answers, styles))


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
    if draf.jenis == 'LOGBOOK_5TAHUN':
        story.append(Paragraph(
            'Peraturan Menteri Kesehatan Nomor 13 Tahun 2025 tentang '
            'Pengelolaan Sumber Daya Manusia Kesehatan',
            styles['footnote'],
        ))
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

    elif draf.jenis == 'LOGBOOK_5TAHUN':
        _build_logbook_5tahun_story(story, draf, employee, identity, answers, styles)

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
