"""Literal seed data for the RKK catalog, transcribed from
"BAB KREDENSIAL.docx" (Modul E-Kredensial & Penugasan Klinis ARIMA).

Structure: {profesi_code: (profesi_nama, keluarga, {jenjang_kode: (jenjang_nama, [(tindakan, status), ...])})}
Status codes: M = Mandiri, S = Supervisi, MT = Mandiri Terbatas.

Profesi sections 19-26 of the source duplicate earlier sections; resolution
follows the authoritative map: #4 Nutrisionis, #3 Dietisien, #12 Fisioterapi,
#9 Okupasi, #2 Sanitarian; #23 PMIK = #7 + extra Madya items; #25 Ahli K3RS
unique; #26 Utama for Penata Anestesi.
"""

# Profesi tanpa rincian jenjang di spec: parent saja, katalog diisi manual.
PROFESI_TANPA_JENJANG = {
    'DOKTER_SP': ('Dokter Spesialis', 'MEDIS'),
    'DOKTER_UMUM': ('Dokter Umum', 'MEDIS'),
}

# Fokus kompetensi jenjang dokter dari "master RKK Kewenangan klinis.docx";
# katalog butir menunggu SK komite (jangan mengarang daftar tindakan).
DOKTER_JENJANG = {
    'DOKTER_UMUM': (
        'Dokter Umum', [
            ('DU-UMUM', 'Dokter Umum (General Practitioner)', 1,
             'Pelayanan medis dasar, diagnosis, tatalaksana kasus gawat darurat awal, '
             'serta rujukan kasus medis umum di IGD dan rawat jalan. Mandiri (M) untuk '
             'kasus kompetensi 4A SKDI; Supervisi (S)/konsultasi untuk kasus di luar kompetensi dasar.',
             3),
            ('DU-SP', 'Dokter Spesialis (Clinical Specialist)', 2,
             'Pelayanan medis spesialistik mandiri, pengelolaan kasus tingkat sedang hingga '
             'berat, tindakan operatif/medis spesifik sesuai bidang ilmu. Mandiri Penuh (M) '
             'dalam lingkup spesialisasi + Anggota Komite Medis / Mitra Bestari.',
             3),
            ('DU-KONS', 'Dokter Subspesialis / Konsultan', 3,
             'Pelayanan medis subspesifik tingkat tinggi/lanjut, penanganan kasus rujukan '
             'tersier kompleks dan langka, riset klinis lanjutan. Mandiri Penuh (M) dengan '
             'hak prerogatif klinis tertinggi dan Tim Mitra Bestari Utama.',
             3),
        ]),
    'DOKTER_GIGI': (
        'Dokter Gigi', [
            ('DG-UMUM', 'Dokter Gigi (General Dentist)', 1,
             'Pelayanan kesehatan gigi dan mulut dasar: pemeriksaan, diagnosis, '
             'tatalaksana kasus gigi dasar, serta rujukan kasus di luar kompetensi. '
             'Mandiri (M) untuk kompetensi 4A SKDI; Supervisi (S) untuk tindakan di luar kompetensi dasar.',
             3),
            ('DG-SP', 'Dokter Gigi Spesialis (Clinical Specialist)', 2,
             'Pelayanan spesialistik mandiri sesuai bidang (Sp.KG, Sp.Ort, Sp.BM, Sp.Pros, '
             'Sp.Perio, Sp.An, Sp.Rad, Sp.PM). Mandiri Penuh (M) dalam lingkup spesialisasi '
             '+ Anggota Komite Medis / Mitra Bestari.',
             3),
            ('DG-KONS', 'Dokter Gigi Subspesialis / Konsultan', 3,
             'Pelayanan subspesifik tingkat tinggi, penanganan kasus rujukan kompleks, '
             'penyusunan PPK & Clinical Pathway kedokteran gigi. Mandiri Penuh (M) dengan '
             'hak prerogatif klinis tertinggi dan Tim Mitra Bestari Utama.',
             3),
        ]),
}

# Fisikawan Medis & Ahli K3RS: spec gives no per-action status -> seed 'S'.
DEFAULT_STATUS_UNSET = 'S'
CATATAN_STATUS_BAKU = 'Status baku belum ditetapkan; tinjau komite.'

