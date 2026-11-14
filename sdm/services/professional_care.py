"""Purpose-scoped clinical adapter. No HR directory permission or role-derived privilege."""
from datetime import date
from zoneinfo import ZoneInfo
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import Q
from django.utils import timezone
from klinis.models import ProfessionalCareGrant, LayananProfesional, PemetaanKewenanganLayanan
from sdm.models import Pegawai, PenugasanKlinis, RincianKewenangan, PrivilegeSnapshot, KatalogTindakan, PengajuanKredensial


def business_date(at):
    if isinstance(at,date) and not hasattr(at,'hour'):return at
    if not at or timezone.is_naive(at):raise ValidationError('Waktu wajib menyertakan zona waktu.')
    return at.astimezone(ZoneInfo('Asia/Jakarta')).date()


def locked(qs, for_update):
    if for_update:
        if not connection.in_atomic_block:raise ValidationError('Penguncian memerlukan transaksi.')
        return qs.select_for_update(of=('self',))
    return qs


def require_scope(actor,visit):
    from pasien.services.igd_assessment_workflow import authorize_visit
    if not actor.is_active or actor.profile.role=='ASESOR':raise PermissionDenied('Akun tidak berwenang.')
    authorize_visit(visit,actor)


def has_grant(actor,visit,capability,*,at,service=None,for_update=False):
    day=business_date(at)
    qs=ProfessionalCareGrant.objects.filter(user=actor,unit_id=visit.unit_kerja_id,capability=capability,is_active=True,valid_from__lte=day,valid_until__gte=day,reviewed_by__isnull=False,reviewed_at__isnull=False).exclude(source_version='').exclude(reviewed_by=actor)
    qs=qs.filter(service=service) if capability=='SUPPORT_SERVICE' else qs.filter(Q(service__isnull=True)|Q(service=service))
    return bool(list(locked(qs,for_update)[:2]))


