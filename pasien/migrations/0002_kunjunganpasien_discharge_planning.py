from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pasien', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='kunjunganpasien',
            name='discharge_planning_aktif',
            field=models.BooleanField(default=False, verbose_name='Discharge Planning Aktif'),
        ),
        migrations.AddField(
            model_name='kunjunganpasien',
            name='discharge_planning_catatan',
            field=models.TextField(blank=True, verbose_name='Catatan Discharge Planning'),
        ),
        migrations.AddField(
            model_name='kunjunganpasien',
            name='discharge_planning_tgl',
            field=models.DateField(blank=True, null=True, verbose_name='Target Tanggal Pulang'),
        ),
    ]
