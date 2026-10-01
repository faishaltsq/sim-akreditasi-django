from django.db import migrations


def run_seed_demo(apps, schema_editor):
    from django.core.management import call_command
    call_command('seed_demo_data')


def reverse_seed_demo(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0023_seed_indikator_mutu_renstra'),
    ]

    operations = [
        migrations.RunPython(run_seed_demo, reverse_seed_demo),
    ]
