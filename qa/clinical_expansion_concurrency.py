"""Real PostgreSQL concurrency and frozen-snapshot probe for synthetic fixtures."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
import json
from pathlib import Path
from threading import Barrier
from uuid import uuid4


def run(state_path,evidence):
    import django
    django.setup()
    from django.db import connection,close_old_connections
    from django.contrib.auth.models import User
    from django.utils import timezone
    from pasien.models import KunjunganPasien,ResepElektronik,IgdAssessmentWorkflow,IgdAssessmentRevision
    from pasien.services.igd_actions import perform_action,digest
    from pasien.services.prescriptions import transition_prescription
    from pasien.services.igd_finalization import EXEMPTIONS
    from klinis.models import ProdukFarmasi
    assert connection.vendor=='postgresql' and connection.settings_dict['NAME']=='clinical_verify'
    state=json.loads(Path(state_path).read_text(encoding='utf-8'))
    doctor=User.objects.get(pk=state['users']['doctor']['id'])
    pharmacist=User.objects.get(pk=state['users']['pharmacist']['id'])
    visit=KunjunganPasien.objects.get(pk=state['visits']['desktop'])
    assert visit.pasien.no_rm.startswith('QC')
    report={'vendor':connection.vendor,'cases':[]}
    def parallel(calls):
        barrier=Barrier(len(calls))
        def worker(call):
            close_old_connections()
            try:
                barrier.wait(timeout=15)
                return {'ok':True,'result':call()}
            except Exception as exc:
                return {'ok':False,'type':type(exc).__name__,'error':str(exc)}
            finally:
                connection.close()
        with ThreadPoolExecutor(max_workers=len(calls)) as pool:
            return list(pool.map(worker,calls))
    def actor(uid):
        return User.objects.select_related('profile').get(pk=uid)
    def version():
        return IgdAssessmentWorkflow.objects.filter(kunjungan=visit).values_list('version',flat=True).first() or 0
    initial=version()
    outcomes=parallel([lambda i=i:perform_action(visit.pk,actor(doctor.pk),'diagnosis_set',{'changes':[{'op':'upsert','temp_id':'concurrent-'+str(i),'mode':'MANUAL','text':'Synthetic primary '+str(i),'is_primary':True}]},initial,str(uuid4())) for i in range(2)])
    assert sum(o['ok'] for o in outcomes)==1,outcomes
    assert visit.diagnoses.filter(active=True,is_primary=True).count()==1
    report['cases'].append({'case':'competing_primary','outcomes':outcomes,'primary_count':1})
    key=str(uuid4());current=version();payload={'items':[{'item_id':state['catalogue']['ancillary'][-1],'prioritas':'CITO','indication':'Synthetic concurrent order'}]}
    outcomes=parallel([lambda:perform_action(visit.pk,actor(doctor.pk),'order_batch',payload,current,key) for _ in range(2)])
    assert all(o['ok'] for o in outcomes) and visit.order_penunjang.count()==1,outcomes
    report['cases'].append({'case':'same_key_order_batch','outcomes':outcomes,'orders':1})
    plan=perform_action(visit.pk,doctor,'plan_action',{'jenis':'BEBAS','mode':'MANUAL','nama':'Synthetic actual care','quantity':'1','tarif':'1000','catatan_tarif':'Harga fixture sintetis','lokasi_anatomis':'Lokasi synthetic','catatan_klinis':'Catatan synthetic'},version(),str(uuid4()))
    performed=perform_action(visit.pk,doctor,'execute',{'action_id':plan['action_id'],'occurred_at':(timezone.now()-timedelta(minutes=5)).isoformat(),'retrospective_reason':'Pencatatan retrospektif fixture sintetis'},version(),str(uuid4()))
    assert visit.cppt.filter(pk=performed['cppt_id']).exists()
    report['cases'].append({'case':'plan_and_retrospective_execution','cppt':performed['cppt_id'],'billing':performed['billing_id']})
    saved=perform_action(visit.pk,doctor,'prescription_save',{'serving_unit_id':state['pharmacy_unit'],'lines':[{'product_id':state['catalogue']['normal'][-1],'kind':'OBAT','regimen':{'schema_version':1,'frequency':'FIXED','times_per_day':'2','dose':'0.5','dose_unit':'tablet','duration_days':'3','route':'PO','timing':'PC'}}]},version(),str(uuid4()))
    key=str(uuid4());current=version()
    outcomes=parallel([lambda:perform_action(visit.pk,actor(doctor.pk),'prescription_submit',{'prescription_id':saved['prescription_id'],'acknowledgements':[]},current,key) for _ in range(2)])
    assert all(o['ok'] for o in outcomes),outcomes
    rx=ResepElektronik.objects.get(pk=saved['prescription_id']);assert rx.status=='DIKIRIM'
    report['cases'].append({'case':'two_submissions_same_key','outcomes':outcomes,'safety_reviews':rx.safety_reviews.count()})
    for action in ['dispensing','selesai']:
        key=str(uuid4());rx.refresh_from_db();rx_version=rx.version
        outcomes=parallel([lambda:transition_prescription(actor(pharmacist.pk),rx.pk,action,rx_version,key) for _ in range(2)])
        assert all(o['ok'] for o in outcomes),outcomes
        report['cases'].append({'case':'concurrent_'+action,'outcomes':outcomes})
    rx.refresh_from_db();row=rx.items.get()
    assert row.billing_item_id and row.billing_item.kuantitas==Decimal('3')
    assert visit.billing.filter(sumber='FARMASI').count()==1
    assert rx.operations.count()==2
    try:
        transition_prescription(pharmacist,rx.pk,'selesai',rx.version-1,str(uuid4()))
    except ValueError:
        pass
    else:
        raise AssertionError('Stale completion was accepted')
    report['cases'].append({'case':'billing_and_stale_version','farmasi_rows':1,'quantity':str(row.billing_item.kuantitas),'stale_rejected':True})
    perform_action(visit.pk,doctor,'sign',{'section':'MEDIS','exemptions':{key:'Batas fixture sintetis untuk uji integrasi' for key in EXEMPTIONS}},version(),str(uuid4()))
    finalized=perform_action(visit.pk,doctor,'finalize',{'outcome':'NONE','resume':'Synthetic PostgreSQL verification'},version(),str(uuid4()))
    revision=IgdAssessmentRevision.objects.get(pk=finalized['revision_id']);old_digest=digest(revision.snapshot)
    expected_name=row.nama_obat
    product=ProdukFarmasi.objects.get(pk=state['catalogue']['normal'][-1]);product.nama='Changed synthetic master after final';product.price=Decimal('2000');product.save(update_fields=['nama','price'])
    order=visit.order_penunjang.get()
    late=perform_action(visit.pk,doctor,'order_result',{'order_id':order.pk,'status':'SELESAI','hasil_pemeriksaan':'Synthetic late result'},version(),str(uuid4()))
    assert late['late_result']
    perform_action(visit.pk,doctor,'addendum',{'section':'MEDIS','reason':'Hasil synthetic diterima setelah final','text':'Tinjauan hasil synthetic pada addendum'},version(),str(uuid4()))
    revision.refresh_from_db();assert digest(revision.snapshot)==old_digest
    assert revision.snapshot['prescriptions'][0]['items'][0]['nama_obat']==expected_name
    assert visit.igd_workflow.revisions.count()==2
    report['cases'].append({'case':'final_snapshot_late_result_addendum','revision_id':revision.pk,'original_digest_unchanged':True,'revisions':2})
    evidence=Path(evidence);evidence.parent.mkdir(parents=True,exist_ok=True)
    evidence.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--state',required=True);parser.add_argument('--evidence',required=True)
    args=parser.parse_args();run(args.state,args.evidence)
