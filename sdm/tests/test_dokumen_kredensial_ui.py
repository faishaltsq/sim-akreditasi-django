"""Fase 3.5: HTTP wiring for credential document generate, edit, finalize, download."""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    DrafDokumenKredensial,
    Pegawai,
    PenempatanPegawai,
    VersiDokumen,
)
from sdm.storage_backend import SupabasePrivateStorage
from sdm.tests.test_dokumen_kredensial import pdf_text
from sdm.tests.test_storage_backend import FakeResponse, FakeSession

GUIDANCE = 'Akun Anda belum terhubung dengan data pegawai'


class DokumenKredensialUIBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Poli Dokumen', code='UI-DOK')
        self.user = self._user('dok-pemilik')
        self.pegawai = Pegawai.objects.create(
            nama_lengkap='Perawat Dokumen UI', kategori='PPA', profesi='Perawat',
            nomor_pegawai='PGW-UI-01', jabatan='Perawat Pelaksana', akun=self.user,
        )
        PenempatanPegawai.objects.create(
            pegawai=self.pegawai, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        self.other_user = self._user('dok-lain')
        self.other_pegawai = Pegawai.objects.create(
            nama_lengkap='Perawat Lain', kategori='PPA', profesi='Perawat',
            nomor_pegawai='PGW-UI-02', akun=self.other_user,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='STAF_NAKES', unit_kerja=self.unit)
        return user

    def _storage(self):
        """Uploads hit a fake session; fetches serve the bytes finalize really made."""
        session = FakeSession(FakeResponse(200, content=b''))
        storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co',
            api_key='service-key',
            bucket='hc-private',
            session=session,
        )
        served = {}

        def fetch_object(storage_key, **kwargs):
            return served[storage_key]

        storage.fetch_object = fetch_object
        self.served = served
        original_upload = storage.upload

        def upload(file_obj, **kwargs):
            payload = file_obj.getvalue()
            stored = original_upload(file_obj, **kwargs)
            served[stored.storage_key] = payload
            return stored

        storage.upload = upload
        return session, storage


class GenerateTests(DokumenKredensialUIBase):
    def test_generate_post_creates_draft_and_redirects(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('sdm:dokumen_kredensial_generate', args=['CV']),
        )
        self.assertRedirects(response, reverse('sdm:kredensial_pengajuan_sendiri'))
        draft = DrafDokumenKredensial.objects.get(pegawai=self.pegawai, jenis='CV')
        self.assertEqual(draft.status, 'DRAF')
        self.assertEqual(draft.created_by, self.user)

    def test_generate_get_is_method_not_allowed(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('sdm:dokumen_kredensial_generate', args=['CV']),
        )
        self.assertEqual(response.status_code, 405)
        self.assertFalse(DrafDokumenKredensial.objects.exists())

    def test_finalize_get_is_method_not_allowed(self):
        self.client.force_login(self.user)
        self.client.post(reverse('sdm:dokumen_kredensial_generate', args=['CV']))
        response = self.client.get(
            reverse('sdm:dokumen_kredensial_finalize', args=['CV']),
        )
        self.assertEqual(response.status_code, 405)


class EditTests(DokumenKredensialUIBase):
    def test_edit_stores_only_filled_manual_fields(self):
        self.client.force_login(self.user)
        self.client.post(reverse('sdm:dokumen_kredensial_generate', args=['KEANGGOTAAN']))

        page = self.client.get(
            reverse('sdm:dokumen_kredensial_edit', args=['KEANGGOTAAN']),
        )
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Simpan Isian')

        response = self.client.post(
            reverse('sdm:dokumen_kredensial_edit', args=['KEANGGOTAAN']),
            {
                'pernyataan': '  Saya anggota aktif PPNI.  ',
                'nama_organisasi': 'PPNI',
                'nomor_anggota': '   ',
            },
        )
        self.assertRedirects(
            response, reverse('sdm:dokumen_kredensial_edit', args=['KEANGGOTAAN']),
        )
        draft = DrafDokumenKredensial.objects.get(
            pegawai=self.pegawai, jenis='KEANGGOTAAN',
        )
        self.assertEqual(draft.isian, {
            'pernyataan': 'Saya anggota aktif PPNI.',
            'nama_organisasi': 'PPNI',
        })

        # The stored manual answers reach the rendered PDF.
        from sdm.services.dokumen_kredensial import render_pdf
        text = pdf_text(render_pdf(draft))
        self.assertIn('Saya anggota aktif PPNI.', text)
        self.assertIn('PPNI', text)

    def test_another_employees_draft_is_404(self):
        DrafDokumenKredensial.objects.create(
            pegawai=self.other_pegawai, jenis='CV', created_by=self.other_user,
        )
        self.client.force_login(self.user)
        for name in ('dokumen_kredensial_edit', 'dokumen_kredensial_finalize',
                     'dokumen_kredensial_download'):
            with self.subTest(view=name):
                method = self.client.post if name != 'dokumen_kredensial_edit' else self.client.get
                response = method(reverse(f'sdm:{name}', args=['CV']))
                self.assertEqual(response.status_code, 404)

    def test_download_never_returns_another_employees_pdf(self):
        session, storage = self._storage()
        with patch('sdm.views.get_private_storage', return_value=storage), patch('sdm.storage.get_private_storage', return_value=storage):
            self.client.force_login(self.other_user)
            self.client.post(reverse('sdm:dokumen_kredensial_generate', args=['CV']))
            self.client.post(reverse('sdm:dokumen_kredensial_finalize', args=['CV']))

        self.client.force_login(self.user)
        response = self.client.get(
            reverse('sdm:dokumen_kredensial_download', args=['CV']),
        )
        self.assertEqual(response.status_code, 404)


