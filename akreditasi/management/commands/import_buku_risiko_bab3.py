"""
Management command: import_buku_risiko_bab3

Imports 333 standardized risk register records from
docs/risiko_buku_bab3_extracted.json (extracted from
Downloads/buku manajemen resiko rs.docx, Bab III onwards)
into RisikoUnit, creating/resolving UnitKerja as needed.

Usage:
    python manage.py import_buku_risiko_bab3
    python manage.py import_buku_risiko_bab3 --dry-run
    python manage.py import_buku_risiko_bab3 --tahun 2026
    python manage.py import_buku_risiko_bab3 --json-path /custom/path.json
"""

import json
import os
import re
from django.core.management.base import BaseCommand
from django.db import transaction
from django.contrib.auth import get_user_model

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit

User = get_user_model()

# ---------------------------------------------------------------------------
# Category mapping: book text → model KATEGORI_CHOICES key
# ---------------------------------------------------------------------------
KATEGORI_MAP = {
    'klinis':               'KLINIS',
    'clinical':             'KLINIS',
    'klinik':               'KLINIS',
    'manajerial':           'MANAJERIAL',
    'manajemen':            'MANAJERIAL',
    'operasional':          'OPERASIONAL',
    'finansial':            'FINANSIAL',
    'keuangan':             'FINANSIAL',
    'reputasi':             'REPUTASI',
    'hukum':                'HUKUM_KEPATUHAN',
    'hukum & kepatuhan':    'HUKUM_KEPATUHAN',
    'hukum dan kepatuhan':  'HUKUM_KEPATUHAN',
    'kepatuhan':            'HUKUM_KEPATUHAN',
    'fasilitas':            'FASILITAS_LINGKUNGAN',
    'fasilitas & lingkungan': 'FASILITAS_LINGKUNGAN',
    'lingkungan':           'FASILITAS_LINGKUNGAN',
    'k3':                   'FASILITAS_LINGKUNGAN',
}

# Default grading when explicit D/P columns are absent
DEFAULT_GRADING = {
    'KLINIS':               {'dampak': 4, 'probabilitas': 3},   # Skor 12 – Tinggi
    'OPERASIONAL':          {'dampak': 3, 'probabilitas': 3},   # Skor  9 – Sedang
    'FINANSIAL':            {'dampak': 3, 'probabilitas': 3},   # Skor  9 – Sedang
    'REPUTASI':             {'dampak': 3, 'probabilitas': 2},   # Skor  6 – Sedang
    'HUKUM_KEPATUHAN':      {'dampak': 3, 'probabilitas': 2},   # Skor  6 – Sedang
    'FASILITAS_LINGKUNGAN': {'dampak': 4, 'probabilitas': 2},   # Skor  8 – Tinggi
    'MANAJERIAL':           {'dampak': 3, 'probabilitas': 3},   # Skor  9 – Sedang
}

