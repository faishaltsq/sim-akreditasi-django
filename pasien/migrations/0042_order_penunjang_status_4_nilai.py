"""F4.2 (ADR-5): status order penunjang menjadi empat nilai.

``ORDERED``/``PROSES`` diganti ``DRAFT``/``DIPROSES``/``SELESAI``/``BATAL``.
Order lama sudah terkirim ke unit pelaksana, jadi ``ORDERED`` dipetakan ke
``DIPROSES`` — bukan ``DRAFT``, yang berarti belum dikirim. ``PROSES`` juga
``DIPROSES``: keduanya sama-sama sedang dikerjakan, dan ADR-5 menetapkan satu
nilai untuk keadaan itu.
"""
from django.db import migrations, models


def forwards(apps, schema_editor):
    OrderPenunjang = apps.get_model('pasien', 'OrderPenunjang')
    OrderPenunjang.objects.filter(status='ORDERED').update(status='DIPROSES')
    OrderPenunjang.objects.filter(status='PROSES').update(status='DIPROSES')


def backwards(apps, schema_editor):
    OrderPenunjang = apps.get_model('pasien', 'OrderPenunjang')
    OrderPenunjang.objects.filter(status='DRAFT').update(status='ORDERED')
    OrderPenunjang.objects.filter(status='DIPROSES').update(status='ORDERED')
    OrderPenunjang.objects.filter(status='BATAL').update(status='ORDERED')


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0041_billing_ownership_sources'),
    ]

    operations = [
        migrations.AlterField(
            model_name='orderpenunjang',
            name='status',
            field=models.CharField(choices=[('DRAFT', 'Draft — belum dikirim'), ('DIPROSES', 'Diproses / Dalam Pemeriksaan'), ('SELESAI', 'Selesai / Hasil Tersedia'), ('BATAL', 'Dibatalkan')], default='DIPROSES', max_length=15, verbose_name='Status Order'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
