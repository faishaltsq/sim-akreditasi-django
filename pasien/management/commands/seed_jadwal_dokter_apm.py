from django.core.management.base import BaseCommand
from datetime import time
from pasien.models import JadwalDokterPoli

class Command(BaseCommand):
    help = 'Seeding Jadwal Dokter Poliklinik untuk Anjungan Pendaftaran Mandiri (APM)'

    def handle(self, *args, **options):
        jadwal_data = [
            {
                'nama_dokter': 'dr. Faisal, Sp.JP',
                'gelar': 'Spesialis Jantung & Pembuluh Darah',
                'poliklinik': 'POLI_JANTUNG',
                'hari_praktik': 'Senin - Jumat',
                'jam_mulai': time(8, 0),
                'jam_selesai': time(12, 0),
                'kuota_maksimal': 25,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Pemeriksaan EKG, Ekokardiografi, Treadmill Test'
            },
            {
                'nama_dokter': 'dr. Bambang, Sp.JP, FIHA',
                'gelar': 'Spesialis Jantung & Pembuluh Darah Konsultan',
                'poliklinik': 'POLI_JANTUNG',
                'hari_praktik': 'Selasa, Kamis, Sabtu',
                'jam_mulai': time(13, 0),
                'jam_selesai': time(16, 30),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1537368910025-700350fe46c7?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Konsultasi Intervensi Vaskular & Kateterisasi'
            },
            {
                'nama_dokter': 'dr. Indah, Sp.P',
                'gelar': 'Spesialis Paru & Kedokteran Respirasi',
                'poliklinik': 'POLI_PARU',
                'hari_praktik': 'Senin - Kamis',
                'jam_mulai': time(8, 30),
                'jam_selesai': time(12, 30),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1594824813576-630230f6eb16?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Pemeriksaan Spirometri & Tes Fungsi Paru'
            },
            {
                'nama_dokter': 'dr. Budi Santoso, Sp.PD',
                'gelar': 'Spesialis Penyakit Dalam',
                'poliklinik': 'POLI_PENYAKIT_DALAM',
                'hari_praktik': 'Senin - Jumat',
                'jam_mulai': time(8, 0),
                'jam_selesai': time(13, 0),
                'kuota_maksimal': 30,
                'durasi_per_pasien_menit': 12,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Layanan Diabetes, Hipertensi, dan Geriatri'
            },
            {
                'nama_dokter': 'dr. Siti Rahma, Sp.PD-KGEH',
                'gelar': 'Spesialis Penyakit Dalam Konsultan Gastroentero-Hepatologi',
                'poliklinik': 'POLI_PENYAKIT_DALAM',
                'hari_praktik': 'Rabu, Jumat',
                'jam_mulai': time(13, 0),
                'jam_selesai': time(16, 0),
                'kuota_maksimal': 15,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Pemeriksaan Endoskopi Saluran Cerna'
            },
            {
                'nama_dokter': 'dr. Nurul, Sp.A',
                'gelar': 'Spesialis Anak (Pediatri)',
                'poliklinik': 'POLI_ANAK',
                'hari_praktik': 'Senin - Sabtu',
                'jam_mulai': time(8, 0),
                'jam_selesai': time(12, 0),
                'kuota_maksimal': 25,
                'durasi_per_pasien_menit': 12,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Imunisasi, Tumbuh Kembang, dan Infeksi Anak'
            },
            {
                'nama_dokter': 'dr. Hendra, Sp.B',
                'gelar': 'Spesialis Bedah Umum',
                'poliklinik': 'POLI_BEDAH',
                'hari_praktik': 'Senin, Rabu, Jumat',
                'jam_mulai': time(9, 0),
                'jam_selesai': time(13, 0),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1612349317150-e413f6a5b16d?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Bedah Minor, Perawatan Luka, Konsultasi Bedah'
            },
            {
                'nama_dokter': 'dr. Rina Marlina, Sp.OG',
                'gelar': 'Spesialis Kebidanan & Kandungan',
                'poliklinik': 'POLI_OBGYN',
                'hari_praktik': 'Senin - Jumat',
                'jam_mulai': time(8, 0),
                'jam_selesai': time(12, 30),
                'kuota_maksimal': 25,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1594824813637-a5796c3fd024?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Pemeriksaan USG 4D Kehamilan & Program Hamil'
            },
            {
                'nama_dokter': 'dr. Denny Setiawan, Sp.M',
                'gelar': 'Spesialis Mata',
                'poliklinik': 'POLI_MATA',
                'hari_praktik': 'Selasa - Sabtu',
                'jam_mulai': time(9, 0),
                'jam_selesai': time(12, 0),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 12,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1582750433449-648ed127bb54?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Pemeriksaan Visus, Katarak, Glaukoma'
            },
            {
                'nama_dokter': 'dr. Farhan Malik, Sp.S',
                'gelar': 'Spesialis Neurologi (Saraf)',
                'poliklinik': 'POLI_SARAF',
                'hari_praktik': 'Senin - Kamis',
                'jam_mulai': time(8, 30),
                'jam_selesai': time(12, 0),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1622253694242-abdfa0139b4b?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Pemeriksaan Stroke, Nyeri Kepala, Saraf Kejepit'
            },
            {
                'nama_dokter': 'dr. Nadia Utami, Sp.THT-KL',
                'gelar': 'Spesialis THT-KL',
                'poliklinik': 'POLI_THT',
                'hari_praktik': 'Senin, Rabu, Jumat',
                'jam_mulai': time(9, 0),
                'jam_selesai': time(12, 0),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 12,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1559839734-2b71ea197ec2?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Endoskopi THT, Audiometri, Pembersihan Serumen'
            },
            {
                'nama_dokter': 'drg. Citra Dewi, Sp.KG',
                'gelar': 'Spesialis Konservasi Gigi',
                'poliklinik': 'POLI_GIGI',
                'hari_praktik': 'Senin - Jumat',
                'jam_mulai': time(8, 0),
                'jam_selesai': time(13, 0),
                'kuota_maksimal': 18,
                'durasi_per_pasien_menit': 20,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Penambalan Estetik, Perawatan Saluran Akar'
            },
            {
                'nama_dokter': 'dr. Rahmat Hidayat, Sp.OT',
                'gelar': 'Spesialis Orthopedi & Traumatologi',
                'poliklinik': 'POLI_ORTHO',
                'hari_praktik': 'Selasa, Kamis',
                'jam_mulai': time(10, 0),
                'jam_selesai': time(14, 0),
                'kuota_maksimal': 20,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1622253692010-333f2da6031d?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Patah Tulang, Sendi, dan Cedera Olahraga'
            },
            {
                'nama_dokter': 'dr. Maya Safitri, Sp.KK',
                'gelar': 'Spesialis Dermatologi & Venereologi',
                'poliklinik': 'POLI_KULIT',
                'hari_praktik': 'Senin, Rabu',
                'jam_mulai': time(8, 30),
                'jam_selesai': time(12, 0),
                'kuota_maksimal': 18,
                'durasi_per_pasien_menit': 15,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1594824813576-630230f6eb16?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Kesehatan Kulit, Alergi, Terapi Laser'
            },
            {
                'nama_dokter': 'dr. Gunawan, Sp.KJ',
                'gelar': 'Spesialis Kedokteran Jiwa (Psikiatri)',
                'poliklinik': 'POLI_JIWA',
                'hari_praktik': 'Selasa, Kamis, Sabtu',
                'jam_mulai': time(9, 0),
                'jam_selesai': time(12, 30),
                'kuota_maksimal': 15,
                'durasi_per_pasien_menit': 20,
                'status_ketersediaan': 'BUKA',
                'foto_url': 'https://images.unsplash.com/photo-1537368910025-700350fe46c7?w=300&auto=format&fit=crop&q=80',
                'keterangan': 'Konseling Psikologis, Gangguan Kecemasan, Depresi'
            }
        ]

        count = 0
        for data in jadwal_data:
            obj, created = JadwalDokterPoli.objects.update_or_create(
                nama_dokter=data['nama_dokter'],
                poliklinik=data['poliklinik'],
                defaults=data
            )
            count += 1
            action = 'Dibuat' if created else 'Diperbarui'
            self.stdout.write(self.style.SUCCESS(f"[{action}] {obj.nama_dokter} - {obj.get_poliklinik_display()}"))

        self.stdout.write(self.style.SUCCESS(f"Total {count} jadwal dokter berhasil disinkronisasi."))
