"""
Fase 2 — Views Manajemen Risiko PDCA + Insiden Keselamatan
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from django.views.decorators.http import require_GET

from .risiko_models import RisikoUnit, TindakLanjutRisiko, InsidenKeselamatan, IndikatorMutu
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


# ── 0. AJAX: Indikator Mutu per Unit (filter dropdown) ─────────────────

# Preset rencana aksi realistis per jenis indikator (kode prefix → preset)
_RENCANA_AKSI_PRESET = {
    # Farmasi
    'IMP-FARM-01': [
        'Review alur antrian pendaftaran & dispensing obat jadi',
        'Optimalkan pra-dispensing dan pembagian shift apoteker',
        'Implementasi sistem pemrosesan resep digital (e-prescribing)',
        'Edukasi pasien terkait estimasi waktu tunggu via display antrian',
    ],
    'IMP-FARM-02': [
        'Audit proses peracikan obat dan identifikasi bottleneck',
        'Tambah staf asisten apoteker saat jam puncak pelayanan',
        'Siapkan bahan baku racikan pre-batch untuk formulasi umum',
    ],
    'IMP-FARM-03': [
        'Lakukan root cause analysis (RCA) setiap kejadian medication error',
        'Implementasi double-check 2 apoteker untuk obat LASA & high-alert',
        'Pasang stiker High Alert & LASA sesuai panduan KARS SKP 3',
        'Edukasi ulang staf farmasi tentang 6 benar pemberian obat',
    ],
    # Laboratorium
    'IMP-LAB-01': [
        'Audit proses pre-analitik: waktu pengambilan sampel hingga pemeriksaan',
        'Kalibrasi rutin alat laboratorium dan validasi reagen',
        'Optimalkan alur pengiriman sampel urgent dari IGD/ICU',
    ],
    # IBS
    'IMP-IBS-01': [
        'Sosialisasi ulang Surgical Safety Checklist (SSC) ke seluruh tim OK',
        'Tunjuk PIC auditor SSC per sesi operasi',
        'Lakukan audit SSC mingguan & feedback langsung ke tim bedah',
    ],
    'IMP-IBS-02': [
        'Implementasi bundle IDO: antibiotik profilaksis <60 menit pre-insisi',
        'Audit kepatuhan teknik aseptik dan preparasi kulit pasien',
        'Monitor suhu & kadar glukosa intraoperatif sesuai bundle IDO KARS',
        'Review dan perbarui SPO perawatan luka post-operasi',
    ],
    # ICU
    'IMP-ICU-01': [
        'Implementasi bundle VAP: elevasi kepala 30-45°, oral hygiene Chlorhexidine',
        'Audit kepatuhan bundle VAP harian oleh PJ infeksi ICU',
        'Review sedasi & target weaning ventilator setiap hari',
    ],
    'IMP-ICU-02': [
        'Implementasi bundle CAUTI: perawatan kateter steril harian',
        'Evaluasi indikasi pemasangan & rencana pencabutan kateter setiap hari',
        'Audit kepatuhan hand hygiene staf ICU sebelum/sesudah intervensi',
    ],
    # PPI (umum)
    'DEFAULT_PPI': [
        'Tingkatkan kepatuhan hand hygiene sesuai 5 Momen WHO',
        'Laksanakan audit PPI mingguan & feedback ke unit',
        'Update SPO penanganan limbah medis & APD sesuai PMK 27/2017',
        'Sosialisasi bundle infeksi terkait layanan kesehatan (HAIS)',
    ],
    # Mutu umum
    'DEFAULT': [
        'Lakukan analisis akar masalah (RCA/Fishbone) atas capaian yang belum tercapai',
        'Susun rencana PDCA bulanan: Plan→Do→Check→Act',
        'Lakukan supervisi dan coaching langsung kepada staf pelaksana',
        'Evaluasi capaian indikator per bulan di rapat mutu unit',
        'Dokumentasikan setiap perbaikan sebagai bukti EP akreditasi',
    ],
}


def _get_preset_rencana_aksi(kode_indikator: str) -> list:
    """Return daftar preset rencana aksi berdasarkan kode indikator."""
    if kode_indikator in _RENCANA_AKSI_PRESET:
        return _RENCANA_AKSI_PRESET[kode_indikator]
    # Coba prefix kategori (IMP-FARM, IMP-IBS, dst.)
    prefix = '-'.join(kode_indikator.split('-')[:2]) if '-' in kode_indikator else ''
    # Cek PPI terkait
    if 'PPI' in kode_indikator.upper() or 'VAP' in kode_indikator.upper() or 'IDO' in kode_indikator.upper():
        return _RENCANA_AKSI_PRESET['DEFAULT_PPI']
    return _RENCANA_AKSI_PRESET['DEFAULT']


@login_required
@require_GET
def api_indikator_by_unit(request):
    """AJAX: Return daftar IndikatorMutu aktif berdasarkan unit_id.
    Tanpa unit_id → return semua. Termasuk preset rencana aksi per indikator.
    """
    unit_id = request.GET.get('unit_id')
    qs = IndikatorMutu.objects.filter(aktif=True).select_related('unit')
    if unit_id:
        # Tampilkan indikator milik unit ini + indikator INM global (unit=null)
        qs = qs.filter(Q(unit_id=unit_id) | Q(unit__isnull=True))
    qs = qs.order_by('jenis', 'kode_indikator')

    data = []
    for ind in qs:
        # Prioritas: ambil rencana aksi dari field DB jika ada
        if hasattr(ind, 'rencana_aksi') and ind.rencana_aksi and ind.rencana_aksi.strip():
            import re as _re
            presets = [l.strip() for l in ind.rencana_aksi.splitlines() if l.strip() and not l.strip().isdigit()]
            presets = [_re.sub(r'^\d+[\.\)]\s*', '', p) for p in presets]
        else:
            presets = _get_preset_rencana_aksi(ind.kode_indikator)

        data.append({
            'id': ind.id,
            'kode': ind.kode_indikator,
            'nama': ind.nama_indikator,
            'jenis': ind.get_jenis_display(),
            'target': float(ind.target_nilai),
            'satuan': ind.satuan,
            'unit_name': ind.unit.name if ind.unit else 'Global / Nasional',
            'pj': getattr(ind, 'pj', '') or '',
            'preset_rencana_aksi': presets,
        })
    return JsonResponse({'indikator': data})




@login_required
def risiko_daftar(request):
    profile = getattr(request.user, 'profile', None)
    qs = RisikoUnit.objects.select_related('unit').all()

    # Scope filtering untuk unit-scoped users
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja

        # Kumpulkan ID: unit sendiri + anak (bawahan) + semua leluhur (parent chain)
        # Sehingga risiko yang di-assign ke bidang/direktorat di atasnya tetap terlihat
        def _collect_ids(unit):
            ids = {unit.id}
            # turun ke anak
            for child in UnitKerja.objects.filter(parent=unit).values_list('id', flat=True):
                ids.add(child)
            # naik ke parent chain
            cur = unit.parent
            while cur:
                ids.add(cur.id)
                cur = cur.parent
            return list(ids)

        unit_ids = _collect_ids(user_unit)
        units = UnitKerja.objects.filter(id__in=unit_ids)

        unit_id = request.GET.get('unit')
        if not unit_id:
            qs = qs.filter(unit_id__in=unit_ids)
            default_filter_unit = str(user_unit.id)
        else:
            qs = qs.filter(unit_id=unit_id)
            default_filter_unit = unit_id
    else:
        units = UnitKerja.objects.all()
        unit_id = request.GET.get('unit')
        if unit_id:
            qs = qs.filter(unit_id=unit_id)
        default_filter_unit = unit_id or ''

    # Filters
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    kategori = request.GET.get('kategori')
    if tahun:
        qs = qs.filter(tahun=tahun)
    if status:
        qs = qs.filter(status=status)
    if kategori:
        qs = qs.filter(kategori_risiko=kategori)

    matrix = _risk_matrix_summary(qs)
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
        'filter_unit': default_filter_unit,
        'filter_tahun': tahun or '',
        'filter_status': status or '',
        'filter_kategori': kategori or '',
    }
    return render(request, 'akreditasi/risiko_daftar.html', ctx)


# ── 2. Input Risiko Baru ─────────────────────────────────────────────────

@login_required
def risiko_input(request):
    profile = getattr(request.user, 'profile', None)
    # Unit-scoped user: hanya unitnya sendiri + child units
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        unit_ids = [user_unit.id] + list(UnitKerja.objects.filter(parent=user_unit).values_list('id', flat=True))
        units = UnitKerja.objects.filter(id__in=unit_ids)
        default_unit_id = user_unit.id
    else:
        units = UnitKerja.objects.all()
        default_unit_id = None

    if request.method == 'POST':
        try:
            indikator_id = request.POST.get('indikator_mutu_terkait') or None
            target_capaian = request.POST.get('target_capaian_indikator') or None

            # Handle manual indikator mutu — append marker to deskripsi_risiko
            indikator_manual = (request.POST.get('indikator_mutu_manual') or '').strip()

            # Handle multiple or single jenis_risiko
            jenis_list = request.POST.getlist('jenis_risiko')
            if len(jenis_list) > 1:
                jenis_val = '\n'.join([j.strip() for j in jenis_list if j.strip()])
            elif len(jenis_list) == 1:
                jenis_val = jenis_list[0].strip()
            else:
                jenis_val = (request.POST.get('jenis_risiko') or '').strip()

            risiko = RisikoUnit(
                unit_id=int(request.POST['unit']),
                tahun=int(request.POST['tahun']),
                periode=request.POST['periode'],
                kategori_risiko=request.POST['kategori_risiko'],
                jenis_risiko=jenis_val,
                masalah=request.POST.get('masalah', '').strip(),
                data_pendukung=(request.POST.get('data') or request.POST.get('data_pendukung') or '').strip(),
                deskripsi_risiko=(request.POST['deskripsi_risiko'] + (f"\n\n[Indikator Mutu Manual: {indikator_manual}]" if (indikator_manual and not indikator_id) else '')),
                dampak=int(request.POST['dampak']),
                probabilitas=int(request.POST['probabilitas']),
                indikator_mutu_terkait_id=int(indikator_id) if indikator_id else None,
                target_capaian_indikator=float(target_capaian) if target_capaian else None,
                strategi_mitigasi=request.POST['strategi_mitigasi'],
                rencana_aksi=request.POST['rencana_aksi'],
                pj_mitigasi=request.POST['pj_mitigasi'],
                biaya_mitigasi=request.POST.get('biaya_mitigasi') or 0,
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

    from .risiko_models import IndikatorMutu
    indikator_list = IndikatorMutu.objects.filter(aktif=True).order_by('jenis', 'kode_indikator')

    ctx = {
        'units': units,
        'default_unit_id': default_unit_id,
        'periode_choices': RisikoUnit.PERIODE_CHOICES,
        'kategori_choices': RisikoUnit.KATEGORI_CHOICES,
        'strategi_choices': RisikoUnit.STRATEGI_CHOICES,
        'indikator_list': indikator_list,
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
