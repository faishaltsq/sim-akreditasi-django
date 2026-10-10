"""
Service AI Asisten Cerdas berbasis DeepSeek API.

KEAMANAN:
- Semua panggilan API dilakukan dari backend Django (TIDAK pernah dari frontend/JS).
- API Key tidak pernah dikembalikan ke response JSON manapun.
- Data medis sensitif (No RM, NIK, nama pasien) disanitasi sebelum dikirim ke API eksternal.
- Setiap panggilan dicatat ke AuditLog.
"""
import re
import json
import logging
import requests
from typing import Optional

from .ai_prompts import (
    SYSTEM_PROMPT_RS,
    PROMPT_MITIGASI_RISIKO,
    PROMPT_PDCA_ACTION_PLAN,
    PROMPT_INSIDEN_GRADING,
    PROMPT_EVALUASI_RISIKO,
    PROMPT_RDWOS_ANALISIS,
    PROMPT_KPS_REKOMENDASI,
    PROMPT_INDIKATOR_MUTU,
    PROMPT_ANALISIS_MASALAH_RISIKO,
    PROMPT_FMEA_SUGGESTION,
    PROMPT_RCA_SUGGESTION,
)

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_TIMEOUT = 30  # detik


# ── SANITIZER DATA MEDIS SENSITIF ────────────────────────────────────────

# Pola regex untuk data medis yang tidak boleh keluar ke API eksternal
_SANITIZE_PATTERNS = [
    # Nomor Rekam Medis (format RS Indonesia: 2-12 digit dengan opsional separator)
    (re.compile(r'\b(?:no\.?\s*rm|rekam\s*medis|rm)\s*:?\s*[\d\-\.\/]{5,15}\b', re.IGNORECASE), '[NO_RM_DISAMARKAN]'),
    # NIK (16 digit)
    (re.compile(r'\b\d{16}\b'), '[NIK_DISAMARKAN]'),
    # Nomor KTP / KK
    (re.compile(r'\b(?:ktp|kk|nik)\s*:?\s*[\d\-\.]{10,20}\b', re.IGNORECASE), '[NO_ID_DISAMARKAN]'),
    # Tanggal lahir dalam berbagai format
    (re.compile(r'\b(?:lahir|dob|tanggal\s+lahir)\s*:?\s*\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\b', re.IGNORECASE), '[TGL_LAHIR_DISAMARKAN]'),
    # Nama pasien yang disebut setelah kata "pasien/tn/ny/nn/an"
    (re.compile(r'\b(?:pasien|tn\.|ny\.|nn\.|an\.)\s+[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,3}', re.IGNORECASE), '[NAMA_PASIEN_DISAMARKAN]'),
    # Nomor telepon
    (re.compile(r'\b(?:08|62|\+62)\d{8,12}\b'), '[NO_HP_DISAMARKAN]'),
]


def sanitize_hospital_prompt(text: str) -> str:
    """
    Hapus/samarkan data medis sensitif sebelum mengirim teks ke API eksternal.
    WAJIB dipanggil pada semua input user sebelum dimasukkan ke prompt AI.
    """
    if not text:
        return ''
    cleaned = text
    for pattern, replacement in _SANITIZE_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned.strip()


# ── CORE API CALLER ──────────────────────────────────────────────────────

