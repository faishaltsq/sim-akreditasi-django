from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from akreditasi.models import UnitKerja, AuditLog
from akreditasi.forms import UnitKerjaForm


class UnitKerjaHierarchyTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin_user = self.User.objects.create_superuser(
            username='admin_test_unit',
            email='admin_unit@hospital.id',
            password='TestPassword123!'
        )
        self.client = Client()
        self.client.force_login(self.admin_user)

        # Base L1 unit
        self.unit_l1 = UnitKerja.objects.create(
            name='Direktur Utama & Pimpinan',
            code='DIRUT-TEST',
            level=1
        )

    def test_unit_form_fields_present(self):
        """Pastikan seluruh field krusial tersedia pada UnitKerjaForm termasuk level."""
        form = UnitKerjaForm()
        self.assertIn('name', form.fields)
        self.assertIn('code', form.fields)
        self.assertIn('level', form.fields)
        self.assertIn('parent', form.fields)
        self.assertIn('tipe_unit', form.fields)

    def test_create_level_1_unit(self):
        """Unit tanpa induk default tersimpan sebagai Level 1."""
        response = self.client.post(reverse('akreditasi:unit_list'), {
            'name': 'Dewan Pengawas Rumah Sakit',
            'code': 'DEWAS-TEST',
            'level': 1,
            'parent': '',
            'tipe_unit': 'PIMPINAN',
            'pic_name': 'Prof. Dr. Suwandi',
            'description': 'Pengawas tata kelola RS'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        unit = UnitKerja.objects.get(code='DEWAS-TEST')
        self.assertEqual(unit.level, 1)
        self.assertIsNone(unit.parent)

    def test_create_level_2_unit_under_l1_parent(self):
        """Unit yang memilih Induk L1 otomatis tersimpan sebagai Level 2."""
        response = self.client.post(reverse('akreditasi:unit_list'), {
            'name': 'Direktorat Pelayanan Medik & Penunjang',
            'code': 'DIR-MED-TEST',
            'level': 2,
            'parent': str(self.unit_l1.id),
            'tipe_unit': 'DIREKTORAT',
            'pic_name': 'dr. Hendra, Sp.A',
            'description': 'Membawahi seluruh instalasi medis'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        unit = UnitKerja.objects.get(code='DIR-MED-TEST')
        self.assertEqual(unit.level, 2)
        self.assertEqual(unit.parent, self.unit_l1)

    def test_create_level_2_unit_directly_without_parent(self):
        """Unit yang ditentukan langsung Level 2 tanpa induk tetap tersimpan sebagai Level 2."""
        response = self.client.post(reverse('akreditasi:unit_list'), {
            'name': 'Komite Etik & Hukum Independen',
            'code': 'KOMITE-ETIK-TEST',
            'level': 2,
            'parent': '',
            'tipe_unit': 'KOMITE',
            'pic_name': 'Dr. dr. Bambang, SH',
            'description': 'Komite independen level 2'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        unit = UnitKerja.objects.get(code='KOMITE-ETIK-TEST')
        self.assertEqual(unit.level, 2)
        self.assertIsNone(unit.parent)

    def test_create_level_3_unit_under_l2_parent(self):
        """Unit di bawah Level 2 otomatis tersimpan sebagai Level 3."""
        unit_l2 = UnitKerja.objects.create(
            name='Direktorat Keuangan',
            code='DIR-KEU-TEST',
            parent=self.unit_l1,
            level=2
        )
        response = self.client.post(reverse('akreditasi:unit_list'), {
            'name': 'Bagian Akuntansi & Anggaran',
            'code': 'BAG-AKUN-TEST',
            'parent': str(unit_l2.id),
            'level': 3,
            'tipe_unit': 'BAGIAN',
            'pic_name': 'Drs. Supriyadi, Ak',
            'description': 'Pengelolaan pembukuan'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        unit = UnitKerja.objects.get(code='BAG-AKUN-TEST')
        self.assertEqual(unit.level, 3)
        self.assertEqual(unit.parent, unit_l2)

    def test_unit_edit_view(self):
        """Mengedit unit kerja memperbarui data dan level dengan benar."""
        unit = UnitKerja.objects.create(
            name='Unit Humas Awal',
            code='HUMAS-AWAL',
            level=1
        )
        response = self.client.post(reverse('akreditasi:unit_edit', args=[unit.id]), {
            'name': 'Unit Humas & PKRS Baru',
            'code': 'HUMAS-AWAL',
            'parent': str(self.unit_l1.id),
            'level': 2,
            'tipe_unit': 'BAGIAN',
            'pic_name': 'Siti Rahma, S.I.Kom',
            'description': 'Diubah ke bawah Dirut'
        }, follow=True)
        self.assertEqual(response.status_code, 200)

        unit.refresh_from_db()
        self.assertEqual(unit.name, 'Unit Humas & PKRS Baru')
        self.assertEqual(unit.level, 2)
        self.assertEqual(unit.parent, self.unit_l1)

    def test_rendered_form_contains_submit_button_and_level_selector(self):
        """Template unit_form.html wajib memiliki tombol submit Simpan Unit Kerja dan selector level."""
        response = self.client.get(reverse('akreditasi:unit_list'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('btnSubmitUnit', content)
        self.assertIn('Simpan &amp; Tambahkan Unit Kerja', content)
        self.assertIn('id_level', content)
        self.assertIn('id_parent', content)
