"""F7.5 — cakupan layanan pada aturan EP (data, bukan kode).

Aturan EP asesmen dan tindakan kini punya kolom ``layanan``:

* ``''`` — berlaku untuk semua jalur. Seluruh baris lama bernilai ini, sehingga
  form asesmen IGD merender aturan yang sama persis seperti sebelum migrasi.
* ``RAJAL_JANTUNG`` — hanya dipakai episode Poli Jantung (F7).

``unique_together`` pada ``AturanEpTindakan`` ikut memuat ``layanan`` supaya
aturan yang sama dapat berlaku pada dua jalur berbeda tanpa saling menimpa.
Tidak ada data yang dihapus atau diubah.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('klinis', '0008_produk_farmasi_pregnancy_class'),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name='aturaneptindakan',
            unique_together=set(),
        ),
        migrations.AddField(
            model_name='aturanepasesmen',
            name='layanan',
            field=models.CharField(
                blank=True,
                choices=[('', 'Semua Jalur Layanan'), ('IGD', 'Gawat Darurat'),
                         ('RAJAL_JANTUNG', 'Rawat Jalan Jantung')],
                default='', max_length=20, verbose_name='Cakupan Layanan',
            ),
        ),
        migrations.AddField(
            model_name='aturaneptindakan',
            name='layanan',
            field=models.CharField(
                blank=True,
                choices=[('', 'Semua Jalur Layanan'), ('IGD', 'Gawat Darurat'),
                         ('RAJAL_JANTUNG', 'Rawat Jalan Jantung')],
                default='',
                help_text='Kosong = semua jalur. Baris POLI-JANTUNG tidak terlihat oleh IGD.',
                max_length=20, verbose_name='Cakupan Layanan',
            ),
        ),
        migrations.AlterUniqueTogether(
            name='aturaneptindakan',
            unique_together={('jenis', 'kode', 'sub_standard', 'layanan')},
        ),
    ]
