"""Aplikasi penyimpanan draft IGD dan batas kompatibilitas writer lama."""
from functools import wraps

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from akreditasi.models import AuditLog
from pasien.forms_igd_workflow import STEPS, VITAL_FIELDS, form_for_step
from pasien.models import IgdAssessmentWorkflow, IgdVitalObservation, KunjunganPasien
from pasien.unit_scope import can_read_kunjungan, get_unit_scope

CLINICAL_PROFESSIONS = {'DOKTER_UMUM', 'DOKTER_SPESIALIS', 'PERAWAT', 'BIDAN'}


class WorkflowConflict(ValueError):
    pass


class WorkflowValidation(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('Data langkah belum valid.')


def authorize_visit(visit, user, *, write=False, workflow=None):
    profile = getattr(user, 'profile', None)
    if not user.is_authenticated or profile is None:
        raise PermissionDenied('Profil pengguna diperlukan.')
    modules = profile.get_allowed_patient_modules()
    if not user.is_superuser and 'igd' not in modules and not (not write and workflow and workflow.status == 'FINAL' and 'riwayat' in modules):
        raise PermissionDenied('Akses modul IGD diperlukan.')
    scope = get_unit_scope(profile)
    historical_units = {workflow.origin_unit_id} if workflow else set()
    if workflow and workflow.status == 'FINAL':
        historical_units.add(visit.unit_kerja_id)
    origin_access = workflow is not None and (scope is None or any(u.pk in historical_units for u in scope))
    if not can_read_kunjungan(visit, profile) and not (origin_access and not write):
        raise PermissionDenied('Kunjungan di luar lingkup unit Anda.')
    if write and (profile.profesi not in CLINICAL_PROFESSIONS or profile.role == 'ASESOR'):
        raise PermissionDenied('Penyimpanan klinis memerlukan profesi klinis yang berwenang.')
    if write and visit.jenis_kunjungan != 'IGD':
        raise PermissionDenied('Episode IGD yang sudah ditransfer hanya dapat dibaca.')
    if write and visit.status in ('PULANG', 'RUJUK', 'MENINGGAL', 'BATAL'):
        raise PermissionDenied('Episode yang sudah ditutup hanya dapat dibaca.')


def get_visit(pk, user, *, write=False, lock=False):
    qs = KunjunganPasien.objects.select_for_update() if lock else KunjunganPasien.objects.all()
    visit = get_object_or_404(qs, pk=pk)
    workflow = IgdAssessmentWorkflow.objects.filter(kunjungan=visit).first()
    if visit.jenis_kunjungan != 'IGD' and workflow is None:
        raise PermissionDenied('Alur ini hanya untuk episode IGD.')
    authorize_visit(visit, user, write=write, workflow=workflow)
    return visit, workflow


@transaction.atomic
def save_step(pk, user, step, payload, version):
    visit, workflow = get_visit(pk, user, write=True, lock=True)
    if step not in STEPS or set(payload) - set(STEPS[step][1]) - ({'ai_ticket'} if step == 8 else set()) - {'observed_at','corrects_id'}:
        raise WorkflowValidation({'__all__': ['Field tidak dimiliki langkah ini.']})
    if 'observed_at' in payload and step not in (4, 10):
        raise WorkflowValidation({'observed_at': ['Waktu pengukuran hanya untuk langkah TTV.']})
    correction = None
    if payload.get('corrects_id'):
        from django.forms import IntegerField
        from django.core.exceptions import ValidationError
        try:
            correction_id = IntegerField(min_value=1).clean(payload['corrects_id'])
        except ValidationError as exc:
            raise WorkflowValidation({'corrects_id':exc.messages}) from exc
        if step not in (4,10) or workflow is None or not any(name in payload for name in VITAL_FIELDS):
            raise WorkflowValidation({'corrects_id':['Koreksi memerlukan pengukuran pada episode dan fase yang sama.']})
        correction = workflow.observations.filter(pk=correction_id,phase='INITIAL' if step == 4 else 'EVALUATION').first()
        if correction is None:
            raise WorkflowValidation({'corrects_id':['Observasi sumber tidak ditemukan pada episode/fase ini.']})
    if workflow is not None and workflow.status == 'FINAL':
        raise WorkflowConflict('Asesmen sudah final; gunakan addendum.')
    try:
        expected = int(version)
    except (TypeError, ValueError) as exc:
        raise WorkflowConflict('Nomor versi tidak valid.') from exc
    if expected != (workflow.version if workflow else 0):
        raise WorkflowConflict('Konflik versi: muat ulang draft terbaru sebelum menyimpan.')
    if not payload:
        raise WorkflowValidation({'__all__': ['Tidak ada perubahan untuk disimpan.']})
    provenance = None
    if step == 8:
        from .igd_planning import validate_planning
        payload, provenance = validate_planning(visit,user,payload,expected)
    if 'penjamin' in payload and payload['penjamin'] != visit.penjamin:
        raise WorkflowValidation({'penjamin': ['Koreksi penjamin melalui admisi dan tinjau ulang tarif terlebih dahulu.']})
    fields = STEPS[step][1]
    merged = {}
    form = form_for_step(step, instance=visit)
    for name in fields:
        merged[name] = form.fields[name].prepare_value(getattr(visit, name))
    merged.update({name: value for name, value in payload.items() if name in fields})
    form = form_for_step(step, instance=visit, data=merged)
    if not form.is_valid():
        raise WorkflowValidation(form.errors.get_json_data())
    observed_at = correction.observed_at if correction else timezone.now()
    if 'observed_at' in payload:
        from django.forms import DateTimeField
        from django.core.exceptions import ValidationError
        try:
            observed_at = DateTimeField().clean(payload['observed_at'])
        except ValidationError as exc:
            raise WorkflowValidation({'observed_at': exc.messages}) from exc
        if observed_at is None or observed_at > timezone.now():
            raise WorkflowValidation({'observed_at': ['Waktu pengukuran tidak boleh kosong atau di masa depan.']})
    if workflow is None:
        workflow = IgdAssessmentWorkflow.objects.create(kunjungan=visit, origin_unit=visit.unit_kerja)
    changed = [name for name in payload if name in fields]
    if step in (4,10) and any(name in payload for name in ('gcs_e','gcs_v','gcs_m')) and all(form.cleaned_data.get(name) is not None for name in ('gcs_e','gcs_v','gcs_m')):
        visit.ttv_gcs = form.cleaned_data['ttv_gcs']
        if 'ttv_gcs' not in changed:
            changed.append('ttv_gcs')
    if provenance is not None:
        visit.diagnosis_provenance = provenance
        changed.append('diagnosis_provenance')
    if step == 5:
        for source, derived in [('skrining_jatuh_detail', ('skrining_jatuh_skor','skrining_jatuh_grade','metode_risiko_jatuh')), ('skrining_gizi_detail', ('skrining_gizi_mst',))]:
            if payload.get(source):
                for name in derived:
                    setattr(visit, name, form.cleaned_data[name])
                    if name not in changed:
                        changed.append(name)
    latest = workflow.observations.order_by('-observed_at', '-pk').first()
    observation_values = {name: form.cleaned_data[name] for name in changed if name in VITAL_FIELDS}
    if step in (4, 10) and observation_values:
        phase = 'INITIAL' if step == 4 else 'EVALUATION'
        previous = correction or workflow.observations.filter(phase=phase).order_by('-observed_at','-pk').first()
        IgdVitalObservation.objects.create(
            workflow=workflow, phase=phase, corrects=correction,
            observed_at=observed_at, recorded_by=user, data={**(previous.data if previous else {}), **observation_values},
        )
        if latest and latest.observed_at > observed_at:
            changed = [name for name in changed if name not in VITAL_FIELDS]
    if changed:
        visit.save(update_fields=changed)
    workflow.version += 1
    workflow.last_step = step
    workflow.updated_by = user
    workflow.signatures = {}
    workflow.save(update_fields=['version', 'last_step', 'updated_by', 'updated_at', 'signatures'])
    AuditLog.objects.create(user=user, aksi='UPDATE', model_name='IgdAssessmentWorkflow',
                            object_repr=f'Workflow #{workflow.pk}',
                            detail=f'Draft langkah {step}; versi {workflow.version}; field: {", ".join(sorted(payload))}')
    return workflow


def legacy_workflow_guard(view):
    @wraps(view)
    def guarded(request, *args, **kwargs):
        mutation = request.method not in ('GET', 'HEAD', 'OPTIONS') or view.__name__ == 'igd_asesmen_copy_prev'
        pk = kwargs.get('pk', kwargs.get('kunjungan_pk', kwargs.get('kunjungan_id')))
        if request.user.is_authenticated and pk and view.__name__ in ('cetak_resume_igd','cetak_asesmen_medis_igd','asesmen_detail'):
            if IgdAssessmentWorkflow.objects.filter(kunjungan_id=pk,status='FINAL').exists():
                from django.shortcuts import redirect
                get_visit(pk,request.user)
                return redirect('pasien:igd_workflow_resume',pk=pk)
        if not mutation or pk is None or not request.user.is_authenticated:
            return view(request, *args, **kwargs)
        with transaction.atomic():
            visit = KunjunganPasien.objects.select_for_update().filter(pk=pk).first()
            workflow = IgdAssessmentWorkflow.objects.filter(kunjungan=visit).first() if visit else None
            if workflow:
                later_care = {'cppt_tambah','order_penunjang_buat','order_lab_create','discharge_proses','kunjungan_disposisi','asesmen_lampiran_upload'}
                if workflow.status == 'FINAL' and visit.jenis_kunjungan in ('RANAP','RAJAL') and view.__name__ in later_care:
                    profile = getattr(request.user,'profile',None)
                    module = 'ranap' if visit.jenis_kunjungan == 'RANAP' else 'rajal'
                    if not profile or profile.profesi not in CLINICAL_PROFESSIONS or profile.role == 'ASESOR' or not can_read_kunjungan(visit,profile):
                        raise PermissionDenied('Perawatan lanjutan memerlukan profesi dan lingkup unit tujuan.')
                    if not request.user.is_superuser and module not in profile.get_allowed_patient_modules():
                        raise PermissionDenied('Akses modul layanan tujuan diperlukan.')
                    return view(request,*args,**kwargs)
                authorize_visit(visit, request.user, workflow=workflow)
                return JsonResponse({'success': False, 'error': 'Episode ini dikelola alur IGD. Gunakan draft berversi atau addendum untuk rekam final.'}, status=409)
            return view(request, *args, **kwargs)
    return guarded
