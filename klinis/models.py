from django.db import models

# Pilihan lokal untuk menghindari dependensi sirkular ke pasien
TRIASE_CHOICES = [
    ('MERAH', 'Merah — Prioritas I (Kritis)'),
    ('KUNING', 'Kuning — Prioritas II (Urgent)'),
    ('HIJAU', 'Hijau — Prioritas III (Non-Urgent)'),
    ('HITAM', 'Hitam — Prioritas IV (Expectant)'),
]

RISIKO_CHOICES = [
    ('LOW', 'LOW'),
    ('MEDIUM', 'MEDIUM'),
    ('HIGH', 'HIGH'),
    ('CRITICAL', 'CRITICAL'),
]


from .expansion_models import (KategoriPenunjang, ItemPenunjang, KelasTerapiObat, GenerikObat, ProdukFarmasi, KomposisiProdukFarmasi, KeanggotaanFormularium, MedicationPolicy)


class KelompokLayanan(models.Model):
    kode = models.CharField('Kode', max_length=30, unique=True)
    nama = models.CharField('Nama Kelompok Layanan', max_length=120)
    unit_kerja = models.ForeignKey(
        'akreditasi.UnitKerja',
        verbose_name='Unit Kerja Default',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='kelompok_layanan_klinis',
    )
    urutan = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Kelompok Layanan'
        verbose_name_plural = 'Kelompok Layanan'
        ordering = ['urutan', 'kode']

    def __str__(self):
        return f"{self.kode} — {self.nama}"


class MasterIcd10(models.Model):
    kode = models.CharField('Kode ICD-10', max_length=10, unique=True, db_index=True)
    nama = models.CharField('Diagnosis ICD-10', max_length=200)
    spesialisasi = models.CharField('Spesialisasi', max_length=50, blank=True, db_index=True)
    triase_default = models.CharField('Triase Default', max_length=10, choices=TRIASE_CHOICES, blank=True)
    risiko_default = models.CharField('Risiko Default', max_length=10, choices=RISIKO_CHOICES, blank=True)
    created_at = models.DateTimeField('Dibuat Pada', auto_now_add=True)

    class Meta:
        verbose_name = 'Master ICD-10'
        verbose_name_plural = 'Master ICD-10'
        ordering = ['kode']

    def __str__(self):
        return f"{self.kode} — {self.nama}"


class MasterIcd9(models.Model):
    kode = models.CharField('Kode ICD-9-CM', max_length=10, unique=True, db_index=True)
    nama = models.CharField('Prosedur ICD-9-CM', max_length=200)
    invasif = models.BooleanField('Tindakan Invasif', default=False)
    requires_consent = models.BooleanField('Wajib Informed Consent', default=False)

    class Meta:
        verbose_name = 'Master ICD-9-CM'
        verbose_name_plural = 'Master ICD-9-CM'
        ordering = ['kode']

    def __str__(self):
        return f"{self.kode} — {self.nama}"


class KasusTersering(models.Model):
    kelompok = models.ForeignKey(
        KelompokLayanan,
        on_delete=models.CASCADE,
        related_name='kasus',
        verbose_name='Kelompok Layanan',
    )
    urutan = models.PositiveIntegerField('Urutan')
    icd10 = models.ForeignKey(
        MasterIcd10,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='kasus_tersering',
        verbose_name='Diagnosis ICD-10',
    )
    sdki_kode = models.CharField('Kode SDKI', max_length=10, blank=True)
    sdki_nama = models.CharField('Nama Diagnosa SDKI', max_length=150, blank=True)
    tatalaksana = models.TextField('Panduan Tatalaksana', blank=True)
    kewenangan = models.CharField('Kewenangan Dokter', max_length=120, blank=True)
    perlu_verifikasi = models.BooleanField('Perlu Verifikasi', default=False)
    catatan_sumber = models.TextField('Catatan Sumber', blank=True)

    class Meta:
        verbose_name = 'Kasus Tersering'
        verbose_name_plural = 'Kasus Tersering'
        unique_together = [('kelompok', 'urutan')]
        ordering = ['kelompok__urutan', 'urutan']

    def __str__(self):
        diag = self.icd10.kode if self.icd10 else (self.sdki_kode or '-')
        return f"[{self.kelompok.kode} #{self.urutan}] {diag}"


