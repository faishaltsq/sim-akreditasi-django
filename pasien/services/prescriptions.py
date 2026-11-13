import json
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from uuid import UUID, uuid4
from django.core.exceptions import PermissionDenied
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.utils import timezone
from akreditasi.models import AuditLog, UnitKerja
from klinis.models import ProdukFarmasi
from klinis.services.medication_catalogue import product_snapshot
from pasien.models import (ResepElektronik, ResepDetail, KomponenRacikan, BillingItem,
    MedicationSafetyReview, PpraReviewRequest, PrescriptionOperation, PharmacyServiceGrant, KunjunganPasien, IgdAssessmentWorkflow)
from .medication_safety import active_policy, evaluate_prescription, current_catalogue_risks


def decimal_value(value, *, allow_zero=False, maximum='1000000'):
    try:
        if isinstance(value,bool):
            raise ValueError('Nilai boolean bukan jumlah.')
        number=Decimal(str(value))
        if not number.is_finite() or number<0 or (not allow_zero and number==0) or number>Decimal(maximum):
            raise ValueError('Nilai di luar batas.')
        return number
    except (InvalidOperation,TypeError) as exc:
        raise ValueError('Gunakan angka desimal yang valid.') from exc


def calculate_quantity(regimen, product_units):
    allowed={'schema_version','frequency','times_per_day','interval_hours','dose','dose_unit','duration_days',
             'route','timing','prn_indication','max_per_day','instructions'}
    if not isinstance(regimen,dict) or set(regimen)-allowed or type(regimen.get('schema_version')) is not int or regimen['schema_version']!=1:
        raise ValueError('Format aturan pakai tidak valid.')
    frequency=regimen.get('frequency')
    if any(not isinstance(regimen[key],str) or len(regimen[key])>2000 for key in ('dose_unit','route','timing','prn_indication','instructions') if key in regimen):
        raise ValueError('Teks aturan pakai tidak valid.')
    if frequency not in ('FIXED','INTERVAL','PRN','VARIABLE','BMHP'):
        raise ValueError('Frekuensi tidak valid.')
    unit=product_units.get('dispense_unit','')
    if frequency=='BMHP':
        return {'quantity':None,'unit':unit,'requires_manual_quantity':True}
    dose=decimal_value(regimen.get('dose')); duration=decimal_value(regimen.get('duration_days'))
    if frequency in ('PRN','VARIABLE'):
        return {'quantity':None,'unit':unit,'requires_manual_quantity':True}
    rate=decimal_value(regimen.get('times_per_day'),maximum='24') if frequency=='FIXED' else Decimal('24')/decimal_value(regimen.get('interval_hours'),maximum='168')
    conversion=Decimal('1')
    if regimen.get('dose_unit')!=unit:
        factor=product_units.get('conversion',{}).get(regimen.get('dose_unit'))
        if factor is None:
            return {'quantity':None,'unit':unit,'requires_manual_quantity':True}
        conversion=decimal_value(factor)
    quantity=dose*rate*duration/conversion
    if quantity>Decimal('1000000') or quantity.as_tuple().exponent < -4:
        raise ValueError('Jumlah membutuhkan pembulatan/penyesuaian manual dengan alasan.')
    return {'quantity':quantity,'unit':unit,'requires_manual_quantity':False}


def content_digest(rx):
    from .igd_actions import digest
    patient=rx.kunjungan.pasien
    policy=active_policy()
    return digest({'items':list(rx.items.order_by('pk').values('id','product_snapshot','regimen','quantity_decimal','reference_price','quantity_reason')),
        'allergy_status':rx.kunjungan.skrining_alergi_status,'allergy_raw':patient.alergi_obat,
        'episode_allergy':rx.kunjungan.alergi_asesmen,
        'allergies':list(patient.structured_allergies.filter(active=True).values('ingredient_code','therapy_class_code','reaction')),
        'policy':{'version':policy.version,'rules':policy.rules} if policy else 'UNCONFIGURED',
        'current_product_risks':current_catalogue_risks(rx)})


