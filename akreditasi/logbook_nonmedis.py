"""View Logbook Harian Non-Medis untuk seluruh unit kerja.

Modul terpisah mengikuti pola ``logbook.py`` dan ``mutu_laporan.py``: satu
berkas untuk satu domain, izin lewat helper lokal, ``AuditLog`` pada setiap
aksi POST.
"""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .akses_indikator import HOSPITAL_WIDE_ROLES, unit_scope_ids
from .indikator_views import unit_subtree_ids
from .logbook_nonmedis_models import (
    SHIFT_CHOICES, STATUS_CHOICES, LogbookNonMedis,
    ep_kandidat, resolve_fokus_ep,
)
from .models import AuditLog, UnitKerja


ROLE_BOLEH_ISI = ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA',
                  'KEPALA_UNIT', 'STAF_NAKES')
ROLE_BOLEH_SETUJU = ('SUPER_ADMIN', 'ADMIN_RS', 'KEPALA_UNIT')
ROLE_LINGKUP_RS = ('SUPER_ADMIN', 'ADMIN_RS') + HOSPITAL_WIDE_ROLES


# ---------------------------------------------------------------------------
# Izin
# ---------------------------------------------------------------------------

def _profil(user):
    return getattr(user, 'profile', None)


def _boleh_isi(user, entry):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = _profil(user)
    if p is None or p.role not in ROLE_BOLEH_ISI:
        return False
    if p.role in ROLE_LINGKUP_RS:
        return True
    if getattr(p, 'is_unit_scoped', False) and p.unit_kerja:
        return entry.unit_id in unit_scope_ids(p.unit_kerja)
    return True


def _boleh_setuju(user, entry):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = _profil(user)
    if p is None or p.role not in ROLE_BOLEH_SETUJU:
        return False
    if p.role in ROLE_LINGKUP_RS:
        return True
    if getattr(p, 'is_unit_scoped', False) and p.unit_kerja:
        return entry.unit_id in unit_scope_ids(p.unit_kerja)
    return False


def _boleh_lihat(user, entry):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = _profil(user)
    if p is None:
        return False
    if p.role == 'ASESOR':
        return entry.status == 'DISETUJUI'
    return _boleh_isi(user, entry)


def _cek(user, entry):
    if not _boleh_lihat(user, entry):
        raise PermissionDenied('Logbook non-medis ini berada di luar lingkup Anda.')


def _scoped(user):
    qs = LogbookNonMedis.objects.select_related('unit', 'pegawai', 'disetujui_oleh')
    if not user.is_authenticated:
        return qs.none()
    if user.is_superuser:
        return qs
    p = _profil(user)
    if p is None:
        return qs.none()
    if p.role == 'ASESOR':
        return qs.filter(status='DISETUJUI')
    if p.role in ROLE_LINGKUP_RS:
        return qs
    if getattr(p, 'is_unit_scoped', False) and p.unit_kerja:
        return qs.filter(unit_id__in=unit_scope_ids(p.unit_kerja))
    return qs


def _unit_pilihan(user):
    qs = UnitKerja.objects.filter(is_active=True).order_by('level', 'name')
    if user.is_superuser:
        return qs
    p = _profil(user)
    if p is None:
        return qs.none()
    if p.role in ROLE_LINGKUP_RS:
        return qs
    if p.unit_kerja:
        allowed_ids = unit_subtree_ids(p.unit_kerja)
        return qs.filter(pk__in=allowed_ids)
    return qs.none()


