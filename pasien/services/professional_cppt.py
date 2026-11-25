"""Authored CPPT, immutable signed revisions and account-bound DPJP verification."""
from uuid import UUID
import base64,binascii,hashlib,re
from datetime import timedelta
from django.core.exceptions import ValidationError,PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from klinis.models import LayananProfesional
from pasien.models import CPPT, CpptRevision, PenugasanDpjpEpisode, VerifikasiCppt
from .igd_actions import digest
from .igd_assessment_workflow import RAJAL_JANTUNG_SERVICE_LINE, get_visit, WorkflowConflict
from sdm.services.professional_care import resolve_professional_context,require_scope,business_date

FIELDS={'SOAP':('subjektif','objektif','asesmen','plan'),'ADIME':('asesmen_gizi','diagnosis_gizi','intervensi','monitoring','evaluasi'),'SPIRITUAL':('kondisi_psikospiritual','pendampingan','respon_pasien')}

#: F6.3 (S9-L1-09/S9-L1-10): kunci SOAP tambahan. Bukan field wajib — ia
#: memperkaya S (keluhan terpilih, status kepatuhan, penandaan per obat) dan
#: disimpan di ``structured_content``, bukan kolom baru.
SOAP_EXTRA=('keluhan_chips','kepatuhan_terapi','kepatuhan_obat')
TTE_MAX_BYTES=512*1024
_TTE_RE=re.compile(r'^data:image/(png|jpeg);base64,([A-Za-z0-9+/=\s]+)$')
VERIFICATION_LABELS={'MENUNGGU':'Menunggu verifikasi','TEPAT':'Tepat waktu','TERLAMBAT':'Terlambat'}

def _extras(format_code,payload):
    """Validasi kunci SOAP tambahan; format lain tidak menerimanya.

    Kunci yang **tidak** dikirim tidak muncul di hasil. Ini penting untuk
    digest: catatan yang ditandatangani sebelum F6 tidak punya kunci ini, dan
    snapshot-nya harus tetap dapat dihitung ulang tanpa berubah.
    """
    from pasien.workflow_schemas import KELUHAN_CPPT_CHOICES, KEPATUHAN_TERAPI_CHOICES
    if format_code!='SOAP':
        return {}
    extras={}
    if 'keluhan_chips' in payload:
        chips=payload['keluhan_chips']
        if (not isinstance(chips,list) or len(set(chips))!=len(chips)
                or any(not isinstance(code,str) or code not in KELUHAN_CPPT_CHOICES for code in chips)):
            raise ValidationError('Pilihan keluhan CPPT tidak valid.')
        extras['keluhan_chips']=chips
    if 'kepatuhan_terapi' in payload:
        status=payload['kepatuhan_terapi']
        if status not in ('',)+KEPATUHAN_TERAPI_CHOICES:
            raise ValidationError('Status kepatuhan terapi tidak valid.')
        extras['kepatuhan_terapi']=status
    if 'kepatuhan_obat' in payload:
        drugs=payload['kepatuhan_obat']
        if not isinstance(drugs,dict) or len(drugs)>200:
            raise ValidationError('Penandaan kepatuhan obat tidak valid.')
        clean={}
        for key,row in drugs.items():
            if (not str(key).isdigit() or not isinstance(row,dict) or set(row)-{'status','catatan'}):
                raise ValidationError('Penandaan kepatuhan obat tidak valid.')
            note=row.get('catatan','')
            if row.get('status') not in KEPATUHAN_TERAPI_CHOICES or not isinstance(note,str) or len(note)>300:
                raise ValidationError('Penandaan kepatuhan obat tidak valid.')
            clean[str(key)]={'status':row['status'],'catatan':note}
        extras['kepatuhan_obat']=clean
    return extras

def _tte_hash(image):
    """SHA-256 byte gambar TTE; menolak selain PNG/JPEG kanvas (F6.4)."""
    match=_TTE_RE.match(image.strip()) if isinstance(image,str) else None
    if not match:
        raise ValidationError('TTE memerlukan gambar tanda tangan PNG/JPEG dari kanvas.')
    try:
        raw=base64.b64decode(''.join(match.group(2).split()),validate=True)
    except (binascii.Error,ValueError):
        raise ValidationError('Gambar TTE tidak dapat dibaca.') from None
    magic=(raw.startswith(b'\x89PNG\r\n\x1a\n') if match.group(1)=='png'
           else raw.startswith(b'\xff\xd8\xff'))
    if not raw or not magic or len(raw)>TTE_MAX_BYTES:
        raise ValidationError('Gambar TTE harus PNG/JPEG kanvas maksimal 512 KB.')
    return hashlib.sha256(raw).hexdigest()

