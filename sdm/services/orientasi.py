"""Level 2 orientation workflows: type matrix, auto-assign, assessments."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from sdm.models import (
    PeristiwaSDM,
    PenugasanOrientasi,
    PenyelesaianOrientasi,
    ProgramOrientasi,
)
from sdm.services.rekrutmen import start_orientation

# Matriks durasi baku (hari) dari "Bab Modul Orientasi Staf.docx",
# tabel 3. Umum = 3 hari semua kelompok; khusus per kelompok staf.
DURASI_UMUM_HARI = 3
DURASI_KHUSUS_HARI = {
    'MEDIS': 28,          # 2-4 minggu; pakai batas bawah? lihat ponytail di bawah
    'KEPERAWATAN': 90,    # 1-3 bulan -> pakai batas atas (dampak keselamatan)
    'NAKES_LAIN': 28,     # 2-4 minggu
    'NON_KLINIS': 14,     # 1-2 minggu
}
KELOMPOK_DARI_KATEGORI = {
    'PPA': None,  # ditentukan profesi, bukan kategori — lihat resolve_kelompok
}

# ponytail: batas atas matriks yang dipilih (90/28/14) supaya tenggat konservatif;
# SK mengatur ulang -> ubah hanya dict ini.
from sdm.models.orientasi import PASSING_GRADE  # noqa: F401  (re-export)


def resolve_kelompok(pegawai):
    """Kelompok staf dari master profesi (fallback kategori)."""
    keluarga = getattr(getattr(pegawai, 'profesi_master', None), 'keluarga', '')
    if keluarga == 'MEDIS':
        return 'MEDIS'
    if keluarga == 'KEPERAWATAN_KEBIDANAN':
        return 'KEPERAWATAN'
    if keluarga == 'NAKES_LAIN':
        return 'NAKES_LAIN'
    return 'NON_KLINIS'


# Program baku KPS 4 & KPS 8 (aktivitas dari dokumen Modul Orientasi Staf).
PROGRAM_BAKU_UMUM = [
    ('Profil, tata kelola & Hospital Bylaws', True),
    ('PMKP & 6 Sasaran Keselamatan Pasien (SKP 1–6) + pelaporan IKP', True),
    ('PPI: hand hygiene, APD, etika batuk, limbah medis/B3', True),
    ('K3RS & code darurat (Red/Blue/Pink/Black) + APAR', True),
    ('Bantuan Hidup Dasar (BHD)', True),
]
PROGRAM_BAKU_KHUSUS = {
    'MEDIS': [
        ('Batas RKK & Penugasan Klinis (SPK)', True),
        ('Alur konsultasi, DPJP utama & CPPT', True),
        ('Clinical pathways unit', True),
    ],
    'KEPERAWATAN': [
        ('Alur kerja ruangan & handover SBAR; koding RME', True),
        ('Pengoperasian alat medis unit (infuse/syringe pump, monitor, defibrilator)', True),
        ('Logbook harian masa orientasi dengan preseptor', True),
    ],
    'NAKES_LAIN': [
        ('SOP teknis profesi unit', True),
        ('Pengelolaan bahan berbahaya & spesimen/hasil kritis', True),
    ],
    'NON_KLINIS': [
        ('Service excellence & alur rekam medis', True),
        ('Operasional modul ARIMA unit', True),
    ],
}


def seed_program_baku():
    """Idempotent: Orientasi Umum + 4 program khusus per kelompok staf."""
    dibuat = 0
    program, created = ProgramOrientasi.objects.get_or_create(
        nama='Orientasi Umum Rumah Sakit',
        defaults={
            'jenis': 'UMUM', 'kelompok_staf': '',
            'durasi_hari': DURASI_UMUM_HARI,
        },
    )
    dibuat += int(created)
    _ensure_activities(program, PROGRAM_BAKU_UMUM)
    for kelompok, aktivitas in PROGRAM_BAKU_KHUSUS.items():
        program, created = ProgramOrientasi.objects.get_or_create(
            nama=f'Orientasi Khusus — {kelompok}',
            defaults={
                'jenis': 'KHUSUS', 'kelompok_staf': kelompok,
                'durasi_hari': DURASI_KHUSUS_HARI[kelompok],
            },
        )
        dibuat += int(created)
        _ensure_activities(program, aktivitas)
    return dibuat


def _ensure_activities(program, aktivitas):
    urutan = program.activities.count()
    ada = set(program.activities.values_list('nama', flat=True))
    for nama, wajib in aktivitas:
        if nama not in ada:
            program.activities.create(nama=nama, wajib=wajib, urutan=urutan)
            urutan += 1


def auto_assign_orientation(pegawai, *, actor, unit_kerja=None):
    """Assign umum + khusus programs for one pegawai; idempotent per (jenis+unit).

    Returns the list of newly created assignments. Existing BERJALAN
    assignments for the same program & unit are never duplicated.
    """
    kelompok = resolve_kelompok(pegawai)
    unit = unit_kerja or _unit_utama(pegawai)
    programs = list(
        ProgramOrientasi.objects.filter(
            is_active=True, jenis='UMUM',
        ) | ProgramOrientasi.objects.filter(
            is_active=True, jenis='KHUSUS',
        ).filter(Q(kelompok_staf=kelompok) | Q(kelompok_staf=''))
    )
    hasil = []
    for program in programs:
        if program.kelompok_staf and program.kelompok_staf != kelompok:
            continue
        if PenugasanOrientasi.objects.filter(
            employee=pegawai, program=program,
            status='BERJALAN', unit_kerja=unit,
        ).exists():
            continue
        hasil.append(_start_for_actor(
            employee=pegawai, program=program, actor=actor, unit_kerja=unit,
        ))
    return hasil


def _start_for_actor(*, employee, program, actor, unit_kerja):
    """start_orientation tanpa re-cek capability orientation (pemanggil
    auto-assign sudah lolos gate intake/penempatan); tetap menulis audit."""
    if not program.activities.exists():
        raise ValidationError({'program': 'Program belum memiliki aktivitas.'})
    tenggat = timezone.localdate() + timedelta(
        days=program.durasi_hari or program.berlaku_hari
    )
    assignment = PenugasanOrientasi.objects.create(
        employee=employee, program=program, unit_kerja=unit_kerja,
        tenggat=tenggat,
    )
    for activity in program.activities.all():
        PenyelesaianOrientasi.objects.create(
            assignment=assignment, activity=activity, selesai=False,
        )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='orientation_started',
        target_tipe='orientation_assignment',
        target_id=str(assignment.pk),
        status_sesudah='BERJALAN',
        alasan=f'program={program.pk} auto_assign=1',
    )
    return assignment


def _unit_utama(pegawai):
    from sdm.models import PenempatanPegawai
    placement = PenempatanPegawai.objects.filter(
        pegawai=pegawai, tanggal_selesai__isnull=True,
    ).order_by('alokasi_fte').first()
    return getattr(placement, 'unit_kerja', None)



def record_assessment(assignment, *, nilai, penguji, catatan=''):
    """Append one post-test score; failure flags remedial & extends deadline.

    Lulus + semua aktivitas wajib selesai -> assignment SELESAI + audit.
    """
    from sdm.models.orientasi import AsesmenOrientasi, PASSING_GRADE

    if assignment.status != 'BERJALAN':
        raise ValidationError({'assignment': 'Penugasan tidak sedang berjalan.'})
    with transaction.atomic():
        asesmen = AsesmenOrientasi(
            assignment=assignment, nilai=nilai,
            penguji=penguji, catatan=catatan or '',
        )
        asesmen._prep()
        asesmen.full_clean()
        asesmen.save()
        if asesmen.lulus:
            _maybe_complete(assignment, actor=penguji)
        else:
            # Remedial: perpanjang tenggat satu siklus durasi program.
            assignment.tenggat = timezone.localdate() + timedelta(
                days=assignment.program.durasi_hari or assignment.program.berlaku_hari
            )
            assignment.save(update_fields=['tenggat'])
    PeristiwaSDM.objects.create(
        actor=penguji,
        jenis_peristiwa='orientation_assessed',
        target_tipe='orientation_assignment',
        target_id=str(assignment.pk),
        status_sesudah='LULUS' if asesmen.lulus else 'REMEDI',
        alasan=f'percobaan={asesmen.percobaan} nilai={asesmen.nilai}',
    )
    return asesmen


def _maybe_complete(assignment, *, actor):
    """Mark SELESAI when all mandatory activities are done and latest
    assessment passed; safe to call repeatedly."""
    kurang = assignment.completions.filter(
        selesai=False, activity__wajib=True,
    ).exists()
    if kurang:
        return False
    from sdm.models.orientasi import AsesmenOrientasi
    terakhir = assignment.assessments.order_by('-percobaan').first()
    if terakhir is None or not terakhir.lulus:
        return False
    if assignment.status != 'SELESAI':
        assignment.status = 'SELESAI'
        assignment.save(update_fields=['status'])
        PeristiwaSDM.objects.create(
            actor=actor,
            jenis_peristiwa='orientation_completed',
            target_tipe='orientation_assignment',
            target_id=str(assignment.pk),
            status_sesudah='SELESAI',
            alasan=f'asesmen#{terakhir.percobaan} lulus',
        )
    return True


# ── O4: PDF sertifikat & TOR ──────────────────────────────────────────

def _pdf_kop(story, styles):
    from akreditasi.system_models import SystemConfig
    config = SystemConfig.objects.first()
    kop = (config.kop_surat_text if config is not None else '') or ''
    from reportlab.platypus import HRFlowable, Paragraph
    from reportlab.lib import colors as rl_colors
    for line in [x.strip() for x in kop.splitlines() if x.strip()]:
        story.append(Paragraph(line, styles['kop']))
    story.append(HRFlowable(
        width='100%', thickness=1, color=rl_colors.HexColor('#64748b'),
        spaceBefore=2, spaceAfter=6,
    ))


def _pdf_styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.enums import TA_CENTER

    def style(name, **kw):
        base = dict(
            fontName='Helvetica', fontSize=9, leading=12,
            textColor=rl_colors.HexColor('#0f172a'),
        )
        base.update(kw)
        return ParagraphStyle(name, **base)

    return {
        'kop': style('kop', fontName='Helvetica-Bold', fontSize=11,
                     leading=14, alignment=TA_CENTER),
        'title': style('title', fontName='Helvetica-Bold', fontSize=13,
                       leading=17, alignment=TA_CENTER),
        'body': style('body'),
        'label': style('label', fontName='Helvetica-Bold', fontSize=9,
                       spaceBefore=6),
        'footnote': style('footnote', fontSize=8, textColor=rl_colors.HexColor('#475569')),
    }


def render_sertifikat_pdf(assignment):
    """Certificate PDF for one PASSED orientation assignment."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    if assignment.status != 'SELESAI':
        raise ValidationError({
            'assignment': 'Sertifikat hanya terbit untuk orientasi selesai.',
        })
    terakhir = assignment.assessments.order_by('-percobaan').first()
    styles = _pdf_styles()
    story = []
    _pdf_kop(story, styles)
    story.append(Paragraph('SERTIFIKAT ORIENTASI STAF', styles['title']))
    story.append(Spacer(1, 5 * mm))
    pegawai = assignment.employee
    story.append(Paragraph(
        f"Yang bersangkutan: <b>{pegawai.nama_lengkap}</b>"
        + (f" ({pegawai.nomor_pegawai})" if pegawai.nomor_pegawai else ''),
        styles['body'],
    ))
    story.append(Paragraph(
        f'Program: {assignment.program.nama} ({assignment.program.get_jenis_display()})',
        styles['body'],
    ))
    if terakhir is not None:
        story.append(Paragraph(
            f"Asesmen akhir: {terakhir.nilai} (percobaan {terakhir.percobaan}) — LULUS",
            styles['body'],
        ))
    story.append(Paragraph(
        f"Periode: {assignment.tanggal_mulai} s.d. {assignment.tenggat}",
        styles['body'],
    ))
    story.append(Paragraph(
        'Catatan: sertifikat ini dibangkitkan otomatis dari data sistem ARIMA '
        'dan sah sebagai bukti KPS 4 / KPS 8 pada e-file pegawai.',
        styles['footnote'],
    ))
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4,
                      topMargin=14 * mm, bottomMargin=14 * mm).build(story)
    return buf.getvalue()


