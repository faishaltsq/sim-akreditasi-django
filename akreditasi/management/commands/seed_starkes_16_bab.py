"""
Management command: seed_starkes_16_bab
Mengisi 16 Bab Standar Akreditasi Rumah Sakit (STARKES Edisi 2022 / Kepmenkes 1128/2022)
dengan total 321 Elemen Penilaian (EP) dan default QualityRecord untuk setiap EP.
"""
from django.core.management.base import BaseCommand
from akreditasi.models import Framework, Category, StandardItem, QualityRecord, UnitKerja


STARKES_DATA = [
    {
        'code': 'TKRS',
        'name': 'Tata Kelola Rumah Sakit',
        'kelompok': 'MANAJEMEN',
        'target_ep_count': 28,
        'order': 1,
        'unit_pengampu': 'Pemilik/Dewan Pengawas, Direksi, Komite Medis/Keperawatan/K3/PMKP, Seluruh Kepala Instalasi & Unit Kerja.',
        'default_unit_code': 'SEK-DIR',
        'sub_standards': [
            {'code': 'TKRS 1', 'title': 'Representasi Pemilik / Dewan Pengawas', 'ep_count': 3, 'desc_prefix': 'Representasi pemilik bertanggung jawab atas pengawasan dan akuntabilitas tata kelola RS'},
            {'code': 'TKRS 2', 'title': 'Akuntabilitas Direktur / Pimpinan RS', 'ep_count': 2, 'desc_prefix': 'Direktur bertanggung jawab memimpin operasional dan mematuhi peraturan perundangan'},
            {'code': 'TKRS 3.1', 'title': 'Kepemimpinan Operasional & Kepala Unit', 'ep_count': 2, 'desc_prefix': 'Pimpinan menetapkan struktur kepemimpinan dan alokasi sumber daya instalasi'},
            {'code': 'TKRS 3.2', 'title': 'Manajemen Risiko Fasilitas & Finansial', 'ep_count': 2, 'desc_prefix': 'Pimpinan mengelola risiko institusi, fasilitas, dan kontinuitas pelayanan'},
            {'code': 'TKRS 4', 'title': 'Pengelolaan Sumber Daya Manusia & Etika', 'ep_count': 2, 'desc_prefix': 'Pimpinan menetapkan tata kelola kepegawaian dan komite etik rumah sakit'},
            {'code': 'TKRS 5', 'title': 'Pengadaan Barang, Jasa, & Kontrak Klinis', 'ep_count': 2, 'desc_prefix': 'Pimpinan memastikan kontrak kerja sama dan vendor mematuhi mutu dan keselamatan'},
            {'code': 'TKRS 6', 'title': 'Manajemen Etika Rumah Sakit & Dilema Klinis', 'ep_count': 2, 'desc_prefix': 'Kerangka kerja pengelolaan etika kedokteran dan penyelesaian dilema etik di RS'},
            {'code': 'TKRS 7', 'title': 'Kepemimpinan untuk Budaya Keselamatan', 'ep_count': 2, 'desc_prefix': 'Pimpinan menciptakan budaya adil (just culture) dan keselamatan pasien terbuka'},
            {'code': 'TKRS 8', 'title': 'Tata Kelola Komite Medis & Kredensial', 'ep_count': 2, 'desc_prefix': 'Komite medis menjalankan tata kelola klinis dan evaluasi mutu profesi dokter'},
            {'code': 'TKRS 9', 'title': 'Tata Kelola Komite Keperawatan & Nakes Lain', 'ep_count': 3, 'desc_prefix': 'Tata kelola klinis keperawatan dan tenaga kesehatan lain untuk standar asuhan'},
            {'code': 'TKRS 10', 'title': 'Tata Kelola Mutu & Pelaporan ke Pemilik', 'ep_count': 3, 'desc_prefix': 'Laporan program mutu dan keselamatan pasien diserahkan berkala ke dewan pengawas'},
            {'code': 'TKRS 11', 'title': 'Kepatuhan Regulasi & Asuransi Kesehatan', 'ep_count': 3, 'desc_prefix': 'Pimpinan mematuhi regulasi perizinan, standar klaim, dan transparansi publik'},
        ]
    },
    {
        'code': 'KPS',
        'name': 'Kualifikasi & Pendidikan Staf',
        'kelompok': 'MANAJEMEN',
        'target_ep_count': 23,
        'order': 2,
        'unit_pengampu': 'Bagian SDM/Kepegawaian, Komite Medis, Komite Keperawatan, Komite Nakes Lain, Bagian Diklat.',
        'default_unit_code': 'BAG-SDM',
        'sub_standards': [
            {'code': 'KPS 1', 'title': 'Perencanaan Kebutuhan Staf', 'ep_count': 1, 'desc_prefix': 'Perencanaan pola ketenagaan RS dievaluasi berkala berdasarkan beban kerja'},
            {'code': 'KPS 2', 'title': 'Proses Rekrutmen & Penempatan Staf', 'ep_count': 2, 'desc_prefix': 'Penerimaan staf baru transparan sesuai kualifikasi dan kompetensi jabatan'},
            {'code': 'KPS 3', 'title': 'Orientasi Umum & Orientasi Khusus Staf', 'ep_count': 2, 'desc_prefix': 'Orientasi keselamatan pasien, PPI, dan unit kerja bagi seluruh pegawai baru'},
            {'code': 'KPS 4', 'title': 'Evaluasi Kinerja Staf & Uraian Tugas', 'ep_count': 2, 'desc_prefix': 'Penilaian kinerja tahunan dan uraian tugas tertulis untuk setiap pegawai'},
            {'code': 'KPS 5', 'title': 'Pendidikan Berkelanjutan & Pelatihan In-House', 'ep_count': 2, 'desc_prefix': 'Peningkatan kompetensi staf melalui diklat, seminar, dan sertifikasi profesi'},
            {'code': 'KPS 6', 'title': 'Pelatihan Bantuan Hidup Dasar (BHD)', 'ep_count': 2, 'desc_prefix': 'Pelatihan berkala BHD dan keselamatan darurat bagi staf klinis dan non-klinis'},
            {'code': 'KPS 7', 'title': 'Kesehatan dan Keselamatan Kerja Staf (K3RS)', 'ep_count': 2, 'desc_prefix': 'Pemeriksaan kesehatan pra-kerja, berkala, vaksinasi, dan penanganan pajanan'},
            {'code': 'KPS 8', 'title': 'Kredensial & Rekredensial Staf Medis', 'ep_count': 2, 'desc_prefix': 'Verifikasi primer ijazah, STR, SIP, dan penetapan Surat Penugasan Klinis (SPK/RKK)'},
            {'code': 'KPS 9', 'title': 'Monitoring Mutu Praktik Profesional Staf Medis (OPPE/FPPE)', 'ep_count': 2, 'desc_prefix': 'Evaluasi mutu praktik berkelanjutan oleh mitra bestari dan komite medis'},
            {'code': 'KPS 10', 'title': 'Kredensial & Rekredensial Staf Keperawatan', 'ep_count': 2, 'desc_prefix': 'Verifikasi STR, SIP, dan SPK/RKK perawat dan bidan sesuai jenjang karir klinis'},
            {'code': 'KPS 11', 'title': 'Evaluasi Kinerja Praktik Keperawatan', 'ep_count': 2, 'desc_prefix': 'Evaluasi mutu asuhan keperawatan berkala oleh komite keperawatan'},
            {'code': 'KPS 12', 'title': 'Kredensial Tenaga Kesehatan Lainnya', 'ep_count': 2, 'desc_prefix': 'Kredensial apoteker, analis lab, radiografer, nutrisionis, dan fisioterapis'},
        ]
    },
    {
        'code': 'MFK',
        'name': 'Manajemen Fasilitas & Keselamatan',
        'kelompok': 'MANAJEMEN',
        'target_ep_count': 21,
        'order': 3,
        'unit_pengampu': 'Bagian K3RS, IPSRS (Sanitasi & Pemeliharaan Sarpras), Security, Terlibat seluruh Unit/Instalasi.',
        'default_unit_code': 'SUB-IPSRS',
        'sub_standards': [
            {'code': 'MFK 1', 'title': 'Kepemimpinan & Program Keselamatan Fasilitas', 'ep_count': 2, 'desc_prefix': 'Pimpinan mematuhi perizinan gedung, sarpras, dan membentuk tim K3RS'},
            {'code': 'MFK 2', 'title': 'Manajemen Keselamatan dan Keamanan Lingkungan', 'ep_count': 2, 'desc_prefix': 'Identifikasi risiko fisik, CCTV, kartu akses, dan proteksi bahaya gedung'},
            {'code': 'MFK 3', 'title': 'Pengelolaan Bahan Berbahaya dan Beracun (B3)', 'ep_count': 2, 'desc_prefix': 'Inventaris B3, MSDS, spill kit, penyimpanan standar, dan pengolahan limbah B3'},
            {'code': 'MFK 4', 'title': 'Proteksi Kebakaran dan Keadaan Darurat', 'ep_count': 2, 'desc_prefix': 'Sistem proteksi pasif/aktif, APAR, hidran, smoke detector, dan simulasi evakuasi'},
            {'code': 'MFK 5', 'title': 'Penanganan Kedaruratan & Bencana (Disaster Plan)', 'ep_count': 2, 'desc_prefix': 'Rencana respon bencana internal/eksternal, HVA, dan simulasi penanggulangan bencana'},
            {'code': 'MFK 5.1', 'title': 'Kesiapsiagaan Dekontaminasi Bahan Kimia & Biologis', 'ep_count': 2, 'desc_prefix': 'Prosedur dekontaminasi korban kontaminasi zat berbahaya dan isolasi wabah'},
            {'code': 'MFK 6', 'title': 'Pengelolaan Peralatan Medis', 'ep_count': 2, 'desc_prefix': 'Inventaris, kalibrasi berkala, uji fungsi, pemeliharaan preventif alat medis RS'},
            {'code': 'MFK 7', 'title': 'Sistem Utilitas: Listrik, Air, & Gas Medis', 'ep_count': 2, 'desc_prefix': 'Penyediaan cadangan genset, air bersih darurat, dan pemantauan gas medis 24 jam'},
            {'code': 'MFK 8', 'title': 'Monitoring Pengujian Berkala Sistem Utilitas', 'ep_count': 2, 'desc_prefix': 'Uji beban genset berkala, inspeksi pipa air, dan verifikasi kualitas udara bersih'},
            {'code': 'MFK 9', 'title': 'Edukasi & Pelatihan Keselamatan Staf', 'ep_count': 2, 'desc_prefix': 'Pelatihan berkala APAR, BHD, dan penanganan tumpahan limbah B3 bagi pegawai'},
            {'code': 'MFK 10', 'title': 'Evaluasi Tahunan & Pengendalian Konstruksi (PCRA)', 'ep_count': 1, 'desc_prefix': 'Analisis dampak renovasi/konstruksi terhadap mutu udara, infeksi, dan kebisingan'},
        ]
    },
    {
        'code': 'PMKP',
        'name': 'Peningkatan Mutu & Keselamatan Pasien',
        'kelompok': 'MANAJEMEN',
        'target_ep_count': 18,
        'order': 4,
        'unit_pengampu': 'Komite/Tim PMKP, Komite Mutu, Sub-Komite Keselamatan Pasien, Seluruh Instalasi Pelayanan & Penunjang.',
        'default_unit_code': 'KMKP',
        'sub_standards': [
            {'code': 'PMKP 1', 'title': 'Pengelolaan Kegiatan PMKP', 'ep_count': 1, 'desc_prefix': 'Komite mutu RS mengelola dan memfasilitasi program peningkatan mutu RS'},
            {'code': 'PMKP 2', 'title': 'Pemilihan dan Pengumpulan Indikator Mutu', 'ep_count': 2, 'desc_prefix': 'Pemilihan indikator mutu nasional (INM), mutu prioritas RS, dan unit kerja'},
            {'code': 'PMKP 3', 'title': 'Validasi dan Analisis Data Mutu', 'ep_count': 2, 'desc_prefix': 'Validasi data indikator baru atau perubahan metodologi sebelum dipublikasikan'},
            {'code': 'PMKP 4', 'title': 'Pencapaian dan Mempertahankan Perbaikan Mutu', 'ep_count': 2, 'desc_prefix': 'Penerapan siklus PDCA untuk mempertahankan perbaikan indikator mutu pelayanan'},
            {'code': 'PMKP 5', 'title': 'Evaluasi Standar Pelayanan Kedokteran (Klinis)', 'ep_count': 2, 'desc_prefix': 'Audit klinis penerapan panduan praktik klinis (PPK) dan alur klinis (clinical pathway)'},
            {'code': 'PMKP 6', 'title': 'Sistem Pelaporan Insiden Keselamatan Pasien (IKP)', 'ep_count': 2, 'desc_prefix': 'Pelaporan insiden KTD, KNC, KTC, KPC internal RS dan eksternal ke KNKP'},
            {'code': 'PMKP 7', 'title': 'Investigasi Sederhana & Root Cause Analysis (RCA)', 'ep_count': 2, 'desc_prefix': 'Pelaksanaan investigasi mendalam RCA untuk grading merah/kuning dan kejadian sentinel'},
            {'code': 'PMKP 8', 'title': 'Penerapan Manajemen Risiko Klinis Terintegrasi', 'ep_count': 2, 'desc_prefix': 'Penyusunan daftar register risiko rumah sakit dan Failure Mode and Effects Analysis (FMEA)'},
            {'code': 'PMKP 9', 'title': 'Penyampaian Informasi Mutu kepada Staf & Publik', 'ep_count': 2, 'desc_prefix': 'Desiminasi capaian mutu dan keselamatan pasien secara transparan kepada publik'},
            {'code': 'PMKP 10', 'title': 'Pengukuran Budaya Keselamatan Pasien', 'ep_count': 1, 'desc_prefix': 'Survei tahunan budaya keselamatan pasien dan tindak lanjut perbaikan iklim kerja'},
        ]
    },
    {
        'code': 'MRMIK',
        'name': 'Manajemen Informasi & Rekam Medis',
        'kelompok': 'MANAJEMEN',
        'target_ep_count': 14,
        'order': 5,
        'unit_pengampu': 'Unit Rekam Medis, SIMRS/IT, Bagian Humas, Seluruh Depo/Unit Pelayanan Klinis.',
        'default_unit_code': 'REKAM-MEDIS',
        'sub_standards': [
            {'code': 'MRMIK 1', 'title': 'Pengelolaan Sistem Informasi Manajemen RS (SIMRS)', 'ep_count': 2, 'desc_prefix': 'Penyelenggaraan SIMRS terintegrasi, pemeliharaan server, dan perlindungan privasi'},
            {'code': 'MRMIK 2', 'title': 'Kerahasiaan, Privasi, & Keamanan Data Pasien', 'ep_count': 2, 'desc_prefix': 'Kebijakan hak akses, otentikasi user, enkripsi data medis, dan pelepasan informasi'},
            {'code': 'MRMIK 3', 'title': 'Proses Penyelenggaraan Rekam Medis Elektronik (RME)', 'ep_count': 2, 'desc_prefix': 'Pemberian satu nomor RM tunggal, penulisan rekam medis tepat waktu dan lengkap'},
            {'code': 'MRMIK 4', 'title': 'Kelengkapan dan Peninjauan Rekam Medis (Review RM)', 'ep_count': 2, 'desc_prefix': 'Review berkala kelengkapan resume medis, informed consent, dan catatan terintegrasi'},
            {'code': 'MRMIK 5', 'title': 'Retensi, Pemusnahan, dan Perlindungan Berkas RM', 'ep_count': 2, 'desc_prefix': 'Jadwal retensi berkas inaktif, digitalisasi berkas bernilai guna, dan pemusnahan resmi'},
            {'code': 'MRMIK 6', 'title': 'Simbol, Singkatan Terstandar, & Kode Diagnosis ICD', 'ep_count': 2, 'desc_prefix': 'Penetapan daftar singkatan baku, singkatan dilarang, serta koding ICD-10 dan ICD-9CM'},
            {'code': 'MRMIK 7', 'title': 'Kesiapsiagaan Bencana Teknologi & Backup Data', 'ep_count': 2, 'desc_prefix': 'Disaster recovery plan SIMRS, uji coba restore backup database secara periodik'},
        ]
    },
    {
        'code': 'PPI',
        'name': 'Pencegahan & Pengendalian Infeksi',
        'kelompok': 'MANAJEMEN',
        'target_ep_count': 18,
        'order': 6,
        'unit_pengampu': 'Komite/Tim PPI, IPCN, Unit Sanitasi, Central Sterile Supply Department (CSSD), Laundry, Seluruh Unit Pelayanan.',
        'default_unit_code': 'KOMITE-PPI',
        'sub_standards': [
            {'code': 'PPI 1', 'title': 'Kepemimpinan & Struktur Komite PPI', 'ep_count': 2, 'desc_prefix': 'Penetapan IPCN purna waktu, struktur komite PPI, dan alokasi anggaran PPI'},
            {'code': 'PPI 2', 'title': 'Penerapan Kewaspadaan Standar & Isolasi', 'ep_count': 2, 'desc_prefix': 'Penerapan 11 kewaspadaan standar: kebersihan tangan, APD, dekontaminasi, etika batuk'},
            {'code': 'PPI 3', 'title': 'Surveilans Infeksi Daerah Operasi, Plebitis, & ISK', 'ep_count': 2, 'desc_prefix': 'Pencatatan harian HAIs (IDO, VAP, ISK, PLEBITIS) dan audit kepatuhan cuci tangan'},
            {'code': 'PPI 4', 'title': 'Pengelolaan Linen dan Laundry Bersih/Kotor', 'ep_count': 2, 'desc_prefix': 'Pemisahan linen infeksius, pencucian standar suhu deterjen, dan distribusi higienis'},
            {'code': 'PPI 5', 'title': 'Sterilisasi Sentral (CSSD) & DTT Alat Medis', 'ep_count': 2, 'desc_prefix': 'Alur satu arah CSSD: dekontaminasi, packing, sterilisasi autoklaf, dan uji indikator'},
            {'code': 'PPI 6', 'title': 'Pengendalian Infeksi pada Pelayanan Makanan (Gizi)', 'ep_count': 2, 'desc_prefix': 'Higiene sanitasi dapur gizi, uji swab berkala alat makan, dan suhu saji makanan'},
            {'code': 'PPI 7', 'title': 'Pencegahan Infeksi Prosedur Invasif (Bundles HAIs)', 'ep_count': 2, 'desc_prefix': 'Penerapan bundle pencegahan IAD, ISK, IDO, dan VAP pada seluruh ruang perawatan'},
            {'code': 'PPI 7.1', 'title': 'Pengendalian Infeksi Kamar Jenazah & Spesimen', 'ep_count': 2, 'desc_prefix': 'Dekontaminasi meja autopsi, transportasi aman jenazah infeksius, dan APD petugas'},
            {'code': 'PPI 8', 'title': 'Pendidikan PPI untuk Staf, Pasien, & Pengunjung', 'ep_count': 2, 'desc_prefix': 'Sosialisasi etika batuk, 6 langkah cuci tangan, dan pemakaian masker di lingkungan RS'},
        ]
    },
    {
        'code': 'ARK',
        'name': 'Akses dan Kontinuitas Pelayanan',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 23,
        'order': 7,
        'unit_pengampu': 'Admisi/Pendaftaran, IGD, Poliklinik Rawat Jalan, Rawat Inap, ICU/HCU, Unit Ambulans, Case Manager (MPP).',
        'default_unit_code': 'ADMISI',
        'sub_standards': [
            {'code': 'ARK 1', 'title': 'Skrining & Triage Pasien di IGD & Poliklinik', 'ep_count': 3, 'desc_prefix': 'Proses triage berbasis bukti di IGD dan skrining visual kebutuhan khusus di poliklinik'},
            {'code': 'ARK 2', 'title': 'Penerimaan Pasien Masuk Rawat Inap (Admisi)', 'ep_count': 3, 'desc_prefix': 'Penjelasan tarif, hak kelas rawat, persetujuan umum (general consent), dan ketersediaan TT'},
            {'code': 'ARK 3', 'title': 'Pelayanan Berkesinambungan & Case Manager (MPP)', 'ep_count': 3, 'desc_prefix': 'Manajer Pelayanan Pasien mengoordinasikan kontinuitas asuhan dan utilisasi layanan'},
            {'code': 'ARK 4', 'title': 'Transfer Pasien Internal Antar Unit RS', 'ep_count': 3, 'desc_prefix': 'Kriteria transfer aman, pemantauan klinis selama transfer, dan komunikasi SBAR'},
            {'code': 'ARK 5', 'title': 'Perencanaan Pemulangan Pasien (Discharge Planning)', 'ep_count': 3, 'desc_prefix': 'Discharge planning dimulai sejak admisi untuk pasien risiko tinggi atau perawatan lanjut'},
            {'code': 'ARK 6', 'title': 'Rujukan Keluar dan Transportasi Pasien (Ambulans)', 'ep_count': 4, 'desc_prefix': 'Kriteria rujukan keluar, perjanjian RS rujukan, pendampingan medis ambulans'},
            {'code': 'ARK 7', 'title': 'Pemulangan Pasien, Penolakan Rawat, & APS', 'ep_count': 4, 'desc_prefix': 'Prosedur pasien pulang atas permintaan sendiri (APS), edukasi risiko, dan tindak lanjut'},
        ]
    },
    {
        'code': 'HPK',
        'name': 'Hak Pasien dan Keluarga',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 11,
        'order': 8,
        'unit_pengampu': 'Customer Service/Humas, Admisi, PPA (Dokter, Perawat, Apoteker), Kerohanian, Seluruh Unit Rawat Inap & Jalan.',
        'default_unit_code': 'HUMAS-CS',
        'sub_standards': [
            {'code': 'HPK 1', 'title': 'Penghormatan Hak Pribadi & Kebutuhan Privasi', 'ep_count': 2, 'desc_prefix': 'Penyampaian hak pasien, tirai privasi pemeriksaan klinis, dan proteksi dari kekerasan'},
            {'code': 'HPK 2', 'title': 'Pengelolaan Nilai Budaya, Spiritual, & Hak Rohani', 'ep_count': 2, 'desc_prefix': 'Pelayanan bimbingan rohani sesuai keyakinan pasien dan penghormatan nilai agama'},
            {'code': 'HPK 3', 'title': 'Persetujuan Tindakan Medis (Informed Consent)', 'ep_count': 2, 'desc_prefix': 'Penjelasan risiko medis oleh DPJP, alternatif tindakan, dan pengisian lembar informed consent'},
            {'code': 'HPK 4', 'title': 'Pengelolaan Komplain, Keluhan, dan Dilema Pasien', 'ep_count': 2, 'desc_prefix': 'Penanganan keluhan cepat melalui kotak saran, hotline CS, dan penelusuran solusi adil'},
            {'code': 'HPK 5', 'title': 'Pelayanan Pasien Tahap Akhir Kehidupan (End of Life)', 'ep_count': 3, 'desc_prefix': 'Perawatan paliatif penuh martabat, manajemen nyeri, dan dukungan psikologis keluarga'},
        ]
    },
    {
        'code': 'PP',
        'name': 'Pengasesan Pasien',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 16,
        'order': 9,
        'unit_pengampu': 'DPJP, Perawat, Nutrisionis/Dietisien, Apoteker (PPA), Laboratorium, Radiologi.',
        'default_unit_code': 'LAB-BDRS',
        'sub_standards': [
            {'code': 'PP 1', 'title': 'Asesmen Awal Medis & Keperawatan Terpadu', 'ep_count': 2, 'desc_prefix': 'Asesmen awal medis dan keperawatan selesai dalam batas waktu regulasi sejak pasien masuk'},
            {'code': 'PP 2', 'title': 'Asesmen Nyeri Terstandarisasi', 'ep_count': 2, 'desc_prefix': 'Skrining nyeri dengan NRS/VAS/BPS, tatalaksana analgesia, dan asesmen ulang berkala'},
            {'code': 'PP 3', 'title': 'Skrining Status Gizi & Asesmen Nutrisi Lanjut', 'ep_count': 2, 'desc_prefix': 'Skrining gizi MST/SGA, rujukan dietisien, dan penetapan preskripsi diet pasien'},
            {'code': 'PP 4', 'title': 'Asesmen Risiko Jatuh Dewasa, Pediatrik, & Geriatri', 'ep_count': 2, 'desc_prefix': 'Penilaian Morse Fall Scale / Humpty Dumpty, pasang gelang kuning, dan intervensi jatuh'},
            {'code': 'PP 5', 'title': 'Pelayanan Laboratorium Patologi & Transfusi Darah', 'ep_count': 2, 'desc_prefix': 'Pelayanan lab 24 jam, pemantapan mutu internal/eksternal (PMI/PME), dan uji silang BDRS'},
            {'code': 'PP 6', 'title': 'Pelaporan Nilai Kritis Laboratorium (Critical Value)', 'ep_count': 2, 'desc_prefix': 'Pelaporan nilai kritis segera <30 menit kepada DPJP dengan teknik read-back (TBaK)'},
            {'code': 'PP 7', 'title': 'Pelayanan Radiologi Diagnostik & Imejing', 'ep_count': 2, 'desc_prefix': 'Proteksi radiasi TLD, pemeliharaan alat sinar-X, dan ekspertise dokter spesialis radiologi'},
            {'code': 'PP 8', 'title': 'Penyusunan Rencana Asuhan Terintegrasi (CPPT)', 'ep_count': 2, 'desc_prefix': 'Catatan Perkembangan Pasien Terintegrasi format SOAP oleh seluruh Profesional Pemberi Asuhan'},
        ]
    },
    {
        'code': 'PAP',
        'name': 'Pelayanan dan Asuhan Pasien',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 19,
        'order': 10,
        'unit_pengampu': 'Rawat Inap, ICU/ICCU/HCU, Kamar Bedah (OK), IGD, Unit Dialisis, Chemotherapy, Rehabilitasi Medik.',
        'default_unit_code': 'IRIN',
        'sub_standards': [
            {'code': 'PAP 1', 'title': 'Pemberian Pelayanan Pasien Seragam & Terstandar', 'ep_count': 2, 'desc_prefix': 'Standar mutu asuhan sama di seluruh ruang rawat tanpa diskriminasi kelas atau biaya'},
            {'code': 'PAP 2', 'title': 'Peresepan & Pelaksanaan Instruksi Klinis Terpadu', 'ep_count': 2, 'desc_prefix': 'Instruksi pengobatan ditulis jelas di CPPT oleh dokter berwenang dengan batas waktu'},
            {'code': 'PAP 3', 'title': 'Pelayanan Pasien Risiko Tinggi & Gawat Darurat', 'ep_count': 2, 'desc_prefix': 'Kriteria penanganan henti jantung, syok, koma, sepsis, dan aktivasi Code Blue cepat'},
            {'code': 'PAP 4', 'title': 'Pelayanan Pasien Kritis di Ruang Intensif (ICU/ICCU)', 'ep_count': 2, 'desc_prefix': 'Kriteria masuk keluar ICU terstandar, rasio perawat kritis, dan monitoring invasif'},
            {'code': 'PAP 5', 'title': 'Pelayanan Darah & Transfusi Aman', 'ep_count': 2, 'desc_prefix': 'Pemberian darah sesuai identifikasi ganda, observasi tanda reaksi transfusi, dan pelaporan'},
            {'code': 'PAP 6', 'title': 'Pelayanan Pasien Dialisis & Kemoterapi', 'ep_count': 2, 'desc_prefix': 'Kepatuhan protokol hemodialisis, reuse dialiser, dan penanganan spill kit sitotoksik'},
            {'code': 'PAP 7', 'title': 'Pelayanan Pasien Imunokompromais & Penyakit Menular', 'ep_count': 2, 'desc_prefix': 'Penempatan pasien di ruang isolasi bertekanan negatif atau pelindung imunodefisiensi'},
            {'code': 'PAP 8', 'title': 'Penerapan Sistem Peringatan Dini Klinis (EWS/PEWS/MEOWS)', 'ep_count': 2, 'desc_prefix': 'Monitoring skor tanda vital berkala, deteksi dini perburukan, dan aktivasi Code Blue'},
            {'code': 'PAP 9', 'title': 'Pelayanan Pengikatan Fisik (Restraint) & Pasien Rentan', 'ep_count': 3, 'desc_prefix': 'Kriteria dan persetujuan tindakan restrain, observasi sirkulasi berkala tiap 2 jam'},
        ]
    },
    {
        'code': 'PAB',
        'name': 'Pelayanan Anestesi dan Bedah',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 20,
        'order': 11,
        'unit_pengampu': 'Kamar Bedah (OK), Depo Farmasi OK, Dokter Anestesi, Dokter Bedah, Penata Anestesi, Recovery Room (PACU).',
        'default_unit_code': 'IBS',
        'sub_standards': [
            {'code': 'PAB 1', 'title': 'Tata Kelola dan Tanggung Jawab Pelayanan Bedah Anestesi', 'ep_count': 2, 'desc_prefix': 'Penetapan dokter spesialis anestesi purna waktu dan SPO pelayanan seragam di RS'},
            {'code': 'PAB 2', 'title': 'Pelayanan Sedasi Ringan, Moderat, & Dalam', 'ep_count': 2, 'desc_prefix': 'Kompetensi dokter pelaku sedasi, monitoring saturasi oksigen, dan kesiapan antidot'},
            {'code': 'PAB 3', 'title': 'Asesmen Pra-Anestesi dan Pra-Induksi Terstandar', 'ep_count': 2, 'desc_prefix': 'Evaluasi pra-anestesi lengkap sebelum operasi dan pra-induksi tepat sebelum anestesi'},
            {'code': 'PAB 4', 'title': 'Pemberian Edukasi Anestesi & Informed Consent Bedah', 'ep_count': 2, 'desc_prefix': 'Informed consent pembedahan dan anestesi terpisah dengan penjelasan risiko komprehensif'},
            {'code': 'PAB 5', 'title': 'Monitoring Status Fisiologis Selama Anestesi', 'ep_count': 2, 'desc_prefix': 'Pencatatan tanda vital per 5 menit pada status anestesi selama prosedur pembedahan'},
            {'code': 'PAB 6', 'title': 'Pelayanan Pemulihan Pasca-Anestesi di Ruang Pulih (PACU)', 'ep_count': 2, 'desc_prefix': 'Kriteria pindah dari PACU menggunakan skor Aldrete, Bromage, atau Steward'},
            {'code': 'PAB 7', 'title': 'Asesmen Pra-Bedah & Rencana Tindakan Operasi', 'ep_count': 2, 'desc_prefix': 'Pengkajian kondisi medis pra-bedah, penandaan lokasi operasi (site marking)'},
            {'code': 'PAB 8', 'title': 'Penerapan Surgical Safety Checklist (SSC WHO)', 'ep_count': 2, 'desc_prefix': 'Verifikasi Sign In, Time Out, dan Sign Out secara disiplin oleh tim kamar bedah'},
            {'code': 'PAB 9', 'title': 'Penulisan Laporan Operasi & Instruksi Pasca-Bedah', 'ep_count': 2, 'desc_prefix': 'Laporan operasi lengkap selesai sebelum pasien dipindahkan dari ruang pemulihan'},
            {'code': 'PAB 10', 'title': 'Pengelolaan Implan Bedah & Sterilitas Kamar Operasi', 'ep_count': 2, 'desc_prefix': 'Traceability nomor batch implan dan audit tekanan positif tata udara kamar operasi'},
        ]
    },
    {
        'code': 'PKPO',
        'name': 'Pelayanan Kefarmasian & Penggunaan Obat',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 20,
        'order': 12,
        'unit_pengampu': 'Instalasi Farmasi (Gudang, Depo Rawat Jalan/Inap/OK), KFT, Komite Medis, Keperawatan.',
        'default_unit_code': 'FARM',
        'sub_standards': [
            {'code': 'PKPO 1', 'title': 'Tata Kelola Pelayanan Kefarmasian & Regulasi Farmasi', 'ep_count': 2, 'desc_prefix': 'Struktur instalasi farmasi dipimpin apoteker ber-STRA/SIPA dan komite farmasi terapi'},
            {'code': 'PKPO 2', 'title': 'Formularium Rumah Sakit & Pengadaan Obat', 'ep_count': 2, 'desc_prefix': 'Penyusunan formularium RS tahunan, kepatuhan peresepan, dan evaluasi berkala'},
            {'code': 'PKPO 3', 'title': 'Penyimpanan Obat, Vaksin, & Rantai Dingin (Cold Chain)', 'ep_count': 2, 'desc_prefix': 'Penyimpanan suhu terkontrol, kartu pantau suhu, dan alarm kulkas vaksin standar'},
            {'code': 'PKPO 3.1', 'title': 'Penyimpanan Obat High Alert & Elektrolit Konsentrat', 'ep_count': 2, 'desc_prefix': 'Pemberian label High Alert merah, stiker LASA/NORUM, dan pembatasan elektrolit pekat'},
            {'code': 'PKPO 4', 'title': 'Peresepan, Ketepatan Penulisan, & Rekonsiliasi Obat', 'ep_count': 2, 'desc_prefix': 'Kelengkapan resep dokter, skrining klinis, dan rekonsiliasi obat saat admisi/pindah/pulang'},
            {'code': 'PKPO 5', 'title': 'Penyiapan, Peracikan, & Dispensing Obat Higienis', 'ep_count': 2, 'desc_prefix': 'Fasilitas laminar air flow (LAF) aseptik dispensing, etiket obat lengkap 5 benar'},
            {'code': 'PKPO 6', 'title': 'Pemberian Obat kepada Pasien & Edukasi Farmasi', 'ep_count': 2, 'desc_prefix': 'Verifikasi identitas pasien sebelum obat diberikan dan pemberian konseling informasi obat'},
            {'code': 'PKPO 7', 'title': 'Pemantauan Terapi Obat & Efek Samping Obat (MESO)', 'ep_count': 2, 'desc_prefix': 'Pelaporan efek samping obat ke BPOM dan farmakovigilans oleh apoteker klinis'},
            {'code': 'PKPO 8', 'title': 'Sistem Pelaporan Kesalahan Obat (Medication Error)', 'ep_count': 2, 'desc_prefix': 'Pelaporan KTD, KNC, KTC peresepan, dispensing, dan administrasi obat ke komite mutu'},
            {'code': 'PKPO 9', 'title': 'Pengelolaan Obat Emergensi & Penguncian Standar', 'ep_count': 2, 'desc_prefix': 'Troli emergensi terkunci segel bernomor, inspeksi kedaluwarsa berkala tiap bulan'},
        ]
    },
    {
        'code': 'KE',
        'name': 'Komunikasi dan Edukasi',
        'kelompok': 'PELAYANAN',
        'target_ep_count': 7,
        'order': 13,
        'unit_pengampu': 'Tim PKRS (Promosi Kesehatan RS), Humas, Seluruh PPA di Rawat Jalan, Rawat Inap, dan Penunjang.',
        'default_unit_code': 'HUMAS-CS',
        'sub_standards': [
            {'code': 'KE 1', 'title': 'Pengorganisasian Promosi Kesehatan RS (PKRS)', 'ep_count': 2, 'desc_prefix': 'Program kerja tim PKRS, penyediaan media edukasi leaflet, banner, dan video informasi'},
            {'code': 'KE 2', 'title': 'Pemberian Edukasi Terintegrasi kepada Pasien & Keluarga', 'ep_count': 2, 'desc_prefix': 'Pengkajian hambatan edukasi (bahasa, fisik, kognitif) dan lembar edukasi terintegrasi'},
            {'code': 'KE 3', 'title': 'Materi Edukasi Penggunaan Obat, Nutrisi, & Pemulangan', 'ep_count': 3, 'desc_prefix': 'Edukasi cara minum obat, diet penyakit kronis, teknik rehabilitasi, dan rujukan lanjut'},
        ]
    },
    {
        'code': 'SKP',
        'name': 'Sasaran Keselamatan Pasien',
        'kelompok': 'SASARAN_KP',
        'target_ep_count': 10,
        'order': 14,
        'unit_pengampu': 'Tim Keselamatan Pasien RS (TKPRS), Seluruh PPA (Dokter, Perawat, Bidan, Apoteker, Analis, Radiografer).',
        'default_unit_code': 'KMKP',
        'sub_standards': [
            {'code': 'SKP 1', 'title': 'Mengidentifikasi Pasien dengan Benar (SKP 1)', 'ep_count': 2, 'desc_prefix': 'Identifikasi minimal 2 identitas (Nama & Tanggal Lahir) sebelum obat, darah, tindakan'},
            {'code': 'SKP 2', 'title': 'Meningkatkan Komunikasi yang Efektif (SKP 2)', 'ep_count': 2, 'desc_prefix': 'Penerapan instruksi verbal Tulis-Baca-Konfirmasi (TBaK) dan komunikasi SBAR'},
            {'code': 'SKP 3', 'title': 'Meningkatkan Keamanan Obat Kewaspadaan Tinggi (SKP 3)', 'ep_count': 2, 'desc_prefix': 'Pemberian stiker High Alert, double check perawat sebelum injeksi obat pekat'},
            {'code': 'SKP 4', 'title': 'Memastikan Lokasi Pembedahan yang Benar (SKP 4)', 'ep_count': 1, 'desc_prefix': 'Penandaan lokasi sayatan operasi (site marking) oleh DPJP bedah bersama pasien'},
            {'code': 'SKP 5', 'title': 'Mengurangi Risiko Infeksi Terkait Pelayanan (SKP 5)', 'ep_count': 1, 'desc_prefix': 'Kepatuhan 6 langkah cuci tangan WHO pada 5 momen oleh seluruh tenaga kesehatan'},
            {'code': 'SKP 6', 'title': 'Mengurangi Risiko Pasien Jatuh dari Cedera (SKP 6)', 'ep_count': 2, 'desc_prefix': 'Pasang gelang risiko jatuh kuning, segitiga risiko jatuh di bed, dan pengaman tempat tidur'},
        ]
    },
    {
        'code': 'PROGNAS',
        'name': 'Program Nasional (PONEK, TB, HIV, Stunting, PPRA)',
        'kelompok': 'PROGNAS',
        'target_ep_count': 26,
        'order': 15,
        'unit_pengampu': 'Tim PONEK, Tim TB-DOTS, Tim HIV/AIDS, Tim PPRA, Tim Stunting/Gizi, VK/Kamar Bersalin, Poliklinik Terpadu.',
        'default_unit_code': 'KMKP',
        'sub_standards': [
            {'code': 'PROGNAS 1', 'title': 'Peningkatan Kesehatan Ibu dan Bayi (PONEK 24 Jam)', 'ep_count': 5, 'desc_prefix': 'Kesiapan tim PONEK 24 jam di IGD dan Kamar Bersalin, rujukan maternal neonatal cepat'},
            {'code': 'PROGNAS 2', 'title': 'Penurunan Angka Kesakitan Tuberkulosis (TB-DOTS)', 'ep_count': 5, 'desc_prefix': 'Pelayanan klinik TB-DOTS, pemeriksaan TCM, pencatatan SITB, dan pencegahan penularan'},
            {'code': 'PROGNAS 3', 'title': 'Pengendalian Infeksi HIV/AIDS (VCT/ART)', 'ep_count': 5, 'desc_prefix': 'Pelayanan konseling testing HIV sukarela, ketersediaan ARV, dan rujukan ODHA'},
            {'code': 'PROGNAS 4', 'title': 'Penurunan Prevalensi Stunting dan Wasting', 'ep_count': 5, 'desc_prefix': 'Klinik laktasi, edukasi ASI eksklusif, tata laksana gizi buruk anak rawat inap'},
            {'code': 'PROGNAS 5', 'title': 'Pengendalian Resistensi Antimikroba (PPRA)', 'ep_count': 6, 'desc_prefix': 'Komite PPRA, panduan penggunaan antibiotik profilaksis dan terapi definitif terstandar'},
        ]
    },
    {
        'code': 'IPKP',
        'name': 'Integrasi Pendidikan Kesehatan dalam Pelayanan',
        'kelompok': 'PENDIDIKAN',
        'target_ep_count': 6,
        'order': 16,
        'unit_pengampu': 'Komite Koordinasi Pendidikan (Korkom/Kordik), Bagian Diklat, Unit Pelayanan yang Menjadi Lahan Praktik/Pendidikan.',
        'default_unit_code': 'BAG-DIKLIT',
        'sub_standards': [
            {'code': 'IPKP 1', 'title': 'Penetapan RS Pendidikan & Kerja Sama Institusi Pendidikan', 'ep_count': 2, 'desc_prefix': 'SK penetapan RS Pendidikan, perjanjian kerja sama (PKS) dengan fakultas kedokteran/nakes'},
            {'code': 'IPKP 2', 'title': 'Struktur & Pengorganisasian Komite Kordik RS', 'ep_count': 2, 'desc_prefix': 'Pembentukan tim sekretariat Kordik, buku panduan peserta didik klinis, rasio pendidik'},
            {'code': 'IPKP 3', 'title': 'Supervisi Klinis & Evaluasi Peserta Didik', 'ep_count': 2, 'desc_prefix': 'Tingkat supervisi klinis residen/koas/mahasiswa dan pemantauan keselamatan pasien asuhan'},
        ]
    },
]