# ---------------------------------------------------------------------------
# section → UnitKerja name lookup (maps sub_heading to a search term)
# Order matters: more specific first
# ---------------------------------------------------------------------------
SECTION_UNIT_MAP = {
    '3.1 Tim Audit Operasional':            'Tim Audit',
    '3.2 Tim Audit Medik':                  'Tim Audit Medik',
    '3.3.1 Sub-Tim Mutu':                   'Sub-Tim Mutu',
    '3.3.2 Sub-Tim Keselamatan':            'Sub-Tim Keselamatan',
    '3.3.3 Sub-Tim Pencegahan':             'Sub-Tim PPI',
    '3.4.1 Subbag Hukum':                   'Hukum',
    '3.4.2 Subbag Sekretariat':             'Sekretariat',
    '3.2.1.1 Subbag Rekrutmen':             'Rekrutmen',
    '3.2.1.2 Subbag Pengembangan SDM':      'Pengembangan SDM',
    '3.2.2.1 Subbag Rumah Tangga':          'Rumah Tangga',
    '3.2.2.2 Subbag Sarana Prasarana':      'Sarana Prasarana',
    '3.2.2.3 Subbag Kesling':               'Kesling',
    '3.2.3.1 Subbag Pelatihan':             'Pelatihan',
    '3.2.3.2 Subbag Penelitian':            'Penelitian',
    '3.3.1.2 Subbag Perbendaharaan':        'Perbendaharaan',
    '4.1  Seksi Pelayanan Rawat Jalan':     'Rawat Jalan',
    '4.1.1 Poliklinik Penyakit Dalam':      'Penyakit Dalam',
    '4.1.2 Poliklinik Bedah':               'Bedah',
    '4.1.3 Poliklinik Kesehatan Anak':      'Anak',
    '4.1.4 Poliklinik Obstetri':            'Obgyn',
    '4.1.5 Poliklinik Spesialis Lain':      'Poliklinik Spesialis',
    '4.1.6 Poliklinik Gigi':               'Gigi',
    '4.1.7 Unit Rehabilitasi':              'Rehabilitasi',
    '4.2 Seksi Pelayanan Gawat Darurat':    'Gawat Darurat',
    '4.2.1 Unit Triase':                    'Triase',
    '4.3  Bidang Keperawatan':              'Keperawatan',
    '4.4  Bidang Pelayanan Penunjang':      'Penunjang Medik',
    '4.4 Instalasi Perawatan Intensif':     'ICU',
    '4.5.1 Bangsal Perawatan VIP':          'VIP',
    '4.5.2 Bangsal Dewasa Non-Bedah':       'Bangsal Dewasa',
    '4.5.2.1 Ruang Perawatan Pria':         'Pria',
    '4.5.2.2 Ruang Perawatan Wanita':       'Wanita',
    '4.5.3 Bangsal Perawatan Bedah':        'Bangsal Bedah',
    '4.5.3.1 Ruang Bedah':                  'Ruang Bedah',
    '7.1 Bagian Keuangan':                  'Keuangan',
    '7.2 Bagian Akuntansi':                 'Akuntansi',
    '7.2.2 Subbag Verifikasi':              'Verifikasi',
    '8.1 Subbag SIMRS':                     'IT',
    '1. Sub-Unit 4.6.1.1 Unit Patologi':    'Patologi',
    '2. Sub-Unit 4.6.1.2 Unit Bank Darah':  'Bank Darah',
    '4. Sub-Unit 4.6.2.2 Unit CT-Scan':     'CT-Scan',
}

# Cache so we don't hit DB on every row
_unit_cache: dict[str, UnitKerja] = {}


def resolve_unit(sub_heading: str, chapter_heading: str) -> UnitKerja | None:
    """Return the best-matching UnitKerja for a section heading.
    Strategy:
      1. Exact cache hit
      2. SECTION_UNIT_MAP keyword → DB icontains search
      3. Fallback: first token after the section number
      4. Create a new LAINNYA unit if nothing found
    """
    cache_key = sub_heading.strip()
    if cache_key in _unit_cache:
        return _unit_cache[cache_key]

    # Find keyword from map
    search_term = None
    for prefix, kw in SECTION_UNIT_MAP.items():
        if sub_heading.startswith(prefix):
            search_term = kw
            break

    if not search_term:
        # Extract words after section number like "4.1.1"
        clean = re.sub(r'^[\d\.]+\s*', '', sub_heading).strip()
        search_term = clean[:40] if clean else sub_heading[:40]

    # Try DB lookup
    qs = UnitKerja.objects.filter(name__icontains=search_term).order_by('level')
    if qs.exists():
        unit = qs.first()
        _unit_cache[cache_key] = unit
        return unit

    # Fallback: broader search using sub_heading words
    words = [w for w in re.split(r'[\s&,]+', sub_heading) if len(w) > 4]
    for word in words:
        qs = UnitKerja.objects.filter(name__icontains=word).order_by('level')
        if qs.exists():
            unit = qs.first()
            _unit_cache[cache_key] = unit
            return unit

    # Create new unit if truly missing
    clean_name = re.sub(r'^[\d\.]+\s*', '', sub_heading).strip()
    # Generate a unique code from the name
    base_code = re.sub(r'[^A-Z0-9]', '-', clean_name.upper())[:20].strip('-')
    # Ensure uniqueness with a suffix
    code = base_code
    suffix = 1
    while UnitKerja.objects.filter(code=code).exists():
        code = f'{base_code[:17]}-{suffix:02d}'
        suffix += 1
    unit = UnitKerja.objects.create(
        name=clean_name[:200],
        code=code,
        tipe_unit='LAINNYA',
    )
    _unit_cache[cache_key] = unit
    return unit