def _call_deepseek(prompt: str, system_prompt: str = SYSTEM_PROMPT_RS,
                   model: str = None, temperature: float = None,
                   max_tokens: int = None) -> dict:
    """
    Panggil DeepSeek API dari backend. API Key TIDAK pernah bocor ke frontend.

    Returns:
        dict: {'success': bool, 'data': dict|None, 'error': str|None}
    """
    from .system_models import SystemConfig
    config = SystemConfig.get_solo()

    if not config.ai_enabled:
        return {'success': False, 'error': 'Fitur AI belum diaktifkan. Hubungi Super Admin.'}

    api_key = config.get_deepseek_api_key()
    if not api_key:
        return {'success': False, 'error': 'API Key DeepSeek belum dikonfigurasi. Hubungi Super Admin.'}

    _model = model or config.ai_model_name
    _temp = temperature if temperature is not None else config.ai_temperature
    _max_tok = max_tokens or config.ai_max_tokens

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }

    payload = {
        'model': _model,
        'messages': [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': _temp,
        'max_tokens': _max_tok,
        'response_format': {'type': 'json_object'},
    }

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content']
        parsed = json.loads(content)
        return {'success': True, 'data': parsed, 'error': None}

    except requests.exceptions.Timeout:
        logger.warning('DeepSeek API timeout setelah %ds', DEFAULT_TIMEOUT)
        return {'success': False, 'error': f'Koneksi ke AI timeout ({DEFAULT_TIMEOUT}s). Coba lagi sebentar.'}

    except requests.exceptions.HTTPError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            pass
        msg = body.get('error', {}).get('message', str(e))
        if 'insufficient_balance' in msg or 'quota' in msg.lower():
            return {'success': False, 'error': 'Kuota API DeepSeek habis. Hubungi Super Admin untuk top-up.'}
        logger.error('DeepSeek HTTP error: %s | body: %s', e, body)
        return {'success': False, 'error': f'Error API: {msg[:120]}'}

    except (json.JSONDecodeError, KeyError, IndexError) as e:
        logger.error('DeepSeek parse error: %s', e)
        return {'success': False, 'error': 'Respons AI tidak valid. Coba ulangi request.'}

    except Exception as e:
        logger.exception('DeepSeek unexpected error')
        return {'success': False, 'error': f'Error tidak terduga: {str(e)[:100]}'}


def _log_ai_call(user, modul: str, prompt_summary: str, success: bool):
    """Catat setiap panggilan AI ke AuditLog untuk audit trail akreditasi."""
    try:
        from .models import AuditLog
        status = 'SUKSES' if success else 'GAGAL'
        AuditLog.objects.create(
            user=user,
            aksi='CREATE',
            model_name='AI_DEEPSEEK',
            object_repr=f'AI Generate ({modul})',
            detail=f'[{status}] Modul: {modul} | {prompt_summary[:120]}',
        )
    except Exception as e:
        logger.warning('Gagal catat AuditLog AI: %s', e)


# ── 1. GENERATE MITIGASI RISIKO ──────────────────────────────────────────

def generate_risk_mitigation(user, unit_name: str, kategori_risiko: str,
                              jenis_risiko: str, deskripsi_risiko: str,
                              dampak: int, probabilitas: int, strategi: str) -> dict:
    """Hasilkan rencana mitigasi risiko otomatis dari konteks risiko unit."""
    from .system_models import SystemConfig
    if not SystemConfig.get_solo().ai_enable_risiko:
        return {'success': False, 'error': 'Fitur AI untuk modul Risiko belum diaktifkan.'}

    skor = dampak * probabilitas
    level_map = {range(1, 6): 'RENDAH', range(6, 11): 'SEDANG', range(11, 16): 'TINGGI', range(16, 26): 'SANGAT TINGGI'}
    level = next((v for k, v in level_map.items() if skor in k), 'SEDANG')

    prompt = PROMPT_MITIGASI_RISIKO.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        kategori_risiko=sanitize_hospital_prompt(kategori_risiko),
        jenis_risiko=sanitize_hospital_prompt(jenis_risiko),
        deskripsi_risiko=sanitize_hospital_prompt(deskripsi_risiko),
        dampak=dampak, probabilitas=probabilitas, skor=skor, level=level,
        strategi=sanitize_hospital_prompt(strategi),
    )

    result = _call_deepseek(prompt)
    _log_ai_call(user, 'RISIKO', f'{unit_name} | {jenis_risiko[:60]}', result['success'])
    return result


# ── 2. GENERATE PDCA ACTION PLAN ─────────────────────────────────────────

def generate_pdca_action_plan(user, ep_code: str, ep_name: str, ep_desc: str,
                               unit_name: str, current_score: int,
                               eval_notes: str = '') -> dict:
    """Hasilkan rencana siklus PDCA otomatis untuk satu Elemen Penilaian."""
    from .system_models import SystemConfig
    if not SystemConfig.get_solo().ai_enable_pdca:
        return {'success': False, 'error': 'Fitur AI untuk modul PDCA belum diaktifkan.'}

    prompt = PROMPT_PDCA_ACTION_PLAN.format(
        ep_code=ep_code,
        ep_name=sanitize_hospital_prompt(ep_name),
        ep_desc=sanitize_hospital_prompt(ep_desc),
        unit_name=sanitize_hospital_prompt(unit_name),
        current_score=current_score,
        eval_notes=sanitize_hospital_prompt(eval_notes or '(belum ada catatan evaluasi)'),
    )

    result = _call_deepseek(prompt)
    _log_ai_call(user, 'PDCA', f'EP {ep_code} | {unit_name}', result['success'])
    return result


# ── 3. GRADING INSIDEN KESELAMATAN PASIEN ────────────────────────────────

