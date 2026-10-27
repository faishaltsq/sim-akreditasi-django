"""Katalog RKK versi komite: jenjang profesi & kewenangan klinis per jenjang."""
import uuid

from django.db import models


class MasterJenjangProfesi(models.Model):
    """Career grade (jenjang) under a reviewed profession master."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profesi = models.ForeignKey(
        'sdm.MasterProfesiPegawai',
        on_delete=models.PROTECT,
        related_name='jenjang',
        verbose_name='Profesi',
    )
    kode = models.CharField('Kode Jenjang', max_length=30)
    nama = models.CharField('Nama Jenjang', max_length=100)
    urutan = models.PositiveIntegerField('Urutan')
    fokus_kompetensi = models.TextField(
        'Fokus Kompetensi', blank=True, default='',
        help_text='Ringkasan fokus kompetensi jenjang dari SK/komite.',
    )
    preceptor_min_urutan = models.PositiveIntegerField(
        'Ambang Urutan Preseptor', default=3,
        help_text='Jenjang dengan urutan >= ambang ini pada profesinya boleh memverifikasi logbook.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Master Jenjang Profesi'
        verbose_name_plural = 'Master Jenjang Profesi'
        ordering = ['profesi__keluarga', 'profesi__nama', 'urutan']
        constraints = [
            models.UniqueConstraint(
                fields=['profesi', 'kode'],
                name='sdm_jenjang_profesi_kode_uniq',
            ),
        ]

    def __str__(self):
        return f'{self.profesi.nama} — {self.kode}'


class KatalogTindakan(models.Model):
    """Catalog clinical action per profession grade with default supervision level."""

    TINGKAT_CHOICES = [
        ('M', 'Mandiri'),
        ('S', 'Supervisi'),
        ('MT', 'Mandiri Terbatas'),
        ('T', 'Tidak Diberikan'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kode = models.CharField('Kode Tindakan', max_length=40, unique=True)
    nama = models.CharField('Nama Tindakan', max_length=200)
    jenjang = models.ForeignKey(
        MasterJenjangProfesi,
        on_delete=models.PROTECT,
        related_name='katalog',
        verbose_name='Jenjang',
    )
    tingkat_supervisi = models.CharField(
        'Tingkat Supervisi', max_length=4, choices=TINGKAT_CHOICES
    )
    catatan = models.TextField('Catatan', blank=True)
    is_active = models.BooleanField('Aktif', default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Katalog Tindakan RKK'
        verbose_name_plural = 'Katalog Tindakan RKK'
        ordering = ['jenjang__profesi__keluarga', 'jenjang__profesi__nama', 'jenjang__urutan', 'kode']
        indexes = [
            models.Index(fields=['jenjang', 'is_active'], name='sdm_katalog_jenjang_idx'),
        ]

    def __str__(self):
        return f'{self.kode} — {self.nama}'