def _catat(user, aksi, obj, detail=''):
    AuditLog.objects.create(
        user=user, aksi=aksi,
        model_name=obj.__class__.__name__,
        object_repr=str(obj)[:250],
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Daftar & pembuatan
# ---------------------------------------------------------------------------

@login_required
def logbook_nonmedis_daftar(request):
    """Tabel rekapitulasi logbook harian non-medis + filter unit/periode."""
    qs = _scoped(request.user)

    unit_id = request.GET.get('unit', '')
    periode = request.GET.get('periode', '')
    cari = request.GET.get('cari', '').strip()

    if unit_id:
        qs = qs.filter(unit_id=unit_id)
    hari_ini = timezone.localdate()
    if periode == 'bulan_ini':
        qs = qs.filter(tanggal__year=hari_ini.year, tanggal__month=hari_ini.month)
    elif periode == 'bulan_lalu':
        awal = (hari_ini.replace(day=1) - timedelta(days=1)).replace(day=1)
        akhir = hari_ini.replace(day=1) - timedelta(days=1)
        qs = qs.filter(tanggal__year=awal.year, tanggal__month=awal.month)
    if cari:
        qs = qs.filter(pelaksana_nama__icontains=cari) | qs.filter(
            pegawai__nama_lengkap__icontains=cari)

    daftar = list(qs.order_by('-tanggal', 'unit__name')[:200])

    unit_choices = _unit_pilihan(request.user)
    p = _profil(request.user)
    boleh_buat = request.user.is_superuser or (p is not None and p.role in ROLE_BOLEH_ISI)

    return render(request, 'akreditasi/logbook_nonmedis_daftar.html', {
        'daftar': daftar,
        'jumlah': len(daftar),
        'unit_pilihan': unit_choices,
        'filter_unit': unit_id,
        'filter_periode': periode,
        'filter_cari': cari,
        'boleh_buat': boleh_buat,
        'hari_ini': hari_ini,
        'status_pilihan': STATUS_CHOICES,
    })


@login_required
def logbook_nonmedis_buat(request):
    """Buat entri logbook non-medis baru (unit + pegawai + tanggal)."""
    p = _profil(request.user)
    boleh = request.user.is_superuser or (p is not None and p.role in ROLE_BOLEH_ISI)
    if not boleh:
        raise PermissionDenied('Anda tidak berwenang membuat logbook non-medis.')

    if request.method == 'POST':
        unit_id = request.POST.get('unit', '')
        pegawai_id = request.POST.get('pegawai', '') or None
        tanggal_teks = request.POST.get('tanggal', '')
        shift = request.POST.get('shift', '')

        unit = get_object_or_404(_unit_pilihan(request.user), pk=unit_id)
        try:
            tanggal = date.fromisoformat(tanggal_teks)
        except (TypeError, ValueError):
            messages.error(request, 'Tanggal dinas tidak valid.')
            return redirect('akreditasi:logbook_nonmedis_daftar')

        from sdm.models import Pegawai
        pegawai = Pegawai.objects.filter(pk=pegawai_id).first() if pegawai_id else None

        entry, dibuat = LogbookNonMedis.objects.get_or_create(
            unit=unit, pegawai=pegawai, tanggal=tanggal,
            defaults={'shift': shift if shift in dict(SHIFT_CHOICES) else '',
                      'pelaksana_nama': pegawai.nama_lengkap if pegawai else '',
                      'dibuat_oleh': request.user})
        if dibuat:
            entry.ensure_checklist()
            _catat(request.user, 'CREATE', entry, 'Logbook non-medis dibuat')
            messages.success(request, 'Logbook non-medis dibuat.')
        else:
            messages.info(request, 'Logbook non-medis tanggal tersebut sudah ada.')
        return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)

    unit_choices = _unit_pilihan(request.user)
    default_unit_id = None
    if p and p.unit_kerja and unit_choices.filter(pk=p.unit_kerja_id).exists():
        default_unit_id = p.unit_kerja_id
    elif unit_choices.exists():
        default_unit_id = unit_choices.first().pk

    # Pegawai yang aktif, urut nama — dipakai dropdown pelaksana.
    from sdm.models import Pegawai
    pegawai_qs = Pegawai.objects.filter(status='AKTIF').order_by('nama_lengkap')

    return render(request, 'akreditasi/logbook_nonmedis_form.html', {
        'unit_pilihan': unit_choices,
        'default_unit_id': default_unit_id,
        'pegawai_pilihan': pegawai_qs,
        'shift_pilihan': SHIFT_CHOICES,
        'hari_ini': timezone.localdate(),
    })


# ---------------------------------------------------------------------------
# Detail & pengisian
# ---------------------------------------------------------------------------

@login_required
def logbook_nonmedis_detail(request, pk):
    """Tampilkan seksi identitas, checklist, uraian+risiko, dan lampiran."""
    entry = get_object_or_404(
        LogbookNonMedis.objects.select_related('unit', 'pegawai', 'fokus_ep',
                                               'dibuat_oleh', 'disetujui_oleh'),
        pk=pk)
    _cek(request.user, entry)

    if entry.status == 'DRAF' and _boleh_isi(request.user, entry):
        entry.ensure_checklist()

    checklist = list(entry.checklist.all())
    kandidat_ep = ep_kandidat(entry.unit)

    return render(request, 'akreditasi/logbook_nonmedis_detail.html', {
        'entry': entry,
        'checklist': checklist,
        'kandidat_ep': kandidat_ep,
        'bukti': entry.bukti.all(),
        'status_pilihan': [('TERLAKSANA', 'Terlaksana'), ('TIDAK', 'Tidak Terlaksana'),
                           ('NA', 'Tidak Berlaku')],
        'shift_label': dict(SHIFT_CHOICES).get(entry.shift, entry.shift),
        'boleh_isi': _boleh_isi(request.user, entry) and entry.boleh_ubah,
        'boleh_setujui': _boleh_setuju(request.user, entry) and entry.boleh_ubah,
        'sudah_disetujui': entry.terkunci,
    })