PROFESI = {
    # ── NAKES_LAIN ──────────────────────────────────────────────────────
    'APOTEKER': ('Apoteker', 'NAKES_LAIN', {
        'AP-PRA': ('Apoteker Pratama / Pelaksana', []),
        'AP-MADYA': ('Apoteker Madya / Spesialis', []),
    }),
    'ELMD': ('Tenaga Elektromedis', 'NAKES_LAIN', {
        'PRATAMA': ('Elektromedis Pratama (Pelaksana)', [
            ('Pemeliharaan rutin alat non-invasif (tensimeter digital, TENS, nebulizer, bed pasien elektrik)', 'M'),
            ('Pencatatan inventaris alat medis', 'M'),
            ('Pemeriksaan kelayakan fisik alat harian', 'M'),
            ('Pemeliharaan alat kesehatan risiko sedang/tinggi', 'S'),
        ]),
        'MUDA': ('Elektromedis Muda (Pelaksana Lanjutan)', [
            ('Perbaikan & pemeliharaan Infuse/Syringe Pump, Patient Monitor, EKG, Suction Pump', 'M'),
            ('Analisis awal kerusakan komponen elektronik', 'M'),
        ]),
        'MADYA': ('Elektromedis Madya (Penyelia)', [
            ('Pengujian kalibrasi internal Defibrillator', 'M'),
            ('Perbaikan Ventilator, Mesin Anestesi, C-Arm, Electrosurgical Unit (ESU)', 'M'),
            ('Investigasi kegagalan sistem alat medis kritikal', 'M'),
            ('Supervisi & validasi kelaikan alat', 'M'),
        ]),
        'UTAMA': ('Elektromedis Utama', [
            ('Audit keselamatan listrik medis (IEC 60601)', 'M'),
            ('Manajemen risiko teknologi medis RS', 'M'),
            ('Evaluasi spesifikasi pengadaan alat medis canggih (CT-Scan/MRI/Cath Lab)', 'M'),
            ('Penguji kredensial elektromedis', 'M'),
        ]),
    }),
    'SANI': ('Sanitarian', 'NAKES_LAIN', {
        'PRATAMA': ('Sanitarian Pratama', [
            ('Pengambilan sampel air, udara, dan makanan harian', 'M'),
            ('Inspeksi ketersediaan tempat sampah medis/non-medis', 'M'),
            ('Pemantauan suhu & kelembaban ruangan non-kritikal', 'M'),
            ('Penanganan pajanan limbah B3', 'S'),
        ]),
        'MUDA': ('Sanitarian Muda', [
            ('Pengawasan operasional IPAL & uji baku mutu air limbah', 'M'),
            ('Pemantauan swab/udara mikrobiologi Kamar Operasi & ICU', 'M'),
            ('Pengendalian vektor & hama (pest control) RS', 'M'),
        ]),
        'MADYA': ('Sanitarian Madya', [
            ('Penyusunan manifes & tata kelola TPS B3', 'M'),
            ('Pengujian kualitas lingkungan kerja RS', 'M'),
            ('Investigasi pencemaran/paparan lingkungan', 'M'),
        ]),
        'UTAMA': ('Sanitarian Utama', [
            ('Audit menyeluruh kepatuhan baku mutu lingkungan nasional', 'M'),
            ('Perancangan sistem efisiensi energi & limbah RS', 'M'),
            ('Penyusunan standar operasional sanitasi instansi', 'M'),
        ]),
    }),
    'DIET': ('Dietisien', 'NAKES_LAIN', {
        'PRATAMA': ('Dietisien Pratama', [
            ('Skrining gizi lanjut (NRS-2002/MUST)', 'M'),
            ('Perhitungan kebutuhan energi dasar', 'M'),
            ('Preskripsi diet standar (Diet Lambung, Diet DM tanpa komplikasi)', 'M'),
            ('Preskripsi diet pada kasus kompleks', 'S'),
        ]),
        'MUDA': ('Dietisien Muda', [
            ('Formulasi Dietetik Khusus (Diet Ginjal, Diet Jantung, Diet Pasca Bedah)', 'M'),
            ('Konseling gizi spesifik', 'M'),
            ('Pemantauan respon terapi nutrisi oral/enteral dasar', 'M'),
        ]),
        'MADYA': ('Dietisien Madya', [
            ('Preskripsi Nutrisi Enteral & Parenteral Total (TPN) bersama DPJP', 'M'),
            ('Asuhan gizi pasien gagal organ multisistem', 'M'),
            ('Penyesuaian diet kasus kritis (ICU/ICCU/NICU)', 'M'),
        ]),
        'UTAMA': ('Dietisien Utama', [
            ('Konsultasi kasus gizi rumit/langka', 'M'),
            ('Evaluasi efektivitas terapi dietetik RS', 'M'),
            ('Penyusunan Formularium Nutrisi RS', 'M'),
        ]),
    }),
    'NUTR': ('Nutrisionis', 'NAKES_LAIN', {
        'PRATAMA': ('Nutrisionis Pratama', [
            ('Pencatatan sisa makanan pasien (Comstock)', 'M'),
            ('Pengawasan porsioning makanan rawat inap', 'M'),
            ('Pemeriksaan fisik bahan makanan yang diterima', 'M'),
        ]),
        'MUDA': ('Nutrisionis Muda', [
            ('Perhitungan kebutuhan bahan makanan harian', 'M'),
            ('Pengawasan penerapan HACCP di instalasi gizi', 'M'),
            ('Penyuluhan gizi kelompok di rawat jalan', 'M'),
        ]),
        'MADYA': ('Nutrisionis Madya', [
            ('Penyusunan siklus menu RS', 'M'),
            ('Evaluasi nilai gizi menu makanan pasien', 'M'),
            ('Audit higiene sanitasi pengolah makanan', 'M'),
            ('Analisis unit cost makanan', 'M'),
        ]),
        'UTAMA': ('Nutrisionis Utama', [
            ('Perancangan tata layout dapur instalasi gizi standar akreditasi', 'M'),
            ('Audit sistem keamanan pangan RS', 'M'),
            ('Penetapan pedoman gizi RS', 'M'),
        ]),
    }),
    'TB': ('Tenaga Teknis Tuberculosis', 'NAKES_LAIN', {
        'PRATAMA': ('TBD Pratama (Pelaksana)', [
            ('Edukasi cara pengeluaran dahak yang benar', 'M'),
            ('Fiksasi sediaan apusan dahak dasar', 'S'),
            ('Pemantauan kepatuhan minum obat (PMO) pasien TB sensitif obat', 'M'),
        ]),
        'MUDA': ('TBD Muda (Pelaksana Lanjutan)', [
            ('Pewarnaan & pembacaan skala IUATLD sediaan BTA', 'M'),
            ('Pengoperasian sampel TCM GeneXpert', 'M'),
            ('Pelaporan hasil Panic Value TB Resistan Obat (TB-RO)', 'M'),
        ]),
        'MADYA': ('TBD Madya (Penyelia)', [
            ('Validasi silang (cross-checking) sediaan BTA', 'M'),
            ('Manajemen logistik obat OAT & kartrid TCM', 'M'),
            ('Analisis data epidemiologi TB RS', 'M'),
        ]),
        'UTAMA': ('TBD Utama', [
            ('Audit klinis kepatuhan standar DOTS RS', 'M'),
            ('Investigasi kontak erat kasus TB-RO di lingkungan RS', 'M'),
            ('Penyusunan SPO pelayanan TB instansi', 'M'),
        ]),
    }),
    'TTK': ('Tenaga Teknis Kefarmasian', 'NAKES_LAIN', {
        'PRATAMA': ('TTK Pratama (Pelaksana)', [
            ('Membaca resep sederhana', 'S'),
            ('Mengambil obat jadi', 'S'),
            ('Menempelkan etiket obat', 'S'),
            ('Pencatatan kartu stok barang farmasi', 'S'),
        ]),
        'MUDA': ('TTK Muda (Pelaksana Lanjutan)', [
            ('Peracikan obat puyer, salep, atau sirup', 'MT'),
            ('Penyiapan obat metode Unit Dose Dispensing (UDD) harian', 'MT'),
            ('Pemeriksaan kedaluwarsa fisik obat', 'MT'),
        ]),
        'MADYA': ('TTK Madya (Penyelia)', [
            ('Pengelolaan stok depo rawat inap/OK', 'M'),
            ('Asistensi penyiapan nutrisi parenteral/rekonstitusi sitostatika di bawah pengarahan langsung Apoteker spesialis', 'S'),
            ('Verifikasi awal kelengkapan resep', 'M'),
        ]),
        'UTAMA': ('TTK Utama', [
            ('Audit kepatuhan penyimpanan obat High Alert / Narkotika di depo', 'M'),
            ('Evaluasi efisiensi ruang peracikan', 'M'),
            ('Penyusunan SPO teknis kefarmasian', 'M'),
        ]),
    }),
    'PMIK': ('Perekam Medis & Informasi Kesehatan', 'NAKES_LAIN', {
        'PRATAMA': ('PMIK Pratama (Pelaksana)', [
            ('Registrasi pasien rawat jalan/inap', 'M'),
            ('Penyimpanan & pengarsipan berkas (filing)', 'M'),
            ('Pencarian dokumen rekam medis fisik/digital', 'M'),
        ]),
        'MUDA': ('PMIK Muda (Pelaksana Lanjutan)', [
            ('Pengodean diagnosis (ICD-10) & prosedur tindakan (ICD-9-CM) kasus rawat jalan/inap umum', 'M'),
            ('Verifikasi kelengkapan ringkasan pulang (resume medis)', 'M'),
            ('Klaim BPJS tingkat awal', 'M'),
        ]),
        'MADYA': ('PMIK Madya (Penyelia)', [
            ('Koding kasus multi-organ & bedah kompleks', 'M'),
            ('Audit kelengkapan RME untuk akreditasi STARKES', 'M'),
            ('Pengolahan indeks penyakit & operasi', 'M'),
            ('Analisis kelayakan klaim asuransi', 'M'),
            ('Manajemen hak akses RME (User Access Control)', 'M'),
            ('Penyusunan statistik SIMRS', 'M'),
        ]),
        'UTAMA': ('PMIK Utama', [
            ('Pelepasan data medis untuk kasus hukum/visum', 'M'),
            ('Audit keamanan data RME & privasi pasien', 'M'),
            ('Perancangan struktur RME RS', 'M'),
        ]),
    }),
    'WICARA': ('Terapis Wicara', 'NAKES_LAIN', {
        'PRATAMA': ('Terapis Wicara Pratama', [
            ('Skrining keterlambatan bicara (speech delay)', 'S'),
            ('Terapi artikulasi sederhana', 'S'),
            ('Latihan kelancaran bicara (stuttering dasar)', 'MT'),
        ]),
        'MUDA': ('Terapis Wicara Muda', [
            ('Terapi artikulasi kompleks', 'M'),
            ('Rehabilitasi bicara anak Autism/Down Syndrome', 'M'),
            ('Latihan motorik oral (oral motor exercise)', 'M'),
            ('Penanganan disfagia fase oral', 'M'),
        ]),
        'MADYA': ('Terapis Wicara Madya', [
            ('Terapi Afasia komprehensif', 'M'),
            ('Latihan menelan pasien pasca stroke di rawat inap/ICU', 'M'),
            ('Rehabilitasi pasca laringektomi', 'M'),
            ('Evaluasi kemajuan fungsi swallowing', 'M'),
        ]),
        'UTAMA': ('Terapis Wicara Utama', [
            ('Penanganan kasus kompleks rujukan lintas subspesialis', 'M'),
            ('Penyusunan program rehabilitasi wicara jangka panjang', 'M'),
            ('Audit kepatuhan SPO keterapian wicara', 'M'),
        ]),
    }),
    'OKT': ('Okupasi Terapis', 'NAKES_LAIN', {
        'PRATAMA': ('Okupasi Terapis Pratama', [
            ('Evaluasi tingkat kemandirian ADL (Barthel Index)', 'S'),
            ('Latihan integrasi sensori dasar pada anak', 'S'),
            ('Pemberian latihan gerak fungsional tangan sederhana', 'MT'),
        ]),
        'MUDA': ('Okupasi Terapis Muda', [
            ('Terapi Sensori Integrasi (SI) mandiri pada pediatri', 'M'),
            ('Re-edukasi fungsi motorik halus tangan', 'M'),
            ('Pembuatan alat bantu adaptif sederhana (splint/brace tangan dasar)', 'M'),
            ('Pemulihan kemandirian ADL pasien stroke sedang', 'M'),
        ]),
        'MADYA': ('Okupasi Terapis Madya', [
            ('Terapi okupasi pasien Spinal Cord Injury / Traumatic Brain Injury', 'M'),
            ('Pembuatan splint/orthosis tangan kompleks', 'M'),
            ('Modifikasi lingkungan rumah/tempat kerja pasien', 'M'),
            ('Rehabilitasi okupasi pasien psikotik/skizofrenia', 'M'),
        ]),
        'UTAMA': ('Okupasi Terapis Utama', [
            ('Evaluasi dan desain aksesibilitas fasilitas umum RS/rumah pasien', 'M'),
            ('Audit program re-integrasi kerja (Return to Work)', 'M'),
            ('Penetapan standar SPO Okupasi Terapi', 'M'),
        ]),
    }),
    'ORPRO': ('Ortotik Prostetik', 'NAKES_LAIN', {
        'PRATAMA': ('Ortotik Prostetik Pratama', [
            ('Pengukuran & pembuatan Insole/Foot Orthosis', 'S'),
            ('Pencetakan gips kaki/tangan sederhana', 'S'),
            ('Perbaikan komponen mekanis alat ortotik yang rusak', 'M'),
        ]),
        'MUDA': ('Ortotik Prostetik Muda', [
            ('Pengukuran & pembalutan Ankle Foot Orthosis (AFO)', 'M'),
            ('Pengukuran & pembalutan Knee Ankle Foot Orthosis (KAFO)', 'M'),
            ('Pembuatan kaki tiruan bawah lutut (Transtibial Prosthesis)', 'M'),
            ('Latihan penggunaan alat (gait training dasar)', 'M'),
        ]),
        'MADYA': ('Ortotik Prostetik Madya', [
            ('Pembuatan Korset TLSO / Milwaukee Brace untuk scoliosis', 'M'),
            ('Pembuatan kaki tiruan atas lutut (Transfemoral Prosthesis)', 'M'),
            ('Pembuatan tangan tiruan mekanis', 'M'),
            ('Analisis laboratorium pola berjalan (gait analysis)', 'M'),
        ]),
        'UTAMA': ('Ortotik Prostetik Utama', [
            ('Konsultasi kasus deformitas bawaan/amputasi kompleks', 'M'),
            ('Evaluasi kelaikan fungsi alat bantu tingkat tinggi', 'M'),
            ('Penyusunan pedoman standar pelayanan Ortotik Prostetik RS', 'M'),
        ]),
    }),
    'ANES': ('Penata Anestesi', 'NAKES_LAIN', {
        'PRATAMA': ('Penata Anestesi Pratama', [
            ('Persiapan mesin anestesi & sirkuit pernapasan', 'S'),
            ('Penyiapan obat anestesi umum', 'S'),
            ('Pemantauan TTV pasien pra-anestesi', 'S'),
            ('Pemasangan akses intravena rutin', 'S'),
        ]),
        'MUDA': ('Penata Anestesi Muda', [
            ('Pemantauan kedalaman anestesi intra-operatif', 'S'),
            ('Pembebasan jalan napas dasar (pemasangan LMA/Intubasi ETT tanpa penyulit di bawah bimbingan)', 'S'),
            ('Pengawasan pasien di ruang pemulihan (PACU) ASA 1-2', 'MT'),
        ]),
        'MADYA': ('Penata Anestesi Madya', [
            ('Asistensi anestesi regional (spinal/epidural)', 'M'),
            ('Tindakan resusitasi jantung paru (RJP) intra-operatif', 'M'),
            ('Ekstubasi pasca bedah kasus berisiko', 'M'),
            ('Penanganan emergensi di PACU', 'M'),
        ]),
        'UTAMA': ('Penata Anestesi Utama', [
            ('Kepenataan anestesi kasus khusus/bedah mayor berisiko tinggi (ASA 4-5 di bawah instruksi Sp.An)', 'M'),
            ('Evaluasi WHO Surgical Safety Checklist', 'M'),
            ('Audit pelayanan anestesi', 'M'),
        ]),
    }),
    'FISIO': ('Fisioterapi', 'NAKES_LAIN', {
        'PRATAMA': ('Fisioterapis Pratama', [
            ('Aplikasi TENS', 'S'),
            ('Aplikasi Infra Red (IR)', 'S'),
            ('Aplikasi Ultrasound (US)', 'S'),
            ('Masase terapeutik dasar', 'MT'),
            ('Latihan gerak aktif/pasif sederhana', 'MT'),
        ]),
        'MUDA': ('Fisioterapis Muda', [
            ('Asesmen kekuatan otot (MMT) & lingkup gerak sendi (LGS)', 'M'),
            ('Fisioterapi dada (chest physiotherapy)', 'M'),
            ('Terapi latihan pasca stroke ringan/cedera olahraga', 'M'),
            ('Rehabilitasi ortopedi sederhana', 'M'),
        ]),
        'MADYA': ('Fisioterapis Madya', [
            ('Fisioterapi pasien terpasang ventilator di ICU', 'M'),
            ('Terapi manipulasi sendi spesifik', 'M'),
            ('Rehabilitasi penderita pasca operasi jantung/paru', 'M'),
            ('Penanganan Cerebral Palsy', 'M'),
        ]),
        'UTAMA': ('Fisioterapis Utama', [
            ('Asesmen kompleks lintas disiplin', 'M'),
            ('Penentuan rencana rehabilitasi jangka panjang kasus cacat berat', 'M'),
            ('Evaluasi kepatuhan SPO rehabilitasi', 'M'),
        ]),
    }),
    'PSIK': ('Psikologi Klinis', 'NAKES_LAIN', {
        'PRATAMA': ('Psikolog Klinis Pratama', [
            ('Administer alat tes psikologi (WAIS/SPM, MMPI dasar, Grafis)', 'M'),
            ('Wawancara psikologi klinis dasar', 'M'),
            ('Konseling psikologi edukatif/suportif', 'M'),
            ('Administer tes kepribadian kompleks', 'S'),
        ]),
        'MUDA': ('Psikolog Klinis Muda', [
            ('Skoring & interpretasi MMPI-2/Rorschach', 'M'),
            ('Pelaksanaan Psikoterapi Kognitif Perilaku (CBT) dasar', 'M'),
            ('Terapi konseling kecemasan/depresi ringan-sedang', 'M'),
            ('Pendampingan psikologis pasien penyakit kronis (kanker/HIV)', 'M'),
        ]),
        'MADYA': ('Psikolog Klinis Madya', [
            ('Psikoterapi trauma berat (EMDR/Somatic Experiencing)', 'M'),
            ('Evaluasi kecenderungan bunuh diri (Suicide Risk Assessment)', 'M'),
            ('Pemeriksaan psikologi forensik (visum et repertum psikiatrikum bersama Sp.KJ)', 'M'),
            ('Konseling krisis bencana', 'M'),
        ]),
        'UTAMA': ('Psikolog Klinis Utama', [
            ('Konsultasi kasus psikologi klinis rumit/langka', 'M'),
            ('Evaluasi standar psikotes RS', 'M'),
            ('Penyusunan pedoman pelayanan kesehatan mental terpadu RS', 'M'),
        ]),
    }),
    'RADG': ('Radiografer', 'NAKES_LAIN', {
        'PRATAMA': ('Radiografer Pratama (Pelaksana)', [
            ('Pemeriksaan X-Ray toraks', 'M'),
            ('Pemeriksaan X-Ray ekstremitas', 'M'),
            ('Pemeriksaan X-Ray tulang belakang konvensional dasar', 'M'),
            ('Pengoperasian alat foto rontgen umum', 'M'),
            ('Pemeriksaan radiografi kasus berat/kontras', 'S'),
        ]),
        'MUDA': ('Radiografer Muda (Pelaksana Lanjutan)', [
            ('Pembuatan foto kontras (IVP, Barium Enema/Swallow)', 'M'),
            ('Pengoperasian CT-Scan konvensional', 'M'),
            ('Proteksi radiasi pasien dan petugas', 'M'),
        ]),
        'MADYA': ('Radiografer Madya (Penyelia)', [
            ('Pemindaian MRI kompleks', 'M'),
            ('Prosedur intervensi radiologi (asistensi Cath Lab/C-Arm di OK)', 'M'),
            ('Evaluasi kualitas citra (Quality Assurance)', 'M'),
            ('Penanganan kedaruratan radiologi', 'M'),
        ]),
        'UTAMA': ('Radiografer Utama', [
            ('Optimalisasi protokol pemindaian modalitas tinggi', 'M'),
            ('Audit dosis radiasi', 'M'),
            ('Penanganan kegagalan teknik kompleks', 'M'),
            ('Penetapan SPO radiologi', 'M'),
        ]),
    }),
    'FMA': ('Fisikawan Medis', 'NAKES_LAIN', {
        'PRATAMA': ('Fisikawan Medis Pratama', [
            ('Pengukuran keluaran radiasi dasar', 'S'),
            ('Pembacaan dosimetri perorangan', 'S'),
        ]),
        'MUDA': ('Fisikawan Medis Muda', [
            ('Perhitungan dosis radioterapi/radiodiagnostik dasar', 'S'),
            ('Uji kesesuaian (compliance test) alat X-Ray', 'S'),
            ('Audit keselamatan radiasi rutin', 'S'),
        ]),
        'MADYA': ('Fisikawan Medis Madya', [
            ('Pengujian kualitas alat modalitas tinggi (CT-Scan/MRI)', 'S'),
            ('Perencanaan terapi radiasi (Treatment Planning System - TPS)', 'S'),
            ('Manajemen proteksi radiasi RS', 'S'),
        ]),
        'UTAMA': ('Fisikawan Medis Utama', [
            ('Konsultasi fisika medis RS', 'S'),
            ('Audit sistematis keselamatan radiasi nasional/instansional', 'S'),
            ('Pengujian kelayakan fasilitas radiologi baru', 'S'),
        ]),
    }),
    'ATLM': ('Ahli Teknologi Laboratorium Medik', 'NAKES_LAIN', {
        'PRATAMA': ('ATLM Pratama (Pelaksana)', [
            ('Pengambilan darah vena/kapiler', 'M'),
            ('Pemeriksaan hematologi rutin (Hb, Leukosit, Trombosit manual/semi-otomatis)', 'M'),
            ('Urinalisis rutin', 'M'),
            ('Pemuatan sampel pada alat otomatis', 'M'),
            ('Pemeriksaan spesimen berisiko tinggi', 'S'),
        ]),
        'MUDA': ('ATLM Muda (Pelaksana Lanjutan)', [
            ('Pemeriksaan kimia klinik komprehensif', 'M'),
            ('Imunoserologi (Widal, HBsAg, HIV rapid)', 'M'),
            ('Pewarnaan & pembacaan sediaan bakteriologi dasar', 'M'),
            ('Verifikasi hasil instrumen otomatis', 'M'),
        ]),
        'MADYA': ('ATLM Madya (Penyelia)', [
            ('Identifikasi kultur bakteri & uji sensitivitas antibiotik', 'M'),
            ('Validasi silang darah (crossmatching bank darah)', 'M'),
            ('Pembacaan apusan darah tepi kompleks', 'M'),
            ('Validasi kendali mutu (Quality Control) harian', 'M'),
        ]),
        'UTAMA': ('ATLM Utama', [
            ('Operasional analisis molekuler/PCR', 'M'),
            ('Investigasi hasil destruktif/pencetus bias sampel', 'M'),
            ('Audit laboratorium', 'M'),
            ('Penyusunan SPO laboratorium RS', 'M'),
        ]),
    }),
    'K3RS': ('Ahli K3RS', 'NAKES_LAIN', {
        'PRATAMA': ('Ahli K3 Pratama', [
            ('Inspeksi ketersediaan APAR/P3K', 'S'),
            ('Pemantauan penggunaan APD staf', 'S'),
            ('Pencatatan awal kejadian kecelakaan kerja (KTD/KNC nakes)', 'S'),
        ]),
        'MUDA': ('Ahli K3 Muda', [
            ('Investigasi kecelakaan kerja (Root Cause Analysis - RCA K3)', 'S'),
            ('Analisis risiko bahaya ruangan (HVA/HRA)', 'S'),
            ('Simulasi tanggap darurat bencana/kebakaran (Code Red)', 'S'),
        ]),
        'MADYA': ('Ahli K3 Madya', [
            ('Penyusunan sistem manajemen K3RS (SMK3)', 'S'),
            ('Audit kepatuhan fasilitas & keselamatan kerja per unit', 'S'),
            ('Evaluasi kesehatan berkala pegawai RS', 'S'),
        ]),
        'UTAMA': ('Ahli K3 Utama', [
            ('Konsultan manajemen risiko fasilitas (MFK STARKES)', 'S'),
            ('Perancangan sistem keselamatan bangunan RS', 'S'),
            ('Ketua tim audit keselamatan RS', 'S'),
        ]),
    }),
    # ── KEPERAWATAN_KEBIDANAN ───────────────────────────────────────────
    'KPR': ('Perawat', 'KEPERAWATAN_KEBIDANAN', {
        'PK-I': ('Perawat Klinis I (PK I)', [
            ('Pemenuhan kebutuhan dasar manusia (oksigenasi, eliminasi, nutrisi)', 'S'),
            ('Pengukuran tanda-tanda vital', 'S'),
            ('Pemberian obat oral dan injeksi dasar (subkutan/intramuskular)', 'S'),
            ('Perawatan luka bersih', 'S'),
        ]),
        'PK-II': ('Perawat Klinis II (PK II)', [
            ('Pemasangan infus', 'M'),
            ('Pemasangan kateter urin', 'M'),
            ('Pemasangan nasogastric tube (NGT)', 'M'),
            ('Pemberian obat high alert dan intravena', 'M'),
            ('Manajemen nyeri dasar', 'M'),
        ]),
        'PK-III': ('Perawat Klinis III (PK III)', [
            ('Pengelolaan asuhan keperawatan kritis/gawat darurat', 'M'),
            ('Bantuan hidup lanjut (BTCLS/PPGD)', 'M'),
            ('Asistensi prosedur medis khusus berisiko tinggi', 'M'),
            ('Supervisi perawat junior', 'M'),
        ]),
        'PK-IV': ('Perawat Klinis IV (PK IV)', [
            ('Intervensi keperawatan subspesialis (perawat kardiovaskular/perawat luka bakar kritis)', 'M'),
            ('Pengambilan keputusan klinis darurat tanpa pengawasan', 'M'),
            ('Menjadi anggota Tim Mitra Bestari Keperawatan', 'M'),
        ]),
        'PK-V': ('Perawat Klinis V (PK V)', [
            ('Kewenangan penuh lintas subspesialis keperawatan', 'M'),
            ('Konsultasi klinis kasus rumit', 'M'),
            ('Pengembangan riset Evidence-Based Practice', 'M'),
        ]),
    }),
    'BID': ('Bidan', 'KEPERAWATAN_KEBIDANAN', {
        'BK-I': ('Bidan Klinis I (BK I)', [
            ('Pemeriksaan kehamilan (ANC) rutin', 'S'),
            ('Edukasi kesehatan ibu dan anak', 'S'),
            ('Pertolongan persalinan normal fisiologis dengan bimbingan ketat', 'S'),
            ('Perawatan nifas dasar', 'S'),
        ]),
        'BK-II': ('Bidan Klinis II (BK II)', [
            ('Pertolongan persalinan normal secara mandiri', 'M'),
            ('Penjahitan jalan lahir (luka perineum derajat 1-2)', 'M'),
            ('Asesmen awal kegawatdaruratan kebidanan ringan', 'M'),
            ('Asuhan bayi baru lahir normal', 'M'),
        ]),
        'BK-III': ('Bidan Klinis III (BK III)', [
            ('Penanganan awal kegawatdaruratan maternal neonatal (PONEK)', 'M'),
            ('Resusitasi neonatus lanjut', 'M'),
            ('Asistensi tindakan operatif obstetri (Sectio Caesarea)', 'M'),
            ('Pemantauan ketat ibu hamil risiko tinggi', 'M'),
        ]),
        'BK-IV': ('Bidan Klinis IV (BK IV)', [
            ('Keputusan klinis tingkat lanjut pada kasus penyulit kebidanan berat', 'M'),
            ('Audit kasus kebidanan bersama Komite Keperawatan/Kebidanan', 'M'),
            ('Pengarah klinis unit ruang bersalin', 'M'),
        ]),
        'BK-V': ('Bidan Klinis V (BK V)', [
            ('Kewenangan penuh pada seluruh tindakan kebidanan kompleks', 'M'),
            ('Konsultasi rujukan kasus khusus', 'M'),
            ('Validasi asesmen kredensial bidang kebidanan', 'M'),
        ]),
    }),
}

