from django.db import migrations


def link_ruangan_to_unit_kerja(apps, schema_editor):
    Ruangan = apps.get_model('pasien', 'Ruangan')
    UnitKerja = apps.get_model('akreditasi', 'UnitKerja')

    RUANGAN_UNIT_CODE = {
        'R-K1': 'BANGSAL-DEWASA',
        'R-K2': 'BANGSAL-DEWASA',
        'R-K3': 'BANGSAL-DEWASA',
        'VIP-A': 'BANGSAL-VIP',
        'ICU-01': 'ICU',
        'IGD-01': 'IGD',
        'IGD-02': 'IGD',
        'OK-01': 'IBS',
    }

    unit_cache = {
        u.code: u for u in UnitKerja.objects.filter(code__in=list(RUANGAN_UNIT_CODE.values()))
    }

    for kode, unit_code in RUANGAN_UNIT_CODE.items():
        unit = unit_cache.get(unit_code)
        if unit:
            Ruangan.objects.filter(kode=kode).update(unit_kerja=unit)


def unlink_ruangan(apps, schema_editor):
    Ruangan = apps.get_model('pasien', 'Ruangan')
    Ruangan.objects.all().update(unit_kerja=None)


class Migration(migrations.Migration):
    dependencies = [
        ('pasien', '0011_kunjunganpasien_unit_kerja_ruangan_unit_kerja'),
        ('akreditasi', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(link_ruangan_to_unit_kerja, unlink_ruangan),
    ]
