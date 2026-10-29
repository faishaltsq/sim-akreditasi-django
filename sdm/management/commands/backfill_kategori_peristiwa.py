from django.core.management.base import BaseCommand

from sdm.models import PeristiwaSDM


class Command(BaseCommand):
    help = 'Isi kategori PeristiwaSDM yang masih kosong.'

    def handle(self, *args, **options):
        rows = PeristiwaSDM.objects.filter(kategori='')
        updated = 0
        for row in rows.iterator():
            row.backfill_kategori()
            updated += 1
        self.stdout.write(f'{updated} baris diperbarui.')