# Fokus kompetensi singkat per (profesi_code, jenjang_kode), dari
# "master RKK Kewenangan klinis.docx". Dipakai seed untuk mengisi kolom
# fokus_kompetensi yang masih kosong; tidak mengubah butir katalog.
FOKUS_KOMPETENSI = {
    ('ELMD', 'PRATAMA'): 'Pengoperasian, pemeliharaan preventif dasar, dan inspeksi fisik elektromedis risiko rendah.',
    ('ELMD', 'MUDA'): 'Pemeliharaan, perbaikan tingkat menengah, dan uji fungsi alat kesehatan risiko sedang.',
    ('ELMD', 'MADYA'): 'Kalibrasi, perbaikan alat medis risiko tinggi/kritikal (OK & ICU), uji kelaikan instrumen canggih.',
    ('ELMD', 'UTAMA'): 'Ahli/konsultan teknologi elektromedis RS; uji kelaikan fasilitas medis baru; penyusun SPO pemeliharaan alat.',
    ('SANI', 'PRATAMA'): 'Pengambilan sampel lingkungan, inspeksi sarana, dan pemantauan dasar kesehatan lingkungan.',
    ('SANI', 'MUDA'): 'Pengawasan IPAL, uji baku mutu, dan pemantauan mikrobiologi ruang kritikal.',
    ('SANI', 'MADYA'): 'Perencanaan program kesehatan lingkungan dan audit keselamatan lingkungan RS.',
    ('SANI', 'UTAMA'): 'Konsultan kesehatan lingkungan; kebijakan manajemen limbah & kualitas lingkungan rumah sakit.',
    ('ANES', 'PRATAMA'): 'Persiapan alat & obat anestesi di bawah delegasi/supervisi langsung Dokter Sp.An.',
    ('ANES', 'MUDA'): 'Asuhan kepenataan anestesi pra-intra-pasca pada pasien ASA 1 & 2.',
    ('ANES', 'MADYA'): 'Kepenataan anestesi kasus bedah kompleks (ASA 3), manajemen jalan napas sulit, resusitasi.',
    ('ANES', 'UTAMA'): 'Konsultan kepenataan anestesi; penyusun SPO pelayanan anestesi bersama Komite Medis.',
    ('PSIK', 'PRATAMA'): 'Asesmen psikologis dasar dengan supervisi psikolog klinis senior.',
    ('PSIK', 'MUDA'): 'Pelaksanaan tes psikologi & intervensi dasar secara mandiri terbatas.',
    ('PSIK', 'MADYA'): 'Diagnosis klinis, psikoterapi, dan supervisi praktik psikologi.',
    ('PSIK', 'UTAMA'): 'Konsultan psikologi klinis; kebijakan layanan psikologi & Mitra Bestari.',
    ('FISIO', 'PRATAMA'): 'Penilaian dan tindakan terapi fisik dasar dengan pendampingan.',
    ('FISIO', 'MUDA'): 'Terapi fisik mandiri untuk kasus muskuloskeletal & neuro dasar.',
    ('FISIO', 'MADYA'): 'Pengelolaan kasus kompleks, preseptor keterapian fisik.',
    ('FISIO', 'UTAMA'): 'Konsultan fisioterapi; pengembang SPO rehabilitasi & Mitra Bestari.',
    ('KPR', 'PK-I'): 'Asuhan keperawatan dasar dengan bimbingan dan supervisi berkala.',
    ('KPR', 'PK-II'): 'Asuhan keperawatan mandiri untuk pasien kompleksitas rendah-sedang di rawat inap.',
    ('KPR', 'PK-III'): 'Mengelola kasus kompleks/kritis, clinical preceptor, tugas di unit khusus.',
    ('KPR', 'PK-IV'): 'Kasus subspesialis lanjut, audit mutu keperawatan, pengembang SPO asuhan.',
    ('KPR', 'PK-V'): 'Konsultan keperawatan klinik, peneliti klinis, penentu kebijakan asuhan keperawatan RS.',
    ('BID', 'BK-I'): 'Asuhan kebidanan fisiologis dasar dengan supervisi bidan senior.',
    ('BID', 'BK-II'): 'Asuhan kebidanan fisiologis mandiri di kamar bersalin & poliklinik.',
    ('BID', 'BK-III'): 'Mengelola kasus penyulit/risiko tinggi, deteksi dini komplikasi obstetri, preseptor.',
    ('BID', 'BK-IV'): 'Kegawatdaruratan obstetri kompleks, audit Maternal Perinatal (AMP).',
    ('BID', 'BK-V'): 'Konsultan maternitas, penentu kebijakan pelayanan KIA, pengembang standar praktik.',
}