def generate_insiden_grading(user, jenis_insiden: str, tingkat_keparahan: str,
                              lokasi_kejadian: str, deskripsi_kejadian: str,
                              tindakan_segera: str, pasien_terpapar: bool,
                              unit_name: str) -> dict:
    """Hasilkan grading IKP dan rekomendasi investigasi (Sederhana vs RCA)."""
    from .system_models import SystemConfig
    if not SystemConfig.get_solo().ai_enable_insiden:
        return {'success': False, 'error': 'Fitur AI untuk modul Insiden belum diaktifkan.'}

    prompt = PROMPT_INSIDEN_GRADING.format(
        jenis_insiden=sanitize_hospital_prompt(jenis_insiden),
        tingkat_keparahan=sanitize_hospital_prompt(tingkat_keparahan),
        lokasi_kejadian=sanitize_hospital_prompt(lokasi_kejadian),
        deskripsi_kejadian=sanitize_hospital_prompt(deskripsi_kejadian),
        tindakan_segera=sanitize_hospital_prompt(tindakan_segera or '(tidak disebutkan)'),
        pasien_terpapar='Ya' if pasien_terpapar else 'Tidak',
        unit_name=sanitize_hospital_prompt(unit_name),
    )

    result = _call_deepseek(prompt)
    _log_ai_call(user, 'INSIDEN', f'{jenis_insiden[:60]} | {unit_name}', result['success'])
    return result


# ── 4. EVALUASI EFEKTIVITAS MITIGASI ─────────────────────────────────────

def generate_evaluasi_risiko(user, unit_name: str, jenis_risiko: str,
                              deskripsi_risiko: str, skor_awal: int,
                              dampak_awal: int, prob_awal: int,
                              mitigasi_terlaksana: str, dampak_residual: int,
                              prob_residual: int, status: str) -> dict:
    """Hasilkan evaluasi efektivitas mitigasi dan saran tindak lanjut."""
    from .system_models import SystemConfig
    if not SystemConfig.get_solo().ai_enable_risiko:
        return {'success': False, 'error': 'Fitur AI untuk modul Risiko belum diaktifkan.'}

    prompt = PROMPT_EVALUASI_RISIKO.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        jenis_risiko=sanitize_hospital_prompt(jenis_risiko),
        deskripsi_risiko=sanitize_hospital_prompt(deskripsi_risiko),
        skor_awal=skor_awal, dampak_awal=dampak_awal, prob_awal=prob_awal,
        mitigasi_terlaksana=sanitize_hospital_prompt(mitigasi_terlaksana or '(belum diisi)'),
        dampak_residual=dampak_residual, prob_residual=prob_residual,
        status=status,
    )

    result = _call_deepseek(prompt)
    _log_ai_call(user, 'EVALUASI_RISIKO', f'{unit_name} | {jenis_risiko[:60]}', result['success'])
    return result


# ── 5. ANALISIS KELENGKAPAN RDWOS ────────────────────────────────────────

def generate_rdwos_analisis(user, ep_code: str, ep_name: str,
                             dokumen_ada: int, total_kebutuhan: int,
                             jenis_dokumen: list) -> dict:
    """Analisis kelengkapan dokumen bukti RDWOS dan rekomendasikan yang kurang."""
    from .system_models import SystemConfig
    if not SystemConfig.get_solo().ai_enable_rdwos:
        return {'success': False, 'error': 'Fitur AI untuk modul RDWOS belum diaktifkan.'}

    prompt = PROMPT_RDWOS_ANALISIS.format(
        ep_code=ep_code,
        ep_name=sanitize_hospital_prompt(ep_name),
        dokumen_ada=dokumen_ada,
        total_kebutuhan=total_kebutuhan,
        jenis_dokumen=', '.join(jenis_dokumen) if jenis_dokumen else '(belum ada)',
    )

    result = _call_deepseek(prompt)
    _log_ai_call(user, 'RDWOS', f'EP {ep_code} | {dokumen_ada}/{total_kebutuhan} dokumen', result['success'])
    return result


# ── 6. REKOMENDASI KPS KREDENSIAL NAKES ──────────────────────────────────

def generate_kps_rekomendasi(user, profesi: str, jabatan: str, unit_name: str,
                              daftar_kredensial: list, segera_expired: list,
                              pelatihan: list) -> dict:
    """Hasilkan rekomendasi kelengkapan kredensial & pelatihan wajib nakes."""
    from .system_models import SystemConfig
    if not SystemConfig.get_solo().ai_enable_kps:
        return {'success': False, 'error': 'Fitur AI untuk modul KPS belum diaktifkan.'}

    prompt = PROMPT_KPS_REKOMENDASI.format(
        profesi=sanitize_hospital_prompt(profesi),
        jabatan=sanitize_hospital_prompt(jabatan),
        unit_name=sanitize_hospital_prompt(unit_name),
        daftar_kredensial=', '.join(daftar_kredensial) if daftar_kredensial else '(belum ada)',
        segera_expired=', '.join(segera_expired) if segera_expired else 'Tidak ada',
        pelatihan=', '.join(pelatihan) if pelatihan else '(belum ada)',
    )

    result = _call_deepseek(prompt)
    _log_ai_call(user, 'KPS', f'{profesi} | {unit_name}', result['success'])
    return result


