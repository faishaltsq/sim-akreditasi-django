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
from pasien.workflow_schemas import (
    RAJAL_JANTUNG_SCHEMA_KEY, RAJAL_JANTUNG_STEPS, STEP_SCHEMAS, validate_disposisi_rajal,
)
from .poli_rbac import authorize_step, can_write, episode_dpjp

CLINICAL_PROFESSIONS = {'DOKTER_UMUM', 'DOKTER_SPESIALIS', 'PERAWAT', 'BIDAN'}

IGD_SERVICE_LINE = 'IGD'
RAJAL_JANTUNG_SERVICE_LINE = 'RAJAL_JANTUNG'
POLI_JANTUNG_UNIT_CODE = 'POLI-JANTUNG'
#: Modul yang boleh membuka episode POLI-JANTUNG. ``farmasi`` ikut karena
#: matriks ADR-11 memberi Farmasi wewenang menulis langkah 9, sedangkan
#: ``get_allowed_patient_modules`` memetakan profesi apoteker/TTK ke modul
#: ``farmasi`` dan bukan ``rajal``. Wewenang per langkah tetap ditentukan
#: matriks; gerbang modul hanya mencegah peran di luar tim (lab, admisi).
RAJAL_JANTUNG_MODULES = {'rajal', 'farmasi'}


class WorkflowConflict(ValueError):
    pass


class WorkflowValidation(ValueError):
    def __init__(self, errors):
        self.errors = errors
        super().__init__('Data langkah belum valid.')


def resolve_service_line(visit, workflow, service_line=None):
    """Tentukan jalur layanan tanpa menebak: eksplisit > workflow > episode > IGD.

    Langkah terakhir (F6.1) ada karena episode POLI-JANTUNG dapat belum punya
    workflow saat operasi pertama dijalankan — ``perform_action`` membuatnya
    sendiri. Tanpa turunan ini, ``require_scope`` (yang tidak membawa workflow)
    akan memeriksa episode rawat jalan sebagai IGD dan menolaknya karena modul
    IGD. Episode IGD dan rawat jalan di unit lain tetap menghasilkan ``IGD``
    persis seperti sebelumnya.
    """
    if service_line is not None:
        if service_line not in STEP_SCHEMAS:
            raise PermissionDenied('Jalur layanan tidak dikenal.')
        if workflow is not None and workflow.service_line != service_line:
            raise PermissionDenied('Jalur layanan episode tidak sesuai.')
        return service_line
    if workflow is not None:
        return workflow.service_line
    if (visit is not None and visit.jenis_kunjungan == 'RAJAL'
            and visit.unit_kerja_id and visit.unit_kerja.code == POLI_JANTUNG_UNIT_CODE):
        return RAJAL_JANTUNG_SERVICE_LINE
    return IGD_SERVICE_LINE

def require_rajal_jantung_episode(visit):
    """Episode harus rawat jalan pada unit POLI-JANTUNG."""
    if visit.jenis_kunjungan != 'RAJAL':
        raise PermissionDenied('Asesmen POLI-JANTUNG hanya untuk episode rawat jalan.')
    if not visit.unit_kerja_id or visit.unit_kerja.code != POLI_JANTUNG_UNIT_CODE:
        raise PermissionDenied('Episode bukan pada unit POLI-JANTUNG.')