# ── Katalog dokter tertutup ("Katalog tindakan klinis.docx", RS Tipe B) ──
# Dokter Umum: 10 butir, status M (SKDI 4A), jenjang DU-UMUM.
KATALOG_DOKTER_UMUM = [
    'Anamnesis dan Pemeriksaan Fisik Komprehensif',
    'Pemasangan & Pelepasan Infus / Jalur Intravena Perifer',
    'Pemasangan & Pelepasan Kateter Urin',
    'Pemasangan & Pelepasan NGT (Nasogastric Tube)',
    'Terapi Oksigenasi & Resusitasi Jantung Paru (RJP / BCLS)',
    'Interpretasi Perekaman EKG Dasar',
    'Penjahitan Luka Sederhana (Hecting) & Debridement Ringan',
    'Pengambilan Darah Vena / Arteri (Analisa Gas Darah)',
    'Pungsi Pleura / Thoracocentesis Sederhana (dengan supervisi/indikasi darurat)',
    'Edukasi & Informed Consent Pasien Rawat Inap',
]

# (kode_sp, nama_spesialisasi, [butir]) — 16 spesialisasi.
KATALOG_SPESIALIS = [
    ('SP-PD', 'Spesialis Penyakit Dalam (Sp.PD)', [
        'Visite dan manajemen kasus metabolik/infeksi kompleks',
        'Pemasangan CVC (Central Venous Catheter)',
        'Pungsi asites dan torakosentesis diagnostik/terapeutik',
        'Biopsi sumsum tulang (bone marrow puncture)',
    ]),
    ('SP-B', 'Spesialis Bedah (Sp.B)', [
        'Operasi bedah digestif dasar (appendektomi, herniotomi)',
        'Debridement luka infeksi/gangren luas',
        'Eksisi tumor jinak/ganas superfisial',
        'Sirkumsisi dan penanganan trauma bedah minor',
    ]),
    ('SP-A', 'Spesialis Anak (Sp.A)', [
        'Resusitasi neonatus dan stabilisasi bayi baru lahir',
        'Pemasangan infus dan injeksi pediatrik khusus',
        'Imunisasi dasar dan lanjutan',
        'Penanganan kasus kegawatdaruratan anak (infeksi berat, dehidrasi)',
    ]),
    ('SP-OG', 'Spesialis Obstetri dan Ginekologi (Sp.OG)', [
        'Pertolongan persalinan normal dan sectio caesarea (SC)',
        'Kuretase dan penanganan perdarahan obstetri',
        'Pemasangan/pencabutan kontrasepsi jangka panjang (IUD/Implan)',
        'Pemeriksaan USG obstetri dan ginekologi',
    ]),
    ('SP-JP', 'Spesialis Jantung dan Pembuluh Darah (Sp.JP)', [
        'Elektrokardiografi (EKG) dan Uji Latih Jantung (Treadmill)',
        'Ekokardiografi transtorakal (TTE)',
        'Pemasangan Holter monitor / ABPM',
        'Kardioversi elektrik darurat',
    ]),
    ('SP-S', 'Spesialis Saraf (Neurologi) (Sp.S / Sp.N)', [
        'Pemeriksaan neurologis komprehensif',
        'Pungsi lumbal (LP)',
        'Interpretasi EEG (Electroencephalography)',
        'Tatalaksana stroke akut dan tata laksana nyeri kepala/neuropati',
    ]),
    ('SP-AN', 'Spesialis Anestesiologi dan Terapi Intensif (Sp.An)', [
        'Manajemen anestesi umum, regional, dan spinal untuk operasi',
        'Manajemen jalan napas lanjut dan intubasi endotrakeal',
        'Perawatan pasien kritis di ICU dan pemantauan hemodinamik invasif',
        'Manajemen nyeri akut dan kronis',
    ]),
    ('SP-RAD', 'Spesialis Radiologi (Sp.Rad)', [
        'Pembacaan dan interpretasi foto Rontgen konvensional',
        'Pemeriksaan USG diagnostik multisistem',
        'Interpretasi CT-Scan dan MRI',
        'Pemeriksaan fluoroskopi khusus (Barium enema/meal, HSG)',
    ]),
    ('SP-PK', 'Spesialis Patologi Klinik (Sp.PK)', [
        'Validasi dan interpretasi hasil laboratorium klinik (hematologi, kimia darah, imunologi)',
        'Konsultasi klinis hasil pemeriksaan laboratorium kritis',
        'Pengendalian mutu internal dan eksternal laboratorium',
    ]),
    ('SP-PA', 'Spesialis Patologi Anatomi (Sp.PA)', [
        'Pemeriksaan sitologi (FNAB/Aspirasi Jarum Halus)',
        'Histopatologi jaringan biopsi/operasi',
        'Interpretasi sediaan frozen section (pembedahan darurat)',
    ]),
    ('SP-OT', 'Spesialis Bedah Orthopedi dan Traumatologi (Sp.OT)', [
        'Reduksi tertutup dan fiksasi fraktur tulang',
        'Operasi pemasangan fiksasi internal (ORIF/Closed Reduction)',
        'Artroskopi sendi dasar',
        'Penanganan cedera olahraga dan rekonstruksi ortopedi',
    ]),
    ('SP-THT', 'Spesialis THT-KL (Sp.THT-KL)', [
        'Ekstraksi korpus alienum (benda asing) di THT',
        'Tindakan miringotomi dan timpanoplasti dasar',
        'Tonsilektomi dan adenoidektomi',
        'Endoskopi diagnostik hidung/tenggorokan',
    ]),
    ('SP-M', 'Spesialis Mata (Sp.M)', [
        'Operasi katarak (Phacoemulsification / SICS)',
        'Ekstraksi benda asing kornea/konjungtiva',
        'Tonometri dan pemeriksaan lapang pandang',
        'Pemeriksaan funduskopi dan refraksi mata',
    ]),
    ('SP-KK', 'Spesialis Kulit dan Kelamin (Sp.KK / Sp.DV)', [
        'Electrocauterization / Kauterisasi lesi kulit',
        'Eksterpasi / eksisi lesi jinak kulit',
        'Patch test (uji tempel) alergi',
        'Terapi sinar/laser dermatologi dasar',
    ]),
    ('SP-KJ', 'Spesialis Kedokteran Jiwa (Psikiatri) (Sp.KJ)', [
        'Psikoterapi suportif dan perilaku kognitif',
        'Wawancara psikiatrik dan asesmen psikopatologi',
        'Penatalaksanaan farmakoterapi gangguan jiwa',
        'Penilaian visum et repertum psikiatrik',
    ]),
    ('SP-P', 'Spesialis Pulmonologi dan Kedokteran Respirasi (Sp.P)', [
        'Spirometri dan uji fungsi paru',
        'Pungsi pleura dan pemasangan WSD (Water Seal Drainage)',
        'Bronkoskopi diagnostik',
        'Penatalaksanaan tuberkulosis resistan obat (TB-RO) dan asma berat',
    ]),
]

