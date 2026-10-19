"""Perbaiki arah target (polaritas) dua baris INM yang salah.

- BAB-INTERNA-INM-02 "Kepatuhan Upaya Pencegahan Risiko Pasien Jatuh (100%)"
  sebelumnya MAX (lower-is-better) padahal kepatuhan: makin tinggi makin baik.
- BAB-VK-INM-01 "Waktu Tanggap Operasi Seksio Sesarea Emergensi <= 30 Menit"
  sebelumnya MIN padahal waktu tanggap: makin kecil makin baik.

Idempoten: hanya menyentuh baris yang nilainya masih salah.
"""
from django.db import migrations

FIXES = (
    ('BAB-INTERNA-INM-02', 'MIN'),
    ('BAB-VK-INM-01', 'MAX'),
)


def forwards(apps, schema_editor):
    IndikatorMutu = apps.get_model('akreditasi', 'IndikatorMutu')
    for kode, arah in FIXES:
        IndikatorMutu.objects.filter(kode_indikator=kode).exclude(
            arah_target=arah
        ).update(arah_target=arah)


def backwards(apps, schema_editor):
    """Kembalikan ke nilai keliru? Tidak. Arah yang benar tidak dibatalkan."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0043_backfill_inm_induk_and_missing_inm'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
