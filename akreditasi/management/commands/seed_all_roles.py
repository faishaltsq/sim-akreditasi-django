"""
Management Command: seed_all_roles
Mengisi database dengan akun untuk SEMUA 6 TINGKATAN ROLE beserta isi data riilnya:
1. SUPER_ADMIN (IT RS / Admin Global)
2. ADMIN_RS (Ketua Komite Mutu RS)
3. KOORDINATOR_POKJA (TKRS, PMKP, KPS)
4. KEPALA_UNIT (Rawat Inap, Farmasi, Laboratorium)
5. STAF_NAKES (Perawat, Dokter Spesialis, Apoteker, Analis Lab)
6. ASESOR (Surveior Akreditasi KARS)
Lengkap dengan Pokja baru (KPS, PMKP), EP, Evidences, dan Dokumen Portofolio Nakes.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date

from accounts.models import UserProfile, NakesCredential
from akreditasi.models import (
    Framework, UnitKerja, Category,
    StandardItem, EvidenceReq, QualityRecord, EvidenceFile
)


class Command(BaseCommand):
    help = 'Seed data untuk semua tingkatan akun beserta konten matriks dan portofolionya.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING('=== SEEDING SEMUA TINGKATAN AKUN SIM AKREDITASI ===\n'))

        # ----------------------------------------------------
        # 1. FRAMEWORK & POKJA
        # ----------------------------------------------------
        fw, _ = Framework.objects.get_or_create(
            name='STARKES Edisi 2022 / Kemenkes RI',
            defaults={'cycle_type': 'PDCA', 'version': '2026'}
        )

        pokja_tkrs, _ = Category.objects.get_or_create(
            code='TKRS', framework=fw,
            defaults={'name': 'Tata Kelola Rumah Sakit', 'order': 1}
        )
        pokja_pmkp, _ = Category.objects.get_or_create(
            code='PMKP', framework=fw,
            defaults={'name': 'Peningkatan Mutu & Keselamatan Pasien', 'order': 2}
        )
        pokja_kps, _ = Category.objects.get_or_create(
            code='KPS', framework=fw,
            defaults={'name': 'Kualifikasi & Pendidikan Staf', 'order': 3}
        )

        # ----------------------------------------------------
        # 2. UNIT KERJA
        # ----------------------------------------------------
        dir_yanmed, _ = UnitKerja.objects.get_or_create(
            code='DIR-MED',
            defaults={'name': 'Direktorat Pelayanan Medik & Keperawatan', 'level': 1}
        )
        dir_mutu, _ = UnitKerja.objects.get_or_create(
            code='DIR-MUTU',
            defaults={'name': 'Sekretariat Dewas & Direksi', 'level': 1}
        )
        bid_yanmed, _ = UnitKerja.objects.get_or_create(
            code='BID-YAN',
            defaults={'name': 'Bidang Pelayanan Medis', 'parent': dir_yanmed, 'level': 2}
        )
        bid_penunjang, _ = UnitKerja.objects.get_or_create(
            code='BID-PENJ',
            defaults={'name': 'Bidang Penunjang Medis', 'parent': dir_yanmed, 'level': 2}
        )
        unit_ranap, _ = UnitKerja.objects.get_or_create(
            code='RANAP',
            defaults={'name': 'Unit Rawat Inap', 'parent': bid_yanmed, 'level': 3}
        )
        unit_igd, _ = UnitKerja.objects.get_or_create(
            code='IGD',
            defaults={'name': 'Instalasi Gawat Darurat', 'parent': bid_yanmed, 'level': 3}
        )
        unit_farmasi, _ = UnitKerja.objects.get_or_create(
            code='FARM',
            defaults={'name': 'Unit Pelayanan Farmasi', 'parent': bid_penunjang, 'level': 3}
        )
        unit_lab, _ = UnitKerja.objects.get_or_create(
            code='LAB',
            defaults={'name': 'Laboratorium Patologi Klinik', 'parent': bid_penunjang, 'level': 3}
        )

        # ----------------------------------------------------
        # 3. KONTEN EP UNTUK PMKP & KPS (AGAR ADA ISINYA)
        # ----------------------------------------------------
        # PMKP EP
        pmkp_items = [
            (
                'PMKP 1 EP 1', 'PMKP 1', 'Pengelolaan Kegiatan PMKP',
                'Direktur menetapkan penanggung jawab kegiatan PMKP (Komite/Tim Mutu) dan uraian tugasnya.',
                1, dir_mutu,
                [('R', 'SK Pembentukan Komite Mutu & Keselamatan Pasien', True),
                 ('D', 'Program Kerja Komite Mutu Tahunan 2026', True)],
                {'score': 10, 'baseline_data': 'Komite mutu telah aktif dan teregistrasi Kemenkes.', 'quality_target': '100% kepatuhan tata kelola mutu.'}
            ),
            (
                'PMKP 2 EP 1', 'PMKP 2', 'Pemilihan dan Pengumpulan Indikator Mutu',
                'Komite Mutu mengumpulkan dan menganalisis 13 Indikator Nasional Mutu (INM) setiap bulan.',
                2, unit_ranap,
                [('D', 'Laporan Bulanan INM ke Aplikasi SIMAR/Kemenkes', True),
                 ('O', 'Bukti Penginputan Real-Time di Ruangan', False)],
                {'score': 10, 'baseline_data': 'Capaian kepatuhan kebersihan tangan (KKT) 88% (Target >85%).', 'quality_target': 'KKT >85% stabil.'}
            ),
        ]
        for code, sub, subtitle, desc, order, unit, reqs, rec in pmkp_items:
            it, created = StandardItem.objects.get_or_create(
                code=code, category=pokja_pmkp,
                defaults={'sub_standard': sub, 'sub_title': subtitle, 'description': desc, 'order': order}
            )
            # Selalu pastikan EvidenceReq terisi
            for r_type, title, mand in reqs:
                EvidenceReq.objects.get_or_create(
                    standard_item=it, category_type=r_type, title=title,
                    defaults={'is_mandatory': mand}
                )
            if not QualityRecord.objects.filter(standard_item=it).exists():
                QualityRecord.objects.create(standard_item=it, unit=unit, **rec)

        # KPS EP
        kps_items = [
            (
                'KPS 1 EP 1', 'KPS 1', 'Perencanaan Kebutuhan Staf',
                'Direktur menetapkan perencanaan kebutuhan staf rumah sakit berdasarkan beban kerja (ABK).',
                1, dir_mutu,
                [('R', 'Dokumen Analisis Beban Kerja (ABK) & Renbut Staf RS', True),
                 ('D', 'Pola Ketenagaan Terintegrasi 2026', True)],
                {'score': 10, 'baseline_data': 'Pola ketenagaan telah mengadopsi standar Kemenkes.', 'quality_target': 'Kesesuaian ABK >90%.'}
            ),
            (
                'KPS 8 EP 1', 'KPS 8', 'Kredensial Tenaga Medis & Keperawatan',
                'Rumah sakit menyelenggarakan kredensialing bagi seluruh staf medis dan keperawatan sebelum praktik.',
                2, unit_igd,
                [('R', 'Pedoman Kredensial & Rekredensial Komite Medis/Keperawatan', True),
                 ('D', 'Berkas Verifikasi STR, SIP, SPK, dan RKK Staf', True)],
                {'score': 10, 'baseline_data': 'Seluruh staf medis aktif memiliki SPK dan RKK yang sah.', 'quality_target': '100% nakes tersertifikasi.'}
            ),
        ]
        for code, sub, subtitle, desc, order, unit, reqs, rec in kps_items:
            it, created = StandardItem.objects.get_or_create(
                code=code, category=pokja_kps,
                defaults={'sub_standard': sub, 'sub_title': subtitle, 'description': desc, 'order': order}
            )
            # Selalu pastikan EvidenceReq terisi
            for r_type, title, mand in reqs:
                EvidenceReq.objects.get_or_create(
                    standard_item=it, category_type=r_type, title=title,
                    defaults={'is_mandatory': mand}
                )
            if not QualityRecord.objects.filter(standard_item=it).exists():
                QualityRecord.objects.create(standard_item=it, unit=unit, **rec)

        self.stdout.write(self.style.SUCCESS('  ✓ Data Pokja PMKP & KPS berhasil dibuat'))

        # ----------------------------------------------------
        # 4. MEMBUAT AKUN SEMUA 6 TINGKATAN
        # ----------------------------------------------------
        ACCOUNTS = [
            # 1. SUPER_ADMIN
            {
                'username': 'admin',
                'password': 'admin123',
                'email': 'admin@simakreditasi.id',
                'full_name': 'Ahmad Fauzi, S.Kom (IT RS)',
                'jabatan': 'Kepala Subbag TI / Super Admin Sistem',
                'role': 'SUPER_ADMIN',
                'unit': dir_mutu,
                'is_staff': True,
                'is_super': True,
            },
            # 2. ADMIN_RS
            {
                'username': 'admin.mutu',
                'password': 'Mutu@1234',
                'email': 'mutu@simakreditasi.id',
                'full_name': 'dr. Hendra Gunawan, M.Kes',
                'jabatan': 'Ketua Komite Mutu & Akreditasi RS',
                'role': 'ADMIN_RS',
                'unit': dir_mutu,
                'is_staff': False,
            },
            # 3. KOORDINATOR_POKJA (3 Pokja Utama)
            {
                'username': 'koord.tkrs',
                'password': 'Pokja@1234',
                'email': 'tkrs@simakreditasi.id',
                'full_name': 'dr. Andi Prasetyo, Sp.PD',
                'jabatan': 'Ketua Kelompok Kerja (Pokja) TKRS',
                'role': 'KOORDINATOR_POKJA',
                'unit': bid_yanmed,
            },
            {
                'username': 'koord.pmkp',
                'password': 'Pokja@1234',
                'email': 'pmkp@simakreditasi.id',
                'full_name': 'drg. Sartika Handayani, M.Kes',
                'jabatan': 'Ketua Kelompok Kerja (Pokja) PMKP',
                'role': 'KOORDINATOR_POKJA',
                'unit': dir_mutu,
            },
            {
                'username': 'koord.kps',
                'password': 'Pokja@1234',
                'email': 'kps@simakreditasi.id',
                'full_name': 'Siti Rahmawati, S.Psi, MM',
                'jabatan': 'Ketua Kelompok Kerja (Pokja) KPS & SDM',
                'role': 'KOORDINATOR_POKJA',
                'unit': dir_mutu,
            },
            # 4. KEPALA_UNIT (3 Unit Layanan)
            {
                'username': 'ka.ranap',
                'password': 'Unit@1234',
                'email': 'ranap@simakreditasi.id',
                'full_name': 'Ns. Hendra Wijaya, S.Kep',
                'jabatan': 'Kepala Unit Rawat Inap Terpadu',
                'role': 'KEPALA_UNIT',
                'unit': unit_ranap,
            },
            {
                'username': 'ka.farmasi',
                'password': 'Unit@1234',
                'email': 'farmasi@simakreditasi.id',
                'full_name': 'apt. Nurul Fatimah, S.Farm',
                'jabatan': 'Kepala Instalasi Farmasi RS',
                'role': 'KEPALA_UNIT',
                'unit': unit_farmasi,
            },
            {
                'username': 'ka.lab',
                'password': 'Unit@1234',
                'email': 'lab@simakreditasi.id',
                'full_name': 'dr. Yusuf, Sp.PK',
                'jabatan': 'Kepala Instalasi Laboratorium Patologi',
                'role': 'KEPALA_UNIT',
                'unit': unit_lab,
            },
            # 5. STAF_NAKES (4 Profesi Berbeda)
            {
                'username': 'perawat.igd',
                'password': 'Nakes@1234',
                'email': 'perawat@simakreditasi.id',
                'full_name': 'Ns. Siti Rahayu, S.Kep',
                'jabatan': 'Perawat Pelaksana Emergency IGD',
                'role': 'STAF_NAKES',
                'profesi': 'PERAWAT',
                'nip_nrp': '199001012020012001',
                'unit': unit_igd,
            },
            {
                'username': 'dokter.spesialis',
                'password': 'Nakes@1234',
                'email': 'dokter@simakreditasi.id',
                'full_name': 'dr. Budi Santoso, Sp.PD',
                'jabatan': 'Dokter Spesialis Penyakit Dalam',
                'role': 'STAF_NAKES',
                'profesi': 'DOKTER_SPESIALIS',
                'nip_nrp': '198507152015011002',
                'unit': unit_ranap,
            },
            {
                'username': 'apoteker.farmasi',
                'password': 'Nakes@1234',
                'email': 'apoteker@simakreditasi.id',
                'full_name': 'Apt. Dewi Lestari, S.Farm',
                'jabatan': 'Apoteker Klinis Bangsal Rawat Inap',
                'role': 'STAF_NAKES',
                'profesi': 'APOTEKER',
                'nip_nrp': '199203082017022003',
                'unit': unit_farmasi,
            },
            {
                'username': 'analis.lab',
                'password': 'Nakes@1234',
                'email': 'analis@simakreditasi.id',
                'full_name': 'Rian Hidayat, A.Md.AK',
                'jabatan': 'Pranata Laboratorium Kesehatan',
                'role': 'STAF_NAKES',
                'profesi': 'ANALIS_LAB',
                'nip_nrp': '199505122019031005',
                'unit': unit_lab,
            },
            # 6. ASESOR
            {
                'username': 'asesor.kars',
                'password': 'Asesor@1234',
                'email': 'surveior@kars.or.id',
                'full_name': 'Dr. dr. H. Soepardi, Sp.A(K), FISQua',
                'jabatan': 'Surveior Akreditasi KARS Bidang Medis',
                'role': 'ASESOR',
                'unit': dir_mutu,
            },
        ]

        self.stdout.write(self.style.MIGRATE_LABEL('\n--- Membuat / Memperbarui Akun ---'))
        for acc in ACCOUNTS:
            uname = acc['username']
            u, created = User.objects.get_or_create(
                username=uname,
                defaults={
                    'email': acc.get('email', ''),
                    'first_name': acc['full_name'].split()[0],
                    'is_staff': acc.get('is_staff', False),
                    'is_superuser': acc.get('is_super', False),
                }
            )
            # Selalu reset password agar pasti bisa login
            u.set_password(acc['password'])
            u.save()

            profile, _ = UserProfile.objects.update_or_create(
                user=u,
                defaults={
                    'role': acc['role'],
                    'full_name': acc['full_name'],
                    'jabatan': acc['jabatan'],
                    'profesi': acc.get('profesi', ''),
                    'nip_nrp': acc.get('nip_nrp', ''),
                    'unit_kerja': acc.get('unit'),
                    'is_active_member': True,
                }
            )
            verb = 'Dibuat' if created else 'Diupdate'
            self.stdout.write(f"  ✓ [{acc['role']:<17}] {uname:<16} ({verb}) — {acc['full_name']}")

        # ----------------------------------------------------
        # 5. DOKUMEN KPS UNTUK ANALIS LAB BARU
        # ----------------------------------------------------
        analis_user = User.objects.get(username='analis.lab')
        analis_prof = analis_user.profile
        if not analis_prof.credentials.exists():
            NakesCredential.objects.create(
                user_profile=analis_prof,
                doc_type='STR',
                title='STR Pranata Laboratorium — Rian Hidayat',
                document_number='STR-LAB-2024-881',
                issued_date=date(2024, 2, 1),
                valid_until=date(2029, 1, 31),
                status='VERIFIED',
            )
            NakesCredential.objects.create(
                user_profile=analis_prof,
                doc_type='SIP',
                title='SIP Petugas Laboratorium RS',
                document_number='SIP-LAB-2024-019',
                issued_date=date(2024, 2, 15),
                valid_until=date(2027, 2, 14),
                status='VERIFIED',
            )
            NakesCredential.objects.create(
                user_profile=analis_prof,
                doc_type='PELATIHAN_PPI',
                title='Sertifikat Workshop K3 Laboratorium & Biosafety',
                document_number='PPI-LAB-2023-55',
                issued_date=date(2023, 10, 10),
                valid_until=date(2025, 10, 9),
                status='VERIFIED',
            )
            self.stdout.write(self.style.SUCCESS('  ✓ 3 Berkas KPS untuk analis.lab ditambahkan'))

        self.stdout.write(self.style.SUCCESS('\n=== SEMUA TINGKATAN AKUN LENGKAP & SIAP DIUJI ===\n'))
