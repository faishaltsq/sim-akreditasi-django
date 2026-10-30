"""Rekap rekrutmen dan paket bukti berdasarkan catatan yang tersimpan."""
import json
from io import BytesIO
from pathlib import PurePosixPath
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from django.core.serializers.json import DjangoJSONEncoder
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

from sdm.models import Lowongan


TAHAP = ('SELEKSI_ADMIN', 'TES_KOMPETENSI', 'WAWANCARA', 'MCU')
HEADERS = ('Kode', 'Posisi', 'Unit', 'Kuota', 'Pelamar', 'Admin', 'CBT', 'Wawancara', 'MCU', 'Status')


def dashboard_rows(units):
    vacancies = Lowongan.objects.filter(unit_kerja__in=units).select_related(
        'unit_kerja'
    ).prefetch_related('applications__penilaian').order_by('-created_at', '-pk')
    rows = []
    for vacancy in vacancies:
        counts = dict.fromkeys(TAHAP, 0)
        applications = list(vacancy.applications.all())
        for application in applications:
            latest = {}
            for assessment in application.penilaian.all():
                if assessment.tahap not in latest:
                    latest[assessment.tahap] = assessment.hasil
            for stage in TAHAP:
                counts[stage] += latest.get(stage) == 'LULUS'
        rows.append({
            'vacancy': vacancy, 'applications': applications,
            'cells': (str(vacancy.pk), vacancy.judul, vacancy.unit_kerja.code,
                      vacancy.jumlah_kebutuhan, len(applications),
                      *(counts[stage] for stage in TAHAP), vacancy.get_status_display()),
        })
    return rows


def dashboard_pdf(rows):
    output = BytesIO()
    style = getSampleStyleSheet()['BodyText']
    style.fontSize = 6
    style.leading = 8
    data = [[Paragraph(escape(str(value)), style) for value in HEADERS]]
    data.extend([[Paragraph(escape(str(value)), style) for value in row['cells']]
                 for row in rows])
    table = Table(data, repeatRows=1, colWidths=[110, 110, 45, 35, 40, 35, 35, 55, 35, 45])
    table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), .25, 'grey'),
                               ('VALIGN', (0, 0), (-1, -1), 'TOP')]))
    SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=20,
                      rightMargin=20).build([table])
    return output.getvalue()


def audit_package(application):
    """Export actual records; missing uploaded files are explicitly identified."""
    payload = {
        'lamaran': {'id': str(application.pk), 'nama': application.nama_pelamar,
                    'lowongan': str(application.lowongan_id), 'status': application.status},
        'riwayat': list(application.history.values('status_sebelum', 'status_sesudah',
                                                   'catatan', 'actor_id', 'created_at')),
        'penilaian': list(application.penilaian.values('tahap', 'hasil', 'skor', 'catatan',
                                                       'penguji_id', 'dinilai_at')),
        'berkas': list(application.berkas.values('id', 'jenis', 'status', 'catatan',
                                                 'diverifikasi_oleh_id', 'diverifikasi_at')),
        'cbt': list(application.sesi_ujian.values('id', 'paket__nama', 'status', 'mulai_at',
                                                  'selesai_at', 'nilai', 'lulus', 'pindah_fokus')),
        'wawancara': [], 'mcu': None, 'file_tidak_tersedia': [],
    }
    jadwal = getattr(application, 'jadwal_wawancara', None)
    if jadwal:
        payload['wawancara'] = list(jadwal.scorecard.values(
            'penguji_id', 'kompetensi_teknis', 'soft_skill', 'ketahanan_beban_kerja',
            'integritas', 'pemahaman_visi', 'catatan', 'dinilai_at'))
    mcu = getattr(application, 'hasil_mcu', None)
    if mcu:
        payload['mcu'] = {'status': mcu.status, 'tanggal_periksa': mcu.tanggal_periksa,
                          'penyelenggara': mcu.penyelenggara, 'catatan': mcu.catatan,
                          'diperiksa_oleh_id': mcu.diperiksa_oleh_id}
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        files = [(f'berkas/{doc.pk}', doc.berkas) for doc in application.berkas.all()]
        if mcu:
            files.append(('mcu/hasil', mcu.berkas))
        for prefix, field in files:
            if not field:
                continue
            name = f'{prefix}-{PurePosixPath(field.name.replace(chr(92), "/")).name}'
            try:
                with field.open('rb') as source, archive.open(name, 'w') as target:
                    while chunk := source.read(65536):
                        target.write(chunk)
            except (OSError, ValueError):
                payload['file_tidak_tersedia'].append(name)
        archive.writestr('bukti.json', json.dumps(payload, cls=DjangoJSONEncoder,
                                                 ensure_ascii=False, indent=2))
    return output.getvalue()
