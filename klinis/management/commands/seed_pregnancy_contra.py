"""Isi kolom kontraindikasi kehamilan pada master produk (AMBIGU-17a, ADR-15).

Masalah yang ditutup: ``pasien.services.pregnancy_safety`` sebelumnya hanya
dapat mencocokkan ``class_code``/``ingredient_code`` katalog. Kelas lokal
``kardiovaskular-antihipertensi`` tidak memisahkan ACEi dari ARB, ARNI, statin,
atau warfarin, sehingga peringatan kehamilan tidak pernah menyala untuk produk
yang seharusnya memicunya.

Perintah ini memetakan lima kelompok matriks §9a ke **baris katalog yang sudah
ada** berdasarkan nama zat pada ``GenerikObat``. Ia tidak membuat produk, tidak
mengubah harga, dan tidak menyentuh whitelist ``flags``.

**Ratifikasi.** Daftar zat di ``SUBSTANCE_GROUPS`` adalah **default
operasional** yang belum diratifikasi Komite Farmasi & Terapi (ADR-15). Setiap
baris yang dipetakan menyimpan sumbernya di ``pregnancy_class_source``.

**Tidak menebak.** Zat yang tidak ada di daftar tidak dipetakan; baris tanpa
kelas dilaporkan terpisah sebagai ``unmapped``. Kelompok yang tidak punya satu
pun baris katalog dilaporkan sebagai ``kelompok_tanpa_baris`` supaya celahnya
terlihat, bukan tertutup diam-diam.

Idempoten: baris yang sudah punya ``pregnancy_class`` tidak ditimpa kecuali
``--force``. Default adalah dry-run; ``--apply`` menulis.
"""
import json
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from klinis.expansion_models import PREGNANCY_CLASS_CODES
from klinis.models import ProdukFarmasi

#: Kelompok matriks §9a → nama zat yang dipetakan ke kelompok itu. Urutan
#: penting: zat yang lebih spesifik didahulukan (``Sacubitril+Valsartan`` adalah
#: ARNI, bukan ARB) — karena itu pencocokan memakai awalan berbatas kata, bukan
#: "mengandung".
SUBSTANCE_GROUPS = (
    ('ARNI', ('Sacubitril+Valsartan',)),
    ('ACEI', ('Captopril', 'Lisinopril', 'Enalapril', 'Ramipril')),
    ('ARB', ('Candesartan', 'Losartan', 'Valsartan', 'Telmisartan')),
    ('STATIN', ('Simvastatin', 'Atorvastatin', 'Rosuvastatin', 'Pravastatin')),
    ('WARFARIN', ('Warfarin',)),
)

#: Kalimat provenance yang ditulis ke setiap baris yang dipetakan.
SOURCE_TEMPLATE = (
    'ADR-15 default operasional (ratifikasi Komite Farmasi & Terapi tertunda); '
    'zat={substance}; kelompok matriks §9a'
)


def classify(generic_name):
    """Return ``(group, substance)`` untuk satu nama generik, atau ``(None, None)``.

    Pencocokan memakai awalan berbatas kata pada nama generik apa adanya, jadi
    ``'Valsartan 80 mg / 160 mg'`` cocok dengan ``Valsartan`` sementara
    ``'Sacubitril+Valsartan 50/25 mg'`` tidak — yang terakhir sudah ditangkap
    ARNI lebih dulu.
    """
    name = str(generic_name or '').strip()
    for group, substances in SUBSTANCE_GROUPS:
        for substance in substances:
            if re.match(rf'^{re.escape(substance)}\b', name, re.IGNORECASE):
                return group, substance
    return None, None


class Command(BaseCommand):
    help = (
        'Petakan kelompok kontraindikasi kehamilan (ADR-15) ke baris katalog '
        'yang ada. Default dry-run; gunakan --apply untuk menulis.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Tulis perubahan ke basis data.')
        parser.add_argument(
            '--force', action='store_true',
            help='Timpa pregnancy_class yang sudah terisi (default: biarkan).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        force = options['force']
        mapped = {group: [] for group in PREGNANCY_CLASS_CODES}
        skipped = []
        with transaction.atomic():
            for product in ProdukFarmasi.objects.select_related('generik').order_by('kode'):
                group, substance = classify(product.generik.nama)
                if group is None:
                    continue
                if product.pregnancy_class and not force:
                    skipped.append(product.kode)
                    continue
                mapped[group].append(product.kode)
                if apply:
                    product.pregnancy_contra = True
                    product.pregnancy_class = group
                    product.pregnancy_class_source = SOURCE_TEMPLATE.format(substance=substance)
                    product.save(update_fields=[
                        'pregnancy_contra', 'pregnancy_class', 'pregnancy_class_source',
                    ])

        unmapped = list(
            ProdukFarmasi.objects.filter(pregnancy_class='').order_by('kode')
            .values_list('kode', flat=True)
        )
        # Zat yang disebut matriks §9a tetapi tidak punya baris generik di
        # katalog: celah data yang tidak boleh ditambal dengan produk karangan.
        present = {classify(name)[1] for name in
                   ProdukFarmasi.objects.values_list('generik__nama', flat=True)}
        report = {
            'mode': 'apply' if apply else 'dry-run',
            'mapped': {group: codes for group, codes in mapped.items() if codes},
            'counts': {group: len(codes) for group, codes in mapped.items()},
            'skipped_already_classified': skipped,
            'kelompok_tanpa_baris': [group for group in PREGNANCY_CLASS_CODES if not mapped[group]],
            'zat_tanpa_generik': [
                substance
                for group, substances in SUBSTANCE_GROUPS
                for substance in substances
                if substance not in present
            ],
            'unmapped': unmapped,
        }
        self.stdout.write(json.dumps(report, indent=2, ensure_ascii=False))
