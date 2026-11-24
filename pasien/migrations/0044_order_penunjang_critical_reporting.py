"""F4.4 (S7-L1-05, SKP 2/PP): jejak pelaporan nilai kritis.

Jam temuan dan jam lapor dipisah karena SLA F4.5 diukur di antaranya.
Penerima laporan dan read-back membuktikan laporan benar-benar diterima dan
dipahami. Semua kolom nullable/kosong sehingga order lama tidak berubah.
"""
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0043_order_penunjang_interpretasi_lvef'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='orderpenunjang',
            name='critical_found_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Jam Temuan Nilai Kritis'),
        ),
        migrations.AddField(
            model_name='orderpenunjang',
            name='critical_reported_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Jam Lapor ke DPJP'),
        ),
        migrations.AddField(
            model_name='orderpenunjang',
            name='critical_reported_to',
            field=models.CharField(blank=True, max_length=150, verbose_name='Penerima Laporan'),
        ),
        migrations.AddField(
            model_name='orderpenunjang',
            name='critical_readback_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Jam Read-back'),
        ),
        migrations.AddField(
            model_name='orderpenunjang',
            name='critical_readback_by',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL, verbose_name='Verifikator Read-back'),
        ),
    ]
