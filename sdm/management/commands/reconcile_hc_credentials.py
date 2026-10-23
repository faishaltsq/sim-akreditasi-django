import json
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError

from sdm.services.kredensial_lama import (
    apply_credential_reconciliation,
    dry_run_credential_reconciliation,
    reconcile_private_inventory,
)
from sdm.storage_backend import PrivateStorageError


class Command(BaseCommand):
    help = 'Dry-run, inventory, or apply a reviewed private mapping for legacy credentials.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', help='Read-only aggregate preview (default).'
        )
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--mapping-artifact')
        parser.add_argument(
            '--inventory', action='store_true',
            help='Read-only aggregate object/checksum inventory.',
        )
        parser.add_argument(
            '--verify-anonymous-denial', action='store_true',
            help='With --inventory, verify public access is denied.',
        )

    @staticmethod
    def _load_artifact(path):
        try:
            return json.loads(Path(path).read_text(encoding='utf-8'))
        except (OSError, UnicodeError, json.JSONDecodeError):
            raise CommandError('Artefak pemetaan tidak dapat dibaca.') from None

    def handle(self, *args, **options):
        apply = options['apply']
        inventory = options['inventory']
        mapping_path = options['mapping_artifact']
        selected_modes = sum((apply, options['dry_run'], inventory))
        if selected_modes > 1:
            raise CommandError('Pilih satu mode: --dry-run, --apply, atau --inventory.')
        if options['verify_anonymous_denial'] and not inventory:
            raise CommandError('--verify-anonymous-denial hanya berlaku dengan --inventory.')
        if apply and not mapping_path:
            raise CommandError('--apply membutuhkan --mapping-artifact yang telah ditinjau.')

        artifact = self._load_artifact(mapping_path) if mapping_path else None
        if inventory:
            try:
                result = reconcile_private_inventory(
                    verify_anonymous_denial=options['verify_anonymous_denial']
                )
            except PrivateStorageError:
                raise CommandError(
                    'Inventaris privat gagal diverifikasi; detail penyedia disembunyikan.'
                ) from None
            self.stdout.write(
                'INVENTORY '
                f'total={result["total"]} '
                f'verified={result["verified"]} '
                f'missing_or_mismatched={result["missing_or_mismatched"]} '
                f'anonymous_denied={result["anonymous_denied"]} '
                f'anonymous_exposed_or_error={result["anonymous_exposed_or_error"]}'
            )
            return
        try:
            if not apply:
                result = dry_run_credential_reconciliation(artifact)
                self.stdout.write(
                    'DRY-RUN '
                    f'credentials={result["total"]} '
                    f'linked={result["linked"]} '
                    f'eligible={result["eligible"]} '
                    f'unresolved={result["unresolved"]}'
                )
                return

            result = apply_credential_reconciliation(artifact)
        except (ValidationError, PrivateStorageError):
            raise CommandError(
                'Rekonsiliasi dibatalkan: pemetaan atau objek privat gagal diverifikasi.'
            ) from None

        self.stdout.write(
            'APPLIED '
            f'linked={result["linked"]} '
            f'already_linked={result["already_linked"]} '
            f'unresolved={result["unresolved"]}'
        )