@login_required
def logbook_nonmedis_simpan_checklist(request, pk):
    entry = get_object_or_404(LogbookNonMedis, pk=pk)
    _cek(request.user, entry)
    if not (_boleh_isi(request.user, entry) and entry.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    from .logbook_nonmedis_models import ChecklistNonMedis
    diubah = 0
    for butir in entry.checklist.all():
        nilai = request.POST.get(f'cek_{butir.kunci}')
        if nilai is None:
            continue
        if nilai in dict(ChecklistNonMedis.STATUS_CHOICES):
            butir.status = nilai
        butir.keterangan = request.POST.get(f'ket_{butir.kunci}', '').strip()
        butir.save(update_fields=['status', 'keterangan'])
        diubah += 1

    _catat(request.user, 'UPDATE', entry, f'Checklist: {diubah} butir')
    messages.success(request, 'Checklist kepatuhan disimpan.')
    return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)


@login_required
def logbook_nonmedis_simpan_narasi(request, pk):
    entry = get_object_or_404(LogbookNonMedis, pk=pk)
    _cek(request.user, entry)
    if not (_boleh_isi(request.user, entry) and entry.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    entry.uraian_aktivitas = request.POST.get('uraian_aktivitas', '').strip()
    entry.target_harian = request.POST.get('target_harian', '').strip()[:250]
    entry.risiko_identifikasi = request.POST.get('risiko_identifikasi', '').strip()
    entry.risiko_mitigasi = request.POST.get('risiko_mitigasi', '').strip()
    entry.fokus_ep_teks = request.POST.get('fokus_ep_teks', '').strip()[:120]

    ep_id = request.POST.get('fokus_ep', '')
    if ep_id:
        ep = resolve_fokus_ep_by_id(ep_id, entry.unit)
        entry.fokus_ep = ep
    else:
        entry.fokus_ep = None

    entry.save(update_fields=['uraian_aktivitas', 'target_harian',
                              'risiko_identifikasi', 'risiko_mitigasi',
                              'fokus_ep_teks', 'fokus_ep'])
    _catat(request.user, 'UPDATE', entry, 'Uraian aktivitas, risiko & fokus EP')
    messages.success(request, 'Uraian aktivitas dan analisis risiko disimpan.')
    return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)


def resolve_fokus_ep_by_id(ep_id, unit):
    """Ambil StandardItem EP hanya bila masih dalam kandidat unit (anti-IDOR)."""
    from .models import StandardItem
    return StandardItem.objects.filter(pk=ep_id, pk__in=ep_kandidat(unit)).first()


@login_required
def logbook_nonmedis_unggah_bukti(request, pk):
    entry = get_object_or_404(LogbookNonMedis, pk=pk)
    _cek(request.user, entry)
    if not (_boleh_isi(request.user, entry) and entry.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    from .file_security import sanitize_filename, validate_uploaded_file
    from .logbook_nonmedis_models import BuktiNonMedis

    berkas = request.FILES.get('berkas')
    sah, pesan = validate_uploaded_file(berkas)
    if not sah:
        messages.error(request, pesan)
        return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)

    judul = request.POST.get('judul', '').strip() or berkas.name
    ukuran = (f'{berkas.size / (1024 * 1024):.1f} MB' if berkas.size >= 1024 * 1024
              else f'{berkas.size / 1024:.0f} KB')
    bukti = BuktiNonMedis.objects.create(
        logbook=entry, judul=judul[:200], berkas=berkas, ukuran=ukuran,
        diunggah_oleh=request.user)
    bukti.berkas.name = sanitize_filename(bukti.berkas.name)
    bukti.save(update_fields=['berkas'])
    _catat(request.user, 'UPLOAD', entry, f'Bukti: {judul}')
    messages.success(request, 'Bukti diunggah.')
    return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)