def render_tor_pdf(program):
    """TOR (KAK) PDF rendered from real program data; cost section stays blank."""
    from io import BytesIO
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

    styles = _pdf_styles()
    story = []
    _pdf_kop(story, styles)
    story.append(Paragraph(
        f'KERANGKA ACUAN KERJA — {program.nama.upper()}', styles['title'],
    ))
    story.append(Paragraph(
        f"Jenis: {program.get_jenis_display()} · Kelompok: "
        f"{program.get_kelompok_staf_display() or 'Semua kelompok staf'} · "
        f"Durasi baku: {program.durasi_hari} hari",
        styles['footnote'],
    ))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph('1. Aktivitas & Materi', styles['label']))
    for a in program.activities.all().order_by('urutan', 'pk'):
        tanda = '[Wajib]' if a.wajib else '[Opsional]'
        story.append(Paragraph(f'{tanda} {a.nama}', styles['body']))
    story.append(Paragraph('2. Penilaian', styles['label']))
    story.append(Paragraph(
        f'Post-test terpadu; ambang lulus {PASSING_GRADE}. '
        'Tidak lulus → program remedial / perpanjangan pendampingan.',
        styles['body'],
    ))
    story.append(Paragraph('3. Rencana Biaya', styles['label']))
    story.append(Paragraph(
        'Biaya dianggarkan melalui Diklat/anggaran unit; tidak dicatat oleh sistem.',
        styles['body'],
    ))
    story.append(Paragraph('4. Laporan Kegiatan', styles['label']))
    story.append(Paragraph(
        'Rekap hasil post-test, evaluasi pelaksanaan, dan lampiran daftar hadir '
        'diterbitkan dari dashboard orientasi ARIMA.',
        styles['body'],
    ))
    buf = BytesIO()
    SimpleDocTemplate(buf, pagesize=A4,
                      topMargin=14 * mm, bottomMargin=14 * mm).build(story)
    return buf.getvalue()


