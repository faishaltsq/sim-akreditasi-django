"""Aksi episode IGD: transaksi, scope, versi dan replay persisten satu pintu."""
import hashlib
import json
from uuid import UUID
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from akreditasi.models import AuditLog
from pasien.forms_igd_operations import InvestigationForm, CpptForm, ActionPlanForm, ActionIdForm
from pasien.models import IgdAssessmentWorkflow, IgdWorkflowAction, OrderPenunjang, TindakanAsesmen, BillingItem, CPPT
from .igd_assessment_workflow import get_visit, authorize_visit, WorkflowConflict, WorkflowValidation

DOCTORS = {'DOKTER_UMUM', 'DOKTER_SPESIALIS'}
NURSES = {'PERAWAT', 'BIDAN'}


def validate(form_type, data):
    form = form_type(data=data)
    if not form.is_valid():
        raise WorkflowValidation(form.errors.get_json_data())
    return form.cleaned_data


def require_doctor(user):
    if user.profile.profesi not in DOCTORS:
        raise PermissionDenied('Aksi ini memerlukan dokter terautentikasi.')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, cls=DjangoJSONEncoder, allow_nan=False).encode()).hexdigest()


def order(visit, workflow, user, data):
    require_doctor(user)
    values = validate(InvestigationForm, data)
    record = OrderPenunjang.objects.create(kunjungan=visit, dokter_pengirim=user.get_full_name() or user.username, **values)
    return {'order_id': record.pk}


def cppt(visit, workflow, user, data):
    values = validate(CpptForm, data)
    note = CPPT.objects.create(kunjungan=visit, profesi='DOKTER' if user.profile.profesi in DOCTORS else 'PERAWAT' if user.profile.profesi == 'PERAWAT' else 'BIDAN',
                               nama_ppa=user.get_full_name() or user.username, tanggal=timezone.now(), created_by=user,
                               verifikasi_dpjp=user.profile.profesi in DOCTORS, **values)
    return {'cppt_id':note.pk}


def plan_action(visit, workflow, user, data):
    from klinis.models import MasterIcd9, SikiIntervensi
    from klinis.services.tarif import resolve_detail
    from klinis.services.ep_tindakan import primary_for
    from akreditasi.models import StandardItem
    values = validate(ActionPlanForm, data)
    jenis = values['jenis']
    team = 'KEPERAWATAN' if jenis == 'SIKI' or (jenis == 'BEBAS' and user.profile.profesi in NURSES) else 'MEDIS'
    if team == 'MEDIS':
        require_doctor(user)
    elif user.profile.profesi not in NURSES:
        raise PermissionDenied('Rencana keperawatan memerlukan perawat/bidan.')
    reference = None
    if jenis != 'BEBAS':
        reference = (MasterIcd9 if jenis == 'ICD9' else SikiIntervensi).objects.filter(kode=values['kode']).first()
        if reference is None:
            raise WorkflowValidation({'kode':['Kode tidak ada pada master.']})
    if not values['nama'] and reference is None:
        raise WorkflowValidation({'nama':['Nama tindakan manual wajib diisi.']})
    if values['action_id']:
        line = TindakanAsesmen.objects.filter(kunjungan=visit, pk=values['action_id']).first()
        if line is None or line.execution_status != 'PLANNED' or line.billing_item_id:
            raise WorkflowConflict('Hanya rencana belum terlaksana yang dapat diedit.')
        if line.execution_team != team:
            raise PermissionDenied('Rencana tidak boleh dialihkan ke profesi lain melalui edit.')
    else:
        sequence = (visit.tindakan_asesmen.aggregate(n=Max('urutan'))['n'] or 0) + 1
        line = TindakanAsesmen(kunjungan=visit, urutan=sequence, execution_status='PLANNED')
    before = {name:getattr(line,name) for name in ('tarif','tarif_acuan','quantity','tarif_penjamin','catatan_tarif')}
    line.jenis, line.kode = jenis, values['kode']
    line.nama = values['nama'] or reference.nama
    line.icd9 = reference if jenis == 'ICD9' else None
    line.siki = reference if jenis == 'SIKI' else None
    line.sumber_data = 'MASTER' if reference else 'MANUAL'
    line.execution_team = team
    line.tarif_penjamin = visit.penjamin
    line.quantity = values['quantity'] or Decimal('1')
    detail = resolve_detail(visit, line.kode) if jenis == 'ICD9' and visit.penjamin != 'ASURANSI' else None
    line.tarif_acuan = detail['nominal'] if detail else None
    line.tarif, line.catatan_tarif = values['tarif'], values['catatan_tarif']
    if line.tarif is not None and line.tarif != line.tarif_acuan and not line.catatan_tarif:
        raise WorkflowValidation({'catatan_tarif':['Alasan tarif manual/override wajib diisi.']})
    from akreditasi.models import Framework
    active_items = StandardItem.objects.filter(category__framework=Framework.active())
    if values['standard_item']:
        line.standard_item = active_items.filter(pk=values['standard_item']).first()
        if not line.standard_item:
            raise WorkflowValidation({'standard_item':['EP tidak ditemukan.']})
    elif not line.pk:
        rule = primary_for(jenis, line.kode)
        if rule:
            line.standard_item = active_items.filter(sub_standard=rule.sub_standard).first()
    if values['ep_status']:
        line.ep_status = values['ep_status']
    line.ep_catatan = values['ep_catatan']
    if line.ep_status == 'TERPENUHI' and (not line.standard_item_id or not line.ep_catatan.strip()):
        raise WorkflowValidation({'ep_catatan':['Status terpenuhi memerlukan EP yang valid dan referensi bukti.']})
    line.diubah_oleh = user
    line.save()
    after = {name:getattr(line,name) for name in before}
    if before != after:
        AuditLog.objects.create(user=user,aksi='UPDATE',model_name='TindakanAsesmen',object_repr=f'Tindakan #{line.pk}',
            detail=json.dumps({'before':before,'after':after,'reason':line.catatan_tarif},cls=DjangoJSONEncoder))
    return {'action_id':line.pk}