def verification_state_at(due,performed_at=None,*,now=None):
    """Bandingkan ``verifikasi_due_at`` dengan waktu verifikasi (F6.5).

    ``None`` berarti tidak ada batas (catatan lama tanpa TTE/due). Tanpa
    ``performed_at`` hasilnya MENUNGGU atau TERLAMBAT menurut jam sekarang.
    """
    if not due:
        return None
    if performed_at is None:
        return 'MENUNGGU' if (now or timezone.now())<=due else 'TERLAMBAT'
    return 'TEPAT' if performed_at<=due else 'TERLAMBAT'

def verification_state(note,verification=None):
    """F6.5: status kepatuhan verifikasi DPJP — dihitung, tidak disimpan.

    ``verifikasi_due_at`` diisi saat tanda tangan (waktu sign + 24 jam). Status
    lahir dari perbandingan kolom itu dengan ``VerifikasiCppt.performed_at``,
    sehingga tidak ada kolom status yang dapat menyimpang dari kenyataan.
    """
    return verification_state_at(note.verifikasi_due_at,verification.performed_at if verification else None)


def validate_note(format_code,payload):
    fields=FIELDS.get(format_code)
    allowed=set(fields or ())|{'unavailable_reasons'}|(set(SOAP_EXTRA) if format_code=='SOAP' else set())
    if not fields or not isinstance(payload,dict) or set(payload)-allowed:
        raise ValidationError('Format/field CPPT tidak valid.')
    result={}
    for field in fields:
        value=payload.get(field,'')
        if not isinstance(value,str) or len(value)>10000:raise ValidationError('Isi CPPT harus teks maksimal 10000 karakter.')
        result[field]=value
    reasons=payload.get('unavailable_reasons',{})
    if not isinstance(reasons,dict) or set(reasons)-set(fields) or any(not isinstance(v,str) or not v.strip() or len(v)>1000 for v in reasons.values()):
        raise ValidationError('Alasan tidak tercatat tidak valid.')
    result['unavailable_reasons']=reasons
    result.update(_extras(format_code,payload))
    return result


def _complete(note,payload):
    reasons=payload.get('unavailable_reasons',{})
    for field in FIELDS[note.format_code]:
        if not payload.get(field,'').strip() and not reasons.get(field,'').strip():
            raise ValidationError(f'{field}: isi atau alasan tidak tercatat wajib ditinjau.')
    if note.format_code=='SOAP' and not all(payload.get(f,'').strip() for f in ('asesmen','plan')):
        raise ValidationError('A/P SOAP wajib diisi penulis.')


def _writable(visit,workflow):
    """F6.1/ADR-3: IGD seperti sebelumnya; RAJAL hanya pada episode POLI-JANTUNG.

    Pelonggaran ini **tidak** membuka rawat jalan biasa: episode RAJAL wajib
    membawa workflow ``service_line='RAJAL_JANTUNG'``. Episode yang sudah
    ditutup atau final tetap ditolak untuk semua jalur.
    """
    if visit.status in {'PULANG','RUJUK','MENINGGAL','BATAL'} or workflow and workflow.status=='FINAL':
        raise WorkflowConflict('Episode tertutup/final hanya dapat dibaca; gunakan jalur addendum.')
    if visit.jenis_kunjungan=='IGD':
        return
    if visit.jenis_kunjungan=='RAJAL' and workflow is not None and workflow.service_line==RAJAL_JANTUNG_SERVICE_LINE:
        return
    raise WorkflowConflict('CPPT profesional rawat jalan memerlukan episode POLI-JANTUNG ber-workflow RAJAL_JANTUNG.')


def _content(note):
    source={k:getattr(note,k) for k in FIELDS['SOAP']} if note.format_code=='SOAP' else {k:note.structured_content.get(k,'') for k in FIELDS[note.format_code]}
    if note.format_code=='SOAP':
        for key in SOAP_EXTRA:
            if key in note.structured_content:source[key]=note.structured_content[key]
    source['unavailable_reasons']=note.structured_content.get('unavailable_reasons',{})
    return validate_note(note.format_code,source)