class FinalizeAndDownloadTests(DokumenKredensialUIBase):
    def test_finalize_creates_version_and_download_returns_pdf(self):
        session, storage = self._storage()
        with patch('sdm.views.get_private_storage', return_value=storage), patch('sdm.storage.get_private_storage', return_value=storage):
            self.client.force_login(self.user)
            self.client.post(reverse('sdm:dokumen_kredensial_generate', args=['CV']))
            response = self.client.post(
                reverse('sdm:dokumen_kredensial_finalize', args=['CV']),
            )
            self.assertRedirects(
                response, reverse('sdm:dokumen_kredensial_download', args=['CV']),
            )
            self.assertEqual(VersiDokumen.objects.count(), 1)
            version = VersiDokumen.objects.get()
            self.assertEqual(version.document.jenis_berkas, 'CV')
            self.assertEqual(
                DokumenPegawai.objects.filter(employee=self.pegawai).count(), 1,
            )

            download = self.client.get(
                reverse('sdm:dokumen_kredensial_download', args=['CV']),
            )
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download['Content-Type'], 'application/pdf')
        self.assertIn('attachment;', download['Content-Disposition'])
        self.assertIn('Perawat Dokumen UI', download['Content-Disposition'])
        self.assertTrue(bytes(download.content).startswith(b'%PDF'))

    def test_download_without_final_version_redirects_with_message(self):
        self.client.force_login(self.user)
        self.client.post(reverse('sdm:dokumen_kredensial_generate', args=['CV']))

        response = self.client.get(
            reverse('sdm:dokumen_kredensial_download', args=['CV']),
            follow=True,
        )
        self.assertRedirects(
            response, reverse('sdm:dokumen_kredensial_edit', args=['CV']),
        )
        self.assertContains(response, 'belum difinalkan')

    def test_download_without_any_draft_returns_404(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse('sdm:dokumen_kredensial_download', args=['CV']),
        )
        self.assertEqual(response.status_code, 404)


class UnlinkedAccountTests(DokumenKredensialUIBase):
    def test_all_four_urls_redirect_with_guidance(self):
        user = get_user_model().objects.create_user(username='dok-tanpa-pegawai')
        UserProfile.objects.create(user=user, role='STAF_NAKES', unit_kerja=self.unit)
        self.client.force_login(user)

        cases = [
            ('dokumen_kredensial_generate', self.client.post),
            ('dokumen_kredensial_edit', self.client.get),
            ('dokumen_kredensial_finalize', self.client.post),
            ('dokumen_kredensial_download', self.client.get),
        ]
        for name, method in cases:
            with self.subTest(view=name):
                response = method(reverse(f'sdm:{name}', args=['CV']), follow=True)
                self.assertRedirects(response, reverse('akreditasi:dashboard'))
                self.assertContains(response, GUIDANCE)


class TemplateActionTests(DokumenKredensialUIBase):
    def _page(self):
        return self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))

    def test_auto_generate_shown_before_draft_and_unduh_pdf_only_after_finalize(self):
        session, storage = self._storage()
        self.client.force_login(self.user)

        page = self._page()
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Auto-Generate')
        self.assertNotContains(
            page, reverse('sdm:dokumen_kredensial_download', args=['CV']),
        )

        self.client.post(reverse('sdm:dokumen_kredensial_generate', args=['CV']))
        page = self._page()
        self.assertContains(page, reverse('sdm:dokumen_kredensial_edit', args=['CV']))
        self.assertNotContains(
            page, reverse('sdm:dokumen_kredensial_download', args=['CV']),
        )

        with patch('sdm.views.get_private_storage', return_value=storage), patch('sdm.storage.get_private_storage', return_value=storage):
            self.client.post(reverse('sdm:dokumen_kredensial_finalize', args=['CV']))
        page = self._page()
        self.assertContains(page, 'Unduh PDF')
        self.assertContains(
            page, reverse('sdm:dokumen_kredensial_download', args=['CV']),
        )

    def test_upload_only_rows_say_so(self):
        self.client.force_login(self.user)
        page = self._page()
        self.assertContains(page, 'Hanya dapat diunggah sebagai berkas.')
        self.assertNotContains(
            page, reverse('sdm:dokumen_kredensial_generate', args=['MCU']),
        )
