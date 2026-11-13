import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from klinis.services.catalogue_import import import_catalogue


class Command(BaseCommand):
    help = 'Import reviewed source examples as inactive staging records; defaults to dry run.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default=str(Path(__file__).resolve().parents[2] / 'data' / 'penunjang_catalogue.json'))
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        try:
            result=import_catalogue('penunjang',options['file'],apply=options['apply'])
        except (ValueError,KeyError,OSError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(json.dumps(result))
