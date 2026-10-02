"""
Insert data Indikator Mutu dari BAB INDIKATOR MUTU bagian 1
ke database Supabase secara terstruktur dan lengkap.
"""
import os, sys, django, json, re
from decimal import Decimal

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DATABASE_URL'] = (
    'postgresql://postgres.gwaeuzbbdawbekrmrvfd:Keqingwangy1*'
    '@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require'
)
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from akreditasi.models import IndikatorMutu, UnitKerja

with open('indikator_data.json', encoding='utf-8') as f:
    records = json.load(f)

# ── Map Dimensi Mutu ───────────────────────────────────────────────────────
def get_dimensi(text: str) -> str:
    low = text.lower()
    if 'safety' in low or 'keselamatan' in low or 'aman' in low:
        return 'AMAN'
    if 'waktu' in low or 'cepat' in low or 'tat' in low or 'tunggu' in low:
        return 'TEPAT_WAKTU'
    if 'efisien' in low or 'biaya' in low or 'anggaran' in low:
        return 'EFISIEN'
    if 'akses' in low:
        return 'AKSESIBEL'
    if 'pasien' in low or 'kepuasan' in low:
        return 'BERPUSAT_PASIEN'
    return 'EFEKTIF'

# ── Parse Nilai Target (Decimal) ──────────────────────────────────────────
def parse_target(text: str) -> tuple[Decimal, str]:
    # Cari persentase misal "≥ 90%" atau "100%"
    m_pct = re.search(r'(\d+(?:[.,]\d+)?)\s*%', text)
    if m_pct:
        val = m_pct.group(1).replace(',', '.')
        return Decimal(val), '%'
    # Cari menit
    m_mnt = re.search(r'(\d+(?:[.,]\d+)?)\s*menit', text, re.IGNORECASE)
    if m_mnt:
        val = m_mnt.group(1).replace(',', '.')
        return Decimal(val), 'menit'
    # Cari hari
    m_hari = re.search(r'(\d+(?:[.,]\d+)?)\s*hari', text, re.IGNORECASE)
    if m_hari:
        val = m_hari.group(1).replace(',', '.')
        return Decimal(val), 'hari'
    # Default 100% jika zero incident
    if 'zero' in text.lower() or '0' in text:
        return Decimal('100.00'), '%'
    return Decimal('80.00'), '%'

# ── Clean Helper ───────────────────────────────────────────────────────────
def clean(t: str) -> str:
    if not t:
        return ''
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    return '\n'.join(lines)

# ── Build/Find UnitKerja ───────────────────────────────────────────────────
unit_cache = {u.name.lower(): u for u in UnitKerja.objects.all()}

def get_or_create_unit(raw_unit: str) -> UnitKerja:
    name_clean = re.sub(r'\s*\(\d[\d.]*\)', '', raw_unit).strip()
    key = name_clean.lower()
    
    if key in unit_cache:
        return unit_cache[key]
    
    # Partial match
    words = set(re.findall(r'\w+', key))
    best_unit = None
    best_score = 0
    for uname, uobj in unit_cache.items():
        uwords = set(re.findall(r'\w+', uname))
        score = len(words & uwords)
        if score > best_score and score >= 2:
            best_score = score
            best_unit = uobj
    
    if best_unit and best_score >= 2:
        unit_cache[key] = best_unit
        return best_unit
    
    # Buat unit baru jika belum ada
    new_unit = UnitKerja.objects.create(
        name=name_clean[:100],
        tipe_unit='PENUNJANG' if 'penunjang' in key or 'subbag' in key or 'tim' in key else 'MEDIS'
    )
    unit_cache[key] = new_unit
    print(f'  [+UNIT] {name_clean}')
    return new_unit

# ── Sequence Counter ──────────────────────────────────────────────────────
seq_counter = {}

def generate_kode(unit_name: str) -> str:
    # Prefix 4-6 huruf dari nama unit
    words = re.findall(r'[A-Za-z]+', unit_name)
    prefix = ''.join(w[0] for w in words[:4]).upper()
    if len(prefix) < 3:
        prefix = (unit_name[:4]).upper()
    prefix = f"IMP-{prefix}"
    seq_counter[prefix] = seq_counter.get(prefix, 0) + 1
    return f"{prefix}-{seq_counter[prefix]:02d}"

# ── Main Loop ─────────────────────────────────────────────────────────────
inserted_count = 0
updated_count = 0

print("Mulai proses insert/update indikator...")
for r in records:
    raw_unit = r['unit_kerja']
    indikator_str = clean(r['indikator'])
    rencana_str = clean(r['rencana_aksi'])
    pj_str = clean(r['pj'])

    if not indikator_str:
        continue

    unit_obj = get_or_create_unit(raw_unit)
    target_val, satuan_val = parse_target(indikator_str)
    dimensi = get_dimensi(indikator_str)

    # Cek apakah nama indikator mirip sudah ada
    short_name = indikator_str[:80]
    existing = IndikatorMutu.objects.filter(nama_indikator__icontains=short_name[:40]).first()

    if existing:
        # Update rencana aksi dan pj jika belum ada
        if not existing.rencana_aksi and rencana_str:
            existing.rencana_aksi = rencana_str
            existing.pj = pj_str or existing.pj
            existing.save(update_fields=['rencana_aksi', 'pj'])
            updated_count += 1
            print(f'  [UPDATE] {existing.kode_indikator} | {existing.nama_indikator[:50]}')
        continue

    # Create new
    kode = generate_kode(unit_obj.name)
    # Pastikan kode unik
    while IndikatorMutu.objects.filter(kode_indikator=kode).exists():
        seq_counter[kode.rsplit('-', 1)[0]] += 1
        kode = f"{kode.rsplit('-', 1)[0]}-{seq_counter[kode.rsplit('-', 1)[0]]:02d}"

    IndikatorMutu.objects.create(
        kode_indikator=kode,
        nama_indikator=indikator_str[:300],
        unit=unit_obj,
        jenis='IMP_UNIT',
        dimensi_mutu=dimensi,
        numerator='Jumlah capaian sesuai kriteria standar indikator',
        denominator='Jumlah seluruh sampel/populasi yang diobservasi',
        target_nilai=target_val,
        satuan=satuan_val,
        rencana_aksi=rencana_str,
        pj=pj_str[:200],
        aktif=True
    )
    inserted_count += 1
    print(f'  [INSERT] {kode} | ({unit_obj.name[:25]}) | {indikator_str[:50]}')

print("\n" + "="*50)
print(f"Total Baru Diinsert  : {inserted_count}")
print(f"Total Diupdate       : {updated_count}")
total_skrg = IndikatorMutu.objects.count()
print(f"Total Indikator di DB: {total_skrg}")
print("="*50)
