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
import time
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
    PROMPT_EP_MATCH,
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
                   max_tokens: int = None, timeout: int = None) -> dict:
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
    _max_tok = max_tokens or max(config.ai_max_tokens or 2500, 2500)

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

    _timeout = timeout or DEFAULT_TIMEOUT

    try:
        resp = requests.post(DEEPSEEK_API_URL, headers=headers, json=payload, timeout=_timeout)
        resp.raise_for_status()
        content = resp.json()['choices'][0]['message']['content']
        parsed = json.loads(content)
        return {'success': True, 'data': parsed, 'error': None}

    except requests.exceptions.Timeout:
        logger.warning('DeepSeek API timeout setelah %ds', _timeout)
        return {'success': False, 'error': f'Koneksi ke AI timeout ({_timeout}s). Coba lagi sebentar.'}

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

def _generate_fallback_evaluasi(unit_name: str, jenis_risiko: str, nama_indikator: str,
                                target_capaian: str, capaian_nilai: str,
                                mitigasi_terlaksana: str, skor_awal: int,
                                dampak_residual: int, prob_residual: int) -> dict:
    try:
        c_val = float(str(capaian_nilai).replace(',', '.').replace('%', '').strip()) if capaian_nilai else None
    except (ValueError, TypeError):
        c_val = None
    try:
        t_val = float(str(target_capaian).replace(',', '.').replace('%', '').strip()) if target_capaian else 100.0
    except (ValueError, TypeError):
        t_val = 100.0

    ind_name = nama_indikator.strip() if nama_indikator else (jenis_risiko or 'mutu unit')
    unit = unit_name.strip() if unit_name else 'unit kerja'
    mitigasi_clean = (mitigasi_terlaksana or '').strip() or 'rencana mitigasi terpasang'

    if c_val is not None:
        gap = c_val - t_val
        is_achieved = gap >= 0
        gap_display = f"{gap:+.1f}%"
        c_display = f"{c_val:.1f}%"
    else:
        is_achieved = False
        gap_display = "belum terukur"
        c_display = "belum dilaporkan"

    if is_achieved:
        efektivitas = "Efektif"
        analisis_capaian = (
            f"Realisasi capaian indikator {ind_name} mencapai {c_display}, "
            f"memenuhi target standar {t_val:.1f}% (surplus {gap_display}). "
            f"Pengendalian operasional di {unit} berjalan stabil dan sesuai SPO."
        )
        efektivitas_barrier = (
            f"Tindakan mitigasi '{mitigasi_clean}' terbukti efektif memperkecil frekuensi "
            f"kegagalan serta menurunkan potensi risiko di {unit}."
        )
        kendala_lapangan = (
            "Tantangan utama adalah menjaga kontinuitas kepatuhan seluruh shift kerja "
            "dan pemeliharaan sarana/prasarana pendukung agar pencapaian target tetap konsisten."
        )
        rekomendasi_status = "SELESAI" if (dampak_residual and prob_residual and dampak_residual * prob_residual <= 4) else "MONITORING"
    else:
        efektivitas = "Sebagian Efektif" if (c_val and c_val >= t_val * 0.7) else "Belum Efektif"
        analisis_capaian = (
            f"Realisasi capaian indikator {ind_name} tercatat sebesar {c_display}, "
            f"belum memenuhi target standar {t_val:.1f}% (terdapat deviasi {gap_display}). "
            f"Diperlukan pengawasan kepatuhan berkala dan percepatan tindakan perbaikan."
        )
        efektivitas_barrier = (
            f"Mitigasi '{mitigasi_clean}' telah dilaksanakan namun belum sepenuhnya "
            f"mengeliminasi faktor determinan risiko di {unit}."
        )
        kendala_lapangan = (
            "Ditemukan fluktuasi beban pelayanan, pemahaman staf yang belum merata terhadap standar teknis, "
            "serta perlunya supervisi berjenjang yang lebih terjadwal."
        )
        rekomendasi_status = "MITIGASI"

    draf_evaluasi = (
        f"1. Analisis Capaian: {analisis_capaian}\n\n"
        f"2. Evaluasi Barrier/Mitigasi: {efektivitas_barrier}\n\n"
        f"3. Kendala di Lapangan: {kendala_lapangan}"
    )

    tindak_lanjut = (
        f"1. Re-evaluasi kepatuhan pelaksanaan SPO {ind_name} dan lakukan coaching bagi staf {unit}.\n"
        f"2. Optimalkan pencatatan harian dan monitoring berkala oleh Kepala Ruangan / Penanggung Jawab.\n"
        f"3. Pastikan kelengkapan logistik dan barrier keselamatan pasien siap pakai 100%."
    )

    return {
        'efektivitas': efektivitas,
        'analisis_capaian': analisis_capaian,
        'efektivitas_barrier': efektivitas_barrier,
        'kendala_lapangan': kendala_lapangan,
        'draf_evaluasi': draf_evaluasi,
        'analisis': f"Mitigasi dinilai {efektivitas.lower()} dengan capaian {c_display} terhadap target {t_val:.1f}%.",
        'tindak_lanjut': tindak_lanjut,
        'rekomendasi_status': rekomendasi_status,
        'catatan': f"Dokumentasi evaluasi mutu terstruktur untuk verifikasi STARKES PMKP {unit}.",
    }


