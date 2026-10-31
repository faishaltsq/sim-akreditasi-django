"""Every logged-in nakes employee sees "Kredensial saya", even with zero grants."""
from datetime import timedelta
from decimal import Decimal

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from sdm.models import HcGrant, KatalogTindakan, MasterJenjangProfesi, MasterProfesiPegawai
from sdm.models.logbook import EntriLogbookKlinis
from sdm.models.pegawai import Pegawai, PenempatanPegawai


class KredensialPribadiMenuBase(TestCase):
    def setUp(self):
        cache.clear()
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli Nav Pribadi', code='NAV-PRB')

    def _employee(self, name, *, user=None):
        employee = Pegawai.objects.create(
            nama_lengkap=name, kategori='PPA', profesi='Perawat', akun=user,
        )
        PenempatanPegawai.objects.create(
            pegawai=employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        return employee

    def _nakes(self, username, *, employee=True):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='STAF_NAKES', unit_kerja=self.unit)
        if employee:
            self._employee(f'Pegawai {username}', user=user)
        return user

    def _sidebar(self, user):
        self.client.force_login(user)
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        return response.content.decode('utf-8')


class SidebarKredensialPribadiTests(KredensialPribadiMenuBase):
    def test_nakes_with_linked_pegawai_sees_both_links_without_any_grant(self):
        user = self._nakes('nakes-linked')
        self.assertFalse(HcGrant.objects.filter(user=user).exists())

        body = self._sidebar(user)

        self.assertIn('Kredensial saya', body)
        self.assertIn('Pengajuan kredensial', body)
        self.assertIn('Logbook saya (5 Tahun)', body)
        self.assertIn('Logbook terpadu', body)
        self.assertIn(reverse('sdm:kredensial_pengajuan_sendiri'), body)
        self.assertIn(reverse('sdm:logbook_list'), body)
        self.assertIn(reverse('akreditasi:logbook_daftar'), body)

    def test_menu_links_are_active_on_their_own_pages(self):
        user = self._nakes('nakes-active')
        self.client.force_login(user)

        page = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        self.assertContains(page, 'Pengajuan kredensial')
        self.assertContains(page, 'nav-link active', msg_prefix='pengajuan link active')

        page = self.client.get(reverse('sdm:logbook_list'))
        self.assertContains(page, 'Logbook saya (5 Tahun)')

    def test_nakes_without_linked_pegawai_still_sees_personal_menu(self):
        # Brief requirement: a STAF_NAKES account sees the menu even when it
        # has no Pegawai row; the target page then explains the missing link.
        user = self._nakes('nakes-unlinked', employee=False)

        body = self._sidebar(user)

        self.assertIn('Kredensial saya', body)
        self.assertIn(reverse('sdm:kredensial_pengajuan_sendiri'), body)

    def test_non_nakes_account_without_pegawai_sees_no_personal_menu(self):
        user = get_user_model().objects.create_user(username='asesor-nav')
        UserProfile.objects.create(user=user, role='ASESOR', unit_kerja=self.unit)

        body = self._sidebar(user)

        self.assertNotIn('Kredensial saya', body)
        self.assertNotIn('Logbook saya', body)

    def test_unlinked_non_nakes_can_open_normal_page(self):
        user = get_user_model().objects.create_user(username='asesor-page')
        UserProfile.objects.create(user=user, role='ASESOR', unit_kerja=self.unit)
        self.assertFalse(Pegawai.objects.filter(akun=user).exists())
        self.client.force_login(user)

        response = self.client.get(reverse('akreditasi:dashboard'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Kredensial saya')

    def test_superadmin_without_pegawai_does_not_see_personal_menu(self):
        user = get_user_model().objects.create_superuser(
            username='root-nav', password='x',
        )
        body = self._sidebar(user)
        self.assertNotIn('Kredensial saya', body)


class SelfServiceFallbackTests(KredensialPribadiMenuBase):
    def test_unlinked_account_gets_guidance_instead_of_500(self):
        user = self._nakes('nakes-fallback', employee=False)
        self.client.force_login(user)

        response = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('akreditasi:dashboard'))
        follow = self.client.get(response.url)
        self.assertContains(follow, 'belum terhubung dengan data pegawai')
        self.assertContains(follow, 'Hubungi bagian SDM')


class OwnEmployeeScopingTests(KredensialPribadiMenuBase):
    def test_nakes_cannot_read_another_employees_logbook(self):
        profesi = MasterProfesiPegawai.objects.create(
            code='P-NAV', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        jenjang = MasterJenjangProfesi.objects.create(
            profesi=profesi, kode='PK-NAV', nama='Perawat Klinis I', urutan=1,
        )
        katalog = KatalogTindakan.objects.create(
            kode='PR-NAV', nama='Pemasangan Infus Nav', jenjang=jenjang,
            tingkat_supervisi='M',
        )
        user = self._nakes('nakes-own')
        foreign = self._employee('Pegawai Asing Nav')
        EntriLogbookKlinis.objects.create(
            employee=foreign, tanggal=self.today, unit_kerja=self.unit,
            katalog_tindakan=katalog, jumlah_mandiri=5,
        )
        self.client.force_login(user)

        response = self.client.get(
            reverse('sdm:logbook_list'), {'pegawai': str(foreign.pk)}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Pegawai Asing Nav')
        self.assertNotContains(response, 'Pemasangan Infus Nav')
