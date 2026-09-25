"""
Fase 2 — Views Manajemen Risiko PDCA + Insiden Keselamatan
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone

from .risiko_models import RisikoUnit, TindakLanjutRisiko, InsidenKeselamatan
from .models import UnitKerja, AuditLog


# ── helpers ──────────────────────────────────────────────────────────────

def _risk_matrix_summary(qs):
    """Build 5×5 matrix counts from a queryset of RisikoUnit."""
    matrix = {}
    for d in range(1, 6):
        for p in range(1, 6):
            matrix[(d, p)] = 0
    for r in qs.values('dampak', 'probabilitas').annotate(n=Count('id')):
        matrix[(r['dampak'], r['probabilitas'])] = r['n']
    return matrix


def _skor_color(skor):
    if skor >= 20:
        return '#dc2626'
    if skor >= 15:
        return '#ea580c'
    if skor >= 10:
        return '#ca8a04'
    if skor >= 5:
        return '#16a34a'
    return '#64748b'


def _skor_label(skor):
    if skor >= 20:
        return 'SANGAT TINGGI'
    if skor >= 15:
        return 'TINGGI'
    if skor >= 10:
        return 'SEDANG'
    if skor >= 5:
        return 'RENDAH'
    return 'SANGAT RENDAH'


STATUS_BADGES = {
    'IDENTIFIKASI': 'secondary',
    'PLAN': 'primary',
    'DO': 'warning',
    'EVALUASI': 'purple',
    'SELESAI': 'success',
    'ACCEPTED': 'teal',
}


def _log(user, aksi, obj, detail=''):
    AuditLog.objects.create(
        user=user,
        aksi=aksi,
        model_name=obj.__class__.__name__,
        object_repr=str(obj)[:250],
        detail=detail,
    )


# ── 1. Daftar Risiko ────────────────────────────────────────────────────

@login_required
def risiko_daftar(request):
    qs = RisikoUnit.objects.select_related('unit').all()

    # Filters
    unit_id = request.GET.get('unit')
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    kategori = request.GET.get('kategori')

    if unit_id:
        qs = qs.filter(unit_id=unit_id)
    if tahun:
        qs = qs.filter(tahun=tahun)
    if status:
        qs = qs.filter(status=status)
    if kategori:
        qs = qs.filter(kategori_risiko=kategori)

    matrix = _risk_matrix_summary(qs)
    units = UnitKerja.objects.all()
    tahun_list = RisikoUnit.objects.values_list('tahun', flat=True).distinct().order_by('-tahun')

    ctx = {
        'risiko_list': qs,
        'matrix': matrix,
        'units': units,
        'tahun_list': tahun_list,
        'status_choices': RisikoUnit.STATUS_CHOICES,
        'kategori_choices': RisikoUnit.KATEGORI_CHOICES,
        'status_badges': STATUS_BADGES,
        'skor_color': _skor_color,
        'filter_unit': unit_id or '',
        'filter_tahun': tahun or '',
        'filter_status': status or '',
        'filter_kategori': kategori or '',
    }
    return render(request, 'akreditasi/risiko_daftar.html', ctx)


# ── 2. Input Risiko Baru ─────────────────────────────────────────────────

@login_required
def risiko_input(request):
    units = UnitKerja.objects.all()

    if request.method == 'POST':
        try:
            risiko = RisikoUnit(
                unit_id=int(request.POST['unit']),
                tahun=int(request.POST['tahun']),
                periode=request.POST['periode'],
                kategori_risiko=request.POST['kategori_risiko'],
                jenis_risiko=request.POST['jenis_risiko'],
                deskripsi_risiko=request.POST['deskripsi_risiko'],
                dampak=int(request.POST['dampak']),
                probabilitas=int(request.POST['probabilitas']),
                strategi_mitigasi=request.POST['strategi_mitigasi'],
                rencana_aksi=request.POST['rencana_aksi'],
                pj_mitigasi=request.POST['pj_mitigasi'],
                target_selesai=request.POST.get('target_selesai') or None,
                status='IDENTIFIKASI',
                created_by=request.user,
            )
            risiko.full_clean()
            risiko.save()
            _log(request.user, 'CREATE', risiko, 'Input risiko baru')
            messages.success(request, 'Risiko berhasil ditambahkan.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    ctx = {
        'units': units,
        'periode_choices': RisikoUnit.PERIODE_CHOICES,
        'kategori_choices': RisikoUnit.KATEGORI_CHOICES,
        'strategi_choices': RisikoUnit.STRATEGI_CHOICES,
    }
    return render(request, 'akreditasi/risiko_form.html', ctx)


# ── 3. Detail Risiko ─────────────────────────────────────────────────────

@login_required
def risiko_detail(request, risiko_id):
    risiko = get_object_or_404(RisikoUnit.objects.select_related('unit'), pk=risiko_id)
    tindak_lanjut = risiko.tindak_lanjut.all()

    # Tambah tindak lanjut inline
    if request.method == 'POST':
        try:
            last_urutan = tindak_lanjut.order_by('-urutan').values_list('urutan', flat=True).first() or 0
            tl = TindakLanjutRisiko(
                risiko=risiko,
                urutan=last_urutan + 1,
                aksi=request.POST['aksi'],
                status_aksi=request.POST.get('status_aksi', 'BELUM'),
                tanggal_mulai=request.POST.get('tanggal_mulai') or None,
                tanggal_selesai=request.POST.get('tanggal_selesai') or None,
                catatan=request.POST.get('catatan', ''),
            )
            tl.full_clean()
            tl.save()
            _log(request.user, 'CREATE', tl, f'Tindak lanjut #{tl.urutan}')
            messages.success(request, 'Tindak lanjut ditambahkan.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except Exception as e:
            messages.error(request, f'Gagal: {e}')

    # Build risk matrix 5×5 for this risiko's position
    matrix = {}
    for d in range(1, 6):
        for p in range(1, 6):
            skor = d * p
            matrix[(d, p)] = {
                'skor': skor,
                'color': _skor_color(skor),
                'is_current': (d == risiko.dampak and p == risiko.probabilitas),
            }

    ctx = {
        'risiko': risiko,
        'tindak_lanjut': tindak_lanjut,
        'matrix': matrix,
        'status_badges': STATUS_BADGES,
        'status_aksi_choices': TindakLanjutRisiko.STATUS_AKSI_CHOICES,
    }
    return render(request, 'akreditasi/risiko_detail.html', ctx)


# ── 4. Evaluasi Risiko ───────────────────────────────────────────────────

@login_required
def risiko_evaluasi(request, risiko_id):
    risiko = get_object_or_404(RisikoUnit.objects.select_related('unit'), pk=risiko_id)

    if request.method == 'POST':
        try:
            risiko.dampak_residual = int(request.POST['dampak_residual'])
            risiko.probabilitas_residual = int(request.POST['probabilitas_residual'])
            risiko.status = 'EVALUASI'
            risiko.full_clean()
            risiko.save()
            _log(request.user, 'UPDATE', risiko, 'Evaluasi residual risk')
            messages.success(request, 'Evaluasi risiko disimpan.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except Exception as e:
            messages.error(request, f'Gagal: {e}')

    ctx = {
        'risiko': risiko,
        'status_badges': STATUS_BADGES,
    }
    return render(request, 'akreditasi/risiko_evaluasi.html', ctx)


# ── 5. Lapor Insiden ─────────────────────────────────────────────────────

@login_required
def insiden_lapor(request):
    units = UnitKerja.objects.all()

    if request.method == 'POST':
        try:
            insiden = InsidenKeselamatan(
                unit_id=request.POST.get('unit') or None,
                tanggal_kejadian=request.POST['tanggal_kejadian'],
                jenis_insiden=request.POST['jenis_insiden'],
                tingkat_keparahan=request.POST['tingkat_keparahan'],
                lokasi_kejadian=request.POST['lokasi_kejadian'],
                deskripsi_kejadian=request.POST['deskripsi_kejadian'],
                tindakan_segera=request.POST.get('tindakan_segera', ''),
                pasien_terpapar='pasien_terpapar' in request.POST,
                pelapor_anonim=True,
            )
            insiden.full_clean()
            insiden.save()
            _log(request.user, 'CREATE', insiden, 'Laporan insiden anonim')
            messages.success(request, 'Laporan insiden berhasil dikirim.')
            return redirect('akreditasi:insiden_lapor')
        except Exception as e:
            messages.error(request, f'Gagal: {e}')

    ctx = {
        'units': units,
        'jenis_choices': InsidenKeselamatan.JENIS_CHOICES,
        'keparahan_choices': InsidenKeselamatan.KEPARAHAN_CHOICES,
    }
    return render(request, 'akreditasi/insiden_form.html', ctx)