def _store(note,payload):
    event=note.structured_content.get('event_log')
    extras={key:payload[key] for key in SOAP_EXTRA if key in payload}
    if note.format_code=='SOAP':
        for field in FIELDS['SOAP']:setattr(note,field,payload[field])
        note.structured_content={'unavailable_reasons':payload['unavailable_reasons'],**extras}
    else:note.structured_content=payload
    if event:note.structured_content['event_log']=event


def note_snapshot(note):
    snapshot={'id':note.pk,'format_code':note.format_code,'content':_content(note),'event_log':note.structured_content.get('event_log'),
              'professional_snapshot':note.professional_snapshot,'author_id':note.created_by_id,'recorded_by_id':note.recorded_by_id,
              'actual_at':note.tanggal.isoformat(),'recorded_at':note.created_at.isoformat(),'version':note.version,'status':note.status}
    # F6.4/F6.5 hanya menambah kunci bila nilainya ada. Revisi yang
    # ditandatangani sebelum F6 tidak punya nilai ini, sehingga digest lamanya
    # tetap dapat dihitung ulang apa adanya — verifikasi catatan lama tidak
    # mendadak gagal karena bentuk snapshot berubah.
    if note.ttd_hash:
        snapshot['ttd_hash']=note.ttd_hash
    if note.verifikasi_due_at:
        snapshot['verifikasi_due_at']=note.verifikasi_due_at.isoformat()
    return snapshot


def _lock_note(actor,note_id,expected_version):
    reference=CPPT.objects.get(pk=note_id)
    visit,workflow=get_visit(reference.kunjungan_id,actor,lock=True)
    _writable(visit,workflow)
    note=CPPT.objects.get(pk=note_id,kunjungan=visit)
    if note.status=='LEGACY':raise ValidationError('Catatan historis memerlukan adopsi yang ditinjau, bukan tanda tangan retrospektif.')
    if note.created_by_id!=actor.pk:raise PermissionDenied('Hanya penulis dapat mengubah/menandatangani catatannya.')
    service=LayananProfesional.objects.get(pk=note.professional_snapshot['service_id'])
    resolve_professional_context(actor,visit,service,at=timezone.now(),supervisor=(note.professional_snapshot.get('supervisor') or {}).get('performer_id'),for_update=True)
    note=CPPT.objects.select_for_update().get(pk=note_id,kunjungan=visit)
    if note.version!=int(expected_version):raise WorkflowConflict('Versi CPPT berubah.')
    return note


@transaction.atomic
def create_care_note(visit,workflow,actor,*,format_code,payload,context,source_action=None):
    _writable(visit,workflow)
    service=LayananProfesional.objects.get(pk=context['service_id'])
    current=resolve_professional_context(actor,visit,service,at=source_action.performed_at if source_action else timezone.now(),performer=context['performer_id'],supervisor=(context.get('supervisor') or {}).get('performer_id'),for_update=True)
    required='ADIME' if current['profession_code'] in {'DIET','NUTR'} else 'SPIRITUAL' if service.authority_kind=='SUPPORT' else service.note_format
    if format_code!=required:raise ValidationError('Format tidak sesuai layanan/profesi yang ditinjau.')
    values=validate_note(format_code,payload)
    if not source_action and not any(values.get(field,'').strip() for field in FIELDS[format_code]):
        raise ValidationError('Draft mandiri harus memiliki isi.')
    if source_action:
        if source_action.kunjungan_id!=visit.pk:raise PermissionDenied('Sumber tindakan berbeda episode.')
        existing=CPPT.objects.filter(source_action=source_action).first()
        if existing:return existing
    profile=current['profile_profession']
    profession={'DOKTER_UMUM':'DOKTER','DOKTER_SPESIALIS':'DOKTER','DOKTER_GIGI':'DOKTER','PERAWAT':'PERAWAT','BIDAN':'BIDAN','APOTEKER':'FARMASI','TTK':'FARMASI','NUTRISIONIS':'GIZI','FISIOTERAPIS':'REHAB'}.get(profile,'LAINNYA')
    note=CPPT(kunjungan=visit,profesi=profession,nama_ppa=current['performer_name'],tanggal=source_action.performed_at if source_action else timezone.now(),created_by_id=current['performer_account_id'],recorded_by=actor,source_action=source_action,status='DRAFT',format_code=format_code,professional_snapshot=current,verifikasi_dpjp=False)
    _store(note,values)
    if source_action:note.structured_content['event_log']=f'{source_action.nama}; kuantitas {source_action.quantity}; waktu aktual {source_action.performed_at.isoformat()}; pelaksana {current["performer_name"]}.'
    note.save()
    return note