def require_prescriber(user):
    if user.profile.profesi not in ('DOKTER_UMUM','DOKTER_SPESIALIS') or user.profile.role=='ASESOR':
        raise PermissionDenied('Peresepan memerlukan dokter.')


def save_prescription(visit, workflow, actor, data):
    require_prescriber(actor)
    if set(data)-{'prescription_id','serving_unit_id','lines','catatan_dokter'} or not isinstance(data.get('lines'),list) or not 1<=len(data['lines'])<=100:
        raise ValueError('Resep memerlukan satu sampai 100 baris.')
    serving=data.get('serving_unit_id')
    if serving is not None and (type(serving) is not int or not PharmacyServiceGrant.objects.filter(unit_id=serving).exists()):
        raise ValueError('Pilih depo dengan penugasan farmasi yang dikonfigurasi.')
    rx=None
    if data.get('prescription_id'):
        rx=visit.resep_list.select_for_update().filter(pk=data['prescription_id'],status='DRAFT',dokter_peresep=actor).first()
        if rx is None:
            raise ValueError('Hanya draft resep dokter ini yang dapat diubah.')
        if rx.items.filter(billing_item__isnull=False).exists():
            raise ValueError('Draft memiliki billing; perlu rekonsiliasi beralasan.')
    prepared=[]
    for line in data['lines']:
        if not isinstance(line,dict) or set(line)-{'product_id','kind','regimen','quantity','quantity_reason','components','compound_instructions','compound_form','formulary'}:
            raise ValueError('Atribut baris resep tidak valid.')
        product=ProdukFarmasi.objects.select_related('generik__kelas').filter(pk=line.get('product_id')).first()
        if product is None:
            raise ValueError('Produk tidak ditemukan.')
        snap=product_snapshot(product); kind=line.get('kind','OBAT')
        if kind not in ('OBAT','RACIKAN','BMHP') or (kind=='BMHP')!=(product.kind=='BMHP'):
            raise ValueError('Kategori resep tidak sesuai produk.')
        regimen=line.get('regimen',{})
        if not isinstance(regimen,dict):
            raise ValueError('Aturan pakai harus berupa objek.')
        if kind!='BMHP' and regimen.get('route') not in product.allowed_routes:
            raise ValueError('Rute tidak sesuai sediaan produk.')
        if regimen.get('frequency')=='PRN':
            maximum=decimal_value(regimen.get('max_per_day'),maximum='24')
            if not str(regimen.get('prn_indication','')).strip() or maximum!=maximum.to_integral_value():
                raise ValueError('PRN memerlukan indikasi dan batas pemberian bulat.')
        calculated=calculate_quantity(regimen,{'dispense_unit':snap['unit'],'conversion':snap['conversion']})
        quantity=decimal_value(line['quantity']) if line.get('quantity') is not None else calculated['quantity']
        if quantity is not None and quantity!=quantity.quantize(Decimal('.0001')):
            raise ValueError('Jumlah maksimal empat angka desimal; sesuaikan dengan alasan.')
        reason=line.get('quantity_reason','')
        if quantity is None or not isinstance(reason,str) or len(reason)>2000:
            raise ValueError('Jumlah manual dan alasan diperlukan.')
        if (calculated['requires_manual_quantity'] or quantity!=calculated['quantity'] or kind=='RACIKAN') and not reason.strip():
            raise ValueError('Alasan penyesuaian jumlah wajib diisi.')
        components=[]
        if kind=='RACIKAN':
            if not isinstance(line.get('components'),list) or not 1<=len(line['components'])<=30 or not str(line.get('compound_instructions','')).strip():
                raise ValueError('Racikan memerlukan komponen dan instruksi peracikan.')
            for part in line['components']:
                if not isinstance(part,dict) or set(part)!={'product_id','amount','unit'}:
                    raise ValueError('Komponen racikan tidak valid.')
                component=ProdukFarmasi.objects.select_related('generik__kelas').filter(pk=part['product_id'],kind='OBAT').first()
                if component is None:
                    raise ValueError('Produk komponen tidak ditemukan.')
                part_snap=product_snapshot(component)
                amount=decimal_value(part['amount']);unit=part['unit']
                if (not isinstance(unit,str) or not 1<=len(unit)<=30 or
                    unit not in {part_snap['unit'],*part_snap['conversion']} or
                    amount!=amount.quantize(Decimal('.0001'))):
                    raise ValueError('Jumlah/satuan komponen memerlukan master konversi yang sesuai.')
                components.append((component,amount,unit,part_snap))
            snap['ingredients']=[i for part in components for i in part[3]['ingredients']]
            snap['flags']=sorted(set(snap['flags']+[flag for part in components for flag in part[3]['flags']]))
            if line.get('compound_form') not in ('PUYER','KAPSUL','SALEP'):
                raise ValueError('Pilih bentuk akhir racikan.')
            snap['compound_form']=line['compound_form']
            snap['unit']={'PUYER':'bungkus','KAPSUL':'kapsul','SALEP':'pot'}[line['compound_form']]
            snap['compound_instructions']=str(line['compound_instructions'])[:2000]
            snap['components']=[{'product':part[3],'amount':str(part[1]),'unit':part[2]} for part in components]
            snap['price']=None
        formulary=line.get('formulary','RS')
        today=timezone.localdate()
        from django.db.models import Q
        membership=product.formularies.filter(jenis=formulary,valid_from__lte=today).filter(Q(valid_to__isnull=True)|Q(valid_to__gte=today)).first()
        if formulary not in ('RS','FORNAS') or (formulary=='FORNAS' and membership is None):
            raise ValueError('Keanggotaan Fornas aktif belum diverifikasi.')
        snap['formulary']={'type':formulary,'version':membership.source_version if membership else None,'restrictions':membership.restrictions if membership else ''}
        prepared.append((product,snap,kind,regimen,quantity,reason,components))
    before=list(rx.items.values('id','product_snapshot','regimen','quantity_decimal')) if rx else []
    if rx is None:
        rx=ResepElektronik.objects.create(kunjungan=visit,no_resep='RSP-'+uuid4().hex[:24],dokter_peresep=actor,jenis_resep='IGD',status='DRAFT')
    else:
        KomponenRacikan.objects.filter(detail__resep=rx).delete()
        rx.items.all().delete()
    rx.serving_unit_id=serving
    note=data.get('catatan_dokter','')
    if not isinstance(note,str) or len(note)>250:
        raise ValueError('Catatan dokter maksimal 250 karakter.')
    rx.catatan_dokter=note; rx.version+=1; rx.submitted_snapshot={}; rx.save()
    for product,snap,kind,regimen,quantity,reason,components in prepared:
        signa=f"{regimen.get('dose','')} {regimen.get('dose_unit','')}, {regimen.get('frequency','')} {regimen.get('times_per_day',regimen.get('interval_hours',''))}, {regimen.get('route','')}, {regimen.get('timing','')}, {regimen.get('duration_days','')} hari"
        row=ResepDetail.objects.create(resep=rx,product=product,product_snapshot=snap,kind=kind,regimen=regimen,
            nama_obat=('Racikan '+snap['compound_form'] if kind=='RACIKAN' else product.nama[:150]),bentuk_sediaan=snap.get('compound_form',product.generik.bentuk[:10]),dosis=str(regimen.get('dose',''))[:50],
            aturan_pakai=signa[:100],jumlah=int(quantity.to_integral_value(rounding=ROUND_CEILING)),quantity_decimal=quantity,
            quantity_reason=reason,reference_price=product.price if kind!='RACIKAN' else None,harga_satuan=product.price if product.price is not None and kind!='RACIKAN' else 0)
        for component,amount,unit,snapshot in components:
            KomponenRacikan.objects.create(detail=row,produk=component,amount=amount,unit=unit,snapshot=snapshot)
    AuditLog.objects.create(user=actor,aksi='UPDATE',model_name='ResepElektronik',object_repr=rx.no_resep,
        detail=json.dumps({'before':before,'after':list(rx.items.values('id','product_snapshot','regimen','quantity_decimal'))},cls=DjangoJSONEncoder))
    return {'prescription_id':rx.pk,'prescription_version':rx.version}


