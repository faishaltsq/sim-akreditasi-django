"""
Management command: import_instrumen_2024
Parses Kemenkes 2024 accreditation instrument PDF and idempotently imports
all Categories (Bab), StandardItems (Standar + EP), into the database.

Usage:
    python manage.py import_instrumen_2024 --pdf-path "path/to/instrumen.pdf"
    python manage.py import_instrumen_2024 --pdf-path "..." --dry-run
    python manage.py import_instrumen_2024 --pdf-path "..." --category TKRS

Replacing the 2022 catalogue with 2024:
    python manage.py import_instrumen_2024 --pdf-path "..." --replace --dry-run
    python manage.py import_instrumen_2024 --pdf-path "..." --replace \
        --mapping-report var/starkes-2024-mapping.json

`--replace` deactivates the previous framework, imports 2024 as the active
catalogue, and moves QualityRecord scores only where the EP code exists in both
editions. Everything else is written to the mapping report for manual review;
no row is deleted.
"""
import json
import re
from collections import defaultdict
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from akreditasi.models import (
    Category,
    EvidenceReq,
    Framework,
    QualityRecord,
    StandardItem,
)


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

FRAMEWORK_NAME_2024 = 'STARKES Edisi 2024 / KMK HK.01.07/MENKES/1596/2024'
FRAMEWORK_VERSION_2024 = '2024'

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

    ep_header_re = re.compile(
        r'[Ee]lemen\s+[Pp]enilaian\s+(?:[Ss]tandar\s+)?([A-Za-z]+)[\s.]+(\d+(?:\.\d+)?)',
        re.IGNORECASE
    )

    found = [(m.start(), m.group(1).upper(), m.group(2)) for m in ep_header_re.finditer(all_text)]
    found.sort(key=lambda x: x[0])

    ep_data = {}

    for idx, (pos, prefix, num) in enumerate(found):
        prefix = LEGACY_ALIASES.get(prefix, prefix)
        if prefix not in BAB_META:
            continue

        code = f'{prefix} {num}'
        next_pos = found[idx + 1][0] if idx + 1 < len(found) else len(all_text)
        block = all_text[pos:next_pos]

        cutoff = re.search(
            r'\n\s*(?:[a-z]\.|\d+\))\s*[Ss]tandar\s+[A-Za-z]', block
        )
        if cutoff:
            block = block[:cutoff.start()]

        items = _extract_ep_items(block)

        if code not in ep_data or len(items) > len(ep_data[code]):
            ep_data[code] = items if items else [{'letter': '1', 'description': '', 'evidence_types': []}]

    return ep_data


