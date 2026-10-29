"""Audit the RKK catalog against the master RKK document (26 sections).

Read-only. Reports, per profession named in "master RKK Kewenangan klinis.docx":
whether the profession row exists, how many career grades it has, and how many
catalog actions are attached. A profession the document names but the database
does not carry is a gap the operator must resolve — this command never invents
the missing rows.

Exit code is 0 regardless of findings; ``--strict`` makes any gap exit 1 so it
can gate a deploy.
"""
from django.core.management.base import BaseCommand

from sdm.models import KatalogTindakan, MasterJenjangProfesi, MasterProfesiPegawai

# Professions the master RKK document covers, with the grade count it states.
# Doctor grades are narrative in the document (no per-action list), so a
# profession may legitimately carry grades but no catalog rows.
DOKUMEN_PROFESI = {
    'DOKTER_UMUM': ('Dokter Umum', 3),
    'DOKTER_SP': ('Dokter Spesialis', 3),
    'DOKTER_GIGI': ('Dokter Gigi', 3),
    'KPR': ('Perawat', 5),
    'BID': ('Bidan', 5),
    'ELMD': ('Tenaga Elektromedis', 4),
    'SANI': ('Sanitarian', 4),
    'DIET': ('Dietisien', 4),
    'NUTR': ('Nutrisionis', 4),
    'TB': ('Tenaga Teknis Tuberculosis', 4),
    'TTK': ('Tenaga Teknis Kefarmasian', 4),
    'PMIK': ('Perekam Medis & Informasi Kesehatan', 4),
    'WICARA': ('Terapis Wicara', 4),
    'OKT': ('Okupasi Terapis', 4),
    'ORPRO': ('Ortotik Prostetik', 4),
    'ANES': ('Penata Anestesi', 4),
    'FISIO': ('Fisioterapis', 4),
    'PSIK': ('Psikologi Klinis', 4),
    'RADG': ('Radiografer', 4),
    'FMA': ('Fisikawan Medis', 4),
    'ATLM': ('Ahli Teknologi Laboratorium Medik', 4),
    'K3RS': ('Ahli K3RS', 4),
    'APOTEKER': ('Apoteker', 2),
}


class Command(BaseCommand):
    help = 'Audit cakupan katalog RKK terhadap dokumen master kewenangan klinis.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--strict', action='store_true',
            help='Keluar dengan kode 1 bila ada profesi yang belum ter-seed.',
        )

    def handle(self, *args, **options):
        gaps = []
        self.stdout.write(
            f'{"Kode":<12} {"Profesi":<38} {"Jenjang":>7} {"Diharapkan":>10} {"Tindakan":>8}'
        )
        self.stdout.write('-' * 80)

        for code, (nama, jenjang_diharapkan) in sorted(DOKUMEN_PROFESI.items()):
            profesi = MasterProfesiPegawai.objects.filter(code=code).first()
            if profesi is None:
                gaps.append((code, nama, 'profesi tidak ada'))
                self.stdout.write(
                    f'{code:<12} {nama:<38} {"—":>7} {jenjang_diharapkan:>10} {"—":>8}  ❌'
                )
                continue

            n_jenjang = MasterJenjangProfesi.objects.filter(profesi=profesi).count()
            n_tindakan = KatalogTindakan.objects.filter(jenjang__profesi=profesi).count()
            jenjang_ok = n_jenjang >= jenjang_diharapkan
            if not jenjang_ok:
                gaps.append(
                    (code, nama, f'jenjang {n_jenjang} < {jenjang_diharapkan}')
                )
            mark = '✓' if jenjang_ok else '❌'
            self.stdout.write(
                f'{code:<12} {nama:<38} {n_jenjang:>7} {jenjang_diharapkan:>10} '
                f'{n_tindakan:>8}  {mark}'
            )

        total_profesi = MasterProfesiPegawai.objects.count()
        total_jenjang = MasterJenjangProfesi.objects.count()
        total_tindakan = KatalogTindakan.objects.count()
        self.stdout.write('-' * 80)
        self.stdout.write(
            f'Total DB: {total_profesi} profesi / {total_jenjang} jenjang / '
            f'{total_tindakan} tindakan'
        )

        if gaps:
            self.stdout.write('')
            self.stdout.write(self.style.WARNING(f'{len(gaps)} gap ditemukan:'))
            for code, nama, alasan in gaps:
                self.stdout.write(f'  - {code} ({nama}): {alasan}')
            if options['strict']:
                raise SystemExit(1)
        else:
            self.stdout.write(self.style.SUCCESS('Tidak ada gap: semua profesi dokumen ter-seed.'))