def _authorize_rajal_visit(visit, user, *, write, workflow):
    profile = getattr(user, 'profile', None)
    if not user.is_authenticated or profile is None:
        raise PermissionDenied('Profil pengguna diperlukan.')
    modules = profile.get_allowed_patient_modules()
    if not user.is_superuser and not (RAJAL_JANTUNG_MODULES & modules):
        raise PermissionDenied('Akses modul rawat jalan diperlukan.')
    scope = get_unit_scope(profile)
    historical_units = {workflow.origin_unit_id} if workflow and workflow.origin_unit_id else set()
    origin_access = workflow is not None and (scope is None or any(u.pk in historical_units for u in scope))
    readable = can_read_kunjungan(visit, profile)
    if not readable and not (origin_access and not write):
        if not (origin_access and write and workflow is not None and workflow.status == 'FINAL'):
            raise PermissionDenied('Kunjungan di luar lingkup unit Anda.')
    if write:
        if not can_write(visit, user):
            raise PermissionDenied('Penyimpanan klinis memerlukan peran asesmen POLI-JANTUNG.')
        # Episode FINAL tidak lagi aktif sehingga lolos dari scope baca; penulisan
        # draft harus berakhir 409 "gunakan addendum", bukan 403 yang menyamarkan
        # sebabnya. Matriks per langkah tetap ditegakkan di _save_rajal_step.
        if workflow is not None and workflow.status == 'FINAL':
            return
        if visit.status in ('PULANG', 'RUJUK', 'MENINGGAL', 'BATAL'):
            raise PermissionDenied('Episode yang sudah ditutup hanya dapat dibaca.')
        # ADR-11 butir 4: tanpa DPJP aktif, episode tidak boleh masuk langkah klinis.
        episode_dpjp(visit)

def authorize_visit(visit, user, *, write=False, workflow=None, service_line=None):
    line = resolve_service_line(visit, workflow, service_line)
    if line == RAJAL_JANTUNG_SERVICE_LINE:
        return _authorize_rajal_visit(visit, user, write=write, workflow=workflow)
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


def get_visit(pk, user, *, write=False, lock=False, service_line=None):
    qs = KunjunganPasien.objects.select_for_update() if lock else KunjunganPasien.objects.all()
    visit = get_object_or_404(qs, pk=pk)
    workflow = IgdAssessmentWorkflow.objects.filter(kunjungan=visit).first()
    line = resolve_service_line(visit, workflow, service_line)
    if line == RAJAL_JANTUNG_SERVICE_LINE:
        require_rajal_jantung_episode(visit)
    elif visit.jenis_kunjungan != 'IGD' and workflow is None:
        raise PermissionDenied('Alur ini hanya untuk episode IGD.')
    authorize_visit(visit, user, write=write, workflow=workflow, service_line=line)
    return visit, workflow


@transaction.atomic
def save_step(pk, user, step, payload, version, *, service_line=None):
    visit, workflow = get_visit(pk, user, write=True, lock=True, service_line=service_line)
    if resolve_service_line(visit, workflow, service_line) == RAJAL_JANTUNG_SERVICE_LINE:
        return _save_rajal_step(visit, workflow, user, step, payload, version)
    if step not in STEPS or set(payload) - set(STEPS[step][1]) - ({'ai_ticket', 'component_modes', 'component_tickets'} if step == 8 else set()) - {'observed_at','corrects_id'}:
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
    if not payload and STEPS[step][1]:
        raise WorkflowValidation({'__all__': ['Tidak ada perubahan untuk disimpan.']})
    provenance = None
    if step == 8:
        if 'diagnosa_masuk' in payload and visit.diagnoses.exists() and payload['diagnosa_masuk'] != visit.diagnosa_masuk:
            raise WorkflowValidation({'diagnosa_masuk': ['Gunakan daftar diagnosis terstruktur untuk mengubah diagnosis medis.']})
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
    if step == 6 and 'secondary_survey_detail' in payload:
        for name in ('secondary_survey_detail','fisik_head_to_toe'):
            if name not in changed:
                changed.append(name)
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

def _expand_group_keys(payload):
    """Ubah kunci bertitik menjadi dict bersarang sebelum validasi.

    Formulir merender sub-field ``group`` sebagai ``fisik_kardio.murmur_derajat``
    karena HTML tidak punya objek bersarang. Skema tetap menerima bentuk dict
    (``{'fisik_kardio': {'murmur_derajat': '2/6'}}``), jadi kedua bentuk masuk
    lewat jalur yang sama dan hanya ada satu aturan validasi.
    """
    expanded = {}
    for name, value in payload.items():
        if isinstance(name, str) and '.' in name:
            parent, child = name.split('.', 1)
            bucket = expanded.get(parent)
            if not isinstance(bucket, dict):
                bucket = {}
                expanded[parent] = bucket
            bucket[child] = value
        elif isinstance(value, dict) and isinstance(expanded.get(name), dict):
            expanded[name] = {**expanded[name], **value}
        else:
            expanded[name] = value
    return expanded

