"""View Logbook Harian IGD & Rawat Inap.

Modul terpisah dari ``akreditasi/views.py`` (sudah 2.800+ baris) mengikuti
pola ``mutu_laporan.py`` dan ``risiko_views.py``: satu berkas untuk satu
domain, izin lewat helper lokal, setiap aksi POST menulis ``AuditLog``.
"""

from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .akses_indikator import HOSPITAL_WIDE_ROLES, unit_scope_ids
from .file_security import sanitize_filename, validate_uploaded_file
from .logbook_models import (
    JENIS_CHOICES, SEKSI_LABEL, SHIFT_CHOICES,
    LogbookBukti, LogbookChecklist, LogbookHarian, LogbookKejadian,
    los_menit, parse_jam, response_time_menit, shift_window,
)
from .models import AuditLog, UnitKerja
from pasien.models import Ruangan

# Label disposisi IGD untuk tampilan tabel & PDF. Disimpan di sini (bukan di
# model) karena LogbookPasien hanya menyimpan kode, sedangkan labelnya milik
# alur IGD di ``KunjunganPasien``.
DISPOSISI_LABEL = {
    'RAWAT_INAP': 'Rawat Inap',
    'RAWAT_JALAN': 'Rawat Jalan / Pulang',
    'RUJUK': 'Rujuk',
    'PAPS': 'PAPS',
}

# Label triage IGD (nilai mentah tersimpan di KunjunganPasien.triage).
TRIAGE_LABEL = {
    'MERAH': 'Merah',
    'KUNING': 'Kuning',
    'HIJAU': 'Hijau',
    'HITAM': 'Hitam',
    'P1': 'P1', 'P2': 'P2', 'P3': 'P3',
}

# Role yang boleh mengisi logbook unitnya.
ROLE_BOLEH_ISI = ('SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA',
                  'KEPALA_UNIT', 'STAF_NAKES')
# Role yang boleh mengesahkan (menutup) logbook shift.
ROLE_BOLEH_SETUJU = ('SUPER_ADMIN', 'ADMIN_RS', 'KEPALA_UNIT')
# Role yang memandang seluruh rumah sakit tanpa cek lingkup unit.
ROLE_LINGKUP_RS = ('SUPER_ADMIN', 'ADMIN_RS') + HOSPITAL_WIDE_ROLES


# ---------------------------------------------------------------------------
# Izin
# ---------------------------------------------------------------------------

def _profil(user):
    return getattr(user, 'profile', None)


def _boleh_isi(user, logbook):
    """True bila ``user`` boleh mengisi logbook ini."""
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
        return logbook.unit_id in unit_scope_ids(p.unit_kerja)
    return True


def _boleh_setuju(user, logbook):
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
        return logbook.unit_id in unit_scope_ids(p.unit_kerja)
    return False


def _boleh_lihat(user, logbook):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    p = _profil(user)
    if p is None:
        return False
    if p.role == 'ASESOR':
        return logbook.status == 'DISETUJUI'
    return _boleh_isi(user, logbook)


def _cek(user, logbook):
    if not _boleh_lihat(user, logbook):
        raise PermissionDenied('Logbook ini berada di luar lingkup Anda.')


def _logbook_scoped(user):
    """QuerySet logbook yang boleh dilihat ``user``."""
    qs = LogbookHarian.objects.select_related('unit', 'ruangan', 'disetujui_oleh')
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
    """Unit kerja yang boleh dipilih saat membuat logbook."""
    qs = UnitKerja.objects.filter(is_active=True).order_by('level', 'name')
    if user.is_superuser:
        return qs
    p = _profil(user)
    if p is None:
        return qs.none()
    if p.role in ROLE_LINGKUP_RS:
        return qs
    if p.unit_kerja:
        return qs.filter(pk__in=unit_scope_ids(p.unit_kerja))
    return qs.none()


def _catat(user, aksi, obj, detail=''):
    """Jejak audit satu aksi logbook."""
    AuditLog.objects.create(
        user=user, aksi=aksi,
        model_name=obj.__class__.__name__,
        object_repr=str(obj)[:250],
        detail=detail,
    )


