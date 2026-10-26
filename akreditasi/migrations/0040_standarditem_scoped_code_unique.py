"""Longgarkan uniqueness kode EP dari global ke per-pokja.

``StandardItem.code`` dulu ``unique=True``. Itu membuat edisi instrumen baru
tidak bisa berdampingan dengan edisi lama selama keduanya memakai kode EP yang
sama — dan STARKES 2022 maupun 2024 memang memakai ``TKRS 1 EP a``. Akibatnya
setiap migrasi menuntut penghapusan data lama lebih dulu.

Uniqueness yang sebenarnya dibutuhkan adalah "tidak ada kode ganda di dalam
satu pokja", jadi constraint-nya dipersempit ke ``(category, code)``.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0039_risikounit_jenis_dokumen_capaian'),
    ]

    operations = [
        migrations.AlterField(
            model_name='standarditem',
            name='code',
            field=models.CharField(max_length=50, verbose_name='Kode Elemen Penilaian (EP)'),
        ),
        migrations.AddConstraint(
            model_name='standarditem',
            constraint=models.UniqueConstraint(
                fields=('category', 'code'),
                name='uniq_standarditem_category_code'),
        ),
    ]