def _employee_context(actor,visit,service,employee_id,at,for_update):
    day=business_date(at)
    qs=Pegawai.objects.filter(status='AKTIF',akun__is_active=True,data_origin__in=['MANUAL','VERIFIED_IMPORT'])
    qs=qs.filter(pk=employee_id) if employee_id else qs.filter(akun=actor)
    employees=list(locked(qs,for_update)[:2])
    if len(employees)!=1:raise PermissionDenied('Pegawai terverifikasi tidak tersedia.')
    employee=employees[0]
    profession,grade=employee.profesi_master,employee.jenjang_master
    if not profession or not profession.is_active or not profession.reviewed_at or not profession.reviewed_by_id or not grade or grade.profesi_id!=profession.pk:
        raise PermissionDenied('Profesi/jenjang belum dikonfigurasi atau tidak sesuai.')
    profile=employee.akun.profile
    expected={'MEDIS':{'DOKTER_UMUM','DOKTER_SPESIALIS','DOKTER_GIGI'},'KEPERAWATAN_KEBIDANAN':{'PERAWAT','BIDAN'}}.get(profession.keluarga)
    if expected is None:
        expected={ 'DIET':'NUTRISIONIS','NUTR':'NUTRISIONIS','APOTEKER':'APOTEKER','TTK':'TTK','ATLM':'ANALIS_LAB','RADG':'RADIOGRAFER','FISIO':'FISIOTERAPIS','PMIK':'PEREKAM_MEDIS' }
        expected={expected.get(profession.code,'LAINNYA')}
    if profile.profesi not in expected or profile.role=='ASESOR':raise PermissionDenied('Profesi akun tidak sesuai sumber HC.')
    context={'actor_id':actor.pk,'performer_id':str(employee.pk),'performer_account_id':employee.akun_id,'performer_name':employee.nama_lengkap,
             'profession_id':profession.pk,'profession_code':profession.code,'profession_name':profession.nama,'profession_family':profession.keluarga,
             'profile_profession':profile.profesi,'grade_id':str(grade.pk),'grade_name':grade.nama,'unit_id':visit.unit_kerja_id,
             'service_id':service.pk,'service_code':service.code,'service_name':service.name,'group':{'MEDIS':'MEDICAL','KEPERAWATAN_KEBIDANAN':'NURSING'}.get(profession.keluarga,'OTHER_PPA'),'note_format':service.note_format,
             'source_version':service.source_version,'business_date':day.isoformat()}
    if service.authority_kind=='SUPPORT':
        if profession.keluarga!='NON_KLINIS' or service.note_format!='SPIRITUAL' or not has_grant(employee.akun,visit,'SUPPORT_SERVICE',at=at,service=service,for_update=for_update):
            raise PermissionDenied('Penugasan/kompetensi layanan support belum disetujui.')
        return {**context,'spk_id':None,'privilege_id':None,'supervision':'SUPPORT'}
    if employee.kategori!='PPA' or profession.keluarga=='NON_KLINIS':raise PermissionDenied('Layanan klinis memerlukan PPA.')
    mappings=list(locked(PemetaanKewenanganLayanan.objects.filter(service=service,is_active=True,reviewed_by__isnull=False,reviewed_at__isnull=False,catalog_item__jenjang=grade,catalog_item__is_active=True).exclude(source_version=''),for_update))
    if len(mappings)!=1:raise PermissionDenied('Pemetaan kewenangan belum ada atau ambigu.')
    catalogue=locked(KatalogTindakan.objects.filter(pk=mappings[0].catalog_item_id),for_update).get()
    if catalogue.tingkat_supervisi=='T':raise PermissionDenied('Tindakan tidak diberikan katalog.')
    assignments=list(locked(PenugasanKlinis.objects.filter(employee=employee,unit_kerja_id=visit.unit_kerja_id,is_active=True,berlaku_mulai__lte=day,decision__outcome='DISETUJUI',decision__pengajuan__employee=employee,decision__pengajuan__unit_kerja_id=visit.unit_kerja_id,decision__pengajuan__status='DISETUJUI').filter(Q(berlaku_sampai__isnull=True)|Q(berlaku_sampai__gte=day)),for_update))
    candidates=[]
    for spk in assignments:
        application=locked(PengajuanKredensial.objects.filter(pk=spk.decision.pengajuan_id),for_update).get()
        if application.status!='DISETUJUI':continue
        snapshots=list(locked(PrivilegeSnapshot.objects.filter(pegawai=employee,unit_kerja_id=visit.unit_kerja_id,source_decision=spk,revoked_at__isnull=True,action_code__code='professional_care',action_code__is_active=True,valid_from__lte=day).filter(Q(valid_until__isnull=True)|Q(valid_until__gte=day)),for_update))
        lines=list(locked(RincianKewenangan.objects.filter(pengajuan=application,catalog_item=catalogue),for_update))
        if snapshots and len(lines)==1 and lines[0].status_spk in {'DISETUJUI_MANDIRI','DISETUJUI_SUPERVISI','DISETUJUI_MANDIRI_TERBATAS'}:
            candidates.append((spk,lines[0],snapshots))
    if len(candidates)!=1:raise PermissionDenied('SPK/kewenangan individual tidak berlaku atau ambigu.')
    spk,line,snapshots=candidates[0]
    if line.status_spk=='DISETUJUI_MANDIRI_TERBATAS':
        from klinis.models import BatasanKewenanganProfesional
        from sdm.professional_policy import limits_digest,enforce_limits
        policies=list(locked(BatasanKewenanganProfesional.objects.filter(privilege=line,is_active=True,reviewed_by__isnull=False,reviewed_at__isnull=False,valid_from__lte=day,valid_until__gte=day).exclude(source_version=''),for_update))
        if len(policies)!=1 or policies[0].narrative_digest!=limits_digest(line.batasan):raise PermissionDenied('Batasan mandat belum ditinjau sebagai aturan terstruktur yang berlaku.')
        context['limits_policy']={'id':policies[0].pk,'conditions':policies[0].conditions,'narrative_digest':policies[0].narrative_digest,'source_version':policies[0].source_version}
        enforce_limits(context['limits_policy'],visit,day)
    from sdm.models import TraineePlacement
    placements=list(locked(TraineePlacement.objects.filter(pegawai=employee,is_active=True,tanggal_mulai__lte=day,tanggal_selesai__gte=day).filter(Q(unit_kerja_id=visit.unit_kerja_id)|Q(unit_kerja__isnull=True)),for_update))
    if placements:
        if any(p.requires_countersignature for p in placements):raise PermissionDenied('Peserta didik memerlukan alur countersign pembimbing khusus; pelayanan mandiri tidak diberikan.')
        if len(placements)!=1 or placements[0].unit_kerja_id!=visit.unit_kerja_id or 'professional_care' not in placements[0].temporary_action_codes or line.status_spk!='DISETUJUI_SUPERVISI':raise PermissionDenied('Peserta didik memerlukan mandat supervisi dan penempatan unit yang eksplisit.')
        context['trainee_supervisor_id']=str(placements[0].supervisor_id)
        context['trainee_placement_id']=str(placements[0].pk)
    return {**context,'spk_id':str(spk.pk),'spk_version':spk.versi,'privilege_id':line.pk,'privilege_status':line.status_spk,
            'privilege_snapshot_ids':sorted(str(x.pk) for x in snapshots),'rkk_code':catalogue.kode,'mapping_id':mappings[0].pk,
            'mapping_source':mappings[0].source_version,'limits':line.batasan,'supervision':line.status_spk}


