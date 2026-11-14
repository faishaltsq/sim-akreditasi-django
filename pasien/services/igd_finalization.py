"""Tanda tangan, disposisi dan revisi append-only episode IGD."""
import copy
import json
from django.core.exceptions import PermissionDenied
from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.forms_igd_workflow import STEPS
from pasien.forms_igd_operations import SignatureForm, FinalizationForm, AddendumForm
from pasien.models import Bed, IgdAssessmentRevision, DischargeRecord, POLIKLINIK_CHOICES
from .igd_actions import validate, digest, require_doctor, DOCTORS, NURSES
from .igd_assessment_workflow import WorkflowConflict, WorkflowValidation

EXEMPTIONS = {'triage','anamnesis','primary_survey','initial_vitals','screening','physical_exam','diagnosis','nursing','investigations','care','evaluation'}


def clinical_snapshot(visit, workflow):
    fields = sorted({name for _, names in STEPS.values() for name in names})
    patient = {key:getattr(visit.pasien,key) for key in ('no_rm','nama_lengkap','tanggal_lahir','jenis_kelamin')}
    snapshot = {
        'schema_version':2, 'patient':patient,
        'visit':{name:getattr(visit,name) for name in fields},
        'no_kunjungan':visit.no_kunjungan, 'origin_unit_id':workflow.origin_unit_id,
        'diagnosis_provenance':visit.diagnosis_provenance, 'exemptions':workflow.exemptions,
        'diagnoses':list(visit.diagnoses.order_by('pk').values('id','kode','nama','mode','active','is_primary','provenance','updated_by_id','created_at','updated_at')),
        'observations':list(workflow.observations.order_by('pk').values('id','phase','observed_at','recorded_by_id','data','corrects_id')),
        'orders':list(visit.order_penunjang.order_by('pk').values('id','jenis','nama_pemeriksaan','prioritas','status','hasil_pemeriksaan','is_critical_value','critical_value_catatan','catalogue_snapshot','preparation','ordered_by_id','created_at','catatan_klinis','dokter_pengirim','destination_id','result_recorded_by_id','result_recorded_at','batch_id')),
        'cppt':list(visit.cppt.order_by('pk').values('id','profesi','nama_ppa','tanggal','subjektif','objektif','asesmen','plan','created_by_id','verifikasi_dpjp')),
        'actions':list(visit.tindakan_asesmen.order_by('pk').values('id','jenis','kode','nama','execution_status','execution_team','performed_by_id','performed_at','quantity','tarif_acuan','tarif','catatan_tarif','billing_item_id','standard_item_id','ep_status','ep_catatan','lokasi_anatomis','catatan_klinis','recorded_at','assistance_provenance')),
        'prescriptions':[{'id':rx.pk,'no_resep':rx.no_resep,'doctor_id':rx.dokter_peresep_id,'items':list(rx.items.order_by('pk').values('nama_obat','aturan_pakai','product_snapshot','regimen','quantity_decimal','reference_price','quantity_reason','kind'))} for rx in visit.resep_list.order_by('pk')],
        'attachments':list(visit.lampiran_asesmen.order_by('pk').values('id','jenis','nama_asli','file','diunggah_pada','diunggah_oleh_id')),
    }
    if getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False) or visit.cppt.exclude(status='LEGACY').exists():
        from .professional_presentation import snapshot_professional_care
        snapshot['professional_care']=snapshot_professional_care(visit)
    return json.loads(json.dumps(snapshot, cls=DjangoJSONEncoder))


def sign(visit, workflow, user, data):
    values = validate(SignatureForm, data)
    section = values['section']
    if section == 'MEDIS':
        require_doctor(user)
    elif user.profile.profesi not in NURSES:
        raise PermissionDenied('Tanda tangan keperawatan hanya untuk perawat/bidan.')
    exemptions = values['exemptions']
    if exemptions is not None:
        if not isinstance(exemptions,dict) or set(exemptions) - EXEMPTIONS or any(not isinstance(v,str) or not 5 <= len(v.strip()) <= 2000 for v in exemptions.values()):
            raise WorkflowValidation({'exemptions':['Gunakan objek alasan minimal lima karakter per bagian yang tidak dapat dinilai.']})
        if section != 'MEDIS' and exemptions != workflow.exemptions:
            raise PermissionDenied('Perubahan pengecualian episode memerlukan dokter.')
        if workflow.exemptions != exemptions:
            workflow.exemptions = exemptions
            workflow.signatures = {}
    signature = {'user_id':user.pk, 'name':user.get_full_name() or user.username,
                 'profession':user.profile.profesi, 'signed_at':timezone.now().isoformat(),
                 'content_digest':digest(clinical_snapshot(visit,workflow))}
    workflow.signatures = {**workflow.signatures, section:signature}
    return {'signed_section':section}


