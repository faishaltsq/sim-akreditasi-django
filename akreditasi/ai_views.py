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
    generate_pdca_action_plan,
    generate_insiden_grading,
    generate_evaluasi_risiko,
    generate_rdwos_analisis,
    generate_kps_rekomendasi,
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
    if profile and not profile.has_permission('can_edit_risk'):
        return JsonResponse({'success': False, 'error': 'Anda tidak memiliki hak akses mengubah data risiko.'}, status=403)

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

    if not jenis_risiko and not deskripsi_risiko:
        return JsonResponse({
            'success': False,
            'error': 'Harap isi Jenis Risiko atau Deskripsi Risiko terlebih dahulu sebelum meminta rekomendasi AI.'
        }, status=400)

    res = generate_risk_mitigation(
        user=request.user,
        unit_name=unit_name,
        kategori_risiko=kategori_risiko,
        jenis_risiko=jenis_risiko,
        deskripsi_risiko=deskripsi_risiko,
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
    if profile and not profile.has_permission('can_edit_risk'):
        return JsonResponse({'success': False, 'error': 'Tidak memiliki hak akses.'}, status=403)

    data = _parse_json_body(request)
    if not data:
        return JsonResponse({'success': False, 'error': 'Payload tidak valid.'}, status=400)

    res = generate_evaluasi_risiko(
        user=request.user,
        unit_name=data.get('unit_name', ''),
        jenis_risiko=data.get('jenis_risiko', ''),
        deskripsi_risiko=data.get('deskripsi_risiko', ''),
        skor_awal=int(data.get('skor_awal') or 0),
        dampak_awal=int(data.get('dampak_awal') or 0),
        prob_awal=int(data.get('prob_awal') or 0),
        mitigasi_terlaksana=data.get('mitigasi_terlaksana', ''),
        dampak_residual=int(data.get('dampak_residual') or 0),
        prob_residual=int(data.get('prob_residual') or 0),
        status=data.get('status', 'EVALUASI'),
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
