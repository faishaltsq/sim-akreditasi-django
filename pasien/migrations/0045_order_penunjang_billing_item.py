"""F4.6 (ADR-4/ADR-10): tautan tagihan order penunjang.

Satu order paling banyak satu baris tagihan. ``PROTECT`` dipilih supaya baris
tagihan yang sudah menjadi bukti penagihan tidak hilang diam-diam; pembatalan
lewat ``penunjang_billing.release_order`` yang melepas tautan lebih dulu.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0044_order_penunjang_critical_reporting'),
    ]

    operations = [
        migrations.AddField(
            model_name='orderpenunjang',
            name='billing_item',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='order_penunjang', to='pasien.billingitem'),
        ),
    ]
