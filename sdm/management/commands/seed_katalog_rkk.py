"""Seed the RKK catalog (professions, career grades, clinical actions) from the
BAB KREDENSIAL spec. Dry-run by default; idempotent via get_or_create on codes."""
from django.core.management.base import BaseCommand
from django.db import transaction

from sdm.management.commands._data_katalog_rkk import PROFESI, PROFESI_TANPA_JENJANG
from sdm.models import KatalogTindakan, MasterJenjangProfesi, MasterProfesiPegawai


URUTAN_MAP = {
    'PRATAMA': 1, 'MUDA': 2, 'MADYA': 3, 'UTAMA': 4,
    'PK-I': 1, 'PK-II': 2, 'PK-III': 3, 'PK-IV': 4, 'PK-V': 5,
    'BK-I': 1, 'BK-II': 2, 'BK-III': 3, 'BK-IV': 4, 'BK-V': 5,
}

JENJANG_ORDER = (
    'PRATAMA', 'MUDA', 'MADYA', 'UTAMA',
    'PK-I', 'PK-II', 'PK-III', 'PK-IV', 'PK-V',
    'BK-I', 'BK-II', 'BK-III', 'BK-IV', 'BK-V',
)


def _iter_katalog_rows():
    """Yield (kode, nama, jenjang_kode, status) with codes numbered continuously
    per profesi (K-KPR-001..K-KPR-0NN), matching the spec format K-KPR-012."""
    for code, (nama, keluarga, jenjang) in PROFESI.items():
        counter = 0
        for jk in JENJANG_ORDER:
            if jk not in jenjang:
                continue
            jnama, items = jenjang[jk]
            for nama_tindakan, status in items:
                yield (f'K-{code}-{counter + 1:03d}', nama_tindakan, jk, status)
                counter += 1


def plan_missing():
    """Return (missing_profesi, missing_jenjang, missing_katalog) counts without
    writing anything: compare literal spec data against existing DB codes."""
    existing_profesi = set(MasterProfesiPegawai.objects.values_list('code', flat=True))
    existing_jenjang = set(
        MasterJenjangProfesi.objects.values_list('profesi__code', 'kode')
    )
    existing_katalog = set(KatalogTindakan.objects.values_list('kode', flat=True))

    profesi_baru = jenjang_baru = katalog_baru = 0

    for code in PROFESI_TANPA_JENJANG:
        if code not in existing_profesi:
            profesi_baru += 1
    for code, (nama, keluarga, jenjang) in PROFESI.items():
        if code not in existing_profesi:
            profesi_baru += 1
        for jk in jenjang:
            if (code, jk) not in existing_jenjang:
                jenjang_baru += 1
    for kode, nama, jk, status in _iter_katalog_rows():
        if kode not in existing_katalog:
            katalog_baru += 1

    return profesi_baru, jenjang_baru, katalog_baru


def apply_seed():
    """Idempotently write every missing row inside one transaction."""
    profesi_baru = jenjang_baru = katalog_baru = 0

    with transaction.atomic():
        for code, (nama, keluarga) in PROFESI_TANPA_JENJANG.items():
            _, was_created = MasterProfesiPegawai.objects.get_or_create(
                code=code, defaults={'nama': nama, 'keluarga': keluarga},
            )
            profesi_baru += int(was_created)

        for code, (nama, keluarga, jenjang) in PROFESI.items():
            profesi, was_created = MasterProfesiPegawai.objects.get_or_create(
                code=code, defaults={'nama': nama, 'keluarga': keluarga},
            )
            profesi_baru += int(was_created)
            for jk in JENJANG_ORDER:
                if jk not in jenjang:
                    continue
                jnama, items = jenjang[jk]
                jenjang_obj, was_created = MasterJenjangProfesi.objects.get_or_create(
                    profesi=profesi, kode=jk,
                    defaults={'nama': jnama, 'urutan': URUTAN_MAP[jk]},
                )
                jenjang_baru += int(was_created)

        for kode, nama, jk, status in _iter_katalog_rows():
            profesi_code = kode.split('-')[1]
            jenjang_obj = MasterJenjangProfesi.objects.get(
                profesi__code=profesi_code, kode=jk,
            )
            _, was_created = KatalogTindakan.objects.get_or_create(
                kode=kode,
                defaults={
                    'nama': nama,
                    'jenjang': jenjang_obj,
                    'tingkat_supervisi': status,
                },
            )
            katalog_baru += int(was_created)

    return profesi_baru, jenjang_baru, katalog_baru


class Command(BaseCommand):
    help = (
        'Seed MasterProfesiPegawai / MasterJenjangProfesi / KatalogTindakan from '
        'the BAB KREDENSIAL spec. Dry-run by default; use --apply to write. '
        'Idempotent: re-running never duplicates rows.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')

    def handle(self, *args, **options):
        if not options['apply']:
            profesi_baru, jenjang_baru, katalog_baru = plan_missing()
            self.stdout.write(
                f'DRY-RUN profesi_baru={profesi_baru} '
                f'jenjang_baru={jenjang_baru} '
                f'tindakan_baru={katalog_baru} '
                f'(existing: profesi={MasterProfesiPegawai.objects.count()}, '
                f'jenjang={MasterJenjangProfesi.objects.count()}, '
                f'katalog={KatalogTindakan.objects.count()})'
            )
            return

        created = apply_seed()
        self.stdout.write(
            f'APPLIED profesi_dibuat={created[0]} '
            f'jenjang_dibuat={created[1]} '
            f'tindakan_dibuat={created[2]}'
        )
