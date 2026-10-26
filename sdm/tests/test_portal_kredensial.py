"""C-5: self-service portal logbook + supporting document surface."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    KatalogTindakan,
    MasterJenjangProfesi,
    MasterProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
)
from sdm.models.logbook import EntriLogbookKlinis


class PortalBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli C5', code='POL-C5')
        self.other_unit = UnitKerja.objects.create(name='Poli C5 Lain', code='POL-C5B')
        self.profesi = MasterProfesiPegawai.objects.create(
            code='P-C5', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        self.jenjang = MasterJenjangProfesi.objects.create(
            profesi=self.profesi, kode='PK-C5', nama='Perawat Klinis I', urutan=1,
        )
        self.katalog = KatalogTindakan.objects.create(
            kode='PR-C5', nama='Pemasangan Infus', jenjang=self.jenjang,
            tingkat_supervisi='M',
        )
        self.user = get_user_model().objects.create_user(username='c5-staff')
        self.employee = self._employee('Pegawai C5', user=self.user)

    def _employee(self, name, *, user=None, unit=None):
        employee = Pegawai.objects.create(
            nama_lengkap=name, kategori='PPA', profesi='Perawat',
            profesi_master=self.profesi, akun=user,
        )
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=unit or self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        return employee

    def _portal_user(self, *, username, employee, unit=None):
        """Staff with zero HC grants: portal reads own data only."""
        user = employee.akun
        if user is None:
            user = get_user_model().objects.create_user(username=username)
            employee.akun = user
            employee.save(update_fields=['akun', 'updated_at'])
        UserProfile.objects.create(user=user, role='STAF_NAKES', unit_kerja=unit or self.unit)
        return user


class PortalPageTests(PortalBase):
    def setUp(self):
        super().setUp()
        self._portal_user(username='c5-staff', employee=self.employee)

    def test_staff_with_zero_hc_grant_opens_page(self):
        self.assertFalse(HcGrant.objects.filter(user=self.user).exists())
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        self.assertEqual(response.status_code, 200)

    def test_portal_shows_own_logbook(self):
        EntriLogbookKlinis.objects.create(
            employee=self.employee, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=self.katalog, jumlah_mandiri=4,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        content = response.content.decode('utf-8')
        self.assertIn('Logbook saya', content)
        self.assertIn('Pemasangan Infus', content)

    def test_portal_document_list_shows_existence_state_only(self):
        from sdm.models import DokumenPegawai, VersiDokumen
        document = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL', jenis_berkas='CV',
            title='CV Rahasia Pegawai', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='cv.pdf',
            storage_key='personnel/x/cv.pdf', sha256='e' * 64, size_bytes=10,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=400),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        content = response.content.decode('utf-8')
        self.assertIn('Dokumen Pendukung', content)
        self.assertIn('CV', content)
        # Content of the document must never surface in the portal list.
        self.assertNotIn('CV Rahasia Pegawai', content)

    def test_portal_processes_no_foreign_logbook_rows(self):
        foreign = self._employee('Pegawai C5 Asing', unit=self.other_unit)
        EntriLogbookKlinis.objects.create(
            employee=foreign, tanggal=self.today, unit_kerja=self.other_unit,
            katalog_tindakan=self.katalog, jumlah_mandiri=9,
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        self.assertNotContains(response, 'Pegawai C5 Asing')

    def test_portal_creates_own_logbook_entry(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('sdm:logbook_create'), {
            'employee': str(self.employee.pk),
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.unit.pk),
            'modus': 'katalog',
            'katalog_tindakan': str(self.katalog.pk),
            'jumlah_mandiri': 2,
            'jumlah_supervisi': 1,
        })
        self.assertEqual(response.status_code, 302)
        entry = EntriLogbookKlinis.objects.get(employee=self.employee)
        self.assertEqual(entry.jumlah_mandiri, 2)
        self.assertEqual(entry.created_by, self.user)

    def test_portal_cannot_create_entry_for_other_employee(self):
        foreign = self._employee('Pegawai C5 Korban', unit=self.other_unit)
        self.client.force_login(self.user)
        response = self.client.post(reverse('sdm:logbook_create'), {
            'employee': str(foreign.pk),
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.other_unit.pk),
            'modus': 'katalog',
            'katalog_tindakan': str(self.katalog.pk),
            'jumlah_mandiri': 2,
        })
        self.assertIn(response.status_code, (302, 403))
        self.assertFalse(
            EntriLogbookKlinis.objects.filter(employee=foreign).exists()
        )

    def test_portal_upload_lands_in_own_vault(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            'cv.pdf', b'%PDF-1.4 own', content_type='application/pdf',
        )
        response = self.client.post(reverse('sdm:portal_dokumen_upload'), {
            'jenis_berkas': 'CV',
            'berkas': upload,
        })
        self.assertEqual(response.status_code, 302)
        from sdm.models import DokumenPegawai
        document = DokumenPegawai.objects.get(employee=self.employee, jenis_berkas='CV')
        self.assertEqual(document.sensitivity, 'personnel')
        self.assertEqual(document.created_by, self.user)

    def test_portal_upload_rejects_health_kind(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            'mcu.pdf', b'%PDF-1.4 mcu', content_type='application/pdf',
        )
        response = self.client.post(reverse('sdm:portal_dokumen_upload'), {
            'jenis_berkas': 'MALPRACTICE_RECORD', 'berkas': upload,
        })
        self.assertEqual(response.status_code, 403)

    def test_portal_upload_cannot_target_other_employee(self):
        foreign = self._employee('Pegawai C5 Sasaran', unit=self.other_unit)
        self.client.force_login(self.user)
        upload = SimpleUploadedFile(
            'cv.pdf', b'%PDF-1.4 foreign', content_type='application/pdf',
        )
        response = self.client.post(reverse('sdm:portal_dokumen_upload'), {
            'employee': str(foreign.pk),
            'jenis_berkas': 'CV',
            'berkas': upload,
        })
        self.assertEqual(response.status_code, 302)
        from sdm.models import DokumenPegawai
        self.assertFalse(
            DokumenPegawai.objects.filter(employee=foreign).exists()
        )
        self.assertTrue(
            DokumenPegawai.objects.filter(employee=self.employee).exists()
        )


class PortalFormD1Tests(PortalBase):
    """D-1: no self-selection, auto unit, read-only profile card."""

    def setUp(self):
        super().setUp()
        self._portal_user(username='c5-staff', employee=self.employee)

    def test_portal_form_has_no_employee_field(self):
        from sdm.forms.kredensial_portal import PengajuanPortalForm
        form = PengajuanPortalForm(user=self.user)
        self.assertNotIn('employee', form.fields)

    def test_portal_form_auto_selects_placement_unit(self):
        from sdm.forms.kredensial_portal import PengajuanPortalForm
        form = PengajuanPortalForm(user=self.user)
        self.assertEqual(list(form.fields['unit_kerja'].queryset),
                         [self.unit])

    def test_portal_submit_uses_logged_in_employee_and_unit(self):
        from sdm.models import PengajuanKredensial
        self.client.force_login(self.user)
        response = self.client.post(reverse('sdm:kredensial_pengajuan_sendiri'), {
            'jenis': 'AWAL',
        })
        self.assertEqual(response.status_code, 302)
        application = PengajuanKredensial.objects.get()
        self.assertEqual(application.employee, self.employee)
        self.assertEqual(application.unit_kerja, self.unit)

    def test_profile_card_shows_identity_and_license_state(self):
        from sdm.models import IzinProfesiPegawai
        IzinProfesiPegawai.objects.create(
            pegawai=self.employee, subtype='STR', nomor_izin='STR-123',
            profesi='Perawat', pemberi_izin='KTKI',
            validity_mode='EXPIRY_REQUIRED',
            tanggal_terbit=self.today - timedelta(days=100),
            tanggal_berakhir=self.today + timedelta(days=400),
        )
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        content = response.content.decode('utf-8')
        self.assertIn('Profil Kredensial', content)
        self.assertIn(self.employee.nama_lengkap, content)
        self.assertIn('STR', content)
        self.assertIn('Berlaku', content)

    def test_profile_card_marks_absent_license(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        content = response.content.decode('utf-8')
        self.assertIn('Belum ada', content)

    def test_hc_form_keeps_employee_field(self):
        from sdm.forms import PengajuanKredensialForm
        from sdm.models import HcGrant
        from accounts.models import RolePermissionConfig, UserProfile
        manager = get_user_model().objects.create_user(username='d1-manager')
        UserProfile.objects.create(user=manager, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.save(update_fields=['can_view_hc', 'can_review_hc_credentials', 'updated_at'])
        HcGrant.objects.create(user=manager, capability='can_view_hc', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=manager, capability='can_review_hc_credentials', unit_kerja=self.unit,
        )
        form = PengajuanKredensialForm(user=manager)
        self.assertIn('employee', form.fields)


class PortalChecklistD2Tests(PortalBase):
    """D-2: the checklist appears on the portal before submitting."""

    def setUp(self):
        super().setUp()
        self._portal_user(username='c5-staff', employee=self.employee)

    def test_checklist_hidden_until_jenis_chosen(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        self.assertNotContains(response, 'Kelengkapan Dokumen Pendukung')

    def test_checklist_renders_three_states_when_jenis_chosen(self):
        from sdm.models import DokumenPegawai, VersiDokumen
        valid = DokumenPegawai.objects.create(
            employee=self.employee, document_type='CREDENTIAL', jenis_berkas='CV',
            title='CV', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=valid, version_number=1, original_filename='cv.pdf',
            storage_key='p/cv.pdf', sha256='a' * 64, size_bytes=1,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today + timedelta(days=400),
        )
        expired = DokumenPegawai.objects.create(
            employee=self.employee, document_type='PROFESSIONAL',
            jenis_berkas='KEANGGOTAAN', title='KTA', sensitivity='personnel',
        )
        VersiDokumen.objects.create(
            document=expired, version_number=1, original_filename='kta.pdf',
            storage_key='p/kta.pdf', sha256='b' * 64, size_bytes=1,
            content_type='application/pdf', status='VERIFIED',
            valid_until=self.today - timedelta(days=1),
        )
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('sdm:kredensial_pengajuan_sendiri'), {'jenis': 'REKREDENSIAL'}
        )
        content = response.content.decode('utf-8')
        self.assertIn('Kelengkapan Dokumen Pendukung', content)
        self.assertIn('Aktif', content)
        self.assertIn('Kadaluarsa', content)
        self.assertIn('Belum Diunggah', content)

    def test_checklist_does_not_create_saved_rows(self):
        from sdm.models.kredensial import DokumenSyaratKredensial
        self.client.force_login(self.user)
        self.client.get(
            reverse('sdm:kredensial_pengajuan_sendiri'), {'jenis': 'AWAL'}
        )
        self.assertEqual(DokumenSyaratKredensial.objects.count(), 0)

    def test_portal_upload_redirects_back_to_chosen_jenis(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile('cv.pdf', b'%PDF-1.4', content_type='application/pdf')
        response = self.client.post(reverse('sdm:portal_dokumen_upload'), {
            'jenis_berkas': 'CV',
            'berkas': upload,
            'next_jenis': 'REKREDENSIAL',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn('jenis=REKREDENSIAL', response.url)

    def test_upload_switches_state_to_aktif(self):
        self.client.force_login(self.user)
        upload = SimpleUploadedFile('cv.pdf', b'%PDF-1.4', content_type='application/pdf')
        self.client.post(reverse('sdm:portal_dokumen_upload'), {
            'jenis_berkas': 'CV', 'berkas': upload,
        })
        response = self.client.get(
            reverse('sdm:kredensial_pengajuan_sendiri'), {'jenis': 'AWAL'}
        )
        self.assertIn('Aktif', response.content.decode('utf-8'))
