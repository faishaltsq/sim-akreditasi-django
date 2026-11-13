from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class KategoriPenunjang(models.Model):
    kode = models.CharField(max_length=80, unique=True)
    nama = models.CharField(max_length=200)
    level = models.PositiveSmallIntegerField(choices=[(1,'Kategori'),(2,'Instalasi'),(3,'Kelompok')])
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT, related_name='children')
    active = models.BooleanField(default=True)
    urutan = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['urutan','kode']

    def __str__(self):
        return self.nama

    def clean(self):
        super().clean()
        if self.level not in (1,2,3) or (self.level == 1 and self.parent_id) or (self.level > 1 and not self.parent_id):
            raise ValidationError('Hierarki penunjang tidak valid.')
        if self.parent_id and (self.parent_id == self.pk or self.parent.level != self.level - 1):
            raise ValidationError('Tingkat induk penunjang tidak sesuai.')


class ItemPenunjang(models.Model):
    kode = models.CharField(max_length=100, unique=True)
    nama = models.CharField(max_length=255)
    group = models.ForeignKey(KategoriPenunjang, on_delete=models.PROTECT, related_name='items')
    jenis_order = models.CharField(max_length=15, choices=[('LAB','Lab'),('RADIOLOGI','Imaging'),('EKG','EKG'),('LAINNYA','Lainnya')])
    destination = models.ForeignKey('akreditasi.UnitKerja', null=True, blank=True, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    source_version = models.CharField(max_length=200)
    source_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)
    preparation_schema = models.JSONField(default=dict, blank=True)
    variants = models.JSONField(default=dict, blank=True)
    is_panel = models.BooleanField(default=False)

    class Meta:
        ordering = ['kode']

    def __str__(self):
        return self.nama

    def clean(self):
        super().clean()
        if self.group.level != 3:
            raise ValidationError('Item harus berada dalam kelompok tingkat 3.')
        if self.active and not (self.source_version and self.reviewed_by_id and self.destination_id):
            raise ValidationError('Aktivasi memerlukan sumber, reviewer dan unit tujuan.')


class KelasTerapiObat(models.Model):
    kode = models.CharField(max_length=80, unique=True)
    nama = models.CharField(max_length=200)
    kind = models.CharField(max_length=8, default='OBAT', choices=[('OBAT','Obat'),('BMHP','BMHP')])
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.nama


class GenerikObat(models.Model):
    kode = models.CharField(max_length=100, unique=True)
    nama = models.CharField(max_length=200)
    kelas = models.ForeignKey(KelasTerapiObat, on_delete=models.PROTECT, related_name='generics')
    bentuk = models.CharField(max_length=30)
    dispense_unit = models.CharField(max_length=30)
    strength = models.CharField(max_length=100, blank=True)
    conversion = models.JSONField(default=dict, blank=True)
    active = models.BooleanField(default=True)

    def __str__(self):
        return self.nama


class ProdukFarmasi(models.Model):
    kode = models.CharField(max_length=100, unique=True)
    nama = models.CharField(max_length=200)
    generik = models.ForeignKey(GenerikObat, on_delete=models.PROTECT, related_name='products')
    kind = models.CharField(max_length=8, default='OBAT', choices=[('OBAT','Obat'),('BMHP','BMHP')])
    kfa_code = models.CharField(max_length=50, blank=True)
    pack = models.CharField(max_length=100, blank=True)
    flags = models.JSONField(default=list, blank=True)
    tall_man_label = models.CharField(max_length=200, blank=True)
    allowed_routes = models.JSONField(default=list, blank=True)
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    active = models.BooleanField(default=False)
    source_version = models.CharField(max_length=200)
    source_note = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT)

    def __str__(self):
        return self.nama

    def clean(self):
        super().clean()
        allowed = {'LASA','HIGH_ALERT','OOT','NARKOTIKA','PSIKOTROPIKA','PPRA'}
        if not isinstance(self.flags,list) or any(flag not in allowed for flag in self.flags):
            raise ValidationError('Flag risiko obat tidak dikenal.')
        if self.active and not (self.reviewed_by_id and self.source_version):
            raise ValidationError('Aktivasi produk memerlukan sumber dan reviewer.')
        if self.price is not None and self.price < 0:
            raise ValidationError('Harga tidak boleh negatif.')


class KomposisiProdukFarmasi(models.Model):
    produk = models.ForeignKey(ProdukFarmasi, on_delete=models.PROTECT, related_name='ingredients')
    ingredient_code = models.CharField(max_length=100)
    nama = models.CharField(max_length=200)
    strength = models.DecimalField(max_digits=12, decimal_places=4)
    unit = models.CharField(max_length=30)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['produk','ingredient_code'],name='unique_product_ingredient')]


class KeanggotaanFormularium(models.Model):
    produk = models.ForeignKey(ProdukFarmasi, on_delete=models.PROTECT, related_name='formularies')
    jenis = models.CharField(max_length=8, choices=[('FORNAS','Fornas'),('RS','Formularium RS')])
    source_version = models.CharField(max_length=200)
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    restrictions = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)


class MedicationPolicy(models.Model):
    version = models.CharField(max_length=100, unique=True)
    source = models.CharField(max_length=200)
    rules = models.JSONField(default=dict)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
