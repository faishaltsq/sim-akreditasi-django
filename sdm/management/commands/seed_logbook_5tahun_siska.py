"""Seed Buku Kinerja Elektronik (Logbook 5 Tahunan) untuk Siska Lestari.

Melengkapi seed 36 bulan dengan siklus 5 tahunan sesuai Peraturan Menteri
Kesehatan Nomor 13 Tahun 2025: entri logbook tersebar pada 5 tahun kalender
terakhir, lalu draf LOGBOOK_5TAHUN diisi 3 ranah (pelayanan, SKP, etik) dan
lembar penilaian Pasal 180.

Jalankan setelah `seed_logbook_36bulan_siska` supaya pegawai, akun, dan unit
sudah ada; command ini aman dijalankan berulang (idempoten).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    EntriLogbookKlinis,
    Pegawai,
    PenempatanPegawai,
)
from sdm.services.dokumen_kredensial import generate_draft


class Command(BaseCommand):
    help = (
        'Seed Buku Kinerja Elektronik (Logbook 5 Tahunan) PMK 13/2025 '
        'untuk perawat Siska Lestari'
    )

    # Tindakan klinis beserta sebaran volume per tahun kalender (T1..T5).
    # Total 5 tahun = 3.110 tindakan, konsisten dengan rekap portofolio.
    TINDAKAN = [
        ('Pengkajian & Triase Anak (Pediatric Assessment Triangle)', 80, 75, 5, 0),
        ('Pemberian Terapi Obat Oral & Injeksi (Anak/Bayi)', 250, 230, 15, 5),
        ('Pemasangan Infus / Akses Vaskuler Perifer pada Anak', 63, 58, 4, 1),
        ('Perhitungan Dosis Obat Pediatrik (Sesuai BB/BSA)', 104, 98, 5, 1),
        ('Manajemen Demam & Kompres Hangat Terpadu', 42, 41, 1, 0),
        ('Fisioterapi Dada & Suctioning pada Anak', 33, 30, 2, 1),
        ('Pemberian Nutrisi Enteral (Naso/Oro-Gastric Tube - NGT)', 22, 20, 1, 1),
        ('Edukasi Perawatan Anak Sakit untuk Orang Tua', 32, 31, 1, 0),
    ]

    def handle(self, *args, **options):
        today = timezone.localdate()
        User = get_user_model()
        username = 'siska.lestari'

        user = User.objects.filter(username=username).first()
        if user is None:
            user = User.objects.create_user(
                username=username,
                email='siska.lestari@rs.local',
                first_name='Siska',
                last_name='Lestari',
            )
            user.set_password('Perawat@1234')
            user.save()

        unit = UnitKerja.objects.filter(code='BANGSAL-ANAK').first()
        if unit is None:
            unit = UnitKerja.objects.create(
                code='BANGSAL-ANAK',
                name='Bangsal Perawatan Anak',
                level=3,
                is_active=True,
            )

        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': 'STAF_NAKES',
                'unit_kerja': unit,
                'full_name': 'Siska Lestari, S.Kep., Ners',
            },
        )

        pegawai, _ = Pegawai.objects.update_or_create(
            nomor_pegawai='NIP-19950812-202101-2-001',
            defaults={
                'nama_lengkap': 'Siska Lestari, S.Kep., Ners',
                'kategori': 'PPA',
                'profesi': 'Perawat',
                'jabatan': 'Perawat Klinik II (PK II)',
                'akun': user,
                'status': 'AKTIF',
            },
        )

        PenempatanPegawai.objects.update_or_create(
            pegawai=pegawai,
            unit_kerja=unit,
            defaults={
                'tanggal_mulai': today - timedelta(days=5 * 365),
                'alokasi_fte': Decimal('1.00'),
            },
        )

        # Bersihkan entri 5 tahun sebelumnya supaya seed idempoten. Entri
        # 36 bulan lama tidak dihapus: keduanya berbagi tabel yang sama dan
        # rentang 36 bulan adalah subset dari 5 tahun.
        EntriLogbookKlinis.objects.filter(
            employee=pegawai,
            tanggal__lt=today - timedelta(days=5 * 365),
        ).delete()

        tahun_terakhir = today.year
        entries = []
        for nama, total, mandiri, kolaborasi, supervisi in self.TINDAKAN:
            # Sebar volume tiap tindakan ke 5 tahun kalender; jaga proporsi
            # mandiri/kolaborasi/supervisi agar rekap tetap konsisten.
            for idx in range(5):
                tahun = tahun_terakhir - (4 - idx)
                tanggal = today.replace(year=tahun, month=6, day=15)
                if tanggal > today:
                    tanggal = today - timedelta(days=30 * (4 - idx))
                entries.append(EntriLogbookKlinis(
                    employee=pegawai,
                    unit_kerja=unit,
                    tanggal=tanggal,
                    tindakan=nama,
                    jumlah_mandiri=max(1, mandiri // 5),
                    jumlah_kolaborasi=kolaborasi // 5,
                    jumlah_supervisi=supervisi // 5,
                    pasien_ref=f'RM-PED-{tahun}-{total}',
                ))

        EntriLogbookKlinis.objects.bulk_create(entries)

        draf = generate_draft(pegawai, 'LOGBOOK_5TAHUN', user=user)
        draf.isian = {
            'periode_siklus': f'{tahun_terakhir - 4} s.d. {tahun_terakhir + 1}',
            'jenjang_klinis_usulan': 'Perawat Klinik III (PK III)',
            'skp_pelayanan': 'Target 25 SKP (Capaian: 28 SKP)',
            'skp_pelatihan': 'Target 15 SKP (Capaian: 16 SKP)',
            'skp_seminar': 'Target 10 SKP (Capaian: 12 SKP)',
            'skp_publikasi': 'Target 5 SKP (Capaian: 6 SKP)',
            'target_skp_dirjen': '50 SKP',
            'total_skp_diperoleh': '62 SKP',
            'etik_perundungan_t1': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t2': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t3': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t4': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t5': 'Baik | Bebas Kasus Perundungan | Siap Rekredensial',
            'checklist_kualifikasi_str_sip': 'MS',
            'checklist_target_volume_pelayanan': 'MS',
            'checklist_kecukupan_skp': 'MS',
            'checklist_kesehatan_fisik_mental': 'MS',
            'checklist_etik_disiplin_perundungan': 'MS',
            'rekomendasi_tim_adhoc': 'DIKABULKAN SEPENUHNYA',
            'catatan_rekomendasi_adhoc': (
                'Seluruh syarat Pasal 180 terpenuhi tanpa pembatasan; '
                'kewenangan klinis diusulkan naik ke PK III.'
            ),
            'nama_ketua_tim_adhoc': 'Dr. H. Subagyo, Sp.A',
            'nip_ketua_tim_adhoc': '197505122003121002',
            'nama_pimpinan_fasyankes': 'Dr. dr. H. Fachruddin, Sp.B, MARS',
        }
        draf.save(update_fields=['isian', 'updated_at'])

        total = sum(item[1] for item in self.TINDAKAN)
        self.stdout.write(self.style.SUCCESS(
            f'Berhasil seed Buku Kinerja Elektronik 5 tahun untuk '
            f'{pegawai.nama_lengkap} (User: {username} / Perawat@1234)'
        ))
        self.stdout.write(
            f'- {len(self.TINDAKAN)} kompetensi × 5 tahun = {len(entries)} entri '
            f'({total} tindakan)'
        )
        self.stdout.write(
            '- Draf LOGBOOK_5TAHUN siap difinalkan di '
            '/human-capital/kredensial/pengajuan-saya/'
        )
