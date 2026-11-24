import json

from django.core.management.base import BaseCommand, CommandError

from klinis.services.poli_jantung_seed import seed

class Command(BaseCommand):
    help = ('Seed fondasi tarif Poliklinik Jantung: KelompokLayanan POLI_JANTUNG, '
            'salinan kasus/tindakan JANTUNG, dan TarifPenunjang yang bersumber.')

    def handle(self, *args, **options):
        try:
            hasil = seed()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(hasil))
