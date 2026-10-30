"""Seed data perawat Siska Lestari, S.Kep., Ners beserta akumulasi logbook 36 bulan.

Sesuai spesifikasi Modul Logbook 36 Bulan (Kredensial ARima).
"""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DrafDokumenKredensial,
    EntriLogbookKlinis,
    Pegawai,
    PenempatanPegawai,
)
from sdm.services.dokumen_kredensial import finalize, generate_draft


class Command(BaseCommand):
    help = 'Seed data kredensial logbook 36 bulan perawat Siska Lestari (Bangsal Anak)'

    def handle(self, *args, **options):
        today = timezone.localdate()
        User = get_user_model()

        # 1. Unit Kerja: Bangsal Perawatan Anak
        unit = UnitKerja.objects.filter(code='BANGSAL-ANAK').first()
        if not unit:
            unit = UnitKerja.objects.create(
                code='BANGSAL-ANAK',
                name='Bangsal Perawatan Anak',
                level=3,
                is_active=True,
            )

        # 2. Akun User & Profil
        username = 'siska.lestari'
        user, user_created = User.objects.get_or_create(
            username=username,
            defaults={
                'first_name': 'Siska',
                'last_name': 'Lestari',
                'email': 'siska.lestari@rs.local',
                'is_active': True,
            },
        )
        if user_created:
            user.set_password('Perawat@1234')
            user.save()

        UserProfile.objects.update_or_create(
            user=user,
            defaults={
                'role': 'STAF_NAKES',
                'unit_kerja': unit,
                'full_name': 'Siska Lestari, S.Kep., Ners',
            },
        )

        # 3. Pegawai
        pegawai, _ = Pegawai.objects.update_or_create(
            nomor_pegawai='NIP-19950812-202101-2-001',
            defaults={
                'nama_lengkap': 'Siska Lestari, S.Kep., Ners',
                'kategori': 'PPA',
                'profesi': 'Perawat',
                'jabatan': 'Perawat Klinik I (PK I)',
                'akun': user,
                'status': 'AKTIF',
            },
        )

        # Penempatan Aktif
        PenempatanPegawai.objects.update_or_create(
            pegawai=pegawai,
            unit_kerja=unit,
            defaults={
                'tanggal_mulai': today - timedelta(days=36 * 30),
                'alokasi_fte': Decimal('1.00'),
            },
        )

        # 4. Hapus entri lama jika ingin seed ulang bersih
        EntriLogbookKlinis.objects.filter(employee=pegawai).delete()

        # 5. Daftar 8 Tindakan Klinis 36 Bulan dari Dokumen Word
        daftar_tindakan = [
            {
                'nama': 'Pengkajian & Triase Anak (Pediatric Assessment Triangle)',
                'total': 380, 'mandiri': 320, 'kolaborasi': 40, 'supervisi': 20,
            },
            {
                'nama': 'Pemberian Terapi Obat Oral & Injeksi (Anak/Bayi)',
                'total': 1250, 'mandiri': 1100, 'kolaborasi': 100, 'supervisi': 50,
            },
            {
                'nama': 'Pemasangan Infus / Akses Vaskuler Perifer pada Anak',
                'total': 315, 'mandiri': 280, 'kolaborasi': 25, 'supervisi': 10,
            },
            {
                'nama': 'Perhitungan Dosis Obat Pediatrik (Sesuai BB/BSA)',
                'total': 520, 'mandiri': 480, 'kolaborasi': 30, 'supervisi': 10,
            },
            {
                'nama': 'Manajemen Demam & Kompres Hangat Terpadu',
                'total': 210, 'mandiri': 200, 'kolaborasi': 10, 'supervisi': 0,
            },
            {
                'nama': 'Fisioterapi Dada & Suctioning pada Anak',
                'total': 165, 'mandiri': 140, 'kolaborasi': 20, 'supervisi': 5,
            },
            {
                'nama': 'Pemberian Nutrisi Enteral (Naso/Oro-Gastric Tube - NGT)',
                'total': 110, 'mandiri': 95, 'kolaborasi': 10, 'supervisi': 5,
            },
            {
                'nama': 'Edukasi Perawatan Anak Sakit untuk Orang Tua',
                'total': 160, 'mandiri': 150, 'kolaborasi': 10, 'supervisi': 0,
            },
        ]

        # Sebar entri ke dalam 3 rentang tahun (Tahun 1, 2, 3)
        offsets = [20, 180, 360, 540, 720, 900]
        entries_to_create = []
        for i, item in enumerate(daftar_tindakan):
            # Buat entri mandiri
            entries_to_create.append(EntriLogbookKlinis(
                employee=pegawai,
                unit_kerja=unit,
                tanggal=today - timedelta(days=offsets[i % len(offsets)]),
                tindakan=item['nama'],
                jumlah_mandiri=item['mandiri'],
                jumlah_kolaborasi=item['kolaborasi'],
                jumlah_supervisi=item['supervisi'],
                pasien_ref=f'RM-PED-{100 + i}',
            ))

        EntriLogbookKlinis.objects.bulk_create(entries_to_create)

        # 6. Buat Draf Dokumen Kredensial LOGBOOK_36BULAN
        draf = generate_draft(pegawai, 'LOGBOOK_36BULAN', user=user)
        draf.isian = {
            'jenjang_klinis_diusulkan': 'Perawat Klinik II (PK II)',
            'evaluasi_tahun_1': (
                'Adaptasi & keterampilan dasar terpenuhi dengan baik; perlu '
                'ketelitian konsisten pada monitoring balance cairan anak.'
            ),
            'evaluasi_tahun_2': (
                'Adaptasi kegawatdaruratan anak sangat baik; komunikasi terapeutik '
                'dengan orang tua pasien terjalin sangat efektif.'
            ),
            'evaluasi_tahun_3': (
                'Penguatan Evidence-Based Practice (EBP) manajemen nyeri, pencegahan '
                'HAIs (CLABSI & VAP), serta aktif memberikan bimbingan peer.'
            ),
            'catatan_penilaian': (
                'Telah melampaui seluruh target volume tindakan klinis 36 bulan '
                'dengan kompetensi mandiri yang solid. Direkomendasikan naik '
                'jenjang klinis ke PK II.'
            ),
            'nama_preseptor': 'Ns. M. Zainuddin, M.Kep., Sp.Mat',
            'nama_kepala_instalasi': 'Dr. Nurlaela, M.Kep.',
        }
        draf.save(update_fields=['isian', 'updated_at'])

        self.stdout.write(self.style.SUCCESS(
            f'Berhasil seed data logbook 36 bulan untuk {pegawai.nama_lengkap} '
            f'(User: {username} / Perawat@1234)'
        ))
        self.stdout.write(f'- Total 8 kompetensi tindakan: {sum(x["total"] for x in daftar_tindakan)} tindakan')
        self.stdout.write('- Draf LOGBOOK_36BULAN siap diisi dan difinalkan di /human-capital/kredensial/pengajuan-saya/')
