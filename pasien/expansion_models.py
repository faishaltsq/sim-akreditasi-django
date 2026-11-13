from django.conf import settings
from django.db import models


class KomponenRacikan(models.Model):
    detail = models.ForeignKey('pasien.ResepDetail', on_delete=models.PROTECT, related_name='components')
    produk = models.ForeignKey('klinis.ProdukFarmasi', on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=4)
    unit = models.CharField(max_length=30)
    snapshot = models.JSONField(default=dict)


class AlergiPasienTerstruktur(models.Model):
    pasien = models.ForeignKey('pasien.Pasien', on_delete=models.PROTECT, related_name='structured_allergies')
    ingredient_code = models.CharField(max_length=100, blank=True)
    therapy_class_code = models.CharField(max_length=80, blank=True)
    reaction = models.TextField()
    active = models.BooleanField(default=True)
    source = models.CharField(max_length=200, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recorded_at = models.DateTimeField(auto_now_add=True)


class MedicationSafetyReview(models.Model):
    resep = models.ForeignKey('pasien.ResepElektronik', on_delete=models.PROTECT, related_name='safety_reviews')
    digest = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=100)
    findings = models.JSONField(default=list)
    acknowledgements = models.JSONField(default=list)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class PpraReviewRequest(models.Model):
    resep = models.ForeignKey('pasien.ResepElektronik', on_delete=models.PROTECT, related_name='ppra_reviews')
    digest = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=100)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    requested_at = models.DateTimeField(auto_now_add=True)
    decision = models.CharField(max_length=10, default='PENDING', choices=[('PENDING','Menunggu'),('APPROVED','Disetujui'),('REJECTED','Ditolak')])
    decided_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    decided_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    culture_order = models.ForeignKey('pasien.OrderPenunjang', null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resep','digest','policy_version'],name='unique_prescription_ppra_review')]


class PrescriptionOperation(models.Model):
    resep = models.ForeignKey('pasien.ResepElektronik', on_delete=models.PROTECT, related_name='operations')
    request_id = models.UUIDField()
    digest = models.CharField(max_length=64)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    result = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['resep','request_id'],name='unique_prescription_operation')]


class PharmacyServiceGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    unit = models.ForeignKey('akreditasi.UnitKerja', on_delete=models.PROTECT)
    can_ppra_review = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['user','unit'],name='unique_pharmacy_service_grant')]
