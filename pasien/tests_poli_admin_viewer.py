"""Regresi ADR-16: administrator rumah sakit dapat membuka modul, tanpa hak tulis.

Sebelum ADR-16, ``resolve_role`` mengembalikan ``None`` untuk akun tanpa profesi
klinis — termasuk superuser dan ``ADMIN_RS`` — sehingga seluruh halaman modul
POLI-JANTUNG menolak 403, bahkan halaman cetak yang hanya membaca. Modul jadi
tidak dapat disupervisi sama sekali oleh pemilik/administrator rumah sakit.

Perilaku yang dikunci di sini: baca 200, tulis tetap 403.
"""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien, PenugasanDpjpEpisode
from pasien.services.poli_rbac import VIEWER, resolve_role

TEST_STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
}


@override_settings(
    POLI_JANTUNG_WORKFLOW_ENABLED=True,
    STORAGES=TEST_STORAGES,
)
class AdminViewerAccessTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG', defaults={'name': 'Poliklinik Jantung', 'level': 3},
        )[0]
        cls.superuser = User.objects.create_superuser('root_adr16', password='***')
        cls.admin_rs = User.objects.create_user('admin_rs_adr16', password='***')
        UserProfile.objects.update_or_create(
            user=cls.admin_rs, defaults={'role': 'ADMIN_RS', 'unit_kerja': cls.unit},
        )
        cls.dokter = User.objects.create_user('dpjp_adr16', password='***')
        UserProfile.objects.update_or_create(
            user=cls.dokter,
            defaults={'role': 'STAF_NAKES', 'profesi': 'DOKTER_SPESIALIS', 'unit_kerja': cls.unit},
        )
        cls.patient = Pasien.objects.create(
            no_rm='QA-ADR16', nama_lengkap='Pasien ADR16',
            tanggal_lahir='1970-01-01', jenis_kelamin='L',
        )
        cls.visit = KunjunganPasien.objects.create(
            pasien=cls.patient, no_kunjungan='QA-ADR16',
            jenis_kunjungan='RAJAL', tanggal_masuk=timezone.now(),
            unit_kerja=cls.unit, poliklinik='POLI-JANTUNG',
        )
        today = timezone.localdate()
        PenugasanDpjpEpisode.objects.create(
            visit=cls.visit, doctor=cls.dokter, unit=cls.unit,
            assignment_type='PRIMARY', valid_from=today,
            valid_until=today + timezone.timedelta(days=30),
            is_active=True, source_version='TEST-ADR16', assigned_by=cls.superuser,
        )

    def test_superuser_dipetakan_ke_viewer(self):
        self.assertEqual(resolve_role(self.superuser, self.visit), VIEWER)

    def test_admin_rs_dipetakan_ke_viewer(self):
        self.assertEqual(resolve_role(self.admin_rs, self.visit), VIEWER)

    def test_admin_dapat_membuka_halaman_asesmen(self):
        for user in (self.superuser, self.admin_rs):
            self.client.force_login(user)
            res = self.client.get(f'/pasien/kunjungan/{self.visit.pk}/asesmen-poli/')
            self.assertEqual(res.status_code, 200, f'{user.username} harus bisa membaca')

    def test_admin_dapat_membuka_cetak_consent(self):
        self.client.force_login(self.admin_rs)
        res = self.client.get(f'/pasien/kunjungan/{self.visit.pk}/asesmen-poli/consent/cetak/')
        self.assertEqual(res.status_code, 200)

    def test_admin_tidak_boleh_menulis_langkah(self):
        self.client.force_login(self.admin_rs)
        res = self.client.post(
            f'/pasien/kunjungan/{self.visit.pk}/asesmen-poli/langkah/1/draft/',
            data={'fields': {'penjamin': 'UMUM'}, 'version': 1},
            content_type='application/json',
        )
        self.assertEqual(res.status_code, 403, 'VIEWER tidak boleh mengisi langkah')