def generate_evaluasi_risiko(user, unit_name: str, jenis_risiko: str,
                              deskripsi_risiko: str, skor_awal: int,
                              dampak_awal: int, prob_awal: int,
                              mitigasi_terlaksana: str, dampak_residual: int,
                              prob_residual: int, status: str,
                              nama_indikator: str = '', target_capaian: str = '',
                              capaian_nilai: str = '', gap_persen: str = '') -> dict:
    """Hasilkan evaluasi efektivitas mitigasi dan saran tindak lanjut."""
    from .system_models import SystemConfig
    config = SystemConfig.get_solo()

    # Rule-based fallback data generator
    fallback_data = _generate_fallback_evaluasi(
        unit_name=unit_name,
        jenis_risiko=jenis_risiko,
        nama_indikator=nama_indikator,
        target_capaian=target_capaian,
        capaian_nilai=capaian_nilai,
        mitigasi_terlaksana=mitigasi_terlaksana,
        skor_awal=skor_awal,
        dampak_residual=dampak_residual,
        prob_residual=prob_residual,
    )

    if not config.ai_enable_risiko or not config.ai_enabled or not config.get_deepseek_api_key():
        # Gunakan fallback cerdas terstruktur bila AI external tidak aktif/tanpa key
        return {'success': True, 'data': fallback_data, 'fallback': True, 'error': None}

    prompt = PROMPT_EVALUASI_RISIKO.format(
        unit_name=sanitize_hospital_prompt(unit_name),
        jenis_risiko=sanitize_hospital_prompt(jenis_risiko),
        deskripsi_risiko=sanitize_hospital_prompt(deskripsi_risiko),
        nama_indikator=sanitize_hospital_prompt(nama_indikator or '(belum ditautkan)'),
        target_capaian=target_capaian or '100%',
        capaian_nilai=capaian_nilai or '(belum diisi)',
        gap_persen=gap_persen or '(belum dihitung)',
        skor_awal=skor_awal, dampak_awal=dampak_awal, prob_awal=prob_awal,
        mitigasi_terlaksana=sanitize_hospital_prompt(mitigasi_terlaksana or '(belum diisi)'),
        dampak_residual=dampak_residual, prob_residual=prob_residual,
        status=status,
    )

    result = _call_deepseek(prompt)
    if not result.get('success') or not result.get('data'):
        # Fallback bila API timeout atau error
        result = {'success': True, 'data': fallback_data, 'fallback': True, 'error': None}
    else:
        # Pastikan draf_evaluasi selalu tersedia di data response
        d = result['data']
        if not d.get('draf_evaluasi'):
            d['draf_evaluasi'] = (
                f"1. Analisis Capaian: {d.get('analisis_capaian', d.get('analisis', ''))}\n\n"
                f"2. Evaluasi Barrier/Mitigasi: {d.get('efektivitas_barrier', '')}\n\n"
                f"3. Kendala di Lapangan: {d.get('kendala_lapangan', '')}"
            ).strip()

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