class KasusTindakan(models.Model):
    kasus = models.ForeignKey(
        KasusTersering,
        on_delete=models.CASCADE,
        related_name='tindakan',
        verbose_name='Kasus Tersering',
    )
    icd9 = models.ForeignKey(
        MasterIcd9,
        on_delete=models.PROTECT,
        related_name='kasus_tindakan',
        verbose_name='Prosedur ICD-9-CM',
    )
    urutan = models.PositiveIntegerField('Urutan', default=1)
    tarif_umum = models.DecimalField('Tarif Umum (Rp)', max_digits=12, decimal_places=2, null=True, blank=True)
    tarif_bpjs = models.DecimalField('Tarif BPJS (Rp)', max_digits=12, decimal_places=2, null=True, blank=True)
    satuan = models.CharField('Satuan Biaya', max_length=30, blank=True)

    class Meta:
        verbose_name = 'Tindakan Kasus'
        verbose_name_plural = 'Tindakan Kasus'
        unique_together = [('kasus', 'icd9', 'urutan')]
        ordering = ['kasus', 'urutan']

    def __str__(self):
        return f"{self.kasus} → {self.icd9.kode} (Umum: {self.tarif_umum}, BPJS: {self.tarif_bpjs})"


class SdkiDiagnosis(models.Model):
    kode = models.CharField('Kode SDKI', max_length=10, unique=True, db_index=True)
    nama = models.CharField('Diagnosa Keperawatan', max_length=200)

    class Meta:
        verbose_name = 'SDKI Diagnosa'
        verbose_name_plural = 'SDKI Diagnosa'
        ordering = ['kode']

    def __str__(self):
        return f"{self.kode} — {self.nama}"


class SlkiLuaran(models.Model):
    kode = models.CharField('Kode SLKI', max_length=12, unique=True, db_index=True)
    nama = models.CharField('Luaran Keperawatan', max_length=200)

    class Meta:
        verbose_name = 'SLKI Luaran'
        verbose_name_plural = 'SLKI Luaran'
        ordering = ['kode']

    def __str__(self):
        return f"{self.kode} — {self.nama}"


class SikiIntervensi(models.Model):
    kode = models.CharField('Kode SIKI', max_length=14, unique=True, db_index=True)
    nama = models.CharField('Intervensi Keperawatan', max_length=200)

    class Meta:
        verbose_name = 'SIKI Intervensi'
        verbose_name_plural = 'SIKI Intervensi'
        ordering = ['kode']

    def __str__(self):
        return f"{self.kode} — {self.nama}"


class Pemetaan3S(models.Model):
    sdki = models.ForeignKey(
        SdkiDiagnosis,
        on_delete=models.CASCADE,
        related_name='pemetaan',
        verbose_name='Diagnosa SDKI',
    )
    slki = models.ForeignKey(
        SlkiLuaran,
        on_delete=models.CASCADE,
        related_name='pemetaan',
        verbose_name='Luaran SLKI',
    )
    siki = models.ForeignKey(
        SikiIntervensi,
        on_delete=models.CASCADE,
        related_name='pemetaan',
        verbose_name='Intervensi SIKI',
    )
    prioritas = models.PositiveIntegerField('Prioritas', default=1)

    class Meta:
        verbose_name = 'Pemetaan 3S (SDKI-SLKI-SIKI)'
        verbose_name_plural = 'Pemetaan 3S (SDKI-SLKI-SIKI)'
        ordering = ['sdki', 'prioritas']

    def __str__(self):
        return f"{self.sdki.kode} → {self.slki.kode} → {self.siki.kode}"


class AturanEpAsesmen(models.Model):
    sub_standard = models.CharField('Sub-Standar Akreditasi', max_length=50, unique=True)
    label = models.CharField('Label Penjelasan', max_length=150)
    wajib = models.BooleanField('Wajib Ditautkan', default=True)
    urutan = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Aturan EP Asesmen'
        verbose_name_plural = 'Aturan EP Asesmen'
        ordering = ['urutan', 'sub_standard']

    def __str__(self):
        return f"{self.sub_standard} — {self.label}"


class AturanEpTindakan(models.Model):
    JENIS = [
        ('ICD9', 'ICD-9-CM'),
        ('SIKI', 'SIKI'),
        ('ANY', 'Semua'),
    ]

    jenis = models.CharField('Jenis Tindakan', max_length=6, choices=JENIS, default='ICD9')
    kode = models.CharField('Kode Tindakan', max_length=20, blank=True,
                            help_text='Kosongkan untuk berlaku pada semua kode')
    sub_standard = models.CharField('Sub-Standar EP', max_length=50)
    label = models.CharField('Label Penjelasan', max_length=150)
    wajib = models.BooleanField('Wajib Ditautkan', default=True)
    urutan = models.PositiveIntegerField('Urutan', default=0)

    class Meta:
        verbose_name = 'Aturan EP per Tindakan'
        verbose_name_plural = 'Aturan EP per Tindakan'
        unique_together = [('jenis', 'kode', 'sub_standard')]
        ordering = ['urutan', 'jenis', 'kode']

    def __str__(self):
        return f"{self.jenis} {self.kode or '*'} → {self.sub_standard}"