def review_risks(rx,actor,acknowledgements):
    if not isinstance(acknowledgements,list) or len(acknowledgements)>100:
        raise ValueError('Daftar konfirmasi risiko tidak valid.')
    accepted={}
    for ack in acknowledgements:
        if not isinstance(ack,dict) or set(ack)!={'code','reason'} or not isinstance(ack['reason'],str) or not 5<=len(ack['reason'].strip())<=2000:
            raise ValueError('Konfirmasi risiko memerlukan kode dan alasan minimal lima karakter.')
        accepted[ack['code']]=ack['reason']
    findings=evaluate_prescription(rx); fingerprint=content_digest(rx); policy=active_policy(); policy_version=policy.version if policy else 'UNCONFIGURED'
    for risk in findings:
        if risk['code']=='PPRA':
            approved=rx.ppra_reviews.filter(digest=fingerprint,policy_version=policy_version,decision='APPROVED',expires_at__gt=timezone.now()).exists()
            if not approved:
                request,_=PpraReviewRequest.objects.get_or_create(resep=rx,digest=fingerprint,policy_version=policy_version,defaults={'requested_by':actor})
                return {'held':True,'ppra_request_id':request.pk,'findings':findings}
        elif risk['blocking']:
            raise ValueError(risk['message'])
        elif risk['requires_ack'] and risk['code'] not in accepted:
            raise ValueError(risk['message']+' Konfirmasi beralasan diperlukan.')
    MedicationSafetyReview.objects.create(resep=rx,digest=fingerprint,policy_version=policy_version,findings=findings,acknowledgements=acknowledgements,actor=actor)
    return {'held':False,'findings':findings}


