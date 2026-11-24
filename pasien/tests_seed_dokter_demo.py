"""Akun demo dokter supaya modul POLI-JANTUNG benar-benar dapat dipakai (P4).

Yang dikunci: ``seed_dokter_demo`` hanya membuat **akun** untuk Pegawai dokter
jantung yang sudah ada (tidak membuat Pegawai baru), akunnya lolos
``eligible_dpjp_accounts()`` apa adanya, idempoten, dan cukup untuk menjalankan
alur penuh daftar → tetapkan DPJP → simpan langkah 1 tanpa Django admin.
"""
import json

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien, PenugasanDpjpEpisode
from pasien.services.poli_dpjp import eligible_dpjp_accounts
from sdm.models import MasterProfesiPegawai, Pegawai
from sdm.management.commands.seed_dokter_demo import (
    DEMO_EMAIL_DOMAIN, DEMO_NAME_SUFFIX, DEMO_PASSWORD, DEMO_USERNAME_PREFIX,
)

from .tests_poli_workflow import TEST_STORAGES

POLI_JANTUNG = 'POLI-JANTUNG'

#: Salinan baris ``seed_staf_medis`` yang menjadi sasaran: lima Sp.JP dan satu
#: subspesialis jantung. Nama, profesi master, dan statusnya sama seperti seed.
DOKTER_SEED = (
    ('dr. Bima Sakti Perdana, Sp.JP', 'SP_JP', 'AKTIF'),
    ('dr. Cynthia Maharani, Sp.JP', 'SP_JP', 'AKTIF'),
    ('dr. Dimas Arya Ramadhan, Sp.JP', 'SP_JP', 'AKTIF'),
    ('dr. Hendra Gunawan, Sp.JP(K)', 'SP_JP', 'AKTIF'),
    ('dr. Ratna Sari Dewi, Sp.JP', 'SP_JP', 'AKTIF'),
    ('dr. Wahyu Setiawan, Sp.JP(K)FIHA', 'SUB_SP', 'AKTIF'),
)

#: Subspesialis NON-jantung dari seed yang sama: harus tetap tanpa akun.
DOKTER_LAIN_SEED = (
    ('Prof. dr. Suryo Hadiwijoyo, Sp.PD-KGEH', 'SUB_SP'),
    ('dr. Kartika Candra Kirana, Sp.B(K)Onk', 'SUB_SP'),
)