@transaction.atomic
def save_care_note(actor,note_id,expected_version,payload):
    note=_lock_note(actor,note_id,expected_version)
    if note.status!='DRAFT':raise WorkflowConflict('Catatan bertanda tangan memerlukan koreksi beralasan.')
    values=validate_note(note.format_code,payload)
    if not any(values.get(field,'').strip() for field in FIELDS[note.format_code]):raise ValidationError('Isi draft tidak boleh kosong.')
    _store(note,values);note.version+=1;note.save(professional_update=True)
    return {'cppt_id':note.pk,'note_version':note.version}


def _revision(note,actor,reason=''):
    snapshot=note_snapshot(note)
    return CpptRevision.objects.create(note=note,version=note.version,snapshot=snapshot,digest=digest(snapshot),author=actor,reason=reason)


@transaction.atomic
def sign_care_note(actor,note_id,expected_version,*,ttd_image='',credential_confirmed=False):
    """Tandatangani catatan; episode RAJAL wajib TTE kanvas + konfirmasi kredensial.

    F6.4 (S9-L1-05/S9-L1-08): tanda tangan bukan PIN dan bukan biometrik — ia
    goresan kanvas (disimpan sebagai data URL) ditambah konfirmasi kredensial
    penanda tangan. Kredensial itu sendiri sudah diperiksa ulang oleh
    ``_lock_note`` lewat ``resolve_professional_context``. F6.5: waktu tanda
    tangan + 24 jam menjadi ``verifikasi_due_at``.
    """
    note=_lock_note(actor,note_id,expected_version)
    if note.status!='DRAFT':raise WorkflowConflict('Catatan sudah ditandatangani.')
    _complete(note,_content(note))
    rajal=note.kunjungan.jenis_kunjungan=='RAJAL'
    if rajal and credential_confirmed is not True:
        raise ValidationError('Konfirmasi kredensial penanda tangan wajib sebelum tanda tangan elektronik.')
    ttd_hash=_tte_hash(ttd_image) if rajal or ttd_image else ''
    now=timezone.now()
    note.status='SIGNED';note.ttd_image=(ttd_image or '').strip() if ttd_hash else '';note.ttd_hash=ttd_hash
    note.verifikasi_due_at=now+timedelta(hours=24)
    note.version+=1;note.save(professional_update=True)
    revision=_revision(note,actor)
    return {'cppt_id':note.pk,'note_version':note.version,'revision_id':revision.pk,'ttd_hash':note.ttd_hash,
            'verifikasi_due_at':note.verifikasi_due_at.isoformat()}


@transaction.atomic
def correct_care_note(actor,note_id,expected_version,payload,reason):
    note=_lock_note(actor,note_id,expected_version)
    if note.status!='SIGNED' or not isinstance(reason,str) or len(reason.strip())<5 or len(reason)>2000:raise ValidationError('Koreksi memerlukan catatan bertanda tangan dan alasan.')
    values=validate_note(note.format_code,payload);_complete(note,values)
    _store(note,values);note.version+=1;note.verifikasi_dpjp=False;note.save(professional_update=True)
    revision=_revision(note,actor,reason)
    return {'cppt_id':note.pk,'note_version':note.version,'revision_id':revision.pk}


