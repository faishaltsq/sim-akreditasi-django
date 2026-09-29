from django.core.management import call_command
from django.db import migrations


def run_seed(apps, schema_editor):
    call_command('seed_starkes_16_bab')


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0012_add_kelompok_target_ep_pengampu'),
    ]

    operations = [
        migrations.RunPython(run_seed, migrations.RunPython.noop),
    ]
