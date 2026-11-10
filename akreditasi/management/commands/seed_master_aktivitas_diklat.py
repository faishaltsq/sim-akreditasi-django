"""Seeder 13 Master Aktivitas Harian Unit Diklat (Non-Medis) ARIMA.

Berdasarkan spesifikasi dokumen 'logbook untuk unit Diklat.docx':
Mencakup seluruh siklus akademik: orientasi pegawai baru & nakes, penyusunan KAK/TOR,
rekapitulasi jam pelatihan (training hours), pelatihan eksternal, evaluasi pasca-diklat,
mandatory training, pengelolaan praktik mahasiswa & magang, fasilitasi penelitian &
ethical clearance, rapat pimpinan & koordinasi, serta digitalisasi arsip akreditasi.
"""

from django.core.management.base import BaseCommand
from akreditasi.logbook_nonmedis_models import MasterAktivitasNonMedis


KATALOG_DIKLAT = [
    {
        'kode': 'DIKLAT-01',
        'kategori_unit': 'DIKLAT',
        'nama': 'Pelaksanaan Orientasi Pegawai Baru & Peserta Didik',
        'deskripsi': (
            'Menyusun jadwal, materi, dan lembar evaluasi untuk orientasi umum '
            'rumah sakit serta orientasi khusus unit bagi staf baru, tenaga kontrak, '
            'dokter, perawat, maupun mahasiswa praktik/klinik.'
        ),
        'ep_rekomendasi': 'KPS 8 / TKRS 9',
        'standar_terkait': ['KPS 8', 'TKRS 9'],
        'urutan': 1,
    },
    {
        'kode': 'DIKLAT-02',
        'kategori_unit': 'DIKLAT',
        'nama': 'Penyusunan Program & KAK/TOR Pelatihan (IHT)',
        'deskripsi': (
            'Merancang Kerangka Acuan Kerja (KAK), proposal kegiatan, surat undangan, '
            'dan jadwal pelaksanaan In-House Training (IHT) berkoordinasi dengan '
            'bagian mutu atau unit terkait.'
        ),
        'ep_rekomendasi': 'KPS 8 / TKRS 9',
        'standar_terkait': ['KPS 8', 'TKRS 9'],
        'urutan': 2,
    },
    {
        'kode': 'DIKLAT-03',
        'kategori_unit': 'DIKLAT',
        'nama': 'Rekapitulasi Jam Pelatihan & Matriks Kompetensi',
        'deskripsi': (
            'Melakukan pendataan, rekapitulasi jumlah jam pelajaran (training hours) '
            'per pegawai, serta memperbarui matriks pemenuhan kompetensi staf '
            'tahun berjalan di SIM-RS.'
        ),
        'ep_rekomendasi': 'KPS 8.1 / TKRS 9',
        'standar_terkait': ['KPS 8.1', 'KPS 8', 'TKRS 9'],
        'urutan': 3,
    },
    {
        'kode': 'DIKLAT-04',
        'kategori_unit': 'DIKLAT',
        'nama': 'Pengelolaan Pelatihan Eksternal & Seminar Staf',
        'deskripsi': (
            'Memproses pengajuan izin, penjadwalan, verifikasi surat tugas, serta '
            'pengumpulan sertifikat pelatihan/seminar eksternal yang diikuti oleh pegawai.'
        ),
        'ep_rekomendasi': 'KPS 8 / KPS 8.1',
        'standar_terkait': ['KPS 8', 'KPS 8.1'],
        'urutan': 4,
    },
    {
        'kode': 'DIKLAT-05',
        'kategori_unit': 'DIKLAT',
        'nama': 'Evaluasi Pasca-Diklat & Analisis Efektivitas',
        'deskripsi': (
            'Mengumpulkan, merekap, dan menganalisis hasil pre-test, post-test, '
            'lembar umpan balik (feedback), serta laporan penerapan hasil pelatihan '
            'di unit kerja masing-masing.'
        ),
        'ep_rekomendasi': 'KPS 8.1',
        'standar_terkait': ['KPS 8.1', 'KPS 8'],
        'urutan': 5,
    },
    {
        'kode': 'DIKLAT-06',
        'kategori_unit': 'DIKLAT',
        'nama': 'Koordinasi Pelatihan Wajib (Mandatory Training)',
        'deskripsi': (
            'Mengoordinasikan penyelenggaraan pelatihan wajib rumah sakit secara berkala, '
            'seperti PPI (Pencegahan dan Pengendalian Infeksi), K3RS, BHD (Bantuan '
            'Hidup Dasar), dan Keselamatan Pasien.'
        ),
        'ep_rekomendasi': 'KPS 8 / SKP / PPI / MFK',
        'standar_terkait': ['KPS 8', 'SKP 1', 'PPI 11', 'MFK 11'],
        'urutan': 6,
    },
    {
        'kode': 'DIKLAT-07',
        'kategori_unit': 'DIKLAT',
        'nama': 'Pengelolaan Praktik Mahasiswa & Peserta Magang',
        'deskripsi': (
            'Mengoordinasikan penerimaan, penempatan unit pembimbing klinik/lapangan, '
            'pembuatan jadwal dinas, serta pemantauan kegiatan pembelajaran mahasiswa '
            '(keperawatan, bidan, ners, kesehatan masyarakat, dll.) atau peserta magang instansi.'
        ),
        'ep_rekomendasi': 'IPKP 1 / IPKP 2 / IPKP 3 / KPS 8',
        'standar_terkait': ['IPKP 1', 'IPKP 2', 'IPKP 3', 'KPS 8'],
        'urutan': 7,
    },
    {
        'kode': 'DIKLAT-08',
        'kategori_unit': 'DIKLAT',
        'nama': 'Fasilitasi Penelitian & Studi Kasus / Responden',
        'deskripsi': (
            'Memproses perizinan etik (ethical clearance), surat pengantar penelitian, '
            'koordinasi dengan kepala ruangan/instalasi, serta pemantauan pelaksanaan riset '
            'atau pengumpulan data oleh mahasiswa/peneliti luar di lingkungan rumah sakit.'
        ),
        'ep_rekomendasi': 'IPKP 3 / TKRS 9',
        'standar_terkait': ['IPKP 3', 'TKRS 9'],
        'urutan': 8,
    },
    {
        'kode': 'DIKLAT-09',
        'kategori_unit': 'DIKLAT',
        'nama': 'Rapat Bersama Pimpinan / Manajemen',
        'deskripsi': (
            'Menghadiri, melaporkan progress program diklat, serta mencatat arahan '
            'strategis, kebijakan, atau disposisi dari pimpinan rumah sakit/direksi.'
        ),
        'ep_rekomendasi': 'TKRS 9',
        'standar_terkait': ['TKRS 9'],
        'urutan': 9,
    },
    {
        'kode': 'DIKLAT-10',
        'kategori_unit': 'DIKLAT',
        'nama': 'Rapat Koordinasi Internal / Antar Unit',
        'deskripsi': (
            'Melaksanakan sinkronisasi jadwal, persiapan teknis program pelatihan, '
            'atau penyelesaian kendala operasional bersama unit kerja lain atau tim akreditasi.'
        ),
        'ep_rekomendasi': 'TKRS 9',
        'standar_terkait': ['TKRS 9'],
        'urutan': 10,
    },
    {
        'kode': 'DIKLAT-11',
        'kategori_unit': 'DIKLAT',
        'nama': 'Rapat Sosialisasi Kebijakan / Program / SOP Baru',
        'deskripsi': (
            'Memimpin atau mengikuti kegiatan diseminasi informasi, sosialisasi '
            'pedoman, panduan, atau regulasi baru terkait pendidikan dan pelatihan '
            'kepada seluruh staf rumah sakit.'
        ),
        'ep_rekomendasi': 'TKRS 9 / KPS 8',
        'standar_terkait': ['TKRS 9', 'KPS 8'],
        'urutan': 11,
    },
    {
        'kode': 'DIKLAT-12',
        'kategori_unit': 'DIKLAT',
        'nama': 'Rapat Kedinasan & Forum Lainnya (Workshop/FGD/Lokakarya)',
        'deskripsi': (
            'Mengikuti atau menyelenggarakan kegiatan forum ilmiah, Focus Group '
            'Discussion (FGD), lokakarya pengembangan kurikulum diklat, atau '
            'rapat instansional lainnya.'
        ),
        'ep_rekomendasi': 'KPS 8',
        'standar_terkait': ['KPS 8'],
        'urutan': 12,
    },
    {
        'kode': 'DIKLAT-13',
        'kategori_unit': 'DIKLAT',
        'nama': 'Pengelolaan Arsip & Dokumen Akreditasi Diklat',
        'deskripsi': (
            'Melakukan penataan, digitalisasi, dan verifikasi dokumen bukti dukung '
            'Standar Akreditasi (seperti EP KPS dan TKRS) ke dalam repository sistem ARIMA.'
        ),
        'ep_rekomendasi': 'KPS 8 / TKRS 9 / MRMIK',
        'standar_terkait': ['KPS 8', 'TKRS 9', 'MRMIK 1'],
        'urutan': 13,
    },
]


class Command(BaseCommand):
    help = 'Seeding 13 Master Aktivitas Harian Unit Diklat sesuai spesifikasi STARKES'

    def handle(self, *args, **options):
        total_created = 0
        total_updated = 0

        for item in KATALOG_DIKLAT:
            obj, created = MasterAktivitasNonMedis.objects.update_or_create(
                kode=item['kode'],
                defaults={
                    'kategori_unit': item['kategori_unit'],
                    'nama': item['nama'],
                    'deskripsi': item['deskripsi'],
                    'ep_rekomendasi': item['ep_rekomendasi'],
                    'standar_terkait': item['standar_terkait'],
                    'urutan': item['urutan'],
                    'is_active': True,
                }
            )
            if created:
                total_created += 1
            else:
                total_updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Selesai! 13 Master Aktivitas Diklat diproses: '
                f'{total_created} dibuat, {total_updated} diperbarui.'
            )
        )
