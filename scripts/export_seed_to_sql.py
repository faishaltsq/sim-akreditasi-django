import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from sdm.models import MasterProfesiPegawai, MasterJenjangProfesi, KatalogTindakan

def escape_str(val):
    if val is None:
        return "NULL"
    escaped = str(val).replace("'", "''")
    return f"'{escaped}'"

# 1. MasterProfesiPegawai
profesi_rows = []
for p in MasterProfesiPegawai.objects.all().order_by('id'):
    code = escape_str(p.code)
    nama = escape_str(p.nama)
    keluarga = escape_str(p.keluarga)
    profesi_rows.append(
        f"INSERT INTO sdm_masterprofesipegawai (code, nama, keluarga, is_active, created_at, updated_at) "
        f"VALUES ({code}, {nama}, {keluarga}, TRUE, NOW(), NOW()) "
        f"ON CONFLICT (code) DO UPDATE SET nama = EXCLUDED.nama, keluarga = EXCLUDED.keluarga, updated_at = NOW();"
    )

# 2. MasterJenjangProfesi
jenjang_rows = []
for j in MasterJenjangProfesi.objects.select_related('profesi').all().order_by('profesi__code', 'urutan'):
    p_code = escape_str(j.profesi.code)
    kode = escape_str(j.kode)
    nama = escape_str(j.nama)
    urutan = j.urutan
    fokus = escape_str(j.fokus_kompetensi)
    preceptor_min = j.preceptor_min_urutan
    jenjang_rows.append(
        f"INSERT INTO sdm_masterjenjangprofesi (id, kode, nama, urutan, fokus_kompetensi, preceptor_min_urutan, profesi_id, created_at, updated_at) "
        f"SELECT gen_random_uuid(), {kode}, {nama}, {urutan}, {fokus}, {preceptor_min}, p.id, NOW(), NOW() "
        f"FROM sdm_masterprofesipegawai p WHERE p.code = {p_code} "
        f"ON CONFLICT (profesi_id, kode) DO UPDATE SET nama = EXCLUDED.nama, urutan = EXCLUDED.urutan, "
        f"fokus_kompetensi = EXCLUDED.fokus_kompetensi, preceptor_min_urutan = EXCLUDED.preceptor_min_urutan, updated_at = NOW();"
    )

# 3. KatalogTindakan
katalog_rows = []
for k in KatalogTindakan.objects.select_related('jenjang__profesi').all().order_by('kode'):
    p_code = escape_str(k.jenjang.profesi.code)
    j_code = escape_str(k.jenjang.kode)
    kode = escape_str(k.kode)
    nama = escape_str(k.nama)
    spv = escape_str(k.tingkat_supervisi)
    catatan = escape_str(k.catatan)
    katalog_rows.append(
        f"INSERT INTO sdm_katalogtindakan (id, kode, nama, tingkat_supervisi, catatan, is_active, jenjang_id, created_at, updated_at) "
        f"SELECT gen_random_uuid(), {kode}, {nama}, {spv}, {catatan}, TRUE, j.id, NOW(), NOW() "
        f"FROM sdm_masterjenjangprofesi j "
        f"JOIN sdm_masterprofesipegawai p ON p.id = j.profesi_id "
        f"WHERE p.code = {p_code} AND j.kode = {j_code} "
        f"ON CONFLICT (kode) DO UPDATE SET nama = EXCLUDED.nama, tingkat_supervisi = EXCLUDED.tingkat_supervisi, "
        f"catatan = EXCLUDED.catatan, jenjang_id = EXCLUDED.jenjang_id, updated_at = NOW();"
    )

print(f"Generated {len(profesi_rows)} profesi, {len(jenjang_rows)} jenjang, {len(katalog_rows)} katalog SQLs")

with open('scripts/supabase_seed_profesi.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(profesi_rows))

with open('scripts/supabase_seed_jenjang.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(jenjang_rows))

with open('scripts/supabase_seed_katalog.sql', 'w', encoding='utf-8') as f:
    f.write('\n'.join(katalog_rows))
