"""Seed master ketenagaan ARIMA: medis, keperawatan, nakes lain, dan non-medis.

Sumber data medis: ``Master_Staf_Medis_ARIMA.xlsx`` (5 kategori x 5 nama).
Rumpun lain mengikuti dokumen *Modul Pola Ketenagaan Komprehensif*: keperawatan
& kebidanan, tenaga kesehatan lainnya, serta tenaga non-medis/penunjang.

Perintah ini idempoten (dicocokkan lewat ``nama_lengkap``), sehingga aman
dijalankan berulang. Opsi:

* ``--user``            username pelaku penerbitan SPK (default: superuser pertama)
* ``--skip-kredensial`` lewati pengajuan kredensial + SPK
* ``--skip-izin``       lewati pembuatan STR/SIP pada master izin profesi
* ``--demo-formasi``    buat JKE, rencana formasi, dan hasil formasi per rumpun
                        agar tabel gap dasbor punya isi (data demo)

Pembuatan SPK memerlukan akun pelaku (``issued_by``/``decided_by`` wajib).
Bila tidak ada pengguna yang cocok, bagian kredensial dilewati dengan peringatan
alih-alih membuat jejak audit palsu.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from akreditasi.models import UnitKerja
from sdm.models import (
    AktivitasBebanKerja,
    HasilFormasi,
    IzinProfesiPegawai,
    JamKerjaEfektif,
    KeputusanKredensial,
    MasterProfesiPegawai,
    Pegawai,
    PengajuanKredensial,
    PenempatanPegawai,
    PenugasanKlinis,
    RencanaFormasi,
    RiwayatKepegawaian,
)

# (kode, nama profesi, keluarga, kode unit, klinis, wajib STR/SIP)
PROFESI_SEED = [
    # ── Tenaga medis ──
    ('DR_UMUM', 'Dokter Umum', 'MEDIS', 'IRJ', True, True),
    ('SP_JP', 'Dokter Spesialis Jantung dan Pembuluh Darah', 'MEDIS', 'ICCU', True, True),
    ('SP_PD', 'Dokter Spesialis Penyakit Dalam', 'MEDIS', 'KSM-PD', True, True),
    ('SP_B', 'Dokter Spesialis Bedah', 'MEDIS', 'KSM-BEDAH', True, True),
    ('SUB_SP', 'Sub Spesialis', 'MEDIS', 'KSM-LAINNYA', True, True),
    # ── Keperawatan & kebidanan ──
    ('PERAWAT_PELAKSANA', 'Perawat Pelaksana', 'KEPERAWATAN_KEBIDANAN',
     'BANGSAL-DEWASA', True, True),
    ('PERAWAT_ICU', 'Perawat Intensif', 'KEPERAWATAN_KEBIDANAN', 'ICU', True, True),
    ('BIDAN', 'Bidan', 'KEPERAWATAN_KEBIDANAN', 'BANGSAL-OBGYN', True, True),
    # ── Tenaga kesehatan lainnya ──
    ('APOTEKER', 'Apoteker', 'NAKES_LAIN', 'FARM', True, True),
    ('TTK', 'Tenaga Teknis Kefarmasian', 'NAKES_LAIN', 'DEPO-RAJAL', True, True),
    ('RADIOGRAFER', 'Radiografer', 'NAKES_LAIN', 'RAD-IMAGING', True, True),
    ('ATLM', 'Ahli Teknologi Laboratorium Medik', 'NAKES_LAIN', 'LAB-BDRS', True, True),
    ('FISIOTERAPIS', 'Fisioterapis', 'NAKES_LAIN', 'IRJ', True, True),
    ('NUTRISIONIS', 'Nutrisionis', 'NAKES_LAIN', 'GIZI-DIETETIK', True, True),
    ('PMIK', 'Perekam Medis & Informasi Kesehatan', 'NAKES_LAIN', 'REKAM-MEDIS', True, True),
    ('SANITARIAN', 'Sanitarian', 'NAKES_LAIN', 'BAG-FASILITAS', True, True),
    ('ELEKTROMEDIS', 'Elektromedis', 'NAKES_LAIN', 'IPSRS-SARANA', True, True),
    # ── Tenaga non-medis / penunjang ──
    ('STAF_KEUANGAN', 'Staf Akuntansi & Klaim', 'NON_KLINIS', 'DIR-KEU', False, False),
    ('KASIR', 'Kasir & Pendaftaran', 'NON_KLINIS', 'ADMISI', False, False),
    ('STAF_IT', 'Programmer / IT Support', 'NON_KLINIS', 'DIR-KEU', False, False),
    ('TEKNISI_IPSRS', 'Teknisi Listrik & Sipil', 'NON_KLINIS', 'IPSRS-SARANA', False, False),
    ('STAF_HRD', 'Staf SDM & Diklat', 'NON_KLINIS', 'BAG-SDM', False, False),
    ('PRAMUSAJI', 'Pramusaji & Juru Masak', 'NON_KLINIS', 'DAPUR-UTAMA', False, False),
    ('SATPAM', 'Petugas Keamanan', 'NON_KLINIS', 'BAG-FASILITAS', False, False),
    ('CLEANING', 'Petugas Kebersihan', 'NON_KLINIS', 'CSSD-LAUNDRY', False, False),
    ('DRIVER', 'Driver Ambulans', 'NON_KLINIS', 'IGD', False, False),
]

# (kode profesi, nama lengkap, status kepegawaian, status kredensial, TMT)
STAF_SEED = [
    # ── Medis (25) ──
    ('DR_UMUM', 'dr. Aditya Pratama Wijaya', 'TETAP', 'AKTIF', date(2021, 1, 12)),
    ('DR_UMUM', 'dr. Nabila Putri Kusuma', 'TETAP', 'AKTIF', date(2022, 5, 3)),
    ('DR_UMUM', 'dr. Reza Mahendra Saputra', 'PKWT', 'PROSES', date(2023, 8, 15)),
    ('DR_UMUM', 'dr. Larasati Dewi Anggraini', 'TETAP', 'AKTIF', date(2020, 2, 10)),
    ('DR_UMUM', 'dr. Farhan Hakim Nugroho', 'PKWT', 'BARU', date(2026, 9, 1)),
    ('SP_JP', 'dr. Hendra Gunawan, Sp.JP(K)', 'MITRA', 'AKTIF', date(2019, 3, 14)),
    ('SP_JP', 'dr. Ratna Sari Dewi, Sp.JP', 'TETAP', 'AKTIF', date(2021, 7, 20)),
    ('SP_JP', 'dr. Bima Sakti Perdana, Sp.JP', 'MITRA', 'AKTIF', date(2022, 11, 5)),
    ('SP_JP', 'dr. Cynthia Maharani, Sp.JP', 'LEPAS', 'PROSES', date(2023, 4, 18)),
    ('SP_JP', 'dr. Dimas Arya Ramadhan, Sp.JP', 'MITRA', 'BARU', date(2026, 8, 10)),
    ('SP_PD', 'dr. Bambang Sutrisno, Sp.PD', 'TETAP', 'AKTIF', date(2018, 2, 2)),
    ('SP_PD', 'dr. Maya Kartika Sari, Sp.PD', 'TETAP', 'AKTIF', date(2020, 6, 19)),
    ('SP_PD', 'dr. Irfan Maulana Yusuf, Sp.PD', 'MITRA', 'AKTIF', date(2021, 9, 11)),
    ('SP_PD', 'dr. Dian Puspita Ningrum, Sp.PD', 'MITRA', 'PROSES', date(2023, 1, 22)),
    ('SP_PD', 'dr. Galih Prakoso Wibowo, Sp.PD', 'PKWT', 'AKTIF', date(2024, 5, 14)),
    ('SP_B', 'dr. Agung Nugroho Santoso, Sp.B', 'TETAP', 'AKTIF', date(2017, 4, 8)),
    ('SP_B', 'dr. Rina Melati Putri, Sp.B', 'MITRA', 'AKTIF', date(2020, 8, 25)),
    ('SP_B', 'dr. Taufik Hidayatullah, Sp.B', 'TETAP', 'AKTIF', date(2021, 10, 12)),
    ('SP_B', 'dr. Eko Prasetyo Utomo, Sp.B', 'MITRA', 'PROSES', date(2023, 3, 3)),
    ('SP_B', 'dr. Fajar Siddiq Alamsyah, Sp.B', 'LEPAS', 'BARU', date(2026, 7, 15)),
    ('SUB_SP', 'Prof. dr. Suryo Hadiwijoyo, Sp.PD-KGEH', 'MITRA', 'AKTIF', date(2016, 1, 10)),
    ('SUB_SP', 'dr. Kartika Candra Kirana, Sp.B(K)Onk', 'MITRA', 'AKTIF', date(2019, 5, 17)),
    ('SUB_SP', 'dr. Wahyu Setiawan, Sp.JP(K)FIHA', 'LEPAS', 'AKTIF', date(2021, 9, 21)),
    ('SUB_SP', 'dr. Novianti Rahmawati, Sp.PD-KHOM', 'MITRA', 'AKTIF', date(2022, 2, 9)),
    ('SUB_SP', 'dr. Darmawan Kusuma, Sp.B-KBD', 'MITRA', 'PROSES', date(2023, 6, 14)),
    # ── Keperawatan & kebidanan (9) ──
    ('PERAWAT_PELAKSANA', 'Ns. Anisa Rahmawati, S.Kep', 'TETAP', 'AKTIF', date(2019, 2, 4)),
    ('PERAWAT_PELAKSANA', 'Ns. Bagus Setiawan, S.Kep', 'TETAP', 'AKTIF', date(2020, 7, 13)),
    ('PERAWAT_PELAKSANA', 'Ns. Citra Ayu Lestari, S.Kep', 'PKWT', 'PROSES', date(2024, 1, 8)),
    ('PERAWAT_ICU', 'Ns. Dwi Handoko, S.Kep', 'TETAP', 'AKTIF', date(2018, 9, 3)),
    ('PERAWAT_ICU', 'Ns. Endah Puspitasari, S.Kep', 'TETAP', 'AKTIF', date(2021, 4, 19)),
    ('PERAWAT_PELAKSANA', 'Ns. Indra Kusuma, S.Kep', 'MITRA', 'AKTIF', date(2023, 11, 6)),
    ('BIDAN', 'Bd. Fitri Nurhaliza, S.Tr.Keb', 'TETAP', 'AKTIF', date(2020, 3, 2)),
    ('BIDAN', 'Bd. Gita Permata Sari, S.Tr.Keb', 'PKWT', 'AKTIF', date(2022, 8, 22)),
    ('BIDAN', 'Bd. Hana Maulidya, A.Md.Keb', 'PKWT', 'BARU', date(2026, 6, 1)),
    # ── Nakes lain (12) ──
    ('APOTEKER', 'apt. Joko Susilo, S.Farm', 'TETAP', 'AKTIF', date(2019, 6, 10)),
    ('APOTEKER', 'apt. Kartika Dewi, S.Farm', 'TETAP', 'AKTIF', date(2021, 2, 15)),
    ('TTK', 'Lestari Wulandari, A.Md.Farm', 'PKWT', 'AKTIF', date(2022, 10, 3)),
    ('RADIOGRAFER', 'Muhammad Rizki, A.Md.Rad', 'TETAP', 'AKTIF', date(2020, 1, 20)),
    ('ATLM', 'Nurul Aini, A.Md.AK', 'TETAP', 'AKTIF', date(2019, 8, 12)),
    ('ATLM', 'Oscar Pratama, A.Md.AK', 'PKWT', 'PROSES', date(2024, 3, 4)),
    ('FISIOTERAPIS', 'Putri Ramadhani, S.Ft', 'TETAP', 'AKTIF', date(2021, 5, 17)),
    ('NUTRISIONIS', 'Qori Amalia, S.Gz', 'TETAP', 'AKTIF', date(2020, 9, 7)),
    ('PMIK', 'Rudi Hartono, A.Md.RMIK', 'TETAP', 'AKTIF', date(2018, 4, 2)),
    ('PMIK', 'Sinta Maharani, A.Md.RMIK', 'PKWT', 'AKTIF', date(2023, 7, 10)),
    ('SANITARIAN', 'Teguh Wicaksono, S.KM', 'TETAP', 'AKTIF', date(2021, 11, 1)),
    ('ELEKTROMEDIS', 'Umar Faruq, A.Md.TEM', 'TETAP', 'AKTIF', date(2022, 2, 21)),
    # ── Non-medis / penunjang (14) ──
    ('STAF_KEUANGAN', 'Vina Oktaviani, S.E', 'TETAP', 'AKTIF', date(2019, 1, 7)),
    ('STAF_KEUANGAN', 'Wahyu Saputra, S.Ak', 'TETAP', 'AKTIF', date(2021, 6, 14)),
    ('KASIR', 'Yuni Astuti', 'PKWT', 'AKTIF', date(2023, 2, 6)),
    ('STAF_IT', 'Zaki Firmansyah, S.Kom', 'TETAP', 'AKTIF', date(2020, 10, 5)),
    ('STAF_IT', 'Agus Setiono, A.Md.Kom', 'PKWT', 'PROSES', date(2025, 1, 13)),
    ('TEKNISI_IPSRS', 'Bambang Iryanto, S.T', 'TETAP', 'AKTIF', date(2018, 7, 9)),
    ('TEKNISI_IPSRS', 'Cahyo Nugroho', 'PKWT', 'AKTIF', date(2022, 5, 16)),
    ('STAF_HRD', 'Dewi Anggraeni, S.Psi', 'TETAP', 'AKTIF', date(2020, 4, 6)),
    ('PRAMUSAJI', 'Eko Yulianto', 'PKWT', 'AKTIF', date(2023, 9, 11)),
    ('PRAMUSAJI', 'Fajar Ramadhan', 'PKWT', 'AKTIF', date(2024, 2, 19)),
    ('SATPAM', 'Gunawan Prasetyo', 'LEPAS', 'AKTIF', date(2022, 1, 3)),
    ('SATPAM', 'Hendro Wijaya', 'LEPAS', 'AKTIF', date(2022, 1, 3)),
    ('CLEANING', 'Iis Suryani', 'LEPAS', 'AKTIF', date(2023, 3, 6)),
    ('DRIVER', 'Junaedi Saputra', 'PKWT', 'AKTIF', date(2021, 8, 2)),
]

# Rencana formasi demo per rumpun: (profesi, volume, standar menit, aktivitas)
# Volume dipilih agar hasil kalkulasi memperlihatkan campuran status kecukupan —
# defisit kritis, defisit ringan, dan surplus — sehingga tombol eskalasi punya
# baris untuk diuji dan tabel tidak hanya berisi satu warna.
FORMASI_SEED = [
    ('Dokter Umum', 60000, 15, 'Kunjungan rawat jalan dokter umum'),
    ('Perawat Pelaksana', 26000, 45, 'Asuhan keperawatan rawat inap'),
    ('Apoteker', 20000, 12, 'Telaah resep dan dispensing'),
    ('Staf Akuntansi & Klaim', 10000, 20, 'Verifikasi klaim JKN'),
]


class Command(BaseCommand):
    help = 'Seed staf medis, keperawatan, nakes lain, dan non-medis ARIMA.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user', default='',
            help='Username pelaku penerbitan SPK (default: superuser pertama).',
        )
        parser.add_argument(
            '--skip-kredensial', action='store_true',
            help='Lewati pembuatan pengajuan kredensial dan SPK.',
        )
        parser.add_argument(
            '--skip-izin', action='store_true',
            help='Lewati pembuatan STR/SIP pada master izin profesi.',
        )
        parser.add_argument(
            '--demo-formasi', action='store_true',
            help='Buat JKE + rencana/hasil formasi demo per rumpun.',
        )

    def handle(self, *args, **options):
        aktor = self._resolve_actor(options['user'])
        if aktor is None and not options['skip_kredensial']:
            self.stdout.write(self.style.WARNING(
                'Tidak ada akun pelaku; pembuatan SPK dilewati. '
                'Jalankan ulang dengan --user <username> bila akun tersedia.'
            ))

        with transaction.atomic():
            self._seed_profesi()
            dibuat = self._seed_pegawai(
                aktor,
                lewati_kredensial=options['skip_kredensial'] or aktor is None,
                lewati_izin=options['skip_izin'],
            )
            formasi = self._seed_formasi(aktor) if options['demo_formasi'] else 0

        pesan = f'Selesai. {dibuat} pegawai baru dibuat, sisanya sudah ada.'
        if options['demo_formasi']:
            pesan += f' {formasi} rencana formasi demo dibuat.'
        self.stdout.write(self.style.SUCCESS(pesan))

    # ── helpers ────────────────────────────────────────────────────────────

    def _resolve_actor(self, username):
        User = get_user_model()
        if username:
            return User.objects.filter(username=username).first()
        return User.objects.filter(is_superuser=True, is_active=True).order_by('pk').first()

    def _seed_profesi(self):
        for kode, nama, keluarga, _unit, _klinis, _str in PROFESI_SEED:
            _, created = MasterProfesiPegawai.objects.get_or_create(
                code=kode, defaults={'nama': nama, 'keluarga': keluarga},
            )
            if created:
                self.stdout.write(f'  + profesi {kode} — {nama}')

    def _unit(self, kode):
        return UnitKerja.objects.filter(code=kode).first()

    def _seed_pegawai(self, aktor, *, lewati_kredensial, lewati_izin):
        profesi_map = {
            p[0]: MasterProfesiPegawai.objects.get(code=p[0]) for p in PROFESI_SEED
        }
        unit_per_profesi = {p[0]: p[3] for p in PROFESI_SEED}
        klinis_map = {p[0]: p[4] for p in PROFESI_SEED}
        str_map = {p[0]: p[5] for p in PROFESI_SEED}

        dibuat = 0
        for kode_profesi, nama, kategori_kerja, status_kredensial, tmt in STAF_SEED:
            profesi = profesi_map[kode_profesi]
            unit = self._unit(unit_per_profesi[kode_profesi])
            klinis = klinis_map[kode_profesi]

            pegawai, created = Pegawai.objects.get_or_create(
                nama_lengkap=nama,
                defaults={
                    'kategori': 'PPA' if klinis else 'NON_PPA',
                    'profesi': profesi.nama,
                    'profesi_master': profesi,
                    'status': 'AKTIF',
                    'data_origin': 'DEMO',
                    'jabatan': profesi.nama,
                },
            )
            if created:
                dibuat += 1
                self.stdout.write(f'  + pegawai {nama}')

            self._seed_riwayat(pegawai, kategori_kerja, tmt)
            self._seed_penempatan(pegawai, unit, tmt)
            if not lewati_izin:
                self._seed_izin(
                    pegawai, profesi, unit, tmt, wajib_str=str_map[kode_profesi],
                )
            if not lewati_kredensial and klinis:
                self._seed_kredensial(
                    pegawai, profesi, unit, status_kredensial, tmt, aktor,
                )
        return dibuat

    def _seed_riwayat(self, pegawai, kategori_kerja, tmt):
        RiwayatKepegawaian.objects.get_or_create(
            pegawai=pegawai, kategori_pegawai=kategori_kerja, tanggal_tmt=tmt,
        )

    def _seed_penempatan(self, pegawai, unit, tmt):
        if unit is None:
            return
        PenempatanPegawai.objects.get_or_create(
            pegawai=pegawai, unit_kerja=unit, tanggal_mulai=tmt,
            defaults={'alokasi_fte': '1.00'},
        )

    def _seed_izin(self, pegawai, profesi, unit, tmt, *, wajib_str):
        """STR (seumur hidup) + SIP aktif (3 tahun) untuk tenaga klinis.

        Nomor izin deterministik dari PK pegawai supaya seed ulang tidak
        menumpuk nomor berbeda untuk orang yang sama.

        Masa berlaku SIP dihitung dari tahun berjalan, bukan dari TMT: izin
        yang diterbitkan saat seseorang pertama masuk akan sudah kedaluwarsa
        untuk staf senior, dan itu membuat seluruh badge legalitas jadwal
        berwarna kuning karena alasan yang salah.
        """
        if not wajib_str:
            return
        kode_unit = unit.code if unit is not None else 'RS'
        sufiks = pegawai.pk.hex[:8].upper()
        hari_ini = date.today()
        terbit = date(hari_ini.year - 1, tmt.month, min(tmt.day, 28))
        berakhir = date(terbit.year + 3, terbit.month, min(terbit.day, 28))

        IzinProfesiPegawai.objects.update_or_create(
            pegawai=pegawai, subtype='STR', nomor_izin=f'STR/{sufiks}',
            defaults={
                'pemberi_izin': 'Konsil Tenaga Kesehatan Indonesia',
                'profesi': profesi.nama,
                'validity_mode': 'LIFETIME',
                'tanggal_terbit': tmt,
                'is_local_rs': False,
            },
        )
        IzinProfesiPegawai.objects.update_or_create(
            pegawai=pegawai, subtype='SIP', nomor_izin=f'SIP/{kode_unit}/{sufiks}',
            defaults={
                'pemberi_izin': 'Dinas Kesehatan Kabupaten/Kota',
                'profesi': profesi.nama,
                'validity_mode': 'DATED',
                'tanggal_terbit': terbit,
                'tanggal_berakhir': berakhir,
                'organisasi_praktik': 'Rumah Sakit',
                'lokasi_praktik': unit.name if unit is not None else '',
                'is_local_rs': True,
            },
        )

    def _seed_kredensial(self, pegawai, profesi, unit, status_kredensial, tmt, aktor):
        """Bentuk pengajuan kredensial; terbitkan SPK hanya untuk status AKTIF.

        Pengajuan yang sudah ada tetap dipakai, dan SPK diperbarui (bukan
        dilewati) supaya seed ulang bisa memperbaiki masa berlaku yang sudah
        terlanjur kedaluwarsa.
        """
        if unit is None:
            return
        jenis = 'REKREDENSIAL' if status_kredensial == 'PROSES' else 'AWAL'
        pengajuan, _ = PengajuanKredensial.objects.get_or_create(
            employee=pegawai,
            unit_kerja=unit,
            jenis=jenis,
            defaults={
                'spesialisasi_teks': profesi.nama,
                'status': 'DISETUJUI' if status_kredensial == 'AKTIF' else 'DIAJUKAN',
                'submitted_by': aktor,
            },
        )
        if status_kredensial != 'AKTIF':
            return
        if pengajuan.status != 'DISETUJUI':
            pengajuan.status = 'DISETUJUI'
            pengajuan.save(update_fields=['status', 'updated_at'])

        keputusan, _ = KeputusanKredensial.objects.get_or_create(
            pengajuan=pengajuan,
            defaults={
                'outcome': 'DISETUJUI',
                'decided_by': aktor,
                'notes': 'Seed data demo — kredensial aktif.',
            },
        )
        # Masa berlaku SPK dihitung dari tahun berjalan (3 tahun ke depan), bukan
        # dari TMT: SPK yang berakhir 3 tahun setelah staf masuk sudah kedaluwarsa
        # untuk staf senior dan membuat validasi jadwal memblokir orang yang
        # sebenarnya aktif.
        hari_ini = date.today()
        berlaku_sampai = date(hari_ini.year + 2, hari_ini.month, min(hari_ini.day, 28))
        PenugasanKlinis.objects.update_or_create(
            employee=pegawai,
            versi=1,
            defaults={
                'unit_kerja': unit,
                'decision': keputusan,
                'nomor_spk': f'SPK/{unit.code}/{pegawai.pk.hex[:8].upper()}',
                'berlaku_mulai': tmt,
                'berlaku_sampai': berlaku_sampai,
                'is_active': True,
                'issued_by': aktor,
            },
        )

    def _reset_demo_formasi(self):
        """Hapus rencana formasi demo sebelumnya agar angka bisa dihitung ulang.

        ``HasilFormasi`` melindungi dirinya dari update/hapus lewat instance
        method, jadi baris hasil dihapus lewat queryset lebih dulu — kalau tidak,
        FK PROTECT akan menahan penghapusan rencananya.
        """
        demo = RencanaFormasi.objects.filter(
            alasan_catatan__startswith='Seed demo'
        )
        if not demo.exists():
            return
        HasilFormasi.objects.filter(rencana__in=demo).delete()
        demo.delete()

    def _seed_formasi(self, aktor):
        """Buat JKE + rencana formasi + hasil formasi demo per rumpun."""
        from sdm.models.formasi import calculate_formasi

        self._reset_demo_formasi()

        tahun = date.today().year
        jke, _ = JamKerjaEfektif.objects.get_or_create(
            tahun=tahun, versi=1,
            defaults={
                'hari_kerja': 312, 'cuti_tahunan': 12, 'hari_sakit_rata2': 5,
                'libur_nasional': 15, 'jam_pelatihan': 8,
                'jam_kerja_per_hari': 7,
                'sumber': 'Seed demo pola ketenagaan',
            },
        )
        if not jke.is_approved and aktor is not None:
            jke.approve(by=aktor)

        dibuat = 0
        kode_by_nama = {p[1]: p[0] for p in PROFESI_SEED}
        for profesi_nama, volume, menit, nama_aktivitas in FORMASI_SEED:
            kode_profesi = kode_by_nama.get(profesi_nama)
            profesi = (
                MasterProfesiPegawai.objects.filter(code=kode_profesi).first()
                if kode_profesi else None
            )
            if profesi is None:
                continue
            # Unit mengikuti pemetaan profesi di PROFESI_SEED; jatuh ke penempatan
            # pertama hanya bila unit yang dimaksud tidak ada di basis data.
            kode_unit = next(
                (p[3] for p in PROFESI_SEED if p[0] == kode_profesi), None,
            )
            unit = self._unit(kode_unit) if kode_unit else None
            if unit is None:
                penempatan = PenempatanPegawai.objects.filter(
                    pegawai__profesi_master=profesi,
                ).select_related('unit_kerja').first()
                unit = penempatan.unit_kerja if penempatan else None
            if unit is None:
                continue

            if RencanaFormasi.objects.filter(
                unit_kerja=unit, profesi=profesi_nama, periode_mulai__year=tahun,
            ).exists():
                continue

            rencana = RencanaFormasi.objects.create(
                unit_kerja=unit,
                profesi=profesi_nama,
                periode_mulai=date(tahun, 1, 1),
                periode_selesai=date(tahun, 12, 31),
                effective_minutes_per_employee=jke.menit_efektif_per_tahun,
                jam_kerja_efektif=jke,
                status='APPROVED',
                alasan='DEFISIT_FTE',
                alasan_catatan='Seed demo: hasil perhitungan beban kerja periode berjalan.',
                approved_by=aktor,
                created_by=aktor,
            )
            AktivitasBebanKerja.objects.create(
                rencana=rencana, nama=nama_aktivitas,
                volume=volume, standard_minutes=menit,
            )
            hasil = calculate_formasi(rencana)
            HasilFormasi.objects.create(
                rencana=rencana,
                calculation_version=hasil['calculation_version'],
                required_fte=hasil['required_fte'],
                required_headcount=hasil['required_headcount'],
                actual_fte=hasil['actual_fte'],
                gap_fte=hasil['gap_fte'],
                sufficiency_pct=hasil['sufficiency_pct'],
                inputs_digest=hasil['inputs_digest'],
                status_risiko='DEFISIT_KRITIS' if hasil['gap_fte'] < -1 else 'MARGINAL',
                approved_by=aktor,
            )
            dibuat += 1
        return dibuat
