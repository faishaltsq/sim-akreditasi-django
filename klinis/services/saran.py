"""Saran diagnosis dari katalog kasus tersering — deterministik, tanpa LLM."""

import re

from klinis.models import KasusTersering, KasusTindakan
from klinis.services.tarif import _kelompok_for, resolve_detail

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

    if jenis == 'ICD9':
        results = []
        seen = set()
        penjamin = getattr(kunjungan, 'penjamin', 'UMUM')
        for _, row in scored:
            for t in row.tindakan.all():
                if t.icd9.kode in seen:
                    continue
                seen.add(t.icd9.kode)
                tarif = t.tarif_bpjs if penjamin == 'BPJS' else t.tarif_umum
                results.append({
                    'kode': t.icd9.kode,
                    'nama': t.icd9.nama,
                    'satuan': t.satuan,
                    'tarif': float(tarif) if tarif is not None else None,
                    'tarif_umum': float(t.tarif_umum) if t.tarif_umum is not None else None,
                    'tarif_bpjs': float(t.tarif_bpjs) if t.tarif_bpjs is not None else None,
                    'kasus_nama': row.icd10.nama if row.icd10 else '',
                })
                if len(results) >= limit:
                    break
            if len(results) >= limit:
                break
        return results

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


def tindakan_untuk_diagnosis(kunjungan, icd10_code, *, query='', limit=30):
    """
    Tindakan ICD-9 untuk satu diagnosis ICD-10 pada kelompok layanan kunjungan.

    Mencocokkan KasusTindakan melalui kasus.icd10.kode dan kasus.kelompok yang
    sama dengan kelompok kunjungan. Karena kasus tersering dapat memuat tindakan
    yang sama dengan tarif berbeda (kasus lebih awal mendahului), hasil dedupe
    berdasarkan kode ICD-9 dan tarif diselesaikan melalui resolver kunjungan
    (kelompok + penjamin) — bukan harga lokal baris.
    """
    from klinis.services.tarif import _kelompok_for, resolve_detail
    kelompok = _kelompok_for(kunjungan)
    if not kelompok:
        return []

    rows = (
        KasusTindakan.objects
        .filter(kasus__icd10__kode=icd10_code, kasus__kelompok=kelompok)
        .select_related('icd9', 'kasus', 'kasus__icd10')
        .order_by('kasus__urutan', 'urutan')
    )
    if not rows:
        return []

    # Dedupe kode ICD-9 sambil mempertahankan urutan kemunculan
    seen: list[str] = []
    for t in rows:
        if t.icd9 and t.icd9.kode not in seen:
            seen.append(t.icd9.kode)

    by_kode = {t.icd9.kode: t for t in rows if t.icd9}

    # terapkan query (tokenisasi nama/kode)
    query_code = query.strip().upper() if query else ''
    if limit is not None and limit <= 0:
        return []
    q_tokens = _tokens(query)
    if query_code or q_tokens:
        seen = [
            k for k in seen
            if (query_code and by_kode[k].icd9.kode.upper() == query_code)
            or (q_tokens and q_tokens & _tokens(by_kode[k].icd9.nama))
        ]

    results = []
    for kode in seen:
        t = by_kode[kode]
        detail = resolve_detail(kunjungan, t.icd9.kode)
        results.append({
            'kode': t.icd9.kode,
            'nama': t.icd9.nama,
            'satuan': t.satuan,
            'tarif': str(detail['nominal']) if detail and detail['nominal'] is not None else None,
            'kasus_nama': t.kasus.icd10.nama if t.kasus.icd10 else '',
        })
        if len(results) >= limit:
            break
    return results
