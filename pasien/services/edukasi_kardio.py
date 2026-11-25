"""Bukti edukasi terstruktur Langkah 8 (F5.5, matriks S8-L2-02).

Satu pembangun data dipakai oleh dua ekspor — PDF (``pasien/pdf_utils.py``)
dan halaman cetak (``templates/pasien/cetak_edukasi_kardio.html``) — supaya
keduanya tidak dapat menyimpang.

**Tanda tangan.** Matriks menuntut bukti bertanda tangan pasien/keluarga dan
edukator. Yang disimpan sistem adalah **nama** kedua pihak plus **cap waktu**
persetujuan; tidak ada gambar tanda tangan yang dikarang. Karena itu PDF
menyebut secara eksplisit bahwa cap waktu elektronik adalah buktinya, bukan
menampilkan tanda tangan palsu.

**Kelengkapan.** Bila edukasi belum dipilih, ekspor tetap dapat dibuat tetapi
dinyatakan belum lengkap — bukan dokumen kosong yang tampak sah.
"""
from django.utils import timezone

from pasien.workflow_schemas import EDUKASI_KARDIO_CHOICES, EDUKASI_KARDIO_LABELS


def edukasi_proof(visit, workflow, *, timestamp=None):
    """Data bukti edukasi untuk satu episode; murni baca, tanpa tulisan DB."""
    draft = (workflow.draft_payload or {}).get('8') if workflow is not None else {}
    draft = draft or {}
    selected = [code for code in (draft.get('edukasi') or []) if code in EDUKASI_KARDIO_CHOICES]
    edukator = getattr(workflow, 'updated_by', None)
    dpjp_text = visit.dpjp or ''
    return {
        'pasien': visit.pasien,
        'kunjungan': visit,
        'edukasi': [{'code': code, 'label': EDUKASI_KARDIO_LABELS[code]} for code in selected],
        # Seluruh materi matriks dengan penanda diberikan/belum, supaya dokumen
        # bukti dapat dinilai kelengkapannya tanpa membaca kode program.
        'materi': [
            {'code': code, 'label': EDUKASI_KARDIO_LABELS[code], 'given': code in selected}
            for code in EDUKASI_KARDIO_CHOICES
        ],
        'edukasi_lengkap': len(selected) == len(EDUKASI_KARDIO_CHOICES),
        'penerima': draft.get('edukasi_penerima') or visit.pasien.nama_lengkap,
        'edukator_nama': (
            (edukator.get_full_name() or edukator.username) if edukator else (dpjp_text or '-')
        ),
        'edukator_profesi': getattr(getattr(edukator, 'profile', None), 'profesi', '') or '',
        'cap_waktu': timestamp or timezone.now(),
        'catatan': draft.get('rencana_terapi') or '',
    }
