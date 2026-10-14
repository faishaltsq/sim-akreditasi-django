"""
Management command: import_instrumen_2024
Parses Kemenkes 2024 accreditation instrument PDF and idempotently imports
all Categories (Bab), StandardItems (Standar + EP), into the database.

Usage:
    python manage.py import_instrumen_2024 --pdf-path "path/to/instrumen.pdf"
    python manage.py import_instrumen_2024 --pdf-path "..." --dry-run
    python manage.py import_instrumen_2024 --pdf-path "..." --category TKRS
"""
import re
import json
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from akreditasi.models import Framework, Category, StandardItem, EvidenceReq


BAB_META = {
    'TKRS':    {'name': 'Tata Kelola Rumah Sakit',                  'order': 1,  'kelompok': 'MANAJEMEN'},
    'KPS':     {'name': 'Kualifikasi & Pendidikan Staf',             'order': 2,  'kelompok': 'MANAJEMEN'},
    'MFK':     {'name': 'Manajemen Fasilitas & Keselamatan',         'order': 3,  'kelompok': 'MANAJEMEN'},
    'PMKP':    {'name': 'Peningkatan Mutu & Keselamatan Pasien',     'order': 4,  'kelompok': 'MANAJEMEN'},
    'MRMIK':   {'name': 'Manajemen Informasi & Rekam Medis',         'order': 5,  'kelompok': 'MANAJEMEN'},
    'PPI':     {'name': 'Pencegahan & Pengendalian Infeksi',         'order': 6,  'kelompok': 'MANAJEMEN'},
    'AKP':     {'name': 'Akses dan Kontinuitas Pelayanan',           'order': 7,  'kelompok': 'PELAYANAN'},
    'HPK':     {'name': 'Hak Pasien dan Keluarga',                   'order': 8,  'kelompok': 'PELAYANAN'},
    'PP':      {'name': 'Pengkajian Pasien',                         'order': 9,  'kelompok': 'PELAYANAN'},
    'PAP':     {'name': 'Pelayanan dan Asuhan Pasien',               'order': 10, 'kelompok': 'PELAYANAN'},
    'PAB':     {'name': 'Pelayanan Anestesi dan Bedah',              'order': 11, 'kelompok': 'PELAYANAN'},
    'PKPO':    {'name': 'Pelayanan Kefarmasian & Penggunaan Obat',   'order': 12, 'kelompok': 'PELAYANAN'},
    'KE':      {'name': 'Komunikasi dan Edukasi',                    'order': 13, 'kelompok': 'PELAYANAN'},
    'SKP':     {'name': 'Sasaran Keselamatan Pasien',                'order': 14, 'kelompok': 'SASARAN_KP'},
    'PROGNAS': {'name': 'Program Nasional',                          'order': 15, 'kelompok': 'PROGNAS'},
    'PPK':     {'name': 'Pendidikan dalam Pelayanan Kesehatan',      'order': 16, 'kelompok': 'PENDIDIKAN'},
}

# Legacy prefix aliases (old code → new code)
LEGACY_ALIASES = {
    'ARK': 'AKP',
    'IPKP': 'PPK',
    'MIRM': 'MRMIK',
}


def parse_pdf(pdf_path: str) -> dict:
    """
    Parse the 2024 accreditation instrument PDF.
    Returns dict: {standard_code: [{'letter', 'description', 'evidence_types'}]}
    """
    try:
        import pypdf
    except ImportError:
        raise CommandError("pypdf not installed. Run: pip install pypdf")

    reader = pypdf.PdfReader(pdf_path)
    all_text = '\n'.join(page.extract_text() or '' for page in reader.pages)

    # Match EP section headers — handles:
    # "Elemen Penilaian TKRS 1"
    # "Elemen penilaian SKP.1"  (dot separator)
    # "Elemen Penilaian Standar Prognas 1.1"
    ep_header_re = re.compile(
        r'[Ee]lemen\s+[Pp]enilaian\s+(?:[Ss]tandar\s+)?([A-Za-z]+)[\s.]+(\d+(?:\.\d+)?)',
        re.IGNORECASE
    )

    found = [(m.start(), m.group(1).upper(), m.group(2)) for m in ep_header_re.finditer(all_text)]
    found.sort(key=lambda x: x[0])

    ep_data = {}

    for idx, (pos, prefix, num) in enumerate(found):
        # Normalise prefix aliases
        prefix = LEGACY_ALIASES.get(prefix, prefix)
        if prefix not in BAB_META:
            continue

        code = f'{prefix} {num}'
        next_pos = found[idx + 1][0] if idx + 1 < len(found) else len(all_text)
        block = all_text[pos:next_pos]

        # Trim block before next Standar declaration
        cutoff = re.search(
            r'\n\s*(?:[a-z]\.|\d+\))\s*[Ss]tandar\s+[A-Za-z]', block
        )
        if cutoff:
            block = block[:cutoff.start()]

        items = _extract_ep_items(block)

        # Keep the richest parse (most items) for duplicate headers
        if code not in ep_data or len(items) > len(ep_data[code]):
            ep_data[code] = items if items else [{'letter': '1', 'description': '', 'evidence_types': []}]

    return ep_data


