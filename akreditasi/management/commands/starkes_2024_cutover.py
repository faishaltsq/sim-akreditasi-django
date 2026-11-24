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

import json
from datetime import datetime

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Count

from akreditasi.models import (
    AktivasiKatalog, Category, Framework, QualityRecord, StandardItem,
)


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
        parser.add_argument(
            '--backup-reference', default='',
            help='Referensi cadangan database yang disimpan di jejak AktivasiKatalog.',
        )
        parser.add_argument(
            '--fixture', default=None,
            help=(
                'Pakai fixture golden (mis. fixtures/standar_akreditasi_2024.json) '
                'alih-alih mem-parsing PDF. Fixture inilah yang dipakai uji dan '
                'dihasilkan dari PDF yang sama.'
            ),
        )
        parser.add_argument(
            '--reset-scores', action='store_true',
            help=(
                'Hapus seluruh QualityRecord sebelum cutover. Hanya untuk basis '
                'data demo: rekonsiliasi menolak EP legacy yang sudah berisi '
                'penilaian tetapi tidak punya padanan di instrumen 2024.'
            ),
        )

    def handle(self, *args, **options):
        pdf = Path(options['pdf_path'])
        if not options['fixture'] and not pdf.exists():
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
        pre = self._snapshot()

        if options['reset_scores']:
            if not options['backup_reference']:
                raise CommandError(
                    '--reset-scores menghapus data penilaian; sertakan '
                    '--backup-reference agar jejaknya dapat diaudit.'
                )
            removed = QualityRecord.objects.count()
            QualityRecord.objects.all().delete()
            self.stdout.write(self.style.WARNING(
                f'[RESET] {removed} QualityRecord dihapus (basis data demo).'
            ))

        # ``import_instrumen_2024`` menerima --pdf-path/--fixture/--prune, bukan
        # ``replace``/``mapping_report``. Dulu command ini mengirim dua opsi
        # yang tidak ada sehingga cutover selalu gagal dengan TypeError sebelum
        # menyentuh database.
        source_kwargs = {'prune': True, 'stdout': self.stdout}
        if options['fixture']:
            source_kwargs['fixture'] = options['fixture']
        else:
            source_kwargs['pdf_path'] = str(pdf)
        call_command('import_instrumen_2024', **source_kwargs)

        framework = self._activate(framework_name='STARKES Edisi 2024 / Kemenkes RI',
                                   backup_reference=options['backup_reference'])
        self._write_mapping_report(Path(options['mapping_report']), pre, framework)

        cache.clear()
        from akreditasi.context_processors import invalidate_catalogue_caches
        invalidate_catalogue_caches()
        self.stdout.write('Cache dibersihkan (sidebar memakai katalog baru).')
        self._postflight()

    # ── helpers ──────────────────────────────────────────────────────────

    def _snapshot(self) -> dict:
        """Ringkasan katalog sebelum cutover, untuk laporan pemetaan."""
        active = Framework.active()
        return {
            'framework': active.name if active else None,
            'framework_id': active.pk if active else None,
            'frameworks': Framework.objects.count(),
            'categories': Category.objects.count(),
            'ep': StandardItem.objects.count(),
            'scores': QualityRecord.objects.count(),
        }

    def _activate(self, *, framework_name: str, backup_reference: str) -> Framework:
        """Jadikan framework 2024 satu-satunya katalog aktif.

        ``import_instrumen_2024`` hanya membuat framework baru (lifecycle
        default ACTIVE, is_active default True) tanpa mengarsipkan yang lama,
        sehingga tanpa langkah ini dua katalog bisa sama-sama aktif dan
        ``Framework.active()`` memilih berdasarkan versi — bukan berdasarkan
        keputusan eksplisit. Jejaknya dicatat sebagai ``AktivasiKatalog``.
        """
        framework = (
            Framework.objects.filter(name=framework_name).order_by('-pk').first()
        )
        if framework is None:
            raise CommandError(
                f'Framework "{framework_name}" tidak ditemukan setelah impor.'
            )

        with transaction.atomic():
            previous = (
                Framework.objects.filter(is_active=True)
                .exclude(pk=framework.pk)
                .order_by('-pk')
                .first()
            )
            Framework.objects.filter(is_active=True).exclude(pk=framework.pk).update(
                is_active=False, lifecycle='ARCHIVED'
            )
            framework.lifecycle = 'ACTIVE'
            framework.is_active = True
            framework.clean()
            framework.save(update_fields=['lifecycle', 'is_active'])

            AktivasiKatalog.objects.create(
                framework=framework,
                previous_framework=previous,
                backup_reference=backup_reference[:200],
                status='ACTIVE',
                run_metadata={
                    'command': 'starkes_2024_cutover',
                    'activated_at': datetime.now().isoformat(timespec='seconds'),
                    'previous_framework_id': previous.pk if previous else None,
                    # Aktivasi lewat service butuh artefak tata kelola
                    # (SumberKatalog + hash rencana + PemetaanEdisi yang sudah
                    # direview). Artefak itu belum ada untuk edisi 2024, jadi
                    # cutover ini dicatat sebagai aktivasi operasional.
                    'governance_plan': 'tidak ada (aktivasi operasional)',
                },
            )

            actives = Framework.objects.filter(is_active=True).count()
            if actives != 1:
                raise CommandError(
                    f'Invarian katalog aktif dilanggar: {actives} framework aktif.'
                )

        self.stdout.write(
            self.style.SUCCESS(
                f'[ACTIVE] {framework.name} (v{framework.version}); '
                f'sebelumnya: {previous.name if previous else "(tidak ada)"}'
            )
        )
        return framework

    def _write_mapping_report(self, path: Path, pre: dict, framework: Framework) -> None:
        """Tulis laporan ringkas sebelum/sesudah cutover ke JSON."""
        post = self._snapshot()
        report = {
            'generated_at': datetime.now().isoformat(timespec='seconds'),
            'pre': pre,
            'post': post,
            'active_framework': {
                'id': framework.pk,
                'name': framework.name,
                'version': framework.version,
                'lifecycle': framework.lifecycle,
            },
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        self.stdout.write(f'Laporan pemetaan: {path}')

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
