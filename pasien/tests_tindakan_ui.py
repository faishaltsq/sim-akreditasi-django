from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import StandardItem, UnitKerja
from klinis.models import MasterIcd9
from pasien.models import KunjunganPasien, Pasien, TindakanAsesmen


class TindakanUiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        UnitKerja.objects.get_or_create(code='IGD', defaults={'name': 'IGD', 'level': 3})
        call_command('seed_katalog_klinis', verbosity=0)

    def setUp(self):
        self.user = User.objects.create_user('ui.tindakan')
        self.client.force_login(self.user)
        self.pasien = Pasien.objects.create(
            no_rm='RM-UI-001', nik='3201000000000199', nama_lengkap='Pasien UI',
            tanggal_lahir='1990-01-01', jenis_kelamin='L')
        self.k = KunjunganPasien.objects.create(
            pasien=self.pasien, jenis_kunjungan='IGD', no_kunjungan='IGD-UI-001',
            unit_kerja=UnitKerja.objects.filter(code='IGD').first(),
            penjamin='UMUM', tanggal_masuk=timezone.now(), status='ASESMEN')

    def test_wizard_renders_picker_and_summary(self):
        res = self.client.get(reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk]))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f'tindakanPicker_{self.k.pk}')
        self.assertContains(res, f'tindakanRowTpl_{self.k.pk}')
        self.assertContains(res, 'name="tindakan_form"')
        self.assertContains(res, f'icd9TindakanSummary_{self.k.pk}')

    def test_wizard_renders_existing_line_with_tariff_and_ep(self):
        TindakanAsesmen.objects.create(
            kunjungan=self.k, urutan=1, jenis='ICD9',
            icd9=MasterIcd9.objects.get(kode='99.18'), kode='99.18',
            nama='Infus RL 20 tpm', sumber_data='MASTER',
            tarif_acuan=Decimal('100000'), tarif=Decimal('125000'),
            catatan_tarif='BHP tambahan',
            standard_item=StandardItem.objects.filter(sub_standard='PAP 3').first(),
            ep_status='TERPENUHI')
        res = self.client.get(reverse('pasien:kunjungan_asesmen_awal', args=[self.k.pk]))
        self.assertContains(res, 'value="Infus RL 20 tpm"')
        self.assertContains(res, 'value="125000.00"')
        self.assertContains(res, 'BHP tambahan')
        self.assertContains(res, 'value="PAP 3" selected')
        self.assertContains(res, 'value="TERPENUHI" selected')

    def test_dashboard_modal_contains_tindakan_card(self):
        res = self.client.get(reverse('pasien:igd_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, f'tindakanCard_{self.k.pk}')
        self.assertContains(res, f'tindakanPicker_{self.k.pk}')
