"""Seed data dummy realistis untuk modul Pasien MonsisKami."""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import date, timedelta
from pasien.models import Pasien, Ruangan, Bed, KunjunganPasien, AsesmenRisikoKlinis, CPPT, BillingItem, DischargeRecord


class Command(BaseCommand):
    help = 'Seed data dummy manajemen pasien untuk demo akreditasi'

    def handle(self, *args, **options):
        self.stdout.write('Seeding data pasien & SIMRS...')

        # ── 1. Ruangan & Bed ────────────────────────────────────────────────
        ruangan_data = [
            ('IGD-01', 'Ruang Resusitasi & Triase IGD', 'IGD', 'IGD', 4),
            ('IGD-02', 'Ruang Observasi IGD', 'IGD', 'IGD', 6),
            ('VIP-A',  'Paviliun Anggrek VIP', 'VIP', 'RANAP', 4),
            ('R-K1',   'Bangsal Mawar (Kelas I)', '1', 'RANAP', 6),
            ('R-K2',   'Bangsal Melati (Kelas II)', '2', 'RANAP', 8),
            ('R-K3',   'Bangsal Dahlia (Kelas III)', '3', 'RANAP', 12),
            ('ICU-01', 'Intensive Care Unit (ICU)', 'ICU', 'ICU', 4),
            ('OK-01',  'Kamar Bedah Sentral', 'OK', 'OK', 2),
        ]

        total_beds = 0
        for kode, nama, kelas, jenis, kap in ruangan_data:
            r, _ = Ruangan.objects.get_or_create(
                kode=kode,
                defaults={'nama': nama, 'kelas': kelas, 'jenis': jenis, 'kapasitas': kap}
            )
            for i in range(1, kap + 1):
                b_code = f'{i:02d}'
                b, created = Bed.objects.get_or_create(
                    ruangan=r, kode_bed=b_code,
                    defaults={'status': 'TERSEDIA'}
                )
                if created:
                    total_beds += 1

        self.stdout.write(f'  ✓ Ruangan & Bed ({Bed.objects.count()} beds)')

        # ── 2. Data Pasien ──────────────────────────────────────────────────
        pasien_samples = [
            ('RM-2026-0001', '3201011205800001', 'Siti Rahmawati', date(1980, 5, 12), 'P', 'O', 'Jl. Merdeka No. 45, Bandung', '081234567890', '0001234567891', 'Penisilin, Ampisilin', ''),
            ('RM-2026-0002', '3201012308750002', 'Budi Santoso', date(1975, 8, 23), 'L', 'A', 'Jl. Sudirman No. 12, Bandung', '081234567891', '0001234567892', '', 'Debu, Udang'),
            ('RM-2026-0003', '3201011502920003', 'Dewi Lestari', date(1992, 2, 15), 'P', 'B', 'Jl. Gatot Subroto No. 88, Bandung', '081234567892', '0001234567893', 'Sulfa', ''),
            ('RM-2026-0004', '3201010101650004', 'Ahmad Supardi', date(1965, 1, 1), 'L', 'AB', 'Jl. Asia Afrika No. 10, Bandung', '081234567893', '0001234567894', '', 'Lateks'),
            ('RM-2026-0005', '3201012011880005', 'Rina Anggraeni', date(1988, 11, 20), 'P', 'O', 'Jl. Riau No. 34, Bandung', '081234567894', '0001234567895', '', ''),
            ('RM-2026-0006', '3201010507990006', 'Fajar Ramadhan', date(1999, 7, 5), 'L', 'B', 'Jl. Buah Batu No. 56, Bandung', '081234567895', '0001234567896', 'Aspirin', ''),
            ('RM-2026-0007', '3201013009550007', 'Hj. Aminah Suryani', date(1955, 9, 30), 'P', 'A', 'Jl. Cihampelas No. 77, Bandung', '081234567896', '0001234567897', '', ''),
            ('RM-2026-0008', '3201011804020008', 'Rizky Pratama', date(2002, 4, 18), 'L', 'O', 'Jl. Dago No. 120, Bandung', '081234567897', '0001234567898', '', ''),
        ]

        pasiens = []
        for no_rm, nik, nama, tgl, jk, goldar, alm, hp, bpjs, al_o, al_l in pasien_samples:
            p, _ = Pasien.objects.get_or_create(
                no_rm=no_rm,
                defaults={
                    'nik': nik, 'nama_lengkap': nama, 'tanggal_lahir': tgl,
                    'jenis_kelamin': jk, 'golongan_darah': goldar, 'alamat': alm,
                    'no_hp': hp, 'no_bpjs': bpjs, 'alergi_obat': al_o, 'alergi_lain': al_l,
                }
            )
            pasiens.append(p)

        self.stdout.write(f'  ✓ Master Pasien ({Pasien.objects.count()} pasien)')

        # ── 3. Kunjungan Pasien ──────────────────────────────────────────────
        now = timezone.now()
        avail_beds = list(Bed.objects.filter(status='TERSEDIA'))

        # Pasien 1: Ranap Bedah (Infeksi Daerah Operasi - Nyata dengan dokumen kasus akreditasi)
        b1 = avail_beds.pop(0) if avail_beds else None
        k1, _ = KunjunganPasien.objects.get_or_create(
            no_kunjungan='REG-2026-0001',
            defaults={
                'pasien': pasiens[0],
                'jenis_kunjungan': 'RANAP',
                'tanggal_masuk': now - timedelta(days=3),
                'dpjp': 'dr. Hendra Sp.B',
                'poliklinik': 'Bangsal Bedah Dahlia',
                'bed': b1,
                'penjamin': 'BPJS',
                'diagnosa_masuk': 'Apendisitis Akut Perforasi post-laparatomi (K35.2)',
                'triage': 'KUNING',
                'status': 'RANAP',
                'general_consent': True,
                'catatan_admisi': 'Pasien rujukan IGD pasca operasi cito. Alergi Penisilin terkonfirmasi.',
            }
        )
        if b1:
            b1.status = 'TERISI'
            b1.save()

        # Pasien 2: Pasien Risiko Jatuh Tinggi (Lansia stroke)
        b2 = avail_beds.pop(0) if avail_beds else None
        k2, _ = KunjunganPasien.objects.get_or_create(
            no_kunjungan='REG-2026-0002',
            defaults={
                'pasien': pasiens[6],  # Hj. Aminah (lansia)
                'jenis_kunjungan': 'RANAP',
                'tanggal_masuk': now - timedelta(days=2),
                'dpjp': 'dr. Bambang Sp.S',
                'poliklinik': 'Bangsal Mawar',
                'bed': b2,
                'penjamin': 'BPJS',
                'diagnosa_masuk': 'Stroke Non-Hemoragik + Hemiparesis Dekstra (I63.9)',
                'triage': 'MERAH',
                'status': 'RANAP',
                'general_consent': True,
                'catatan_admisi': 'Hemiparesis sisi kanan, gangguan keseimbangan berat. Gelang kuning terpasang.',
            }
        )
        if b2:
            b2.status = 'TERISI'
            b2.save()

        # Pasien 3: IGD Aktif
        b3 = avail_beds.pop(0) if avail_beds else None
        k3, _ = KunjunganPasien.objects.get_or_create(
            no_kunjungan='REG-2026-0003',
            defaults={
                'pasien': pasiens[1],
                'jenis_kunjungan': 'IGD',
                'tanggal_masuk': now - timedelta(hours=4),
                'dpjp': 'dr. Maya Sp.EM',
                'poliklinik': 'IGD',
                'bed': b3,
                'penjamin': 'UMUM',
                'diagnosa_masuk': 'Sindrom Koroner Akut — UAP (I20.0)',
                'triage': 'MERAH',
                'status': 'TRIAGE',
                'general_consent': True,
                'catatan_admisi': 'Nyeri dada menjalar ke lengan kiri, skala nyeri 8. EKG sedang evaluasi.',
            }
        )
        if b3:
            b3.status = 'TERISI'
            b3.save()

        # Pasien 4: Rajal Poliklinik
        k4, _ = KunjunganPasien.objects.get_or_create(
            no_kunjungan='REG-2026-0004',
            defaults={
                'pasien': pasiens[2],
                'jenis_kunjungan': 'RAJAL',
                'tanggal_masuk': now - timedelta(hours=2),
                'dpjp': 'dr. Ratna Sp.PD',
                'poliklinik': 'Poli Penyakit Dalam',
                'penjamin': 'BPJS',
                'diagnosa_masuk': 'Diabetes Melitus Tipe 2 Terkontrol (E11.9)',
                'status': 'ASESMEN',
                'general_consent': True,
            }
        )

        # Pasien 5: Sudah Pulang (Discharge lengkap)
        k5, _ = KunjunganPasien.objects.get_or_create(
            no_kunjungan='REG-2026-0005',
            defaults={
                'pasien': pasiens[3],
                'jenis_kunjungan': 'RANAP',
                'tanggal_masuk': now - timedelta(days=6),
                'tanggal_keluar': now - timedelta(days=1),
                'dpjp': 'dr. Hendra Sp.B',
                'poliklinik': 'Bangsal Melati',
                'penjamin': 'BPJS',
                'diagnosa_masuk': 'Hernia Inguinalis Dekstra (K40.9)',
                'diagnosa_keluar': 'Post-Herniorafi Dekstra — Membaik (K40.9)',
                'status': 'PULANG',
                'general_consent': True,
            }
        )

        self.stdout.write(f'  ✓ Kunjungan Pasien ({KunjunganPasien.objects.count()} kunjungan)')

        # ── 4. Asesmen Risiko Klinis ─────────────────────────────────────────
        # K1: Risiko Jatuh Morse (Sedang)
        AsesmenRisikoKlinis.objects.get_or_create(
            kunjungan=k1, jenis='JATUH_MORSE',
            defaults={
                'skor': 35, 'grade': 'SEDANG',
                'temuan': 'Riwayat jatuh (-), diagnosa sekunder (+), berjalan dengan bantuan (+)',
                'intervensi': 'Pasang bed rail, orientasi ruangan, edukasi keluarga call bell.',
                'dinilai_oleh': 'Ns. Dewi S.Kep',
            }
        )
        # K1: PPI Bundle IDO
        AsesmenRisikoKlinis.objects.get_or_create(
            kunjungan=k1, jenis='PPI',
            defaults={
                'skor': 85, 'grade': 'SEDANG',
                'temuan': 'Luka insisi laparotomi bersih, rembesan minimal, balutan steril.',
                'intervensi': 'Perawatan luka steril aseptik tiap 48 jam, bundle IDO dipatuhi.',
                'dinilai_oleh': 'Ns. Siti Amd.Kep',
            }
        )
        # K2: Risiko Jatuh Morse Lansia (Tinggi)
        AsesmenRisikoKlinis.objects.get_or_create(
            kunjungan=k2, jenis='JATUH_MORSE',
            defaults={
                'skor': 65, 'grade': 'SANGAT_TINGGI',
                'temuan': 'Hemiparesis dextra, kelemahan anggota gerak, usia >65 th, keterbatasan mobilitas penuh.',
                'intervensi': 'Pasang klem/gelang kuning, bed rail ganda terkunci, lantai non-slip, pendampingan keluarga 24 jam.',
                'dinilai_oleh': 'Ns. Arif S.Kep',
            }
        )

        # ── 5. CPPT SOAP ─────────────────────────────────────────────────────
        CPPT.objects.get_or_create(
            kunjungan=k1, nama_ppa='dr. Hendra Sp.B', profesi='DOKTER',
            defaults={
                'tanggal': now - timedelta(days=2),
                'subjektif': 'Nyeri luka operasi berkurang, skala 3/10. Flatus (+), mual (-).',
                'objektif': 'TD 120/80, N 82x, RR 18x, T 36.8C. Abdomen supel, bising usus normal. Kassa kering.',
                'asesmen': 'Post laparotomi apendisitis perforasi H+2 — hemodinamik stabil.',
                'plan': 'Diet cair bertahap, mobilisasi duduk, IVFD RL 20 tpm, Ketorolac 30mg/8jam.',
                'verifikasi_dpjp': True,
            }
        )
        CPPT.objects.get_or_create(
            kunjungan=k1, nama_ppa='Ns. Dewi S.Kep', profesi='PERAWAT',
            defaults={
                'tanggal': now - timedelta(days=1),
                'subjektif': 'Pasien sudah mulai minum air putih hangat tanpa mual.',
                'objektif': 'TTV stabil, balutan luka bersih dan kering, intake cairan 800ml/12jam, urin jernih.',
                'asesmen': 'Kesiapan mobilisasi mandiri meningkat, nyeri terkontrol.',
                'plan': 'Bantu mobilisasi bertahap ke kursi, motivasi intake nutrisi seimbang.',
                'verifikasi_dpjp': True,
            }
        )

        # ── 6. Billing Items ─────────────────────────────────────────────────
        billing_items = [
            (k1, 'JASA_MEDIS', 'Tindakan Laparatomi Apendisitis Cito', 1, 4500000, '47.0'),
            (k1, 'KAMAR',      'Akomodasi Rawat Inap Dahlia (3 Hari)', 3, 250000, ''),
            (k1, 'OBAT',       'Ketorolac Injeksi 30mg Ampul', 6, 25000, ''),
            (k1, 'OBAT',       'Ceftriaxone 1gr Vial', 3, 75000, ''),
            (k1, 'LAB',        'Darah Lengkap + Elektrolit Post-Op', 1, 350000, ''),
            (k5, 'JASA_MEDIS', 'Operasi Herniorafi Elektif', 1, 3800000, '53.0'),
            (k5, 'KAMAR',      'Akomodasi Melati Kelas II (5 Hari)', 5, 200000, ''),
            (k5, 'OBAT',       'Paket Obat Pulang & Analgetik', 1, 280000, ''),
        ]
        for kunj, kat, item, qty, hrg, icd in billing_items:
            BillingItem.objects.get_or_create(
                kunjungan=kunj, nama_item=item,
                defaults={'kategori': kat, 'kuantitas': qty, 'harga_satuan': hrg, 'kode_icd': icd}
            )

        # ── 7. Discharge K5 ──────────────────────────────────────────────────
        DischargeRecord.objects.get_or_create(
            kunjungan=k5,
            defaults={
                'tanggal_discharge': now - timedelta(days=1),
                'kondisi_pulang': 'MEMBAIK',
                'resume_medis': 'Pasien menjalani herniorafi tanpa komplikasi. Nyeri minimal, luka insisi kering, toleransi oral baik.',
                'edukasi_pulang': 'Hindari mengangkat beban berat >5kg selama 4 minggu. Rawat luka tetap kering. Kontrol poli H+7.',
                'obat_pulang': 'Asam Mefenamat 500mg 3x1 (prn), Cefixime 200mg 2x1 (5 hari).',
                'jadwal_kontrol': (now + timedelta(days=6)).date(),
                'total_tagihan': 5080000,
                'status_clearance': 'CLEARANCE',
            }
        )

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ SEEDING BERHASIL!\n'
            f'   • {Ruangan.objects.count()} Ruangan, {Bed.objects.count()} Beds (BOR: {Bed.objects.filter(status="TERISI").count()}/{Bed.objects.count()})\n'
            f'   • {Pasien.objects.count()} Pasien\n'
            f'   • {KunjunganPasien.objects.count()} Kunjungan\n'
            f'   • {AsesmenRisikoKlinis.objects.count()} Asesmen Risiko\n'
            f'   • {CPPT.objects.count()} CPPT\n'
            f'   • {BillingItem.objects.count()} Billing Items\n'
            f'   • {DischargeRecord.objects.count()} Discharge Record'
        ))
