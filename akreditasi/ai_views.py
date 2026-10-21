"""
Views Controller untuk Endpoint AI DeepSeek.

Semua endpoint:
- Mengembalikan response format JSON standar: {'success': bool, 'data': dict, 'error': str}
- Diproteksi login (@login_required)
- Memverifikasi permission RBAC spesifik per modul
- TIDAK pernah mengekspos API Key ke response JSON
- Memvalidasi input payload sebelum memanggil service AI
"""
import json
import logging
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from .security_utils import rate_limit
from .ai_service import (
    generate_risk_mitigation,
    generate_ep_rekomendasi,
    generate_pdca_action_plan,
    generate_insiden_grading,
    generate_evaluasi_risiko,
    generate_rdwos_analisis,
    generate_kps_rekomendasi,
    generate_indicator_draft,
    generate_risk_analysis_from_problem,
    generate_fmea_suggestion,
    generate_rca_suggestion,
    test_deepseek_connection,
)
from .models import StandardItem, UnitKerja

logger = logging.getLogger(__name__)


def _parse_json_body(request):
    """Parse JSON body dari request, toleran terhadap encoding."""
    try:
        return json.loads(request.body.decode('utf-8'))
    except Exception as e:
        return None


# ── 1. GENERATE MITIGASI RISIKO ──────────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_mitigasi_risiko(request):
    """Endpoint untuk tombol '✨ AI Bantu Rencana Mitigasi' di form risiko."""
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_permission('can_view_risiko'):
        return JsonResponse({'success': False, 'error': 'Anda tidak memiliki hak akses melihat data risiko.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload request tidak valid (bukan JSON).'}, status=400)

    unit_name = data.get('unit_name') or 'Unit Kerja'
    kategori_risiko = data.get('kategori_risiko') or 'Operasional'
    jenis_risiko = (data.get('jenis_risiko') or '').strip()
    deskripsi_risiko = (data.get('deskripsi_risiko') or '').strip()
    dampak = int(data.get('dampak') or 3)
    probabilitas = int(data.get('probabilitas') or 3)
    strategi = data.get('strategi') or 'Mitigasi (Reduce)'

    masalah = (data.get('masalah') or '').strip()
    data_pendukung = (data.get('data_pendukung') or data.get('data') or '').strip()

    if not jenis_risiko and not deskripsi_risiko and not masalah:
        return JsonResponse({
            'success': False,
            'error': 'Harap isi Jenis Risiko, Masalah, atau Deskripsi Risiko terlebih dahulu sebelum meminta rekomendasi AI.'
        }, status=400)

    # Standar 5.15: Perkaya konteks deskripsi risiko dengan masalah dan data pendukung
    full_deskripsi = []
    if masalah:
        full_deskripsi.append(f"Masalah: {masalah}")
    if data_pendukung:
        full_deskripsi.append(f"Data Pendukung: {data_pendukung}")
    if deskripsi_risiko:
        full_deskripsi.append(f"Deskripsi: {deskripsi_risiko}")
    context_deskripsi = "\n".join(full_deskripsi) if full_deskripsi else deskripsi_risiko

    res = generate_risk_mitigation(
        user=request.user,
        unit_name=unit_name,
        kategori_risiko=kategori_risiko,
        jenis_risiko=jenis_risiko,
        deskripsi_risiko=context_deskripsi,
        dampak=dampak,
        probabilitas=probabilitas,
        strategi=strategi,
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 2. GENERATE PDCA ACTION PLAN ─────────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_pdca_plan(request):
    """Endpoint untuk tombol '✨ AI Susun Action Plan PDCA'."""
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_permission('can_edit_pdca'):
        return JsonResponse({'success': False, 'error': 'Anda tidak memiliki hak akses mengubah data PDCA.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload request tidak valid.'}, status=400)

    ep_code = data.get('ep_code', '')
    ep_name = data.get('ep_name', '')
    ep_desc = data.get('ep_desc', '')
    unit_name = data.get('unit_name', 'Seluruh Unit')
    current_score = int(data.get('current_score') or 0)
    eval_notes = data.get('eval_notes', '')

    res = generate_pdca_action_plan(
        user=request.user,
        ep_code=ep_code,
        ep_name=ep_name,
        ep_desc=ep_desc,
        unit_name=unit_name,
        current_score=current_score,
        eval_notes=eval_notes,
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 3. GRADING INSIDEN KESELAMATAN ───────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_insiden_grading(request):
    """Endpoint untuk tombol '✨ AI Grading & Rekomendasi Investigasi' di form insiden."""
    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload request tidak valid.'}, status=400)

    jenis_insiden = data.get('jenis_insiden', '')
    tingkat_keparahan = data.get('tingkat_keparahan', '')
    lokasi_kejadian = data.get('lokasi_kejadian', '')
    deskripsi_kejadian = (data.get('deskripsi_kejadian') or '').strip()
    tindakan_segera = data.get('tindakan_segera', '')
    pasien_terpapar = bool(data.get('pasien_terpapar', False))
    unit_name = data.get('unit_name', 'Unit Kerja')

    if not deskripsi_kejadian:
        return JsonResponse({
            'success': False,
            'error': 'Harap isi deskripsi kronologi kejadian terlebih dahulu.'
        }, status=400)

    res = generate_insiden_grading(
        user=request.user,
        jenis_insiden=jenis_insiden,
        tingkat_keparahan=tingkat_keparahan,
        lokasi_kejadian=lokasi_kejadian,
        deskripsi_kejadian=deskripsi_kejadian,
        tindakan_segera=tindakan_segera,
        pasien_terpapar=pasien_terpapar,
        unit_name=unit_name,
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 4. EVALUASI EFEKTIVITAS RISIKO ───────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_evaluasi_risiko(request):
    """Endpoint untuk analisis efektivitas mitigasi di halaman evaluasi risiko."""
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_permission('can_view_risiko'):
        return JsonResponse({'success': False, 'error': 'Tidak memiliki hak akses.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid.'}, status=400)

    # Sumber konteks: halaman evaluasi tidak lagi memuat input capaian inline,
    # jadi klien kirim risiko_id dan nilai diambil dari model — capaian berasal
    # dari agregat Input Capaian (CatatanIndikator), bukan angka yang dirender
    # ke JS. Field eksplisit pada payload tetap didahulukan agar payload lama
    # (dipakai test & klien lama) tetap berfungsi.
    derived = {}
    if data.get('risiko_id'):
        from .risiko_models import RisikoUnit
        try:
            rk = RisikoUnit.objects.select_related(
                'unit', 'indikator_mutu_terkait').get(pk=int(data['risiko_id']))
        except (RisikoUnit.DoesNotExist, TypeError, ValueError):
            return JsonResponse({'success': False, 'error': 'Risiko tidak ditemukan.'}, status=400)

        ev = rk.capaian_evaluasi
        gap_str = ''
        if ev['gap'] is not None:
            gap_str = ('+' if ev['gap'] >= 0 else '') + f"{ev['gap']:.1f}%"
        capaian_disp = rk.capaian_persen_display
        derived = {
            'unit_name': rk.unit.name if rk.unit_id else '',
            'jenis_risiko': rk.jenis_risiko or '',
            'deskripsi_risiko': rk.deskripsi_risiko or rk.masalah or '',
            'skor_awal': rk.skor_inherent,
            'dampak_awal': rk.dampak,
            'prob_awal': rk.probabilitas,
            'mitigasi_terlaksana': rk.rencana_aksi or '',
            'nama_indikator': (rk.indikator_mutu_terkait.nama_indikator
                               if rk.indikator_mutu_terkait_id else ''),
            'target_capaian': f"{ev['target']}%" if ev['target'] is not None else '',
            'capaian_nilai': '' if capaian_disp == '—' else capaian_disp,
            'gap_persen': gap_str,
        }

    def pick(key, default=''):
        val = data.get(key)
        if val not in (None, ''):
            return val
        return derived.get(key, default)

    res = generate_evaluasi_risiko(
        user=request.user,
        unit_name=pick('unit_name'),
        jenis_risiko=pick('jenis_risiko'),
        deskripsi_risiko=pick('deskripsi_risiko'),
        skor_awal=int(pick('skor_awal', 0) or 0),
        dampak_awal=int(pick('dampak_awal', 0) or 0),
        prob_awal=int(pick('prob_awal', 0) or 0),
        mitigasi_terlaksana=pick('mitigasi_terlaksana'),
        dampak_residual=int(data.get('dampak_residual') or 0),
        prob_residual=int(data.get('prob_residual') or 0),
        status=pick('status', 'EVALUASI'),
        nama_indikator=pick('nama_indikator'),
        target_capaian=str(pick('target_capaian')),
        capaian_nilai=str(pick('capaian_nilai')),
        gap_persen=str(pick('gap_persen')),
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 5. ANALISIS RDWOS BUKTI ──────────────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_rdwos_analisis(request):
    """Endpoint untuk analisis kelengkapan bukti dokumen RDWOS."""
    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid.'}, status=400)

    res = generate_rdwos_analisis(
        user=request.user,
        ep_code=data.get('ep_code', ''),
        ep_name=data.get('ep_name', ''),
        dokumen_ada=int(data.get('dokumen_ada') or 0),
        total_kebutuhan=int(data.get('total_kebutuhan') or 0),
        jenis_dokumen=data.get('jenis_dokumen') or [],
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── SINKRONISASI EP <-> INDIKATOR MUTU ────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_ep_rekomendasi(request):
    """Rekomendasi Elemen Penilaian (EP) untuk satu indikator mutu.

    Menggabungkan saran cepat berbasis kata (Tier B, instan) dengan rekomendasi
    DeepSeek atas katalog EP penuh (Tier C). Keduanya selalu ikut dikembalikan,
    karena AI bisa mati dan operator tetap perlu melihat sesuatu.
    """
    from .indikator_views import _is_manager          # lazy: hindari siklus impor
    from .ep_sync import prefilter_candidates, rule_boost_map
    from .risiko_models import IndikatorMutu

    if not _is_manager(request.user):
        return JsonResponse(
            {'success': False, 'error': 'Anda tidak memiliki hak akses sinkronisasi EP.'},
            status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid (bukan JSON).'},
                            status=400)

    try:
        ind_id = int(data.get('indikator_id'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'indikator_id tidak valid.'},
                            status=400)

    ind = (IndikatorMutu.objects.select_related('unit', 'ep_terkait')
           .filter(pk=ind_id).first())
    if ind is None:
        return JsonResponse({'success': False, 'error': 'Indikator tidak ditemukan.'},
                            status=404)

    # Link manual adalah keputusan manusia — jangan diusik.
    # Guard ini membaca DATABASE, sedangkan layar menampilkan FORM; keduanya bisa
    # berbeda (dropdown sudah dikosongkan tapi belum disimpan). Karena itu pesan
    # menyebut EP yang menghalangi dan memberi jalan keluar sekali klik.
    if ind.ep_terkait_id and ind.ep_sumber == 'MANUAL':
        ep = ind.ep_terkait
        return JsonResponse({
            'success': False,
            'error': (f'EP {ep.code} masih tertaut manual di database. '
                      f'Kosongkan kolom EP lalu tekan "Simpan Perubahan", '
                      f'atau pakai tombol "Lepas & cari ulang".'),
            'ep_terkait': {'id': ep.id, 'code': ep.code, 'sumber': ind.ep_sumber},
            'butuh_simpan': True,
            'bisa_lepas': True,
        }, status=400)

    boost = rule_boost_map(ind.unit)
    petunjuk = '; '.join(f'{k}: {", ".join(sorted(v))}' for k, v in sorted(boost.items()))

    cepat = [{
        'id': c['ep'].id, 'code': c['code'], 'deskripsi': c['deskripsi'],
        'pokja': c['pokja'], 'skor': float(c['skor']), 'dari_unit': c['dari_unit'],
    } for c in prefilter_candidates(ind, top_k=10)]

    res = generate_ep_rekomendasi(user=request.user, ind=ind, petunjuk_unit=petunjuk)

    notice = None if res.get('success') else 'Gagal memproses rekomendasi AI.'
    return JsonResponse({
        'success': bool(res.get('success')),
        'kandidat': cepat,
        'rekomendasi': (res.get('data') or {}).get('rekomendasi') or [],
        'sumber': (res.get('data') or {}).get('sumber'),
        'ai_terpakai': bool(res.get('ai_terpakai')),
        'notice': notice,
        'ai_status': _ai_status(),
        'ep_terkait': (
            {'id': ind.ep_terkait_id, 'code': ind.ep_terkait.code,
             'sumber': ind.ep_sumber} if ind.ep_terkait_id else None),
    }, status=200 if res.get('success') else 400)


def _ai_status() -> dict:
    """Ketersediaan AI untuk kartu Sinkronisasi EP, SEBELUM operator menekan tombol.

    Tanpa ini operator baru tahu AI mati setelah klik, dan hasil Tier B
    (kecocokan kata, precision@1 terukur 10%) terbaca sebagai hasil AI.
    """
    from .system_models import SystemConfig
    cfg = SystemConfig.get_solo()
    try:
        ada_kunci = bool(cfg.get_deepseek_api_key())
    except Exception:            # konfigurasi rusak tidak boleh merontokkan kartu
        ada_kunci = False
    flag = bool(getattr(cfg, 'ai_enable_ep_sync', True))
    aktif = bool(flag and cfg.ai_enabled and ada_kunci)
    return {
        'aktif': aktif,
        'flag_ep_sync': flag,
        'ai_enabled': bool(cfg.ai_enabled),
        'api_key_terkonfigurasi': ada_kunci,
        'keterangan': ('AI aktif' if aktif else
                       'AI nonaktif — hasil akan berupa kecocokan kata'),
    }


@login_required
@require_POST
@rate_limit(max_calls=30, window=60, scope='ep_write')
def api_ai_ep_terapkan(request):
    """Tulis link EP pilihan operator SEKARANG (tombol 'Pakai' di kartu sinkron).

    Sebelumnya 'Pakai' hanya menggerakkan dropdown di browser — link baru masuk
    database hanya bila *Simpan Perubahan* ditekan, jadi hasil AI sering hilang
    begitu operator menutup halaman. Keputusan operator tetap menang:
    ``ep_sumber='MANUAL'`` sehingga auto-sync takkan pernah menimpanya; asal
    usul AI-nya tercatat di AuditLog.
    """
    from .indikator_views import _is_manager          # lazy: hindari siklus impor
    from .ai_service import _log_ai_call
    from .risiko_models import IndikatorMutu

    if not _is_manager(request.user):
        return JsonResponse(
            {'success': False, 'error': 'Anda tidak memiliki hak akses sinkronisasi EP.'},
            status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid (bukan JSON).'},
                            status=400)
    try:
        ind_id = int(data.get('indikator_id'))
        ep_id = int(data.get('ep_id'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'indikator_id atau ep_id tidak valid.'},
                            status=400)

    ind = IndikatorMutu.objects.filter(pk=ind_id).first()
    if ind is None:
        return JsonResponse({'success': False, 'error': 'Indikator tidak ditemukan.'},
                            status=404)
    ep = StandardItem.objects.filter(pk=ep_id).first()
    if ep is None:
        return JsonResponse({'success': False, 'error': 'EP tidak ada di katalog.'},
                            status=400)

    ind.ep_terkait = ep
    ind.ep_sumber = 'MANUAL'
    ind.ep_skor = None
    ind.save(update_fields=['ep_terkait', 'ep_sumber', 'ep_skor'])
    _log_ai_call(request.user, 'EP_SYNC',
                 f'{ind.kode_indikator} -> {ep.code} (diterapkan operator)', True)
    return JsonResponse({
        'success': True,
        'ep_terkait': {'id': ep.id, 'code': ep.code, 'sumber': ind.ep_sumber},
        'pesan': f'EP {ep.code} tersimpan.',
    })


@login_required
@require_POST
@rate_limit(max_calls=30, window=60, scope='ep_write')
def api_ai_ep_lepas(request):
    """Lepas link EP dari database (jalan keluar satu klik dari guard manual).

    Guard ``ep-rekomendasi`` membaca database, bukan form: dropdown yang sudah
    dikosongkan tapi belum disimpan tetap dianggap tertaut. Tombol ini
    merekonsiliasi keduanya tanpa operator harus menebak state mana yang benar.
    """
    from .indikator_views import _is_manager
    from .ai_service import _log_ai_call
    from .risiko_models import IndikatorMutu

    if not _is_manager(request.user):
        return JsonResponse(
            {'success': False, 'error': 'Anda tidak memiliki hak akses sinkronisasi EP.'},
            status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid (bukan JSON).'},
                            status=400)
    try:
        ind_id = int(data.get('indikator_id'))
    except (TypeError, ValueError):
        return JsonResponse({'success': False, 'error': 'indikator_id tidak valid.'},
                            status=400)

    ind = IndikatorMutu.objects.select_related('ep_terkait').filter(pk=ind_id).first()
    if ind is None:
        return JsonResponse({'success': False, 'error': 'Indikator tidak ditemukan.'},
                            status=404)

    if not ind.ep_terkait_id:
        return JsonResponse({'success': True, 'ep_terkait': None,
                             'pesan': 'Tidak ada EP yang tertaut.'})

    lama = ind.ep_terkait.code
    ind.ep_terkait = None
    # Kosong bukan keputusan manual: baris harus tetap bisa diisi auto-sync.
    ind.ep_sumber = ''
    ind.ep_skor = None
    ind.save(update_fields=['ep_terkait', 'ep_sumber', 'ep_skor'])
    _log_ai_call(request.user, 'EP_SYNC',
                 f'{ind.kode_indikator} lepas {lama} (operator)', True)
    return JsonResponse({'success': True, 'ep_terkait': None,
                         'pesan': f'EP {lama} dilepas.'})


# ── 7. PERUMUSAN INDIKATOR MUTU CERDAS ────────────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_rumus_indikator(request):
    """Endpoint untuk tombol '✨ AI Bantu Rumuskan Indikator' di form indikator."""
    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid.'}, status=400)

    nama_indikator = (data.get('nama_indikator') or '').strip()
    if not nama_indikator:
        return JsonResponse({'success': False, 'error': 'Nama atau topik indikator wajib diisi.'}, status=400)

    unit_name = (data.get('unit_name') or '').strip()
    jenis = (data.get('jenis') or 'IMP_UNIT').strip()
    masalah = (data.get('masalah') or '').strip()

    res = generate_indicator_draft(
        user=request.user,
        nama_indikator=nama_indikator,
        unit_name=unit_name,
        jenis=jenis,
        masalah=masalah,
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 8. ANALISIS MASALAH & PENENTUAN RISIKO (STANDAR 5.15) ────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_analisis_masalah_risiko(request):
    """Endpoint untuk tombol '✨ AI Analisis Masalah & Sarankan Risiko' di form risiko."""
    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid.'}, status=400)

    masalah = (data.get('masalah') or '').strip()
    if not masalah:
        return JsonResponse({'success': False, 'error': 'Uraian masalah (Issue Statement) wajib diisi untuk dianalisis AI.'}, status=400)

    unit_name = (data.get('unit_name') or '').strip()
    data_pendukung = (data.get('data_pendukung') or data.get('data') or '').strip()

    res = generate_risk_analysis_from_problem(
        user=request.user,
        unit_name=unit_name,
        masalah=masalah,
        data_pendukung=data_pendukung,
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 9. FMEA — FAILURE MODE & EFFECTS ANALYSIS (PROAKTIF) ─────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_fmea_saran(request):
    """Endpoint untuk tombol 'AI Bantu Susun FMEA' di Section E form risiko."""
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_permission('can_view_risiko'):
        return JsonResponse({'success': False, 'error': 'Anda tidak memiliki hak akses melihat data risiko.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload request tidak valid.'}, status=400)

    jenis_risiko = (data.get('jenis_risiko') or '').strip()
    masalah = (data.get('masalah') or '').strip()
    if not jenis_risiko and not masalah:
        return JsonResponse({
            'success': False,
            'error': 'Harap isi Jenis Risiko atau Masalah terlebih dahulu sebelum meminta analisis FMEA.'
        }, status=400)

    res = generate_fmea_suggestion(
        user=request.user,
        unit_name=(data.get('unit_name') or 'Unit Kerja').strip(),
        kategori_risiko=(data.get('kategori_risiko') or 'KLINIS').strip(),
        jenis_risiko=jenis_risiko,
        masalah=masalah,
        data_pendukung=(data.get('data_pendukung') or '').strip(),
        dampak=int(data.get('dampak') or 3),
        probabilitas=int(data.get('probabilitas') or 3),
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 10. RCA — ROOT CAUSE ANALYSIS (REAKTIF) ──────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_rca_saran(request):
    """Endpoint untuk tombol 'AI Bantu 5-Whys' di Section E form risiko."""
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_permission('can_view_risiko'):
        return JsonResponse({'success': False, 'error': 'Anda tidak memiliki hak akses melihat data risiko.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload request tidak valid.'}, status=400)

    jenis_risiko = (data.get('jenis_risiko') or '').strip()
    masalah = (data.get('masalah') or '').strip()
    if not jenis_risiko and not masalah:
        return JsonResponse({
            'success': False,
            'error': 'Harap isi Jenis Risiko atau Masalah terlebih dahulu sebelum meminta analisis RCA.'
        }, status=400)

    res = generate_rca_suggestion(
        user=request.user,
        unit_name=(data.get('unit_name') or 'Unit Kerja').strip(),
        jenis_risiko=jenis_risiko,
        masalah=masalah,
        data_pendukung=(data.get('data_pendukung') or '').strip(),
        dampak=int(data.get('dampak') or 3),
        probabilitas=int(data.get('probabilitas') or 3),
    )
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 6. TES KONEKSI DEEPSEEK (SUPER ADMIN ONLY) ───────────────────────────

@login_required
@require_POST
def api_ai_test_connection(request):
    """Endpoint untuk tes ping API DeepSeek dari Pusat Kontrol Sistem."""
    profile = getattr(request.user, 'profile', None)
    if not (request.user.is_superuser or (profile and profile.has_permission('can_manage_system_settings'))):
        return JsonResponse({'success': False, 'error': 'Hanya Super Admin yang dapat menguji koneksi AI.'}, status=403)

    res = test_deepseek_connection()
    return JsonResponse(res, status=200 if res['success'] else 400)


# ── 7. NARASI LAPORAN CAPAIAN INDIKATOR MUTU ─────────────────────────────

@login_required
@require_POST
@rate_limit(max_calls=12, window=60, scope='ai')
def api_ai_narasi_laporan(request):
    """Endpoint tombol '✨ Bantu AI Tulis' pada bagian naratif laporan mutu.

    Konteks (angka capaian, rekap IKP, identitas laporan) dibangun ulang di
    server dari ``laporan_id`` — klien tidak boleh menyuplai angka yang akan
    dikutip AI, supaya narasi tidak pernah memuat data yang tidak ada di tabel.
    """
    from .risiko_models import LaporanMutu
    from .mutu_laporan import boleh_sunting
    from .ai_service import generate_narasi_laporan

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False,
                             'error': 'Payload request tidak valid (bukan JSON).'},
                            status=400)

    laporan = (LaporanMutu.objects.select_related('unit')
               .filter(pk=data.get('laporan_id')).first())
    if laporan is None:
        return JsonResponse({'success': False, 'error': 'Laporan tidak ditemukan.'},
                            status=404)

    if not boleh_sunting(request.user, laporan):
        return JsonResponse({
            'success': False,
            'error': 'Laporan ini sudah terkunci atau berada di luar lingkup Anda.'},
            status=403)

    res = generate_narasi_laporan(
        user=request.user,
        laporan=laporan,
        kunci=(data.get('kunci') or '').strip().upper(),
        instruksi=(data.get('instruksi') or '').strip()[:800],
        isi_sekarang=(data.get('isi_sekarang') or '').strip()[:4000],
    )
    if not res.get('success'):
        res = {**res, 'error': 'Gagal menyusun narasi laporan.'}
    return JsonResponse(res, status=200 if res['success'] else 400)