def missing_sections(visit, workflow):
    from pasien.physical_exam import exam_present
    def measured(phase):
        observation = workflow.observations.filter(phase=phase).order_by('-observed_at','-pk').first()
        return bool(observation and any(value is not None and value != '' for value in observation.data.values()))
    checks = {
        'triage': bool(visit.triase_skala and (visit.triase_kategori or visit.triage)),
        'anamnesis': bool(visit.anamnesis_rps.strip()),
        'primary_survey': bool(visit.fisik_airway.strip()),
        'initial_vitals': measured('INITIAL'),
        'screening': bool(visit.skrining_alergi_status not in ('','BELUM') and visit.skrining_gizi_mst is not None and visit.skrining_jatuh_skor is not None),
        'physical_exam': exam_present(visit.fisik_head_to_toe,visit.secondary_survey_detail,visit.fisik_lokalis),
        'diagnosis': bool(visit.diagnosa_masuk.strip()),
        'nursing': bool(visit.diagnosa_keperawatan_sdki.strip() and visit.luaran_keperawatan_slki.strip() and visit.intervensi_keperawatan_siki.strip()),
        'investigations':visit.order_penunjang.exists(),
        'care':visit.cppt.filter(status='SIGNED').exists() if getattr(settings,'IGD_PROFESSIONAL_CARE_ENABLED',False) else visit.cppt.exists(),
        'evaluation':bool(visit.disposisi_kondisi_akhir and visit.evaluasi_respon_terapi.strip() and measured('EVALUATION')),
    }
    return [name for name,present in checks.items() if not present and name not in workflow.exemptions]


def _release_bed(visit):
    if visit.bed_id:
        bed = Bed.objects.select_for_update().get(pk=visit.bed_id)
        bed.status = 'STERILISASI'
        bed.save(update_fields=['status'])
        visit.bed = None


def apply_disposition(visit, user, values):
    outcome = values['outcome']
    now = timezone.now()
    if outcome == 'NONE':
        return
    expected = {'PULANG':'RAWAT_JALAN','PAPS':'PAPS','RANAP':'RAWAT_INAP','RUJUK':'RUJUK','CONSULT':'KONSUL','TRANSFER':'TRANSFER','MENINGGAL':'MENINGGAL'}[outcome]
    if visit.disposisi_tindak_lanjut != expected:
        raise WorkflowValidation({'outcome':['Simpan rencana disposisi yang sesuai pada langkah 11 sebelum finalisasi.']})
    if outcome in ('PULANG','PAPS'):
        if outcome == 'PAPS' and not (values['paps_alasan'] and values['paps_nama_penolak']):
            raise WorkflowValidation({'paps_alasan':['Alasan dan nama penolak wajib untuk PAPS.']})
        visit.discharge_patient(kondisi='APS' if outcome == 'PAPS' else 'MEMBAIK', resume=values['resume'],
                                user=user, edukasi=values['edukasi'], obat=values['obat'], kontrol=values['kontrol'])
        record = visit.discharge
        record.status_clearance = 'PROSES'
        record.paps_alasan, record.paps_nama_penolak = values['paps_alasan'], values['paps_nama_penolak']
        record.save()
    elif outcome == 'RANAP':
        bed = Bed.objects.select_for_update().select_related('ruangan').filter(pk=values['bed_id']).first()
        if bed is None or bed.status != 'TERSEDIA' or not bed.ruangan.unit_kerja_id or not values['dpjp']:
            raise WorkflowValidation({'bed_id':['Pilih bed tersedia dengan unit tujuan dan DPJP yang jelas.']})
        visit.admit_to_ranap(bed, dpjp=values['dpjp'])
        visit.unit_kerja_id = bed.ruangan.unit_kerja_id
    elif outcome in ('CONSULT','TRANSFER'):
        poli = visit.disposisi_kontrol_poli
        if poli not in dict(POLIKLINIK_CHOICES):
            raise WorkflowValidation({'disposisi_kontrol_poli':['Pilih poli tujuan yang valid.']})
        visit.konsul_ke_poli = poli
        visit.konsul_catatan = values['resume']
        if outcome == 'TRANSFER':
            from akreditasi.layanan_unit import POLI_UNIT_CODE
            from pasien.services.antrean import allocate_queue_number
            unit = UnitKerja.objects.filter(code=POLI_UNIT_CODE.get(poli)).first()
            if unit is None:
                raise WorkflowValidation({'disposisi_kontrol_poli':['Unit poli tujuan belum dikonfigurasi.']})
            visit.jenis_kunjungan, visit.status, visit.poliklinik = 'RAJAL','DAFTAR',poli
            visit.unit_kerja = unit
            visit.nomor_antrean = allocate_queue_number('RAJAL', poli)
            visit.status_antrean = 'MENUNGGU'
        else:
            visit.status = 'DISPOSISI'
    else:
        if outcome == 'RUJUK':
            if not visit.disposisi_rujuk_rs.strip() or not visit.disposisi_rujuk_alasan.strip():
                raise WorkflowValidation({'disposisi_rujuk_rs':['RS dan alasan rujukan wajib.']})
            visit.status = 'RUJUK'
            visit.sisrute_rs_tujuan, visit.sisrute_alasan = visit.disposisi_rujuk_rs, visit.disposisi_rujuk_alasan
        else:
            if not visit.waktu_kematian or visit.waktu_kematian > now or not visit.penyebab_kematian.strip():
                raise WorkflowValidation({'waktu_kematian':['Waktu kematian yang valid dan keterangan penyebab wajib diisi.']})
            visit.status = 'MENINGGAL'
        _release_bed(visit)
        visit.tanggal_keluar = visit.waktu_kematian if outcome == 'MENINGGAL' else now
        DischargeRecord.objects.create(kunjungan=visit, tanggal_discharge=visit.tanggal_keluar,
            kondisi_pulang='MENINGGAL' if outcome == 'MENINGGAL' else 'RUJUK', resume_medis=values['resume'],
            status_clearance='PROSES', dibuat_oleh=user,
            total_tagihan=sum((b.subtotal for b in visit.billing.all()),0))
    if outcome not in ('TRANSFER','CONSULT'):
        visit.status_antrean = 'SELESAI'
    visit.save()


