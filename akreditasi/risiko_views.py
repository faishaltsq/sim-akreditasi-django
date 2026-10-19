"""
Fase 2 — Views Manajemen Risiko PDCA + Insiden Keselamatan
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Count, Q, Exists, OuterRef
from django.utils import timezone
from django.core.paginator import Paginator
from django.views.decorators.http import require_GET, require_POST
from django.core.exceptions import ValidationError
from decimal import Decimal

from .ep_sync import bukti_ringkas
from .risiko_models import RisikoUnit, TindakLanjutRisiko, InsidenKeselamatan, IndikatorMutu, CatatanIndikator
from .models import UnitKerja, AuditLog, Category, StandardItem
from .indikator_views import _is_manager


# ── helpers ──────────────────────────────────────────────────────────────

def _format_rupiah(val):
    """Format angka nominal menjadi format Rupiah Indonesia (cth: Rp 5.000.000)."""
    if not val:
        return "Rp 0"
    try:
        val_float = float(val)
        return f"Rp {val_float:,.0f}".replace(",", ".")
    except (ValueError, TypeError):
        return f"Rp {val}"

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
    """AJAX: daftar IndikatorMutu aktif berdasarkan unit_id, jenis, dan tahun.

    Dipakai form risiko (unit_id) dan filter dashboard (jenis + tahun).
    Menyertakan penanda punya_data agar UI bisa membedakan indikator yang
    sudah diukur dari yang belum.
    """
    unit_id = request.GET.get('unit_id')
    jenis = request.GET.get('jenis', '')
    try:
        tahun = int(request.GET.get('tahun') or 0)
    except (ValueError, TypeError):
        tahun = 0

    qs = IndikatorMutu.objects.filter(aktif=True).select_related('unit')
    if unit_id:
        # Tampilkan indikator milik unit ini + indikator INM global (unit=null)
        qs = qs.filter(Q(unit_id=unit_id) | Q(unit__isnull=True))
    if jenis:
        _JENIS_MAP = {'INM': ['INM', 'NASIONAL'], 'IMRS': ['IMRS', 'IMP_RS'], 'IMU': ['IMU', 'IMP_UNIT']}
        qs = qs.filter(jenis__in=_JENIS_MAP.get(jenis, [jenis]))
    qs = qs.order_by('jenis', 'kode_indikator')

    # Fallback: jika unit ada tapi tidak punya indikator sama sekali,
    # tampilkan semua indikator NASIONAL (INM) sebagai indikator universal
    if unit_id and not qs.exists():
        qs = IndikatorMutu.objects.filter(aktif=True, jenis='NASIONAL').order_by('kode_indikator')

    if tahun:
        qs = qs.annotate(punya_data=Exists(
            CatatanIndikator.objects.filter(indikator=OuterRef('pk'), tahun=tahun)))

    # Fallback: jika unit ada tapi tidak punya indikator sama sekali,
    # tampilkan semua indikator NASIONAL (INM) sebagai indikator universal
    if unit_id and not qs.exists():
        qs = IndikatorMutu.objects.filter(aktif=True, jenis='NASIONAL').order_by('kode_indikator')

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
            'jenis_code': ind.jenis,
            'target': float(ind.target_nilai),
            'satuan': ind.satuan,
            'unit_name': ind.unit.name if ind.unit else 'Global / Nasional',
            'pj': getattr(ind, 'pj', '') or '',
            'preset_rencana_aksi': presets,
            'punya_data': bool(getattr(ind, 'punya_data', False)) if tahun else None,
            'arah': getattr(ind, 'arah_target', 'MIN'),
        })
    return JsonResponse({'indikator': data})




@login_required
def risiko_daftar(request):
    profile = getattr(request.user, 'profile', None)
    qs = RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'created_by') \
        .prefetch_related('tindak_lanjut__ep_terkait__category').all()

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

    # Serialisasi matrix ke JSON untuk heatmap interaktif
    import json as _json
    matrix_json = _json.dumps({f"{d},{p}": cnt for (d, p), cnt in matrix.items()})

    # Residual risk matrix
    residual_matrix = {}
    for d in range(1, 6):
        for p in range(1, 6):
            residual_matrix[(d, p)] = 0
    residual_qs = qs.filter(
        dampak_residual__isnull=False, probabilitas_residual__isnull=False
    ).values('dampak_residual', 'probabilitas_residual').annotate(n=Count('id'))
    for r in residual_qs:
        residual_matrix[(r['dampak_residual'], r['probabilitas_residual'])] = r['n']
    residual_matrix_json = _json.dumps({f"{d},{p}": cnt for (d, p), cnt in residual_matrix.items()})

    tahun_list = RisikoUnit.objects.values_list('tahun', flat=True).distinct().order_by('-tahun')

    ctx = {
        'risiko_list': qs,
        'matrix': matrix,
        'matrix_json': matrix_json,
        'residual_matrix_json': residual_matrix_json,
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

            # ── Section C: FMEA & RCA ────────────────────────────────────────
            metode_evaluasi = (request.POST.get('metode_evaluasi') or 'STANDAR').strip()
            if metode_evaluasi not in ('STANDAR', 'FMEA', 'RCA'):
                metode_evaluasi = 'STANDAR'

            # Tim evaluasi: ambil dari field sesuai metode yang dipilih
            if metode_evaluasi == 'FMEA':
                tim_evaluasi = (request.POST.get('tim_evaluasi_fmea') or '').strip()
            elif metode_evaluasi == 'RCA':
                tim_evaluasi = (request.POST.get('tim_evaluasi_rca') or '').strip()
            else:
                tim_evaluasi = ''

            # Deteksi FMEA & RPN
            deteksi_fmea = None
            if metode_evaluasi == 'FMEA':
                det_raw = (request.POST.get('deteksi_fmea') or '').strip()
                try:
                    deteksi_fmea = int(det_raw) if det_raw else 3
                except ValueError:
                    deteksi_fmea = 3

            dampak_val = int(request.POST['dampak'])
            prob_val = int(request.POST['probabilitas'])

            rpn_raw = (request.POST.get('rpn_fmea') or '').strip()
            try:
                rpn_fmea = int(rpn_raw) if rpn_raw else (dampak_val * prob_val * (deteksi_fmea or 1) if metode_evaluasi == 'FMEA' else None)
            except ValueError:
                rpn_fmea = dampak_val * prob_val * (deteksi_fmea or 1) if metode_evaluasi == 'FMEA' else None

            tanggal_eval_raw = (request.POST.get('tanggal_evaluasi') or '').strip()

            # Section F: Residual Risk
            dampak_res_raw = (request.POST.get('dampak_residual') or '').strip()
            prob_res_raw = (request.POST.get('probabilitas_residual') or '').strip()
            det_res_raw = (request.POST.get('deteksi_residual') or '').strip()
            dampak_res = int(dampak_res_raw) if dampak_res_raw else None
            prob_res = int(prob_res_raw) if prob_res_raw else None
            det_res = int(det_res_raw) if det_res_raw else None
            rpn_res = None
            if dampak_res and prob_res:
                if det_res:
                    rpn_res = dampak_res * prob_res * det_res
                elif metode_evaluasi == 'FMEA':
                    rpn_res = dampak_res * prob_res * (deteksi_fmea or 1)

            # Section G: Evaluasi & RTL
            eval_capaian = (request.POST.get('evaluasi_capaian') or '').strip()
            rca_ulang_val = (request.POST.get('rca_ulang') or '').strip()
            rtl_val = (request.POST.get('rencana_tindak_lanjut') or '').strip()
            pj_rtl_val = (request.POST.get('pj_rtl') or '').strip()

            status_val = 'EVALUASI' if (dampak_res and prob_res) else 'IDENTIFIKASI'

            risiko = RisikoUnit(
                unit_id=int(request.POST['unit']),
                tahun=int(request.POST['tahun']),
                periode=request.POST['periode'],
                kategori_risiko=request.POST['kategori_risiko'],
                jenis_risiko=jenis_val,
                masalah=request.POST.get('masalah', '').strip(),
                data_pendukung=(request.POST.get('data') or request.POST.get('data_pendukung') or '').strip(),
                tujuan=request.POST.get('tujuan', '').strip(),
                deskripsi_risiko=(request.POST['deskripsi_risiko'] + (f"\n\n[Indikator Mutu Manual: {indikator_manual}]" if (indikator_manual and not indikator_id) else '')),
                dampak=dampak_val,
                probabilitas=prob_val,
                pengendalian_ada=(request.POST.get('pengendalian_ada') or '').strip(),
                indikator_mutu_terkait_id=int(indikator_id) if indikator_id else None,
                target_capaian_indikator=float(target_capaian) if target_capaian else None,
                arah_capaian=(request.POST.get('arah_capaian') or '').strip()[:3],
                strategi_mitigasi=request.POST['strategi_mitigasi'],
                rencana_aksi=request.POST['rencana_aksi'],
                pj_mitigasi=request.POST['pj_mitigasi'],
                biaya_mitigasi=request.POST.get('biaya_mitigasi') or 0,
                target_selesai=request.POST.get('target_selesai') or None,
                status=status_val,
                # Section C: Metode Evaluasi
                metode_evaluasi=metode_evaluasi,
                tim_evaluasi=tim_evaluasi,
                deteksi_fmea=deteksi_fmea,
                failure_mode_fmea=(request.POST.get('failure_mode_fmea') or '').strip() if metode_evaluasi == 'FMEA' else '',
                akar_masalah_rca=(request.POST.get('akar_masalah_rca') or '').strip() if metode_evaluasi == 'RCA' else '',
                tindakan_korektif_rca=(request.POST.get('tindakan_korektif_rca') or '').strip() if metode_evaluasi == 'RCA' else '',
                rpn_fmea=rpn_fmea if metode_evaluasi == 'FMEA' else None,
                tanggal_evaluasi=tanggal_eval_raw or None,
                # Section F: Residual Risk
                dampak_residual=dampak_res,
                probabilitas_residual=prob_res,
                deteksi_residual=det_res,
                rpn_residual=rpn_res,
                # Section G: Evaluasi & RTL
                evaluasi_capaian=eval_capaian,
                rca_ulang=rca_ulang_val,
                rencana_tindak_lanjut=rtl_val,
                pj_rtl=pj_rtl_val,
                created_by=request.user,
            )
            risiko.full_clean(exclude=['bukti_data_pendukung'])
            risiko.save()
            if request.FILES.get('bukti_data_pendukung'):
                risiko.bukti_data_pendukung = request.FILES['bukti_data_pendukung']
                risiko.save(update_fields=['bukti_data_pendukung'])
            _log(request.user, 'CREATE', risiko, 'Input risiko baru')
            messages.success(request, 'Risiko berhasil ditambahkan.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    from .risiko_models import IndikatorMutu
    indikator_list = IndikatorMutu.objects.filter(aktif=True).order_by('jenis', 'kode_indikator')

    # ── Pre-fill from dashboard drill-down: ?indikator=&bulan=&tahun= ────────
    prefill_ctx = {}
    try:
        pf_ind_id = int(request.GET.get('indikator') or 0)
        pf_bulan = int(request.GET.get('bulan') or 0)
        pf_tahun = int(request.GET.get('tahun') or 0)
    except (ValueError, TypeError):
        pf_ind_id = pf_bulan = pf_tahun = 0

    if pf_ind_id and 1 <= pf_bulan <= 12 and pf_tahun:
        pf_ind = IndikatorMutu.objects.filter(pk=pf_ind_id, aktif=True).first()
        pf_cat = CatatanIndikator.objects.filter(
            indikator_id=pf_ind_id, bulan=pf_bulan, tahun=pf_tahun
        ).first() if pf_ind else None
        if pf_ind:
            capaian_txt = f"{float(pf_cat.nilai_capaian):.1f}" if pf_cat else 'belum ada data'
            prefill_ctx = {
                'prefill_indikator_id': pf_ind.pk,
                'prefill_unit_id': pf_ind.unit_id,
                'prefill_bulan': pf_bulan,
                'prefill_tahun': pf_tahun,
                'prefill_target': float(pf_ind.target_nilai),
                'prefill_masalah': (
                    f"Capaian {pf_ind.nama_indikator} bulan {pf_bulan}/{pf_tahun} sebesar "
                    f"{capaian_txt}{pf_ind.satuan or '%'} (target "
                    f"{'≤' if pf_ind.arah_target == 'MAX' else '≥'} {pf_ind.target_nilai}{pf_ind.satuan or '%'}). "
                    f"Lakukan analisis akar masalah dan susun rencana PDCA."
                ),
            }

    ctx = {
        'units': units,
        'default_unit_id': default_unit_id,
        'periode_choices': RisikoUnit.PERIODE_CHOICES,
        'kategori_choices': RisikoUnit.KATEGORI_CHOICES,
        'strategi_choices': RisikoUnit.STRATEGI_CHOICES,
        'indikator_list': indikator_list,
    }
    ctx.update(prefill_ctx)
    return render(request, 'akreditasi/risiko_form.html', ctx)


# ── 3. Detail Risiko ─────────────────────────────────────────────────────

@login_required
def risiko_detail(request, risiko_id):
    risiko = get_object_or_404(RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'created_by'), pk=risiko_id)
    tindak_lanjut = risiko.tindak_lanjut.all()

    # Tambah tindak lanjut inline
    if request.method == 'POST':
        try:
            last_urutan = tindak_lanjut.order_by('-urutan').values_list('urutan', flat=True).first() or 0
            standar_id = request.POST.get('standar_terkait') or None
            ep_id = request.POST.get('ep_terkait') or None
            # EP memutuskan standarnya bila keduanya dikirim: form memfilter EP
            # berdasarkan standar, jadi selisih berarti halaman sudah usang dan
            # EP yang menang supaya tautan tidak pernah drift.
            if ep_id:
                standar_id = StandardItem.objects.filter(pk=ep_id) \
                    .values_list('category_id', flat=True).first() or standar_id
            tl = TindakLanjutRisiko(
                risiko=risiko,
                urutan=last_urutan + 1,
                aksi=request.POST['aksi'],
                status_aksi=request.POST.get('status_aksi', 'BELUM'),
                tanggal_mulai=request.POST.get('tanggal_mulai') or None,
                tanggal_selesai=request.POST.get('tanggal_selesai') or None,
                catatan=request.POST.get('catatan', ''),
                standar_terkait_id=standar_id,
                ep_terkait_id=ep_id,
            )
            # Bukti ikut divalidasi (status SELESAI wajib punya bukti), jadi
            # filenya dipasang sebelum full_clean, bukan sesudah save.
            if request.FILES.get('bukti_upload'):
                tl.bukti_upload = request.FILES['bukti_upload']
            tl.full_clean()
            tl.save()
            _log(request.user, 'CREATE', tl, f'Tindak lanjut #{tl.urutan}')
            messages.success(request, 'Tindak lanjut ditambahkan.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except ValidationError as e:
            pesan = '; '.join(
                f'{k}: {" ".join(v)}' if k != '__all__' else ' '.join(v)
                for k, v in e.message_dict.items()) if hasattr(e, 'message_dict')                 else '; '.join(e.messages)
            messages.error(request, f'Gagal menyimpan pelaksanaan — {pesan}')
        except Exception as e:
            messages.error(request, f'Gagal: {e}')

    # Ringkasan kebutuhan bukti EP per baris. Sekali per EP, bukan sekali
    # per baris -- beberapa aksi boleh menunjuk EP yang sama.
    _ringkas_ep = {}
    tindak_lanjut = list(
        tindak_lanjut.select_related('standar_terkait', 'ep_terkait').order_by('urutan'))
    for tl in tindak_lanjut:
        if tl.ep_terkait_id and tl.ep_terkait_id not in _ringkas_ep:
            _ringkas_ep[tl.ep_terkait_id] = bukti_ringkas(tl.ep_terkait)
        tl.ep_ringkas = _ringkas_ep.get(tl.ep_terkait_id)

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
        'standar_list': Category.objects.order_by('code'),
        'ep_list': StandardItem.objects.select_related('category').order_by('category__code', 'code'),
    }
    return render(request, 'akreditasi/risiko_detail.html', ctx)


# ── 3b. Edit Risiko ──────────────────────────────────────────────────────

@login_required
def risiko_edit(request, risiko_id):
    risiko = get_object_or_404(RisikoUnit, pk=risiko_id)

    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        unit_ids = [user_unit.id] + list(UnitKerja.objects.filter(parent=user_unit).values_list('id', flat=True))
        units = UnitKerja.objects.filter(id__in=unit_ids)
    else:
        units = UnitKerja.objects.all()

    if request.method == 'POST':
        try:
            indikator_id = request.POST.get('indikator_mutu_terkait') or None
            target_capaian = request.POST.get('target_capaian_indikator') or None

            indikator_manual = (request.POST.get('indikator_mutu_manual') or '').strip()

            jenis_list = request.POST.getlist('jenis_risiko')
            if len(jenis_list) > 1:
                jenis_val = '\n'.join([j.strip() for j in jenis_list if j.strip()])
            elif len(jenis_list) == 1:
                jenis_val = jenis_list[0].strip()
            else:
                jenis_val = (request.POST.get('jenis_risiko') or '').strip()

            metode_evaluasi = (request.POST.get('metode_evaluasi') or 'STANDAR').strip()
            if metode_evaluasi not in ('STANDAR', 'FMEA', 'RCA'):
                metode_evaluasi = 'STANDAR'

            if metode_evaluasi == 'FMEA':
                tim_evaluasi = (request.POST.get('tim_evaluasi_fmea') or '').strip()
            elif metode_evaluasi == 'RCA':
                tim_evaluasi = (request.POST.get('tim_evaluasi_rca') or '').strip()
            else:
                tim_evaluasi = ''

            deteksi_fmea = None
            if metode_evaluasi == 'FMEA':
                det_raw = (request.POST.get('deteksi_fmea') or '').strip()
                try:
                    deteksi_fmea = int(det_raw) if det_raw else 3
                except ValueError:
                    deteksi_fmea = 3

            dampak_val = int(request.POST['dampak'])
            prob_val = int(request.POST['probabilitas'])

            rpn_raw = (request.POST.get('rpn_fmea') or '').strip()
            try:
                rpn_fmea = int(rpn_raw) if rpn_raw else (dampak_val * prob_val * (deteksi_fmea or 1) if metode_evaluasi == 'FMEA' else None)
            except ValueError:
                rpn_fmea = dampak_val * prob_val * (deteksi_fmea or 1) if metode_evaluasi == 'FMEA' else None

            tanggal_eval_raw = (request.POST.get('tanggal_evaluasi') or '').strip()

            dampak_res_raw = (request.POST.get('dampak_residual') or '').strip()
            prob_res_raw = (request.POST.get('probabilitas_residual') or '').strip()
            det_res_raw = (request.POST.get('deteksi_residual') or '').strip()
            dampak_res = int(dampak_res_raw) if dampak_res_raw else risiko.dampak_residual
            prob_res = int(prob_res_raw) if prob_res_raw else risiko.probabilitas_residual
            det_res = int(det_res_raw) if det_res_raw else risiko.deteksi_residual
            rpn_res = None
            if dampak_res and prob_res:
                if det_res:
                    rpn_res = dampak_res * prob_res * det_res
                elif metode_evaluasi == 'FMEA':
                    rpn_res = dampak_res * prob_res * (deteksi_fmea or 1)

            eval_capaian = (request.POST.get('evaluasi_capaian') or '').strip() or risiko.evaluasi_capaian
            rca_ulang_val = (request.POST.get('rca_ulang') or '').strip() or risiko.rca_ulang
            rtl_val = (request.POST.get('rencana_tindak_lanjut') or '').strip() or risiko.rencana_tindak_lanjut
            pj_rtl_val = (request.POST.get('pj_rtl') or '').strip() or risiko.pj_rtl

            risiko.unit_id = int(request.POST['unit'])
            risiko.tahun = int(request.POST['tahun'])
            risiko.periode = request.POST['periode']
            risiko.kategori_risiko = request.POST['kategori_risiko']
            risiko.jenis_risiko = jenis_val
            risiko.masalah = request.POST.get('masalah', '').strip()
            risiko.data_pendukung = (request.POST.get('data') or request.POST.get('data_pendukung') or '').strip()
            risiko.tujuan = request.POST.get('tujuan', '').strip()
            deskripsi_base = request.POST['deskripsi_risiko']
            risiko.deskripsi_risiko = deskripsi_base + (f"\n\n[Indikator Mutu Manual: {indikator_manual}]" if (indikator_manual and not indikator_id) else '')
            risiko.dampak = dampak_val
            risiko.probabilitas = prob_val
            risiko.pengendalian_ada = (request.POST.get('pengendalian_ada') or '').strip()
            risiko.indikator_mutu_terkait_id = int(indikator_id) if indikator_id else None
            risiko.target_capaian_indikator = float(target_capaian) if target_capaian else None
            risiko.arah_capaian = (request.POST.get('arah_capaian') or '').strip()[:3]
            risiko.strategi_mitigasi = request.POST['strategi_mitigasi']
            risiko.rencana_aksi = request.POST['rencana_aksi']
            risiko.pj_mitigasi = request.POST['pj_mitigasi']
            risiko.biaya_mitigasi = request.POST.get('biaya_mitigasi') or 0
            risiko.target_selesai = request.POST.get('target_selesai') or None
            risiko.metode_evaluasi = metode_evaluasi
            risiko.tim_evaluasi = tim_evaluasi
            risiko.deteksi_fmea = deteksi_fmea
            risiko.failure_mode_fmea = (request.POST.get('failure_mode_fmea') or '').strip() if metode_evaluasi == 'FMEA' else ''
            risiko.akar_masalah_rca = (request.POST.get('akar_masalah_rca') or '').strip() if metode_evaluasi == 'RCA' else ''
            risiko.tindakan_korektif_rca = (request.POST.get('tindakan_korektif_rca') or '').strip() if metode_evaluasi == 'RCA' else ''
            risiko.rpn_fmea = rpn_fmea if metode_evaluasi == 'FMEA' else None
            risiko.tanggal_evaluasi = tanggal_eval_raw or None
            risiko.dampak_residual = dampak_res
            risiko.probabilitas_residual = prob_res
            risiko.deteksi_residual = det_res
            risiko.rpn_residual = rpn_res
            risiko.evaluasi_capaian = eval_capaian
            risiko.rca_ulang = rca_ulang_val
            risiko.rencana_tindak_lanjut = rtl_val
            risiko.pj_rtl = pj_rtl_val

            risiko.full_clean(exclude=['bukti_data_pendukung'])
            risiko.save()
            if request.FILES.get('bukti_data_pendukung'):
                risiko.bukti_data_pendukung = request.FILES['bukti_data_pendukung']
                risiko.save(update_fields=['bukti_data_pendukung'])
            _log(request.user, 'UPDATE', risiko, f'Edit risiko #{risiko_id}')
            messages.success(request, 'Risiko berhasil diperbarui.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan: {e}')

    from .risiko_models import IndikatorMutu
    indikator_list = IndikatorMutu.objects.filter(aktif=True).order_by('jenis', 'kode_indikator')

    ctx = {
        'risiko': risiko,
        'is_edit': True,
        'units': units,
        'default_unit_id': risiko.unit_id,
        'periode_choices': RisikoUnit.PERIODE_CHOICES,
        'kategori_choices': RisikoUnit.KATEGORI_CHOICES,
        'strategi_choices': RisikoUnit.STRATEGI_CHOICES,
        'indikator_list': indikator_list,
    }
    return render(request, 'akreditasi/risiko_form.html', ctx)


# ── 3c. Hapus Risiko ─────────────────────────────────────────────────────

@login_required
def risiko_hapus(request, risiko_id):
    risiko = get_object_or_404(RisikoUnit, pk=risiko_id)
    if request.method == 'POST':
        unit_name = str(risiko.unit)
        jenis = risiko.jenis_risiko[:60]
        _log(request.user, 'DELETE', risiko, f'Hapus risiko #{risiko_id}: {jenis}')
        risiko.delete()
        messages.success(request, f'Risiko "{jenis}…" dari unit {unit_name} berhasil dihapus.')
        return redirect('akreditasi:risiko_daftar')
    # GET: tampilkan halaman konfirmasi
    return render(request, 'akreditasi/risiko_hapus_konfirmasi.html', {'risiko': risiko})


# ── 4. Evaluasi Risiko ───────────────────────────────────────────────────

@login_required
def risiko_evaluasi(request, risiko_id):
    risiko = get_object_or_404(RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'created_by'), pk=risiko_id)

    if request.method == 'POST':
        try:
            risiko.dampak_residual = int(request.POST['dampak_residual'])
            risiko.probabilitas_residual = int(request.POST['probabilitas_residual'])

            det_res_raw = request.POST.get('deteksi_residual', '').strip()
            if det_res_raw:
                try:
                    risiko.deteksi_residual = int(det_res_raw)
                    risiko.rpn_residual = risiko.dampak_residual * risiko.probabilitas_residual * risiko.deteksi_residual
                except ValueError:
                    pass
            elif risiko.is_fmea:
                d = risiko.deteksi_fmea or 1
                risiko.rpn_residual = risiko.dampak_residual * risiko.probabilitas_residual * d

            # ── Penautan Indikator Mutu (bila belum tertaut) ──
            if 'indikator_mutu_terkait' in request.POST:
                link_id = (request.POST.get('indikator_mutu_terkait') or '').strip()
                risiko.indikator_mutu_terkait_id = int(link_id) if link_id else None
                tgt_raw = (request.POST.get('target_capaian_indikator') or '').strip().replace(',', '.')
                try:
                    risiko.target_capaian_indikator = Decimal(tgt_raw) if tgt_raw else None
                except (ArithmeticError, ValueError, TypeError):
                    risiko.target_capaian_indikator = None

            # ── Capaian Indikator Mutu ──
            capaian_raw = request.POST.get('capaian_nilai', '').strip()
            if capaian_raw:
                try:
                    risiko.capaian_nilai = Decimal(capaian_raw.replace(',', '.'))
                except Exception:
                    pass
            if request.FILES.get('bukti_capaian'):
                risiko.bukti_capaian = request.FILES['bukti_capaian']

            if 'jenis_dokumen_capaian' in request.POST:
                risiko.jenis_dokumen_capaian = request.POST.get('jenis_dokumen_capaian', '').strip()

            if 'evaluasi_capaian' in request.POST:
                risiko.evaluasi_capaian = request.POST.get('evaluasi_capaian', '').strip()

            # ── Pelaksanaan Tindakan (Per Item & Agregat) ──
            existing_tls = list(risiko.tindak_lanjut.all().order_by('urutan'))
            collected_statuses = []
            if existing_tls:
                for tl in existing_tls:
                    st_val = request.POST.get(f'tl_status_{tl.pk}')
                    if st_val in dict(TindakLanjutRisiko.STATUS_AKSI_CHOICES):
                        tl.status_aksi = st_val
                        tl.save(update_fields=['status_aksi'])
                        collected_statuses.append(st_val)
                    else:
                        collected_statuses.append(tl.status_aksi)
            elif risiko.rencana_aksi_list:
                # Tautan diwarisi dari indikator terkait agar pelaksanaan hasil
                # materialisasi tidak pernah yatim EP/standarnya; pilihan butir
                # pada form G.2 menimpanya kalau operator mengisinya.
                ep_warisan = risiko.indikator_mutu_terkait.ep_terkait \
                    if risiko.indikator_mutu_terkait_id else None
                for item in risiko.rencana_aksi_list:
                    idx = item['urutan']
                    st_val = request.POST.get(f'step_status_{idx}')
                    if st_val in dict(TindakLanjutRisiko.STATUS_AKSI_CHOICES):
                        ep_pilihan = ep_warisan
                        raw_ep = request.POST.get(f'step_ep_{idx}')
                        if raw_ep is not None:
                            raw_ep = raw_ep.strip()
                            if raw_ep:
                                try:
                                    ep_pilihan = StandardItem.objects.get(pk=raw_ep)
                                except (StandardItem.DoesNotExist, ValueError, TypeError):
                                    raise ValidationError(
                                        f'EP untuk butir {idx} tidak ditemukan.')
                            else:
                                # kolom sengaja dikosongkan = tanpa tautan
                                ep_pilihan = None
                        TindakLanjutRisiko.objects.create(
                            risiko=risiko,
                            urutan=idx,
                            aksi=item['text'],
                            status_aksi=st_val,
                            ep_terkait=ep_pilihan,
                            standar_terkait=ep_pilihan.category if ep_pilihan else None,
                        )
                        collected_statuses.append(st_val)

            if collected_statuses:
                if all(s == 'SELESAI' for s in collected_statuses):
                    risiko.status_pelaksanaan = 'DILAKUKAN'
                elif any(s in ('SELESAI', 'SEDANG') for s in collected_statuses):
                    risiko.status_pelaksanaan = 'SEBAGIAN'
                else:
                    risiko.status_pelaksanaan = 'TIDAK_DILAKUKAN'
            elif 'status_pelaksanaan' in request.POST:
                risiko.status_pelaksanaan = request.POST.get('status_pelaksanaan', 'DILAKUKAN')

            # ── RCA Fishbone Terstruktur ──
            if 'rca_ulang' in request.POST:
                risiko.rca_ulang = request.POST.get('rca_ulang', '').strip()

            fb = {}
            for dim in ['manpower', 'process', 'material', 'machine', 'environment', 'system']:
                val = request.POST.get(f'rca_{dim}', '').strip()
                if val:
                    fb[dim] = val
            risiko.rca_fishbone = fb

            # ── Rencana Tindak Lanjut (RTL) ──
            if 'rencana_tindak_lanjut' in request.POST:
                risiko.rencana_tindak_lanjut = request.POST.get('rencana_tindak_lanjut', '').strip()
            if 'pj_rtl' in request.POST:
                risiko.pj_rtl = request.POST.get('pj_rtl', '').strip()
            if 'deadline_rtl' in request.POST:
                risiko.deadline_rtl = request.POST.get('deadline_rtl') or None
            if 'status_rtl' in request.POST:
                risiko.status_rtl = request.POST.get('status_rtl', 'BELUM')
            if request.FILES.get('bukti_rtl'):
                risiko.bukti_rtl = request.FILES['bukti_rtl']

            risiko.status = 'EVALUASI'
            risiko.full_clean(exclude=['bukti_capaian', 'bukti_rtl'])
            risiko.save()
            _log(request.user, 'UPDATE', risiko, 'Evaluasi residual risk, RCA fishbone & RTL')
            messages.success(request, 'Evaluasi risiko, analisis RCA, dan RTL berhasil disimpan.')
            return redirect('akreditasi:risiko_detail', risiko_id=risiko.pk)
        except Exception as e:
            messages.error(request, f'Gagal menyimpan evaluasi: {e}')

    tindak_lanjut_list = list(
        risiko.tindak_lanjut.select_related('standar_terkait', 'ep_terkait').order_by('urutan'))
    rencana_aksi_items = risiko.rencana_aksi_list

    _ev = risiko.capaian_evaluasi
    target_nilai_display = _ev['target']
    arah_nilai_display = _ev['arah']
    satuan_nilai_display = _ev['satuan']
    # ponytail: nama konteks tanpa underscore awal — Django menolak
    # nama variabel template yang diawali underscore (TemplateSyntaxError).

    # G.1 kini hanya membaca: input inline capaian/bukti sudah dihapus, sumber
    # datanya halaman Input Capaian (CatatanIndikator) lewat agregat tahunan.
    # Penautan indikator dilakukan di form perencanaan/edit risiko, bukan di sini.
    agregat = None
    if risiko.indikator_mutu_terkait_id:
        agregat = risiko.indikator_mutu_terkait.agregat_capaian(risiko.tahun)

    # Daftar EP untuk picker per-butir pada form G.2.
    ep_list = StandardItem.objects.select_related('category').order_by(
        'category__order', 'code')

    ctx = {
        'risiko': risiko,
        'status_badges': STATUS_BADGES,
        'status_pelaksanaan_choices': RisikoUnit.STATUS_PELAKSANAAN_CHOICES,
        'status_rtl_choices': RisikoUnit.STATUS_RTL_CHOICES,
        'tindak_lanjut_list': tindak_lanjut_list,
        'rencana_aksi_items': rencana_aksi_items,
        'ep_list': ep_list,
        'target_nilai_display': target_nilai_display,
        'arah_nilai_display': arah_nilai_display,
        'satuan_nilai_display': satuan_nilai_display,
        'ev_capaian': _ev,
        'agregat': agregat,
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'akreditasi/risiko_evaluasi.html', ctx)


# ── 4B. Monitoring & Evaluasi Risiko (Tabel Komprehensif MONEV + RCA) ──

@login_required
def risiko_monitoring_evaluasi(request, unit_id=None):
    """
    Tabel Monitoring dan Evaluasi Risiko Mutu Lengkap sesuai standar akreditasi:
    Kolom: No, Indikator Mutu & Target, Capaian & Bukti, Pelaksanaan & Bukti, RCA (Fishbone), RTL & Bukti, Skor Sebelum vs Sesudah.
    """
    profile = getattr(request.user, 'profile', None)
    is_scoped = profile and profile.is_unit_scoped and profile.unit_kerja

    if is_scoped:
        user_unit = profile.unit_kerja
        allowed_ids = [user_unit.id] + list(UnitKerja.objects.filter(parent=user_unit).values_list('id', flat=True))
        units = UnitKerja.objects.filter(id__in=allowed_ids)
    else:
        units = UnitKerja.objects.all()
        allowed_ids = None

    # Filter parameters
    sel_unit_id = unit_id or request.GET.get('unit') or (profile.unit_kerja.id if is_scoped else None)
    sel_unit = None
    if sel_unit_id:
        try:
            sel_unit = UnitKerja.objects.get(pk=int(sel_unit_id))
        except (UnitKerja.DoesNotExist, ValueError):
            sel_unit = None

    tahun_raw = request.GET.get('tahun', '2026')
    try:
        tahun = int(tahun_raw) if tahun_raw else None
    except (ValueError, TypeError):
        tahun = None

    status_rtl = request.GET.get('status_rtl', '')
    status_pelaksanaan = request.GET.get('status_pelaksanaan', '')
    query = request.GET.get('q', '').strip()

    qs = RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'indikator_mutu_terkait__ep_terkait', 'created_by').prefetch_related('tindak_lanjut').all()

    if is_scoped and allowed_ids:
        qs = qs.filter(unit_id__in=allowed_ids)
    if sel_unit:
        qs = qs.filter(unit=sel_unit)
    if tahun:
        qs = qs.filter(tahun=tahun)
    if status_rtl:
        qs = qs.filter(status_rtl=status_rtl)
    if status_pelaksanaan:
        qs = qs.filter(status_pelaksanaan=status_pelaksanaan)
    if query:
        qs = qs.filter(
            Q(jenis_risiko__icontains=query) |
            Q(masalah__icontains=query) |
            Q(indikator_mutu_terkait__nama_indikator__icontains=query) |
            Q(rencana_aksi__icontains=query) |
            Q(rencana_tindak_lanjut__icontains=query) |
            Q(pj_rtl__icontains=query)
        )

    risiko_list = list(qs.order_by('-tahun', '-dampak', '-probabilitas'))

    # Calculate additional dynamic attributes for rendering
    total_risiko = len(risiko_list)
    rtl_selesai_count = sum(1 for r in risiko_list if r.status_rtl == 'SELESAI')
    rtl_proses_count = sum(1 for r in risiko_list if r.status_rtl == 'PROSES')
    terevaluasi_count = sum(1 for r in risiko_list if r.dampak_residual and r.probabilitas_residual)

    capaian_vals = [float(r.capaian_nilai) for r in risiko_list if r.capaian_nilai is not None]
    avg_capaian = round(sum(capaian_vals) / len(capaian_vals), 1) if capaian_vals else None

    # Prefetch tindak lanjut per risiko (model properties handle skor_* calculations)
    for r in risiko_list:
        r.daftar_tindak_lanjut = list(
            r.tindak_lanjut.select_related('standar_terkait', 'ep_terkait'))

    ctx = {
        'risiko_list': risiko_list,
        'total_risiko': total_risiko,
        'rtl_selesai_count': rtl_selesai_count,
        'rtl_proses_count': rtl_proses_count,
        'terevaluasi_count': terevaluasi_count,
        'avg_capaian': avg_capaian,
        'units': units,
        'sel_unit': sel_unit,
        'tahun': tahun,
        'status_rtl': status_rtl,
        'status_pelaksanaan': status_pelaksanaan,
        'query': query,
        'status_rtl_choices': RisikoUnit.STATUS_RTL_CHOICES,
        'status_pelaksanaan_choices': RisikoUnit.STATUS_PELAKSANAAN_CHOICES,
        'is_manager': _is_manager(request.user),
    }
    return render(request, 'akreditasi/risiko_monitoring_evaluasi.html', ctx)


@login_required
def risiko_monev_export_csv(request):
    """
    Ekspor tabel Monitoring & Evaluasi Risiko ke CSV/Excel dengan UTF-8 BOM.
    """
    import csv
    from django.http import HttpResponse

    profile = getattr(request.user, 'profile', None)
    is_scoped = profile and profile.is_unit_scoped and profile.unit_kerja

    qs = RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait').prefetch_related('tindak_lanjut').all()

    if is_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        allowed_ids = [user_unit.id] + list(UnitKerja.objects.filter(parent=user_unit).values_list('id', flat=True))
        qs = qs.filter(unit_id__in=allowed_ids)

    unit_id = request.GET.get('unit')
    if unit_id:
        qs = qs.filter(unit_id=unit_id)

    tahun_raw = request.GET.get('tahun')
    try:
        tahun = int(tahun_raw) if tahun_raw else None
    except (ValueError, TypeError):
        tahun = None

    if tahun:
        qs = qs.filter(tahun=tahun)

    status_rtl = request.GET.get('status_rtl')
    if status_rtl:
        qs = qs.filter(status_rtl=status_rtl)

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="Monev_Risiko_ARIMA_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'
    # UTF-8 BOM for Microsoft Excel
    response.write('\ufeff'.encode('utf8'))

    writer = csv.writer(response)
    writer.writerow([
        'No',
        'Unit Kerja',
        'Jenis / Deskripsi Risiko',
        'Indikator Mutu & Target',
        'Capaian Indikator Mutu (%)',
        'Pelaksanaan Tindakan (Status)',
        'Rincian Tindakan (Do)',
        'RCA (Penyebab Utama / Fishbone)',
        'RTL (Rencana Tindak Lanjut)',
        'PIC RTL',
        'Deadline RTL',
        'Status RTL',
        'Skor Risiko Awal (D x P)',
        'Skor Risiko Residual (D x P)',
        'Status Capaian',
    ])

    for i, r in enumerate(qs.order_by('-tahun', '-dampak', '-probabilitas'), start=1):
        # Indikator
        _ev = r.capaian_evaluasi
        if r.indikator_mutu_terkait:
            ind_text = (f"{r.indikator_mutu_terkait.nama_indikator} "
                        f"(Target: {'≤' if _ev['arah'] == 'MAX' else '≥'}{_ev['target']:.1f}{_ev['satuan']})"
                        if _ev['target'] is not None
                        else f"{r.indikator_mutu_terkait.nama_indikator} (Target: —)")
        else:
            ind_text = "—"

        # Capaian
        capaian_str = f"{r.capaian_nilai}%" if r.capaian_nilai is not None else "Belum Diisi"

        # Pelaksanaan
        pelaksanaan_status = r.get_status_pelaksanaan_display()
        tl_list = [f"- {tl.aksi} ({tl.get_status_aksi_display()})" for tl in r.tindak_lanjut.all()]
        tl_str = "\n".join(tl_list) if tl_list else r.rencana_aksi or "—"

        # RCA
        rca_parts = []
        if r.rca_fishbone:
            for k, v in r.rca_fishbone.items():
                rca_parts.append(f"{k.capitalize()}: {v}")
        if r.rca_ulang:
            rca_parts.append(f"RCA Ulang: {r.rca_ulang}")
        rca_str = "\n".join(rca_parts) if rca_parts else (r.akar_masalah_rca or "—")

        # Skor
        skor_awal = f"{r.dampak * r.probabilitas} ({_skor_label(r.dampak * r.probabilitas)})"
        if r.dampak_residual and r.probabilitas_residual:
            skor_res = f"{r.dampak_residual * r.probabilitas_residual} ({_skor_label(r.dampak_residual * r.probabilitas_residual)})"
        else:
            skor_res = "Belum Evaluasi"

        writer.writerow([
            i,
            r.unit.name if r.unit else "—",
            r.jenis_risiko,
            ind_text,
            capaian_str,
            pelaksanaan_status,
            tl_str,
            rca_str,
            r.rencana_tindak_lanjut or "—",
            r.pj_rtl or "—",
            r.deadline_rtl.strftime('%d/%m/%Y') if r.deadline_rtl else "—",
            r.get_status_rtl_display(),
            skor_awal,
            skor_res,
            r.capaian_status_label or 'Belum Dievaluasi',
        ])

    return response


# ── 5. Laporan Komprehensif Manajemen Risiko (5-Seksi STARKES 5.15) ─────

_KAT_PREFIX = {
    'KLINIS':               'KLN',
    'OPERASIONAL':          'OPS',
    'FINANSIAL':            'FIN',
    'REPUTASI':             'REP',
    'HUKUM_KEPATUHAN':      'HKM',
    'FASILITAS_LINGKUNGAN': 'FAL',
    'MANAJERIAL':           'MAN',
}

_KAT_LABEL_SEKSI = {
    'KLINIS':               'A. Masalah dan Data Keselamatan Pasien & Klinis',
    'OPERASIONAL':          'B. Masalah dan Data Operasional & Sarana Prasarana',
    'FASILITAS_LINGKUNGAN': 'C. Masalah dan Data Fasilitas, B3 & Lingkungan (PPI)',
    'HUKUM_KEPATUHAN':      'D. Masalah dan Data Hukum, Manajemen & Finansial',
    'FINANSIAL':            'D. Masalah dan Data Hukum, Manajemen & Finansial',
    'REPUTASI':             'E. Masalah dan Data Reputasi & Kepuasan',
    'MANAJERIAL':           'F. Masalah dan Data Manajerial',
}


@login_required
def risiko_laporan(request, unit_id=None):
    profile = getattr(request.user, 'profile', None)
    is_scoped = profile and profile.is_unit_scoped and profile.unit_kerja

    # Determine available units for filter
    if is_scoped:
        user_unit = profile.unit_kerja
        def _collect_ids(unit):
            ids = {unit.id}
            for child in UnitKerja.objects.filter(parent=unit).values_list('id', flat=True):
                ids.add(child)
            cur = unit.parent
            while cur:
                ids.add(cur.id)
                cur = cur.parent
            return list(ids)
        allowed_ids = _collect_ids(user_unit)
        units = UnitKerja.objects.filter(id__in=allowed_ids)
    else:
        units = UnitKerja.objects.all()
        allowed_ids = None

    # Resolve selected unit
    sel_unit_id = unit_id or request.GET.get('unit') or (profile.unit_kerja.id if is_scoped else None)
    sel_unit = None
    if sel_unit_id:
        try:
            sel_unit = UnitKerja.objects.get(pk=int(sel_unit_id))
        except (UnitKerja.DoesNotExist, ValueError):
            sel_unit = None

    tahun   = request.GET.get('tahun', '2026')
    periode = request.GET.get('periode', '')

    qs = RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'indikator_mutu_terkait__ep_terkait', 'created_by').prefetch_related('tindak_lanjut').all()
    if is_scoped and allowed_ids:
        qs = qs.filter(unit_id__in=allowed_ids)
    if sel_unit:
        qs = qs.filter(unit=sel_unit)
    if tahun:
        qs = qs.filter(tahun=tahun)
    if periode:
        qs = qs.filter(periode=periode)

    # Assign kode risiko: sort by skor desc, then by kategori
    risiko_list = list(qs.order_by('-dampak', '-probabilitas', 'kategori_risiko'))
    # Count per kategori prefix for sequential numbering
    kat_counter = {}
    for r in risiko_list:
        prefix = _KAT_PREFIX.get(r.kategori_risiko, 'RSK')
        kat_counter[prefix] = kat_counter.get(prefix, 0) + 1
        r.kode_risiko = f'R-{prefix}-{kat_counter[prefix]:02d}'
        r.skor_calc = r.dampak * r.probabilitas
        r.skor_color_val = _skor_color(r.skor_calc)
        r.skor_label_val = _skor_label(r.skor_calc)
        r.skor_residual_calc = (r.dampak_residual or 0) * (r.probabilitas_residual or 0) if r.dampak_residual else None
        r.rencana_list = [l.strip() for l in (r.rencana_aksi or '').splitlines() if l.strip()]

    # Section 1: group by kategori, preserving docx order
    KAT_ORDER = ['KLINIS', 'OPERASIONAL', 'FASILITAS_LINGKUNGAN', 'HUKUM_KEPATUHAN', 'FINANSIAL', 'REPUTASI', 'MANAJERIAL']
    grouped = {}
    for r in risiko_list:
        k = r.kategori_risiko
        if k not in grouped:
            grouped[k] = []
        grouped[k].append(r)
    grouped_ordered = [(k, _KAT_LABEL_SEKSI.get(k, k), grouped[k])
                       for k in KAT_ORDER if k in grouped]

    # Section 2: ranked by skor desc (already sorted)
    ranked = list(enumerate(risiko_list, 1))

    # Section 5: status summary as list of tuples for template
    status_counts_list = []
    _sc = {}
    for r in risiko_list:
        _sc[r.status] = _sc.get(r.status, 0) + 1
    for s, label in RisikoUnit.STATUS_CHOICES:
        status_counts_list.append((s, label, _sc.get(s, 0), STATUS_BADGES.get(s, 'secondary')))

    # KPI list from linked indikator mutu
    kpi_list = [(r.kode_risiko, r.indikator_mutu_terkait, r.target_capaian_indikator)
                for r in risiko_list if r.indikator_mutu_terkait]

    tahun_list = RisikoUnit.objects.values_list('tahun', flat=True).distinct().order_by('-tahun')

    total_biaya = sum((r.biaya_mitigasi or Decimal('0')) for r in risiko_list)
    total_biaya_format = _format_rupiah(total_biaya)

    ctx = {
        'sel_unit':        sel_unit,
        'units':           units,
        'tahun':           tahun,
        'periode':         periode,
        'tahun_list':      tahun_list,
        'periode_choices': RisikoUnit.PERIODE_CHOICES,
        'risiko_list':     risiko_list,
        'grouped_ordered': grouped_ordered,
        'ranked':          ranked,
        'kpi_list':        kpi_list,
        'status_counts_list': status_counts_list,
        'status_choices':  RisikoUnit.STATUS_CHOICES,
        'status_badges':   STATUS_BADGES,
        'total':           len(risiko_list),
        'total_biaya':     total_biaya,
        'total_biaya_format': total_biaya_format,
        'fmea_list':       [r for r in risiko_list if r.metode_evaluasi == 'FMEA'],
        'rca_list':        [r for r in risiko_list if r.metode_evaluasi == 'RCA'],
    }
    return render(request, 'akreditasi/risiko_laporan.html', ctx)


# ── 6. Insiden Keselamatan Pasien (IKP) ──────────────────────────────────

def _grading_pita(keparahan):
    """Return pita risiko KNKP (warna, label, aksi) berdasarkan tingkat keparahan."""
    MAP = {
        'TIDAK_CEDERA': ('biru',   'Biru',   'Investigasi sederhana oleh atasan langsung, selesai maks 7 hari'),
        'MINOR':        ('hijau',  'Hijau',  'Investigasi sederhana oleh atasan langsung, selesai maks 14 hari'),
        'MODERAT':      ('kuning', 'Kuning', 'Investigasi komprehensif / RCA oleh Tim KP, selesai maks 45 hari'),
        'MAYOR':        ('merah',  'Merah',  'Investigasi komprehensif / RCA oleh Tim KP + Direksi, selesai maks 45 hari'),
        'SENTINEL':     ('merah',  'Merah',  'RCA wajib oleh Tim KP + Direksi, lapor ke KNKP maks 2x24 jam'),
    }
    return MAP.get(keparahan, ('biru', 'Biru', '-'))


@login_required
def insiden_daftar(request):
    """Register Insiden Keselamatan Pasien — daftar, filter, statistik."""
    qs = InsidenKeselamatan.objects.select_related('unit', 'pj_investigasi').all()

    # ── Filters ──────────────────────────────────────────────────────────
    f_jenis  = request.GET.get('jenis', '')
    f_status = request.GET.get('status', '')
    f_unit   = request.GET.get('unit', '')
    f_q      = request.GET.get('q', '')

    if f_jenis:
        qs = qs.filter(jenis_insiden=f_jenis)
    if f_status:
        qs = qs.filter(status_investigasi=f_status)
    if f_unit:
        qs = qs.filter(unit_id=f_unit)
    if f_q:
        qs = qs.filter(
            Q(deskripsi_kejadian__icontains=f_q) |
            Q(lokasi_kejadian__icontains=f_q) |
            Q(tindakan_segera__icontains=f_q)
        )

    # ── Stats ────────────────────────────────────────────────────────────
    all_qs = InsidenKeselamatan.objects.all()
    stats = {
        'total':       all_qs.count(),
        'sentinel':    all_qs.filter(jenis_insiden='SENTINEL').count(),
        'ktd':         all_qs.filter(jenis_insiden='KTD').count(),
        'knc':         all_qs.filter(jenis_insiden='KNC').count(),
        'perlu_investigasi': all_qs.filter(
            status_investigasi__in=['DILAPORKAN', 'VERIFIKASI']
        ).count(),
        'selesai':     all_qs.filter(status_investigasi='SELESAI').count(),
    }

    # ── Pagination ───────────────────────────────────────────────────────
    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page', 1))

    # Add grading pita to each insiden
    for ins in page:
        pita_color, pita_label, pita_aksi = _grading_pita(ins.tingkat_keparahan)
        ins.pita_color = pita_color
        ins.pita_label = pita_label
        ins.pita_aksi  = pita_aksi

    ctx = {
        'page': page,
        'stats': stats,
        'units': UnitKerja.objects.all(),
        'jenis_choices':  InsidenKeselamatan.JENIS_CHOICES,
        'status_choices': InsidenKeselamatan.STATUS_INVESTIGASI_CHOICES,
        'f_jenis': f_jenis,
        'f_status': f_status,
        'f_unit': f_unit,
        'f_q': f_q,
    }
    return render(request, 'akreditasi/insiden_daftar.html', ctx)


@login_required
def insiden_detail(request, pk):
    """Detail lengkap insiden dengan grading pita risiko KNKP."""
    insiden = get_object_or_404(
        InsidenKeselamatan.objects.select_related('unit', 'pj_investigasi'), pk=pk
    )
    pita_color, pita_label, pita_aksi = _grading_pita(insiden.tingkat_keparahan)

    from django.contrib.auth import get_user_model
    User = get_user_model()
    staff_users = User.objects.filter(is_active=True).order_by('username')

    ctx = {
        'insiden': insiden,
        'pita_color': pita_color,
        'pita_label': pita_label,
        'pita_aksi': pita_aksi,
        'status_choices': InsidenKeselamatan.STATUS_INVESTIGASI_CHOICES,
        'staff_users': staff_users,
    }
    return render(request, 'akreditasi/insiden_detail.html', ctx)


@login_required
@require_POST
def insiden_update_status(request, pk):
    """Update status investigasi, assign PJ, flag RCA."""
    insiden = get_object_or_404(InsidenKeselamatan, pk=pk)

    new_status = request.POST.get('status_investigasi', '')
    pj_id      = request.POST.get('pj_investigasi', '')
    rca_flag   = 'rca_dilakukan' in request.POST
    catatan    = request.POST.get('catatan_investigasi', '')

    valid_statuses = [c[0] for c in InsidenKeselamatan.STATUS_INVESTIGASI_CHOICES]
    if new_status and new_status in valid_statuses:
        old_status = insiden.status_investigasi
        insiden.status_investigasi = new_status

        if pj_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                insiden.pj_investigasi = User.objects.get(pk=pj_id)
            except User.DoesNotExist:
                pass

        insiden.rca_dilakukan = rca_flag
        insiden.save()

        _log(request.user, 'UPDATE', insiden,
             f'Status: {old_status}→{new_status}. PJ: {insiden.pj_investigasi}. RCA: {rca_flag}. {catatan}')
        messages.success(request, f'Status insiden diperbarui: {insiden.get_status_investigasi_display()}')
    else:
        messages.error(request, 'Status tidak valid.')

    return redirect('akreditasi:insiden_detail', pk=pk)


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


# ── FMEA & RCA — Command Center (Section E) ──────────────────────────────

@login_required
def risiko_fmea_rca(request):
    """Pusat evaluasi mendalam: Kajian FMEA Proaktif & Investigasi RCA Reaktif.

    Menampilkan register risiko yang menggunakan metode evaluasi mendalam
    (FMEA / RCA) beserta ringkasan KPI dan filter unit/tahun/status.
    """
    profile = getattr(request.user, 'profile', None)
    qs = RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait').all()

    # ── Scope filtering (sama dengan risiko_daftar) ──────────────────────
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja

        def _collect_ids(unit):
            ids = {unit.id}
            for child in UnitKerja.objects.filter(parent=unit).values_list('id', flat=True):
                ids.add(child)
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

    # ── Filters ──────────────────────────────────────────────────────────
    tahun = request.GET.get('tahun')
    status = request.GET.get('status')
    if tahun:
        qs = qs.filter(tahun=tahun)
    if status:
        qs = qs.filter(status=status)

    tahun_list = RisikoUnit.objects.values_list('tahun', flat=True).distinct().order_by('-tahun')

    # ── Split data per metode ────────────────────────────────────────────
    fmea_list = list(qs.filter(metode_evaluasi='FMEA').order_by('-dampak', '-probabilitas'))
    rca_list = list(qs.filter(metode_evaluasi='RCA').order_by('-dampak', '-probabilitas'))

    # ── KPI Summary ──────────────────────────────────────────────────────
    kpi = {
        'total_fmea': len(fmea_list),
        'total_rca': len(rca_list),
        'fmea_selesai': sum(1 for r in fmea_list if r.status == 'SELESAI'),
        'rca_selesai': sum(1 for r in rca_list if r.status == 'SELESAI'),
        'korektif_berjalan': sum(1 for r in rca_list if r.tindakan_korektif_rca and r.status not in ('SELESAI',)),
        'fmea_berjalan': sum(1 for r in fmea_list if r.status not in ('SELESAI',)),
    }

    # RPN rata-rata untuk FMEA
    rpn_values = [r.rpn_calc for r in fmea_list if r.rpn_calc]
    kpi['rpn_avg'] = round(sum(rpn_values) / len(rpn_values)) if rpn_values else 0
    kpi['rpn_max'] = max(rpn_values) if rpn_values else 0

    # ── Top RPN FMEA (prioritas tertinggi) ───────────────────────────────
    fmea_prioritas = sorted([r for r in fmea_list if r.rpn_calc],
                            key=lambda x: x.rpn_calc, reverse=True)[:5]

    ctx = {
        'fmea_list': fmea_list,
        'rca_list': rca_list,
        'fmea_prioritas': fmea_prioritas,
        'kpi': kpi,
        'units': units,
        'tahun_list': tahun_list,
        'status_choices': RisikoUnit.STATUS_CHOICES,
        'default_filter_unit': default_filter_unit,
        'sel_tahun': tahun or '',
        'sel_status': status or '',
    }
    return render(request, 'akreditasi/risiko_fmea_rca.html', ctx)


# ── 11. Dokumen Perencanaan Risiko (Siklus Plan — STARKES 5.15) ─────────────

@login_required
def risiko_perencanaan_dokumen(request, risiko_id):
    """
    Dokumen Perencanaan Risiko Spesifik (Single Risk View).
    Sesuai format resmi dokumen perencanaan RS Monsiskami ARIMA.
    """
    risiko = get_object_or_404(
        RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'indikator_mutu_terkait__ep_terkait', 'created_by').prefetch_related('tindak_lanjut'),
        pk=risiko_id
    )
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        allowed_ids = [profile.unit_kerja.id] + list(UnitKerja.objects.filter(parent=profile.unit_kerja).values_list('id', flat=True))
        if risiko.unit_id not in allowed_ids:
            messages.error(request, 'Anda tidak memiliki akses ke dokumen perencanaan risiko unit ini.')
            return redirect('akreditasi:risiko_daftar')

    tindak_lanjut = list(risiko.tindak_lanjut.all().order_by('urutan'))
    total_biaya = risiko.biaya_mitigasi or Decimal('0')
    total_biaya_format = _format_rupiah(total_biaya)

    ctx = {
        'risiko':             risiko,
        'is_single':          True,
        'unit':               risiko.unit,
        'tahun':              risiko.tahun,
        'periode':            risiko.get_periode_display(),
        'tindak_lanjut_list': tindak_lanjut,
        'total_biaya':        total_biaya,
        'total_biaya_format': total_biaya_format,
        'tgl_cetak':          timezone.now(),
    }
    return render(request, 'akreditasi/risiko_perencanaan.html', ctx)


@login_required
def risiko_perencanaan_unit(request, unit_id=None):
    """
    Dokumen Perencanaan Risiko Unit Kerja (Rekapitulasi Agregat Unit - Siklus Plan).
    Memformat seluruh risiko unit ke dalam Tabel Indikator Mutu (5 Kolom)
    dan Tabel Rencana Aksi Mitigasi (7 Kolom) sesuai dokumen resmi.
    """
    profile = getattr(request.user, 'profile', None)

    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        unit_ids = [user_unit.id] + list(UnitKerja.objects.filter(parent=user_unit).values_list('id', flat=True))
        units = UnitKerja.objects.filter(id__in=unit_ids)
        default_unit = user_unit
    else:
        units = UnitKerja.objects.all().order_by('name')
        default_unit = units.first()

    target_unit_id = unit_id or request.GET.get('unit')
    if target_unit_id:
        try:
            target_unit_id = int(target_unit_id)
            selected_unit = get_object_or_404(UnitKerja, pk=target_unit_id)
        except (ValueError, TypeError, Http404):
            selected_unit = default_unit
    else:
        selected_unit = default_unit

    tahun_raw = request.GET.get('tahun')
    tahun = 2026
    if tahun_raw:
        try:
            tahun = int(tahun_raw)
        except (ValueError, TypeError):
            tahun = 2026

    tahun_list = sorted(list(set(RisikoUnit.objects.values_list('tahun', flat=True).distinct())), reverse=True)
    if not tahun_list:
        tahun_list = [2026]

    risiko_qs = RisikoUnit.objects.filter(unit=selected_unit).select_related(
        'unit', 'indikator_mutu_terkait', 'indikator_mutu_terkait__ep_terkait',
        'created_by'
    ).prefetch_related('tindak_lanjut').order_by('-dampak', '-probabilitas', 'id')

    if tahun:
        risiko_qs = risiko_qs.filter(tahun=tahun)

    risiko_list = list(risiko_qs)

    # Tabel 1: Indikator Mutu (5 Kolom)
    # No | Masalah Resiko | Indikator mutu | Target | Jenis (INM, IM RS/IMUnit)
    table_indikator = []
    for idx, r in enumerate(risiko_list, start=1):
        ind = r.indikator_mutu_terkait
        nama_ind = ind.nama_indikator if ind else '—'
        kode_ind = f"[{ind.kode_indikator}] " if ind else ''
        _ev = r.capaian_evaluasi
        if _ev['target'] is not None:
            target_str = f"{_ev['target']:.1f}{_ev['satuan']}"
        else:
            target_str = "—"

        jenis_str = ind.get_jenis_display() if ind else 'IMP Unit'

        table_indikator.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'indikator_mutu': f"{kode_ind}{nama_ind}" if nama_ind != '—' else 'Belum ditentukan',
            'target': target_str,
            'jenis': jenis_str,
        })

    # Tabel 2: Rencana Aksi Mitigasi (7 Kolom)
    # No | Masalah resiko | Indikator mutu | Rencana Aksi | waktu | Biaya | PJ
    table_aksi = []
    for idx, r in enumerate(risiko_list, start=1):
        ind = r.indikator_mutu_terkait
        nama_ind = ind.nama_indikator if ind else '—'
        waktu_str = r.target_selesai.strftime('%d/%m/%Y') if r.target_selesai else r.get_periode_display()
        biaya_str = _format_rupiah(r.biaya_mitigasi)
        tindak_items = list(r.tindak_lanjut.all().order_by('urutan'))

        table_aksi.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'indikator_mutu': nama_ind,
            'rencana_aksi': r.rencana_aksi,
            'tindak_lanjut_items': tindak_items,
            'waktu': waktu_str,
            'biaya': biaya_str,
            'pj': r.pj_mitigasi or 'Ka. Unit',
            # Kolom EP (Pelaksanaan): turunan indikator, sama seperti tautan
            # yang diwarisi oleh pelaksanaan.
            'ep': ind.ep_terkait if ind else None,
            'standar': ind.ep_terkait.category if (ind and ind.ep_terkait_id) else None,
        })

    total_biaya = sum((r.biaya_mitigasi or Decimal('0')) for r in risiko_list)
    total_biaya_format = _format_rupiah(total_biaya)

    ctx = {
        'is_single': False,
        'selected_unit': selected_unit,
        'units': units,
        'tahun': tahun,
        'tahun_list': tahun_list,
        'risiko_list': risiko_list,
        'table_indikator': table_indikator,
        'table_aksi': table_aksi,
        'total_risiko': len(risiko_list),
        'total_biaya': total_biaya,
        'total_biaya_format': total_biaya_format,
        'tgl_cetak': timezone.now(),
    }
    return render(request, 'akreditasi/risiko_perencanaan.html', ctx)


@login_required
def risiko_perencanaan_export_csv(request):
    """Ekspor Tabel Perencanaan Risiko (Indikator & Rencana Aksi) ke format CSV UTF-8 BOM."""
    import csv
    unit_id = request.GET.get('unit')
    tahun_raw = request.GET.get('tahun')

    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        target_unit = profile.unit_kerja
    elif unit_id:
        target_unit = get_object_or_404(UnitKerja, pk=unit_id)
    else:
        target_unit = UnitKerja.objects.first()

    tahun = int(tahun_raw) if tahun_raw and tahun_raw.isdigit() else 2026

    risiko_qs = RisikoUnit.objects.filter(unit=target_unit, tahun=tahun).select_related(
        'unit', 'indikator_mutu_terkait'
    ).order_by('-dampak', '-probabilitas', 'id')

    unit_slug = (target_unit.name if target_unit else 'Unit').replace(' ', '_')
    filename = f"Perencanaan_Risiko_{unit_slug}_{tahun}_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff'.encode('utf-8'))

    writer = csv.writer(response)
    writer.writerow(['PERENCANAAN RESIKO RS MONSISKAMI ARIMA'])
    writer.writerow(['JL. Candiwulan Kalibuntu Mangli Kuwarasan Kebumen Jawatengah'])
    writer.writerow([f'Unit Kerja: {target_unit.name if target_unit else "Semua"}', f'Tahun: {tahun}'])
    writer.writerow([])

    # Table 1: Indikator Mutu
    writer.writerow(['TABEL 1: INDIKATOR MUTU DENGAN RISIKO TERKAIT'])
    writer.writerow(['No', 'Masalah Resiko', 'Indikator Mutu', 'Target', 'Jenis (INM, IM RS/IMUnit)'])
    for idx, r in enumerate(risiko_qs, start=1):
        ind = r.indikator_mutu_terkait
        nama_ind = ind.nama_indikator if ind else 'Belum ditentukan'
        _ev = r.capaian_evaluasi
        target_val = f"{_ev['target']:.1f}{_ev['satuan']}" if _ev['target'] is not None else '—'
        jenis_val = ind.get_jenis_display() if ind else 'IMP Unit'
        writer.writerow([idx, r.masalah or r.jenis_risiko, nama_ind, target_val, jenis_val])

    writer.writerow([])
    # Table 2: Rencana Aksi (Mitigasi)
    writer.writerow(['TABEL 2: RENCANA AKSI (MITIGASI) RISIKO'])
    writer.writerow(['No', 'Masalah Resiko', 'Indikator Mutu', 'Rencana Aksi', 'Waktu', 'Biaya', 'PJ'])
    total_biaya_csv = Decimal('0')
    for idx, r in enumerate(risiko_qs, start=1):
        ind = r.indikator_mutu_terkait
        nama_ind = ind.nama_indikator if ind else '—'
        waktu_val = r.target_selesai.strftime('%d/%m/%Y') if r.target_selesai else r.get_periode_display()
        biaya_val = _format_rupiah(r.biaya_mitigasi)
        if r.biaya_mitigasi:
            total_biaya_csv += r.biaya_mitigasi
        writer.writerow([idx, r.masalah or r.jenis_risiko, nama_ind, r.rencana_aksi, waktu_val, biaya_val, r.pj_mitigasi or 'Ka. Unit'])

    writer.writerow(['TOTAL BIAYA MITIGASI', '', '', '', '', _format_rupiah(total_biaya_csv), ''])

    return response


# ── Dokumen Pelaksanaan (Do) ──────────────────────────────────────────────────

@login_required
def risiko_pelaksanaan_dokumen(request, risiko_id):
    """Dokumen Cetak Pelaksanaan Risiko (Siklus DO) — per satu risiko."""
    risiko = get_object_or_404(
        RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'created_by'),
        pk=risiko_id
    )
    tindak_lanjut = risiko.tindak_lanjut.all().order_by('urutan')

    total_tl = tindak_lanjut.count()
    selesai_tl = tindak_lanjut.filter(status_aksi='SELESAI').count()
    pct_selesai = round((selesai_tl / total_tl * 100) if total_tl > 0 else 0)

    ctx = {
        'is_single': True,
        'risiko': risiko,
        'tindak_lanjut': tindak_lanjut,
        'total_tl': total_tl,
        'selesai_tl': selesai_tl,
        'pct_selesai': pct_selesai,
        'tgl_cetak': timezone.now(),
    }
    return render(request, 'akreditasi/risiko_pelaksanaan.html', ctx)


@login_required
def risiko_pelaksanaan_unit(request, unit_id=None):
    """Dokumen Cetak Pelaksanaan Risiko (Siklus DO) — rekap semua risiko per unit & tahun."""
    from .models import UnitKerja as UK
    profile = getattr(request.user, 'profile', None)

    if profile and profile.is_unit_scoped and profile.unit_kerja:
        units = UK.objects.filter(pk=profile.unit_kerja.pk)
        default_unit = profile.unit_kerja
    else:
        units = UK.objects.all().order_by('name')
        default_unit = UK.objects.first()

    if unit_id:
        selected_unit = get_object_or_404(UK, pk=unit_id)
    elif request.GET.get('unit'):
        try:
            selected_unit = UK.objects.get(pk=int(request.GET.get('unit')))
        except (UK.DoesNotExist, ValueError):
            selected_unit = default_unit
    else:
        selected_unit = default_unit

    tahun_raw = request.GET.get('tahun')
    tahun = 2026
    if tahun_raw:
        try:
            tahun = int(tahun_raw)
        except (ValueError, TypeError):
            tahun = 2026

    tahun_list = sorted(list(set(RisikoUnit.objects.values_list('tahun', flat=True).distinct())), reverse=True)
    if not tahun_list:
        tahun_list = [2026]

    risiko_qs = RisikoUnit.objects.filter(unit=selected_unit, tahun=tahun).select_related(
        'unit', 'indikator_mutu_terkait', 'created_by'
    ).prefetch_related('tindak_lanjut').order_by('-dampak', '-probabilitas', 'id')

    risiko_list = []
    for r in risiko_qs:
        tl_list = list(r.tindak_lanjut.all().order_by('urutan'))
        total = len(tl_list)
        selesai = sum(1 for tl in tl_list if tl.status_aksi == 'SELESAI')
        pct = round((selesai / total * 100) if total > 0 else 0)
        risiko_list.append({
            'risiko': r,
            'tindak_lanjut': tl_list,
            'total_tl': total,
            'selesai_tl': selesai,
            'pct_selesai': pct,
        })

    ctx = {
        'is_single': False,
        'selected_unit': selected_unit,
        'units': units,
        'tahun': tahun,
        'tahun_list': tahun_list,
        'risiko_list': risiko_list,
        'total_risiko': len(risiko_list),
        'tgl_cetak': timezone.now(),
    }
    return render(request, 'akreditasi/risiko_pelaksanaan.html', ctx)


@login_required
def risiko_pelaksanaan_export_csv(request):
    """Ekspor Dokumen Pelaksanaan Risiko (Siklus DO) ke CSV UTF-8 BOM."""
    import csv
    unit_id = request.GET.get('unit')
    tahun_raw = request.GET.get('tahun')

    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        target_unit = profile.unit_kerja
    elif unit_id:
        target_unit = get_object_or_404(UnitKerja, pk=unit_id)
    else:
        target_unit = UnitKerja.objects.first()

    tahun = int(tahun_raw) if tahun_raw and tahun_raw.isdigit() else 2026

    risiko_qs = RisikoUnit.objects.filter(unit=target_unit, tahun=tahun).select_related(
        'unit', 'indikator_mutu_terkait'
    ).prefetch_related('tindak_lanjut').order_by('-dampak', '-probabilitas', 'id')

    unit_slug = (target_unit.name if target_unit else 'Unit').replace(' ', '_')
    filename = f"Pelaksanaan_Risiko_{unit_slug}_{tahun}_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff'.encode('utf-8'))

    writer = csv.writer(response)
    writer.writerow(['PELAKSANAAN RESIKO RS MONSISKAMI ARIMA'])
    writer.writerow(['JL. Candiwulan Kalibuntu Mangli Kuwarasan Kebumen Jawatengah'])
    writer.writerow([f'Unit Kerja: {target_unit.name if target_unit else "Semua"}', f'Tahun: {tahun}'])
    writer.writerow([])

    writer.writerow(['TABEL PELAKSANAAN TINDAKAN RISIKO (SIKLUS DO)'])
    writer.writerow(['No', 'Jenis Risiko', 'Rencana Aksi Mitigasi', 'No. Aksi', 'Deskripsi Pelaksanaan', 'Status', 'Tgl Mulai', 'Tgl Selesai', 'Catatan', 'Bukti Dokumen', 'PJ Mitigasi',
                     'standar', 'kode_ep', 'judul_ep', 'ada_bukti'])

    row_no = 1
    for r in risiko_qs:
        tl_list = list(r.tindak_lanjut.all().order_by('urutan'))
        if tl_list:
            for tl in tl_list:
                writer.writerow([
                    row_no,
                    r.jenis_risiko,
                    r.rencana_aksi,
                    tl.urutan,
                    tl.aksi,
                    tl.get_status_aksi_display(),
                    tl.tanggal_mulai.strftime('%d/%m/%Y') if tl.tanggal_mulai else '—',
                    tl.tanggal_selesai.strftime('%d/%m/%Y') if tl.tanggal_selesai else '—',
                    tl.catatan or '—',
                    'Ada' if tl.bukti_upload else 'Belum ada',
                    r.pj_mitigasi or 'Ka. Unit',
                    # Kolom tambahan ditambah di belakang, tanpa menggeser yang
                    # lama -- pihak lain bisa mem-parse file ini secara posisional.
                    tl.standar_terkait.code if tl.standar_terkait_id else '—',
                    tl.ep_terkait.code if tl.ep_terkait_id else '—',
                    tl.ep_terkait.description if tl.ep_terkait_id else '—',
                    'Ada' if tl.bukti_upload else 'Belum ada',
                ])
                row_no += 1
        else:
            writer.writerow([
                row_no,
                r.jenis_risiko,
                r.rencana_aksi,
                '—', 'Belum ada pelaksanaan dicatat',
                'BELUM', '—', '—', '—', '—',
                r.pj_mitigasi or 'Ka. Unit',
                '—', '—', '—', 'Belum ada',
            ])
            row_no += 1

    return response


# ── 13. Dokumen Laporan Lengkap Manajemen Risiko (Plan + Do + Check/Monev + Action/RTL) ──

@login_required
def risiko_laporan_lengkap(request, risiko_id):
    """
    Dokumen Laporan Lengkap Manajemen Risiko Terintegrasi (Single Risk).
    Mencakup 4 Fase Siklus PDCA Utuh:
    1. Plan: Identifikasi, Tujuan, Skor Awal, Metode, Indikator Mutu, Rencana Aksi
    2. Do: Realisasi Pelaksanaan Tindakan & Bukti Dokumen
    3. Check (Monev): Capaian Indikator Mutu, Evaluasi & Analisis RCA (Fishbone/5-Whys)
    4. Action (RTL): Rencana Tindak Lanjut, PIC, Target Waktu, Status RTL & Matriks Perubahan Risiko
    """
    risiko = get_object_or_404(
        RisikoUnit.objects.select_related('unit', 'indikator_mutu_terkait', 'indikator_mutu_terkait__ep_terkait', 'created_by').prefetch_related('tindak_lanjut'),
        pk=risiko_id
    )
    profile = getattr(request.user, 'profile', None)
    if profile and profile.is_unit_scoped and profile.unit_kerja:
        allowed_ids = [profile.unit_kerja.id] + list(UnitKerja.objects.filter(parent=profile.unit_kerja).values_list('id', flat=True))
        if risiko.unit_id not in allowed_ids:
            messages.error(request, 'Anda tidak memiliki akses ke laporan risiko unit ini.')
            return redirect('akreditasi:risiko_daftar')

    tindak_lanjut = list(risiko.tindak_lanjut.all().order_by('urutan'))
    total_tl = len(tindak_lanjut)
    selesai_tl = sum(1 for tl in tindak_lanjut if tl.status_aksi == 'SELESAI')
    proses_tl = sum(1 for tl in tindak_lanjut if tl.status_aksi == 'PROSES')
    persen_tl = int((selesai_tl / total_tl) * 100) if total_tl > 0 else 0
    total_biaya = risiko.biaya_mitigasi or Decimal('0')
    total_biaya_format = _format_rupiah(total_biaya)

    ctx = {
        'risiko': risiko,
        'is_single': True,
        'unit': risiko.unit,
        'tahun': risiko.tahun,
        'periode': risiko.get_periode_display(),
        'tindak_lanjut_list': tindak_lanjut,
        'total_tl': total_tl,
        'selesai_tl': selesai_tl,
        'proses_tl': proses_tl,
        'persen_tl': persen_tl,
        'rca_items': risiko.rca_fishbone_items,
        'total_biaya': total_biaya,
        'total_biaya_format': total_biaya_format,
        'tgl_cetak': timezone.now(),
    }
    return render(request, 'akreditasi/risiko_laporan_lengkap.html', ctx)


@login_required
def risiko_laporan_lengkap_unit(request, unit_id=None):
    """
    Dokumen Laporan Lengkap Manajemen Risiko Agregat Unit Kerja (Siklus PDCA Lengkap).
    Menyajikan seluruh risiko unit dengan rincian Perencanaan, Pelaksanaan, MONEV, dan RTL.
    """
    profile = getattr(request.user, 'profile', None)

    if profile and profile.is_unit_scoped and profile.unit_kerja:
        user_unit = profile.unit_kerja
        unit_ids = [user_unit.id] + list(UnitKerja.objects.filter(parent=user_unit).values_list('id', flat=True))
        units = UnitKerja.objects.filter(id__in=unit_ids)
        default_unit = user_unit
    else:
        units = UnitKerja.objects.all().order_by('name')
        from django.db.models import Count as _Count
        default_unit = (
            UnitKerja.objects.annotate(_n=_Count('risikounit')).order_by('-_n').first()
            or units.first()
        )

    target_unit_id = unit_id or request.GET.get('unit')
    if target_unit_id:
        try:
            target_unit_id = int(target_unit_id)
            selected_unit = get_object_or_404(UnitKerja, pk=target_unit_id)
        except (ValueError, TypeError, Http404):
            selected_unit = default_unit
    else:
        selected_unit = default_unit

    tahun_raw = request.GET.get('tahun')
    tahun = 2026
    if tahun_raw:
        try:
            tahun = int(tahun_raw)
        except (ValueError, TypeError):
            tahun = 2026

    tahun_list = sorted(list(set(RisikoUnit.objects.values_list('tahun', flat=True).distinct())), reverse=True)
    if not tahun_list:
        tahun_list = [2026]

    risiko_qs = RisikoUnit.objects.filter(unit=selected_unit).select_related(
        'unit', 'indikator_mutu_terkait', 'indikator_mutu_terkait__ep_terkait',
        'created_by'
    ).prefetch_related('tindak_lanjut').order_by('-dampak', '-probabilitas', 'id')

    if tahun:
        risiko_qs = risiko_qs.filter(tahun=tahun)

    risiko_list = list(risiko_qs)
    if not risiko_list:
        risiko_list = list(
            RisikoUnit.objects.filter(unit=selected_unit).select_related(
                'unit', 'indikator_mutu_terkait', 'created_by'
            ).prefetch_related('tindak_lanjut').order_by('-dampak', '-probabilitas', 'id')
        )

    total_risiko = len(risiko_list)
    rtl_selesai = sum(1 for r in risiko_list if r.status_rtl == 'SELESAI')
    rtl_proses = sum(1 for r in risiko_list if r.status_rtl == 'PROSES')
    terevaluasi = sum(1 for r in risiko_list if r.capaian_nilai is not None or r.evaluasi_capaian)

    # Siapkan 5 dataset tabel untuk tampilan siklus PDCA ke bawah (1, 2, 3, 4)
    # Sesuai spesifikasi resmi Word: contoh laporan manajemen resiko 1310.docx
    table_penilaian_awal = []
    table_indikator = []
    table_rencana_aksi = []
    table_pelaksanaan = []
    table_monev = []

    dampak_map = {1: 'Sangat Rendah', 2: 'Rendah', 3: 'Sedang', 4: 'Tinggi', 5: 'Katastropik'}
    prob_map = {1: 'Sangat Jarang', 2: 'Jarang', 3: 'Kadang', 4: 'Sering', 5: 'Sangat Sering'}

    for idx, r in enumerate(risiko_list, start=1):
        ind = r.indikator_mutu_terkait
        nama_ind = ind.nama_indikator if ind else '—'
        kode_ind = f"[{ind.kode_indikator}] " if ind and ind.kode_indikator else ""

        if r.target_capaian_indikator is not None:
            target_str = f"{r.target_capaian_indikator:.1f}%"
        elif ind and ind.target_nilai is not None:
            target_str = f"{ind.target_nilai:.1f}%"
        else:
            target_str = "—"

        jenis_str = ind.get_jenis_display() if ind else 'IMP Unit'
        waktu_str = r.target_selesai.strftime('%d/%m/%Y') if r.target_selesai else (f"{r.get_periode_display()} {r.tahun}" if r.periode else "—")
        biaya_str = _format_rupiah(r.biaya_mitigasi)
        tindak_items = list(r.tindak_lanjut.all().order_by('urutan'))

        # 1. Tabel Penilaian Risiko Awal
        table_penilaian_awal.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'kategori': r.get_kategori_risiko_display() if hasattr(r, 'get_kategori_risiko_display') else '',
            'dampak': r.dampak,
            'dampak_display': dampak_map.get(r.dampak, str(r.dampak)),
            'probabilitas': r.probabilitas,
            'probabilitas_display': prob_map.get(r.probabilitas, str(r.probabilitas)),
            'skor': r.skor_inherent,
            'risk_level': r.risk_level,
        })

        # 2. Tabel Indikator Mutu
        table_indikator.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'indikator_mutu': f"{kode_ind}{nama_ind}" if nama_ind != '—' else 'Belum ditentukan',
            'target': target_str,
            'jenis': jenis_str,
        })

        # 3. Tabel Rencana Aksi (Mitigasi)
        table_rencana_aksi.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'indikator_mutu': nama_ind,
            'rencana_aksi': r.rencana_aksi,
            'tindak_lanjut_items': tindak_items,
            'waktu': waktu_str,
            'biaya': biaya_str,
            'pj': r.pj_mitigasi or 'Ka. Unit',
        })

        # 4. Tabel Pelaksanaan (Do)
        # Susun narasi pelaksanaan dari tindak_lanjut jika ada
        pelaksanaan_text = r.rencana_aksi
        if tindak_items:
            pelaksanaan_text = "; ".join([t.aksi for t in tindak_items])

        table_pelaksanaan.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'indikator_mutu': nama_ind,
            'pelaksanaan_do': pelaksanaan_text,
            'tindak_lanjut_items': tindak_items,
            'waktu': waktu_str,
            'biaya': biaya_str,
            'pj': r.pj_mitigasi or 'Ka. Unit',
            'bukti_dokumen': [t for t in tindak_items if t.bukti_upload],
        })

        # 5. Tabel Monitoring dan Evaluasi (5W + RTL)
        capaian_str = r.capaian_persen_display if (r.capaian_nilai is not None or r.capaian_persen_display) else '—'
        akar_5w = r.akar_masalah_rca or ''
        if r.rca_fishbone_items:
            akar_5w = "; ".join([f"{item['label']}: {item['text']}" for item in r.rca_fishbone_items])

        table_monev.append({
            'no': idx,
            'risiko': r,
            'risiko_id': r.id,
            'masalah': r.masalah or r.jenis_risiko,
            'indikator_mutu_target': target_str,
            'indikator_mutu_capaian': capaian_str,
            'capaian_nilai': r.capaian_nilai,
            'evaluasi_capaian': r.evaluasi_capaian,
            'akar_masalah_5w': akar_5w,
            'rca_items': r.rca_fishbone_items,
            'rtl': r.rencana_tindak_lanjut or '—',
            'pj_rtl': r.pj_rtl or r.pj_mitigasi or 'Ka. Unit',
            'deadline_rtl': r.deadline_rtl,
            'status_rtl': r.get_status_rtl_display(),
            'status_rtl_badge_color': r.status_rtl_badge_color,
        })

    total_biaya = sum((r.biaya_mitigasi or Decimal('0')) for r in risiko_list)
    total_biaya_format = _format_rupiah(total_biaya)

    ctx = {
        'is_single': False,
        'selected_unit': selected_unit,
        'units': units,
        'tahun': tahun,
        'tahun_list': tahun_list,
        'risiko_list': risiko_list,
        'total_risiko': total_risiko,
        'total_biaya': total_biaya,
        'total_biaya_format': total_biaya_format,
        'rtl_selesai': rtl_selesai,
        'rtl_proses': rtl_proses,
        'terevaluasi': terevaluasi,
        'table_penilaian_awal': table_penilaian_awal,
        'table_indikator': table_indikator,
        'table_rencana_aksi': table_rencana_aksi,
        'table_pelaksanaan': table_pelaksanaan,
        'table_monev': table_monev,
        'tgl_cetak': timezone.now(),
    }
    return render(request, 'akreditasi/risiko_laporan_lengkap.html', ctx)



