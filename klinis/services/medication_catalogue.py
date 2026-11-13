from django.db.models import Q
from django.utils import timezone
from klinis.models import KelasTerapiObat, GenerikObat, ProdukFarmasi


def product_snapshot(product):
    if not (product.active and product.reviewed_by_id and product.source_version and product.generik.active and product.generik.kelas.active):
        raise ValueError('Produk belum aktif atau belum direview.')
    return {'id':product.pk,'kode':product.kode,'nama':product.nama,'kind':product.kind,
        'generic':product.generik.nama,'generic_id':product.generik_id,'class_code':product.generik.kelas.kode,
        'form':product.generik.bentuk,'unit':product.generik.dispense_unit,
        'conversion':product.generik.conversion,'flags':product.flags,'tall_man_label':product.tall_man_label,
        'allowed_routes':product.allowed_routes,'kfa_code':product.kfa_code,'source_version':product.source_version,
        'price':str(product.price) if product.price is not None else None,
        'ingredients':[{'ingredient_code':i.ingredient_code,'nama':i.nama,'strength':str(i.strength),'unit':i.unit} for i in product.ingredients.all()]}


def medication_choices(actor, *, visit, kind, parent_id=None, query='', page=1, level='class', formulary=''):
    if kind not in ('OBAT','RACIKAN','BMHP') or level not in ('class','generic','product') or page < 1 or len(query)>200:
        raise ValueError('Parameter katalog obat tidak valid.')
    category='BMHP' if kind=='BMHP' else 'OBAT'
    if level=='class':
        qs=KelasTerapiObat.objects.filter(active=True,kind=category)
    elif level=='generic':
        qs=GenerikObat.objects.filter(active=True,kelas_id=parent_id,kelas__active=True,kelas__kind=category)
    else:
        qs=ProdukFarmasi.objects.select_related('generik__kelas').filter(active=True,reviewed_by__isnull=False,
            generik_id=parent_id,generik__active=True,generik__kelas__active=True,kind=category).exclude(source_version='')
        if formulary:
            if formulary not in ('FORNAS','RS'):
                raise ValueError('Formularium tidak valid.')
            today=timezone.localdate()
            qs=qs.filter(formularies__jenis=formulary,formularies__valid_from__lte=today).filter(
                Q(formularies__valid_to__isnull=True)|Q(formularies__valid_to__gte=today)).distinct()
    if query:
        qs=qs.filter(Q(kode__icontains=query)|Q(nama__icontains=query))
    rows=list(qs.order_by('kode')[(page-1)*50:page*50+1])
    return {'results':[product_snapshot(r) if level=='product' else {'id':r.pk,'kode':r.kode,'nama':r.nama} for r in rows[:50]],
            'page':page,'has_more':len(rows)>50}