def _label_shift(kode):
    return dict(SHIFT_CHOICES).get(kode, kode)


# ---------------------------------------------------------------------------
# Daftar & pembuatan
# ---------------------------------------------------------------------------

@login_required
def logbook_daftar(request):
    """Daftar logbook dalam lingkup pengguna, dengan filter jenis/tanggal/status."""
    qs = _logbook_scoped(request.user)

    jenis = request.GET.get('jenis', '')
    status = request.GET.get('status', '')
    tanggal_teks = request.GET.get('tanggal', '')

    if jenis in dict(JENIS_CHOICES):
        qs = qs.filter(jenis=jenis)
    if status:
        qs = qs.filter(status=status)
    tanggal = None
    if tanggal_teks:
        try:
            tanggal = date.fromisoformat(tanggal_teks)
        except ValueError:
            tanggal = None
    if tanggal:
        qs = qs.filter(tanggal=tanggal)

    daftar = list(qs.order_by('-tanggal', 'shift')[:200])

    return render(request, 'akreditasi/logbook_daftar.html', {
        'daftar': daftar,
        'jumlah': len(daftar),
        'jenis_pilihan': JENIS_CHOICES,
        'status_pilihan': [('DRAF', 'Draf'), ('DIISI', 'Sudah Diserahterimakan'),
                           ('DISETUJUI', 'Disetujui Kepala Unit')],
        'filter_jenis': jenis,
        'filter_status': status,
        'filter_tanggal': tanggal.isoformat() if tanggal else '',
        'hari_ini': timezone.localdate(),
        'boleh_buat': _profil(request.user) is not None
                      and (_profil(request.user).role in ROLE_BOLEH_ISI
                           or request.user.is_superuser),
    })


@login_required
def logbook_buat(request):
    """Buat (atau buka kembali) logbook satu shift."""
    p = _profil(request.user)
    boleh = request.user.is_superuser or (p is not None and p.role in ROLE_BOLEH_ISI)
    if not boleh:
        raise PermissionDenied('Anda tidak berwenang membuat logbook.')

    if request.method == 'POST':
        jenis = request.POST.get('jenis', '')
        shift = request.POST.get('shift', '')
        unit_id = request.POST.get('unit', '')
        ruangan_id = request.POST.get('ruangan', '') or None
        tanggal_teks = request.POST.get('tanggal', '')

        if jenis not in dict(JENIS_CHOICES) or shift not in dict(SHIFT_CHOICES):
            messages.error(request, 'Jenis logbook atau shift tidak dikenal.')
            return redirect('akreditasi:logbook_daftar')
        try:
            tanggal = date.fromisoformat(tanggal_teks)
        except (TypeError, ValueError):
            messages.error(request, 'Tanggal shift tidak valid.')
            return redirect('akreditasi:logbook_daftar')

        unit = get_object_or_404(_unit_pilihan(request.user), pk=unit_id)
        ruangan = None
        if ruangan_id:
            ruangan = Ruangan.objects.filter(pk=ruangan_id).first()

        logbook, dibuat = LogbookHarian.objects.get_or_create(
            jenis=jenis, unit=unit, tanggal=tanggal, shift=shift,
            defaults={'ruangan': ruangan, 'dibuat_oleh': request.user})
        if dibuat:
            _catat(request.user, 'CREATE', logbook, 'Logbook shift dibuat')
            messages.success(request, 'Logbook shift dibuat.')
        else:
            messages.info(request, 'Logbook shift tersebut sudah ada — dibuka kembali.')
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    ruangan_qs = Ruangan.objects.all().order_by('kode')
    return render(request, 'akreditasi/logbook_form.html', {
        'jenis_pilihan': JENIS_CHOICES,
        'shift_pilihan': SHIFT_CHOICES,
        'unit_pilihan': _unit_pilihan(request.user),
        'ruangan_pilihan': ruangan_qs,
        'hari_ini': timezone.localdate(),
        'tanggal_awal': (timezone.localdate() - timedelta(days=1)).isoformat(),
    })


