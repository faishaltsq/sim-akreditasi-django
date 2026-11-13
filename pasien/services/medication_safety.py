from collections import Counter
from decimal import Decimal
from klinis.models import MedicationPolicy


def active_policy():
    return MedicationPolicy.objects.filter(active=True).order_by('-pk').first()


def current_catalogue_risks(prescription):
    products={}
    for row in prescription.items.select_related('product__generik__kelas').prefetch_related('components__produk__generik__kelas'):
        for product in [row.product,*[part.produk for part in row.components.all()]]:
            if product:
                products[product.pk]={'id':product.pk,'flags':product.flags,
                    'active':bool(product.active and product.reviewed_by_id and product.source_version and product.generik.active and product.generik.kelas.active),
                    'ingredients':list(product.ingredients.order_by('ingredient_code').values('ingredient_code','strength','unit'))}
    return [products[pk] for pk in sorted(products)]


def evaluate_prescription(prescription, policy=None):
    policy=policy or active_policy()
    visit=prescription.kunjungan
    rows=list(prescription.items.select_related('product__generik__kelas').all())
    findings=[]; ingredients=[]; classes=[]
    current={product['id']:product for product in current_catalogue_risks(prescription)}
    def add(code,message,blocking=False,review=False):
        if not any(r['code']==code and r['message']==message for r in findings):
            findings.append({'code':code,'message':message,'blocking':blocking,'requires_ack':review})
    allergies=list(visit.pasien.structured_allergies.filter(active=True))
    if (visit.skrining_alergi_status!='TIDAK_ADA' or visit.pasien.alergi_obat.strip() or visit.alergi_asesmen.strip()) and not allergies:
        add('ALLERGY_UNRESOLVED','Riwayat alergi belum dipetakan; tinjauan klinis diperlukan.',review=True)
    for row in rows:
        snap=row.product_snapshot
        component_snapshots=[part['product'] for part in snap.get('components',[])] if row.kind=='RACIKAN' else [snap]
        flags=set(snap.get('flags',[]))
        for source in component_snapshots:
            live=current.get(source.get('id'),{})
            if not live.get('active'):
                add('CATALOGUE_UNAVAILABLE','Produk/komponen tidak aktif atau belum dipetakan; tinjau resep.',blocking=True)
            signature=lambda items:{(item['ingredient_code'],Decimal(str(item['strength'])),item['unit']) for item in items}
            if signature(live.get('ingredients',[]))!=signature(source.get('ingredients',[])):
                add('CATALOGUE_CHANGED','Komposisi/kekuatan master berubah; simpan ulang draft setelah review.',blocking=True)
            flags.update(live.get('flags',[]))
        codes={part['ingredient_code'] for part in snap.get('ingredients',[])}
        ingredients.extend(codes); cls=snap.get('class_code'); therapy_classes={source.get('class_code') for source in component_snapshots}
        classes.extend(therapy_classes)
        if any((a.ingredient_code and a.ingredient_code in codes) or
               (a.therapy_class_code and a.therapy_class_code in therapy_classes) for a in allergies):
            add('ALLERGY','Produk sesuai riwayat alergi terstruktur.',blocking=True)
        for flag in flags:
            if flag=='PPRA':
                add('PPRA','Produk memerlukan persetujuan PPRA.',blocking=True)
            else:
                add('RISK_'+flag,'Risiko produk: '+flag,review=True)
        if policy and any(source.get('kode') in policy.rules.get('ppra_products',[]) for source in component_snapshots):
            add('PPRA','Produk dibatasi kebijakan PPRA '+policy.version,blocking=True)
    if any(n>1 for n in Counter(ingredients).values()):
        add('DUPLICATE_INGREDIENT','Zat aktif berulang pada resep ini.',review=True)
    if any(cls and n>1 for cls,n in Counter(classes).items()):
        add('THERAPY_OVERLAP','Kelas terapi berulang; verifikasi tujuan kombinasi.',review=True)
    return findings