# (kode_subsp, nama_subspesialisasi, [butir]) — 16 subspesialisasi,
# menggantung di profesi DOKTER_SP dengan urutan 3.
KATALOG_SUBSPESIALIS = [
    ('SUBSP-PD-GINJAL', 'Subspesialis Penyakit Dalam - Ginjal Hipertensi', [
        'Tindakan Hemodialisis darurat dan pemeliharaan',
        'Pemasangan kateter vakuum / kateter hemofiltrasi akut',
        'Biopsi ginjal perkutan bimbingan USG',
        'Peritoneal dialysis (CAPD) tatalaksana dan evaluasi',
    ]),
    ('SUBSP-PD-KARDIO', 'Subspesialis Penyakit Dalam - Kardiologi', [
        'Ekokardiografi lanjut dan pemantauan hemodinamik non-invasif',
        'Tatalaksana gagal jantung lanjut dan aritmia kompleks',
        'Kardioversi medikamentosa dan elektrik terarah',
    ]),
    ('SUBSP-B-KBD', 'Subspesialis Bedah - Digestif (Sp.B-KBD)', [
        'Bedah laparoskopi tingkat lanjut (kolektomi, gastrektomi, reseksi usus)',
        'Operasi saluran empedu kompleks dan pankreas',
        'Penanganan bedah onkologi saluran cerna kompleks',
    ]),
    ('SUBSP-B-ONK', 'Subspesialis Bedah - Onkologi (Sp.B(K)Onk)', [
        'Operasi radikal kanker payudara (Modified Radical Mastectomy / Breast Conserving Surgery)',
        'Eksisi luas dan diseksen kelenjar getah bening regional',
        'Biopsi eksisional tumor ganas jaringan lunak/kulit',
    ]),
    ('SUBSP-A-PERINATO', 'Subspesialis Anak - Perinatologi / Neonatologi', [
        'Pemasangan akses vaskular sentral pada neonatus (UVC/UAC)',
        'Perawatan intensif neonatus (NICU) dengan ventilasi mekanik lanjut',
        'Transfusi tukar pada bayi baru lahir dengan hiperbilirubinemia berat',
    ]),
    ('SUBSP-A-RESPI', 'Subspesialis Anak - Respirologi / Infeksi', [
        'Bronkoskopi diagnostik pediatrik',
        'Pungsi pleura dan pemasangan WSD anak',
        'Tatalaksana kasus infeksi paru berat/pneumonia berulang',
    ]),
    ('SUBSP-OG-FETOM', 'Subspesialis Obstetri & Ginekologi - Fetomaternal', [
        'USG fetomaternal tingkat lanjut (Anomaly scan / USG 4D diagnostik)',
        'Amniosentesis dan prosedur prenatal invasif',
        'Penanganan kehamilan risiko tinggi dengan komplikasi maternal-fetal kompleks',
    ]),
    ('SUBSP-OG-ONK', 'Subspesialis Obstetri & Ginekologi - Onkologi', [
        'Operasi radikal kanker serviks, ovarium, dan endometrium',
        'Histerektomi radikal dan limfadenektomi pelvik',
        'Kolposkopi dan biopsi lesi prakanker ginekologi',
    ]),
    ('SUBSP-JP-FIHA', 'Subspesialis Jantung - Kardiologi Intervensi (FIHA)', [
        'Kateterisasi jantung diagnostik (Coronary Angiography)',
        'Intervensi Koroner Perkutan (PCI / Pasang Ring Jantung primer maupun elektif)',
        'Pemasangan Alat Pacu Jantung Permanen (PPM) dan pericardiocentesis terapeutik',
    ]),
    ('SUBSP-S-NEUROVASK', 'Subspesialis Saraf - Neurovaskular / Stroke', [
        'Tatalaksana trombolisis intravena pada stroke iskemik akut',
        'USG Doppler pembacaan vaskular ekstrakranial/transcranial',
        'Manajemen intervensi neurovaskular dasar bersama tim terkait',
    ]),
    ('SUBSP-BS-NEURONK', 'Subspesialis Bedah Saraf - Neuro-Onkologi', [
        'Craniotomy pengangkatan tumor otak kompleks',
        'Bedah mikroskopik saraf tulang belakang (Spine surgery / laminektomi & fiksasi)',
        'Evakuasi perdarahan intrakranial kompleks',
    ]),
    ('SUBSP-AN-ICU', 'Subspesialis Anestesiologi - Intensive Care', [
        'Manajemen ventilasi mekanik lanjut dan titrasi hemodinamik invasif di ICU',
        'Pemasangan kateter vena sentral (CVC) dan kateter arteri radialis',
        'Penanganan kegagalan multi-organ (MODS) di ruang intensif',
    ]),
    ('SUBSP-OT-TRAUMA', 'Subspesialis Orthopedi - Traumatologi / Hip & Knee', [
        'Artroskopi rekonstruksi ligamen lutut lanjut (ACL/PCL reconstruction)',
        'Penggantian sendi panggul dan lutut total (Total Hip / Knee Replacement)',
        'Fiksasi fraktur kompleks pelvis dan acetabulum',
    ]),
    ('SUBSP-THT-OTO', 'Subspesialis THT - Otologi / Rinologi', [
        'Operasi timpanoplasti dan mastoidektomi radikal (Bedah mikro telinga)',
        'Bedah Sinus Endoskopi Fungsional (BSEF / FESS)',
        'Operasi rekonstruksi jalan napas dan bedah kepala leher lanjut',
    ]),
    ('SUBSP-M-RETINA', 'Subspesialis Mata - Vitreoretina / Glaukoma', [
        'Operasi vitrektomi pars plana (kasus retina dan ablasi retina)',
        'Operasi trabekulektomi dan penanganan bedah glaukoma lanjut',
        'Injeksi intravitreal obat anti-VEGF',
    ]),
    ('SUBSP-P-TORAKS', 'Subspesialis Pulmonologi - Onkologi Toraks', [
        'Bronkoskopi terapeutik intervensi (pengambilan benda asing, stenting saluran napas)',
        'Pleurodesis dan torakosentesis lanjutan',
        'Evaluasi uji fungsi paru komprehensif lanjutan',
    ]),
]