def _extract_ep_items(block: str) -> list:
    """
    Extract individual EP sub-items from an EP block.
    Handles both:
      a) Lettered bullets   a) b) c) ...  (most chapters)
      1) Numbered bullets   1) 2) 3) ...  (SKP)
    """
    items = []

    # Try lettered first
    for m in re.finditer(
        r'(?:^|\n)\s*([a-z])\)\s+(.*?)(?=\n\s*[a-z]\)|\n\s*(?:[a-z]\.|\d+\))\s*[Ss]tandar|\Z)',
        block, re.DOTALL
    ):
        letter = m.group(1)
        raw = m.group(2)
        desc = re.sub(r'\s+', ' ', raw).strip()[:300]
        rdwos = sorted(set(re.findall(r'\b([RDWOS])\b', raw[:200])))
        items.append({'letter': letter, 'description': desc, 'evidence_types': rdwos})

    if items:
        return items

    # Fallback: numbered bullets (SKP style)
    for m in re.finditer(
        r'(?:^|\n)\s*(\d+)\)\s+(.*?)(?=\n\s*\d+\)|\n\s*(?:[a-z]\.|\d+\))\s*[Ss]tandar|\Z)',
        block, re.DOTALL
    ):
        num = m.group(1)
        raw = m.group(2)
        desc = re.sub(r'\s+', ' ', raw).strip()[:300]
        rdwos = sorted(set(re.findall(r'\b([RDWOS])\b', raw[:200])))
        items.append({'letter': num, 'description': desc, 'evidence_types': rdwos})

    return items


def sort_code_key(code: str):
    """Numeric sort key for standard codes like 'TKRS 7.1'."""
    prefix = code.split()[0]
    num_part = code.split()[1] if len(code.split()) > 1 else '0'
    parts = [float(x) for x in num_part.split('.')]
    order = BAB_META.get(prefix, {}).get('order', 99)
    return (order, *parts)


