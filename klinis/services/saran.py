"""Saran diagnosis dari katalog kasus tersering — deterministik, tanpa LLM."""

import re

from klinis.models import KasusTersering
from klinis.services.tarif import _kelompok_for

_TOKEN = re.compile(r'[a-z]{3,}')


def _tokens(text):
    return set(_TOKEN.findall((text or '').lower()))


def saran_untuk(kunjungan, q='', jenis='ICD10', limit=5):
    """
    Saran ICD-10 (atau kode kasus) untuk satu kunjungan.

    Skor = jumlah token kueri (>= 3 huruf) yang muncul pada nama diagnosis atau
    tatalaksana kasus. Tanpa kueri, kembalikan kasus dengan urutan teratas pada
    kelompok layanan kunjungan. Hasil selalu dibatasi ke kelompok kunjungan:
    saran IGD tidak boleh menawarkan kasus rawat inap jantung.
    """
    kelompok = _kelompok_for(kunjungan)
    if not kelompok:
        return []

    rows = (
        KasusTersering.objects
        .filter(kelompok=kelompok)
        .select_related('icd10')
        .prefetch_related('tindakan__icd9')
        .order_by('urutan')
    )

    q_tokens = _tokens(q)
    scored = []
    for row in rows:
        if jenis == 'ICD10' and not row.icd10_id:
            continue
        haystack = ' '.join(filter(None, [
            row.icd10.nama if row.icd10 else '',
            row.sdki_nama,
            row.tatalaksana,
            row.kewenangan,
        ]))
        score = len(q_tokens & _tokens(haystack)) if q_tokens else 0
        if q_tokens and score == 0:
            continue
        scored.append((score, row))

    scored.sort(key=lambda item: (-item[0], item[1].urutan))

    results = []
    for score, row in scored[:limit]:
        results.append({
            'kode': row.icd10.kode if row.icd10 else row.sdki_kode,
            'nama': row.icd10.nama if row.icd10 else row.sdki_nama,
            'alasan': (row.tatalaksana or '')[:160],
            'skor': score,
            'tindakan': [t.icd9.kode for t in row.tindakan.all()],
        })
    return results
