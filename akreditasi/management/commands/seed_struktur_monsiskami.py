import logging
from django.core.management.base import BaseCommand
from akreditasi.models import UnitKerja, TIPE_UNIT_CHOICES

logger = logging.getLogger(__name__)

# Struktur Arsitektur Menu Hirarkis RS Monsiskami Tipe B
# Format: (kode, nama, parent_code, level, order, tipe)
# level 1: Menu Utama / Direksi
# level 2: Sub-Menu Utama / Direktorat / Bagian / Instalasi Utama
# level 3: Bidang / Bagian / Sub-Instalasi / Poliklinik
# level 4: Seksi / Subbag / Unit / Ruangan
# level 5: Depo / Sub-Tim / Ruang Khusus

# tipe_unit: PIMPINAN | DIREKTORAT | KOMITE | SPI | BAGIAN | INSTALASI | KSM | RUANGAN | DEPO | LAINNYA
STRUKTUR_MONSISKAMI = [
    # =========================================================================
    # MENU UTAMA 1. PEMILIK & PENGAWAS (Level 1)
    # =========================================================================
    ("1.1", "PEMILIK", "Pemilik / Dewan Pembina", None, 1, 10, "PIMPINAN"),
    ("1.2", "DEWAS", "Dewan Pengawas (Dewas)", None, 1, 20, "PIMPINAN"),
    ("1.2.1", "SEK-DEWAS", "Sekretariat Dewan Pengawas", "DEWAS", 2, 21, "BAGIAN"),

    # =========================================================================
    # MENU UTAMA 2. UNSUR PIMPINAN TINGGI (DIREKSI) (Level 1)
    # =========================================================================
    ("2.1", "DIRUT", "Direktur Utama", None, 1, 30, "PIMPINAN"),

    # 2.1.1 SPI
    ("2.1.1", "SPI", "Satuan Pemeriksa Internal (SPI)", "DIRUT", 2, 31, "SPI"),
    ("2.1.1.1", "AUDIT-OPS", "Tim Audit Operasional & Keuangan", "SPI", 3, 32, "BAGIAN"),
    ("2.1.1.2", "AUDIT-MED", "Tim Audit Medik & Governance", "SPI", 3, 33, "BAGIAN"),

    # 2.1.2 Tim Manajemen Mutu & Keselamatan Pasien (KMKP)
    ("2.1.2", "KMKP", "Tim Manajemen Mutu & Keselamatan Pasien", "DIRUT", 2, 34, "KOMITE"),
    ("2.1.2.1", "MUTU-PEL", "Sub-Tim Mutu Pelayanan & Akreditasi", "KMKP", 3, 35, "BAGIAN"),
    ("2.1.2.2", "KP-RISIKO", "Sub-Tim Keselamatan Pasien & Manajemen Risiko", "KMKP", 3, 36, "BAGIAN"),
    ("2.1.2.3", "PPI-TIM", "Sub-Tim Pencegahan & Pengendalian Infeksi (PPI)", "KMKP", 3, 37, "BAGIAN"),

    # 2.1.3 Bagian Tata Usaha & Sekretariat
    ("2.1.3", "TU-SEK", "Bagian Tata Usaha & Sekretariat", "DIRUT", 2, 38, "BAGIAN"),
    ("2.1.3.1", "HUKUM-HUMAS", "Subbag Hukum, Etika RS & Humas", "TU-SEK", 3, 39, "BAGIAN"),
    ("2.1.3.2", "SEK-PELANGGAN", "Subbag Sekretariat & Layanan Pelanggan", "TU-SEK", 3, 40, "BAGIAN"),

    # =========================================================================
    # MENU UTAMA 3. UNSUR PELAKSANA OPERASIONAL (DIREKTORAT) (Level 1 & Sub)
    # =========================================================================
    # 3.1 Direktorat Pelayanan Medik & Keperawatan
    ("3.1", "DIR-MED", "Direktorat Pelayanan Medik & Keperawatan", None, 1, 50, "DIREKTORAT"),

    # 3.1.1 Bidang Pelayanan Medik
    ("3.1.1", "BID-YANMED", "Bidang Pelayanan Medik", "DIR-MED", 2, 51, "BAGIAN"),
    ("3.1.1.1", "SEK-RAJAL-RANAP", "Seksi Pelayanan Rawat Jalan & Rawat Inap", "BID-YANMED", 3, 52, "RUANGAN"),
    ("3.1.1.2", "SEK-IGD-BEDAH", "Seksi Pelayanan Gawat Darurat, Bedah Sentral & Perawatan Intensif", "BID-YANMED", 3, 53, "RUANGAN"),

    # 3.1.2 Bidang Keperawatan
    ("3.1.2", "BID-KEP", "Bidang Keperawatan", "DIR-MED", 2, 54, "BAGIAN"),
    ("3.1.2.1", "SEK-ASUHAN-KEP", "Seksi Asuhan Keperawatan & Kebidanan", "BID-KEP", 3, 55, "RUANGAN"),
    ("3.1.2.2", "SEK-MUTU-LOG-KEP", "Seksi Mutu, Etika, & Logistik Keperawatan", "BID-KEP", 3, 56, "RUANGAN"),

    # 3.1.3 Bidang Pelayanan Penunjang Medik
    ("3.1.3", "BID-PENJMED", "Bidang Pelayanan Penunjang Medik", "DIR-MED", 2, 57, "BAGIAN"),
    ("3.1.3.1", "SEK-PENJ-DIAG", "Seksi Penunjang Diagnostik", "BID-PENJMED", 3, 58, "RUANGAN"),
    ("3.1.3.2", "SEK-PENJ-NONDIAG", "Seksi Penunjang Non-Diagnostik", "BID-PENJMED", 3, 59, "RUANGAN"),

    # 3.2 Direktorat Umum, SDM & Pendidikan
    ("3.2", "DIR-UMUM", "Direktorat Umum, SDM & Pendidikan", None, 1, 60, "DIREKTORAT"),

    # 3.2.1 Bagian Sumber Daya Manusia (SDM) & Kredensial
    ("3.2.1", "BAG-SDM", "Bagian Sumber Daya Manusia (SDM) & Kredensial", "DIR-UMUM", 2, 61, "BAGIAN"),
    ("3.2.1.1", "SUB-REKRUTMEN", "Subbag Rekrutmen & Administrasi Kepegawaian", "BAG-SDM", 3, 62, "RUANGAN"),
    ("3.2.1.2", "SUB-KREDENSIAL", "Subbag Pengembangan SDM, Kredensial & Etika Profesi", "BAG-SDM", 3, 63, "RUANGAN"),

    # 3.2.2 Bagian Umum, Fasilitas & K3RS
    ("3.2.2", "BAG-FASILITAS", "Bagian Umum, Fasilitas & K3RS", "DIR-UMUM", 2, 64, "BAGIAN"),
    ("3.2.2.1", "SUB-RUMAHTANGGA", "Subbag Rumah Tangga, Logistik Non-Medis & Aset", "BAG-FASILITAS", 3, 65, "RUANGAN"),
    ("3.2.2.2", "SUB-IPSRS", "Subbag Sarana Prasarana & IPSRS", "BAG-FASILITAS", 3, 66, "RUANGAN"),
    ("3.2.2.3", "SUB-KESLING", "Subbag Kesling, Sanitasi, & K3RS", "BAG-FASILITAS", 3, 67, "RUANGAN"),

    # 3.2.3 Bagian Pendidikan & Penelitian (Diklit)
    ("3.2.3", "BAG-DIKLIT", "Bagian Pendidikan & Penelitian (Diklit)", "DIR-UMUM", 2, 68, "BAGIAN"),
    ("3.2.3.1", "SUB-PELATIHAN", "Subbag Pelatihan Staf & Pasien", "BAG-DIKLIT", 3, 69, "RUANGAN"),
    ("3.2.3.2", "SUB-LITBANG", "Subbag Penelitian & Pengembangan Service Line", "BAG-DIKLIT", 3, 70, "RUANGAN"),

    # 3.3 Direktorat Keuangan, Akuntansi & SIMRS
    ("3.3", "DIR-KEU", "Direktorat Keuangan, Akuntansi & SIMRS", None, 1, 80, "DIREKTORAT"),

    # 3.3.1 Bagian Keuangan & Penganggaran
    ("3.3.1", "BAG-KEUANGAN", "Bagian Keuangan & Penganggaran", "DIR-KEU", 2, 81, "BAGIAN"),
    ("3.3.1.1", "SUB-ANGGARAN", "Subbag Perencanaan Anggaran & Mobilisasi Dana", "BAG-KEUANGAN", 3, 82, "RUANGAN"),
    ("3.3.1.2", "SUB-KAS", "Subbag Perbendaharaan & Kas", "BAG-KEUANGAN", 3, 83, "RUANGAN"),

    # 3.3.2 Bagian Akuntansi & Klaim
    ("3.3.2", "BAG-AKUNTANSI", "Bagian Akuntansi & Klaim", "DIR-KEU", 2, 84, "BAGIAN"),
    ("3.3.2.1", "SUB-AKUN-MANAJ", "Subbag Akuntansi Keuangan & Manajemen", "BAG-AKUNTANSI", 3, 85, "RUANGAN"),
    ("3.3.2.2", "SUB-KLAIM-BPJS", "Subbag Verifikasi, Billing, & Klaim BPJS/Asuransi", "BAG-AKUNTANSI", 3, 86, "RUANGAN"),

    # 3.3.3 Bagian Teknologi Informasi & Digitalisasi
    ("3.3.3", "BAG-IT", "Bagian Teknologi Informasi & Digitalisasi", "DIR-KEU", 2, 87, "BAGIAN"),
    ("3.3.3.1", "SUB-SIMRS-IT", "Subbag SIMRS, Infrastruktur IT & Analisis Data Pelayanan", "BAG-IT", 3, 88, "RUANGAN"),

    # =========================================================================
    # MENU UTAMA 4. UNSUR PELAKSANA TEKNIS & UNIT KERJA OPERASIONAL (Level 1)
    # =========================================================================
    ("4.0", "PELAKSANA-TEKNIS", "Unsur Pelaksana Teknis & Unit Kerja Operasional", None, 1, 90, "DIREKTORAT"),

    # 4.1 Instalasi Rawat Jalan (IRJ)
    ("4.1", "IRJ", "Instalasi Rawat Jalan (IRJ)", "PELAKSANA-TEKNIS", 2, 91, "INSTALASI"),
    ("4.1.1", "POLI-PD", "Poliklinik Penyakit Dalam", "IRJ", 3, 92, "RUANGAN"),
    ("4.1.2", "POLI-BEDAH", "Poliklinik Bedah (Umum, Orthopedi, Bedah Saraf)", "IRJ", 3, 93, "RUANGAN"),
    ("4.1.3", "POLI-ANAK", "Poliklinik Kesehatan Anak", "IRJ", 3, 94, "RUANGAN"),
    ("4.1.4", "POLI-OBGYN", "Poliklinik Obstetri & Ginekologi (Obgyn)", "IRJ", 3, 95, "RUANGAN"),
    ("4.1.5", "POLI-SPESIALIS", "Poliklinik Spesialis Lain (Jantung, Paru, Saraf, Mata, THT, Jiwa, Kulit)", "IRJ", 3, 96, "RUANGAN"),
    ("4.1.6", "POLI-GIGI", "Poliklinik Gigi & Mulut Spesialis", "IRJ", 3, 97, "RUANGAN"),
    ("4.1.7", "REHAB-MEDIK", "Unit Rehabilitasi Medik & Fisioterapi", "IRJ", 3, 98, "RUANGAN"),

    # 4.2 Instalasi Gawat Darurat (IGD)
    ("4.2", "IGD", "Instalasi Gawat Darurat (IGD)", "PELAKSANA-TEKNIS", 2, 100, "INSTALASI"),
    ("4.2.1", "TRIASE-RESUS", "Unit Triase & Resusitasi", "IGD", 3, 101, "RUANGAN"),
    ("4.2.2", "TINDAKAN-EMERGENCY", "Unit Tindakan Bedah & Non-Bedah", "IGD", 3, 102, "RUANGAN"),
    ("4.2.3", "OBSERVASI-EMERGENCY", "Unit Observasi Emergency", "IGD", 3, 103, "RUANGAN"),

    # 4.3 Instalasi Bedah Sentral (IBS)
    ("4.3", "IBS", "Instalasi Bedah Sentral (IBS)", "PELAKSANA-TEKNIS", 2, 110, "INSTALASI"),
    ("4.3.1", "KAMAR-OPERASI", "Unit Kamar Operasi (OK)", "IBS", 3, 111, "RUANGAN"),
    ("4.3.2", "PACU-RECOVERY", "Unit Recovery Room (PACU)", "IBS", 3, 112, "RUANGAN"),

    # 4.4 Instalasi Perawatan Intensif
    ("4.4", "INTENSIF", "Instalasi Perawatan Intensif", "PELAKSANA-TEKNIS", 2, 120, "INSTALASI"),
    ("4.4.1", "ICU", "Unit ICU (Intensive Care Unit)", "INTENSIF", 3, 121, "RUANGAN"),
    ("4.4.2", "ICCU", "Unit ICCU (Intensive Coronary Care Unit)", "INTENSIF", 3, 122, "RUANGAN"),
    ("4.4.3", "NICU-PICU", "Unit NICU / PICU", "INTENSIF", 3, 123, "RUANGAN"),
    ("4.4.4", "HCU", "Unit HCU (High Dependency Unit)", "INTENSIF", 3, 124, "RUANGAN"),

    # 4.5 Instalasi Rawat Inap (IRIN) & Unit Kerja Bangsal
    ("4.5", "IRIN", "Instalasi Rawat Inap (IRIN) & Unit Kerja Bangsal", "PELAKSANA-TEKNIS", 2, 130, "INSTALASI"),
    ("4.5.1", "BANGSAL-VIP", "Bangsal Perawatan VIP / Super VIP", "IRIN", 3, 131, "RUANGAN"),
    ("4.5.2", "BANGSAL-DEWASA", "Bangsal Dewasa Non-Bedah", "IRIN", 3, 132, "RUANGAN"),
    ("4.5.2.1", "RUANG-PRIA", "Ruang Perawatan Pria", "BANGSAL-DEWASA", 4, 133, "RUANGAN"),
    ("4.5.2.2", "RUANG-WANITA", "Ruang Perawatan Wanita", "BANGSAL-DEWASA", 4, 134, "RUANGAN"),
    ("4.5.3", "BANGSAL-BEDAH", "Bangsal Perawatan Bedah", "IRIN", 3, 135, "RUANGAN"),
    ("4.5.3.1", "RUANG-BEDAH-PRIA-WANITA", "Ruang Bedah Pria & Wanita", "BANGSAL-BEDAH", 4, 136, "RUANGAN"),
    ("4.5.4", "BANGSAL-ANAK", "Bangsal Perawatan Anak", "IRIN", 3, 137, "RUANGAN"),
    ("4.5.4.1", "RUANG-ANAK-UMUM", "Ruang Perawatan Anak Umum", "BANGSAL-ANAK", 4, 138, "RUANGAN"),
    ("4.5.4.2", "ISOLASI-ANAK", "Unit Isolasi Anak", "BANGSAL-ANAK", 4, 139, "RUANGAN"),
    ("4.5.5", "BANGSAL-OBGYN", "Bangsal Kebidanan & Kandungan (Obgyn)", "IRIN", 3, 140, "RUANGAN"),
    ("4.5.5.1", "RUANG-BERSALIN-VK", "Ruang Bersalin (VK / Verlos Kamer)", "BANGSAL-OBGYN", 4, 141, "RUANGAN"),
    ("4.5.5.2", "RUANG-NIFAS", "Bangsal Perawatan Nifas", "BANGSAL-OBGYN", 4, 142, "RUANGAN"),
    ("4.5.5.3", "RUANG-PERINATOLOGI", "Ruang Perinatologi / Neonatus", "BANGSAL-OBGYN", 4, 143, "RUANGAN"),
    ("4.5.6", "ISOLASI-INFEKSIUS", "Bangsal Perawatan Isolasi (Infeksius)", "IRIN", 3, 144, "RUANGAN"),

    # 4.6 Unit Instalasi Penunjang
    ("4.6", "UNIT-PENUNJANG", "Unit Instalasi Penunjang", "PELAKSANA-TEKNIS", 2, 150, "INSTALASI"),

    # 4.6.1 Instalasi Laboratorium & Bank Darah
    ("4.6.1", "LAB-BDRS", "Instalasi Laboratorium & Bank Darah", "UNIT-PENUNJANG", 3, 151, "INSTALASI"),
    ("4.6.1.1", "PATOLOGI-MIKRO", "Unit Patologi Klinik, Patologi Anatomi & Mikrobiologi", "LAB-BDRS", 4, 152, "RUANGAN"),
    ("4.6.1.2", "BANK-DARAH-BDRS", "Unit Bank Darah RS (BDRS)", "LAB-BDRS", 4, 153, "RUANGAN"),

    # 4.6.2 Instalasi Radiologi & Diagnostic Imaging
    ("4.6.2", "RAD-IMAGING", "Instalasi Radiologi & Diagnostic Imaging", "UNIT-PENUNJANG", 3, 154, "INSTALASI"),
    ("4.6.2.1", "XRAY-MAMMO", "Unit X-Ray & Mammografi", "RAD-IMAGING", 4, 155, "RUANGAN"),
    ("4.6.2.2", "CT-MRI-USG", "Unit CT-Scan, MRI & USG", "RAD-IMAGING", 4, 156, "RUANGAN"),

    # 4.6.3 Instalasi Farmasi RS (IFRS) — Gunakan kode FARM agar kompatibel
    ("4.6.3", "FARM", "Instalasi Farmasi RS (IFRS)", "UNIT-PENUNJANG", 3, 157, "INSTALASI"),
    ("4.6.3.1", "DEPO-RAJAL", "Depo Farmasi Rawat Jalan", "FARM", 4, 158, "DEPO"),
    ("4.6.3.2", "DEPO-RANAP-IGD", "Depo Farmasi Rawat Inap & IGD", "FARM", 4, 159, "DEPO"),
    ("4.6.3.3", "DEPO-BEDAH-INTENSIF", "Depo Farmasi Bedah & Perawatan Intensif", "FARM", 4, 160, "DEPO"),
    ("4.6.3.4", "ASEPTIK-COMPOUNDING", "Unit Aseptik Compounding (Pencampuran Obat Steril)", "FARM", 4, 161, "DEPO"),

    # 4.6.4 Instalasi Gizi & Dietetik
    ("4.6.4", "GIZI-DIETETIK", "Instalasi Gizi & Dietetik", "UNIT-PENUNJANG", 3, 162, "INSTALASI"),
    ("4.6.4.1", "DAPUR-UTAMA", "Unit Dapur Utama / Penyelenggaraan Makanan", "GIZI-DIETETIK", 4, 163, "RUANGAN"),
    ("4.6.4.2", "ASUHAN-GIZI", "Unit Asuhan Gizi & Konsultasi Diet", "GIZI-DIETETIK", 4, 164, "RUANGAN"),

    # 4.6.5 Instalasi Rekam Medis & Pendaftaran
    ("4.6.5", "REKAM-MEDIS", "Instalasi Rekam Medis & Pendaftaran", "UNIT-PENUNJANG", 3, 165, "INSTALASI"),
    ("4.6.5.1", "PENDAFTARAN-ADMISSION", "Unit Pendaftaran & Admission", "REKAM-MEDIS", 4, 166, "RUANGAN"),
    ("4.6.5.2", "CODING-RME", "Unit Coding, Indexing, & Rekam Medis Elektronik", "REKAM-MEDIS", 4, 167, "RUANGAN"),

    # 4.6.6 Instalasi Pendukung Teknis & Sarana
    ("4.6.6", "PENDUKUNG-TEKNIS", "Instalasi Pendukung Teknis & Sarana", "UNIT-PENUNJANG", 3, 168, "INSTALASI"),
    ("4.6.6.1", "CSSD-LAUNDRY", "Instalasi Sterilisasi Sentral (CSSD) & Laundry", "PENDUKUNG-TEKNIS", 4, 169, "RUANGAN"),
    ("4.6.6.2", "JENAZAH-FORENSIK", "Instalasi Pemulasaraan Jenazah & Forensik", "PENDUKUNG-TEKNIS", 4, 170, "RUANGAN"),
    ("4.6.6.3", "IPSRS-SARANA", "Instalasi Pemeliharaan Sarana RS (IPSRS)", "PENDUKUNG-TEKNIS", 4, 171, "RUANGAN"),

    # 4.7 Kelompok Staf Medis (KSM)
    ("4.7", "KOMITE-MEDIK-KSM", "Kelompok Staf Medis (KSM)", "PELAKSANA-TEKNIS", 2, 180, "KOMITE"),
    ("4.7.1", "KSM-BEDAH", "KSM Bedah", "KOMITE-MEDIK-KSM", 3, 181, "KSM"),
    ("4.7.2", "KSM-PD", "KSM Penyakit Dalam", "KOMITE-MEDIK-KSM", 3, 182, "KSM"),
    ("4.7.3", "KSM-ANAK", "KSM Kesehatan Anak", "KOMITE-MEDIK-KSM", 3, 183, "KSM"),
    ("4.7.4", "KSM-OBGYN", "KSM Obstetri & Ginekologi", "KOMITE-MEDIK-KSM", 3, 184, "KSM"),
    ("4.7.5", "KSM-ANESTESI", "KSM Anestesi & Reanimasi", "KOMITE-MEDIK-KSM", 3, 185, "KSM"),
    ("4.7.6", "KSM-RADIOLOGI", "KSM Radiologi", "KOMITE-MEDIK-KSM", 3, 186, "KSM"),
    ("4.7.7", "KSM-LAINNYA", "KSM Penunjang & Spesialis Lainnya", "KOMITE-MEDIK-KSM", 3, 187, "KSM"),
]


