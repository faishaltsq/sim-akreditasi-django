"""Seed the RKK catalog (professions, career grades, clinical actions) from the
BAB KREDENSIAL spec. Dry-run by default; idempotent via get_or_create on codes."""
from django.core.management.base import BaseCommand
from django.db import transaction

from sdm.management.commands._data_katalog_rkk import (
    KATALOG_DOKTER_UMUM,
    KATALOG_NAKES_TAMBAHAN,
    KATALOG_SPESIALIS,
    KATALOG_SUBSPESIALIS,
    CATATAN_STATUS_BAKU,
    DEFAULT_STATUS_UNSET,
    DOKTER_JENJANG,
    FOKUS_KOMPETENSI,
    PROFESI,
    PROFESI_TANPA_JENJANG,
)
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

    # Katalog dokter tertutup + nakes tambahan (K1/K3 plan kaskade).
    if ('DOKTER_UMUM', 'DU-UMUM') not in existing_jenjang:
        jenjang_baru += 1
    for counter in range(1, len(KATALOG_DOKTER_UMUM) + 1):
        if f'K-DOKUM-{counter:03d}' not in existing_katalog:
            katalog_baru += 1
    doksp_ada = 'DOKTER_SP' in existing_profesi
    for jkode, _, butir in KATALOG_SPESIALIS:
        if ('DOKTER_SP', jkode) not in existing_jenjang:
            jenjang_baru += 1
    for jkode, _, butir in KATALOG_SUBSPESIALIS:
        if ('DOKTER_SP', jkode) not in existing_jenjang:
            jenjang_baru += 1
    # butir spesialis/subsp memakai counter berurutan K-DOKSP/K-DOKSUB;
    # hitung yang belum ada dengan menjawab: berapa kode pertama yang kosong
    # tidak bisa presisi — pakai pendekatan hitung total kode > existing.
    sp_len = sum(len(b) for _, _, b in KATALOG_SPESIALIS)
    sub_len = sum(len(b) for _, _, b in KATALOG_SUBSPESIALIS)
    for prefix, total in (('K-DOKSP-', sp_len), ('K-DOKSUB-', sub_len)):
        sudah = sum(
            1 for k in existing_katalog if k.startswith(prefix)
        )
        katalog_baru += max(0, total - sudah)

    for pcode, jenjang_map in KATALOG_NAKES_TAMBAHAN.items():
        sudah_p = sum(
            1 for k in existing_katalog if k.startswith(f'T-{pcode}-')
        )
        butir_p = sum(len(v) for v in jenjang_map.values())
        katalog_baru += max(0, butir_p - sudah_p)

    return profesi_baru, jenjang_baru, katalog_baru


