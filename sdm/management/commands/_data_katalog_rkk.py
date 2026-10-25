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
    'DOKTER_GIGI': ('Dokter Gigi', 'MEDIS'),
    'APOTEKER': ('Apoteker', 'NAKES_LAIN'),
}

# Fisikawan Medis & Ahli K3RS: spec gives no per-action status -> seed 'S'.
DEFAULT_STATUS_UNSET = 'S'
CATATAN_STATUS_BAKU = 'Status baku belum ditetapkan; tinjau komite.'

PROFESI = {
    # ── NAKES_LAIN ──────────────────────────────────────────────────────
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
