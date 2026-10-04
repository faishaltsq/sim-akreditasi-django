"""
Management command: seed_renstra_db
Populates RenstraRoadmap and RenstraFokusItem from existing hardcoded RENSTRA_ANNUAL_FOCUS dict.
Idempotent — safe to run multiple times (uses update_or_create).
"""
from django.core.management.base import BaseCommand
from akreditasi.risiko_models import RenstraRoadmap, RenstraFokusItem, IndikatorMutu
from akreditasi.indikator_views import RENSTRA_ANNUAL_FOCUS

RENSTRA_META = {
    2026: {'ikon': 'bi-cpu',                'warna': '#0d6efd', 'urutan': 1},
    2027: {'ikon': 'bi-gear-wide-connected','warna': '#6f42c1', 'urutan': 2},
    2028: {'ikon': 'bi-hospital',           'warna': '#198754', 'urutan': 3},
    2029: {'ikon': 'bi-tree',               'warna': '#20c997', 'urutan': 4},
    2030: {'ikon': 'bi-trophy',             'warna': '#fd7e14', 'urutan': 5},
}


class Command(BaseCommand):
    help = 'Populate RenstraRoadmap and RenstraFokusItem from existing hardcoded definitions (idempotent)'

    def handle(self, *args, **options):
        self.stdout.write('Seeding Renstra Roadmap database records...')
        created_years = 0
        updated_years = 0
        created_items = 0
        updated_items = 0

        for tahun, data in RENSTRA_ANNUAL_FOCUS.items():
            meta = RENSTRA_META.get(tahun, {'ikon': 'bi-flag', 'warna': '#0d6efd', 'urutan': tahun - 2025})
            roadmap, created = RenstraRoadmap.objects.update_or_create(
                tahun=tahun,
                defaults={
                    'isu_strategis': data['isu_strategis'],
                    'sub_tema':      data.get('sub_tema', ''),
                    'deskripsi':     data.get('deskripsi', ''),
                    'ikon':          meta['ikon'],
                    'warna_hex':     meta['warna'],
                    'urutan':        meta['urutan'],
                    'aktif':         True,
                }
            )
            if created:
                created_years += 1
                self.stdout.write(f'  Created: Renstra {tahun} — {data["isu_strategis"]}')
            else:
                updated_years += 1
                self.stdout.write(f'  Updated: Renstra {tahun}')

            for item_data in data.get('fokus_items', []):
                kode_ref = item_data.get('kode_ref', '')
                # Try matching IndikatorMutu by kode_indikator field
                ind_obj = None
                if kode_ref:
                    ind_obj = IndikatorMutu.objects.filter(kode_indikator=kode_ref).first()

                _, item_created = RenstraFokusItem.objects.update_or_create(
                    roadmap=roadmap,
                    nomor=item_data['nomor'],
                    defaults={
                        'nama_fokus':      item_data['nama'],
                        'indikator_mutu':  ind_obj,
                        'kode_ref':        kode_ref,
                        'target_label':    item_data.get('target', '100%'),
                        'target_nilai':    item_data.get('target_val', 100.0),
                        'satuan':          item_data.get('satuan', '%'),
                        'unit_kerja_label':item_data.get('unit_name', ''),
                    }
                )
                if item_created:
                    created_items += 1
                else:
                    updated_items += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Renstra years: {created_years} created / {updated_years} updated. '
            f'Focus items: {created_items} created / {updated_items} updated.'
        ))