def normalize_fmea_text(text: str, daftar_modes: list = None) -> str:
    """Susun format nomor urut FMEA hierarkis, rapi, dan mudah dibaca."""
    if isinstance(daftar_modes, list) and len(daftar_modes) > 0:
        blocks = []
        for idx, item in enumerate(daftar_modes, 1):
            if not isinstance(item, dict):
                continue
            m = (item.get('mode') or '').strip()
            e = (item.get('efek') or '').strip()
            p = (item.get('penyebab') or '').strip()
            b = (item.get('barrier') or '').strip()
            if not m:
                continue
            lines = [f"{idx}. MODE KEGAGALAN:\n   {m}"]
            if e:
                lines.append(f"   a. Efek Potensial:\n      {e}")
            if p:
                lines.append(f"   b. Akar Masalah / Penyebab:\n      {p}")
            if b:
                lines.append(f"   c. Barrier / Kontrol Pencegahan:\n      {b}")
            blocks.append("\n".join(lines))
        if blocks:
            return "\n\n".join(blocks)

    if not text or not isinstance(text, str):
        return ""

    parts = re.split(r"(?:^|\n+)(?:\d+[\.\)]\s*(?:Mode Kegagalan:?)?)", text.strip(), flags=re.IGNORECASE)
    parts = [p.strip() for p in parts if p.strip()]
    if not parts:
        return text.strip()

    formatted_items = []
    for idx, part in enumerate(parts, 1):
        m_efek = re.search(r"Efek(?: Potensial)?\s*:\s*([\s\S]*?)(?=(?:Penyebab|Akar Masalah|Barrier|Kontrol|$))", part, re.IGNORECASE)
        m_penyebab = re.search(r"(?:Penyebab(?: Potensial)?|Akar Masalah)\s*:\s*([\s\S]*?)(?=(?:Barrier|Kontrol|$))", part, re.IGNORECASE)
        m_barrier = re.search(r"(?:Barrier(?: Pencegahan)?|Kontrol(?: Pencegahan)?)\s*:\s*([\s\S]*)$", part, re.IGNORECASE)

        mode_text = part
        if m_efek:
            mode_text = mode_text[:m_efek.start()]
        elif m_penyebab:
            mode_text = mode_text[:m_penyebab.start()]
        elif m_barrier:
            mode_text = mode_text[:m_barrier.start()]
        mode_text = re.sub(r"^[\s\:\-]+", "", mode_text).strip()

        efek_text = m_efek.group(1).strip() if m_efek else ""
        penyebab_text = m_penyebab.group(1).strip() if m_penyebab else ""
        barrier_text = m_barrier.group(1).strip() if m_barrier else ""

        lines = [f"{idx}. MODE KEGAGALAN:\n   {mode_text}"]
        if efek_text:
            lines.append(f"   a. Efek Potensial:\n      {efek_text}")
        if penyebab_text:
            lines.append(f"   b. Akar Masalah / Penyebab:\n      {penyebab_text}")
        if barrier_text:
            lines.append(f"   c. Barrier / Kontrol Pencegahan:\n      {barrier_text}")
        formatted_items.append("\n".join(lines))

    return "\n\n".join(formatted_items) if formatted_items else text.strip()


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
    result = _call_deepseek(prompt, max_tokens=2500)
    if result.get('success') and isinstance(result.get('data'), dict):
        d = result['data']
        d['failure_mode'] = normalize_fmea_text(d.get('failure_mode') or '', d.get('daftar_failure_mode'))
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
    result = _call_deepseek(prompt, max_tokens=2500)
    if result.get('success') and isinstance(result.get('data'), dict):
        d = result['data']
        if d.get('akar_masalah') and isinstance(d['akar_masalah'], str):
            lines = [l.strip() for l in d['akar_masalah'].split('\n') if l.strip()]
            d['akar_masalah'] = '\n'.join(lines)
    _log_ai_call(user, 'RCA_SUGGESTION', f'{unit_name} | {jenis_risiko[:50]}', result['success'])
    return result


# ── UTILITY: Cek Koneksi API ─────────────────────────────────────────────

# ── SINKRONISASI INDIKATOR MUTU <-> EP (STARKES) ────────────────────────────
#
# Tier C: katalog EP dikirim UTUH dalam satu panggilan (terukur 1053 baris,
# ~116 KB, ~33-46k token — masih di bawah konteks deepseek-chat 64k). Penyaring
# lexical sengaja TIDAK dipakai sebagai gerbang: presisi@1-nya hanya 10% pada
# 72 link manual, dan 17 dari 36 kasus yang meleset tidak berbagi satu kata pun
# dengan teks EP yang benar, sehingga gerbang katas akan mematikan jawaban yang
# sebenarnya mampu ditemukan model.

