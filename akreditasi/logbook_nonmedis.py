"""View Logbook Harian Non-Medis untuk seluruh unit kerja.

Modul terpisah mengikuti pola ``logbook.py`` dan ``mutu_laporan.py``: satu
berkas untuk satu domain, izin lewat helper lokal, ``AuditLog`` pada setiap
aksi POST.
"""

from datetime import date, time, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .akses_indikator import HOSPITAL_WIDE_ROLES, unit_scope_ids
from .indikator_views import unit_subtree_ids
from .logbook_nonmedis_models import (
    AktivitasNonMedis,
    LogbookNonMedis,
    MasterAktivitasNonMedis,
    SHIFT_CHOICES,
    STATUS_CHOICES,
    ep_kandidat,
    resolve_ep_aktivitas,
    resolve_fokus_ep,
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
        jam_mulai_teks = request.POST.get('jam_mulai', '').strip()
        jam_selesai_teks = request.POST.get('jam_selesai', '').strip()
        pelaksana_nama_input = request.POST.get('pelaksana_nama', '').strip()

        unit = get_object_or_404(_unit_pilihan(request.user), pk=unit_id)
        try:
            tanggal = date.fromisoformat(tanggal_teks)
        except (TypeError, ValueError):
            messages.error(request, 'Tanggal dinas tidak valid.')
            return redirect('akreditasi:logbook_nonmedis_daftar')

        jam_mulai = None
        jam_selesai = None
        try:
            if jam_mulai_teks:
                jam_mulai = time.fromisoformat(jam_mulai_teks)
        except (ValueError, TypeError):
            pass
        try:
            if jam_selesai_teks:
                jam_selesai = time.fromisoformat(jam_selesai_teks)
        except (ValueError, TypeError):
            pass

        from sdm.models import Pegawai
        pegawai = Pegawai.objects.filter(pk=pegawai_id).first() if pegawai_id else None

        # Delegasi pelaksana untuk role manajerial/admin
        boleh_delegasi = request.user.is_superuser or (p is not None and p.role in ROLE_BOLEH_SETUJU)
        if boleh_delegasi and pelaksana_nama_input:
            pelaksana_nama = pelaksana_nama_input
        elif pegawai:
            pelaksana_nama = pegawai.nama_lengkap
        else:
            pelaksana_nama = request.user.get_full_name() or request.user.username

        entry, dibuat = LogbookNonMedis.objects.get_or_create(
            unit=unit, pegawai=pegawai, tanggal=tanggal,
            defaults={
                'shift': shift if shift in dict(SHIFT_CHOICES) else '',
                'pelaksana_nama': pelaksana_nama,
                'jam_mulai': jam_mulai,
                'jam_selesai': jam_selesai,
                'dibuat_oleh': request.user,
            })
        if dibuat:
            entry.ensure_checklist()
            _catat(request.user, 'CREATE', entry, 'Logbook non-medis dibuat')
            messages.success(request, 'Logbook non-medis dibuat.')
        else:
            if entry.boleh_ubah:
                if jam_mulai:
                    entry.jam_mulai = jam_mulai
                if jam_selesai:
                    entry.jam_selesai = jam_selesai
                if boleh_delegasi and pelaksana_nama_input:
                    entry.pelaksana_nama = pelaksana_nama_input
                entry.save(update_fields=['jam_mulai', 'jam_selesai', 'pelaksana_nama'])
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
    aktivitas_list = list(entry.aktivitas_list.select_related('master').all())
    master_aktivitas_list = list(MasterAktivitasNonMedis.objects.filter(is_active=True).order_by('kategori_unit', 'urutan', 'kode'))

    return render(request, 'akreditasi/logbook_nonmedis_detail.html', {
        'entry': entry,
        'checklist': checklist,
        'kandidat_ep': kandidat_ep,
        'aktivitas_list': aktivitas_list,
        'master_aktivitas_list': master_aktivitas_list,
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
    jam_dinas_str = f"{entry.jam_mulai.strftime('%H:%M')} – {entry.jam_selesai.strftime('%H:%M')} WIB" if entry.jam_mulai and entry.jam_selesai else '—'

    elemen = [
        Paragraph(f'Logbook Harian Non-Medis — {entry.unit.name}', judul),
        Paragraph(
            f'Pelaksana: {pelaksana} · Tanggal {entry.tanggal:%d/%m/%Y} · '
            f'Shift {dict(SHIFT_CHOICES).get(entry.shift, entry.shift) or "—"} · '
            f'Jam Dinas: {jam_dinas_str} · Fokus EP: {fokus}', sub),
        Spacer(1, 8),
    ]

    aktivitas = list(entry.aktivitas_list.select_related('master').all())
    if aktivitas:
        elemen += [Paragraph('<b>Rincian Aktivitas Harian &amp; Dokumen Bukti Terstandar</b>', si)]
        baris_akt = [['No', 'Waktu', 'Aktivitas', 'Detail / Uraian Bebas', 'Standar STARKES', 'Dokumen Bukti']]
        for i, a in enumerate(aktivitas, start=1):
            waktu_str = a.waktu_display or '—'
            if a.durasi_jam > 0:
                waktu_str += f'\n({a.durasi_jam} jam)'
            nama_akt = a.nama_aktivitas
            if a.master:
                nama_akt = f'[{a.master.kode}] {nama_akt}'
            baris_akt.append([
                str(i),
                Paragraph(waktu_str, si),
                Paragraph(nama_akt, si),
                Paragraph(a.detail_uraian or '—', si),
                Paragraph(a.ep_starkes or '—', si),
                Paragraph(a.nama_bukti or (a.dokumen_bukti.name if a.dokumen_bukti else '—'), si)
            ])
        tabel_akt = Table(baris_akt, repeatRows=1,
                          colWidths=[8 * mm, 24 * mm, 45 * mm, 53 * mm, 25 * mm, 30 * mm])
        tabel_akt.setStyle(TableStyle([
            ('FONTSIZE', (0, 0), (-1, -1), 7.5),
            ('BACKGROUND', (0, 0), (-1, 0), colors.whitesmoke),
            ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elemen += [tabel_akt, Spacer(1, 8)]

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
        Spacer(1, 12),
    ]

    # Tabel Tanda Tangan
    tgl_teks = entry.tanggal.strftime('%d %B %Y')
    ttd_data = [
        [
            Paragraph(f'Mengetahui / Menyetujui,<br/><b>Kepala Unit Kerja / Atasan</b><br/><br/><br/><br/><u>{entry.disetujui_oleh.get_full_name() if entry.disetujui_oleh_id else "................................................"}</u><br/><font size="7">NIP. ' + (getattr(getattr(entry.disetujui_oleh, 'pegawai', None), 'nip', '') if entry.disetujui_oleh_id else '') + '</font>', si),
            Paragraph(f'Rumah Sakit, {tgl_teks}<br/><b>Staf Pelaksana Kegiatan</b><br/><br/><br/><br/><u>{pelaksana}</u><br/><font size="7">NIP. ' + (getattr(entry.pegawai, 'nip', '') if entry.pegawai else '') + '</font>', si),
        ]
    ]
    tabel_ttd = Table(ttd_data, colWidths=[90 * mm, 90 * mm])
    tabel_ttd.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elemen += [tabel_ttd]

    doc.build(elemen)
    return buffer


@login_required
def logbook_nonmedis_rekap(request):
    """
    Dashboard Rekapitulasi Multidimensi Kinerja Non-Medis & Diklat:
    - Tab 1: BULANAN (Insentif & Remunerasi, Produktivitas, Kehadiran Jam Dinas)
    - Tab 2: TAHUNAN (20 JPL Pegawai, Mandatory Training KPS 8, SPMI RS, SKP/DP3)
    - Tab 3: 5 TAHUNAN (Siklus STARKES, Portofolio Dokumen Bukti Surveior, Tren Kompetensi)
    - Tab 4: KONTROL (Integrated Control, Approval Backlog, Monitoring Realtime)
    """
    unit_id = request.GET.get('unit', '')
    tab_aktif = request.GET.get('periode', 'BULANAN').upper()
    if tab_aktif not in ['BULANAN', 'TAHUNAN', '5TAHUNAN', 'KONTROL']:
        tab_aktif = 'BULANAN'

    hari_ini = timezone.localdate()
    try:
        tahun = int(request.GET.get('tahun') or hari_ini.year)
    except ValueError:
        tahun = hari_ini.year
    try:
        bulan = int(request.GET.get('bulan') or hari_ini.month)
    except ValueError:
        bulan = hari_ini.month

    # Scoping user unit access
    qs_base = _scoped(request.user)
    unit = None
    if unit_id:
        try:
            unit = UnitKerja.objects.get(pk=unit_id)
            qs_base = qs_base.filter(unit=unit)
        except UnitKerja.DoesNotExist:
            unit = None

    # Filter queryset based on tab
    if tab_aktif == 'BULANAN':
        qs_rekap = qs_base.filter(tanggal__year=tahun, tanggal__month=bulan)
    elif tab_aktif == 'TAHUNAN':
        qs_rekap = qs_base.filter(tanggal__year=tahun)
    elif tab_aktif == '5TAHUNAN':
        qs_rekap = qs_base.filter(tanggal__year__gte=tahun - 4, tanggal__year__lte=tahun)
    else:  # KONTROL
        qs_rekap = qs_base.filter(tanggal__year=tahun)

    logbooks = list(qs_rekap.prefetch_related('aktivitas_list__master', 'checklist', 'bukti', 'pegawai'))

    # Metrics calculation
    total_logbook = len(logbooks)
    total_disetujui = sum(1 for lb in logbooks if lb.status == 'DISETUJUI')
    total_draf = sum(1 for lb in logbooks if lb.status == 'DRAF')
    total_jam_dinas = sum(lb.durasi_dinas_jam for lb in logbooks)

    semua_aktivitas = []
    for lb in logbooks:
        semua_aktivitas.extend(list(lb.aktivitas_list.all()))

    total_aktivitas = len(semua_aktivitas)
    total_jam_aktivitas = sum(a.durasi_jam for a in semua_aktivitas)
    total_dokumen_bukti = sum(1 for a in semua_aktivitas if a.dokumen_bukti or a.nama_bukti)

    # 1. Tab Bulanan: Rekap Pegawai (Insentif & Remunerasi)
    rekap_pegawai = {}
    for lb in logbooks:
        pelaksana_nama = lb.pegawai.nama_lengkap if lb.pegawai_id else (lb.pelaksana_nama or 'Staf Tidak Dikenal')
        if pelaksana_nama not in rekap_pegawai:
            rekap_pegawai[pelaksana_nama] = {
                'nama': pelaksana_nama,
                'nip': getattr(lb.pegawai, 'nip', '—') if lb.pegawai_id else '—',
                'logbook_count': 0,
                'jam_dinas': 0.0,
                'jam_aktivitas': 0.0,
                'bukti_count': 0,
            }
        rekap_pegawai[pelaksana_nama]['logbook_count'] += 1
        rekap_pegawai[pelaksana_nama]['jam_dinas'] += lb.durasi_dinas_jam
        for akt in lb.aktivitas_list.all():
            rekap_pegawai[pelaksana_nama]['jam_aktivitas'] += akt.durasi_jam
            if akt.dokumen_bukti or akt.nama_bukti:
                rekap_pegawai[pelaksana_nama]['bukti_count'] += 1

    # Tentukan skor & tier insentif
    for r in rekap_pegawai.values():
        jam_akt = r['jam_aktivitas']
        if jam_akt >= 30:
            r['tier'] = 'Tier A (Sangat Produktif)'
            r['skor'] = 100
            r['badge'] = 'success'
        elif jam_akt >= 20:
            r['tier'] = 'Tier B (Produktif / Standar)'
            r['skor'] = 85
            r['badge'] = 'primary'
        elif jam_akt >= 10:
            r['tier'] = 'Tier C (Cukup)'
            r['skor'] = 70
            r['badge'] = 'warning'
        else:
            r['tier'] = 'Tier D (Kurang)'
            r['skor'] = 50
            r['badge'] = 'danger'

    rekap_pegawai_list = sorted(rekap_pegawai.values(), key=lambda x: x['jam_aktivitas'], reverse=True)

    # 2. Tab Tahunan: 20 JPL Tracking & Mandatory Training Capaian
    mandatory_stats = {
        'BHD': {'nama': 'Bantuan Hidup Dasar (BHD)', 'count': 0, 'standar': 'KPS 8 / SKP'},
        'PPI': {'nama': 'Pencegahan & Pengendalian Infeksi (PPI)', 'count': 0, 'standar': 'KPS 8 / PPI'},
        'APAR': {'nama': 'Keselamatan Kerja & APAR (MFK)', 'count': 0, 'standar': 'KPS 8 / MFK'},
        'SKP': {'nama': 'Sasaran Keselamatan Pasien (SKP)', 'count': 0, 'standar': 'KPS 8 / SKP'},
    }
    for akt in semua_aktivitas:
        teks = f"{akt.nama_aktivitas} {akt.detail_uraian} {akt.ep_starkes}".upper()
        if 'BHD' in teks or 'RESUSITASI' in teks:
            mandatory_stats['BHD']['count'] += 1
        if 'PPI' in teks or 'HAND HYGIENE' in teks or 'INFEKSI' in teks:
            mandatory_stats['PPI']['count'] += 1
        if 'APAR' in teks or 'KEBAKARAN' in teks or 'MFK' in teks or 'EVAKUASI' in teks:
            mandatory_stats['APAR']['count'] += 1
        if 'SKP' in teks or 'KESELAMATAN PASIEN' in teks:
            mandatory_stats['SKP']['count'] += 1

    # 3. Tab 5 Tahunan: Portofolio STARKES per Bab
    starkes_bab_map = {
        'KPS': {'nama': 'Kualifikasi & Pendidikan Staf (KPS)', 'aktivitas_count': 0, 'bukti_count': 0},
        'TKRS': {'nama': 'Tata Kelola Rumah Sakit (TKRS)', 'aktivitas_count': 0, 'bukti_count': 0},
        'IPKP': {'nama': 'Integrasi Pendidikan Kesehatan Klinis (IPKP)', 'aktivitas_count': 0, 'bukti_count': 0},
        'PPI': {'nama': 'Pencegahan & Pengendalian Infeksi (PPI)', 'aktivitas_count': 0, 'bukti_count': 0},
        'SKP': {'nama': 'Sasaran Keselamatan Pasien (SKP)', 'aktivitas_count': 0, 'bukti_count': 0},
        'MFK': {'nama': 'Manajemen Fasilitas & Keselamatan (MFK)', 'aktivitas_count': 0, 'bukti_count': 0},
        'MRMIK': {'nama': 'Manajemen Rekam Medis & Informasi (MRMIK)', 'aktivitas_count': 0, 'bukti_count': 0},
        'PMKP': {'nama': 'Peningkatan Mutu & Keselamatan Pasien (PMKP)', 'aktivitas_count': 0, 'bukti_count': 0},
    }
    for akt in semua_aktivitas:
        ep_teks = (akt.ep_starkes or '').upper()
        memiliki_bukti = bool(akt.dokumen_bukti or akt.nama_bukti)
        for bab, d in starkes_bab_map.items():
            if bab in ep_teks:
                d['aktivitas_count'] += 1
                if memiliki_bukti:
                    d['bukti_count'] += 1

    # 4. Distribusi Master Aktivitas
    master_distribusi = {}
    for akt in semua_aktivitas:
        m_kode = akt.master.kode if akt.master else 'NON-MASTER'
        m_nama = akt.master.nama if akt.master else akt.nama_aktivitas
        if m_kode not in master_distribusi:
            master_distribusi[m_kode] = {
                'kode': m_kode,
                'nama': m_nama,
                'frekuensi': 0,
                'durasi_total': 0.0,
            }
        master_distribusi[m_kode]['frekuensi'] += 1
        master_distribusi[m_kode]['durasi_total'] += akt.durasi_jam

    master_distribusi_list = sorted(master_distribusi.values(), key=lambda x: x['frekuensi'], reverse=True)

    unit_pilihan = _unit_pilihan(request.user)

    context = {
        'tab_aktif': tab_aktif,
        'unit': unit,
        'unit_pilihan': unit_pilihan,
        'filter_unit': unit_id,
        'filter_tahun': tahun,
        'filter_bulan': bulan,
        'tahun_list': list(range(hari_ini.year - 4, hari_ini.year + 2)),
        'bulan_list': [
            (1, 'Januari'), (2, 'Februari'), (3, 'Maret'), (4, 'April'),
            (5, 'Mei'), (6, 'Juni'), (7, 'Juli'), (8, 'Agustus'),
            (9, 'September'), (10, 'Oktober'), (11, 'November'), (12, 'Desember'),
        ],
        'total_logbook': total_logbook,
        'total_disetujui': total_disetujui,
        'total_draf': total_draf,
        'total_jam_dinas': total_jam_dinas,
        'total_aktivitas': total_aktivitas,
        'total_jam_aktivitas': total_jam_aktivitas,
        'total_dokumen_bukti': total_dokumen_bukti,
        'logbooks': logbooks,
        'semua_aktivitas': semua_aktivitas,
        'rekap_pegawai': rekap_pegawai_list,
        'mandatory_stats': mandatory_stats,
        'starkes_bab_map': starkes_bab_map,
        'master_distribusi': master_distribusi_list,
        'hari_ini': hari_ini,
    }
    return render(request, 'akreditasi/logbook_nonmedis_rekap.html', context)


@login_required
def logbook_nonmedis_rekap_pdf(request):
    """
    Cetak PDF Rekapitulasi Multidimensi Kinerja Non-Medis & Diklat:
    - BULANAN: Evaluasi insentif/remunerasi, kehadiran jam dinas, produktivitas harian.
    - TAHUNAN: Batas minimal 20 JPL staf, capaian mandatory training KPS 8, SPMI & SKP/DP3.
    - 5TAHUNAN: Portofolio bukti survei siklus STARKES (KPS, TKRS, IPKP, PPI, MFK) & tren kompetensi.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    unit_id = request.GET.get('unit')
    periode = request.GET.get('periode', 'BULANAN').upper()
    tahun = int(request.GET.get('tahun') or timezone.now().year)
    bulan = int(request.GET.get('bulan') or timezone.now().month)

    unit = None
    if unit_id:
        unit = get_object_or_404(UnitKerja, pk=unit_id)

    # Scoping logbooks
    qs = _scoped(request.user)
    if unit:
        qs = qs.filter(unit=unit)

    if periode == 'BULANAN':
        qs = qs.filter(tanggal__year=tahun, tanggal__month=bulan)
        judul_periode = f"REKAPITULASI KINERJA BULANAN — {bulan:02d}/{tahun}"
        sub_judul = "Fokus: Evaluasi Insentif / Remunerasi, Jam Pelayanan Dinas & Produktivitas Kerja Harian"
    elif periode == 'TAHUNAN':
        qs = qs.filter(tanggal__year=tahun)
        judul_periode = f"REKAPITULASI KINERJA TAHUNAN — TAHUN {tahun}"
        sub_judul = "Fokus: Evaluasi Batas Minimal 20 JPL Staf, Mandatory Training KPS 8 & SPMI Rumah Sakit"
    else:  # 5TAHUNAN
        tahun_mulai = tahun - 4
        qs = qs.filter(tanggal__year__gte=tahun_mulai, tanggal__year__lte=tahun)
        judul_periode = f"REKAPITULASI KINERJA 5 TAHUNAN SIKLUS AKREDITASI STARKES ({tahun_mulai} – {tahun})"
        sub_judul = "Fokus: Portofolio Digital Bukti Surveior Akreditasi KPS, TKRS, IPKP, PPI, MFK & Tren Pengembangan Kompetensi"

    unit_nama = unit.name if unit else "Seluruh Unit Non-Medis"
    logbooks = list(qs.prefetch_related('aktivitas_list__master', 'checklist', 'bukti'))

    # Agregat metrik
    total_logbook = len(logbooks)
    total_disetujui = sum(1 for lb in logbooks if lb.status == 'DISETUJUI')
    total_jam_dinas = sum(lb.durasi_dinas_jam for lb in logbooks)

    semua_aktivitas = []
    for lb in logbooks:
        semua_aktivitas.extend(list(lb.aktivitas_list.all()))
    total_aktivitas = len(semua_aktivitas)
    total_jam_aktivitas = sum(a.durasi_jam for a in semua_aktivitas)
    total_dokumen_bukti = sum(1 for a in semua_aktivitas if a.dokumen_bukti or a.nama_bukti)

    buffer = HttpResponse(content_type='application/pdf')
    buffer['Content-Disposition'] = f'inline; filename="rekap-kinerja-{periode.lower()}-{tahun}.pdf"'

    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4),
                            leftMargin=12 * mm, rightMargin=12 * mm,
                            topMargin=12 * mm, bottomMargin=12 * mm,
                            title=f"Rekap Kinerja {unit_nama} - {periode}")

    gaya = getSampleStyleSheet()
    h1 = ParagraphStyle('h1', parent=gaya['Title'], fontSize=13, leading=15, alignment=1)
    h2 = ParagraphStyle('h2', parent=gaya['Normal'], fontSize=9, leading=12, alignment=1, textColor=colors.navy)
    sub = ParagraphStyle('sub', parent=gaya['Normal'], fontSize=8.5, leading=11, alignment=1)
    si = ParagraphStyle('si', parent=gaya['Normal'], fontSize=7.5, leading=9.5)
    si_center = ParagraphStyle('si_center', parent=si, alignment=1)
    si_bold = ParagraphStyle('si_bold', parent=si, fontName='Helvetica-Bold')

    elemen = [
        Paragraph(f"<b>RUMAH SAKIT UMUM DAERAH</b>", h2),
        Paragraph(f"<b>{judul_periode}</b>", h1),
        Paragraph(f"<b>Unit: {unit_nama}</b>", sub),
        Paragraph(f"<i>{sub_judul}</i>", sub),
        Spacer(1, 6),
    ]

    # Ringkasan KPI Card Table
    kpi_data = [
        [
            Paragraph(f"<b>Total Entri Logbook</b><br/><font size=\"11\" color=\"navy\">{total_logbook}</font><br/><font size=\"6.5\" color=\"gray\">Disetujui: {total_disetujui}</font>", si_center),
            Paragraph(f"<b>Total Jam Dinas</b><br/><font size=\"11\" color=\"navy\">{total_jam_dinas:.1f} Jam</font><br/><font size=\"6.5\" color=\"gray\">Jam pelayanan operasional</font>", si_center),
            Paragraph(f"<b>Total Kegiatan Tercatat</b><br/><font size=\"11\" color=\"navy\">{total_aktivitas}</font><br/><font size=\"6.5\" color=\"gray\">Baris aktivitas terinci</font>", si_center),
            Paragraph(f"<b>Total Jam Aktivitas / JPL</b><br/><font size=\"11\" color=\"navy\">{total_jam_aktivitas:.1f} Jam</font><br/><font size=\"6.5\" color=\"gray\">Beban kerja produktif</font>", si_center),
            Paragraph(f"<b>Dokumen Bukti Fisik / File</b><br/><font size=\"11\" color=\"navy\">{total_dokumen_bukti}</font><br/><font size=\"6.5\" color=\"gray\">Lampiran pendukung akreditasi</font>", si_center),
        ]
    ]
    tabel_kpi = Table(kpi_data, colWidths=[54 * mm, 54 * mm, 54 * mm, 55 * mm, 55 * mm])
    tabel_kpi.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.grey),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elemen += [tabel_kpi, Spacer(1, 8)]

    # Tabel Rincian Rekap Aktivitas
    elemen += [Paragraph("<b>Matriks Rincian Pelaksanaan Tugas &amp; Tautan Standar STARKES</b>", si_bold), Spacer(1, 3)]

    baris_tabel = [[
        Paragraph("<b>No</b>", si_center),
        Paragraph("<b>Tanggal &amp; Shift</b>", si_center),
        Paragraph("<b>Pelaksana</b>", si_center),
        Paragraph("<b>Nama Aktivitas &amp; Kode Master</b>", si),
        Paragraph("<b>Uraian Detail / Notulen Kegiatan</b>", si),
        Paragraph("<b>Waktu / Durasi</b>", si_center),
        Paragraph("<b>Standar STARKES (EP)</b>", si),
        Paragraph("<b>Dokumen Bukti</b>", si),
    ]]

    no = 1
    for lb in logbooks:
        pelaksana_lb = lb.pegawai.nama_lengkap if lb.pegawai_id else (lb.pelaksana_nama or '—')
        tgl_str = f"{lb.tanggal:%d/%m/%Y}<br/><font size=\"6.5\" color=\"gray\">Shift {lb.shift}</font>"
        for akt in lb.aktivitas_list.all():
            wkt = akt.waktu_display or '—'
            if akt.durasi_jam > 0:
                wkt += f"<br/>({akt.durasi_jam} jam)"
            nama_full = akt.nama_aktivitas
            if akt.master:
                nama_full = f"<b>[{akt.master.kode}]</b> {nama_full}"

            bukti_str = akt.nama_bukti or (akt.dokumen_bukti.name if akt.dokumen_bukti else '—')

            baris_tabel.append([
                Paragraph(str(no), si_center),
                Paragraph(tgl_str, si_center),
                Paragraph(pelaksana_lb, si),
                Paragraph(nama_full, si),
                Paragraph(akt.detail_uraian or '—', si),
                Paragraph(wkt, si_center),
                Paragraph(akt.ep_starkes or '—', si),
                Paragraph(bukti_str, si),
            ])
            no += 1

    if len(baris_tabel) == 1:
        baris_tabel.append([
            Paragraph("—", si_center),
            Paragraph("—", si_center),
            Paragraph("—", si_center),
            Paragraph("<i>Belum ada catatan aktivitas pada periode ini</i>", si),
            Paragraph("—", si),
            Paragraph("—", si_center),
            Paragraph("—", si),
            Paragraph("—", si),
        ])

    tabel_rekap = Table(
        baris_tabel,
        repeatRows=1,
        colWidths=[8 * mm, 24 * mm, 32 * mm, 54 * mm, 68 * mm, 22 * mm, 35 * mm, 29 * mm]
    )
    tabel_rekap.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eef5')),
        ('GRID', (0, 0), (-1, -1), 0.3, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 2.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
    ]))
    elemen += [tabel_rekap, Spacer(1, 10)]

    # Tanda tangan pengesahan pimpinan
    ttd_rekap = [
        [
            Paragraph(f"Mengetahui,<br/><b>Direktur / Wakil Direktur</b><br/><br/><br/><br/><br/><u>dr. H. Supriyanto, Sp.B, FINACS, M.Kes</u><br/><font size=\"7\">NIP. 196805141998031004</font>", si_center),
            Paragraph(f"Penyusun / Penanggung Jawab,<br/><b>Kepala {unit_nama}</b><br/><br/><br/><br/><br/><u>{request.user.get_full_name() or request.user.username}</u><br/><font size=\"7\">NIP. " + (getattr(getattr(request.user, 'pegawai', None), 'nip', '') or '—') + "</font>", si_center),
        ]
    ]
    tabel_ttd_rekap = Table(ttd_rekap, colWidths=[136 * mm, 136 * mm])
    tabel_ttd_rekap.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elemen += [tabel_ttd_rekap]

    doc.build(elemen)
    return buffer


# ---------------------------------------------------------------------------
# API & Pengelolaan Aktivitas Harian Logbook
# ---------------------------------------------------------------------------

@login_required
def logbook_nonmedis_api_master_aktivitas(request):
    """API JSON untuk autocomplete dan template master aktivitas."""
    kategori = request.GET.get('kategori', '').strip().upper()
    qs = MasterAktivitasNonMedis.objects.filter(is_active=True)
    if kategori:
        qs = qs.filter(kategori_unit=kategori)

    items = [
        {
            'id': m.id,
            'kode': m.kode,
            'kategori_unit': m.kategori_unit,
            'nama': m.nama,
            'deskripsi': m.deskripsi,
            'ep_rekomendasi': m.ep_rekomendasi,
            'standar_terkait': m.standar_terkait,
            'urutan': m.urutan,
        }
        for m in qs
    ]
    return JsonResponse({'items': items})


@login_required
def logbook_nonmedis_tambah_aktivitas(request, pk):
    """Tambah baris aktivitas harian ke logbook non-medis beserta upload bukti."""
    entry = get_object_or_404(LogbookNonMedis, pk=pk)
    _cek(request.user, entry)
    if not (_boleh_isi(request.user, entry) and entry.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    if request.method == 'POST':
        master_id = request.POST.get('master_id', '').strip() or None
        master = MasterAktivitasNonMedis.objects.filter(pk=master_id).first() if master_id else None

        nama_aktivitas = request.POST.get('nama_aktivitas', '').strip()
        if not nama_aktivitas and master:
            nama_aktivitas = master.nama
        if not nama_aktivitas:
            messages.error(request, 'Nama aktivitas wajib diisi.')
            return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)

        jam_mulai_teks = request.POST.get('jam_mulai', '').strip()
        jam_selesai_teks = request.POST.get('jam_selesai', '').strip()
        jam_mulai = None
        jam_selesai = None
        try:
            if jam_mulai_teks:
                jam_mulai = time.fromisoformat(jam_mulai_teks)
        except (ValueError, TypeError):
            pass
        try:
            if jam_selesai_teks:
                jam_selesai = time.fromisoformat(jam_selesai_teks)
        except (ValueError, TypeError):
            pass

        detail_uraian = request.POST.get('detail_uraian', '').strip()
        ep_starkes = request.POST.get('ep_starkes', '').strip()
        if not ep_starkes:
            ep_starkes = resolve_ep_aktivitas(master=master, nama=nama_aktivitas, uraian=detail_uraian)

        pelaksana_nama = request.POST.get('pelaksana_nama', '').strip()
        if not pelaksana_nama:
            pelaksana_nama = entry.pelaksana_nama or request.user.get_full_name() or request.user.username

        nama_bukti = request.POST.get('nama_bukti', '').strip()
        berkas = request.FILES.get('dokumen_bukti')
        if berkas:
            from .file_security import sanitize_filename, validate_uploaded_file
            sah, pesan = validate_uploaded_file(berkas)
            if not sah:
                messages.error(request, f'Berkas bukti ditolak: {pesan}')
                return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)
            berkas.name = sanitize_filename(berkas.name)

        next_urutan = (entry.aktivitas_list.aggregate(models.Max('urutan'))['urutan__max'] or 0) + 1

        row = AktivitasNonMedis.objects.create(
            logbook=entry,
            master=master,
            urutan=next_urutan,
            jam_mulai=jam_mulai,
            jam_selesai=jam_selesai,
            nama_aktivitas=nama_aktivitas[:250],
            detail_uraian=detail_uraian,
            ep_starkes=ep_starkes[:120],
            pelaksana_nama=pelaksana_nama[:150],
            nama_bukti=nama_bukti[:200],
            dokumen_bukti=berkas,
        )
        _catat(request.user, 'CREATE', row, f'Aktivitas logbook #{row.urutan} ditambahkan')
        messages.success(request, f'Aktivitas "{nama_aktivitas}" berhasil ditambahkan.')

    return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)


@login_required
def logbook_nonmedis_hapus_aktivitas(request, pk, aktivitas_id):
    """Hapus baris aktivitas harian dari logbook draf."""
    entry = get_object_or_404(LogbookNonMedis, pk=pk)
    _cek(request.user, entry)
    if not (_boleh_isi(request.user, entry) and entry.boleh_ubah):
        raise PermissionDenied('Logbook ini sudah dikunci.')

    row = get_object_or_404(entry.aktivitas_list, pk=aktivitas_id)
    nama = row.nama_aktivitas
    row.delete()
    _catat(request.user, 'DELETE', entry, f'Aktivitas "{nama}" dihapus')
    messages.success(request, f'Aktivitas "{nama}" telah dihapus.')
    return redirect('akreditasi:logbook_nonmedis_detail', pk=entry.pk)