def normalize_row(raw: dict) -> dict:
    """Normalize a raw extracted table row to RisikoUnit field values."""
    raw_kat = (raw.get('Kategori Risiko') or '').strip().lower()
    kategori = KATEGORI_MAP.get(raw_kat, 'MANAJERIAL')

    grading = DEFAULT_GRADING.get(kategori, {'dampak': 3, 'probabilitas': 3})
    # If the row itself has D/P values (Bab II style tables), prefer those
    dampak = int(raw['Dampak (D)']) if raw.get('Dampak (D)', '').isdigit() else grading['dampak']
    probabilitas = int(raw['Probabilitas (P)']) if raw.get('Probabilitas (P)', '').isdigit() else grading['probabilitas']

    jenis_risiko = (raw.get('Jenis Risiko') or '').strip()
    deskripsi = (raw.get('Deskripsi Risiko') or '').strip()
    indikator = (raw.get('Indikator Mutu') or '').strip()
    strategi = (raw.get('Strategi Mitigasi') or '').strip()
    rencana = (raw.get('Rencana Aksi') or raw.get('Rencana Aksi (Min. 2 Langkah)') or raw.get('Rencana Aksi (3 Langkah)') or '').strip()

    # Append indicator text to rencana_aksi if it contains useful detail
    if indikator and indikator not in rencana:
        rencana = f"{rencana}\n[Indikator: {indikator}]".strip() if rencana else f"[Indikator: {indikator}]"

    return {
        'kategori_risiko': kategori,
        'jenis_risiko': jenis_risiko[:200],
        'deskripsi_risiko': deskripsi or jenis_risiko,
        'dampak': dampak,
        'probabilitas': probabilitas,
        'strategi_mitigasi': strategi[:500] if strategi else 'Risk Control',
        'rencana_aksi': rencana or '-',
        'pj_mitigasi': 'Kepala Unit',
        'status': 'IDENTIFIKASI',
    }


# ---------------------------------------------------------------------------
# Management command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Import risk register records from Buku Manajemen Risiko RS (Bab III onwards)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dry_run',
            default=False,
            help='Simulate import without committing to DB.',
        )
        parser.add_argument(
            '--tahun',
            type=int,
            default=2026,
            help='Tahun for imported risk records (default: 2026)',
        )
        parser.add_argument(
            '--periode',
            default='SEMESTER_1',
            help='Periode for imported risk records (default: SEMESTER_1)',
        )
        parser.add_argument(
            '--json-path',
            default=None,
            dest='json_path',
            help='Path to extracted JSON file (default: docs/risiko_buku_bab3_extracted.json)',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        tahun = options['tahun']
        periode = options['periode']

        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)
        ))))
        json_path = options.get('json_path') or os.path.join(
            base_dir, 'docs', 'risiko_buku_bab3_extracted.json'
        )

        if not os.path.exists(json_path):
            self.stderr.write(self.style.ERROR(f'JSON file not found: {json_path}'))
            return

        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Filter Bab III+ only
        rows = [r for r in data if 'BAB II' not in r.get('unit_heading', '')]
        self.stdout.write(f'Loaded {len(rows)} rows from Bab III+')

        created = 0
        updated = 0
        skipped = 0
        errors = 0

        # Get or create a system user for created_by
        system_user = User.objects.filter(is_superuser=True).first()

        try:
            with transaction.atomic():
                for row in rows:
                    try:
                        fields = normalize_row(row)
                        if not fields['jenis_risiko']:
                            skipped += 1
                            continue

                        unit = resolve_unit(
                            row.get('sub_heading', ''),
                            row.get('unit_heading', ''),
                        )
                        if unit is None:
                            skipped += 1
                            continue

                        lookup = {
                            'unit': unit,
                            'tahun': tahun,
                            'jenis_risiko': fields['jenis_risiko'],
                        }
                        defaults = {
                            'periode': periode,
                            'kategori_risiko': fields['kategori_risiko'],
                            'deskripsi_risiko': fields['deskripsi_risiko'],
                            'dampak': fields['dampak'],
                            'probabilitas': fields['probabilitas'],
                            'strategi_mitigasi': fields['strategi_mitigasi'],
                            'rencana_aksi': fields['rencana_aksi'],
                            'pj_mitigasi': fields['pj_mitigasi'],
                            'status': fields['status'],
                            'biaya_mitigasi': 0,
                        }
                        if system_user:
                            defaults['created_by'] = system_user

                        _, was_created = RisikoUnit.objects.update_or_create(
                            **lookup, defaults=defaults
                        )
                        if was_created:
                            created += 1
                        else:
                            updated += 1

                    except Exception as e:
                        self.stderr.write(f'  ERROR row ({row.get("Jenis Risiko", "?")}): {e}')
                        errors += 1

                if dry_run:
                    self.stdout.write(self.style.WARNING(
                        f'\n[DRY RUN] Rolling back. Would create: {created}, update: {updated}, skip: {skipped}, error: {errors}'
                    ))
                    raise transaction.TransactionManagementError('dry-run rollback')

        except transaction.TransactionManagementError:
            pass  # expected dry-run rollback
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Import complete — created: {created}, updated: {updated}, skipped: {skipped}, errors: {errors}'
            ))
