"""Demo seeder alias for 5-Year Clinical Logbook (PMK No. 13 Tahun 2025)."""
from sdm.management.commands.seed_logbook_5tahun_siska import Command as SiskaCommand


class Command(SiskaCommand):
    help = (
        'Seed demo Buku Kinerja Elektronik (Logbook 5 Tahunan) PMK 13/2025 '
        '(alias of seed_logbook_5tahun_siska)'
    )