class Command(BaseCommand):
    help = 'Seed 16 Bab Standar STARKES Edisi 2022 lengkap dengan 321 Elemen Penilaian (EP)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Memulai seeding 16 Bab Standar STARKES..."))

        # Pastikan Framework ada
        framework = Framework.objects.first()
        if not framework:
            framework = Framework.objects.create(
                name='STARKES Edisi 2022 / Kemenkes RI (PDCA)',
                version='2022',
                cycle_type='PDCA',
            )

        # Fallback unit default
        default_fallback_unit = UnitKerja.objects.first()

        total_cat_created = 0
        total_cat_updated = 0
        total_ep_created = 0
        total_ep_existing = 0
        total_qr_created = 0

        for cat_data in STARKES_DATA:
            category, cat_created = Category.objects.get_or_create(
                framework=framework,
                code=cat_data['code'],
                defaults={
                    'name': cat_data['name'],
                    'kelompok': cat_data['kelompok'],
                    'target_ep_count': cat_data['target_ep_count'],
                    'order': cat_data['order'],
                    'unit_pengampu': cat_data['unit_pengampu'],
                }
            )
            if cat_created:
                total_cat_created += 1
            else:
                # Update data jika sudah ada
                category.name = cat_data['name']
                category.kelompok = cat_data['kelompok']
                category.target_ep_count = cat_data['target_ep_count']
                category.order = cat_data['order']
                category.unit_pengampu = cat_data['unit_pengampu']
                category.save()
                total_cat_updated += 1

            # Tentukan unit pengampu default
            unit_obj = None
            if cat_data.get('default_unit_code'):
                unit_obj = UnitKerja.objects.filter(code=cat_data['default_unit_code']).first()
            if not unit_obj:
                unit_obj = default_fallback_unit

            # Seed Elemen Penilaian (EP)
            ep_order = 1
            for sub in cat_data['sub_standards']:
                for ep_idx in range(1, sub['ep_count'] + 1):
                    ep_code = f"{sub['code']} EP {ep_idx}"
                    ep_desc = f"{sub['desc_prefix']} sesuai standar elemen penilaian ke-{ep_idx} STARKES."

                    ep_item, ep_created = StandardItem.objects.get_or_create(
                        category=category,
                        code=ep_code,
                        defaults={
                            'sub_standard': sub['code'],
                            'sub_title': sub['title'],
                            'description': ep_desc,
                            'order': ep_order,
                        }
                    )
                    if ep_created:
                        total_ep_created += 1
                    else:
                        total_ep_existing += 1

                    ep_order += 1

                    # Pastikan QualityRecord ada untuk setiap EP
                    if unit_obj:
                        qr, qr_created = QualityRecord.objects.get_or_create(
                            standard_item=ep_item,
                            defaults={
                                'unit': unit_obj,
                                'score': 0,
                                'budget_status': 'DRAFT',
                                'eval_notes': f'Belum dinilai. Unit pengampu: {unit_obj.name}',
                            }
                        )
                        if qr_created:
                            total_qr_created += 1

        self.stdout.write(self.style.SUCCESS(
            f"Seeding Selesai!\n"
            f"- Pokja/Bab: {total_cat_created} dibuat, {total_cat_updated} diperbarui (Total: {Category.objects.count()} Bab)\n"
            f"- EP: {total_ep_created} dibuat baru, {total_ep_existing} sudah ada (Total: {StandardItem.objects.count()} EP)\n"
            f"- QualityRecord: {total_qr_created} dibuat baru (Total: {QualityRecord.objects.count()} QR)"
        ))