class Command(BaseCommand):
    help = "Seed struktur organisasi RS Monsiskami Tipe B (Pola Urutan Arsitektur Menu Hirarkis)"

    def handle(self, *args, **options):
        self.stdout.write("Menyesuaikan struktur unit dengan RS Monsiskami...")

        # Simpan standar terkait farmasi lama agar tidak hilang
        farmasi_lama = UnitKerja.objects.filter(code='FARM').first()
        standar_farmasi = farmasi_lama.standar_terkait if farmasi_lama else {
            'TKRS': ['TKRS 9', 'TKRS 10', 'TKRS 11'],
            'PKPO': ['PKPO 1', 'PKPO 2', 'PKPO 3', 'PKPO 4', 'PKPO 5', 'PKPO 6 & 7'],
            'PPI':  ['PPI 5', 'PPI 7', 'PPI 7.1', 'PPI 7.2', 'PPI 8'],
            'MFK':  ['MFK 4', 'MFK 5', 'MFK 5.1', 'MFK 7', 'MFK 8', 'MFK 9'],
            'KPS':  ['KPS 1 & 3', 'KPS 4', 'KPS 5', 'KPS 8', 'KPS 10 & 12', 'KPS 11 & 14'],
        }

        created_count = 0
        updated_count = 0

        # Pass 1: Upsert unit tanpa parent
        for no_urut, code, name, parent_code, level, order, tipe_unit in STRUKTUR_MONSISKAMI:
            unit, created = UnitKerja.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'tipe_unit': tipe_unit if tipe_unit in dict(TIPE_UNIT_CHOICES) else 'LAINNYA',
                    'order': order,
                    'is_active': True,
                    'level': level,
                }
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        # Pass 2: Set parent relation
        for no_urut, code, name, parent_code, level, order, unit_type in STRUKTUR_MONSISKAMI:
            if parent_code:
                parent = UnitKerja.objects.filter(code=parent_code).first()
                if parent:
                    UnitKerja.objects.filter(code=code).update(parent=parent, level=parent.level + 1)
            else:
                UnitKerja.objects.filter(code=code).update(parent=None, level=1)

        # Restore standar_terkait Farmasi
        farmasi = UnitKerja.objects.filter(code='FARM').first()
        if farmasi:
            farmasi.standar_terkait = standar_farmasi
            farmasi.save(update_fields=['standar_terkait'])
            self.stdout.write(self.style.SUCCESS(f"Standar terkait Farmasi di-link: {len(standar_farmasi)} pokja"))

        # Pastikan user ka.farmasi terhubung ke Farmasi baru
        from django.contrib.auth.models import User
        user_farmasi = User.objects.filter(username='ka.farmasi').first()
        if user_farmasi and hasattr(user_farmasi, 'profile') and farmasi:
            user_farmasi.profile.unit_kerja = farmasi
            user_farmasi.profile.save(update_fields=['unit_kerja'])
            self.stdout.write(self.style.SUCCESS(f"User ka.farmasi di-link ke {farmasi.name}"))

        total = UnitKerja.objects.count()
        self.stdout.write(self.style.SUCCESS(
            f"Selesai! {created_count} dibuat, {updated_count} diperbarui. Total unit aktif: {total}"
        ))
