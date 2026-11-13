from django.core.exceptions import ValidationError
from django.db.models import Q
from klinis.models import KategoriPenunjang, ItemPenunjang


def item_snapshot(item):
    node = item.group
    path = []
    for level in (3,2,1):
        if node is None or node.level != level or not node.active:
            raise ValueError('Hierarki pemeriksaan tidak aktif atau tidak sesuai.')
        path.insert(0, {'id':node.pk,'kode':node.kode,'nama':node.nama})
        node = node.parent
    if node is not None:
        raise ValueError('Hierarki pemeriksaan tidak valid.')
    return {'id':item.pk,'kode':item.kode,'nama':item.nama,'path':path,
            'jenis_order':item.jenis_order,'destination_id':item.destination_id,
            'source_version':item.source_version,'is_panel':item.is_panel,
            'preparation_schema':item.preparation_schema,'variants':item.variants}


def resolve_items(user, item_ids):
    if not isinstance(item_ids,list) or not 1 <= len(item_ids) <= 50 or any(type(pk) is not int or pk < 1 for pk in item_ids):
        raise ValueError('Pilih satu sampai 50 item pemeriksaan.')
    if len(set(item_ids)) != len(item_ids):
        raise ValueError('Item berulang dalam satu batch; kirim permintaan ulang terpisah bila perlu.')
    rows = {r.pk:r for r in ItemPenunjang.objects.select_related('group__parent__parent','destination').filter(pk__in=item_ids)}
    result=[]
    for pk in item_ids:
        item=rows.get(pk)
        if not item or not item.active or not item.reviewed_by_id or not item.source_version or not item.destination_id:
            raise ValueError('Pemeriksaan belum aktif, belum direview atau belum memiliki tujuan.')
        item_snapshot(item)
        result.append(item)
    return result


def list_choices(user, *, parent_id=None, query='', page=1):
    if type(page) is not int or page < 1 or len(query) > 200:
        raise ValueError('Parameter pencarian tidak valid.')
    if parent_id is None:
        qs=KategoriPenunjang.objects.filter(parent=None,active=True)
        leaf=False
    else:
        parent=KategoriPenunjang.objects.filter(pk=parent_id,active=True).first()
        if parent is None:
            raise ValueError('Induk pemeriksaan tidak aktif.')
        node=parent
        while node:
            if not node.active:
                raise ValueError('Induk pemeriksaan tidak aktif.')
            node=node.parent
        leaf=parent.level==3
        qs=(ItemPenunjang.objects.filter(group=parent,active=True,reviewed_by__isnull=False,destination__isnull=False).exclude(source_version='') if leaf
            else KategoriPenunjang.objects.filter(parent=parent,active=True))
    if query:
        qs=qs.filter(Q(kode__icontains=query)|Q(nama__icontains=query))
    rows=list(qs.order_by('kode')[(page-1)*50:page*50+1])
    return {'results':[item_snapshot(r) if leaf else {'id':r.pk,'kode':r.kode,'nama':r.nama,'level':r.level} for r in rows[:50]],
            'page':page,'has_more':len(rows)>50,'leaf':leaf}
