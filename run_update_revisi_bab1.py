import docx, json, re, os, sys, django
from decimal import Decimal

doc = docx.Document('C:/Users/cubeb/Downloads/BAB INDIKATOR MUTU dan rencana aksi bagian 1.docx')

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DATABASE_URL'] = (
    'postgresql://postgres.gwaeuzbbdawbekrmrvfd:Keqingwangy1*'
    '@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require'
)
sys.path.insert(0, 'C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django')
django.setup()

from akreditasi.models import IndikatorMutu, UnitKerja

def clean(t): return '\n'.join(l.strip() for l in t.splitlines() if l.strip())

def get_dimensi(txt):
    low = txt.lower()
    if any(k in low for k in ['safety','keselamatan','aman','zero','jatuh','infeksi','ppi']): return 'AMAN'
    if any(k in low for k in ['waktu','tunggu','tat','respon','cepat']): return 'TEPAT_WAKTU'
    if any(k in low for k in ['efisien','biaya','anggaran']): return 'EFISIEN'
    if any(k in low for k in ['akses']): return 'AKSESIBEL'
    if any(k in low for k in ['kepuasan','pasien','berpusat']): return 'BERPUSAT_PASIEN'
    return 'EFEKTIF'

def parse_target(txt):
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*%', txt)
    if m: return Decimal(m.group(1).replace(',','.')), '%'
    m = re.search(r'(\d+)\s*menit', txt, re.I)
    if m: return Decimal(m.group(1)), 'menit'
    m = re.search(r'(\d+)\s*hari', txt, re.I)
    if m: return Decimal(m.group(1)), 'hari'
    if 'zero' in txt.lower(): return Decimal('100'), '%'
    return Decimal('90'), '%'

unit_cache = {u.name.lower(): u for u in UnitKerja.objects.all()}

def find_unit(raw):
    name = re.sub(r'\s*\(\d[\d.]*\)', '', raw).strip()
    key = name.lower()
    if key in unit_cache: return unit_cache[key]
    words = set(re.findall(r'\w+', key))
    best, bscore = None, 0
    for uname, uobj in unit_cache.items():
        sc = len(words & set(re.findall(r'\w+', uname)))
        if sc > bscore and sc >= 2: bscore, best = sc, uobj
    if best:
        unit_cache[key] = best
        return best
    new = UnitKerja.objects.create(name=name[:100], tipe_unit='PENUNJANG')
    unit_cache[key] = new
    return new

seq = {}
def gen_kode(uname):
    words = re.findall(r'[A-Za-z]+', uname)
    prefix = 'IMP-' + ''.join(w[0] for w in words[:4]).upper()
    seq[prefix] = seq.get(prefix, 0) + 1
    kode = f"{prefix}-{seq[prefix]:02d}"
    while IndikatorMutu.objects.filter(kode_indikator=kode).exists():
        seq[prefix] += 1
        kode = f"{prefix}-{seq[prefix]:02d}"
    return kode

records = []
for ti, table in enumerate(doc.tables):
    rows = table.rows
    if len(rows) < 2: continue
    hdr = [c.text.strip() for c in rows[0].cells]
    ncols = len(hdr)
    if ncols >= 7:
        ci_jenis, ci_ind, ci_aksi = 4, 5, 6
    else:
        ci_jenis, ci_ind, ci_aksi = None, 4, 5

    for ri in range(1, len(rows)):
        cells = [c.text.strip() for c in rows[ri].cells]
        if len(cells) <= ci_ind: continue
        ind_txt = clean(cells[ci_ind])
        if not ind_txt or ind_txt == hdr[ci_ind]: continue
        records.append({
            'table_idx': ti,
            'unit_raw': cells[1] if len(cells) > 1 else '',
            'pj': clean(cells[2]) if len(cells) > 2 else '',
            'jenis_raw': clean(cells[ci_jenis]) if ci_jenis and len(cells) > ci_jenis else '',
            'indikator': ind_txt,
            'rencana_aksi': clean(cells[ci_aksi]) if len(cells) > ci_aksi else '',
        })

print(f"Extracted {len(records)} records dari dokumen revisi")

db_all = {ind.nama_indikator[:60].lower(): ind for ind in IndikatorMutu.objects.all()}

inserted = updated = skipped = 0
for rec in records:
    unit_obj = find_unit(rec['unit_raw'])
    ind_text = rec['indikator']
    rencana = rec['rencana_aksi']
    pj_val = rec['pj'][:200] if rec['pj'] else ''

    key60 = ind_text[:60].lower()
    existing = db_all.get(key60) or next(
        (ind for k, ind in db_all.items() if (ind_text[:35].lower() in k or k[:35] in key60)), None
    )

    if existing:
        changed = False
        if rencana and rencana != existing.rencana_aksi:
            existing.rencana_aksi = rencana
            changed = True
        if pj_val and pj_val != existing.pj:
            existing.pj = pj_val
            changed = True
        if len(ind_text) > len(existing.nama_indikator):
            existing.nama_indikator = ind_text[:300]
            changed = True
        if changed:
            existing.save()
            updated += 1
            print(f"  [UPDATE] {existing.kode_indikator} | {ind_text[:55]}")
        else:
            skipped += 1
        continue

    target_val, satuan_val = parse_target(ind_text)
    jenis_dok = rec.get('jenis_raw','')
    if 'Nasional' in jenis_dok or 'INM' in jenis_dok.upper(): jenis = 'NASIONAL'
    elif 'Prioritas' in jenis_dok or 'RS' in jenis_dok: jenis = 'IMP_RS'
    else: jenis = 'IMP_UNIT'

    kode = gen_kode(unit_obj.name)
    ind_obj = IndikatorMutu.objects.create(
        kode_indikator=kode,
        nama_indikator=ind_text[:300],
        unit=unit_obj,
        jenis=jenis,
        dimensi_mutu=get_dimensi(ind_text),
        numerator='Jumlah capaian sesuai kriteria standar',
        denominator='Jumlah seluruh sampel yang diobservasi',
        target_nilai=target_val,
        satuan=satuan_val,
        rencana_aksi=rencana,
        pj=pj_val,
        aktif=True,
    )
    db_all[ind_text[:60].lower()] = ind_obj
    inserted += 1
    print(f"  [INSERT] {kode} | ({unit_obj.name[:20]}) | {ind_text[:50]}")

total = IndikatorMutu.objects.count()
print(f"\n{'='*55}")
print(f"Insert baru  : {inserted}")
print(f"Update       : {updated}")
print(f"Skip (sama)  : {skipped}")
print(f"Total DB     : {total}")
print(f"{'='*55}")
