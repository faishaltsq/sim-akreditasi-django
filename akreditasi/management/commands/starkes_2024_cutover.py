"""Guarded STARKES 2024 catalogue cutover.

Runs the whole replacement in one auditable step:
  1. pre-flight snapshot of the current catalogue,
  2. optional dry-run,
  3. import + retire + score migration with a JSON report,
  4. post-flight verification,
  5. cache invalidation so the sidebar picks up the new catalogue.

Requires an explicit confirmation flag because it changes the active catalogue.
"""
from pathlib import Path

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Count

from akreditasi.models import Category, Framework, QualityRecord, StandardItem


DEFAULT_PDF = Path.home() / 'Downloads' / 'starkes 2024.pdf'


class Command(BaseCommand):
    help = 'Guarded cutover from the 2022 catalogue to STARKES 2024.'

    def add_arguments(self, parser):
        parser.add_argument('--pdf-path', default=str(DEFAULT_PDF))
        parser.add_argument(
            '--apply', action='store_true',
            help='Actually perform the cutover. Without this it is a dry run.',
        )
        parser.add_argument(
            '--mapping-report', default='var/starkes-2024-mapping.json',
            help='Where to write the unmatched-score report.',
        )
        parser.add_argument(
            '--skip-backup-check', action='store_true',
            help='Proceed without an explicit backup acknowledgement.',
        )

    def handle(self, *args, **options):
        pdf = Path(options['pdf_path'])
        if not pdf.exists():
            raise CommandError(f'PDF tidak ditemukan: {pdf}')

        self._preflight()

        if not options['apply']:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN — tidak ada perubahan. Jalankan dengan --apply untuk menerapkan.'
            ))
            return

        if not options['skip_backup_check']:
            raise CommandError(
                'Buat backup database terlebih dahulu, lalu jalankan ulang dengan '
                '--skip-backup-check untuk mengonfirmasi.'
            )

        self.stdout.write(self.style.NOTICE('\nMenerapkan katalog STARKES 2024...'))
        call_command(
            'import_instrumen_2024',
            pdf_path=str(pdf),
            replace=True,
            mapping_report=options['mapping_report'],
            stdout=self.stdout,
        )

        cache.clear()
        self.stdout.write('Cache dibersihkan (sidebar memakai katalog baru).')
        self._postflight()

    # ── helpers ──────────────────────────────────────────────────────────

    def _preflight(self):
        active = Framework.active()
        self.stdout.write(self.style.NOTICE('=== PRE-FLIGHT ==='))
        self.stdout.write(f'Database  : {connection.settings_dict["ENGINE"]}')
        self.stdout.write(f'Katalog   : {active.name if active else "(tidak ada)"}')
        self.stdout.write(f'Frameworks: {Framework.objects.count()}')
        self.stdout.write(f'Kategori  : {Category.objects.count()}')
        self.stdout.write(f'EP        : {StandardItem.objects.count()}')
        self.stdout.write(f'Skor      : {QualityRecord.objects.count()}')
        dup = (
            QualityRecord.objects.values('standard_item')
            .annotate(n=Count('id')).filter(n__gt=1).count()
        )
        if dup:
            raise CommandError(
                f'Ditemukan {dup} StandardItem dengan lebih dari satu QualityRecord; '
                'perbaiki dulu agar migrasi skor tidak ambigu.'
            )

    def _postflight(self):
        active = Framework.active()
        if active is None:
            raise CommandError('Tidak ada katalog aktif setelah cutover.')

        ep = StandardItem.objects.filter(category__framework=active).count()
        scores = QualityRecord.objects.filter(
            standard_item__category__framework=active
        ).count()
        orphan = QualityRecord.objects.exclude(
            standard_item__category__framework=active
        ).count()

        self.stdout.write(self.style.SUCCESS('\n=== POST-FLIGHT ==='))
        self.stdout.write(f'Katalog aktif : {active.name} ({active.version})')
        self.stdout.write(f'Kategori      : {active.categories.count()}')
        self.stdout.write(f'EP            : {ep}')
        self.stdout.write(f'Skor di 2024  : {scores}')
        self.stdout.write(f'Skor di arsip : {orphan} (dilaporkan untuk tinjauan manual)')

        codes = set(
            StandardItem.objects.filter(category__framework=active)
            .values_list('code', flat=True)
        )
        if len(codes) != ep:
            raise CommandError('Kode EP duplikat terdeteksi pada katalog aktif.')
        self.stdout.write('Integritas kode: OK (tidak ada duplikat)')