class Command(BaseCommand):
    help = 'Import 2024 Kemenkes hospital accreditation standards & EP from PDF'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pdf-path',
            type=str,
            default=str(Path.home() / 'Downloads' / 'instrumen standar survey akreditasi  rs 2024.pdf'),
            help='Path to instrumen PDF file',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview changes without saving to database',
        )
        parser.add_argument(
            '--category',
            type=str,
            default=None,
            help='Limit import to a single chapter code (e.g. TKRS)',
        )
        parser.add_argument(
            '--framework-name',
            type=str,
            default='STARKES Edisi 2022 / Kemenkes RI',
            help='Framework name to attach standards to',
        )

    def handle(self, *args, **options):
        pdf_path = options['pdf_path']
        dry_run = options['dry_run']
        only_category = options['category'].upper() if options['category'] else None
        framework_name = options['framework_name']

        if not Path(pdf_path).exists():
            raise CommandError(f"PDF not found: {pdf_path}")

        self.stdout.write(f"📄 Parsing PDF: {pdf_path}")
        ep_data = parse_pdf(pdf_path)
        self.stdout.write(f"✅ Parsed {len(ep_data)} standards from PDF")

        # Filter by category if requested
        if only_category:
            ep_data = {k: v for k, v in ep_data.items() if k.startswith(only_category + ' ')}
            self.stdout.write(f"🔍 Filtered to category {only_category}: {len(ep_data)} standards")

        if dry_run:
            self._dry_run_report(ep_data)
            return

        with transaction.atomic():
            self._import(ep_data, framework_name)

    def _dry_run_report(self, ep_data: dict):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("DRY RUN — no changes written")
        self.stdout.write("=" * 60)

        bab_summary = defaultdict(lambda: {'std': 0, 'ep': 0})
        for code, items in ep_data.items():
            prefix = code.split()[0]
            bab_summary[prefix]['std'] += 1
            bab_summary[prefix]['ep'] += len(items)

        grand_std = grand_ep = 0
        for prefix in sorted(bab_summary, key=lambda p: BAB_META.get(p, {}).get('order', 99)):
            s = bab_summary[prefix]
            name = BAB_META.get(prefix, {}).get('name', prefix)
            self.stdout.write(f"  {prefix:8s} {name:45s} {s['std']:3d} std  {s['ep']:4d} EP")
            grand_std += s['std']
            grand_ep += s['ep']

        self.stdout.write("-" * 60)
        self.stdout.write(f"  {'TOTAL':8s} {grand_std:3d} standards  {grand_ep:4d} EP")

        # Compare against DB
        db_ep = StandardItem.objects.count()
        self.stdout.write(f"\n  DB current: {db_ep} EP | PDF 2024: {grand_ep} EP | Gap: +{grand_ep - db_ep}")

    def _import(self, ep_data: dict, framework_name: str):
        # Get or create framework
        framework, _ = Framework.objects.get_or_create(
            name=framework_name,
            defaults={'version': '2024', 'cycle_type': 'PDCA'}
        )

        stats = {'cat_created': 0, 'cat_updated': 0, 'std_created': 0, 'std_updated': 0, 'ep_total': 0}

        # Group by bab prefix
        bab_standards = defaultdict(list)
        for code in sorted(ep_data.keys(), key=sort_code_key):
            prefix = code.split()[0]
            bab_standards[prefix].append(code)

        for prefix, codes in bab_standards.items():
            if prefix not in BAB_META:
                self.stdout.write(self.style.WARNING(f"  Skip unknown prefix: {prefix}"))
                continue

            meta = BAB_META[prefix]

            # Upsert Category
            cat, created = Category.objects.update_or_create(
                code=prefix,
                defaults={
                    'name': meta['name'],
                    'order': meta['order'],
                    'kelompok': meta['kelompok'],
                    'framework': framework,
                }
            )
            if created:
                stats['cat_created'] += 1
                self.stdout.write(self.style.SUCCESS(f"  [NEW BAB]  {prefix} - {meta['name']}"))
            else:
                stats['cat_updated'] += 1

            # Upsert each StandardItem (EP)
            ep_order = 1
            for code in codes:
                items = ep_data[code]
                std_num = code.split()[1]

                for ep in items:
                    ep_code = f"{code} EP {ep['letter']}"
                    ep_desc = ep['description'] or f"Elemen Penilaian {ep_code}"

                    std_item, created = StandardItem.objects.update_or_create(
                        category=cat,
                        code=ep_code,
                        defaults={
                            'sub_standard': code,
                            'sub_title': '',
                            'description': ep_desc[:500],
                            'order': ep_order,
                        }
                    )

                    if created:
                        stats['std_created'] += 1
                    else:
                        stats['std_updated'] += 1

                    # Upsert EvidenceReq records for each RDWOS type
                    for ev_type in ep['evidence_types']:
                        EvidenceReq.objects.get_or_create(
                            standard_item=std_item,
                            category_type=ev_type,
                            defaults={'title': f'Bukti {ev_type} — {ep_code}', 'is_mandatory': True}
                        )

                    stats['ep_total'] += 1
                    ep_order += 1

            self.stdout.write(
                f"  {prefix:8s}  {len(codes):3d} std  "
                f"{sum(len(ep_data[c]) for c in codes):4d} EP"
            )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            f"✅ IMPORT COMPLETE\n"
            f"   Categories : {stats['cat_created']} created, {stats['cat_updated']} updated\n"
            f"   StandardItem: {stats['std_created']} created, {stats['std_updated']} updated\n"
            f"   Total EP    : {stats['ep_total']}"
        )
