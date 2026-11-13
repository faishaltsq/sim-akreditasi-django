from datetime import timedelta
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone
from akreditasi.models import AuditLog
from pasien.models import PpraReviewRequest, PharmacyServiceGrant, KunjunganPasien, IgdAssessmentWorkflow
from .medication_safety import active_policy
from .prescriptions import content_digest


@transaction.atomic
def review_ppra(actor,request_id,decision,reason,expected_digest):
    ref=PpraReviewRequest.objects.select_related('resep').get(pk=request_id)
    KunjunganPasien.objects.select_for_update().get(pk=ref.resep.kunjungan_id)
    IgdAssessmentWorkflow.objects.select_for_update().filter(kunjungan_id=ref.resep.kunjungan_id).first()
    rx=ref.resep.__class__.objects.select_for_update().select_related('kunjungan__pasien').get(pk=ref.resep_id)
    request=PpraReviewRequest.objects.select_for_update().get(pk=request_id)
    profile=getattr(actor,'profile',None)
    if not profile or profile.role=='ASESOR' or profile.profesi not in ('DOKTER_UMUM','DOKTER_SPESIALIS','APOTEKER') or not PharmacyServiceGrant.objects.filter(user=actor,unit_id=rx.serving_unit_id,can_ppra_review=True).exists():
        raise PermissionDenied('Persetujuan PPRA memerlukan reviewer yang ditugaskan.')
    if request.requested_by_id==actor.pk or rx.dokter_peresep_id==actor.pk:
        raise PermissionDenied('Pemohon tidak boleh menyetujui resep sendiri.')
    policy=active_policy()
    if policy is None or policy.version!=request.policy_version or request.digest!=expected_digest or content_digest(rx)!=expected_digest:
        raise ValueError('Kebijakan atau isi resep berubah; buat tinjauan baru.')
    if request.decision!='PENDING' or decision not in ('APPROVED','REJECTED') or not isinstance(reason,str) or not 5<=len(reason.strip())<=2000:
        raise ValueError('Keputusan dan alasan PPRA tidak valid.')
    request.decision=decision;request.reason=reason.strip();request.decided_by=actor;request.decided_at=timezone.now()
    request.expires_at=timezone.now()+timedelta(hours=24);request.save()
    AuditLog.objects.create(user=actor,aksi='UPDATE',model_name='PpraReviewRequest',object_repr=f'PPRA #{request.pk}',detail=f'{decision}; {reason}')
    return {'ppra_request_id':request.pk,'decision':decision}