def _extract_ep_items(block: str) -> list:
    """
    Extract individual EP sub-items from an EP block.
    Handles:
      a) b) c) ...   lettered bullets (most chapters)
      1) 2) 3) ...   numbered bullets (SKP)
      1. 2. 3. ...   dotted numbering (PROGNAS)
    """
    items = []

    # Lettered first. A repeated letter means the block ran into the next
    # standard's EP list (the PDF prints some EP lists on the page before their
    # own header, e.g. MFK 4), so stop at the restart.
    seen = set()
    for m in re.finditer(
        r'(?:^|\n)\s*([a-z])\)\s+(.*?)(?=\n\s*[a-z]\)|\n\s*(?:[a-z]\.|\d+[.)])\s*[Ss]tandar|\Z)',
        block, re.DOTALL
    ):
        letter = m.group(1)
        if letter in seen:
            break
        seen.add(letter)
        raw = m.group(2)
        desc = re.sub(r'\s+', ' ', raw).strip()[:300]
        # "poin a) - e) pada maksud dan tujuan" is prose, not an EP item.
        if len(desc) < 25 and re.match(r'^(pada|dalam|di)\b', desc):
            continue
        rdwos = sorted(set(re.findall(r'\b([RDWOS])\b', raw[:200])))
        items.append({'letter': letter, 'description': desc, 'evidence_types': rdwos})

    if items:
        return items

    # Numbered bullets: "1)" (SKP) or "1." (PROGNAS)
    seen = set()
    for m in re.finditer(
        r'(?:^|\n)\s*(\d+)[.)]\s+(.*?)(?=\n\s*\d+[.)]|\n\s*(?:[a-z]\.|\d+[.)])\s*[Ss]tandar|\Z)',
        block, re.DOTALL
    ):
        num = m.group(1)
        if num in seen:
            break
        seen.add(num)
        raw = m.group(2)
        desc = re.sub(r'\s+', ' ', raw).strip()[:300]
        if not desc:
            continue
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
            default=str(Path.home() / 'Downloads' / 'starkes 2024.pdf'),
            help='Path to the STARKES 2024 PDF',
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
            default=FRAMEWORK_NAME_2024,
            help='Framework name to attach standards to',
        )
        parser.add_argument(
            '--replace',
            action='store_true',
            help=(
                'Make 2024 the active catalogue: deactivate other frameworks, '
                'move scores where EP codes match, and report the rest.'
            ),
        )
        parser.add_argument(
            '--mapping-report',
            type=str,
            default=None,
            help='Write the 2022→2024 score mapping report to this JSON path',
        )

    def handle(self, *args, **options):
        pdf_path = options['pdf_path']
        dry_run = options['dry_run']
        only_category = options['category'].upper() if options['category'] else None
        framework_name = options['framework_name']

        if not Path(pdf_path).exists():
            raise CommandError(f"PDF not found: {pdf_path}")

        self.stdout.write(f"Parsing PDF: {pdf_path}")
        ep_data = parse_pdf(pdf_path)
        self.stdout.write(f"Parsed {len(ep_data)} standards from PDF")

        if only_category:
            ep_data = {k: v for k, v in ep_data.items() if k.startswith(only_category + ' ')}
            self.stdout.write(f"Filtered to category {only_category}: {len(ep_data)} standards")

        if dry_run:
            self._dry_run_report(ep_data)
            return

        stats = self._import(ep_data, framework_name, replace=options['replace'])
        if options['replace']:
            self._replace(ep_data, framework_name, options['mapping_report'], stats)

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

        db_ep = StandardItem.objects.count()
        self.stdout.write(f"\n  DB current: {db_ep} EP | PDF 2024: {grand_ep} EP | Gap: +{grand_ep - db_ep}")

    def _import(self, ep_data: dict, framework_name: str, *, replace: bool = False):
        framework, _ = Framework.objects.get_or_create(
            name=framework_name,
            defaults={
                'version': FRAMEWORK_VERSION_2024,
                'cycle_type': 'PDCA',
                'is_active': False,
            },
        )

        # A code is globally unique. Capture score provenance before the legacy
        # codes are renamed, then retire them so 2024 rows can take the codes.
        if replace:
            self._capture_legacy_scores(framework)
            self._retire_legacy_codes(ep_data, framework)

        stats = {'cat_created': 0, 'cat_updated': 0, 'std_created': 0, 'std_updated': 0, 'ep_total': 0}

        bab_standards = defaultdict(list)
        for code in sorted(ep_data.keys(), key=sort_code_key):
            prefix = code.split()[0]
            bab_standards[prefix].append(code)

        for prefix, codes in bab_standards.items():
            if prefix not in BAB_META:
                self.stdout.write(self.style.WARNING(f"  Skip unknown prefix: {prefix}"))
                continue

            with transaction.atomic():
                meta = BAB_META[prefix]

                cat, created = Category.objects.update_or_create(
                    framework=framework,
                    code=prefix,
                    defaults={
                        'name': meta['name'],
                        'order': meta['order'],
                        'kelompok': meta['kelompok'],
                    },
                )
                if created:
                    stats['cat_created'] += 1
                    self.stdout.write(self.style.SUCCESS(f"  [NEW BAB]  {prefix} - {meta['name']}"))
                else:
                    stats['cat_updated'] += 1

                ep_order = 1
                for code in codes:
                    for ep in ep_data[code]:
                        ep_code = f"{code} EP {ep['letter']}"
                        ep_desc = ep['description'] or f"Elemen Penilaian {ep_code}"

                        std_item, created = StandardItem.objects.update_or_create(
                            code=ep_code,
                            defaults={
                                'category': cat,
                                'sub_standard': code,
                                'sub_title': '',
                                'description': ep_desc[:500],
                                'order': ep_order,
                            },
                        )

                        if created:
                            stats['std_created'] += 1
                        else:
                            stats['std_updated'] += 1

                        for ev_type in ep['evidence_types']:
                            EvidenceReq.objects.get_or_create(
                                standard_item=std_item,
                                category_type=ev_type,
                                defaults={
                                    'title': f'Bukti {ev_type} — {ep_code}',
                                    'is_mandatory': True,
                                },
                            )

                        stats['ep_total'] += 1
                        ep_order += 1

            self.stdout.write(
                f"  {prefix:8s}  {len(codes):3d} std  "
                f"{sum(len(ep_data[c]) for c in codes):4d} EP"
            )

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(
            f"IMPORT COMPLETE\n"
            f"   Categories  : {stats['cat_created']} created, {stats['cat_updated']} updated\n"
            f"   StandardItem: {stats['std_created']} created, {stats['std_updated']} updated\n"
            f"   Total EP    : {stats['ep_total']}"
        )
        return stats

    def _capture_legacy_scores(self, framework):
        """Snapshot 2022 scores by original code before codes are renamed."""
        self._legacy_scores = [
            {
                'code': record.standard_item.code,
                'framework_id': record.standard_item.category.framework_id,
                'record_id': record.pk,
                'unit_id': record.unit_id,
                'unit': record.unit.code,
                'score': record.score,
                'payload': {
                    'score': record.score,
                    'baseline_data': record.baseline_data,
                    'quality_target': record.quality_target,
                    'risk_mitigation': record.risk_mitigation,
                    'eval_notes': record.eval_notes,
                    'action_plan': record.action_plan,
                    'pic': record.pic,
                    'target_date': record.target_date,
                    'est_cost': record.est_cost,
                    'budget_source': record.budget_source,
                    'budget_status': record.budget_status,
                },
            }
            for record in QualityRecord.objects.exclude(
                standard_item__category__framework=framework
            ).select_related('standard_item', 'unit')
        ]
        self.stdout.write(f"  Captured {len(self._legacy_scores)} legacy score rows")

    def _retire_legacy_codes(self, ep_data, framework):
        """Rename colliding codes from older frameworks so they stay queryable."""
        codes = {
            f"{std} EP {ep['letter']}"
            for std, items in ep_data.items()
            for ep in items
        }
        legacy = StandardItem.objects.exclude(
            category__framework=framework
        ).filter(code__in=codes).select_related('category__framework')

        for item in legacy:
            # Label by the edition the framework claims, not by a stray version
            # string such as '2026'; fall back to the framework id.
            edition = (item.category.framework.version or '').split('-')[0]
            if not edition.isdigit():
                edition = str(item.category.framework_id)
            item.code = f"{item.code} [{edition}]"
            item.save(update_fields=['code'])

        if legacy:
            self.stdout.write(
                f"  Archived {len(legacy)} colliding 2022 codes as '<code> [2022]'"
            )

    def _replace(self, ep_data: dict, framework_name: str, report_path, stats):
        """Make 2024 active, carry over matching scores, report the rest."""
        framework = Framework.objects.get(name=framework_name)
        previous = list(Framework.objects.exclude(pk=framework.pk))

        new_by_code = {
            item.code: item
            for item in StandardItem.objects.filter(category__framework=framework)
        }

        moved, unmatched = [], []
        for entry in getattr(self, '_legacy_scores', []):
            target = new_by_code.get(entry['code'])
            if target is None:
                unmatched.append({
                    'code': entry['code'],
                    'unit': entry['unit'],
                    'score': entry['score'],
                })
                continue
            # QualityRecord is one-per-StandardItem, so move the existing row
            # onto the 2024 item instead of inserting a second one.
            record = QualityRecord.objects.filter(
                standard_item__code=entry['code'],
                standard_item__category__framework_id=entry['framework_id'],
            ).first()
            if record is None:
                record = QualityRecord.objects.filter(
                    standard_item__code__startswith=entry['code'] + ' [',
                    standard_item__category__framework_id=entry['framework_id'],
                ).first()
            if record is None:
                unmatched.append({
                    'code': entry['code'], 'unit': entry['unit'],
                    'score': entry['score'], 'reason': 'record not found',
                })
                continue
            if QualityRecord.objects.filter(standard_item=target).exists():
                unmatched.append({
                    'code': entry['code'], 'unit': entry['unit'],
                    'score': entry['score'], 'reason': 'target already scored',
                })
                continue
            for field, value in entry['payload'].items():
                setattr(record, field, value)
            record.standard_item = target
            record.save()
            moved.append({'code': entry['code'], 'unit': entry['unit'], 'score': entry['score']})

        previous_names = [f.name for f in previous]
        for old_framework in previous:
            version = (old_framework.version or 'lama').split('-')[0]
            old_framework.version = f'{version}-archived'
            old_framework.is_active = False
            old_framework.save(update_fields=['version', 'is_active'])
        framework.is_active = True
        framework.save(update_fields=['is_active'])

        report = {
            'framework': framework_name,
            'previous_frameworks': previous_names,
            'new_ep_count': len(new_by_code),
            'moved_count': len(moved),
            'unmatched_count': len(unmatched),
            'unmatched': unmatched,
        }
        if report_path:
            path = Path(report_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8'
            )
            self.stdout.write(f"Mapping report written: {path}")

        self.stdout.write(
            f"REPLACE COMPLETE\n"
            f"   Scores moved      : {len(moved)}\n"
            f"   Unmatched (manual): {len(unmatched)}\n"
            f"   Archived frameworks: {', '.join(previous_names) or '-'}"
        )
