from django.core.management import call_command
from django.db import migrations


def run_seed(apps, schema_editor):
    call_command('seed_pemetaan_akun_l4')


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0013_seed_starkes_16_bab'),
        ('accounts', '0004_seed_monsiskami_superadmin'),
    ]

    operations = [
        migrations.RunPython(run_seed, migrations.RunPython.noop),
    ]