# ---------------------------------------------------------------------------
# Detail & pengisian
# ---------------------------------------------------------------------------

@login_required
def logbook_detail(request, pk):
    """Tampilkan lima seksi logbook; tarik pasien & checklist saat masih draf."""
    logbook = get_object_or_404(
        LogbookHarian.objects.select_related('unit', 'ruangan', 'dibuat_oleh',
                                             'disetujui_oleh', 'diserahterimakan_oleh'),
        pk=pk)
    _cek(request.user, logbook)

    if logbook.status == 'DRAF' and _boleh_isi(request.user, logbook):
        logbook.tarik_pasien()
        logbook.ensure_checklist()

    baris = list(logbook.pasien.select_related('kunjungan', 'kunjungan__pasien'))

    checklist = list(logbook.checklist.all())
    grup = {}
    for c in checklist:
        grup.setdefault(c.seksi, []).append(c)
    checklist_seksi = [
        (kode, SEKSI_LABEL.get(kode, kode), grup.get(kode, []))
        for kode in ('HPK', 'KE', 'SKP') if grup.get(kode)
    ]

    rekap = logbook.rekap()
    # Response time & LOS per baris untuk tabel seksi I.
    for b in baris:
        k = b.kunjungan
        b.rt_menit = response_time_menit(k) if k else None
        b.los_menit = los_menit(k) if k else None

    return render(request, 'akreditasi/logbook_detail.html', {
        'logbook': logbook,
        'baris': baris,
        'rekap': rekap,
        'checklist_seksi': checklist_seksi,
        'kejadian': logbook.kejadian.select_related('insiden').all(),
        'bukti': logbook.bukti.all(),
        'disposisi_pilihan': list(DISPOSISI_LABEL.items()),
        'jenis_insiden': LogbookKejadian._meta.get_field('jenis_insiden').choices,
        'keparahan': LogbookKejadian._meta.get_field('tingkat_keparahan').choices,
        'boleh_isi': _boleh_isi(request.user, logbook) and logbook.boleh_ubah,
        'boleh_setujui': (_boleh_setuju(request.user, logbook)
                          and logbook.status == 'DIISI'),
        'sudah_disetujui': logbook.status == 'DISETUJUI',
        'shift_label': _label_shift(logbook.shift),
        'periode_awal': shift_window(logbook.tanggal, logbook.shift)[0],
        'periode_akhir': shift_window(logbook.tanggal, logbook.shift)[1],
    })


