"""Shared result boundary for requesting clinicians and assigned performing services."""
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from akreditasi.models import AuditLog, UnitKerja
from pasien.models import OrderPenunjang, KunjunganPasien, IgdAssessmentWorkflow
from pasien.forms_igd_operations import InvestigationResultForm
from .igd_assessment_workflow import authorize_visit, WorkflowConflict, WorkflowValidation

DOCTORS={'DOKTER_UMUM','DOKTER_SPESIALIS'}
PERFORMERS=DOCTORS|{'ANALIS_LAB','RADIOGRAFER'}
User=get_user_model()

#: Unit yang menjalankan Langkah 7 kardiologi (ADR-1, F4).
KODE_UNIT_KARDIOLOGI = 'POLI-JANTUNG'

def is_cardiologi_episode(visit, workflow=None):
    """True bila order ini milik alur Poli Jantung (F4), bukan IGD."""
    if workflow is not None and getattr(workflow, 'service_line', None) == 'RAJAL_JANTUNG':
        return True
    unit = getattr(visit, 'unit_kerja', None)
    return bool(unit and unit.code == KODE_UNIT_KARDIOLOGI)


def service_units(actor):
    profile=getattr(actor,'profile',None)
    if not actor.is_authenticated or not actor.is_active or not profile or profile.role=='ASESOR' or profile.profesi not in PERFORMERS or not profile.unit_kerja_id:
        raise PermissionDenied('Hasil memerlukan petugas klinis dengan penugasan unit layanan.')
    units={profile.unit_kerja_id};pending=set(units)
    while pending:
        pending=set(UnitKerja.objects.filter(parent_id__in=pending).values_list('pk',flat=True))-units
        units.update(pending)
    return units


def service_orders(actor,*,read_only=False):
    profile=getattr(actor,'profile',None)
    if (read_only and actor.is_authenticated and actor.is_active and profile and
        (actor.is_superuser or profile.role in ('SUPER_ADMIN','ADMIN_RS','DIREKTUR'))):
        return OrderPenunjang.objects.all()
    units=service_units(actor)
    scope=Q(destination_id__in=units)
    # Existing unassigned LAB records retain their canonical laboratory worklist.
    if UnitKerja.objects.filter(pk__in=units,code='LAB-BDRS').exists():
        scope|=Q(destination__isnull=True,jenis='LAB')
    return OrderPenunjang.objects.filter(scope)


@transaction.atomic
def record_result(order_id,actor,data,*,requesting=False,manage_workflow=True,expected_state=None,correction_reason=''):
    reference=OrderPenunjang.objects.get(pk=order_id)
    visit=KunjunganPasien.objects.select_for_update().get(pk=reference.kunjungan_id)
    workflow=IgdAssessmentWorkflow.objects.select_for_update().filter(kunjungan=visit).first()
    order=OrderPenunjang.objects.select_for_update().get(pk=order_id)
    profile=getattr(actor,'profile',None)
    if requesting:
        authorize_visit(visit,actor,write=False,workflow=workflow)
        if not profile or profile.profesi not in DOCTORS or profile.role=='ASESOR':
            raise PermissionDenied('Pencatatan hasil dari IGD memerlukan dokter.')
    elif not service_orders(actor).filter(pk=order.pk).exists():
        raise PermissionDenied('Order bukan penugasan layanan Anda.')
    # F4.3 hanya untuk episode kardiologi; jalur IGD tidak berubah.
    form=InvestigationResultForm(data={'order_id':order_id,**data},
        require_interpretation=is_cardiologi_episode(visit,workflow))
    if not form.is_valid():
        raise WorkflowValidation(form.errors.get_json_data())
    values=form.cleaned_data;values.pop('order_id')
    if expected_state is not None and order.status!=expected_state:
        raise WorkflowConflict('Status hasil berubah; muat ulang worklist.')
    # F4.4: form membawa id verifikator; simpan objeknya supaya FK PROTECT
    # menahan penghapusan akun yang membuktikan read-back.
    verifier_id=values.pop('critical_readback_by',None)
    verifier=None
    if verifier_id:
        verifier=User.objects.filter(pk=verifier_id,is_active=True).first()
        if verifier is None:
            raise WorkflowValidation({'critical_readback_by':['Verifikator read-back tidak dikenal.']})
    values['critical_readback_by']=verifier
    if not order.can_transition_to(values['status']):
        raise WorkflowConflict(
            f"Status order tidak boleh berpindah dari {order.get_status_display()} "
            f"ke {dict(OrderPenunjang.STATUS_CHOICES)[values['status']]}.")
    fields=('status','hasil_pemeriksaan','interpretasi','lvef','is_critical_value','critical_value_catatan',
            'critical_found_at','critical_reported_at','critical_reported_to','critical_readback_at',
            'critical_readback_by')
    before={field:getattr(order,field) for field in fields}
    if values==before:
        return {'order_id':order.pk,'late_result':bool(workflow and workflow.status=='FINAL')}
    if order.status=='SELESAI':
        if values['status']!='SELESAI' or not isinstance(correction_reason,str) or not 8<=len(correction_reason.strip())<=2000:
            raise WorkflowValidation({'correction_reason':['Koreksi hasil selesai memerlukan alasan minimal 8 karakter dan tidak boleh menurunkan status.']})
    for field,value in values.items():
        setattr(order,field,value)
    order.result_recorded_by=actor;order.result_recorded_at=timezone.now();order.save()
    if manage_workflow and workflow:
        workflow.version+=1
        if workflow.status!='FINAL':
            workflow.signatures={}
        workflow.updated_by=actor;workflow.save(update_fields=['version','signatures','updated_by','updated_at'])
    # AuditLog menyimpan JSON: FK ditulis sebagai id, bukan objek model.
    def _audit(value):
        return getattr(value, 'pk', value)
    AuditLog.objects.create(user=actor,aksi='UPDATE',model_name='OrderPenunjang',object_repr=f'Order #{order.pk}',
        detail=json.dumps({'before':{k:_audit(v) for k,v in before.items()},
                           'after':{k:_audit(v) for k,v in values.items()},
                           'correction_reason':correction_reason,'recorded_at':order.result_recorded_at},cls=DjangoJSONEncoder))
    return {'order_id':order.pk,'late_result':bool(workflow and workflow.status=='FINAL')}
