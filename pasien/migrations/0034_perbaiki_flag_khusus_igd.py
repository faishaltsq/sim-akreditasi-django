from django.db import migrations


def perbaiki_flag_khusus(apps, schema_editor):
    """'MERAH' bukan pilihan valid FLAG_KHUSUS_CHOICES; nilai yang benar 'KRITIS'."""
    KunjunganPasien = apps.get_model('pasien', 'KunjunganPasien')
    KunjunganPasien.objects.filter(flag_khusus='MERAH').update(flag_khusus='KRITIS')


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0033_apm_bpjs_multichannel'),
    ]

    operations = [
        migrations.RunPython(perbaiki_flag_khusus, migrations.RunPython.noop),
    ]