"""Seed peta distribusi INM (13 baris dari dokumen usulan) ke InmUnitMapping.

Sumber: "Berikut adalah tabel usulan Peta Distribusi Indikator Nasional Mutu.docx".

Kolom "Unit Terkait" pada dokumen memakai nama generik (IRJA, ICU/ICCU,
VK/Kebidanan). Command ini memetakannya ke kode UnitKerja riil. Subtree tidak
didaftar manual — resolver (`unit_subtree_ids`) yang memperluasnya saat query.

Baris yang tidak bisa dicocokkan DICETAK sebagai [SKIP] dan tidak dibuat.
Tidak ada unit yang dikarang.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from akreditasi.models import UnitKerja
from akreditasi.risiko_models import IndikatorMutu, InmUnitMapping

# kode INM -> (unit PJ, unit terkait, role_scope)
MATRIX = [
    ('INM-01', ['KOM-PPI'], [
        'IRIN', 'RANAP', 'IRJ', 'RAJAL', 'IGD', 'ICU', 'ICCU', 'VK', 'IBS',
        'LAB', 'RAD', 'FARM', 'GIZI', 'JENAZAH', 'RM', 'KESLING',
    ], []),
    ('INM-02', ['KOM-PPI'], [
        'IRIN', 'RANAP', 'IRJ', 'RAJAL', 'IGD', 'ICU', 'ICCU', 'VK', 'IBS',
        'LAB', 'RAD', 'CSSD', 'LAUNDRY', 'KESLING', 'JENAZAH',
    ], []),
    ('INM-03', ['KMKP'], [
        'IRIN', 'RANAP', 'IRJ', 'RAJAL', 'IGD', 'ICU', 'ICCU', 'VK', 'IBS',
        'LAB', 'RAD', 'FARM', 'ADMISI', 'PENDAFTARAN-ADMISSION', 'REHAB',
    ], []),
    ('INM-16', ['IGD', 'VK'], [
        'IGD', 'VK', 'IBS', 'KAMAR-OPERASI', 'ICU', 'KSM-ANESTESI', 'LAB', 'BDRS',
    ], []),
    ('INM-06', ['IRJ'], [
        'IRJ', 'RAJAL', 'PENDAFTARAN-ADMISSION', 'ADMISI', 'RM', 'DEPO-RAJAL', 'FARM',
    ], []),
    ('INM-05', ['IBS'], [
        'IBS', 'KAMAR-OPERASI', 'IRIN', 'RANAP', 'POLI-BEDAH', 'KSM-ANESTESI', 'CSSD',
    ], []),
    ('INM-15', ['BID-YAN'], [
        'IRIN', 'RANAP', 'ICU', 'ICCU', 'HCU',
    ], []),
    ('INM-12', ['LAB'], [
        'LAB', 'IRIN', 'RANAP', 'ICU', 'ICCU', 'IGD', 'VK',
    ], []),
    ('INM-07', ['FARM'], [
        'FARM', 'DEPO-RAJAL', 'DEPO-RANAP-IGD', 'DEPO-BEDAH-INTENSIF', 'KOM-MED', 'KOM-FARMASI',
    ], ['DPJP']),
    ('INM-08', ['KOM-MED'], [
        'IRIN', 'RANAP', 'BANGSAL-ANAK', 'BANGSAL-DEWASA', 'BANGSAL-OBGYN', 'RM', 'KOM-MUTU',
    ], []),
    ('INM-09', ['KMKP'], [
        'IRIN', 'RANAP', 'ICU', 'ICCU', 'IGD', 'REHAB', 'RAD',
    ], []),
    ('INM-10', ['HUMAS-CS'], ['HUMAS-CS'], ['KEPALA_UNIT']),
    ('INM-11', ['HUMAS-CS', 'KOM-MUTU'], [
        'IRJ', 'RAJAL', 'IRIN', 'RANAP', 'IGD', 'FARM', 'SUB-KAS', 'LAB', 'RAD',
    ], []),
]


class Command(BaseCommand):
    help = 'Seed peta distribusi INM (13 INM dari dokumen usulan) ke InmUnitMapping.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Tampilkan rencana tanpa menulis ke database.')
        parser.add_argument('--prune', action='store_true',
                            help='Hapus baris mapping INM yang tidak ada di matriks.')
        parser.add_argument('--strict', action='store_true',
                            help='Exit code 1 bila ada baris yang di-skip.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        created = updated = skipped = 0
        warnings = []

        ind_map = {
            i.kode_indikator: i
            for i in IndikatorMutu.objects.filter(
                kode_indikator__in=[row[0] for row in MATRIX]
            )
        }
        unit_map = {
            u.code: u
            for u in UnitKerja.objects.filter(
                code__in={c for row in MATRIX for c in row[1] + row[2]}
            )
        }
        matrix_ind_ids = set()
        matrix_unit_ids = set()

        def apply(ind, unit, role, is_pj):
            nonlocal created, updated
            lookup = dict(indikator=ind, unit=unit, role_scope=role)
            defaults = dict(is_pj=is_pj, boleh_input=True)
            if dry:
                exists = InmUnitMapping.objects.filter(**lookup).exists()
                if exists:
                    updated += 1
                else:
                    created += 1
                return
            _, was_created = InmUnitMapping.objects.update_or_create(
                **lookup, defaults=defaults
            )
            if was_created:
                created += 1
            else:
                updated += 1

        for kode, pj_codes, unit_codes, roles in MATRIX:
            ind = ind_map.get(kode)
            if not ind:
                warnings.append(f'[SKIP] INM {kode} tidak ditemukan di IndikatorMutu')
                skipped += 1
                continue
            matrix_ind_ids.add(ind.pk)

            for code in dict.fromkeys(pj_codes + unit_codes):
                unit = unit_map.get(code)
                if not unit:
                    warnings.append(f'[SKIP] {kode}: unit {code} tidak ditemukan')
                    skipped += 1
                    continue
                matrix_unit_ids.add(unit.pk)
                apply(ind, unit, '', code in pj_codes)

            for role in roles:
                apply(ind, None, role, False)

        # INM kanonik yang tidak tercantum di matriks tetap harus terlihat oleh
        # unit PJ-nya, supaya tidak ada indikator yang hilang setelah auto-hide.
        unlisted = [
            i for i in IndikatorMutu.objects.filter(
                inm_induk__isnull=True, jenis__in=('INM', 'NASIONAL'), aktif=True
            )
            if i.pk not in matrix_ind_ids
        ]
        for ind in unlisted:
            if not ind.unit_id:
                warnings.append(
                    f'[SKIP] {ind.kode_indikator} tidak ada di matriks dan tidak punya unit PJ'
                )
                skipped += 1
                continue
            apply(ind, ind.unit, '', True)

        if opts['prune'] and not dry:
            with transaction.atomic():
                del_qs = InmUnitMapping.objects.filter(
                    indikator__jenis__in=('INM', 'NASIONAL')
                ).exclude(indikator_id__in=matrix_ind_ids)
                removed = del_qs.count()
                del_qs.delete()
            self.stdout.write(f'[PRUNE] {removed} baris di luar matriks dihapus')
        elif opts['prune']:
            self.stdout.write('[PRUNE] dilewati (dry-run)')

        for w in warnings:
            self.stderr.write(w)

        self.stdout.write(self.style.SUCCESS(
            f'Seed selesai — created={created} updated={updated} skipped={skipped} '
            f'{"(DRY-RUN)" if dry else ""}'
        ))

        if opts['strict'] and skipped:
            raise SystemExit(1)
