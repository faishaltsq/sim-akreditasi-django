from decimal import Decimal,ROUND_HALF_UP
from django.core.exceptions import ValidationError,PermissionDenied
from django.utils import timezone
from pasien.models import BillingItem, PembatalanTagihan, TindakanAsesmen
from .igd_assessment_workflow import WorkflowConflict
from sdm.services.professional_care import has_grant,require_scope


def charge_state(unit_total,is_free):
    if unit_total is None:return 'PENDING'
    if unit_total==0 and is_free:return 'FREE'
    if unit_total<=0 or is_free:raise ValidationError('Nol bukan tarif gratis tanpa persetujuan.')
    return 'POSTED'


def professional_billing_summary(visit):
    categories={k:{'gross':Decimal('0'),'void':Decimal('0'),'net':Decimal('0')} for k in ('MEDICAL','NURSING','OTHER_PPA','DRUG_BMHP','ANCILLARY','ACCOMMODATION','ADMIN','LEGACY_UNMAPPED')}
    total={'gross':Decimal('0'),'void':Decimal('0'),'net':Decimal('0'),'categories':categories,'pending':0,'free':0,'planned_estimate':Decimal('0'),'planned_unknown':0}
    for line in visit.tindakan_asesmen.filter(execution_status='PLANNED'):
        if line.tarif_efektif is None:total['planned_unknown']+=1
        else:total['planned_estimate']+=(line.tarif_efektif*line.quantity).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    for item in visit.billing.all():
        category=(item.professional_price_snapshot.get('professional_context') or {}).get('group')
        if category not in categories:category={'OBAT':'DRUG_BMHP','LAB':'ANCILLARY','RADIOLOGI':'ANCILLARY','KAMAR':'ACCOMMODATION','ADMIN':'ADMIN'}.get(item.kategori,'LEGACY_UNMAPPED')
        gross=(item.kuantitas*item.harga_satuan).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
        row={'gross':gross,'void':gross if item.is_void else Decimal('0'),'net':item.subtotal}
        for key,value in row.items():total[key]+=value;categories[category][key]+=value
    states=visit.tindakan_asesmen.values_list('financial_status',flat=True)
    for state in states:
        if state=='PENDING':total['pending']+=1
        if state=='FREE':total['free']+=1
    return total


def void_authorized(actor,visit,service):
    require_scope(actor,visit)
    if not has_grant(actor,visit,'VOID_UNPAID_CHARGE',at=timezone.now(),service=service,for_update=True):raise PermissionDenied('Grant koreksi tagihan tidak tersedia.')


def _void_charge(visit,workflow,actor,data,request_id):
    line=TindakanAsesmen.objects.select_for_update().filter(kunjungan=visit,billing_item_id=data.get('billing_id'),professional_service__isnull=False).first()
    if not line:raise PermissionDenied('Tagihan bukan milik layanan profesional episode ini.')
    void_authorized(actor,visit,line.professional_service)
    item=BillingItem.objects.select_for_update().get(pk=line.billing_item_id,kunjungan=visit)
    if not item.professional_price_snapshot:raise PermissionDenied('Tagihan bukan milik handler profesional.')
    reason=data.get('reason','')
    if not isinstance(reason,str) or not 5<=len(reason.strip())<=2000:raise ValidationError('Alasan koreksi wajib 5–2000 karakter.')
    if hasattr(visit,'discharge'):raise WorkflowConflict('Episode dengan proses discharge tidak dapat di-void di sini.')
    existing=PembatalanTagihan.objects.filter(item=item).first()
    if existing:return {'void_id':existing.pk,'billing_id':item.pk}
    if item.is_void:raise WorkflowConflict('Proyeksi void tanpa audit memerlukan rekonsiliasi.')
    amount=(item.kuantitas*item.harga_satuan).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    if str(item.professional_price_snapshot.get('subtotal'))!=str(amount):
        if Decimal(str(item.professional_price_snapshot.get('subtotal')))!=amount:raise WorkflowConflict('Nominal asli tidak konsisten dengan snapshot.')
    record=PembatalanTagihan.objects.create(item=item,action=line,actor=actor,amount=amount,reason=reason.strip(),request_id=request_id)
    item.is_void=True;item.save(professional_update=True,update_fields=['is_void'])
    line.financial_status='VOID';line.save(professional_update=True,update_fields=['financial_status'])
    return {'void_id':record.pk,'billing_id':item.pk}


def void_professional_charge(actor,billing_id,expected_version,request_id,reason):
    from .igd_actions import perform_action
    item=BillingItem.objects.get(pk=billing_id)
    return perform_action(item.kunjungan_id,actor,'professional_void',{'billing_id':item.pk,'reason':reason},expected_version,request_id)
