"""Backfill INM Induk + tambah INM-15 (Visite Dokter) & INM-16 (SC Emergency).

Dua langkah:
1. Buat INM kanonik yang belum ada tetapi diminta peta distribusi INM.
2. Tautkan baris realisasi per-unit (BAB-*-INM-*) ke INM kanoniknya.

Penautan berbasis nama, bukan urutan nomor: penomoran docx tidak sama dengan
penomoran DB (docx #4 = SC Emergency, sedangkan INM-04 = waktu tanggap IGD).
Baris yang ambigu atau tidak cocok dibiarkan NULL dan dilaporkan oleh
`manage.py seed_inm_matrix`.
"""
import re

from django.db import migrations

NEW_INM = [
    dict(
        kode_indikator='INM-15',
        nama_indikator='Kepatuhan Waktu Visite Dokter',
        target_nilai=80,
        arah_target='MIN',
        satuan='%',
        dimensi_mutu='TEPAT_WAKTU',
        numerator='Jumlah visite dokter yang dilakukan sesuai jadwal (tepat waktu)',
        denominator='Jumlah total visite dokter yang diamati',
        pj='Bidang Pelayanan Medis',
    ),
    dict(
        kode_indikator='INM-16',
        nama_indikator='Waktu Tanggap Operasi Seksio Sesarea Emergency (<= 30 Menit)',
        target_nilai=30,
        arah_target='MAX',
        satuan='menit',
        dimensi_mutu='TEPAT_WAKTU',
        numerator='Jumlah SC emergency dengan waktu tanggap <= 30 menit',
        denominator='Jumlah total SC emergency',
        pj='IGD / VK',
    ),
]

# Penautan yang tidak bisa disimpulkan dari nama (ejaan berbeda).
EXPLICIT_LINKS = {
    'BAB-VK-INM-01': 'INM-16',
    'BAB-HD-INM-02': 'INM-02',      # nama disingkat "APD", bukan "Alat Pelindung Diri"
    'BAB-VK-INM-02': 'INM-02',
}

# Singkatan yang lazim dipakai di nama baris per-unit.
ALIASES = (
    ('alat pelindung diri', 'apd'),
    ('indeks kepuasan masyarakat', 'ikm'),
)


def _norm(text):
    """Normalisasi nama indikator untuk pencocokan."""
    text = (text or '').lower()
    text = re.sub(r'\(.*?\)', ' ', text)          # buang anotasi target
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = ' '.join(text.split())
    for long_form, short in ALIASES:
        text = text.replace(long_form, short)
    return ' '.join(text.split())


def _score(row_norm, cand_norm):
    """Skor kecocokan: panjang string terpendek bila salah satu memuat yang lain."""
    if not row_norm or not cand_norm:
        return 0
    if row_norm in cand_norm or cand_norm in row_norm:
        return min(len(row_norm), len(cand_norm))
    return 0


def forwards(apps, schema_editor):
    IndikatorMutu = apps.get_model('akreditasi', 'IndikatorMutu')

    for spec in NEW_INM:
        IndikatorMutu.objects.get_or_create(
            kode_indikator=spec['kode_indikator'],
            defaults=dict(spec, jenis='INM', aktif=True, rencana_aksi=''),
        )

    canonical = list(IndikatorMutu.objects.filter(kode_indikator__startswith='INM-'))
    canon_norm = {c.pk: _norm(c.nama_indikator) for c in canonical}

    for row in IndikatorMutu.objects.filter(kode_indikator__startswith='BAB-'):
        target_code = EXPLICIT_LINKS.get(row.kode_indikator)
        if target_code:
            parent = next((c for c in canonical if c.kode_indikator == target_code), None)
            if parent:
                row.inm_induk_id = parent.pk
                row.save(update_fields=['inm_induk'])
            continue

        row_norm = _norm(row.nama_indikator)
        scored = sorted(
            ((_score(row_norm, canon_norm[c.pk]), c.pk) for c in canonical),
            reverse=True,
        )
        if not scored or scored[0][0] == 0:
            continue
        best_score = scored[0][0]
        winners = {pk for s, pk in scored if s == best_score}
        if len(winners) != 1:
            continue      # ambigu -> biarkan NULL, dilaporkan oleh seed_inm_matrix
        row.inm_induk_id = winners.pop()
        row.save(update_fields=['inm_induk'])


def backwards(apps, schema_editor):
    """Kolom ini turunan, bukan data pengguna — aman dikosongkan.

    INM-15/INM-16 sengaja TIDAK dihapus: kalau sudah dipakai, menghapusnya akan
    memutus CatatanIndikator dan peta distribusi.
    """
    IndikatorMutu = apps.get_model('akreditasi', 'IndikatorMutu')
    IndikatorMutu.objects.filter(kode_indikator__startswith='BAB-').update(inm_induk=None)


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0042_indikatormutu_inm_induk'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