def _save_rajal_step(visit, workflow, user, step, payload, version):
    """Simpan satu langkah RAJAL_JANTUNG ke ``draft_payload`` (ADR-9).

    Satu-satunya kolom ``KunjunganPasien`` yang ikut ditulis adalah
    ``red_flag_kardio``/``red_flag_at`` (F2.5): keduanya di-query per baris
    antrean dan untuk agregat door-to-ECG, sehingga tidak dapat tinggal di JSON.
    Nilai langkah lain tidak menyentuh kolom model.
    """
    spec = RAJAL_JANTUNG_STEPS.get(step)
    if spec is None:
        raise WorkflowValidation({'__all__': ['Langkah tidak valid.']})
    if not isinstance(payload, dict):
        raise WorkflowValidation({'__all__': ['Payload langkah harus objek.']})
    payload = _expand_group_keys(payload)
    if set(payload) - set(spec.field_names):
        raise WorkflowValidation({'__all__': ['Field tidak dimiliki langkah ini.']})
    authorize_step(user, visit, step, 'fill')
    if workflow is not None and workflow.status == 'FINAL':
        raise WorkflowConflict('Asesmen sudah final; gunakan addendum.')
    try:
        expected = int(version)
    except (TypeError, ValueError) as exc:
        raise WorkflowConflict('Nomor versi tidak valid.') from exc
    if expected != (workflow.version if workflow else 0):
        raise WorkflowConflict('Konflik versi: muat ulang draft terbaru sebelum menyimpan.')
    if not payload and spec.fields:
        raise WorkflowValidation({'__all__': ['Tidak ada perubahan untuk disimpan.']})
    cleaned, errors = spec.validate(payload)
    if errors:
        raise WorkflowValidation(errors)
    if step == 10:
        # Percabangan S10-L1-05 divalidasi memakai nilai gabungan: isian cabang
        # boleh dikirim bertahap, jadi syaratnya diperiksa terhadap draft baru.
        merged_step10 = {**(((workflow.draft_payload if workflow else {}) or {}).get('10') or {}), **cleaned}
        branch_errors = validate_disposisi_rajal(merged_step10)
        if branch_errors:
            raise WorkflowValidation(branch_errors)
    # F5.7: matriks S8-L1-01 menyebut tiga mode, tetapi penyedia AI baru F9.
    # Menerima nilai AI lalu menyimpannya diam-diam akan membuat provenance
    # berbohong, jadi ditolak dengan sebab yang eksplisit.
    from pasien.workflow_schemas import INPUT_MODE_UNAVAILABLE
    if cleaned.get('input_mode') in INPUT_MODE_UNAVAILABLE:
        raise WorkflowValidation({
            'input_mode': [
                'Bantuan AI belum tersedia pada rilis ini (dijadwalkan F9); '
                'pilih Manual atau Master.'
            ],
        })
    if workflow is None:
        workflow = IgdAssessmentWorkflow.objects.create(
            kunjungan=visit, origin_unit=visit.unit_kerja,
            service_line=RAJAL_JANTUNG_SERVICE_LINE, schema_key=RAJAL_JANTUNG_SCHEMA_KEY,
        )
    draft = dict(workflow.draft_payload or {})
    draft[str(step)] = {**draft.get(str(step), {}), **cleaned}
    workflow.draft_payload = draft
    workflow.version += 1
    workflow.last_step = step
    workflow.updated_by = user
    workflow.signatures = {}
    workflow.save(update_fields=['draft_payload', 'version', 'last_step', 'updated_by', 'updated_at', 'signatures'])
    if step == 2 and 'red_flag_kardio' in payload:
        # Kunci dikirim walau nilainya dikosongkan: ``StepField.clean`` membuang
        # nilai kosong dari ``cleaned``, sehingga memakai ``cleaned`` saja membuat
        # red flag tidak pernah bisa dicabut.
        _sync_red_flag(visit, cleaned.get('red_flag_kardio') or '')
    if step == 8 and cleaned.get('jadwal_kontrol'):
        # F5.6: menyimpan jarak kontrol menerbitkan e-SKDP dengan skema nomor
        # yang sudah dipakai dasbor rawat jalan (lihat pasien/services/skdp.py).
        from .skdp import apply_jadwal_kontrol
        apply_jadwal_kontrol(
            visit, cleaned['jadwal_kontrol'],
            diagnosa=cleaned.get('diagnosa_utama') or visit.diagnosa_masuk,
            terapi=cleaned.get('rencana_terapi') or '',
        )
    AuditLog.objects.create(user=user, aksi='UPDATE', model_name='IgdAssessmentWorkflow',
                            object_repr=f'Workflow #{workflow.pk}',
                            detail=f'Draft rajal langkah {step}; versi {workflow.version}; field: {", ".join(sorted(cleaned))}')
    return workflow

