"""
Management Command: seed_hospital_type_b
Menambahkan seluruh unit kerja dan instalasi standar Rumah Sakit Kelas B
sesuai Permenkes No. 3/2020, Permenkes 56/2014, dan STARKES 2022.
"""
from django.core.management.base import BaseCommand
from akreditasi.models import UnitKerja

class Command(BaseCommand):
    help = 'Seed struktur organisasi dan unit kerja lengkap RS Tipe B'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.MIGRATE_HEADING('=== SEEDING STRUKTUR RS TIPE B (STANDAR KEMENKES & STARKES) ===\n'))

        # ==========================================================
        # LEVEL 1: DIREKTORAT / PIMPINAN
        # ==========================================================
        dir_mutu, _ = UnitKerja.objects.get_or_create(
            code='DIR-MUTU',
            defaults={
                'name': 'Sekretariat Dewas, Direksi & Komite Mutu',
                'level': 1,
                'pic_name': 'drg. Sartika Handayani, M.Kes',
                'description': 'Membawahi Dewan Pengawas, Direktur Utama, Komite Mutu, dan Komite Medis/Keperawatan.'
            }
        )
        dir_med, _ = UnitKerja.objects.get_or_create(
            code='DIR-MED',
            defaults={
                'name': 'Direktorat Pelayanan Medik & Keperawatan',
                'level': 1,
                'pic_name': 'Dr. dr. Haryono, Sp.B',
                'description': 'Membawahi seluruh bidang pelayanan medis, keperawatan, dan pelayanan kritis.'
            }
        )
        dir_penj, _ = UnitKerja.objects.get_or_create(
            code='DIR-PENJ',
            defaults={
                'name': 'Direktorat Penunjang Medis & Sarana',
                'level': 1,
                'pic_name': 'dr. Maya Lestari, Sp.PK',
                'description': 'Membawahi penunjang diagnostik klinis, farmasi, rekam medis, dan sarana prasarana.'
            }
        )
        dir_um, _ = UnitKerja.objects.get_or_create(
            code='DIR-UM',
            defaults={
                'name': 'Direktorat Umum, SDM & Keuangan',
                'level': 1,
                'pic_name': 'Ir. Rudi Hartono, MM',
                'description': 'Membawahi tata usaha, keuangan, kepegawaian/diklat, logistik, dan hukum.'
            }
        )

        # ==========================================================
        # LEVEL 2: BIDANG & BAGIAN
        # ==========================================================
        # Di bawah DIR-MED
        bid_yanmed, _ = UnitKerja.objects.get_or_create(
            code='BID-YAN',
            defaults={
                'name': 'Bidang Pelayanan Medis',
                'parent': dir_med,
                'level': 2,
                'pic_name': 'dr. Andi Prasetyo, Sp.PD',
                'description': 'Mengatur operasional medis gawat darurat, rawat inap, rawat jalan, dan bedah.'
            }
        )
        bid_kep, _ = UnitKerja.objects.get_or_create(
            code='BID-KEP',
            defaults={
                'name': 'Bidang Keperawatan & Kebidanan',
                'parent': dir_med,
                'level': 2,
                'pic_name': 'Ns. Sri Wahyuni, M.Kep',
                'description': 'Mengkoordinasi standar asuhan keperawatan, logistik perawat, dan etika keperawatan.'
            }
        )
        bid_kritis, _ = UnitKerja.objects.get_or_create(
            code='BID-KRITIS',
            defaults={
                'name': 'Bidang Pelayanan Kritis & Khusus',
                'parent': dir_med,
                'level': 2,
                'pic_name': 'dr. Bambang Irawan, Sp.An-KIC',
                'description': 'Mengkoordinasi ICU, ICCU, NICU, PICU, dan Kamar Operasi (IBS).'
            }
        )

        # Di bawah DIR-PENJ
        bid_penj, _ = UnitKerja.objects.get_or_create(
            code='BID-PENJ',
            defaults={
                'name': 'Bidang Penunjang Medis Diagnostik',
                'parent': dir_penj,
                'level': 2,
                'pic_name': 'dr. Yusuf, Sp.PK',
                'description': 'Membawahi Laboratorium, Radiologi, Farmasi, Bank Darah, dan Rehabilitasi Medik.'
            }
        )
        bid_sarana, _ = UnitKerja.objects.get_or_create(
            code='BID-SARANA',
            defaults={
                'name': 'Bidang Penunjang Non-Klinis & Fasilitas (MFK)',
                'parent': dir_penj,
                'level': 2,
                'pic_name': 'Ir. Dedi Supriyadi, ST',
                'description': 'Membawahi IPSRS, Kesehatan Lingkungan, Laundry, Gizi, CSSD, dan SIMRS.'
            }
        )

        # Di bawah DIR-UM
        bag_sdm, _ = UnitKerja.objects.get_or_create(
            code='SDM',
            defaults={
                'name': 'Bagian SDM, Hukum & Diklat',
                'parent': dir_um,
                'level': 2,
                'pic_name': 'Siti Rahmawati, S.Psi, MM',
                'description': 'Perencanaan staf, kredensial, orientasi karyawan, dan pengembangan kompetensi (KPS).'
            }
        )
        bag_keu, _ = UnitKerja.objects.get_or_create(
            code='KEU',
            defaults={
                'name': 'Bagian Keuangan & Akuntansi',
                'parent': dir_um,
                'level': 2,
                'pic_name': 'Hj. Ratna Sari, SE, Ak',
                'description': 'Penganggaran RKA akreditasi, billing, klaim BPJS, dan perbendaharaan.'
            }
        )
        bag_umum, _ = UnitKerja.objects.get_or_create(
            code='BAG-UMUM',
            defaults={
                'name': 'Bagian Umum, Logistik & Rumah Tangga',
                'parent': dir_um,
                'level': 2,
                'pic_name': 'Bambang Sukoco, S.Sos',
                'description': 'Pengadaan barang, keamanan/satpam, transportasi ambulans, dan kerumahtanggaan.'
            }
        )

        # ==========================================================
        # LEVEL 3: INSTALASI, RUANGAN & UNIT PELAKSANA
        # ==========================================================
        LEVEL3_UNITS = [
            # Pelayanan Medis (BID-YAN)
            ('IGD', 'Instalasi Gawat Darurat (IGD 24 Jam & PONEK)', bid_yanmed, 'dr. Rizky Pratama', 'Pintu masuk darurat RS 24 jam dengan triase ATS.'),
            ('RAJAL', 'Instalasi Rawat Jalan (Poliklinik Spesialis & Subspesialis)', bid_yanmed, 'dr. Dewi Kusuma', 'Klinik rawat jalan 18 poli spesialis sesuai standar RS Kelas B.'),
            ('RANAP', 'Instalasi Rawat Inap (Dewasa, Anak, Bedah)', bid_yanmed, 'Ns. Hendra Wijaya, S.Kep', 'Bangsal perawatan inap dengan kapasitas >200 tempat tidur.'),
            ('VK', 'Instalasi Kamar Bersalin & Kebidanan (PONEK 24 Jam)', bid_yanmed, 'Bdn. Hj. Marwiyah, S.Tr.Keb', 'Pelayanan persalinan normal dan komplikasi obstetri neonatal emergensi.'),

            # Pelayanan Kritis & Khusus (BID-KRITIS)
            ('IBS', 'Instalasi Bedah Sentral (Kamar Operasi / OK)', bid_kritis, 'dr. Taufik Hidayat, Sp.B', 'Kamar operasi terpadu dengan sistem HEPA filter dan standar bedah steril.'),
            ('ICU', 'Instalasi Rawat Intensif Terpadu (ICU & HCU)', bid_kritis, 'dr. Bambang Irawan, Sp.An-KIC', 'Pelayanan intensif dengan ventilator, monitor sentral dan perawat bersertifikat ICU.'),
            ('NICU', 'Instalasi Rawat Intensif Anak & Neonatus (NICU & PICU)', bid_kritis, 'dr. Melisa, Sp.A(K)', 'Perawatan intensif bayi prematur, inkubator, dan ventilator neonatal.'),
            ('HD', 'Unit Hemodialisa (Cuci Darah)', bid_kritis, 'dr. Irfan, Sp.PD-KGH', 'Unit cuci darah kapasitas 16 mesin hemodialisis terakreditasi.'),

            # Penunjang Medis Klinis (BID-PENJ)
            ('FARM', 'Instalasi Pelayanan Farmasi RS (Rawat Jalan, Inap, Depo OK)', bid_penj, 'apt. Nurul Fatimah, S.Farm', 'Pengelolaan perbekalan farmasi, farmasi klinis, dan dispensing steril.'),
            ('LAB', 'Instalasi Laboratorium Patologi Klinik & Anatomi', bid_penj, 'dr. Yusuf, Sp.PK', 'Pemeriksaan hematologi, kimia klinik, imunoserologi, mikrobiologi & PA.'),
            ('RAD', 'Instalasi Radiologi & Diagnostik Imejing (CT-Scan, USG, X-Ray)', bid_penj, 'dr. Hendro, Sp.Rad', 'Pemeriksaan radiologi digital, CT-Scan 128 slice, USG Doppler, dan C-Arm.'),
            ('BDRS', 'Bank Darah Rumah Sakit (BDRS)', bid_penj, 'dr. Yusuf, Sp.PK', 'Penyimpanan, uji cocok serasi (crossmatch), dan distribusi darah transfusi.'),
            ('REHAB', 'Instalasi Rehabilitasi Medik & Fisioterapi', bid_penj, 'dr. Anita, Sp.KFR', 'Pelayanan fisioterapi, terapi wicara, terapi okupasi, dan ortotik prostetik.'),
            ('RM', 'Instalasi Rekam Medis & Manajemen Informasi Kesehatan (MIRM)', bid_penj, 'Ahmad Junaidi, A.Md.PK', 'Pengelolaan berkas rekam medis, RME/e-Resume, koding ICD-10 & klaim INA-CBG.'),

            # Penunjang Non-Klinis & MFK (BID-SARANA)
            ('GIZI', 'Instalasi Gizi & Tata Boga RS', bid_sarana, 'Endang Susilowati, S.Gz, RD', 'Penyelenggaraan makanan pasien, konsultasi gizi rawat jalan & inap, HACCP.'),
            ('CSSD', 'Instalasi Pusat Sterilisasi (CSSD / Central Sterile Supply Dept)', bid_sarana, 'Ns. Joko Purwanto, S.Kep', 'Dekontaminasi, pengemasan, sterilisasi alat medis autoklaf dan plasma.'),
            ('IPSRS', 'Instalasi Pemeliharaan Sarana & Prasarana RS (IPSRS)', bid_sarana, 'Ir. Dedi Supriyadi, ST', 'Pemeliharaan gedung, kalibrasi alat medik, gas medis sentral, genset, chiller.'),
            ('KESLING', 'Instalasi Kesehatan Lingkungan, Sanitasi & IPAL (Limbah B3)', bid_sarana, 'Wawan Setiawan, SKM', 'Pengolahan air limbah (IPAL), incinerator/pihak ke-3 limbah B3, uji mutu air & udara.'),
            ('LAUNDRY', 'Instalasi Linen & Laundry Steril', bid_sarana, 'Siti Munawarah', 'Pencucian infeksius dan non-infeksius, pengelolaan par stock linen ruangan.'),
            ('SIMRS', 'Instalasi SIMRS & Teknologi Informasi Kesehatan', bid_sarana, 'Ahmad Fauzi, S.Kom', 'Infrastruktur server, jaringan LAN/WiFi, bridging SatuSehat Kemenkes & BPJS.'),
            ('JENAZAH', 'Instalasi Pemulasaraan Jenazah & Kedokteran Forensik', bid_sarana, 'dr. Sugeng, Sp.FM', 'Kamar pendingin jenazah, pemulasaraan, transportasi duka, dan visum et repertum.'),

            # Bagian Umum & Rumah Tangga (BAG-UMUM)
            ('K3RS', 'Komite / Unit Keselamatan & Kesehatan Kerja Rumah Sakit (K3RS)', bag_umum, 'dr. Maya Rosida, MKK', 'Manajemen risiko bencana, proteksi kebakaran (APAR/Hydrant), ergonomi staf.'),
            ('AMBULANS', 'Unit Pelayanan Ambulans & Transportasi Medik Rujukan', bag_umum, 'Suranto', 'Armada ambulans gawat darurat transport 118 dan ambulans jenazah 24 jam.'),
            ('SECURITY', 'Unit Keamanan & Ketertiban Lingkungan RS (Satpam)', bag_umum, 'Agus Triyono', 'Pengawasan akses 24 jam, CCTV sentral, dan perlindungan pasien rentan.'),
        ]

        self.stdout.write(self.style.MIGRATE_LABEL('--- Memperbarui Unit Kerja Level 3 (Instalasi & Ruangan) ---'))
        for code, name, parent, pic, desc in LEVEL3_UNITS:
            u, created = UnitKerja.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'parent': parent,
                    'level': 3,
                    'pic_name': pic,
                    'description': desc
                }
            )
            status = 'Dibuat' if created else 'Diupdate'
            self.stdout.write(f"  ✓ [{code:<8}] {status:<8} (Parent: {parent.code:<10}) — {name[:45]}")

        total_units = UnitKerja.objects.count()
        l1 = UnitKerja.objects.filter(level=1).count()
        l2 = UnitKerja.objects.filter(level=2).count()
        l3 = UnitKerja.objects.filter(level=3).count()

        self.stdout.write(self.style.SUCCESS(
            f"\n=== STRUKTUR RS TIPE B LENGKAP TERCATAT ==="
            f"\nTotal Unit Kerja: {total_units}"
            f"\n  • Level 1 (Direktorat) : {l1}"
            f"\n  • Level 2 (Bidang/Bag) : {l2}"
            f"\n  • Level 3 (Instalasi)  : {l3}\n"
        ))
