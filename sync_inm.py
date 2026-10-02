"""
Sinkronisasi 13 Indikator Mutu Nasional (INM) dengan PJ dan Rencana Aksi
dari dokumen 'indikator mutu nasional dengan rencana aksi.docx'.
"""
import docx, os, sys, django, re

os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
os.environ['DATABASE_URL'] = (
    'postgresql://postgres.gwaeuzbbdawbekrmrvfd:Keqingwangy1*'
    '@aws-0-ap-northeast-2.pooler.supabase.com:5432/postgres?sslmode=require'
)
sys.path.insert(0, 'C:/Users/cubeb/OneDrive/Documents/coding/sim-akreditasi-django')
django.setup()

from akreditasi.models import IndikatorMutu, UnitKerja

doc = docx.Document('C:/Users/cubeb/Downloads/indikator mutu nasional dengan rencana aksi.docx')
table = doc.tables[0]

def clean(t):
    return '\n'.join(l.strip() for l in t.splitlines() if l.strip())

# Extract 13 items
items = []
for ri in range(1, len(table.rows)):
    cells = [c.text.strip() for c in table.rows[ri].cells]
    no = int(cells[0])
    nama = clean(cells[1])
    pj = clean(cells[2])
    unit_terkait = clean(cells[3])
    aksi = clean(cells[4])
    items.append({
        'no': no,
        'nama': nama,
        'pj': pj,
        'unit_terkait': unit_terkait,
        'aksi': aksi
    })

print(f"Total item terbaca: {len(items)}")

# Mapping kata kunci ke kode INM
KEYWORDS_MAP = [
    (1, ['kebersihan tangan', 'hand hygiene'], 'INM-01'),
    (2, ['alat pelindung diri', 'apd'], 'INM-02'),
    (3, ['identifikasi pasien'], 'INM-03'),
    (4, ['seksio sesarea', 'sc elektif', 'operasi sc'], 'INM-04'),
    (5, ['rawat jalan', 'waktu tunggu'], 'INM-06'),
    (6, ['penundaan operasi elektif', 'operasi elektif'], 'INM-05'),
    (7, ['visite dokter spesialis', 'dpjp'], 'INM-13'), # atau buat baru / pakai slot kosong
    (8, ['hasil kritis', 'laboratorium', 'critical value'], 'INM-12'),
    (9, ['formularium nasional', 'fornas'], 'INM-07'),
    (10, ['clinical pathway'], 'INM-08'),
    (11, ['pasien jatuh', 'risiko jatuh'], 'INM-09'),
    (12, ['waktu tanggap komplain', 'komplain'], 'INM-10'),
    (13, ['kepuasan pasien', 'ikm'], 'INM-11'),
]

# Update ke database
for item in items:
    no = item['no']
    nama = item['nama']
    pj = item['pj']
    aksi = item['aksi']
    
    # Cari INM di DB yang cocok
    target_obj = None
    for num, kws, kode in KEYWORDS_MAP:
        if num == no:
            # Cari by kode dulu
            target_obj = IndikatorMutu.objects.filter(kode_indikator=kode).first()
            if not target_obj:
                # Cari by keyword di nama_indikator
                for kw in kws:
                    target_obj = IndikatorMutu.objects.filter(nama_indikator__icontains=kw, jenis='NASIONAL').first()
                    if target_obj:
                        break
            break

    if target_obj:
        target_obj.pj = pj
        target_obj.rencana_aksi = aksi
        # Update nama agar sesuai dokumen terbaru jika lebih representatif
        target_obj.nama_indikator = nama
        target_obj.jenis = 'NASIONAL'
        target_obj.save()
        print(f"  [UPDATED] {target_obj.kode_indikator} | {nama[:45]} | PJ: {pj[:30]}")
    else:
        # Jika belum ada, buat baru
        kode = f"INM-{no:02d}"
        new_ind = IndikatorMutu.objects.create(
            kode_indikator=kode,
            nama_indikator=nama,
            jenis='NASIONAL',
            dimensi_mutu='AMAN',
            numerator='Capaian pemenuhan standar INM',
            denominator='Total sampel observasi',
            target_nilai=100.00 if '100' in nama or 'zero' in nama.lower() else 85.00,
            satuan='%',
            pj=pj,
            rencana_aksi=aksi,
            aktif=True
        )
        print(f"  [CREATED] {kode} | {nama[:45]} | PJ: {pj[:30]}")

print("\nVerifikasi 13 INM di DB:")
for ind in IndikatorMutu.objects.filter(jenis='NASIONAL').order_by('kode_indikator'):
    print(f"  {ind.kode_indikator:8s} | {ind.nama_indikator[:50]:50s} | PJ: {ind.pj[:25]:25s} | Aksi: {len(ind.rencana_aksi)} chars")
