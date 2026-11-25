"""Bukti pelaksanaan EP untuk satu kunjungan (F7.6).

Satu sumber data untuk dua ekspor: halaman cetak ``cetak_bukti_ep.html`` dan
PDF ``generate_bukti_ep_pdf``. Tidak ada kode EP yang ditulis di sini — seluruh
baris berasal dari ``KorelasiEpAsesmen`` dan ``TindakanAsesmen``, yang isinya
ditentukan aturan EP (ADR-7).
"""
from django.utils import timezone

STATUS_LABEL = {
    'TERPENUHI': 'Terpenuhi',
    'BELUM': 'Belum Terpenuhi',
    'NA': 'Tidak Berlaku',
}

def _verifier(row):
    user = getattr(row, 'diverifikasi_oleh', None)
    if user is None:
        return ''
    return user.get_full_name() or user.username

def evidence_rows(visit):
    """Baris bukti EP asesmen: kode + status + catatan + verifikator + waktu."""
    rows = []
    for row in (
        visit.korelasi_ep
        .select_related('standard_item__category', 'diverifikasi_oleh')
        .order_by('standard_item__category__order', 'standard_item__order', 'pk')
    ):
        rows.append({
            'source': 'ASESMEN',
            'sub_standard': row.standard_item.sub_standard,
            'category': row.standard_item.category.code,
            'code': row.standard_item.code,
            'title': row.standard_item.sub_title or row.standard_item.sub_standard,
            'status': row.status,
            'status_label': STATUS_LABEL.get(row.status, row.status),
            'catatan': row.catatan,
            'verifier': _verifier(row),
            'verified_at': row.diverifikasi_pada,
        })
    return rows

def action_rows(visit):
    """Baris bukti EP tindakan: kode tindakan + EP + status + catatan."""
    rows = []
    for line in (
        visit.tindakan_asesmen
        .select_related('standard_item__category')
        .order_by('urutan', 'pk')
    ):
        item = line.standard_item
        rows.append({
            'source': 'TINDAKAN',
            'kode_tindakan': line.kode or line.nama,
            'nama': line.nama,
            'sub_standard': item.sub_standard if item else '',
            'code': item.code if item else '',
            'title': (item.sub_title or item.sub_standard) if item else '',
            'status': line.ep_status or '',
            'status_label': STATUS_LABEL.get(line.ep_status, 'Belum dinilai'),
            'catatan': line.ep_catatan,
            'verifier': '',
            'verified_at': line.recorded_at,
        })
    return rows

def bukti_ep(visit):
    """Konteks bukti EP satu kunjungan; dipakai template dan PDF."""
    workflow = getattr(visit, 'igd_workflow', None)
    asesmen = evidence_rows(visit)
    tindakan = action_rows(visit)
    terpenuhi = sum(1 for row in asesmen if row['status'] == 'TERPENUHI')
    return {
        'kunjungan': visit,
        'pasien': visit.pasien,
        'workflow': workflow,
        'asesmen': asesmen,
        'tindakan': tindakan,
        'terpenuhi': terpenuhi,
        'total_asesmen': len(asesmen),
        'generated_at': timezone.localtime(),
    }
