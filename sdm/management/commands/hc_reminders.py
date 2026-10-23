from django.core.management.base import BaseCommand

from sdm.models import PengingatSDM
from sdm.models.pengingat import sync_all_reminders


class Command(BaseCommand):
    help = 'Create missing idempotent in-app Human Capital reminders.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true', help='Report counts without writing.'
        )

    def handle(self, *args, **options):
        if options['dry_run']:
            self.stdout.write(
                f'DRY-RUN pending_reminders={PengingatSDM.objects.count()}'
            )
            return
        created = sync_all_reminders()
        self.stdout.write(f'REMINDERS created={created}')