def archive_certificate(assignment, *, actor):
    """Render passed-orientation certificate and archive it to the employee
    e-file (DokumenPegawai CREDENTIAL + VersiDokumen). Idempotent per version."""
    from io import BytesIO
    from sdm.models import DokumenPegawai
    from sdm.storage import store_document_version

    pdf = render_sertifikat_pdf(assignment)
    pegawai = assignment.employee
    document = DokumenPegawai.objects.filter(
        employee=pegawai,
        document_type='CREDENTIAL',
        jenis_berkas='SERTIFIKAT_KOMPETENSI',
        title__contains=assignment.program.nama,
    ).first()
    if document is None:
        document = DokumenPegawai.objects.create(
            employee=pegawai,
            document_type='CREDENTIAL',
            jenis_berkas='SERTIFIKAT_KOMPETENSI',
            title=f"Sertifikat {assignment.program.nama}",
            sensitivity='personnel',
            created_by=actor,
        )
    upload = BytesIO(pdf)
    upload.name = f'orientasi-{pegawai.pk}-{assignment.pk}.pdf'
    upload.content_type = 'application/pdf'
    version = store_document_version(
        upload, document=document, uploaded_by=actor,
    )
    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='orientation_certificate_issued',
        target_tipe='orientation_assignment',
        target_id=str(assignment.pk),
        status_sesudah='ARCHIVED',
        alasan=f'versi={version.pk}',
    )
    return version