# ── Katalog nakes lain per level ("Katalog tindakan klinis.docx") ──
# {profesi_code: {jenjang_kode: [(butir, status)]}}; profesi & jenjang
# harus sudah ada di PROFESI di atas. Status: 'M' bila dokumen eksplisit
# menyebut mandiri; selain itu DEFAULT_STATUS_UNSET ('S').
KATALOG_NAKES_TAMBAHAN = {
    'KPR': {
        'PK-I': [
            ('Pengukuran tanda-tanda vital komprehensif & asesmen risiko jatuh', 'S'),
            ('Pemasangan infus (IV line) dan pengambilan darah vena', 'S'),
            ('Pemberian obat oral, injeksi (IM, IV, SC, IC), dan topikal', 'S'),
            ('Perawatan luka bersih / ganti balutan dasar', 'S'),
            ('Pemasangan kateter urin & NGT (Nasogastric Tube)', 'S'),
        ],
        'PK-II': [
            ('Manajemen pemantauan hemodinamik dasar & balance cairan ketat', 'S'),
            ('Perawatan luka stadium lanjut / dekubitus / luka diabetes (modern dressing)', 'M'),
            ('Resusitasi Jantung Paru (RJP/BCLS) & manajemen oksigenasi kompleks', 'S'),
            ('Fasilitasi mobilisasi pasien dengan traksi / tirah baring lama', 'M'),
        ],
        'PK-III': [
            ('Manajemen asuhan keperawatan pasien kritis di ICU/ICCU/ICU Neonatus', 'M'),
            ('Manajemen nyeri komprehensif (termasuk perawatan pasien paliatif)', 'M'),
        ],
        'PK-IV': [
            ('Supervisi klinis, preseptorship, & audit dokumentasi asuhan keperawatan', 'M'),
            ('Koordinasi evakuasi pasien gawat darurat / bencana (Triage disaster)', 'M'),
        ],
    },
    'BID': {
        'BK-I': [
            ('Pemeriksaan ANC (Antenatal Care) rutin & pemantauan denyut jantung janin (DJJ)', 'M'),
            ('Pertolongan persalinan normal (Asuhan Persalinan Normal / APN)', 'M'),
            ('Perawatan nifas & konseling laktasi dasar', 'M'),
            ('Imunisasi dasar pada bayi & ibu hamil', 'M'),
        ],
        'BK-II': [
            ('Manajemen penanganan komplikasi kebidanan awal (rujukan darurat kasus preeklamsia/atonia uteri)', 'M'),
            ('Pemasangan dan pelepasan alat kontrasepsi (IUD / Implant)', 'M'),
            ('Asuhan bayi baru lahir dengan penyulit ringan (asfiksia ringan)', 'M'),
        ],
        'BK-III': [
            ('Manajemen pelayanan obstetri neonatal emergensi komprehensif (PONEK)', 'M'),
            ('Konseling kesehatan reproduksi dan keluarga berencana tingkat lanjut', 'M'),
        ],
        'BK-IV': [
            ('Supervisi fasilitas pelayanan kebidanan dan audit Maternal Perinatal (AMP)', 'M'),
        ],
    },
    'APOTEKER': {
        'AP-PRA': [
            ('Skrining resep administratif, farmasetik, dan klinis harian', 'M'),
            ('Pelayanan Informasi Obat (PIO) kepada pasien dan tenaga medis', 'M'),
            ('Rekonsiliasi obat pasien rawat inap (masuk, pindah ruang, pulang)', 'M'),
            ('Pemantauan Terapi Obat (PTO) dasar', 'M'),
        ],
        'AP-MADYA': [
            ('Monitoring Efek Samping Obat (MESO) dan pelaporan IFRS', 'M'),
            ('Evaluasi Penggunaan Obat (EPO) & farmakoekonomi bangsal', 'M'),
            ('Visite klinis mandiri / kolaboratif bersama dokter spesialis (ICU/Onkologi)', 'M'),
            ('Manajemen pencampuran obat steril (Aseptic Dispensing / Sitostatika)', 'M'),
        ],
    },
    'ELMD': {
        'PRATAMA': [
            ('Kalibrasi dan pemeliharaan preventif alat elektromedik ringan (suction pump, infusion pump)', 'M'),
            ('Perbaikan kerusakan ringan perangkat medis non-life supporting', 'M'),
            ('Inventarisasi dan inspeksi keselamatan kerja alat elektromedik harian', 'M'),
        ],
        'MADYA': [
            ('Kalibrasi dan pemeliharaan alat medis kompleks (Ventilator, Mesin Anestesi, Defibrilator, Mesin USG)', 'M'),
            ('Uji fungsi dan kelaikan alat medis baru (Commissioning test) sebelum dioperasikan', 'M'),
            ('Analisis risiko kegagalan alat medis (Risk assessment maintenance) berbasis standar ISO/STARKES', 'M'),
        ],
    },
    'SANI': {
        'PRATAMA': [
            ('Pengambilan sampel kualitas air bersih dan air limbah rumah sakit', 'M'),
            ('Pemantauan kebersihan lingkungan fisik ruangan (lantai, dinding, udara ruang steril)', 'M'),
            ('Pengelolaan dan pengangkutan limbah medis/non-medis sementara (TPS B3)', 'M'),
        ],
        'MADYA': [
            ('Pengendalian vektor dan binatang pembawa penyakit (pest control monitoring)', 'M'),
            ('Audit Instalasi Pengolahan Air Limbah (IPAL) dan insinerator rumah sakit', 'M'),
            ('Evaluasi analisis dampak lingkungan (AMDAL/UKL-UPL) fasilitas kesehatan', 'M'),
        ],
    },
}
KATALOG_NAKES_TAMBAHAN['DIET'] = {
    'MADYA': [
        ('Asesmen gizi mendalam untuk pasien dengan kondisi khusus (DM, Gagal Ginjal, Stroke, Kanker)', 'M'),
        ('Perhitungan kebutuhan zat gizi makro dan mikro serta penyusunan preskripsi diet khusus', 'M'),
        ('Konseling gizi klinik individual bagi pasien rawat inap maupun rawat jalan', 'M'),
        ('Evaluasi intervensi asuhan gizi terintegrasi bersama tim medis', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['NUTR'] = {
    'PRATAMA': [
        ('Pengukuran antropometri pasien (berat badan, tinggi badan, LILA, IMT)', 'M'),
        ('Distribusi makanan pasien sesuai diet dan penyusunan porsi harian', 'M'),
        ('Skrining gizi awal pasien rawat inap', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['TTK'] = {
    'PRATAMA': [
        ('Penyiapan, peracikan, dan pengemasan sediaan farmasi (puyer, kapsul, salep)', 'M'),
        ('Pengelolaan persediaan obat di depo farmasi / floor stock', 'M'),
        ('Distribusi perbekalan kesehatan dan obat ke ruang perawatan', 'M'),
    ],
    'MADYA': [
        ('Pengelolaan logistik rantai dingin (cold chain) vaksin dan obat termolabil', 'M'),
        ('Pemeriksaan stok opname berkala dan pemantauan tanggal kadaluarsa obat', 'M'),
        ('Pengawasan penyimpanan obat High Alert dan LASA di instalasi farmasi', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['ANES'] = {
    'PRATAMA': [
        ('Persiapan mesin anestesi, alat intubasi, dan obat-obatan anestesi sebelum tindakan', 'S'),
        ('Asistensi dokter spesialis anestesiologi selama induksi, pemeliharaan, hingga pemulihan', 'S'),
        ('Pemantauan tanda vital dan kedalaman sedasi/anestesi intra-operatif', 'S'),
    ],
    'MADYA': [
        ('Manajemen jalan napas lanjutan (advanced airway management) mandiri/kolaborasi', 'M'),
        ('Manajemen pemulihan pasien di Ruang Pulih Sadar (Recovery Room / PACU)', 'M'),
        ('Pengelolaan asesmen pra-anestesi dan edukasi risiko anestesi bersama tim', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['PMIK'] = {
    'PRATAMA': [
        ('Pengumpulan, perakitan (assembling), dan penataan dokumen rekam medis (RM)', 'M'),
        ('Pendataan registrasi pasien rawat jalan, gawat darurat, dan rawat inap', 'M'),
        ('Distribusi berkas rekam medis ke poliklinik/bangsal', 'M'),
    ],
    'MADYA': [
        ('Koding diagnosis dan tindakan medis menggunakan ICD-10 dan ICD-9-CM (untuk klaim BPJS/asuransi)', 'M'),
        ('Audit kelengkapan pengisian rekam medis (Quantitative & Qualitative Analysis)', 'M'),
        ('Manajemen kerahasiaan, retensi, dan pemusnahan arsip rekam medis sesuai regulasi', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['WICARA'] = {
    'PRATAMA': [
        ('Skrining gangguan komunikasi, bahasa, dan bicara pada anak atau dewasa', 'S'),
    ],
    'MADYA': [
        ('Terapi rehabilitasi gangguan artikulasi, bahasa ekspresif/reseptif, dan gagap', 'M'),
        ('Terapi gangguan menelan (dysphagia therapy) pada pasien stroke atau pasca-bedah', 'M'),
        ('Penyusunan program latihan wicara mandiri untuk keluarga pasien di rumah', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['OKT'] = {
    'PRATAMA': [
        ('Identifikasi hambatan aktivitas sehari-hari (Activities of Daily Living / ADL) pasien', 'S'),
    ],
    'MADYA': [
        ('Rehabilitasi okupasional fisik/mental (latihan fungsi motorik halus tangan, kognitif, persepsi)', 'M'),
        ('Modifikasi lingkungan rumah dan alat bantu kerja/hidup mandiri bagi penyandang disabilitas', 'M'),
        ('Evaluasi kesiapan kembali bekerja (return to work assessment) bagi pasien pasca trauma/stroke', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['ORPRO'] = {
    'PRATAMA': [
        ('Pengukuran dimensi tubuh pasien untuk pembuatan alat bantu ortosis atau prostesis', 'S'),
    ],
    'MADYA': [
        ('Desain, pembuatan, dan fitting alat bantu gerak (kaki/tangan palsu, korset koreksi skoliosis, brace)', 'M'),
        ('Evaluasi biomekanik dan pelatihan penyesuaian penggunaan alat bagi pasien amputasi/kelainan muskuloskeletal', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['FISIO'] = {
    'PRATAMA': [
        ('Pelaksanaan modalitas fisioterapi standar (terapi panas/dingin, TENS, US fisioterapi)', 'M'),
        ('Latihan rentang gerak (Range of Motion / ROM) dasar pada pasien tirah baring', 'M'),
    ],
    'MADYA': [
        ('Pemeriksaan neuromuskuloskeletal dan cardiorespiratory lanjutan', 'M'),
        ('Fisioterapi dada (chest physiotherapy) untuk pembersihan jalan napas', 'M'),
        ('Rehabilitasi jantung, paru, stroke, dan pasca cedera olahraga secara komprehensif', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['PSIK'] = {
    'MUDA': [
        ('Pelaksanaan asesmen psikologis awal dan observasi perilaku klinis', 'S'),
    ],
    'MADYA': [
        ('Pemeriksaan psikodiagnostik lanjut (tes proyektif, inteligensi, kepribadian)', 'M'),
        ('Psikoterapi klinis individual/keluarga (terapi kognitif perilaku / CBT, konseling trauma)', 'M'),
        ('Penanganan kasus kesehatan mental berat dan asesmen kelayakan psikologis pasien khusus', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['RADG'] = {
    'PRATAMA': [
        ('Pembuatan citra radiografi konvensional (X-ray dada, ekstremitas, abdomen)', 'M'),
        ('Persiapan pasien dan pengaturan proteksi radiasi dasar', 'M'),
    ],
    'MADYA': [
        ('Pengoperasian pencitraan tingkat lanjut (CT-Scan, MRI, USG, Mammografi, Fluoroskopi)', 'M'),
        ('Quality Control (QC) harian alat pencitraan diagnostik dan pemantauan dosis radiasi pekerja', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['FMA'] = {
    'NUTR_FALLBACK_PLACEHOLDER': [],
}
# Fisikawan Medis: jenjang seed lama tidak membagi Pratama/Madya + katalog lama
# sudah 11 butir (FMA). Dokumen menambah 2 level — tulis ke jenjang MUDA-MADYA
# gabungan hanya bila ada; kalau tidak, letakkan di jenjang pertama.
KATALOG_NAKES_TAMBAHAN.pop('NUTR_FALLBACK_PLACEHOLDER', None)
KATALOG_NAKES_TAMBAHAN['FMA'] = {
    'PRATAMA': [
        ('Pengukuran dosis radiasi harian dan survei radiasi lingkungan sekitar instalasi radioterapi/radiologi', 'S'),
    ],
    'MADYA': [
        ('Perencanaan dosis radiasi (treatment planning) untuk pasien radioterapi kanker', 'M'),
        ('Kalibrasi dosimetri berkala pada mesin linac, telekobalt, dan peralatan kedokteran nuklir', 'M'),
        ('Evaluasi audit keselamatan proteksi radiasi fasilitas medis secara menyeluruh', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['ATLM'] = {
    'PRATAMA': [
        ('Pengambilan spesimen darah (vena, kapiler, arteri) dan penyiapan sampel laboratorium', 'S'),
    ],
    'MADYA': [
        ('Pengoperasian instrumen analisis hematologi, kimia klinik, dan mikrobiologi otomatis/manual', 'M'),
        ('Pemelihapan kontrol kualitas internal (QC) laboratorium harian', 'M'),
        ('Validasi teknis hasil pemeriksaan laboratorium sebelum diverifikasi oleh dokter spesialis Patologi Klinik', 'M'),
    ],
}
KATALOG_NAKES_TAMBAHAN['K3RS'] = {
    'PRATAMA': [
        ('Inspeksi harian alat pelindung diri (APD) dan potensi bahaya area kerja rumah sakit', 'M'),
        ('Pencatatan insiden kecelakaan kerja atau nyaris cedera (near miss)', 'M'),
    ],
    'MADYA': [
        ('Perencanaan dan evaluasi manajemen tanggap darurat bencana internal rumah sakit (Hospital Disaster Plan)', 'M'),
        ('Investigasi kecelakaan kerja dan audit keselamatan lingkungan kerja (K3RS)', 'M'),
        ('Pelaksanaan program mitigasi risiko bahaya kebakaran, paparan B3, dan ergonomi tenaga kesehatan', 'M'),
    ],
}
