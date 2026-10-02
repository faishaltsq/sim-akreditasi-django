"""
Insert data Indikator Mutu dari BAB INDIKATOR MUTU bagian 1
ke database Supabase.
Run: python insert_indikator_bab1.py
"""
import os, sys, django, json, re

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DATABASE_URL'] = (
    'postgresql://postgres.gwaeuzbbdawbekrmrvfd:Keqingwangy1*'
    '@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require'
)
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from akreditasi.models import IndikatorMutu, UnitKerja

# ── Load data ─────────────────────────────────────────────────────────────
with open('indikator_data.json', encoding='utf-8') as f:
    records = json.load(f)

# ── Build fuzzy unit lookup ────────────────────────────────────────────────
all_units = {u.name.lower(): u for u in UnitKerja.objects.all()}

def find_unit(raw: str) -> UnitKerja | None:
    """Match unit kerja dari string dokumen ke UnitKerja DB."""
    if not raw:
        return None
    raw_clean = raw.strip()
    # Hapus kode arsitektur dalam kurung, misal "(2.1.1.1)"
    raw_no_code = re.sub(r'\s*\(\d[\d.]*\)', '', raw_clean).strip().lower()

    # 1. Exact match
    if raw_no_code in all_units:
        return all_units[raw_no_code]

    # 2. Partial: cari unit yang namanya paling banyak kata match
    best, best_score = None, 0
    words = set(raw_no_code.split())
    for name, unit in all_units.items():
        score = len(words & set(name.split()))
        if score > best_score and score >= 2:
            best, best_score = unit, score
    return best

# ── Deteksi jenis indikator dari teks ──────────────────────────────────────
def detect_jenis(indikator: str) -> str:
    low = indikator.lower()
    if any(k in low for k in ['keselamatan', 'insiden', 'kti', 'zero', 'jatuh', 'infeksi', 'isk', 'idu', 'phlebitis', 'ppi']):
        return 'keselamatan_pasien'
    if any(k in low for k in ['kepuasan', 'komplain', 'edukasi', 'pkrs']):
        return 'manajemen'
    if any(k in low for k in ['waktu', 'tunggu', 'respon', 'tat', 'ketepatan']):
        return 'pelayanan'
    return 'klinis'

# ── Bersihkan rencana aksi ─────────────────────────────────────────────────
def clean_text(t: str) -> str:
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    return '\n'.join(lines)

# ── Auto-kode: format IMP-<UNIT>-<seq> ────────────────────────────────────
unit_seq: dict[str, int] = {}

def make_kode(unit_name: str, unit_obj) -> str:
    if unit_obj:
        key = re.sub(r'[^A-Za-z0-9]', '', unit_obj.name)[:8].upper()
    else:
        key = re.sub(r'[^A-Za-z0-9]', '', unit_name)[:8].upper()
    unit_seq[key] = unit_seq.get(key, 0) + 1
    return f"IMP-{key}-{unit_seq[key]:02d}"

# ── Target default dari teks indikator ────────────────────────────────────
def extract_target(indikator: str) -> str:
    # Cari pola seperti "≥ 90%", "100%", "≤ 5 menit"
    m = re.search(r'[≥≤<>]=?\s*[\d,.]+\s*(%|menit|hari|jam|kasus)?', indikator)
    return m.group(0).strip() if m else ''

# ── Insert ─────────────────────────────────────────────────────────────────
inserted = 0
skipped = 0
skipped_list = []

for rec in records:
    unit_raw = rec['unit_kerja']
    indikator_text = clean_text(rec['indikator'])
    rencana_aksi = clean_text(rec['rencana_aksi'])

    if not indikator_text:
        skipped += 1
        continue

    unit_obj = find_unit(unit_raw)
    kode = make_kode(unit_raw, unit_obj)

    # Skip jika sudah ada indikator dengan nama sama (case-insensitive, 80% match)
    existing = IndikatorMutu.objects.filter(
        nama_indikator__icontains=indikator_text[:40]
    ).exists()
    if existing:
        skipped += 1
        skipped_list.append(indikator_text[:60])
        continue

    ind = IndikatorMutu(
        kode_indikator=kode,
        nama_indikator=indikator_text[:500],
        jenis=detect_jenis(indikator_text),
        unit=unit_obj,
        target=extract_target(indikator_text) or '≥ 90%',
        numerator='Jumlah yang sesuai standar',
        denominator='Jumlah total yang diobservasi',
        rencana_aksi=rencana_aksi[:2000] if rencana_aksi else '',
        is_aktif=True,
    )
    ind.save()
    inserted += 1
    print(f'[OK] {kode} | {unit_raw[:40]} | {indikator_text[:60]}')

print(f'\n──────────────────────────────────────────────')
print(f'Inserted : {inserted}')
print(f'Skipped  : {skipped} (duplikat atau kosong)')
if skipped_list:
    print('Skipped items:')
    for s in skipped_list[:10]:
        print(f'  - {s}')