def apply_seed(apps=None):
    """Idempotently write every missing row inside one transaction.
    
    Accepts an optional Django apps registry for use in migrations.
    """
    if apps is not None:
        MasterProfesiPegawai = apps.get_model('sdm', 'MasterProfesiPegawai')
        MasterJenjangProfesi = apps.get_model('sdm', 'MasterJenjangProfesi')
        KatalogTindakan = apps.get_model('sdm', 'KatalogTindakan')
    else:
        from sdm.models import (
            KatalogTindakan,
            MasterJenjangProfesi,
            MasterProfesiPegawai,
        )

    profesi_baru = jenjang_baru = katalog_baru = 0

    with transaction.atomic():
        for code, (nama, keluarga) in PROFESI_TANPA_JENJANG.items():
            _, was_created = MasterProfesiPegawai.objects.get_or_create(
                code=code, defaults={'nama': nama, 'keluarga': keluarga},
            )
            profesi_baru += int(was_created)

        # Dokter: jenjang + fokus kompetensi dari master RKK; katalog butir
        # sengaja kosong sampai SK komite menetapkannya.
        for code, (profesi_nama, jenjang_list) in DOKTER_JENJANG.items():
            profesi, was_created = MasterProfesiPegawai.objects.get_or_create(
                code=code,
                defaults={'nama': profesi_nama, 'keluarga': 'MEDIS'},
            )
            profesi_baru += int(was_created)
            for jkode, jnama, urutan, fokus, preceptor_min in jenjang_list:
                jen_obj, was_created = MasterJenjangProfesi.objects.get_or_create(
                    profesi=profesi, kode=jkode,
                    defaults={
                        'nama': jnama, 'urutan': urutan,
                        'fokus_kompetensi': fokus,
                        'preceptor_min_urutan': preceptor_min,
                    },
                )
                jenjang_baru += int(was_created)

        # Fill empty fokus_kompetensi on existing jenjang rows (idempotent).
        for (pcode, jkode), fokus in FOKUS_KOMPETENSI.items():
            MasterJenjangProfesi.objects.filter(
                profesi__code=pcode, kode=jkode, fokus_kompetensi='',
            ).update(fokus_kompetensi=fokus)

        # Katalog dokter tertutup: Umum (DU-UMUM) + 16 spesialisasi +
        # 16 subspesialisasi di bawah DOKTER_SP.
        dokum_prof, _ = MasterProfesiPegawai.objects.get_or_create(
            code='DOKTER_UMUM',
            defaults={'nama': 'Dokter Umum', 'keluarga': 'MEDIS'},
        )
        du_jenjang, was_created = MasterJenjangProfesi.objects.get_or_create(
            profesi=dokum_prof, kode='DU-UMUM', defaults={
                'nama': 'Dokter Umum', 'urutan': 1,
            },
        )
        jenjang_baru += int(was_created)
        for counter, nama_tindakan in enumerate(KATALOG_DOKTER_UMUM, start=1):
            _, was_created = KatalogTindakan.objects.get_or_create(
                kode=f'K-DOKUM-{counter:03d}',
                defaults={
                    'nama': nama_tindakan, 'jenjang': du_jenjang,
                    'tingkat_supervisi': 'M',
                },
            )
            katalog_baru += int(was_created)

        doksp_prof, _ = MasterProfesiPegawai.objects.get_or_create(
            code='DOKTER_SP',
            defaults={'nama': 'Dokter Spesialis', 'keluarga': 'MEDIS'},
        )
        counter = 0
        for jkode, jnama, butir in KATALOG_SPESIALIS:
            jen_obj, was_created = MasterJenjangProfesi.objects.get_or_create(
                profesi=doksp_prof, kode=jkode, defaults={
                    'nama': jnama, 'urutan': 2,
                },
            )
            jenjang_baru += int(was_created)
            for nama_tindakan in butir:
                counter += 1
                _, was_created = KatalogTindakan.objects.get_or_create(
                    kode=f'K-DOKSP-{counter:03d}',
                    defaults={
                        'nama': nama_tindakan, 'jenjang': jen_obj,
                        'tingkat_supervisi': 'M',
                    },
                )
                katalog_baru += int(was_created)
        for jkode, jnama, butir in KATALOG_SUBSPESIALIS:
            jen_obj, was_created = MasterJenjangProfesi.objects.get_or_create(
                profesi=doksp_prof, kode=jkode, defaults={
                    'nama': jnama, 'urutan': 3,
                },
            )
            jenjang_baru += int(was_created)
            for nama_tindakan in butir:
                counter += 1
                _, was_created = KatalogTindakan.objects.get_or_create(
                    kode=f'K-DOKSUB-{counter:03d}',
                    defaults={
                        'nama': nama_tindakan, 'jenjang': jen_obj,
                        'tingkat_supervisi': 'M',
                    },
                )
                katalog_baru += int(was_created)

        for code, (nama, keluarga, jenjang) in PROFESI.items():
            profesi, was_created = MasterProfesiPegawai.objects.get_or_create(
                code=code, defaults={'nama': nama, 'keluarga': keluarga},
            )
            profesi_baru += int(was_created)
            for jk, (jnama_j, items_j) in jenjang.items():
                urutan = URUTAN_MAP.get(jk, len(JENJANG_ORDER) + 1)
                jenjang_obj, was_created = MasterJenjangProfesi.objects.get_or_create(
                    profesi=profesi, kode=jk,
                    defaults={'nama': jnama_j, 'urutan': urutan},
                )
                jenjang_baru += int(was_created)

        # Katalog nakes tambahan (dokumen level Pelaksana/Ahli), digabung
        # ke jenjang yang sudah ada; butir lama tidak disentuh. Kodebutir
        # deterministik: urutan butir di data, per profesi.
        for pcode, jenjang_map in KATALOG_NAKES_TAMBAHAN.items():
            prof = MasterProfesiPegawai.objects.get(code=pcode)
            pcounter = 0
            for jkode, items in jenjang_map.items():
                jen_obj = MasterJenjangProfesi.objects.get(
                    profesi=prof, kode=jkode,
                )
                for nama_tindakan, status in items:
                    pcounter += 1
                    _, was_created = KatalogTindakan.objects.get_or_create(
                        kode=f'T-{pcode}-{pcounter:03d}',
                        defaults={
                            'nama': nama_tindakan, 'jenjang': jen_obj,
                            'tingkat_supervisi': status,
                            'catatan': CATATAN_STATUS_BAKU
                            if status == DEFAULT_STATUS_UNSET else '',
                        },
                    )
                    katalog_baru += int(was_created)

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