def resolve_professional_context(actor,visit,service,*,at,performer=None,supervisor=None,for_update=False):
    require_scope(actor,visit)
    if not isinstance(service,LayananProfesional) or not service.is_active or not service.reviewed_by_id or not service.reviewed_at or not service.source_version:
        raise PermissionDenied('Layanan belum ditinjau.')
    if performer and str(performer)!=str(getattr(getattr(actor,'pegawai_hc',None),'pk','')):
        if not has_grant(actor,visit,'RECORD_FOR_OTHER',at=at,service=service,for_update=for_update):raise PermissionDenied('Pencatatan pelaksana lain tidak diizinkan.')
    context=_employee_context(actor,visit,service,performer,at,for_update)
    needs_supervisor=context['supervision']=='DISETUJUI_SUPERVISI' or context['supervision']=='DISETUJUI_MANDIRI_TERBATAS'
    if needs_supervisor:
        if not supervisor or str(supervisor)==context['performer_id']:raise PermissionDenied('Pembimbing independen wajib dipilih.')
        if context.get('trainee_supervisor_id') and str(supervisor)!=context['trainee_supervisor_id']:raise PermissionDenied('Pembimbing tidak sesuai penempatan peserta didik.')
        mentor=_employee_context(actor,visit,service,supervisor,at,for_update)
        if mentor['supervision']!='DISETUJUI_MANDIRI':raise PermissionDenied('Pembimbing tidak mandiri untuk layanan ini.')
        if context['supervision']=='DISETUJUI_MANDIRI_TERBATAS' and not context.get('limits','').strip():raise PermissionDenied('Batasan mandat belum terdokumentasi.')
        context['supervisor']={key:mentor[key] for key in ('performer_id','performer_name','spk_id','privilege_id')}
    elif supervisor:raise ValidationError('Pembimbing tidak diperlukan oleh mandat ini.')
    return context


def eligible_performers(actor,visit,service,*,at):
    require_scope(actor,visit)
    delegated=has_grant(actor,visit,'RECORD_FOR_OTHER',at=at,service=service)
    qs=Pegawai.objects.filter(status='AKTIF',akun__is_active=True)
    if not delegated:qs=qs.filter(akun=actor)
    else:qs=qs.filter(Q(clinical_assignments__unit_kerja_id=visit.unit_kerja_id,clinical_assignments__is_active=True)|Q(akun__professional_care_grants__unit_id=visit.unit_kerja_id,akun__professional_care_grants__capability='SUPPORT_SERVICE',akun__professional_care_grants__is_active=True)).distinct()
    result=[]
    for employee in qs.order_by('pk')[:50]:
        try:
            context=_employee_context(actor,visit,service,employee.pk,at,False)
            result.append({key:context[key] for key in ('performer_id','performer_name','profession_id','profession_name','grade_id','grade_name','supervision')})
        except PermissionDenied:continue
    return result


def eligible_supervisors(actor,visit,service,*,at):
    require_scope(actor,visit)
    result=[]
    qs=Pegawai.objects.filter(status='AKTIF',akun__is_active=True,clinical_assignments__unit_kerja_id=visit.unit_kerja_id,clinical_assignments__is_active=True).exclude(akun=actor).distinct().order_by('pk')
    for employee in qs[:50]:
        try:
            context=_employee_context(actor,visit,service,employee.pk,at,False)
            if context['supervision']=='DISETUJUI_MANDIRI':result.append({key:context[key] for key in ('performer_id','performer_name','profession_id','grade_id')})
        except PermissionDenied:continue
    return result


def scoped_staff_choices(actor,visit,*,at):
    require_scope(actor,visit)
    day=business_date(at)
    delegated=ProfessionalCareGrant.objects.filter(user=actor,unit_id=visit.unit_kerja_id,capability='RECORD_FOR_OTHER',is_active=True,valid_from__lte=day,valid_until__gte=day,reviewed_by__isnull=False,reviewed_at__isnull=False).exclude(source_version='').exclude(reviewed_by=actor).exists()
    qs=Pegawai.objects.filter(status='AKTIF',akun__is_active=True,data_origin__in=['MANUAL','VERIFIED_IMPORT'],profesi_master__is_active=True,jenjang_master__isnull=False)
    if delegated:
        qs=qs.filter(Q(akun=actor)|Q(clinical_assignments__unit_kerja_id=visit.unit_kerja_id,clinical_assignments__is_active=True))
    else:qs=qs.filter(akun=actor)
    return [employee for employee in qs.select_related('profesi_master','jenjang_master').distinct().order_by('pk')[:50] if employee.jenjang_master.profesi_id==employee.profesi_master_id]