def _sync_red_flag(visit, code):
    """Turunkan kolom ``red_flag_*`` dari langkah 2.

    ``red_flag_at`` hanya diisi saat red flag pemicu door-to-ECG dipilih
    (matriks §7). Memilih ulang red flag pemicu pada episode yang sudah punya
    stempel **tidak** menggeser jam: door-to-ECG mengukur skrining pertama,
    bukan penyuntingan terakhir. Mengganti ke red flag non-pemicu menghapus
    stempel, karena tidak ada lagi indikator yang harus dihitung.
    """
    from pasien.workflow_schemas import RED_FLAG_DOOR_TO_ECG

    changed = []
    if visit.red_flag_kardio != code:
        visit.red_flag_kardio = code
        changed.append('red_flag_kardio')
    if code in RED_FLAG_DOOR_TO_ECG:
        if visit.red_flag_at is None:
            visit.red_flag_at = timezone.now()
            changed.append('red_flag_at')
    elif visit.red_flag_at is not None:
        visit.red_flag_at = None
        changed.append('red_flag_at')
    if changed:
        visit.save(update_fields=changed)


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
            from django.conf import settings
            if visit and visit.jenis_kunjungan=='IGD' and getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False) and view.__name__ in {'cppt_tambah','igd_cppt_quick_add','igd_eksekusi_tindakan'}:
                authorize_visit(visit,request.user,workflow=workflow)
                return JsonResponse({'success':False,'error':'Gunakan pelaksanaan dan CPPT profesional yang tervalidasi.'},status=409)
            if workflow:
                # F6.1 (ADR-3): pengecualian F1.9 sudah dicabut. Sejak CPPT
                # profesional tersedia untuk RAJAL_JANTUNG, penulis lama
                # (`cppt_tambah`, `rajal_soap_simpan`) ditutup 409 agar catatan
                # rajal tidak bercabang antara status LEGACY dan SIGNED.
                if workflow.service_line == RAJAL_JANTUNG_SERVICE_LINE and visit.jenis_kunjungan == 'RAJAL':
                    authorize_visit(visit, request.user, workflow=workflow)
                    if view.__name__ in ('cppt_tambah', 'rajal_soap_simpan'):
                        return JsonResponse({'success': False, 'error': 'CPPT POLI-JANTUNG wajib melalui jalur CPPT profesional (create/save/sign) yang tervalidasi.'}, status=409)
                    if view.__name__ in ('order_penunjang_buat', 'order_lab_create'):
                        return JsonResponse({'success': False, 'error': 'Order penunjang POLI-JANTUNG wajib melalui jalur penunjang berversi.'}, status=409)
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