def submit_prescription(visit,workflow,actor,data):
    require_prescriber(actor)
    if set(data)-{'prescription_id','acknowledgements'}:
        raise ValueError('Atribut pengiriman resep tidak dikenal.')
    rx=visit.resep_list.select_for_update().filter(pk=data.get('prescription_id'),status='DRAFT',dokter_peresep=actor).first()
    if rx is None or not rx.items.exists():
        raise ValueError('Draft resep tidak ditemukan.')
    if not rx.serving_unit_id:
        raise ValueError('Depo farmasi tujuan belum ditetapkan.')
    result=review_risks(rx,actor,data.get('acknowledgements',[]))
    if result['held']:
        return {'prescription_id':rx.pk,**result}
    rx.status='DIKIRIM';rx.version+=1
    rx.policy_version=active_policy().version if active_policy() else 'UNCONFIGURED'
    rx.submitted_snapshot={'digest':content_digest(rx),'items':list(rx.items.values('product_snapshot','regimen','quantity_decimal','reference_price'))}
    rx.submitted_snapshot=json.loads(json.dumps(rx.submitted_snapshot,cls=DjangoJSONEncoder))
    rx.save()
    return {'prescription_id':rx.pk,'prescription_version':rx.version,**result}


def authorize_pharmacy(actor,rx):
    profile=getattr(actor,'profile',None)
    if not actor.is_authenticated or not profile or profile.role=='ASESOR' or profile.profesi not in ('APOTEKER','TTK'):
        raise PermissionDenied('Tindakan farmasi memerlukan petugas farmasi.')
    if not PharmacyServiceGrant.objects.filter(user=actor,unit_id=rx.serving_unit_id).exists():
        raise PermissionDenied('Resep di luar penugasan depo Anda.')


