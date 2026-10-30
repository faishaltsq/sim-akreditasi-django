from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('sdm', '0060_paketsoal_passing_grade_nullable'),
    ]

    operations = [
        migrations.AddField(
            model_name='scorecardwawancara',
            name='jenis',
            field=models.CharField(blank=True, choices=[('HRD', 'HRD'), ('USER', 'User / Komite')], default='', max_length=4, verbose_name='Jenis Penguji'),
        ),
    ]
