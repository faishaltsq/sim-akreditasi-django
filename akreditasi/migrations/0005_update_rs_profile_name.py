# Generated migration — update RumahSakitProfile default name to RS MonsisKami
from django.db import migrations


def update_rs_profile(apps, schema_editor):
    RumahSakitProfile = apps.get_model('akreditasi', 'RumahSakitProfile')
    RumahSakitProfile.objects.filter(id=1).update(
        name='RS MonsisKami',
        tipe='Rumah Sakit Tipe B',
        kota='Jakarta',
        akreditasi_tahun=2026,
    )
    # Jika belum ada row id=1, buat sekarang
    if not RumahSakitProfile.objects.filter(id=1).exists():
        RumahSakitProfile.objects.create(
            id=1,
            name='RS MonsisKami',
            tipe='Rumah Sakit Tipe B',
            kota='Jakarta',
            akreditasi_tahun=2026,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0004_indikatormutu_insidenkeselamatan_risikounit_and_more'),
    ]

    operations = [
        migrations.RunPython(update_rs_profile, migrations.RunPython.noop),
    ]