@transaction.atomic
def transition_prescription(actor,prescription_id,action,expected_version,request_id,reason=''):
    from .igd_actions import digest
    ref=ResepElektronik.objects.get(pk=prescription_id)
    KunjunganPasien.objects.select_for_update().get(pk=ref.kunjungan_id)
    IgdAssessmentWorkflow.objects.select_for_update().filter(kunjungan_id=ref.kunjungan_id).first()
    rx=ResepElektronik.objects.select_for_update().select_related('kunjungan__pasien').get(pk=prescription_id)
    authorize_pharmacy(actor,rx)
    key=UUID(str(request_id)); fingerprint=digest({'action':action,'reason':reason,'version':expected_version})
    previous=rx.operations.filter(request_id=key).first()
    if previous:
        if previous.actor_id!=actor.pk or previous.digest!=fingerprint:
            raise ValueError('ID permintaan telah digunakan untuk aksi berbeda.')
        return previous.result
    if type(expected_version) is not int or expected_version!=rx.version:
        raise ValueError('Versi resep berubah; muat ulang.')
    if action not in ('dispensing','selesai','batal'):
        raise ValueError('Transisi resep tidak dikenal.')
    if rx.status=='SELESAI' and action=='selesai':
        return {'prescription_id':rx.pk,'version':rx.version,'financial_pending':rx.financial_pending}
    if (action=='dispensing' and rx.status!='DIKIRIM') or (action=='selesai' and rx.status!='DISPENSING') or (action=='batal' and rx.status not in ('DRAFT','DIKIRIM','DISPENSING')):
        raise ValueError('Urutan status resep tidak valid.')
    if action=='batal' and (not isinstance(reason,str) or not 5<=len(reason.strip())<=2000):
        raise ValueError('Pembatalan memerlukan alasan.')
    if action in ('dispensing','selesai'):
        reviews=rx.safety_reviews.filter(digest=content_digest(rx)).order_by('-pk').first()
        if reviews is None or any(r['blocking'] and r['code']!='PPRA' for r in evaluate_prescription(rx)):
            raise ValueError('Risiko/alergi berubah; resep perlu tinjauan dokter kembali.')
        if any(r['code']=='PPRA' for r in evaluate_prescription(rx)) and not rx.ppra_reviews.filter(digest=content_digest(rx),decision='APPROVED',expires_at__gt=timezone.now()).exists():
            raise ValueError('Persetujuan PPRA belum berlaku.')
    if action=='selesai':
        rows=list(rx.items.select_for_update().all())
        if not rows:
            raise ValueError('Resep kosong tidak dapat diselesaikan.')
        for row in rows:
            if (row.reference_price is None or row.quantity_decimal is None or
                row.quantity_decimal != row.quantity_decimal.quantize(Decimal('.01')) or
                row.quantity_decimal > Decimal('999999.99')):
                rx.financial_pending=True
            elif row.billing_item_id is None:
                row.billing_item=BillingItem.objects.create(kunjungan=rx.kunjungan,kategori='OBAT',nama_item='Obat: '+row.nama_obat,
                    kuantitas=row.quantity_decimal,harga_satuan=row.reference_price,sumber='FARMASI',dicatat_oleh=actor)
                row.save(update_fields=['billing_item'])
        rx.waktu_selesai=timezone.now()
    rx.status={'dispensing':'DISPENSING','selesai':'SELESAI','batal':'BATAL'}[action]
    rx.apoteker=actor;rx.version+=1;rx.save()
    result={'prescription_id':rx.pk,'version':rx.version,'financial_pending':rx.financial_pending}
    PrescriptionOperation.objects.create(resep=rx,request_id=key,digest=fingerprint,actor=actor,result=result)
    AuditLog.objects.create(user=actor,aksi='UPDATE',model_name='ResepElektronik',object_repr=rx.no_resep,detail=json.dumps({'action':action,'reason':reason,'result':result}))
    return result