def finalize(visit, workflow, user, data):
    require_doctor(user)
    values = validate(FinalizationForm,data)
    snapshot = clinical_snapshot(visit,workflow)
    fingerprint = digest(snapshot)
    errors = missing_sections(visit,workflow)
    for section in ('MEDIS', 'KEPERAWATAN') if visit.diagnosa_keperawatan_sdki.strip() else ('MEDIS',):
        signature = workflow.signatures.get(section,{})
        if signature.get('content_digest') != fingerprint:
            errors.append(f'Tanda tangan {section} untuk data terkini')
    if errors:
        raise WorkflowValidation({'finalisasi':errors})
    # Capture signed clinical content before administrative transfer changes ownership.
    apply_disposition(visit,user,values)
    snapshot['signatures'] = copy.deepcopy(workflow.signatures)
    snapshot['disposition'] = {**values,'status_after':visit.status,'service_after':visit.jenis_kunjungan,
                               'bed_after':visit.bed_id,'finalized_by':user.pk,'finalized_at':timezone.now().isoformat()}
    revision = IgdAssessmentRevision.objects.create(workflow=workflow, revision=1, snapshot=snapshot, signed_by=user)
    workflow.status, workflow.finalized_by, workflow.finalized_at, workflow.last_step = 'FINAL',user,timezone.now(),11
    return {'revision_id':revision.pk,'outcome':values['outcome']}


def addendum(visit, workflow, user, data):
    values = validate(AddendumForm,data)
    if workflow.status != 'FINAL':
        raise WorkflowConflict('Addendum hanya untuk dokumentasi final.')
    if values['section'] == 'MEDIS':
        require_doctor(user)
    elif user.profile.profesi not in NURSES:
        raise PermissionDenied('Addendum keperawatan memerlukan perawat/bidan.')
    previous = workflow.revisions.order_by('-revision').first()
    if previous is None:
        raise WorkflowConflict('Snapshot final tidak ditemukan.')
    snapshot = copy.deepcopy(previous.snapshot)
    snapshot.setdefault('addenda',[]).append({**values,'author_id':user.pk,'author':user.get_full_name() or user.username,
        'profession':user.profile.profesi,'signed_at':timezone.now().isoformat()})
    revision = IgdAssessmentRevision.objects.create(workflow=workflow,revision=previous.revision+1,
        snapshot=snapshot,reason=values['reason'],signed_by=user)
    return {'revision_id':revision.pk}