def execute(visit, workflow, user, data):
    values = validate(ActionIdForm, data)
    line = TindakanAsesmen.objects.filter(kunjungan=visit, pk=values['action_id']).first()
    if line is None:
        raise WorkflowValidation({'action_id':['Tindakan tidak ditemukan pada kunjungan ini.']})
    if line.execution_team == 'MEDIS':
        require_doctor(user)
    elif line.execution_team == 'KEPERAWATAN' and user.profile.profesi not in NURSES:
        raise PermissionDenied('Pelaksanaan keperawatan memerlukan perawat/bidan.')
    if line.execution_status == 'PERFORMED':
        return {'action_id':line.pk,'cppt_id':line.execution_cppt_id,'billing_id':line.billing_item_id}
    if line.execution_status != 'PLANNED' or line.tarif_penjamin != visit.penjamin:
        raise WorkflowConflict('Status tindakan/penjamin berubah; tinjau rencana terlebih dahulu.')
    note = cppt(visit, workflow, user, {'objektif':f'Tindakan: {line.nama}', 'plan':f'Dilaksanakan {line.quantity} kali oleh petugas terautentikasi.'})
    if line.tarif_efektif is not None and line.tarif_efektif > 0:
        line.billing_item = BillingItem.objects.create(kunjungan=visit, kategori='JASA_MEDIS', nama_item=line.nama,
            kode_icd=line.kode, sumber='ASESMEN', kuantitas=line.quantity, harga_satuan=line.tarif_efektif, dicatat_oleh=user)
    line.execution_status, line.performed_by, line.performed_at = 'PERFORMED', user, timezone.now()
    line.execution_cppt_id = note['cppt_id']
    line.save()
    return {'action_id':line.pk, 'cppt_id':line.execution_cppt_id, 'billing_id':line.billing_item_id}


