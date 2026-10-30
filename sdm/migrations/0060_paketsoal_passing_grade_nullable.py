from decimal import Decimal

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sdm', '0059_hasilmcu_konfirmasioffering'),
    ]

    operations = [
        migrations.AlterField(
            model_name='paketsoal',
            name='passing_grade',
            field=models.DecimalField(
                'Passing Grade', max_digits=5, decimal_places=2, null=True, blank=True,
                validators=[MinValueValidator(Decimal('0.00')), MaxValueValidator(Decimal('100.00'))],
                help_text='Nilai minimum lulus (0–100), ditetapkan komite; kosong jika belum ditetapkan.',
            ),
        ),
    ]
