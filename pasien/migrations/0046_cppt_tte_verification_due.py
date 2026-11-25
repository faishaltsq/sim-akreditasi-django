"""F6.4/F6.5 (S9-L1-05, S9-L1-08, §7): TTE dan batas verifikasi DPJP.

Tiga kolom aditif pada ``CPPT``:

* ``ttd_image`` — goresan kanvas tanda tangan sebagai data URL (bukan PIN,
  bukan biometrik).
* ``ttd_hash`` — SHA-256 atas byte gambar, supaya isi tanda tangan dapat
  dibuktikan tidak berubah setelah ditandatangani.
* ``verifikasi_due_at`` — waktu tanda tangan + 24 jam. Status TERLAMBAT
  **tidak** menjadi kolom: ia dihitung dari kolom ini dibanding
  ``VerifikasiCppt.performed_at``.

Semua kolom ber-default sehingga baris lama tidak perlu backfill.
"""
from django.db import migrations, models

class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0045_order_penunjang_billing_item'),
    ]

    operations = [
        migrations.AddField(
            model_name='cppt',
            name='ttd_image',
            field=models.TextField(blank=True, default='', verbose_name='Gambar TTE'),
        ),
        migrations.AddField(
            model_name='cppt',
            name='ttd_hash',
            field=models.CharField(blank=True, default='', max_length=64, verbose_name='SHA-256 gambar TTE'),
        ),
        migrations.AddField(
            model_name='cppt',
            name='verifikasi_due_at',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Batas verifikasi DPJP'),
        ),
    ]
