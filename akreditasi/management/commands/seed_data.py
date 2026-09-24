from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from akreditasi.models import (
    Framework, UnitKerja, Category,
    StandardItem, EvidenceReq, QualityRecord, EvidenceFile
)
from accounts.models import UserProfile


class Command(BaseCommand):
    help = 'Seed data awal: Framework STARKES, Pokja TKRS, 7 EP riil, Unit Kerja hierarki 3 tingkat, Superuser admin + user contoh'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database SIM Akreditasi RS...')

        # ========================================================
        # SUPERUSER + USER PROFILES
        # ========================================================
        admin_user, admin_created = User.objects.get_or_create(
            username='admin',
            defaults={'email': 'admin@simakreditasi.id', 'is_superuser': True, 'is_staff': True}
        )
        if admin_created:
            admin_user.set_password('admin123')
            admin_user.save()
            self.stdout.write('  [+] Superuser admin dibuat (password: admin123)')

        UserProfile.objects.get_or_create(
            user=admin_user,
            defaults={
                'role': 'SUPER_ADMIN',
                'full_name': 'Administrator Sistem',
                'jabatan': 'IT RS / Super Admin SIK AP',
                'is_active_member': True,
            }
        )

        # User contoh: Koordinator TKRS
        koord_user, koord_created = User.objects.get_or_create(
            username='koord_tkrs',
            defaults={'email': 'koord_tkrs@simakreditasi.id', 'is_staff': False}
        )
        if koord_created:
            koord_user.set_password('koord123')
            koord_user.save()
            self.stdout.write('  [+] User koord_tkrs dibuat (password: koord123)')

        # User contoh: Kepala Unit Farmasi
        kaunit_user, kaunit_created = User.objects.get_or_create(
            username='ka_farmasi',
            defaults={'email': 'ka_farmasi@simakreditasi.id', 'is_staff': False}
        )
        if kaunit_created:
            kaunit_user.set_password('farmasi123')
            kaunit_user.save()
            self.stdout.write('  [+] User ka_farmasi dibuat (password: farmasi123)')

        # User contoh: Asesor
        asesor_user, asesor_created = User.objects.get_or_create(
            username='asesor1',
            defaults={'email': 'asesor@simakreditasi.id', 'is_staff': False}
        )
        if asesor_created:
            asesor_user.set_password('asesor123')
            asesor_user.save()
            self.stdout.write('  [+] User asesor1 dibuat (password: asesor123)')

        # Framework
        fw, _ = Framework.objects.get_or_create(
            name='STARKES Edisi 2022 / Kemenkes RI',
            defaults={'cycle_type': 'PDCA', 'version': '2026'}
        )

        # ========================================================
        # UNIT KERJA HIERARKI 3 TINGKAT
        # ========================================================

        # Level 1: Direktorat / Bidang
        dir_yanmed, _ = UnitKerja.objects.get_or_create(
            code='DIR-MED',
            defaults={
                'name': 'Direktorat Pelayanan Medik & Keperawatan',
                'pic_name': 'Dr. dr. Haryono, Sp.B',
                'description': 'Membawahi seluruh bidang dan unit pelayanan medik, keperawatan, dan penunjang klinis.',
            }
        )
        dir_umum, _ = UnitKerja.objects.get_or_create(
            code='DIR-UM',
            defaults={
                'name': 'Direktorat Umum, SDM & Keuangan',
                'pic_name': 'Ir. Rudi Hartono, MM',
                'description': 'Membawahi bagian SDM, keuangan, logistik, dan tata usaha.',
            }
        )
        dir_mutu, _ = UnitKerja.objects.get_or_create(
            code='DIR-MUTU',
            defaults={
                'name': 'Sekretariat Dewas & Direksi',
                'pic_name': 'drg. Sartika Handayani, M.Kes',
                'description': 'Sekretariat Dewan Pengawas, Direksi, dan Tim Mutu RS.',
            }
        )

        # Level 2: Bagian / Instalasi / Komite (children of Level 1)
        bag_sdm, _ = UnitKerja.objects.get_or_create(
            code='SDM',
            defaults={
                'name': 'Bagian SDM & Diklat',
                'pic_name': 'Siti Rahmawati, S.Psi, MM',
                'parent': dir_umum,
                'description': 'Perencanaan pegawai, kredensial nakes, pendidikan & pelatihan.',
            }
        )
        bag_keuangan, _ = UnitKerja.objects.get_or_create(
            code='KEU',
            defaults={
                'name': 'Bagian Keuangan & Akuntansi',
                'pic_name': 'Bambang Sudibyo, SE, Ak',
                'parent': dir_umum,
                'description': 'Pengelolaan keuangan, perbendaharaan, akuntansi, dan anggaran RKA.',
            }
        )
        bid_yanmed, _ = UnitKerja.objects.get_or_create(
            code='BID-YAN',
            defaults={
                'name': 'Bidang Pelayanan Medis',
                'pic_name': 'dr. Andi Prasetyo, Sp.PD',
                'parent': dir_yanmed,
                'description': 'Koordinasi pelayanan medik spesialis, rawat jalan, dan rawat inap.',
            }
        )
        bid_penunjang, _ = UnitKerja.objects.get_or_create(
            code='BID-PENJ',
            defaults={
                'name': 'Bidang Penunjang Medis',
                'pic_name': 'dr. Maya Lestari, Sp.PK',
                'parent': dir_yanmed,
                'description': 'Farmasi, laboratorium, radiologi, gizi, dan penunjang medik lainnya.',
            }
        )

        # Level 3: Sub-Bagian / Unit Layanan (children of Level 2)
        unit_ranap, _ = UnitKerja.objects.get_or_create(
            code='RANAP',
            defaults={
                'name': 'Unit Rawat Inap',
                'pic_name': 'Ns. Hendra Wijaya, S.Kep',
                'parent': bid_yanmed,
                'description': 'Bangsal rawat inap kelas I, II, III, VIP, dan ICU.',
            }
        )
        unit_rajal, _ = UnitKerja.objects.get_or_create(
            code='RAJAL',
            defaults={
                'name': 'Unit Rawat Jalan / Poliklinik',
                'pic_name': 'dr. Dewi Kusuma, Sp.A',
                'parent': bid_yanmed,
                'description': 'Poliklinik spesialis, poli umum, dan klinik eksekutif.',
            }
        )
        unit_farmasi, _ = UnitKerja.objects.get_or_create(
            code='FARM',
            defaults={
                'name': 'Unit Pelayanan Farmasi',
                'pic_name': 'apt. Nurul Fatimah, S.Farm',
                'parent': bid_penunjang,
                'description': 'Farmasi rawat jalan, rawat inap, dan depo obat bangsal.',
            }
        )
        unit_lab, _ = UnitKerja.objects.get_or_create(
            code='LAB',
            defaults={
                'name': 'Laboratorium Patologi Klinik',
                'pic_name': 'dr. Yusuf, Sp.PK',
                'parent': bid_penunjang,
                'description': 'Pemeriksaan hematologi, kimia klinik, urinalisis, serologi.',
            }
        )

        units = {
            'SEK-DIR': dir_mutu,  # backward-compatible alias
            'SDM': bag_sdm,
            'KEU': bag_keuangan,
            'RANAP': unit_ranap,
            'FARM': unit_farmasi,
        }

        # User Profiles yang terhubung ke Unit Kerja
        UserProfile.objects.get_or_create(
            user=kaunit_user,
            defaults={
                'role': 'KEPALA_UNIT',
                'full_name': 'apt. Nurul Fatimah, S.Farm',
                'jabatan': 'Kepala Unit Farmasi',
                'unit_kerja': unit_farmasi,
                'is_active_member': True,
            }
        )
        UserProfile.objects.get_or_create(
            user=asesor_user,
            defaults={
                'role': 'ASESOR',
                'full_name': 'Dr. Surya Pratama',
                'jabatan': 'Asesor Eksternal',
                'is_active_member': True,
            }
        )

        # Pokja TKRS
        tkrs, _ = Category.objects.get_or_create(
            code='TKRS',
            framework=fw,
            defaults={
                'name': 'Tata Kelola Rumah Sakit',
                'description': 'Representasi pemilik, akuntabilitas direktur, kepemimpinan unit kerja, dan etik.',
                'order': 1
            }
        )

        # Pokja PMKP (kosong, sebagai placeholder)
        Category.objects.get_or_create(
            code='PMKP',
            framework=fw,
            defaults={
                'name': 'Peningkatan Mutu & Keselamatan Pasien',
                'description': 'Indikator mutu nasional, manajemen risiko terintegrasi, keselamatan pasien.',
                'order': 2
            }
        )

        eps = [
            # (code, sub_std, sub_title, desc, order, unit_code, reqs, record)
            (
                'TKRS 1 EP 1', 'TKRS 1', 'Representasi Pemilik / Dewan Pengawas',
                'Pemilik/Dewan Pengawas menetapkan struktur organisasi dan Peraturan Internal Rumah Sakit (Hospital Bylaws).',
                1, 'SEK-DIR',
                [('R', 'Hospital Bylaws (HBL) Edisi 2026 Disahkan Pemilik', True),
                 ('R', 'SK Struktur Organisasi RS oleh Pemilik/Dewas', True)],
                {
                    'baseline_data': 'HBL versi 2021 belum diperbarui sesuai peraturan Kemenkes terbaru.',
                    'quality_target': '100% Regulasi HBL ter-update.',
                    'risk_mitigation': 'Risiko sengketa hukum tata kelola RS.',
                    'score': 10,
                    'eval_notes': 'Evaluasi Dokumen: HBL telah disahkan oleh Pemilik.',
                    'action_plan': 'Cetak dan distribusi HBL ke seluruh jajaran direksi.',
                    'pic': 'Sekrs', 'target_date': 'Jan 2026',
                    'est_cost': 2500000, 'budget_source': 'RKA Rutin / Operasional', 'budget_status': 'APPROVED'
                },
                'HBL_RS_2026.pdf'
            ),
            (
                'TKRS 1 EP 2', 'TKRS 1', 'Representasi Pemilik / Dewan Pengawas',
                'Pemilik/Dewan Pengawas menyetujui Visi, Misi, Rencana Strategis, dan Rencana Kerja Anggaran RS.',
                2, 'SEK-DIR',
                [('R', 'SK Visi Misi & Renstra RS', True),
                 ('D', 'Bukti Persetujuan Dewas/Pemilik atas Renstra & RKA', True)],
                {
                    'baseline_data': 'Renstra dan RKA telah disahkan pada rapat pleno tahunan.',
                    'quality_target': '100% Renstra dan RKA memiliki persetujuan resmi Dewas.',
                    'risk_mitigation': 'Risiko ketidakselarasan program dengan anggaran.',
                    'score': 10,
                    'eval_notes': 'Diteken oleh Ketua Dewan Pengawas.',
                    'action_plan': 'Distribusi matriks program Renstra ke seluruh kepala bidang.',
                    'pic': 'Sekrs', 'target_date': 'Jan 2026',
                    'est_cost': 1200000, 'budget_source': 'RKA Rutin / Operasional', 'budget_status': 'APPROVED'
                },
                None
            ),
            (
                'TKRS 1 EP 3', 'TKRS 1', 'Representasi Pemilik / Dewan Pengawas',
                'Pemilik/Dewan Pengawas melakukan evaluasi kinerja Direktur dan jajaran direksi secara berkala.',
                3, 'SEK-DIR',
                [('D', 'Laporan Evaluasi Kinerja Direktur', True),
                 ('W', 'Panduan / Notulen Wawancara Dewan Pengawas', True)],
                {
                    'baseline_data': 'Evaluasi kinerja Direktur tahun 2025 baru terlaksana 1x dari target 2x setahun.',
                    'quality_target': 'Ketepatan waktu evaluasi Direktur (100%).',
                    'risk_mitigation': 'Kinerja operasional RS tidak terawasi optimal.',
                    'score': 5,
                    'eval_notes': 'Capaian evaluasi belum lengkap untuk seluruh triwulan.',
                    'action_plan': 'Pelaksanaan rapat pleno evaluasi kinerja Direktur semester II.',
                    'pic': 'Ketua Dewas', 'target_date': 'Feb 2026',
                    'est_cost': 5000000, 'budget_source': 'Anggaran Sekretariat Dewas', 'budget_status': 'SUBMITTED'
                },
                None
            ),
            (
                'TKRS 2 EP 1', 'TKRS 2', 'Akuntabilitas Direktur / Pimpinan',
                'Direktur bertanggung jawab mengelola operasional rumah sakit sesuai kualifikasi dan kewenangan.',
                4, 'SDM',
                [('R', 'SK Pengangkatan & Uraian Tugas Direktur', True),
                 ('D', 'Sertifikat Diklat Manajemen RS / STR & SIP Direktur', True)],
                {
                    'baseline_data': 'Direktur memiliki STR/SIP aktif, namun sertifikat diklat manajemen RS habis masa berlaku.',
                    'quality_target': '100% diklat pimpinan terpenuhi.',
                    'risk_mitigation': 'Masalah legalitas kepemimpinan & akreditasi.',
                    'score': 10,
                    'eval_notes': 'Sertifikat pelatihan manajemen RS perlu refresher.',
                    'action_plan': 'Pendaftaran Direktur pada Pelatihan Manajemen RS terakreditasi.',
                    'pic': 'Ka. SDM', 'target_date': 'Mar 2026',
                    'est_cost': 8500000, 'budget_source': 'Anggaran Diklat SDM', 'budget_status': 'APPROVED'
                },
                None
            ),
            (
                'TKRS 2 EP 2', 'TKRS 2', 'Akuntabilitas Direktur / Pimpinan',
                'Direktur menyampaikan laporan pertanggungjawaban operasional dan keuangan kepada Pemilik/Dewan Pengawas.',
                5, 'KEU',
                [('D', 'Laporan Pertanggungjawaban (LPJ) Triwulan', True),
                 ('D', 'Laporan Keuangan Audit Kantor Akuntan Publik (KAP)', True)],
                {
                    'baseline_data': 'Laporan Keuangan Audit 2025 masih proses finalisasi KAP eksternal.',
                    'quality_target': 'Pelaporan keuangan tepat waktu.',
                    'risk_mitigation': 'Opini keuangan tidak wajar / keterlambatan LPJ.',
                    'score': 0,
                    'eval_notes': 'Laporan Keuangan Audit final belum diunggah.',
                    'action_plan': 'Koordinasi percepatan rilis laporan KAP.',
                    'pic': 'Ka. Keuangan', 'target_date': 'Feb 2026',
                    'est_cost': 35000000, 'budget_source': 'Anggaran Jasa Profesional/KAP', 'budget_status': 'SUBMITTED'
                },
                None
            ),
            (
                'TKRS 3.1 EP 1', 'TKRS 3.1', 'Kepemimpinan Operasional & Kepala Unit Kerja',
                'Kepala Unit Kerja menyusun Program Kerja Unit berbasis Manajemen Risiko secara tahunan.',
                6, 'RANAP',
                [('D', 'Program Kerja Tahunan Unit Rawat Inap 2026', True),
                 ('D', 'Dokumen Risk Register / Profil Risiko Unit', True),
                 ('O', 'Checklist Observasi Implementasi Mitigasi Risiko di Bangsal', False)],
                {
                    'baseline_data': 'Kejadian pasien jatuh di Rawat Inap meningkat 2% pada Triwulan 4.',
                    'quality_target': 'Kepatuhan asesmen risiko jatuh >95%.',
                    'risk_mitigation': 'Pemasangan bed rail & gelang penanda risiko jatuh.',
                    'score': 10,
                    'eval_notes': 'Pengadaan bed rail masih kurang di Bangsal B.',
                    'action_plan': 'Pengadaan 10 unit bed rail baru dan gelang penanda risiko jatuh.',
                    'pic': 'Ka. Ruang Ranap', 'target_date': 'Feb 2026',
                    'est_cost': 15000000, 'budget_source': 'Anggaran Capex/Sarpras', 'budget_status': 'APPROVED'
                },
                None
            ),
            (
                'TKRS 3.1 EP 2', 'TKRS 3.1', 'Kepemimpinan Operasional & Kepala Unit Kerja',
                'Kepala Unit Kerja melakukan evaluasi pelaksanaan indikator mutu unit kerja secara berkala.',
                7, 'FARM',
                [('D', 'Laporan Capaian Indikator Mutu Farmasi Bulanan (INM/IMU)', True),
                 ('W', 'Wawancara dengan Kepala Unit Farmasi', True)],
                {
                    'baseline_data': 'Waktu tunggu obat jadi baru mencapai 75% (Target: ≥80%).',
                    'quality_target': 'Waktu tunggu obat jadi <30 menit.',
                    'risk_mitigation': 'Penumpukan antrean & komplain pasien.',
                    'score': 5,
                    'eval_notes': 'Keterlambatan terjadi karena proses peracikan manual.',
                    'action_plan': 'Re-layout alur kerja farmasi dan pembagian tugas verifikasi resep.',
                    'pic': 'Ka. Farmasi', 'target_date': 'Mar 2026',
                    'est_cost': 0, 'budget_source': 'Non-Biaya / Penataan Internal', 'budget_status': 'NON_BUDGET'
                },
                None
            ),
        ]

        for ep_data in eps:
            code, sub_std, sub_title, desc, order, unit_code, reqs, record_data, *rest = ep_data
            sample_file = rest[0] if rest else None

            item, created = StandardItem.objects.get_or_create(
                code=code,
                category=tkrs,
                defaults={
                    'sub_standard': sub_std,
                    'sub_title': sub_title,
                    'description': desc,
                    'order': order,
                }
            )

            # Selalu pastikan EvidenceReq terisi jika belum ada
            req_objects = []
            for cat_type, title, mandatory in reqs:
                req, _ = EvidenceReq.objects.get_or_create(
                    standard_item=item,
                    category_type=cat_type,
                    title=title,
                    defaults={'is_mandatory': mandatory}
                )
                req_objects.append(req)

            if record_data and not QualityRecord.objects.filter(standard_item=item).exists():
                QualityRecord.objects.create(
                    standard_item=item,
                    unit=units[unit_code],
                    **record_data
                )

            if sample_file and req_objects and not EvidenceFile.objects.filter(requirement=req_objects[0]).exists():
                EvidenceFile.objects.create(
                    requirement=req_objects[0],
                    file_name=sample_file,
                    file_url='#',
                    file_size='2.4 MB',
                    version=1,
                    status='VALID'
                )

            self.stdout.write(f'  [+] EP {code} berhasil dibuat.')

        self.stdout.write(self.style.SUCCESS('\nSeeding selesai! Login: admin / admin123'))
