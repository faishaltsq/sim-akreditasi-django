"""
Buat akun demo read-only (ASESOR) + isi data dummy transaksional:
 - QualityRecord (skor EP)
 - EvidenceFile (file bukti dummy)
 - RisikoUnit + TindakLanjutRisiko
 - InsidenKeselamatan
 - CatatanIndikator (capaian 12 bulan untuk 49 indikator)
"""
import random
from decimal import Decimal
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password


class Command(BaseCommand):
    help = 'Buat akun demo.viewer (ASESOR read-only) + seed data dummy transaksional'

    def handle(self, *args, **options):
        from django.contrib.auth.models import User
        from accounts.models import UserProfile
        from akreditasi.models import (
            UnitKerja, Category, StandardItem, QualityRecord,
            EvidenceFile, EvidenceReq, AuditLog,
        )
        from akreditasi.risiko_models import (
            RisikoUnit, TindakLanjutRisiko, InsidenKeselamatan,
            IndikatorMutu, CatatanIndikator,
        )

        self.stdout.write(self.style.SUCCESS('\n=== SEED AKUN DEMO READ-ONLY + DATA DUMMY ==='))

        # ── 1. Akun demo.viewer ──────────────────────────────────────────
        u, created = User.objects.update_or_create(
            username='demo.viewer',
            defaults={
                'first_name': 'Demo',
                'last_name': 'Viewer (Read Only)',
                'is_staff': False,
                'is_superuser': False,
                'password': make_password('Demo@1234'),
            }
        )
        UserProfile.objects.update_or_create(
            user=u,
            defaults={'role': 'ASESOR', 'unit_kerja': None}
        )
        self.stdout.write(f'  ✓ Akun demo.viewer (ASESOR) {"dibuat" if created else "diupdate"}')
        self.stdout.write(f'    Login: demo.viewer / Demo@1234')

        # ── 2. Data dummy QualityRecord (skor EP) ────────────────────────
        records = QualityRecord.objects.select_related('standard_item', 'unit').all()
        scored = 0
        for rec in records:
            if rec.score is None or rec.score == 0:
                rec.score = random.choice([0, 5, 10, 10, 10])  # bias ke 10
                rec.plan = 'Rencana perbaikan mutu sesuai standar STARKES.' if rec.score < 10 else ''
                rec.do_action = 'Pelaksanaan kegiatan perbaikan.' if rec.score < 10 else 'Sudah terlaksana sesuai standar.'
                rec.check_result = 'Monitoring dan evaluasi berkala.' if rec.score < 10 else 'Hasil memenuhi standar.'
                rec.action_followup = 'Tindak lanjut perbaikan berkelanjutan.' if rec.score < 10 else ''
                rec.save()
                scored += 1
        self.stdout.write(f'  ✓ {scored} QualityRecord diberi skor dummy (total {records.count()})')

        # ── 3. Data dummy RisikoUnit ─────────────────────────────────────
        units = list(UnitKerja.objects.filter(level__lte=3)[:12])
        risk_data = [
            # (jenis_risiko, deskripsi, kategori, pj)
            ('Keterlambatan pelayanan pendaftaran', 'Pasien menunggu > 60 menit di loket pendaftaran IRJ', 'MANAJERIAL', 'Ka. Instalasi Rekam Medis'),
            ('Infeksi Nosokomial / HAIs', 'Kepatuhan cuci tangan petugas di bawah target 85%', 'KLINIS', 'Ketua Komite PPI'),
            ('Medication Error', 'Kesalahan dosis/identitas obat pada proses dispensing farmasi', 'KLINIS', 'Ka. Instalasi Farmasi'),
            ('Risiko Jatuh Pasien Geriatri', 'Lantai basah, bed tanpa pengaman, pasien tanpa gelang risiko jatuh', 'KLINIS', 'Ka. Instalasi Ranap'),
            ('Kebocoran Data Rekam Medis', 'Akses SIMRS tanpa otorisasi valid (shared password)', 'MANAJERIAL', 'Ka. Instalasi SIMRS'),
            ('Kegagalan Sterilisasi CSSD', 'Indikator biologi uji sterilisasi tidak lulus sesuai standar', 'KLINIS', 'Ka. Instalasi CSSD'),
            ('Kerusakan Alat Medis Kritikal', 'Mesin anestesi tidak dikalibrasi sesuai jadwal preventif', 'MANAJERIAL', 'Ka. IPSRS'),
            ('Kecelakaan Kerja Petugas (Needlestick)', 'Tertusuk jarum saat phlebotomy tanpa APD sarung tangan', 'KLINIS', 'Ka. K3RS'),
            ('Ketidaklengkapan Rekam Medis', 'Resume medis > 24 jam belum ditandatangani DPJP', 'MANAJERIAL', 'Ka. Rekam Medis'),
            ('Penundaan Operasi Elektif', 'Jadwal OK penuh dan instrumen belum tersedia dari CSSD', 'MANAJERIAL', 'Ka. IBS'),
            ('Salah Identifikasi Pasien', 'Gelang ID tidak terpasang atau terpasang keliru sebelum tindakan', 'KLINIS', 'Ka. Keperawatan'),
            ('Keterlambatan Pelaporan Kritis Lab', 'Hasil kritis laboratorium > 15 menit belum dilaporkan ke DPJP', 'KLINIS', 'Ka. Laboratorium'),
        ]
        statuses = ['IDENTIFIKASI', 'PLAN', 'DO', 'EVALUASI', 'SELESAI']
        strategies = ['HINDARI', 'KURANGI', 'TRANSFER', 'TERIMA']
        risk_created = 0
        for i, (jenis, deskripsi, kategori, pj) in enumerate(risk_data):
            unit = units[i % len(units)]
            dampak = random.randint(2, 5)
            prob = random.randint(2, 5)
            if not RisikoUnit.objects.filter(jenis_risiko=jenis, unit=unit).exists():
                r = RisikoUnit.objects.create(
                    unit=unit,
                    tahun=2026,
                    periode=random.choice(['TRIWULAN_1', 'TRIWULAN_2', 'TRIWULAN_3', 'TRIWULAN_4']),
                    kategori_risiko=kategori,
                    jenis_risiko=jenis,
                    deskripsi_risiko=deskripsi,
                    dampak=dampak,
                    probabilitas=prob,
                    status=random.choice(statuses),
                    strategi_mitigasi=random.choice(strategies),
                    rencana_aksi=f'Implementasi prosedur {jenis} sesuai standar STARKES.',
                    pj_mitigasi=pj,
                    biaya_mitigasi=Decimal(str(random.randint(5, 50) * 1_000_000)),
                    target_selesai=date.today() + timedelta(days=random.randint(30, 180)),
                    dampak_residual=max(1, dampak - random.randint(0, 2)),
                    probabilitas_residual=max(1, prob - random.randint(0, 2)),
                )
                risk_created += 1
                TindakLanjutRisiko.objects.create(
                    risiko=r,
                    urutan=1,
                    aksi=f'Sosialisasi dan pelatihan: {jenis[:60]}',
                    status_aksi=random.choice(['BELUM', 'SEDANG', 'SELESAI']),
                    tanggal_mulai=date.today() - timedelta(days=30),
                    tanggal_selesai=date.today() + timedelta(days=60),
                    catatan='Tindak lanjut sesuai rencana PDCA unit.',
                )
        self.stdout.write(f'  ✓ {risk_created} RisikoUnit baru (total {RisikoUnit.objects.count()})')

        # ── 4. Data dummy InsidenKeselamatan ──────────────────────────────
        insiden_list = [
            ('KNC', 'MINOR', 'UGD', 'Hampir salah identifikasi pasien di triase — petugas menyadari sebelum tindakan', 'Verifikasi ulang gelang pasien, edukasi petugas'),
            ('KTD', 'MODERAT', 'RANAP', 'Pasien jatuh dari tempat tidur saat malam hari — luka lecet pada lengan', 'Pasien dipindah ke bed rendah, asesmen ulang risiko jatuh'),
            ('KTC', 'TIDAK_CEDERA', 'FARM', 'Obat expired nyaris diberikan ke pasien — terdeteksi petugas farmasi saat dispensing', 'Obat ditarik, pengecekan ulang stok expired bulanan'),
            ('KNC', 'MINOR', 'LAB', 'Spesimen darah tidak berlabel saat diterima di laboratorium', 'Dikembalikan ke ruangan untuk relabeling, edukasi phlebotomist'),
            ('SENTINEL', 'SENTINEL', 'IBS', 'Kassa tertinggal dalam abdomen pasien post-operasi laparotomi', 'Re-operasi segera, pelaporan ke direksi dan KARS, RCA dilakukan'),
        ]
        insiden_created = 0
        for jenis, keparahan, unit_code, deskripsi, tindakan in insiden_list:
            unit = UnitKerja.objects.filter(code=unit_code).first()
            obj, created = InsidenKeselamatan.objects.get_or_create(
                deskripsi_kejadian=deskripsi,
                defaults={
                    'unit': unit,
                    'tanggal_kejadian': date.today() - timedelta(days=random.randint(1, 90)),
                    'jenis_insiden': jenis,
                    'tingkat_keparahan': keparahan,
                    'lokasi_kejadian': f'Area {unit.name[:40]}' if unit else 'Area pelayanan',
                    'tindakan_segera': tindakan,
                    'pasien_terpapar': jenis in ('KTD', 'SENTINEL'),
                    'pelapor_anonim': True,
                }
            )
            if created:
                insiden_created += 1
        self.stdout.write(f'  ✓ {insiden_created} InsidenKeselamatan baru (total {InsidenKeselamatan.objects.count()})')

        # ── 5. Data dummy CatatanIndikator (12 bulan × 49 indikator) ─────
        indikators = IndikatorMutu.objects.filter(aktif=True)
        catatan_created = 0
        for ind in indikators:
            target = float(ind.target_nilai)
            for bulan in range(1, 13):
                # Simulasi: capaian fluktuatif ±15% dari target
                base = target * random.uniform(0.80, 1.10)
                denominator = random.randint(50, 200)
                numerator = round(base * denominator / 100, 2)
                numerator = max(0, min(numerator, denominator))

                obj, created = CatatanIndikator.objects.update_or_create(
                    indikator=ind, bulan=bulan, tahun=2026,
                    defaults={
                        'nilai_numerator': Decimal(str(numerator)),
                        'nilai_denominator': Decimal(str(denominator)),
                        'catatan': f'Data evaluasi bulan {bulan}/2026 — {ind.kode_indikator}',
                    }
                )
                if created:
                    catatan_created += 1
        self.stdout.write(f'  ✓ {catatan_created} CatatanIndikator baru (total {CatatanIndikator.objects.count()})')

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ Selesai! Akun demo.viewer (Demo@1234) siap digunakan.\n'
            f'   Data dummy: {scored} skor EP, {risk_created} risiko, '
            f'{insiden_created} insiden, {catatan_created} capaian indikator.'
        ))