@login_required
def logbook_nonmedis_setujui(request, pk):
    """Kunci logbook non-medis (DRAF → DISETUJUI) oleh kepala unit / admin."""
    entry = get_object_or_404(LogbookNonMedis, pk=pk)
    _cek(request.user, entry)
    if not _boleh_setuju(request.user, entry):
        raise PermissionDenied('Hanya kepala unit atau admin yang boleh mengesahkan.')
    if entry.status != 'DRAF':
        messages.warning(request, 'Logbook ini sudah disetujui.')
        return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)

    entry.status = 'DISETUJUI'
    entry.disetujui_oleh = request.user
    entry.disetujui_pada = timezone.now()
    entry.save(update_fields=['status', 'disetujui_oleh', 'disetujui_pada'])
    _catat(request.user, 'UPDATE', entry, 'Pengesahan: DRAF → DISETUJUI')
    messages.success(request, 'Logbook non-medis disetujui dan dikunci.')
    return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@login_required
def logbook_nonmedis_pdf(request, pk):
    """Cetak logbook non-medis sebagai PDF portrait (reportlab)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    entry = get_object_or_404(
        LogbookNonMedis.objects.select_related('unit', 'pegawai', 'fokus_ep'), pk=pk)
    _cek(request.user, entry)

    buffer = HttpResponse(content_type='application/pdf')
    buffer['Content-Disposition'] = \
        f'inline; filename="logbook-nonmedis-{entry.tanggal}.pdf"'

    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=15 * mm, bottomMargin=15 * mm,
                            title=f'Logbook Non-Medis {entry.unit.name}')
    gaya = getSampleStyleSheet()
    judul = ParagraphStyle('judul', parent=gaya['Title'], fontSize=14, spaceAfter=4)
    sub = ParagraphStyle('sub', parent=gaya['Normal'], fontSize=9, leading=11)
    si = ParagraphStyle('si', parent=gaya['Normal'], fontSize=8.5, leading=10)

    pelaksana = entry.pegawai.nama_lengkap if entry.pegawai_id else (entry.pelaksana_nama or '—')
    fokus = entry.fokus_ep.code if entry.fokus_ep_id else (entry.fokus_ep_teks or '—')

    elemen = [
        Paragraph(f'Logbook Harian Non-Medis — {entry.unit.name}', judul),
        Paragraph(
            f'Pelaksana: {pelaksana} · Tanggal {entry.tanggal:%d/%m/%Y} · '
            f'Shift {dict(SHIFT_CHOICES).get(entry.shift, entry.shift) or "—"} · '
            f'Fokus EP: {fokus}', sub),
        Spacer(1, 8),
    ]

    elemen += [Paragraph('<b>Checklist Kepatuhan</b>', si)]
    baris_cek = [['No', 'Parameter', 'Status', 'Keterangan']]
    for i, c in enumerate(entry.checklist.all(), start=1):
        baris_cek.append([str(i), Paragraph(c.parameter, si),
                          c.get_status_display(), Paragraph(c.keterangan or '—', si)])
    tabel_cek = Table(baris_cek, repeatRows=1,
                      colWidths=[10 * mm, 95 * mm, 30 * mm, 50 * mm])
    tabel_cek.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elemen += [tabel_cek, Spacer(1, 8)]

    elemen += [
        Paragraph('<b>Uraian Aktivitas / Layanan</b>', si),
        Paragraph(entry.uraian_aktivitas or '—', si),
        Spacer(1, 4),
        Paragraph('<b>Evaluasi Ketercapaian Target Harian</b>', si),
        Paragraph(entry.target_harian or '—', si),
        Spacer(1, 8),
        Paragraph('<b>Identifikasi Potensi Risiko</b>', si),
        Paragraph(entry.risiko_identifikasi or '—', si),
        Spacer(1, 4),
        Paragraph('<b>Rencana Mitigasi / Penanganan</b>', si),
        Paragraph(entry.risiko_mitigasi or '—', si),
        Spacer(1, 8),
    ]

    bukti = list(entry.bukti.all())
    if bukti:
        elemen += [Paragraph('<b>Lampiran Bukti Audit</b>', si)]
        baris_b = [['No', 'Judul Berkas', 'Ukuran']]
        for i, b in enumerate(bukti, start=1):
            baris_b.append([str(i), Paragraph(b.judul, si), b.ukuran or '—'])
        tabel_b = Table(baris_b, colWidths=[10 * mm, 140 * mm, 35 * mm])
        tabel_b.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elemen += [tabel_b, Spacer(1, 8)]

    elemen += [
        Spacer(1, 10),
        Paragraph(
            f'Status: {entry.get_status_display()} · '
            f'Disetujui: {entry.disetujui_oleh.get_full_name() or entry.disetujui_oleh.username if entry.disetujui_oleh_id else "—"} '
            f'({timezone.localtime(entry.disetujui_pada):%d/%m/%Y %H:%M} WIB)' if entry.disetujui_pada
            else f'Status: {entry.get_status_display()}', si),
    ]

    doc.build(elemen)
    return buffer