@login_required
@require_POST
def logbook_simpan_pasien(request, pk):
    """Simpan isian manual per pasien (tindakan, disposisi, ADL, catatan)."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not (_boleh_isi(request.user, logbook) and logbook.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    diubah = 0
    for baris in logbook.pasien.all():
        awalan = f'baris_{baris.pk}_'
        if f'{awalan}tindakan' not in request.POST:
            continue
        baris.tindakan = request.POST.get(f'{awalan}tindakan', '').strip()[:300]
        baris.catatan = request.POST.get(f'{awalan}catatan', '').strip()
        dispo = request.POST.get(f'{awalan}disposisi', '')
        if dispo in ('RAWAT_INAP', 'RAWAT_JALAN', 'RUJUK', 'PAPS', ''):
            baris.disposisi = dispo
        dep = request.POST.get(f'{awalan}dependency', '')
        if dep in ('M', 'P', 'T', '?'):
            baris.dependency = dep
        jam_keluar = parse_jam(request.POST.get(f'{awalan}jam_keluar', ''))
        if jam_keluar is not None:
            baris.jam_keluar = jam_keluar
        baris.save(update_fields=['tindakan', 'catatan', 'disposisi',
                                  'dependency', 'jam_keluar'])
        diubah += 1

    _catat(request.user, 'UPDATE', logbook, f'Isian pasien shift: {diubah} baris')
    messages.success(request, f'Isian {diubah} pasien disimpan.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


@login_required
@require_POST
def logbook_simpan_checklist(request, pk):
    """Simpan checklist akreditasi (HPK / KE / SKP) beserta nomor segel."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not (_boleh_isi(request.user, logbook) and logbook.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    diubah = 0
    for butir in logbook.checklist.all():
        nilai = request.POST.get(f'cek_{butir.kunci}')
        if nilai is None:
            continue
        if nilai in dict(LogbookChecklist.STATUS_CHOICES):
            butir.status = nilai
        butir.keterangan = request.POST.get(f'ket_{butir.kunci}', '').strip()
        if butir.butuh_nomor_segel:
            butir.nomor_segel = request.POST.get(f'segel_{butir.kunci}', '').strip()[:60]
        butir.save(update_fields=['status', 'keterangan', 'nomor_segel'])
        diubah += 1

    _catat(request.user, 'UPDATE', logbook, f'Checklist akreditasi: {diubah} butir')
    messages.success(request, 'Checklist akreditasi disimpan.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


@login_required
@require_POST
def logbook_simpan_narasi(request, pk):
    """Simpan personel jaga, catatan shift, dan lembar serah terima SBAR."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not (_boleh_isi(request.user, logbook) and logbook.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    logbook.pj_shift_nama = request.POST.get('pj_shift_nama', '').strip()[:150]
    logbook.ttd_perawat = request.POST.get('ttd_perawat', '').strip()[:150]
    logbook.rasio_perawat_pasien = request.POST.get('rasio_perawat_pasien', '').strip()[:20]
    logbook.pasien_kritis_nama = request.POST.get('pasien_kritis_nama', '').strip()[:250]
    logbook.penunjang_pending = request.POST.get('penunjang_pending', '').strip()
    logbook.catatan_shift = request.POST.get('catatan_shift', '').strip()
    logbook.sbar_situation = request.POST.get('sbar_situation', '').strip()
    logbook.sbar_background = request.POST.get('sbar_background', '').strip()
    logbook.sbar_assessment = request.POST.get('sbar_assessment', '').strip()
    logbook.sbar_recommendation = request.POST.get('sbar_recommendation', '').strip()

    for medan, kunci in (('jumlah_perawat', 'jumlah_perawat'),
                         ('pasien_menunggu_kamar', 'pasien_menunggu_kamar')):
        nilai = request.POST.get(kunci, '').strip()
        if nilai.isdigit():
            setattr(logbook, medan, int(nilai))

    logbook.save(update_fields=['pj_shift_nama', 'ttd_perawat', 'rasio_perawat_pasien',
                               'pasien_kritis_nama', 'penunjang_pending', 'catatan_shift',
                               'sbar_situation', 'sbar_background', 'sbar_assessment',
                               'sbar_recommendation', 'jumlah_perawat',
                               'pasien_menunggu_kamar'])
    _catat(request.user, 'UPDATE', logbook, 'Narasi shift & serah terima SBAR')
    messages.success(request, 'Catatan shift dan serah terima disimpan.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


@login_required
@require_POST
def logbook_simpan_kejadian(request, pk):
    """Catat kejadian keselamatan shift dan teruskan ke Insiden Keselamatan."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not (_boleh_isi(request.user, logbook) and logbook.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    jenis = request.POST.get('jenis_insiden', '')
    keparahan = request.POST.get('tingkat_keparahan', '')
    lokasi = request.POST.get('lokasi_kejadian', '').strip()[:200]
    deskripsi = request.POST.get('deskripsi_kejadian', '').strip()
    valid_jenis = dict(LogbookKejadian._meta.get_field('jenis_insiden').choices)
    valid_parah = dict(LogbookKejadian._meta.get_field('tingkat_keparahan').choices)

    if jenis not in valid_jenis or keparahan not in valid_parah or not lokasi or not deskripsi:
        messages.error(request, 'Jenis, keparahan, lokasi, dan deskripsi kejadian wajib diisi.')
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    kejadian = LogbookKejadian.objects.create(
        logbook=logbook,
        jenis_insiden=jenis,
        tingkat_keparahan=keparahan,
        waktu_kejadian=parse_jam(request.POST.get('waktu_kejadian', '')),
        lokasi_kejadian=lokasi,
        deskripsi_kejadian=deskripsi,
        tindakan_segera=request.POST.get('tindakan_segera', '').strip(),
        pasien_terpapar=request.POST.get('pasien_terpapar') == 'on',
        dilaporkan_oleh=request.user,
    )
    kejadian.sync_ke_ikp()
    _catat(request.user, 'CREATE', logbook,
           f'Kejadian {jenis} dilaporkan dan diteruskan ke Insiden Keselamatan')
    messages.success(request, 'Kejadian tercatat dan masuk ke Insiden Keselamatan.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


@login_required
@require_POST
def logbook_unggah_bukti(request, pk):
    """Unggah berkas bukti shift (validasi ekstensi & sanitasi nama)."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not (_boleh_isi(request.user, logbook) and logbook.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    berkas = request.FILES.get('berkas')
    sah, pesan = validate_uploaded_file(berkas)
    if not sah:
        messages.error(request, pesan)
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    judul = request.POST.get('judul', '').strip() or berkas.name
    ukuran = (f'{berkas.size / (1024 * 1024):.1f} MB' if berkas.size >= 1024 * 1024
              else f'{berkas.size / 1024:.0f} KB')
    buku = LogbookBukti.objects.create(
        logbook=logbook,
        checklist_id=request.POST.get('checklist') or None,
        judul=judul[:200],
        berkas=berkas,
        ukuran=ukuran,
        diunggah_oleh=request.user,
    )
    # Nama file disanitasi setelah tersimpan supaya storage tidak menyimpan
    # nama berbahaya (path traversal / karakter shell).
    buku.berkas.name = sanitize_filename(buku.berkas.name)
    buku.save(update_fields=['berkas'])
    _catat(request.user, 'UPLOAD', logbook, f'Bukti: {judul}')
    messages.success(request, 'Bukti shift diunggah.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


# ---------------------------------------------------------------------------
# Alur status
# ---------------------------------------------------------------------------

@login_required
@require_POST
def logbook_serah_terima(request, pk):
    """DRAF → DIISI: perawat penanggung jawab menyerahkan logbook shift."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not _boleh_isi(request.user, logbook):
        raise PermissionDenied('Anda tidak berwenang menyerahterimakan logbook ini.')
    if logbook.status != 'DRAF':
        messages.warning(request, 'Logbook ini bukan draf lagi.')
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    nama = request.POST.get('ttd_perawat', '').strip()
    if not nama:
        messages.error(request, 'Nama perawat penanggung jawab wajib diisi sebelum serah terima.')
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    logbook.ttd_perawat = nama[:150]
    logbook.status = 'DIISI'
    logbook.diserahterimakan_oleh = request.user
    logbook.diserahterimakan_pada = timezone.now()
    logbook.save(update_fields=['ttd_perawat', 'status', 'diserahterimakan_oleh',
                                'diserahterimakan_pada'])
    _catat(request.user, 'UPDATE', logbook, 'Serah terima shift: DRAF → DIISI')
    messages.success(request, 'Logbook diserahterimakan, menunggu pengesahan kepala unit.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


@login_required
@require_POST
def logbook_setujui(request, pk):
    """DIISI → DISETUJUI: kepala unit mengunci logbook shift."""
    logbook = get_object_or_404(LogbookHarian, pk=pk)
    _cek(request.user, logbook)
    if not _boleh_setuju(request.user, logbook):
        raise PermissionDenied('Hanya kepala unit atau admin yang boleh mengesahkan logbook.')
    if logbook.status != 'DIISI':
        messages.warning(request, 'Logbook harus berstatus sudah diserahterimakan.')
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    nama = request.POST.get('ttd_kepala_ruang', '').strip()
    if not nama:
        messages.error(request, 'Nama kepala ruangan / katim wajib diisi untuk pengesahan.')
        return redirect('akreditasi:logbook_detail', pk=logbook.pk)

    logbook.ttd_kepala_ruang = nama[:150]
    logbook.status = 'DISETUJUI'
    logbook.disetujui_oleh = request.user
    logbook.disetujui_pada = timezone.now()
    logbook.save(update_fields=['ttd_kepala_ruang', 'status', 'disetujui_oleh',
                                'disetujui_pada'])
    _catat(request.user, 'UPDATE', logbook, 'Pengesahan kepala unit: DIISI → DISETUJUI')
    messages.success(request, 'Logbook disetujui dan dikunci.')
    return redirect('akreditasi:logbook_detail', pk=logbook.pk)


# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------

@login_required
def logbook_pdf(request, pk):
    """Cetak logbook satu shift sebagai PDF landscape (reportlab)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    logbook = get_object_or_404(LogbookHarian.objects.select_related('unit', 'ruangan'), pk=pk)
    _cek(request.user, logbook)

    buffer = HttpResponse(content_type='application/pdf')
    buffer['Content-Disposition'] = \
        f'inline; filename="logbook-{logbook.jenis.lower()}-{logbook.tanggal}-{logbook.shift.lower()}.pdf"'

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f'Logbook {logbook.get_jenis_display()}')
    gaya = getSampleStyleSheet()
    judul = ParagraphStyle('judul', parent=gaya['Title'], fontSize=13, spaceAfter=4)
    sub = ParagraphStyle('sub', parent=gaya['Normal'], fontSize=9, leading=11)
    si = ParagraphStyle('si', parent=gaya['Normal'], fontSize=7, leading=8.5)

    awal, akhir = shift_window(logbook.tanggal, logbook.shift)
    elemen = [
        Paragraph(f'{logbook.get_jenis_display()} — {logbook.unit.name}', judul),
        Paragraph(
            f'Tanggal {logbook.tanggal:%d/%m/%Y} · Shift {logbook.get_shift_display()} · '
            f'{timezone.localtime(awal):%d/%m %H:%M}–{timezone.localtime(akhir):%d/%m %H:%M} · '
            f'Status {logbook.get_status_display()}', sub),
        Spacer(1, 5),
    ]

    rekap = logbook.rekap()
    ringkas = [
        ['Pasien', str(rekap['jumlah_pasien'])],
        ['Triage M/K/H/T', f"{rekap['triage'].get('MERAH', 0)}/{rekap['triage'].get('KUNING', 0)}/"
                           f"{rekap['triage'].get('HIJAU', 0)}/{rekap['triage'].get('HITAM', 0)}"],
        ['RT rata-rata (menit)', '—' if rekap['rt_rata2'] is None else str(rekap['rt_rata2'])],
        ['RT > 5 menit', str(rekap['rt_terlambat'])],
        ['LOS rata-rata (jam)', '—' if rekap['los_rata2_jam'] is None else str(rekap['los_rata2_jam'])],
        ['LOS > 6 jam', str(rekap['los_lebih_6_jam'])],
        ['BOR shift', '—' if rekap['bor_persen'] is None else f"{rekap['bor_persen']}%"],
    ]
    tabel_ringkas = Table(ringkas, colWidths=[45 * mm, 30 * mm])
    tabel_ringkas.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 7.5),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.grey),
        ('BACKGROUND', (0, 0), (0, -1), colors.whitesmoke),
    ]))
    elemen += [Paragraph('<b>I. Rekap Shift</b>', si), tabel_ringkas, Spacer(1, 6)]

    kepala = ['No', 'No. RM', 'Nama Pasien', 'Bed', 'Triage', 'Masuk', 'Keluar',
              'Diagnosa', 'RT (mnt)', 'LOS (mnt)', 'ADL', 'Disposisi']
    isi = [kepala]
    for i, b in enumerate(logbook.pasien.select_related('kunjungan'), start=1):
        k = b.kunjungan
        isi.append([
            str(i), b.no_rm, Paragraph(b.nama_pasien, si), b.no_bed or '—',
            TRIAGE_LABEL.get(b.triage, b.triage or '—'),
            b.jam_masuk.strftime('%H:%M') if b.jam_masuk else '—',
            b.jam_keluar.strftime('%H:%M') if b.jam_keluar else '—',
            Paragraph(b.diagnosa or '—', si),
            '—' if not k or response_time_menit(k) is None else str(response_time_menit(k)),
            '—' if not k or los_menit(k) is None else str(los_menit(k)),
            b.get_dependency_display(),
            DISPOSISI_LABEL.get(b.disposisi, b.disposisi) if b.disposisi else '—',
        ])
    if len(isi) == 1:
        isi.append(['—'] * len(kepala))
    tabel_pasien = Table(isi, repeatRows=1, colWidths=[
        8 * mm, 18 * mm, 40 * mm, 12 * mm, 16 * mm, 12 * mm, 12 * mm,
        42 * mm, 14 * mm, 15 * mm, 22 * mm, 22 * mm])
    tabel_pasien.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6.5),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1f3864')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elemen += [Paragraph('<b>II. Pasien Shift</b>', si), tabel_pasien, Spacer(1, 6)]

    checklist = list(logbook.checklist.all())
    if checklist:
        baris_cek = [['Seksi', 'Butir', 'Status', 'Keterangan', 'No. Segel']]
        for c in checklist:
            baris_cek.append([c.seksi, Paragraph(c.parameter, si), c.get_status_display(),
                              Paragraph(c.keterangan or '—', si), c.nomor_segel or '—'])
        tabel_cek = Table(baris_cek, repeatRows=1,
                          colWidths=[14 * mm, 105 * mm, 22 * mm, 70 * mm, 30 * mm])
        tabel_cek.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 6.5),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elemen += [Paragraph('<b>III. Checklist Akreditasi</b>', si), tabel_cek, Spacer(1, 6)]

    kejadian = list(logbook.kejadian.all())
    baris_kj = [['Jam', 'Jenis', 'Keparahan', 'Lokasi', 'Deskripsi', 'Tindakan Segera']]
    for k in kejadian:
        baris_kj.append([k.waktu_kejadian.strftime('%H:%M') if k.waktu_kejadian else '—',
                         k.get_jenis_insiden_display(), k.get_tingkat_keparahan_display(),
                         Paragraph(k.lokasi_kejadian, si),
                         Paragraph(k.deskripsi_kejadian, si),
                         Paragraph(k.tindakan_segera or '—', si)])
    if len(baris_kj) == 1:
        baris_kj.append(['—'] * 6)
    tabel_kj = Table(baris_kj, repeatRows=1,
                     colWidths=[14 * mm, 30 * mm, 24 * mm, 45 * mm, 70 * mm, 58 * mm])
    tabel_kj.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 6.5),
        ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elemen += [Paragraph('<b>IV. Kejadian Keselamatan</b>', si), tabel_kj, Spacer(1, 6)]

    sbar = (f'<b>S</b>ituation: {logbook.sbar_situation or "—"}<br/>'
            f'<b>B</b>ackground: {logbook.sbar_background or "—"}<br/>'
            f'<b>A</b>ssessment: {logbook.sbar_assessment or "—"}<br/>'
            f'<b>R</b>ecommendation: {logbook.sbar_recommendation or "—"}')
    elemen += [
        Paragraph('<b>V. Serah Terima (SBAR)</b>', si),
        Paragraph(sbar, si),
        Spacer(1, 8),
        Paragraph(
            f'PJ Shift: {logbook.pj_shift_nama or "—"} · Jumlah perawat: '
            f'{logbook.jumlah_perawat or "—"} · Rasio: {logbook.rasio_perawat_pasien or "—"}<br/>'
            f'Perawat: {logbook.ttd_perawat or "—"} &nbsp;&nbsp; '
            f'Kepala Ruangan / Katim: {logbook.ttd_kepala_ruang or "—"}', si),
    ]

    doc.build(elemen)
    return buffer