def verification_authority(actor,visit,note):
    from sdm.models import Pegawai,PrivilegeSnapshot,PenugasanKlinis,PengajuanKredensial
    require_scope(actor,visit)
    day=business_date(timezone.now())
    if actor.profile.profesi not in {'DOKTER_UMUM','DOKTER_SPESIALIS','DOKTER_GIGI'}:raise PermissionDenied('Verifikasi DPJP memerlukan dokter.')
    employees=list(Pegawai.objects.select_for_update().filter(akun=actor,status='AKTIF',data_origin__in=['MANUAL','VERIFIED_IMPORT'],profesi_master__keluarga='MEDIS',profesi_master__is_active=True))
    if len(employees)!=1 or not employees[0].jenjang_master_id or employees[0].jenjang_master.profesi_id!=employees[0].profesi_master_id:raise PermissionDenied('Dokter belum terhubung ke HC terverifikasi.')
    if employees[0].kategori!='PPA' or not employees[0].profesi_master.reviewed_at or not employees[0].profesi_master.reviewed_by_id:raise PermissionDenied('Profesi dokter belum ditinjau.')
    sources=list(PenugasanKlinis.objects.select_for_update(of=('self',)).filter(employee=employees[0],unit_kerja_id=visit.unit_kerja_id,is_active=True,berlaku_mulai__lte=day,decision__outcome='DISETUJUI').filter(Q(berlaku_sampai__isnull=True)|Q(berlaku_sampai__gte=day)))
    source_ids=[]
    for source in sources:
        application=PengajuanKredensial.objects.select_for_update().get(pk=source.decision.pengajuan_id)
        if application.status=='DISETUJUI' and application.employee_id==employees[0].pk and application.unit_kerja_id==visit.unit_kerja_id:source_ids.append(source.pk)
    grants=PrivilegeSnapshot.objects.select_for_update(of=('self',)).filter(pegawai=employees[0],unit_kerja_id=visit.unit_kerja_id,revoked_at__isnull=True,action_code__code='verify_cppt',action_code__is_active=True,valid_from__lte=day,source_decision__is_active=True,source_decision__employee=employees[0],source_decision__unit_kerja_id=visit.unit_kerja_id,source_decision__berlaku_mulai__lte=day,source_decision__decision__outcome='DISETUJUI',source_decision__decision__pengajuan__status='DISETUJUI',source_decision__decision__pengajuan__employee=employees[0],source_decision__decision__pengajuan__unit_kerja_id=visit.unit_kerja_id).filter(Q(valid_until__isnull=True)|Q(valid_until__gte=day)).filter(Q(source_decision__berlaku_sampai__isnull=True)|Q(source_decision__berlaku_sampai__gte=day))
    if not list(grants.filter(source_decision_id__in=source_ids)[:2]):raise PermissionDenied('Mandat verifikasi CPPT tidak berlaku.')
    assignments=list(PenugasanDpjpEpisode.objects.select_for_update().filter(visit=visit,unit_id=visit.unit_kerja_id,doctor=actor,is_active=True,valid_from__lte=day,valid_until__gte=day).exclude(assigned_by=actor).exclude(source_version='')[:2])
    if len(assignments)!=1:raise PermissionDenied('Penugasan DPJP tidak tersedia atau ambigu.')
    return assignments[0]


@transaction.atomic
def verify_cppt(actor,note_id,expected_version,request_id):
    reference=CPPT.objects.get(pk=note_id)
    visit,workflow=get_visit(reference.kunjungan_id,actor,lock=True);_writable(visit,workflow)
    if visit.jenis_kunjungan=='RAJAL':
        # F6.5: matriks RBAC yang dideklarasikan (``VERIFY_ROLES`` langkah 9 =
        # DPJP saja) kini benar-benar ditegakkan di jalur verifikasi, bukan
        # hanya dideklarasikan. Jalur IGD tidak melewati matriks ini agar
        # perilakunya tidak bergeser.
        from .poli_rbac import authorize_step
        authorize_step(actor,visit,9,'verify')
    assignment=verification_authority(actor,visit,reference)
    note=CPPT.objects.select_for_update().get(pk=note_id,kunjungan=visit)
    if note.status!='SIGNED' or note.version!=int(expected_version):raise WorkflowConflict('Catatan belum ditandatangani atau versinya berubah.')
    revision=note.care_revisions.get(version=note.version)
    if digest(revision.snapshot)!=revision.digest or digest(note_snapshot(note))!=revision.digest:raise WorkflowConflict('Isi catatan tidak sesuai revisi bertanda tangan.')
    key=UUID(str(request_id))
    existing=VerifikasiCppt.objects.filter(Q(request_id=key)|Q(revision=revision)).first()
    if existing:
        if existing.verifier_id!=actor.pk or existing.revision_id!=revision.pk:raise WorkflowConflict('Identitas/permintaan verifikasi berbeda.')
        return {'verification_id':existing.pk,'cppt_id':note.pk,'note_version':note.version}
    assignment_snapshot={key:getattr(assignment,key) for key in ('doctor_id','unit_id','assignment_type','source_version','assigned_by_id')}
    assignment_snapshot.update(valid_from=assignment.valid_from.isoformat(),valid_until=assignment.valid_until.isoformat(),assigned_at=assignment.assigned_at.isoformat())
    verification=VerifikasiCppt.objects.create(revision=revision,verifier=actor,verifier_name=actor.get_full_name() or actor.username,assignment=assignment,assignment_snapshot=assignment_snapshot,digest=revision.digest,request_id=key)
    note.verifikasi_dpjp=True;note.save(professional_update=True,update_fields=['verifikasi_dpjp'])
    return {'verification_id':verification.pk,'cppt_id':note.pk,'note_version':note.version}
