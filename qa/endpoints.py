"""Inventory endpoint untuk QA fleet testing.

Daftar URL diturunkan dari router Django, bukan ditulis tangan, supaya tidak
menyimpang saat route berubah. Lihat `refresh()`.
"""
import re

# Path yang mengubah state atau menghasilkan file. Tidak boleh di-GET pada
# fase baca karena efeknya nyata (hapus, setujui, ekspor, dsb).
SKIP_PATTERN = re.compile(
    r'logout|delete|hapus|update|toggle|reset|create|download|cetak|pdf|csv|'
    r'export|/baru/|/buat/|/lapor/|upload|scoring|verifikasi|setujui|simpan|'
    r'batal|checkin|disposisi|proses|regenerasi|tarik|analisis|seksi|sertifikat|'
    r'finalkan|putuskan|ajukan|psv|kewenangan|aktivitas|tandai|/ai/',
    re.I,
)

# 12 URL yang mewakili setiap modul inti. Dipakai fase sanity, dengan
# assertion isi (bukan hanya status code).
SANITY_URLS = [
    '/dashboard/',
    '/control/',
    '/control/risiko/',
    '/control/emr/',
    '/matriks/',
    '/risiko/',
    '/rekap/',
    '/indikator-mutu/',
    '/laporan-mutu/',
    '/logbook/',
    '/pencarian/',
    '/human-capital/',
]

# Endpoint JSON/API yang diuji pada fase API.
# (method, url, butuh_json)
API_ENDPOINTS = [
    ('GET', '/risiko/api/indikator-by-unit/', True),
    ('GET', '/api/mutu-indikator/', True),
    ('GET', '/indikator-mutu/api/komparasi-unit/', True),
    ('GET', '/pasien/api/cari/', True),
    ('GET', '/pasien/api/cek-nik/', True),
    ('GET', '/pasien/api/cek-bpjs/', True),
    ('GET', '/pasien/api/bed-tersedia/', True),
    ('GET', '/pasien/api/icd10/', True),
    ('GET', '/pasien/api/sdki/', True),
    ('GET', '/pasien/api/parse-qr/', True),
    ('GET', '/pasien/bpjs/cek-peserta/', True),
    ('GET', '/pasien/integrasi/status/', True),
    ('GET', '/ai/test-connection/', False),
    ('POST', '/ai/test-connection/', True),
    ('POST', '/ai/ep-rekomendasi/', True),
    ('POST', '/ai/ep-terapkan/', True),
    ('POST', '/ai/ep-lepas/', True),
    ('POST', '/ai/narasi-laporan/', True),
    ('POST', '/ai/mitigasi-risiko/', True),
    ('POST', '/ai/pdca-plan/', True),
    ('POST', '/ai/insiden-grading/', True),
    ('POST', '/ai/risiko-fmea-saran/', True),
    ('POST', '/ai/risiko-rca-saran/', True),
    ('POST', '/ai/evaluasi-risiko/', True),
    ('POST', '/ai/rdwos-analisis/', True),
    ('POST', '/ai/rumus-indikator/', True),
]


def walk(res, prefix=''):
    for p in res.url_patterns:
        pat = prefix + str(p.pattern)
        if hasattr(p, 'url_patterns'):
            # Pattern hasil include() tidak membawa leading slash, sehingga
            # 'risiko/' + 'pelaksanaan/' menjadi 'risikopelaksanaan/'.
            if not pat.endswith('/'):
                pat += '/'
            yield from walk(p, pat)
        else:
            yield pat


def discover_smoke_urls():
    """Turunkan daftar GET aman dari router. Harus dipanggil setelah django.setup()."""
    from django.urls import get_resolver

    out = set()
    for u in walk(get_resolver()):
        if u.startswith('admin-sikai'):
            continue
        if '<' in u or '^' in u or '(' in u:
            continue
        if SKIP_PATTERN.search(u):
            continue
        # include() tanpa prefix menghasilkan path tanpa leading slash
        out.add('/' + u.lstrip('/'))
    return sorted(out)


# Nilai default agar modul bisa diimpor tanpa Django siap. Runner akan
# memanggil discover_smoke_urls() dan memakai hasilnya bila tersedia.
SMOKE_URLS = []
