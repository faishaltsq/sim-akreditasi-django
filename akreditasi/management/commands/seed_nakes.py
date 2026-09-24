"""
Management command: seed_nakes
Membuat akun demo staf nakes lengkap dengan kredensial STR/SIP/Pelatihan contoh.

Jalankan:
    python manage.py seed_nakes
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

from accounts.models import UserProfile, NakesCredential
from akreditasi.models import UnitKerja


NAKES_DATA = [
    {
        'username': 'perawat.igd',
        'password': 'Nakes@1234',
        'full_name': 'Ns. Siti Rahayu, S.Kep',
        'jabatan': 'Perawat Pelaksana IGD',
        'profesi': 'PERAWAT',
        'nip_nrp': '199001012020012001',
        'unit_code': None,  # akan di-match ke unit pertama yang ada
        'unit_keywords': ['IGD', 'gawat darurat', 'emergency'],
        'credentials': [
            {
                'doc_type': 'STR',
                'title': 'STR Perawat — Ns. Siti Rahayu, S.Kep',
                'document_number': 'STR-19001-2024',
                'issued_date': date(2024, 1, 15),
                'valid_until': date(2029, 1, 14),
                'status': 'VERIFIED',
            },
            {
                'doc_type': 'SIP',
                'title': 'SIP Perawat — RSUD Contoh, Kab. Demo',
                'document_number': 'SIP-0098-2024',
                'issued_date': date(2024, 2, 1),
                'valid_until': date(2027, 1, 31),
                'status': 'VERIFIED',
            },
            {
                'doc_type': 'PELATIHAN_BHD',
                'title': 'Sertifikat BLS/ACLS — RSUD Contoh 2024',
                'document_number': 'BLS-2024-001',
                'issued_date': date(2024, 3, 10),
                'valid_until': date(2026, 3, 9),
                'status': 'VERIFIED',
            },
            {
                'doc_type': 'PELATIHAN_PPI',
                'title': 'Sertifikat Pelatihan Dasar PPI',
                'document_number': 'PPI-2023-88',
                'issued_date': date(2023, 9, 5),
                'valid_until': None,
                'status': 'PENDING',
            },
        ],
    },
    {
        'username': 'dokter.spesialis',
        'password': 'Nakes@1234',
        'full_name': 'dr. Budi Santoso, Sp.PD',
        'jabatan': 'Dokter Spesialis Penyakit Dalam',
        'profesi': 'DOKTER_SPESIALIS',
        'nip_nrp': '198507152015011002',
        'unit_keywords': ['Rawat Inap', 'inap', 'penyakit dalam'],
        'credentials': [
            {
                'doc_type': 'STR',
                'title': 'STR Dokter Spesialis Penyakit Dalam — dr. Budi Santoso',
                'document_number': 'STR-SPESIALIS-2022-012',
                'issued_date': date(2022, 6, 1),
                'valid_until': date(2027, 5, 31),
                'status': 'VERIFIED',
            },
            {
                'doc_type': 'SIP',
                'title': 'SIP Dokter Spesialis Penyakit Dalam — RS Demo',
                'document_number': 'SIP-SP-PD-2023-007',
                'issued_date': date(2023, 1, 10),
                'valid_until': date(2026, 1, 9),
                'status': 'VERIFIED',
            },
            {
                'doc_type': 'SPK_RKK',
                'title': 'Surat Penugasan Klinis & RKK Sp.PD',
                'document_number': 'SPK-2023-PD-015',
                'issued_date': date(2023, 1, 15),
                'valid_until': date(2025, 12, 31),
                'status': 'EXPIRED',  # sengaja expired untuk demo warning
            },
        ],
    },
    {
        'username': 'apoteker.farmasi',
        'password': 'Nakes@1234',
        'full_name': 'Apt. Dewi Lestari, S.Farm',
        'jabatan': 'Apoteker Klinis',
        'profesi': 'APOTEKER',
        'nip_nrp': '199203082017022003',
        'unit_keywords': ['Farmasi', 'farmasi', 'apotek'],
        'credentials': [
            {
                'doc_type': 'STR',
                'title': 'STR Apoteker — Apt. Dewi Lestari, S.Farm',
                'document_number': 'STRA-2024-DL-009',
                'issued_date': date(2024, 4, 1),
                'valid_until': date(2029, 3, 31),
                'status': 'PENDING',
            },
            {
                'doc_type': 'PELATIHAN_PMKP',
                'title': 'Sertifikat Pelatihan Mutu & Keselamatan Pasien',
                'document_number': 'PMKP-2024-022',
                'issued_date': date(2024, 5, 20),
                'valid_until': None,
                'status': 'VERIFIED',
            },
            {
                'doc_type': 'PELATIHAN_K3RS',
                'title': 'Sertifikat K3RS & Penanggulangan Kebakaran',
                'document_number': 'K3RS-2023-044',
                'issued_date': date(2023, 11, 15),
                'valid_until': date(2025, 11, 14),
                'status': 'VERIFIED',
            },
        ],
    },
]


class Command(BaseCommand):
    help = 'Buat akun demo staf nakes beserta kredensial KPS untuk pengujian fitur Portal Nakes.'

    def handle(self, *args, **options):
        all_units = list(UnitKerja.objects.all())
        created_count = 0
        skipped_count = 0

        for data in NAKES_DATA:
            username = data['username']

            if User.objects.filter(username=username).exists():
                self.stdout.write(self.style.WARNING(f'  → Skip (sudah ada): {username}'))
                skipped_count += 1
                continue

            # Cari unit yang cocok
            matched_unit = None
            for keyword in data.get('unit_keywords', []):
                for u in all_units:
                    if keyword.lower() in u.name.lower():
                        matched_unit = u
                        break
                if matched_unit:
                    break
            # Fallback: ambil unit pertama
            if not matched_unit and all_units:
                matched_unit = all_units[0]

            # Buat User
            user = User.objects.create_user(
                username=username,
                password=data['password'],
                first_name=data['full_name'].split(',')[0] if ',' in data['full_name'] else data['full_name'],
            )

            # Buat/Update profile
            profile, _ = UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    'role': 'STAF_NAKES',
                    'full_name': data['full_name'],
                    'jabatan': data['jabatan'],
                    'profesi': data['profesi'],
                    'nip_nrp': data['nip_nrp'],
                    'unit_kerja': matched_unit,
                    'is_active_member': True,
                }
            )

            # Buat kredensial KPS
            for cred_data in data.get('credentials', []):
                NakesCredential.objects.create(
                    user_profile=profile,
                    doc_type=cred_data['doc_type'],
                    title=cred_data['title'],
                    document_number=cred_data['document_number'],
                    issued_date=cred_data['issued_date'],
                    valid_until=cred_data.get('valid_until'),
                    status=cred_data['status'],
                    file_url='',
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f'  ✓ Akun: {username} | Unit: {matched_unit.name if matched_unit else "-"} | '
                    f'{len(data["credentials"])} dokumen KPS dibuat'
                )
            )
            created_count += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Selesai! {created_count} akun nakes dibuat, {skipped_count} dilewati.'
        ))
        self.stdout.write('Login dengan password: Nakes@1234')
