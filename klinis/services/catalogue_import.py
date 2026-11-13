import json
from pathlib import Path
from django.db import transaction
from klinis.models import KategoriPenunjang,ItemPenunjang,KelasTerapiObat,GenerikObat,ProdukFarmasi


@transaction.atomic
def import_catalogue(kind,path,apply=False):
    data=json.loads(Path(path).read_text(encoding='utf-8'))
    if kind not in ('penunjang','medication') or not data.get('version') or not data.get('sha256') or len(data['sha256'])!=64:
        raise ValueError('Provenance katalog tidak valid.')
    keys=('nodes','items') if kind=='penunjang' else ('classes','generics','products')
    for key in keys:
        rows=data.get(key)
        if not isinstance(rows,list) or len(rows)>10000 or len({r['kode'] for r in rows})!=len(rows):
            raise ValueError('Katalog memuat kode berulang atau format tidak valid.')
    if not apply:
        return {'applied':False,'counts':{key:len(data[key]) for key in keys},'source_sha256':data['sha256']}
    created=0
    if kind=='penunjang':
        nodes={}
        for row in sorted(data['nodes'],key=lambda r:r['level']):
            parent=nodes.get(row.get('parent'))
            if row['level']>1 and parent is None:
                raise ValueError('Induk katalog tidak ditemukan.')
            obj,new=KategoriPenunjang.objects.get_or_create(kode=row['kode'],defaults={'nama':row['nama'],'level':row['level'],'parent':parent})
            if obj.level!=row['level'] or obj.parent_id!=(parent.pk if parent else None):
                raise ValueError('Kode kategori bertentangan dengan hierarki lokal.')
            obj.full_clean();nodes[row['kode']]=obj;created+=int(new)
        for row in data['items']:
            obj,new=ItemPenunjang.objects.get_or_create(kode=row['kode'],defaults={'nama':row['nama'],'group':nodes[row['group']],
                'jenis_order':row['jenis_order'],'is_panel':row['is_panel'],'source_note':row['source_note'],
                'source_version':data['version'],'active':False})
            if new:
                obj.full_clean()
            created+=int(new)
    else:
        classes={};generics={}
        for row in data['classes']:
            obj,new=KelasTerapiObat.objects.get_or_create(kode=row['kode'],defaults={'nama':row['nama'],'kind':row['kind']})
            classes[row['kode']]=obj;created+=int(new)
        for row in data['generics']:
            obj,new=GenerikObat.objects.get_or_create(kode=row['kode'],defaults={'nama':row['nama'],'kelas':classes[row['kelas']],
                'bentuk':row['bentuk'],'dispense_unit':row['dispense_unit'],'active':False})
            generics[row['kode']]=obj;created+=int(new)
        for row in data['products']:
            obj,new=ProdukFarmasi.objects.get_or_create(kode=row['kode'],defaults={'nama':row['nama'],'generik':generics[row['generik']],
                'kind':row['kind'],'source_note':row['source_note'],'source_version':data['version'],'active':False})
            if new:
                obj.full_clean()
            created+=int(new)
    return {'applied':True,'created':created,'counts':{key:len(data[key]) for key in keys},'source_sha256':data['sha256']}
