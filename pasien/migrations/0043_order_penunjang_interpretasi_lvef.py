"""F4.3 (S7-L1-02/S7-L1-04): interpretasi klinis + LVEF terpisah dari status.

Status order menjawab "sudah selesai atau belum"; dua kolom ini menjawab "apa
maknanya". Keduanya nullable/kosong sehingga order lama tidak berubah.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0042_order_penunjang_status_4_nilai'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderpenunjang',
            name='interpretasi',
            field=models.TextField(blank=True, verbose_name='Interpretasi Klinis'),
        ),
        migrations.AddField(
            model_name='orderpenunjang',
            name='lvef',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Fraksi ejeksi ventrikel kiri, persen (0–100).', null=True, verbose_name='LVEF (%)'),
        ),
    ]
