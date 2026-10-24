"""Reconcile staff census provenance (Task B1).

Dry-run by default. --apply requires an explicit reviewed artifact JSON file and
rejects ambiguous collision rows rather than blanking identifiers. Preserves all
existing employee UUIDs, account links, placements and historical employment
records.
"""

import json
import uuid
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import Pegawai, PenempatanPegawai, PeristiwaSDM


ARTIFACT_SCHEMA_VERSION = '1'


class Command(BaseCommand):
    help = (
        'Reconcile staff census provenance without destroying rows. '
        'Dry-run by default; --apply requires --reviewed-artifact.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument(
            '--reviewed-artifact',
            dest='reviewed_artifact',
            help='Path to reviewed reconciliation artifact JSON (required for --apply).',
        )
        parser.add_argument(
            '--as-of',
            dest='as_of',
            help='Opening-balance placement date for approved creates (ISO YYYY-MM-DD).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        artifact_path = options['reviewed_artifact']
        as_of = options['as_of']

        artifact = None
        if artifact_path:
            try:
                artifact = self._load_artifact(artifact_path)
            except CommandError as exc:
                if apply:
                    raise
                self.stdout.write(f'Dry-run: {exc}; no changes reported.')

        if apply:
            self._apply(artifact, as_of)
        else:
            self._dry_run(artifact)

    def _load_artifact(self, path):
        try:
            data = json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError(f'Cannot read reviewed artifact {path!r}: {exc}')
        if data.get('schema_version') != ARTIFACT_SCHEMA_VERSION:
            raise CommandError(
                f'Unsupported artifact schema_version {data.get("schema_version")!r}; '
                f'expected {ARTIFACT_SCHEMA_VERSION!r}.'
            )
        return data

    def _dry_run(self, artifact):
        total = Pegawai.objects.count()
        unclassified = Pegawai.objects.filter(data_origin='UNCLASSIFIED').count()
        self.stdout.write(
            f'DRY-RUN employees={total} unclassified={unclassified} '
            f'apply={"yes" if artifact else "no"}'
        )
        if artifact:
            decisions = artifact.get('decisions', [])
            self.stdout.write(f'Reviewed decisions in artifact: {len(decisions)}')
            for decision in decisions:
                self.stdout.write(
                    f"  {decision.get('action')} "
                    f"employee={decision.get('employee_id')} "
                    f"unit={decision.get('unit_id')} "
                    f"reason={decision.get('reason')}"
                )
        else:
            self.stdout.write('No reviewed artifact: no rows would change.')

    def _apply(self, artifact, as_of):
        if artifact is None:
            raise CommandError('--apply requires --reviewed-artifact.')

        decisions = artifact.get('decisions', [])
        if not isinstance(decisions, list):
            raise CommandError('Reviewed artifact must contain a decisions list.')

        placement_date = None
        if as_of:
            try:
                placement_date = timezone.datetime.strptime(as_of, '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('--as-of must be ISO YYYY-MM-DD.')

        created = skipped = rejected = 0
        with transaction.atomic():
            for decision in decisions:
                action = decision.get('action')
                employee_id = decision.get('employee_id')
                unit_id = decision.get('unit_id')

                if action == 'noop':
                    skipped += 1
                    continue

                if action == 'reject':
                    rejected += 1
                    self.stdout.write(
                        f"Rejected employee {employee_id}: {decision.get('reason')}"
                    )
                    continue

                if action == 'create':
                    if not employee_id or not unit_id:
                        raise CommandError(
                            f'Create decision missing employee_id or unit_id: {decision!r}'
                        )
                    try:
                        employee_uuid = uuid.UUID(str(employee_id))
                    except (ValueError, AttributeError):
                        raise CommandError(f'Invalid employee UUID: {employee_id!r}')
                    try:
                        unit = UnitKerja.objects.get(pk=unit_id)
                    except UnitKerja.DoesNotExist:
                        raise CommandError(f'Unknown unit: {unit_id!r}')

                    if Pegawai.objects.filter(pk=employee_uuid).exists():
                        raise CommandError(
                            f'Employee {employee_id} already exists; cannot create.'
                        )

                    employee = Pegawai.objects.create(
                        pk=employee_uuid,
                        nama_lengkap=decision.get('nama_lengkap', ''),
                        nomor_pegawai=decision.get('nomor_pegawai', '') or '',
                        kategori=decision.get('kategori', 'NON_PPA'),
                        profesi=decision.get('profesi', '') or '',
                        status=decision.get('status', 'AKTIF'),
                        data_origin=decision.get('data_origin', 'VERIFIED_IMPORT'),
                    )
                    if placement_date:
                        PenempatanPegawai.objects.create(
                            pegawai=employee,
                            unit_kerja=unit,
                            tanggal_mulai=placement_date,
                            alokasi_fte=Decimal('1.00'),
                        )
                        PeristiwaSDM.objects.create(
                            actor=None,
                            jenis_peristiwa='employee_created',
                            target_tipe='employee',
                            target_id=str(employee.pk),
                            status_sesudah=employee.status,
                            alasan='Opening balance placement with provenance; not actual hiring date.',
                        )
                    created += 1
                    continue

                raise CommandError(f'Unknown decision action: {action!r}')

        self.stdout.write(
            f'APPLIED created={created} skipped={skipped} rejected={rejected}'
        )
