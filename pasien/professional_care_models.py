from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q,F


class ImmutableCareRecord(models.Model):
    class Meta:
        abstract=True

    def save(self,*args,**kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError('Bukti pelayanan bersifat immutable.')
        return super().save(*args,**kwargs)

    def delete(self,*args,**kwargs):
        raise ValidationError('Bukti pelayanan tidak boleh dihapus.')


class CpptRevision(ImmutableCareRecord):
    note=models.ForeignKey('pasien.CPPT',on_delete=models.PROTECT,related_name='care_revisions')
    version=models.PositiveIntegerField()
    snapshot=models.JSONField(encoder=DjangoJSONEncoder)
    digest=models.CharField(max_length=64)
    author=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    signed_at=models.DateTimeField(auto_now_add=True)
    reason=models.TextField(blank=True)

    class Meta:
        constraints=[models.UniqueConstraint(fields=['note','version'],name='professional_note_revision_unique')]


class PenugasanDpjpEpisode(models.Model):
    visit=models.ForeignKey('pasien.KunjunganPasien',on_delete=models.PROTECT,related_name='dpjp_assignments')
    doctor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    unit=models.ForeignKey('akreditasi.UnitKerja',on_delete=models.PROTECT)
    assignment_type=models.CharField(max_length=10,choices=[('PRIMARY','Utama'),('SUBSTITUTE','Pengganti')])
    valid_from=models.DateField()
    valid_until=models.DateField()
    is_active=models.BooleanField(default=False)
    source_version=models.CharField(max_length=200)
    assigned_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    assigned_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=Q(valid_until__gte=F('valid_from')),name='professional_dpjp_dates_valid')]

    def clean(self):
        if self.doctor_id==self.assigned_by_id:raise ValidationError('DPJP tidak boleh mengesahkan penugasannya sendiri.')
        if self.is_active and self.visit_id and self.visit.unit_kerja_id!=self.unit_id:raise ValidationError('Unit penugasan tidak sesuai episode.')
        if self.doctor_id and self.doctor.profile.profesi not in {'DOKTER_UMUM','DOKTER_SPESIALIS','DOKTER_GIGI'}:raise ValidationError('DPJP harus akun dokter.')
        if not self.source_version.strip():raise ValidationError('Sumber penugasan wajib diisi.')

    def save(self,*args,**kwargs):
        original=type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if original and any(getattr(original,key)!=getattr(self,key) for key in ('visit_id','doctor_id','unit_id','assignment_type','valid_from','valid_until','source_version','assigned_by_id')):
            raise ValidationError('Identitas/sumber penugasan tidak dapat ditimpa; cabut lalu buat penugasan baru.')
        self.full_clean()
        return super().save(*args,**kwargs)


class VerifikasiCppt(ImmutableCareRecord):
    verifier_name=models.CharField(max_length=301,blank=True)
    assignment_snapshot=models.JSONField(default=dict,encoder=DjangoJSONEncoder)
    revision=models.OneToOneField(CpptRevision,on_delete=models.PROTECT,related_name='verification')
    verifier=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    assignment=models.ForeignKey(PenugasanDpjpEpisode,on_delete=models.PROTECT)
    performed_at=models.DateTimeField(auto_now_add=True)
    digest=models.CharField(max_length=64)
    request_id=models.UUIDField(unique=True)


class PembatalanTagihan(ImmutableCareRecord):
    item=models.OneToOneField('pasien.BillingItem',on_delete=models.PROTECT,related_name='void_record')
    action=models.ForeignKey('pasien.TindakanAsesmen',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name='+')
    amount=models.DecimalField(max_digits=14,decimal_places=2)
    reason=models.TextField()
    request_id=models.UUIDField(unique=True)
    created_at=models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints=[models.CheckConstraint(condition=Q(amount__gte=0),name='professional_void_nonnegative')]
