"""Run only against disposable loopback fixture settings; never production."""
import os,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root));os.environ['DJANGO_SETTINGS_MODULE']='config.professional_browser_settings'
assert not os.environ.get('DATABASE_URL')
import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.contrib.auth.models import User
from django.test import Client
from django.utils import timezone
from django.contrib.staticfiles.handlers import StaticFilesHandler
from django.core.wsgi import get_wsgi_application
from wsgiref.simple_server import make_server
from pasien.professional_test_support import ProfessionalCareCase
from klinis.models import TarifLayananProfesi,ProfessionalCareGrant,LayananProfesional,PemetaanKewenanganLayanan
from sdm.models import ClinicalActionCode,PrivilegeSnapshot
from pasien.models import PenugasanDpjpEpisode,CPPT,BillingItem,TindakanAsesmen,IgdAssessmentWorkflow,VerifikasiCppt

if settings.DATABASES['default']['NAME'].exists():raise SystemExit('Owned fixture already exists; do not overwrite a running QA database.')
call_command('migrate',interactive=False,verbosity=0)
ProfessionalCareCase.setUpTestData()
f=ProfessionalCareCase
reviewer=User.objects.create_superuser('qa-dpjp-assigner')
extra={}
for code,free in [('QA.FREE',True),('QA.PENDING',False)]:
    service=LayananProfesional.objects.create(code=code,name='Layanan sintetis '+code,group='MEDICAL',authority_kind='CLINICAL',allow_unpriced=not free,is_active=True,source_version='qa-fixture',reviewed_by=reviewer,reviewed_at=timezone.now())
    PemetaanKewenanganLayanan.objects.create(service=service,catalog_item=f.catalogue,is_active=True,source_version='qa-fixture',reviewed_by=reviewer,reviewed_at=timezone.now())
    if free:TarifLayananProfesi.objects.create(service=service,unit=f.unit,profession=f.profession,grade=f.grade,payor=f.visit.penjamin,valid_from=timezone.localdate(),jasa_sarana=0,jasa_pelayanan=0,is_free=True,review_state='APPROVED',is_active=True,reviewed_by=reviewer,reviewed_at=timezone.now(),source_version='qa-free-approval')
    extra[code]=service.pk
planned=TindakanAsesmen.objects.create(kunjungan=f.visit,urutan=1,jenis='BEBAS',kode=f.service.code,nama=f.service.name,execution_status='PLANNED',execution_team='MEDIS',tarif_penjamin=f.visit.penjamin)
TarifLayananProfesi.objects.create(service=f.service,unit=f.unit,profession=f.profession,grade=f.grade,payor=f.visit.penjamin,valid_from=timezone.localdate(),jasa_sarana=50000,jasa_pelayanan=150000,is_free=False,review_state='APPROVED',is_active=True,reviewed_by=reviewer,reviewed_at=timezone.now(),source_version='qa-reviewed-source')
ProfessionalCareGrant.objects.create(user=f.user,unit=f.unit,capability='VOID_UNPAID_CHARGE',valid_from=timezone.localdate(),valid_until=timezone.localdate(),is_active=True,source_version='qa-fixture',reviewed_by=reviewer,reviewed_at=timezone.now())
code=ClinicalActionCode.objects.create(code='verify_cppt',label='Verifikasi CPPT QA')
PrivilegeSnapshot.objects.create(pegawai=f.employee,unit_kerja=f.unit,action_code=code,valid_from=timezone.localdate(),source_decision=f.spk)
PenugasanDpjpEpisode.objects.create(visit=f.visit,doctor=f.user,unit=f.unit,assignment_type='PRIMARY',valid_from=timezone.localdate(),valid_until=timezone.localdate(),source_version='qa-reviewed-assignment',assigned_by=reviewer,is_active=True)
client=Client();client.force_login(f.user)
metadata={'visit':f.visit.pk,'service':f.service.pk,'actor':f.user.pk,'cookies':{k:v.value for k,v in client.cookies.items()}}
metadata.update(extra=extra,planned=planned.pk)
(settings.QA_ROOT/'fixture.json').write_text(json.dumps(metadata),encoding='utf-8')
application=StaticFilesHandler(get_wsgi_application())
def app(environ,start_response):
    if environ.get('PATH_INFO')=='/__qa/state':
        assert environ.get('REMOTE_ADDR')=='127.0.0.1'
        result={'actions':TindakanAsesmen.objects.filter(kunjungan=f.visit).count(),'notes':list(CPPT.objects.filter(kunjungan=f.visit).values('id','status','version','verifikasi_dpjp')),'charges':list(BillingItem.objects.filter(kunjungan=f.visit).values('id','is_void','harga_satuan')),'verifications':VerifikasiCppt.objects.count(),'workflow':list(IgdAssessmentWorkflow.objects.filter(kunjungan=f.visit).values('version','status'))}
        from django.core.serializers.json import DjangoJSONEncoder
        result['action_statuses']=list(TindakanAsesmen.objects.filter(kunjungan=f.visit).values_list('execution_status',flat=True))
        body=json.dumps(result,cls=DjangoJSONEncoder).encode()
        start_response('200 OK',[('Content-Type','application/json'),('Cache-Control','no-store'),('Content-Length',str(len(body)))])
        return [body]
    return application(environ,start_response)
print('PROFESSIONAL_BROWSER_READY',flush=True)
with make_server('127.0.0.1',18769,app) as server:server.serve_forever()