def cancel_action(visit, workflow, user, data):
    values = validate(ActionIdForm, data)
    line = TindakanAsesmen.objects.filter(kunjungan=visit, pk=values['action_id']).first()
    if not line or line.execution_status != 'PLANNED' or line.billing_item_id:
        raise WorkflowConflict('Tindakan historis/terlaksana tidak boleh dihapus atau dibatalkan lewat rencana.')
    if line.execution_team == 'MEDIS':
        require_doctor(user)
    elif line.execution_team == 'KEPERAWATAN' and user.profile.profesi not in NURSES:
        raise PermissionDenied('Pembatalan rencana keperawatan memerlukan perawat/bidan.')
    line.execution_status = 'CANCELLED'
    line.save(update_fields=['execution_status'])
    return {'action_id':line.pk}


def order_result(visit, workflow, user, data):
    from pasien.forms_igd_operations import InvestigationResultForm
    require_doctor(user)
    values = validate(InvestigationResultForm,data)
    record = visit.order_penunjang.filter(pk=values.pop('order_id')).first()
    if record is None:
        raise WorkflowValidation({'order_id':['Order tidak ditemukan pada episode ini.']})
    for name,value in values.items():
        setattr(record,name,value)
    record.result_recorded_by, record.result_recorded_at = user, timezone.now()
    record.save()
    return {'order_id':record.pk,'late_result':workflow.status=='FINAL'}


HANDLERS = {'order': order, 'cppt': cppt, 'plan_action': plan_action, 'execute': execute, 'cancel_action': cancel_action, 'order_result':order_result}


@transaction.atomic
def perform_action(pk, user, operation, payload, version, request_id, attachment=None):
    if operation == 'attachment':
        from .igd_attachments import store_attachment
        HANDLERS['attachment'] = store_attachment
    if operation in ('sign','finalize','addendum'):
        from .igd_finalization import sign, finalize, addendum
        HANDLERS.update(sign=sign, finalize=finalize, addendum=addendum)
    if operation not in HANDLERS or not isinstance(payload, dict):
        raise WorkflowValidation({'__all__':['Aksi/payload tidak valid.']})
    try:
        key = UUID(str(request_id))
        fingerprint = digest({'operation':operation,'payload':payload})
    except (ValueError, TypeError) as exc:
        raise WorkflowValidation({'request_id':['ID permintaan atau payload tidak valid.']}) from exc
    visit, workflow = get_visit(pk, user, lock=True)
    if user.profile.profesi not in DOCTORS | NURSES or user.profile.role == 'ASESOR':
        raise PermissionDenied('Aksi klinis memerlukan profesi klinis yang berwenang.')
    if workflow:
        previous = workflow.actions.filter(request_id=key).first()
        if previous:
            if previous.digest != fingerprint or previous.actor_id != user.pk:
                raise WorkflowConflict('ID permintaan sudah dipakai untuk aksi berbeda.')
            return {**previous.result, 'version':workflow.version, 'replayed':True}
    if operation != 'addendum' and not (operation == 'order_result' and workflow and workflow.status == 'FINAL'):
        authorize_visit(visit, user, write=True, workflow=workflow)
    if workflow and workflow.status == 'FINAL' and operation not in ('addendum','order_result'):
        raise WorkflowConflict('Dokumentasi final tidak dapat ditimpa; gunakan addendum.')
    try:
        if int(version) != (workflow.version if workflow else 0):
            raise WorkflowConflict('Konflik versi: muat ulang episode.')
    except (TypeError, ValueError) as exc:
        raise WorkflowConflict('Konflik versi: muat ulang episode.') from exc
    if workflow is None:
        workflow = IgdAssessmentWorkflow.objects.create(kunjungan=visit, origin_unit=visit.unit_kerja)
    result = HANDLERS[operation](visit, workflow, user, payload, attachment) if operation == 'attachment' else HANDLERS[operation](visit, workflow, user, payload)
    if operation not in ('sign','finalize','addendum') and workflow.status != 'FINAL':
        workflow.signatures = {}
    workflow.version += 1
    workflow.updated_by = user
    workflow.save()
    IgdWorkflowAction.objects.create(workflow=workflow, request_id=key, operation=operation,
                                     digest=fingerprint, actor=user, result=result)
    AuditLog.objects.create(user=user, aksi='CREATE', model_name='IgdWorkflowAction',
                            object_repr=f'Workflow #{workflow.pk}', detail=f'{operation}; versi {workflow.version}')
    return {**result, 'version':workflow.version, 'replayed':False}
