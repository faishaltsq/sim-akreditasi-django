"""F4.0: satu sumber billing per asal penulisan.

Sebelum migrasi ini kedua penulis otomatis memakai ``sumber='ASESMEN'`` dan
menyapu ``filter(kunjungan, sumber='ASESMEN')`` tanpa melihat kategori,
sehingga (a) baris penunjang ber-``ASESMEN`` terhapus saat tindakan disimpan
dan (b) kedua fungsi saling menghapus baris pada kunjungan yang sama.

Migrasi ini menambahkan dua nilai pilihan dan memindahkan baris lama ke
pemiliknya yang benar. Kepemilikan baris turunan tindakan dapat dibuktikan
dari data: ``TindakanAsesmen.billing_item`` menunjuk tepat satu baris. Baris
``ASESMEN`` yang tidak dirujuk baris tindakan mana pun adalah milik jalur form
teks bebas lama dan dibiarkan apa adanya.
"""
from django.db import migrations, models


def forwards(apps, schema_editor):
    BillingItem = apps.get_model('pasien', 'BillingItem')
    TindakanAsesmen = apps.get_model('pasien', 'TindakanAsesmen')
    linked = TindakanAsesmen.objects.filter(
        billing_item__isnull=False,
    ).values_list('billing_item_id', flat=True)
    BillingItem.objects.filter(
        pk__in=list(linked), kategori='JASA_MEDIS', sumber='ASESMEN',
    ).update(sumber='TINDAKAN')


def backwards(apps, schema_editor):
    BillingItem = apps.get_model('pasien', 'BillingItem')
    BillingItem.objects.filter(sumber__in=('TINDAKAN', 'PENUNJANG')).update(sumber='ASESMEN')


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0040_rajal_red_flag'),
    ]

    operations = [
        migrations.AlterField(
            model_name='billingitem',
            name='sumber',
            field=models.CharField(choices=[('MANUAL', 'Input Manual'), ('ASESMEN', 'Otomatis dari Asesmen'), ('FARMASI', 'Farmasi'), ('PROFESI', 'Pelaksanaan profesional'), ('TINDAKAN', 'Turunan Baris Tindakan'), ('PENUNJANG', 'Turunan Order Penunjang')], default='MANUAL', max_length=10, verbose_name='Sumber'),
        ),
        migrations.RunPython(forwards, backwards),
    ]
