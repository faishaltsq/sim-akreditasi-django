"""Reviewed service authority and effective price configuration. No operational seeds."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, F


class ReviewedSource(models.Model):
    source_version = models.CharField(max_length=200)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+', null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if self.is_active and (not self.source_version.strip() or not self.reviewed_by_id or not self.reviewed_at):
            raise ValidationError('Sumber aktif memerlukan referensi dan peninjau.')


class LayananProfesional(ReviewedSource):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    group = models.CharField(max_length=12, choices=[('MEDICAL','Medis'),('NURSING','Keperawatan'),('OTHER_PPA','PPA lain')])
    authority_kind = models.CharField(max_length=8, choices=[('CLINICAL','Klinis'),('SUPPORT','Penunjang spiritual')])
    note_format = models.CharField(max_length=9, choices=[('SOAP','SOAP'),('ADIME','ADIME'),('SPIRITUAL','Spiritual')], default='SOAP')
    icd9 = models.ForeignKey('klinis.MasterIcd9', null=True, blank=True, on_delete=models.PROTECT)
    siki = models.ForeignKey('klinis.SikiIntervensi', null=True, blank=True, on_delete=models.PROTECT)
    allow_unpriced = models.BooleanField(default=False)

    def save(self,*args,**kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exclude(code=self.code).exists():
            raise ValidationError('Kode layanan tidak dapat diubah.')
        self.full_clean()
        return super().save(*args,**kwargs)

    def __str__(self):
        return f'{self.code} — {self.name}'


class PemetaanKewenanganLayanan(ReviewedSource):
    service = models.ForeignKey(LayananProfesional, on_delete=models.PROTECT, related_name='authority_mappings')
    catalog_item = models.ForeignKey('sdm.KatalogTindakan', on_delete=models.PROTECT)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['service','catalog_item'],name='professional_service_catalogue_unique')]

    def save(self,*args,**kwargs):
        self.full_clean()
        return super().save(*args,**kwargs)


class ProfessionalCareGrant(ReviewedSource):
    CAPABILITIES=[(v,v) for v in ('MANAGE_TARIFF','RECORD_FOR_OTHER','VOID_UNPAID_CHARGE','SUPPORT_SERVICE')]
    user = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='professional_care_grants')
    unit = models.ForeignKey('akreditasi.UnitKerja',on_delete=models.PROTECT)
    service = models.ForeignKey(LayananProfesional,on_delete=models.PROTECT,null=True,blank=True)
    capability = models.CharField(max_length=24,choices=CAPABILITIES)
    valid_from = models.DateField()
    valid_until = models.DateField()

    class Meta:
        constraints=[models.CheckConstraint(condition=Q(valid_until__gte=F('valid_from')),name='professional_grant_dates_valid')]

    def clean(self):
        super().clean()
        if self.capability=='SUPPORT_SERVICE' and (not self.service_id or self.service.authority_kind!='SUPPORT'):
            raise ValidationError('Penugasan support harus menunjuk layanan support yang ditinjau.')
        if self.is_active and self.reviewed_by_id==self.user_id:
            raise ValidationError('Penerima tidak boleh menyetujui grant sendiri.')

    def save(self,*args,**kwargs):
        self.full_clean()
        return super().save(*args,**kwargs)


class BatasanKewenanganProfesional(ReviewedSource):
    privilege=models.OneToOneField('sdm.RincianKewenangan',on_delete=models.PROTECT,related_name='professional_limits')
    narrative_digest=models.CharField(max_length=64)
    conditions=models.JSONField()
    valid_from=models.DateField()
    valid_until=models.DateField()

    class Meta:
        constraints=[models.CheckConstraint(condition=Q(valid_until__gte=F('valid_from')),name='professional_limits_dates_valid')]

    def clean(self):
        super().clean()
        from sdm.professional_policy import validate_limits,limits_digest
        validate_limits(self.conditions)
        if self.privilege_id and (not self.privilege.batasan.strip() or self.narrative_digest!=limits_digest(self.privilege.batasan)):
            raise ValidationError('Interpretasi batasan harus terikat teks mandat yang ditinjau.')

    def save(self,*args,**kwargs):
        self.full_clean()
        return super().save(*args,**kwargs)


class TarifLayananProfesi(ReviewedSource):
    service = models.ForeignKey(LayananProfesional,on_delete=models.PROTECT,related_name='price_versions')
    unit = models.ForeignKey('akreditasi.UnitKerja',on_delete=models.PROTECT)
    profession = models.ForeignKey('sdm.MasterProfesiPegawai',on_delete=models.PROTECT)
    grade = models.ForeignKey('sdm.MasterJenjangProfesi',on_delete=models.PROTECT)
    payor = models.CharField(max_length=10,choices=[('UMUM','Umum'),('BPJS','BPJS'),('ASURANSI','Asuransi')])
    valid_from = models.DateField()
    valid_until = models.DateField(null=True,blank=True)
    jasa_sarana = models.DecimalField(max_digits=12,decimal_places=2)
    jasa_pelayanan = models.DecimalField(max_digits=12,decimal_places=2)
    is_free = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    review_state = models.CharField(max_length=8,choices=[('DRAFT','Draft'),('APPROVED','Disetujui')],default='DRAFT')

    class Meta:
        constraints=[
            models.UniqueConstraint(fields=['service','unit','profession','grade','payor','version'],name='professional_price_context_version'),
            models.CheckConstraint(condition=Q(jasa_sarana__gte=0,jasa_pelayanan__gte=0),name='professional_price_nonnegative'),
            models.CheckConstraint(condition=Q(valid_until__isnull=True)|Q(valid_until__gte=F('valid_from')),name='professional_price_dates_valid'),
            models.CheckConstraint(condition=Q(is_free=True,jasa_sarana=0,jasa_pelayanan=0)|Q(is_free=False)&(Q(jasa_sarana__gt=0)|Q(jasa_pelayanan__gt=0)),name='professional_price_free_explicit'),
        ]

    def clean(self):
        super().clean()
        from .services.professional_tariffs import price_breakdown
        amount=price_breakdown(self.jasa_sarana,self.jasa_pelayanan,'1')['unit_total']
        if (amount==0)!=self.is_free:
            raise ValidationError('Nol harus disetujui sebagai layanan gratis.')
        if self.grade_id and self.grade.profesi_id!=self.profession_id:
            raise ValidationError('Jenjang tidak sesuai profesi.')
        if self.review_state=='APPROVED' and not (self.is_active and self.reviewed_by_id and self.reviewed_at and self.source_version.strip()):
            raise ValidationError('Harga disetujui memerlukan sumber aktif yang ditinjau.')

    def save(self,*args,**kwargs):
        from django.db import transaction
        with transaction.atomic():
            LayananProfesional.objects.select_for_update().get(pk=self.service_id)
            if self.pk and type(self).objects.filter(pk=self.pk,review_state='APPROVED').exists():
                raise ValidationError('Versi tarif disetujui immutable; buat versi/periode baru.')
            self.full_clean()
            if self.review_state=='APPROVED':
                rows=type(self).objects.filter(service=self.service,unit=self.unit,profession=self.profession,grade=self.grade,payor=self.payor,review_state='APPROVED',is_active=True).exclude(pk=self.pk)
                if self.valid_until:rows=rows.filter(valid_from__lte=self.valid_until)
                if rows.filter(Q(valid_until__isnull=True)|Q(valid_until__gte=self.valid_from)).exists():
                    raise ValidationError('Periode tarif disetujui bertumpang tindih.')
            return super().save(*args,**kwargs)