# ── 7. FORMULASI INDIKATOR MUTU ──────────────────────────────────────────

def generate_indicator_draft(user, nama_indikator: str, unit_name: str,
                              jenis: str, masalah: str) -> dict:
    """Rumuskan formula indikator mutu (numerator, denominator, target, dimensi, rencana aksi)."""
    prompt = PROMPT_INDIKATOR_MUTU.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        jenis=jenis,
        nama_indikator=sanitize_hospital_prompt(nama_indikator),
        masalah=sanitize_hospital_prompt(masalah),
    )
    result = _call_deepseek(prompt)
    _log_ai_call(user, 'INDIKATOR_MUTU', f'{jenis} | {unit_name} | {nama_indikator[:50]}', result['success'])
    return result


# ── 8. ANALISIS MASALAH & SARAN KATEGORI/JENIS RISIKO (STANDAR 5.15) ─────

def generate_risk_analysis_from_problem(user, unit_name: str, masalah: str, data_pendukung: str) -> dict:
    """Analisis masalah dan data pendukung untuk merekomendasikan kategori dan daftar jenis risiko."""
    prompt = PROMPT_ANALISIS_MASALAH_RISIKO.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        masalah=sanitize_hospital_prompt(masalah),
        data_pendukung=sanitize_hospital_prompt(data_pendukung),
    )
    result = _call_deepseek(prompt)
    _log_ai_call(user, 'ANALISIS_MASALAH_RISIKO', f'{unit_name} | {masalah[:50]}', result['success'])
    return result


# ── SECTION E: FMEA (Proaktif) ───────────────────────────────────────────

def generate_fmea_suggestion(user, unit_name: str, kategori_risiko: str, jenis_risiko: str,
                             masalah: str, data_pendukung: str,
                             dampak: int, probabilitas: int) -> dict:
    """Hasilkan analisis FMEA proaktif: failure mode, efek, penyebab, barrier, RPN."""
    prompt = PROMPT_FMEA_SUGGESTION.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        kategori_risiko=sanitize_hospital_prompt(kategori_risiko),
        jenis_risiko=sanitize_hospital_prompt(jenis_risiko),
        masalah=sanitize_hospital_prompt(masalah),
        data_pendukung=sanitize_hospital_prompt(data_pendukung),
        dampak=dampak,
        probabilitas=probabilitas,
    )
    result = _call_deepseek(prompt)
    _log_ai_call(user, 'FMEA_SUGGESTION', f'{unit_name} | {jenis_risiko[:50]}', result['success'])
    return result


# ── SECTION E: RCA (Reaktif) ─────────────────────────────────────────────

def generate_rca_suggestion(user, unit_name: str, jenis_risiko: str,
                            masalah: str, data_pendukung: str,
                            dampak: int, probabilitas: int) -> dict:
    """Hasilkan analisis RCA reaktif: 5-Whys, fishbone, tindakan korektif."""
    prompt = PROMPT_RCA_SUGGESTION.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        jenis_risiko=sanitize_hospital_prompt(jenis_risiko),
        masalah=sanitize_hospital_prompt(masalah),
        data_pendukung=sanitize_hospital_prompt(data_pendukung),
        dampak=dampak,
        probabilitas=probabilitas,
    )
    result = _call_deepseek(prompt)
    _log_ai_call(user, 'RCA_SUGGESTION', f'{unit_name} | {jenis_risiko[:50]}', result['success'])
    return result


# ── UTILITY: Cek Koneksi API ─────────────────────────────────────────────

def test_deepseek_connection() -> dict:
    """Tes koneksi ke DeepSeek API — digunakan di Pusat Kontrol Admin."""
    from .system_models import SystemConfig
    config = SystemConfig.get_solo()
    api_key = config.get_deepseek_api_key()

    if not api_key:
        return {'success': False, 'error': 'API Key belum dikonfigurasi.'}

    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': config.ai_model_name,
        'messages': [{'role': 'user', 'content': 'Jawab hanya: OK'}],
        'max_tokens': 5,
    }
    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=15)
        resp.raise_for_status()
        return {'success': True, 'model': config.ai_model_name, 'status': 'Koneksi berhasil ✓'}
    except requests.exceptions.HTTPError as e:
        body = {}
        try:
            body = e.response.json()
        except Exception:
            pass
        msg = body.get('error', {}).get('message', str(e))
        return {'success': False, 'error': f'API error: {msg[:150]}'}
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'Timeout — server DeepSeek tidak merespons dalam 15 detik.'}
    except Exception as e:
        return {'success': False, 'error': str(e)[:150]}
