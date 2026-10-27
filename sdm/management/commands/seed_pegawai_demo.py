"""Seed demo employees so the HC surfaces have real data to render.

The project ships demo accounts and accreditation data but no employees, so
every employee-centric page (profile card, document vault, credential
requests) renders empty and the upload route cannot be reached at all.
This command fills that gap with a small, clearly-labelled demo roster.

Run: python manage.py seed_pegawai_demo [--apply]
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import (
    IzinProfesiPegawai,
    MasterProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
)

# name, profession master code, kategori, unit code, jumlah years of service,
# STR number, licence state ('valid' | 'expiring' | 'expired' | None)
ROSTER = [
    ('Ahmad Fauzi', 'KPR', 'PPA', 'RUANG-OK', 6, 'STR-KPR-001', 'valid'),
    ('Siti Nurhaliza', 'BID', 'PPA', 'TIM-PONEK', 9, 'STR-BID-002', 'expiring'),
    ('Budi Santoso', 'DOKTER_UMUM', 'PPA', 'AUDIT-MED', 4, 'STR-DU-003', 'valid'),
    ('Rina Wati', 'KPR', 'PPA', 'MUTU-PEL', 11, 'STR-KPR-004', 'expired'),
    ('Dedi Kurniawan', 'DOKTER_GIGI', 'PPA', 'HUMAS-CS', 3, None, None),
    ('Yuni Astuti', 'KPR', 'NON_PPA', 'AUDIT-OPS', 2, None, None),
]


class Command(BaseCommand):
    help = 'Seed demo employees with placements and STR so HC pages have data.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write the roster. Without it the command reports what it would do.',
        )

    def handle(self, *args, **options):
        apply_changes = options['apply']
        today = timezone.localdate()
        profesi = {p.code: p for p in MasterProfesiPegawai.objects.all()}
        units = {u.code: u for u in UnitKerja.objects.filter(is_active=True)}

        created = 0
        skipped = 0
        missing = []
        for index, (name, prof_code, kategori, unit_code, years, str_no, state) in enumerate(ROSTER, start=1):
            unit = units.get(unit_code)
            master = profesi.get(prof_code)
            if unit is None or master is None:
                missing.append(f'{name}: unit={unit_code or "?"} profesi={prof_code}')
                continue
            if Pegawai.objects.filter(nama_lengkap=name).exists():
                skipped += 1
                self.stdout.write(f'  = {name} sudah ada, dilewati')
                continue
            if not apply_changes:
                self.stdout.write(f'  + {name} ({prof_code} @ {unit_code}) akan dibuat')
                created += 1
                continue

            with transaction.atomic():
                employee = Pegawai.objects.create(
                    nama_lengkap=name,
                    kategori=kategori,
                    profesi=master.nama,
                    profesi_master=master,
                    jabatan=master.nama,
                    data_origin='DEMO',
                    status='AKTIF',
                    nomor_pegawai=f'DEMO-{index:05d}',
                )
                PenempatanPegawai.objects.create(
                    pegawai=employee,
                    unit_kerja=unit,
                    tanggal_mulai=today - timedelta(days=365 * years),
                    alokasi_fte=Decimal('1.00'),
                )
                self._licence(employee, master, str_no, state, today)
            created += 1
            self.stdout.write(f'  + {name} ({prof_code} @ {unit_code}) dibuat')

        for line in missing:
            self.stdout.write(self.style.WARNING(f'  ! dilewati: {line}'))
        summary = (
            f'{created} pegawai demo {"dibuat" if apply_changes else "siap dibuat"}, '
            f'{skipped} sudah ada'
        )
        if apply_changes:
            self.stdout.write(self.style.SUCCESS(summary))
        else:
            self.stdout.write(summary + ' — jalankan ulang dengan --apply')

    @staticmethod
    def _licence(employee, master, str_no, state, today):
        if not str_no:
            return
        offsets = {
            'valid': (today + timedelta(days=700)),
            'expiring': (today + timedelta(days=20)),
            'expired': (today - timedelta(days=30)),
        }
        IzinProfesiPegawai.objects.create(
            pegawai=employee,
            subtype='STR',
            nomor_izin=str_no,
            profesi=master.nama,
            pemberi_izin='KTKI',
            validity_mode='EXPIRY_REQUIRED',
            tanggal_terbit=today - timedelta(days=365 * 2),
            tanggal_berakhir=offsets[state],
            is_local_rs=True,
        )