def generate_ep_rekomendasi(user, ind, petunjuk_unit: str = '') -> dict:
    """Rekomendasi EP untuk sebuah indikator mutu via DeepSeek.

    Mengembalikan ``{'success': bool, 'data': {...}, 'error': str|None,
    'ai_terpakai': bool}``. Saat AI mati/gagal, hasil lexical Tier B tetap
    dikembalikan agar pemanggil tidak pernah pecah.
    """
    from .system_models import SystemConfig
    from . import ep_sync
    # Durasi ikut tercatat: regresi 60s batas Vercel terlihat di AuditLog tanpa
    # perlu mereproduksi secara manual.
    _mulai = time.monotonic()

    def _lexical(reason: str, ai_terpakai: bool = False) -> dict:
        kandidat = ep_sync.lexical_top(ind, n=5)
        # Tier B ikut tercatat: tanpa ini kegagalan AI (timeout, kunci mati,
        # kehabisan durasi) tidak meninggalkan jejak dan tidak pernah diperbaiki.
        _log_ai_call(user, 'EP_SYNC',
                     f'{time.monotonic() - _mulai:.1f}s | '
                     f'{getattr(ind, "kode_indikator", "-")} -> LEXICAL, {reason[:60]}',
                     ai_terpakai)
        return {
            'success': True,
            'ai_terpakai': ai_terpakai,
            'error': None if ai_terpakai else reason,
            'data': {
                'sumber': 'LEXICAL',
                'rekomendasi': [{
                    'ep_code': k['code'], 'confidence': float(k['skor']),
                    'alasan': 'Kecocokan kata dengan teks EP.', 'dari_unit': k['dari_unit'],
                } for k in kandidat],
            },
        }

    config = SystemConfig.get_solo()
    if not getattr(config, 'ai_enable_ep_sync', True):
        return _lexical('Fitur AI sinkronisasi EP dimatikan; memakai kecocokan kata.')
    if not config.ai_enabled:
        return _lexical('AI belum diaktifkan; memakai kecocokan kata.')

    lines, codes, n_ep = ep_sync.build_ep_catalog()
    prompt = PROMPT_EP_MATCH.format(
        kode=sanitize_hospital_prompt(getattr(ind, 'kode_indikator', '') or '-'),
        nama=sanitize_hospital_prompt(getattr(ind, 'nama_indikator', '') or '-'),
        numerator=sanitize_hospital_prompt(getattr(ind, 'numerator', '') or '-'),
        denominator=sanitize_hospital_prompt(getattr(ind, 'denominator', '') or '-'),
        jenis=getattr(ind, 'jenis', '') or '-',
        dimensi=getattr(ind, 'get_dimensi_mutu_display', lambda: '-')() if hasattr(ind, 'get_dimensi_mutu_display') else '-',
        unit=sanitize_hospital_prompt(getattr(getattr(ind, 'unit', None), 'name', '') or '-'),
        petunjuk_unit=petunjuk_unit or '(tidak ada pemetaan pokja untuk unit ini)',
        n_ep=n_ep,
        daftar_ep='\n'.join(lines),
    )

    # Output kecil (maks 5 entri) tapi input ~35k token: default 30s terlalu
    # ketat untuk prompt sebesar ini — tetapi 120s juga salah. `vercel.json`
    # membatasi fungsi ini 60 detik; HTTP client yang menunggu lebih lama dari
    # itu mendapat 504 HTML dari Lambda sebelum proses sempat mencapai fallback
    # Tier B, sehingga operator menerima "Unexpected token <". Batasi client di
    # bawah batas fungsi: 45s menyisakan ruang untuk fallback dan render.
    result = _call_deepseek(prompt, max_tokens=1200, timeout=45)
    if not result.get('success'):
        return _lexical(result.get('error') or 'Panggilan AI gagal; memakai kecocokan kata.')

    raw = result.get('data') or {}
    items = raw.get('rekomendasi')
    if not isinstance(items, list):
        return _lexical('Balasan AI tidak berisi daftar rekomendasi.')

    cleaned = []
    ditolak = 0
    for it in items[:5]:
        if not isinstance(it, dict):
            ditolak += 1
            continue
        code = str(it.get('ep_code') or '').strip()
        if code not in codes:          # anti-halusinasi: kode harus ada di katalog
            ditolak += 1
            continue
        try:
            conf = float(it.get('confidence', 0))
        except (TypeError, ValueError):
            conf = 0.0
        conf = min(max(conf, 0.0), 1.0)
        alasan = str(it.get('alasan') or '').strip()[:300]
        cleaned.append({'ep_code': code, 'confidence': conf, 'alasan': alasan})

    if not cleaned:
        return _lexical(f'AI tidak mengembalikan kode EP yang valid ({ditolak} ditolak).')

    cleaned.sort(key=lambda x: -x['confidence'])
    _log_ai_call(user, 'EP_SYNC',
                 f'{time.monotonic() - _mulai:.1f}s | '
                 f'{getattr(ind, "kode_indikator", "-")} -> {len(cleaned)}/{n_ep} EP, '
                 f'{ditolak} ditolak', True)
    return {
        'success': True,
        'ai_terpakai': True,
        'error': None,
        'ditolak': ditolak,
        'data': {'sumber': 'AI', 'rekomendasi': cleaned},
    }


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
