from django.db import migrations


def normalize_igd_visits(apps, schema_editor):
    KunjunganPasien = apps.get_model('pasien', 'KunjunganPasien')
    UnitKerja = apps.get_model('akreditasi', 'UnitKerja')

    igd_unit = UnitKerja.objects.filter(code='IGD').first()
    update_kwargs = {'poliklinik': 'IGD'}
    if igd_unit:
        update_kwargs['unit_kerja'] = igd_unit

    KunjunganPasien.objects.filter(jenis_kunjungan='IGD').update(**update_kwargs)


def reverse_noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('pasien', '0012_backfill_ruangan_unit_kerja'),
        ('akreditasi', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(normalize_igd_visits, reverse_noop),
    ]
