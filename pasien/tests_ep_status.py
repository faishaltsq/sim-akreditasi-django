from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import StandardItem
from klinis.models import AturanEpAsesmen
from pasien.models import Pasien, KunjunganPasien, KorelasiEpAsesmen


class StatusEpTest(TestCase):
    def setUp(self):
        call_command('seed_katalog_klinis')
        self.pasien = Pasien.objects.create(
            nama_lengkap='Pasien EP Test',
            no_rm='RM-EP-001',
            tanggal_lahir='1985-05-05',
            jenis_kelamin='P',
        )
        self.kunjungan = KunjunganPasien.objects.create(
            pasien=self.pasien,
            no_kunjungan='KUNJ-EP-001',
            jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(),
            status='AKTIF',
        )
        self.item_ark1 = StandardItem.objects.filter(sub_standard='ARK 1').first()
        self.item_pap3 = StandardItem.objects.filter(sub_standard='PAP 3').first()
        self.item_pap8 = StandardItem.objects.filter(sub_standard='PAP 8').first()
        self.item_skp1 = StandardItem.objects.filter(sub_standard='SKP 1').first()

    def test_belum_when_no_rows(self):
        self.assertEqual(self.kunjungan.status_ep_ringkas, 'BELUM')

    def test_sebagian_when_partial(self):
        KorelasiEpAsesmen.objects.create(
            kunjungan=self.kunjungan,
            standard_item=self.item_ark1,
            status='TERPENUHI',
        )
        self.assertEqual(self.kunjungan.status_ep_ringkas, 'SEBAGIAN')

    def test_terpenuhi_when_all_mandatory(self):
        for item in [self.item_ark1, self.item_pap3, self.item_pap8, self.item_skp1]:
            KorelasiEpAsesmen.objects.create(
                kunjungan=self.kunjungan,
                standard_item=item,
                status='TERPENUHI',
            )
        self.assertEqual(self.kunjungan.status_ep_ringkas, 'TERPENUHI')

    def test_na_does_not_count_as_terpenuhi(self):
        KorelasiEpAsesmen.objects.create(
            kunjungan=self.kunjungan,
            standard_item=self.item_ark1,
            status='NA',
        )
        self.assertEqual(self.kunjungan.status_ep_ringkas, 'BELUM')