@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class SeedDokterDemoTest(TestCase):
    """Seed dua kali, lalu periksa akun, penanda demo, dan alur penuh."""

    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.get_or_create(
            code=POLI_JANTUNG,
            defaults={'name': 'Poliklinik Jantung & Pembuluh Darah', 'level': 3},
        )[0]
        cls.desk = UnitKerja.objects.get_or_create(
            code='PENDAFTARAN-ADMISSION',
            defaults={'name': 'Pendaftaran & Admisi', 'level': 2},
        )[0]

        cls.profesi = {
            code: MasterProfesiPegawai.objects.get_or_create(
                code=code, defaults={'nama': f'Master {code}', 'keluarga': 'MEDIS'},
            )[0]
            for code in ('SP_JP', 'SUB_SP')
        }
        for index, (nama, kode, status) in enumerate(DOKTER_SEED, start=1):
            Pegawai.objects.get_or_create(
                nama_lengkap=nama,
                defaults={
                    'kategori': 'PPA', 'profesi': cls.profesi[kode].nama,
                    'profesi_master': cls.profesi[kode], 'status': status,
                    'data_origin': 'DEMO', 'nomor_pegawai': f'DEMO-JP-{index:02d}',
                },
            )
        for nama, kode in DOKTER_LAIN_SEED:
            Pegawai.objects.get_or_create(
                nama_lengkap=nama,
                defaults={
                    'kategori': 'PPA', 'profesi': cls.profesi[kode].nama,
                    'profesi_master': cls.profesi[kode], 'status': 'AKTIF',
                    'data_origin': 'DEMO',
                },
            )

        cls.pegawai_count = Pegawai.objects.count()
        cls.admin = User.objects.create_user('admin_demo_jantung', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.admin, defaults={'role': 'ADMIN_RS', 'unit_kerja': cls.desk},
        )
        cls.patient = Pasien.objects.create(
            no_rm='RM-DEMO-DOKTER', nama_lengkap='Pasien Demo DPJP',
            tanggal_lahir='1955-04-12', jenis_kelamin='L',
        )

        call_command('seed_dokter_demo', verbosity=0)
        cls.akun_pertama = list(
            User.objects.filter(username__startswith=DEMO_USERNAME_PREFIX)
            .order_by('username').values_list('username', 'pk')
        )

    def test_command_creates_one_account_per_existing_cardiology_pegawai(self):
        self.assertEqual(len(self.akun_pertama), 6)
        self.assertEqual(
            Pegawai.objects.filter(akun__isnull=False).count(), 6,
        )
        # Tidak ada baris Pegawai baru: hanya akun yang ditambahkan.
        self.assertEqual(Pegawai.objects.count(), self.pegawai_count)

    def test_non_cardiology_subspecialists_remain_without_accounts(self):
        for nama, _kode in DOKTER_LAIN_SEED:
            self.assertIsNone(Pegawai.objects.get(nama_lengkap=nama).akun_id)

    def test_accounts_are_marked_as_demo(self):
        for username, pk in self.akun_pertama:
            user = User.objects.get(pk=pk)
            self.assertTrue(username.startswith(DEMO_USERNAME_PREFIX))
            self.assertTrue(user.email.endswith(f'@{DEMO_EMAIL_DOMAIN}'))
            self.assertTrue(user.profile.full_name.endswith(DEMO_NAME_SUFFIX))
            self.assertTrue(user.check_password(DEMO_PASSWORD))
            self.assertEqual(user.profile.profesi, 'DOKTER_SPESIALIS')
            self.assertEqual(user.profile.unit_kerja_id, self.unit.pk)
        self.assertFalse(
            Pegawai.objects.filter(akun__isnull=False).exclude(data_origin='DEMO').exists()
        )

    def test_second_run_creates_zero_new_accounts(self):
        before = User.objects.count()
        call_command('seed_dokter_demo', verbosity=0)
        self.assertEqual(User.objects.count(), before)
        self.assertEqual(
            User.objects.filter(username__startswith=DEMO_USERNAME_PREFIX).count(), 6)

    def test_dpjp_selector_lists_six_accounts(self):
        self.assertEqual(eligible_dpjp_accounts().count(), 6)

        visit = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='KJ-DEMO-SELECTOR',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            unit_kerja=self.unit, poliklinik='Poli Jantung & Pembuluh Darah',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('pasien:rajal_dashboard'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertNotIn('Belum ada akun dokter terdaftar.', body)
        for _username, pk in self.akun_pertama:
            self.assertIn(f'<option value="{pk}"', body)

    def test_end_to_end_register_assign_dpjp_and_save_step_one(self):
        """Daftar → routing poli → tetapkan DPJP → simpan langkah 1, lewat HTTP."""
        dpjp = User.objects.get(pk=self.akun_pertama[0][1])

        self.client.force_login(self.admin)
        register = self.client.post(reverse('pasien:kunjungan_baru'), {
            'pasien_id': self.patient.pk,
            'jenis_kunjungan': 'RAJAL',
            'tanggal_masuk': timezone.now().strftime('%Y-%m-%dT%H:%M:%S%z'),
            'poliklinik': 'POLI_JANTUNG',
            'penjamin': 'UMUM',
            'no_kunjungan': 'KJ-DEMO-E2E',
        })
        self.assertEqual(register.status_code, 302)

        visit = KunjunganPasien.objects.get(no_kunjungan='KJ-DEMO-E2E')
        # Langkah routing yang nyata: di sinilah unit POLI-JANTUNG dicap.
        route = self.client.post(
            reverse('pasien:pendaftaran_route', args=[visit.pk]),
            {'tujuan': 'RAJAL', 'poliklinik': 'POLI_JANTUNG', 'flag_khusus': 'NORMAL'},
        )
        self.assertEqual(route.status_code, 302)
        visit.refresh_from_db()
        self.assertEqual(visit.unit_kerja.code, POLI_JANTUNG)

        # Penetapan DPJP lewat jalur produksi (bukan Django admin).
        assign = self.client.post(
            reverse('pasien:rajal_dpjp_simpan', args=[visit.pk]),
            {'dpjp_user': dpjp.pk},
        )
        self.assertEqual(assign.status_code, 302)
        rows = list(PenugasanDpjpEpisode.objects.filter(visit=visit, is_active=True))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].doctor_id, dpjp.pk)

        # DPJP sendiri yang mengisi langkah 1 — bukan superuser, bukan admin.
        self.client.force_login(dpjp)
        draft = self.client.post(
            reverse('pasien:poli_workflow_draft', args=[visit.pk, 1]),
            data=json.dumps({
                'fields': {'penjamin': 'BPJS', 'jenis_kunjungan_klinis': 'KONTROL'},
                'version': 0,
            }),
            content_type='application/json',
        )
        self.assertEqual(draft.status_code, 200)
        payload = draft.json()
        self.assertTrue(payload['success'])
        self.assertEqual(payload['values']['penjamin'], 'BPJS')
        self.assertEqual(payload['version'], 1)
