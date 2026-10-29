"""Kategori & metrik Aktivitas. Memetakan 63 nilai jenis_peristiwa yang ada
ke enam kategori spec; nilai yang tidak dikenali jatuh ke SYSTEM."""
from django.db.models import Q

PREFIX_MAP = [
    ('health_', 'SYSTEM'),
    ('k3_', 'SYSTEM'),
    ('logbook_', 'VERIFIKASI'),
    ('credential_', 'VERIFIKASI'),
    ('syarat_', 'VERIFIKASI'),
    ('peer_review_', 'VERIFIKASI'),
    ('spk_', 'VERIFIKASI'),
    ('rkk_', 'VERIFIKASI'),
    ('berita_acara_', 'VERIFIKASI'),
    ('recruitment_', 'VERIFIKASI'),
    ('private_document_', 'UPLOAD_DOC'),
    ('legacy_credential_', 'UPLOAD_DOC'),
    ('psv_', 'UPLOAD_DOC'),
    ('employee_', 'UPDATE_PROFILE'),
    ('riwayat_kepegawaian_', 'UPDATE_PROFILE'),
    ('hc_grant_', 'UPDATE_PROFILE'),
    ('account_invitation_', 'UPDATE_PROFILE'),
    ('staff_request_', 'UPDATE_PROFILE'),
    ('appraisal_', 'VERIFIKASI'),
    ('training_', 'SYSTEM'),
    ('orientation_', 'SYSTEM'),
    ('formasi_', 'SYSTEM'),
    ('scenario_', 'SYSTEM'),
    ('kps_artifact_', 'SYSTEM'),
    ('hc_audit_', 'SYSTEM'),
    ('hc_health_', 'SYSTEM'),
]

ACTIVITY_ROW_LIMIT = 200


def kategori_for(jenis_peristiwa):
    value = (jenis_peristiwa or '').lower()
    for prefix, kategori in PREFIX_MAP:
        if value.startswith(prefix):
            return kategori
    return 'SYSTEM'


def activity_rows(user, *, employee, kategori='', q=''):
    """Audit rows for one employee, newest first, capped for the page."""
    from sdm.models import PeristiwaSDM

    rows = PeristiwaSDM.objects.filter(
        target_tipe='employee', target_id=str(employee.pk)
    ).exclude(jenis_peristiwa__icontains='health').select_related('actor')
    if kategori:
        rows = rows.filter(kategori=kategori)
    if q:
        rows = rows.filter(
            Q(judul__icontains=q)
            | Q(deskripsi__icontains=q)
            | Q(jenis_peristiwa__icontains=q)
            | Q(actor__username__icontains=q)
        )
    return rows.order_by('-created_at', '-pk')[:ACTIVITY_ROW_LIMIT]


def activity_metrics(rows):
    """Summary counters for the activity page.

    "Sesi terakhir IP/peranti" reads from the newest LOGIN row; login logging
    is wired in sdm/signals.py, so the value is None until a login happens.
    """
    materialized = list(rows)
    per_kategori = {}
    for row in materialized:
        if row.kategori:
            per_kategori[row.kategori] = per_kategori.get(row.kategori, 0) + 1
    last_login = None
    for row in materialized:
        if row.kategori == 'LOGIN':
            last_login = row
            break
    return {
        'total': len(materialized),
        'per_kategori': per_kategori,
        'perubahan_data': per_kategori.get('UPDATE_PROFILE', 0),
        'unggah_berkas': per_kategori.get('UPLOAD_DOC', 0),
        'verifikasi': per_kategori.get('VERIFIKASI', 0),
        'terakhir': materialized[0] if materialized else None,
        'sesi_terakhir': last_login,
    }
