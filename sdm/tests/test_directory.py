from datetime import timedelta
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DrafInputPegawai,
    DokumenPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
)


class PegawaiDirectoryViewTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.root = UnitKerja.objects.create(name='Direktorat HC', code='DIR-HC')
        self.child = UnitKerja.objects.create(
            name='Unit Turunan', code='DIR-HC-CH', parent=self.root
        )
        self.other = UnitKerja.objects.create(name='Unit Rahasia', code='DIR-OTHER')
        self.reader = self._user('hr-reader')
        self.manager = self._user('hr-manager')
        self._grant(self.reader, 'can_view_hc', self.root)
        self._grant(self.manager, 'can_view_hc', self.root)
        self._grant(self.manager, 'can_manage_hc_employees', self.root)
        self.visible = self._employee('Pegawai Terlihat', 'VISIBLE-1', self.root)
        self.hidden = self._employee('Pegawai Rahasia', 'SECRET-1', self.other)

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.root)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_manage_hc_employees = True
        config.save(update_fields=['can_view_hc', 'can_manage_hc_employees', 'updated_at'])
        return user

    def _grant(self, user, capability, unit):
        return HcGrant.objects.create(user=user, capability=capability, unit_kerja=unit)

    def _employee(self, name, number, unit):
        employee = Pegawai.objects.create(
            nama_lengkap=name,
            nomor_pegawai=number,
            kategori='NON_PPA',
            profesi='Administrasi',
            status='AKTIF',
        )
        PenempatanPegawai.objects.create(
            pegawai=employee,
            unit_kerja=unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        return employee

    def test_directory_search_and_pagination_stay_inside_grant_scope(self):
        for index in range(26):
            self._employee(f'Directory Staff {index:02}', f'DIR-{index:03}', self.root)
        self._employee('Directory Secret', 'DIR-SECRET', self.other)
        self.client.force_login(self.reader)

        response = self.client.get(reverse('sdm:pegawai_list'), {'q': 'Directory', 'page': 2})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 26)
        self.assertEqual(len(response.context['page_obj'].object_list), 1)
        self.assertNotContains(response, 'Directory Secret')

    def test_directory_unit_filter_fails_closed_for_foreign_unit(self):
        self.client.force_login(self.reader)

        response = self.client.get(
            reverse('sdm:pegawai_list'), {'unit': str(self.other.pk)}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['page_obj'].paginator.count, 0)

    def test_action_header_has_an_accessible_name_without_offscreen_text(self):
        self.client.force_login(self.reader)

        response = self.client.get(reverse('sdm:pegawai_list'))

        self.assertContains(
            response, '<th scope="col" aria-label="Aksi"></th>', html=True
        )
        self.assertNotContains(
            response, '<span class="visually-hidden">Aksi</span>', html=True
        )

    def test_foreign_employee_detail_is_not_found(self):
        self.client.force_login(self.reader)

        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.hidden.pk})
        )

        self.assertEqual(response.status_code, 404)

    def test_resumed_step_renders_previous_link_for_same_draft(self):
        self.client.force_login(self.manager)
        draft = DrafInputPegawai.objects.create(
            owner=self.manager, current_step=2, version=1,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={'1': {'nama_depan': 'Fixture'}},
        )
        response = self.client.get(reverse('sdm:pegawai_wizard_resume', kwargs={
            'step': 2, 'draft_id': draft.pk,
        }))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('sdm:pegawai_wizard_resume', kwargs={
            'step': 1, 'draft_id': draft.pk,
        }))
        self.assertContains(response, 'name="expected_version"')
        self.assertContains(response, 'enctype="multipart/form-data"')

    def test_stale_draft_post_does_not_overwrite_saved_step(self):
        self.client.force_login(self.manager)
        draft = DrafInputPegawai.objects.create(
            owner=self.manager, current_step=2, version=2,
            expires_at=timezone.now() + timedelta(days=1),
            draft_data={'1': {'nama_depan': 'Current'}},
        )
        response = self.client.post(reverse('sdm:pegawai_wizard_resume', kwargs={
            'step': 1, 'draft_id': draft.pk,
        }), {'nama_depan': 'Stale', 'expected_version': '1'})
        self.assertEqual(response.status_code, 409)
        draft.refresh_from_db()
        self.assertEqual(draft.version, 2)
        self.assertEqual(draft.draft_data['1']['nama_depan'], 'Current')

    def test_detail_shows_personal_and_legal_sections(self):
        from sdm.models import ProfilPribadiPegawai
        ProfilPribadiPegawai.objects.create(
            employee=self.visible, nik='3201010101010001',
            nama_depan='Pegawai', nama_belakang='Terlihat',
            telepon='081234567890', alamat_ktp='Jl. Merdeka 1',
        )
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '3201010101010001')
        self.assertContains(response, '081234567890')
        self.assertContains(response, 'Identitas Pribadi')

    def test_detail_masks_personal_data_for_a_view_only_grant(self):
        from sdm.models import ProfilPribadiPegawai
        ProfilPribadiPegawai.objects.create(
            employee=self.visible, nik='3201010101010001',
            tanggal_lahir=timezone.localdate() - timedelta(days=10000),
            telepon='081299988877', email_terverifikasi='private@example.test',
            alamat_ktp='Jl. Privat 9',
        )
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '3201010101010001')
        self.assertNotContains(response, '081299988877')
        self.assertNotContains(response, 'private@example.test')
        self.assertNotContains(response, 'Jl. Privat 9')
        self.assertContains(response, 'Tersembunyi')

    def test_avatar_requires_a_view_grant(self):
        import hashlib
        from datetime import timedelta as _td
        from unittest.mock import Mock, patch
        from django.utils import timezone as _tz
        from sdm.models import DokumenPegawai, ProfilPribadiPegawai, VersiDokumen
        photo = b'\xff\xd8\xff' + b'jpeg-avatar'
        document = DokumenPegawai.objects.create(
            employee=self.visible, document_type='IDENTITY', jenis_berkas='FOTO',
            title='Pas Foto', sensitivity='personnel',
        )
        version = VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='foto.jpg',
            storage_key=f'personnel/{self.visible.pk}/{uuid.uuid4()}.jpg',
            sha256=hashlib.sha256(photo).hexdigest(), size_bytes=len(photo),
            content_type='image/jpeg', status='VERIFIED',
            valid_until=_tz.localdate() + _td(days=365),
        )
        ProfilPribadiPegawai.objects.create(
            employee=self.visible, foto_profil_versi=version,
        )
        storage = Mock()
        storage.fetch_object.return_value = photo
        self.client.force_login(self.reader)
        with patch('sdm.views.get_private_storage', return_value=storage):
            response = self.client.get(
                reverse('sdm:pegawai_avatar', kwargs={'employee_id': self.visible.pk})
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, photo)
        self.assertEqual(response['Content-Type'], 'image/jpeg')
        self.client.force_login(self._user('unscoped-photo-reader'))
        with patch('sdm.views.get_private_storage', return_value=storage):
            response = self.client.get(
                reverse('sdm:pegawai_avatar', kwargs={'employee_id': self.visible.pk})
            )
        self.assertEqual(response.status_code, 404)

    def test_avatar_refuses_a_photo_document_owned_by_another_employee(self):
        from sdm.models import DokumenPegawai, ProfilPribadiPegawai, VersiDokumen
        document = DokumenPegawai.objects.create(
            employee=self.hidden, document_type='IDENTITY', jenis_berkas='FOTO',
            title='Foto pegawai lain', sensitivity='personnel',
        )
        version = VersiDokumen.objects.create(
            document=document, version_number=1, original_filename='foto.jpg',
            storage_key=f'personnel/{self.hidden.pk}/{uuid.uuid4()}.jpg',
            sha256='a' * 64, size_bytes=10, content_type='image/jpeg',
            status='VERIFIED',
        )
        ProfilPribadiPegawai.objects.create(
            employee=self.visible, foto_profil_versi=version,
        )
        self.client.force_login(self.reader)
        response = self.client.get(
            reverse('sdm:pegawai_avatar', kwargs={'employee_id': self.visible.pk})
        )
        self.assertEqual(response.status_code, 404)

    def test_create_employee_uses_scoped_unit_and_assignment_service(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse('sdm:pegawai_create'), {
            'nama_depan': 'Pegawai Baru',
            'nama_belakang': 'Wizard',
        })
        self.assertEqual(response.status_code, 302)

        draft = DrafInputPegawai.objects.filter(owner=self.manager).order_by('-pk').first()
        response = self.client.post(
            reverse('sdm:pegawai_wizard_resume', kwargs={'step': 2, 'draft_id': draft.pk}),
            {
                'nomor_pegawai': 'NEW-HC-001',
                'kategori': 'NON_PPA',
                'profesi': 'Administrasi',
                'jabatan': 'Staf',
                'status': 'AKTIF',
                'kategori_pegawai': 'TETAP',
                'unit_kerja': self.root.pk,
                'tanggal_mulai': self.today.isoformat(),
                'tanggal_selesai': '',
                'alokasi_fte': '0.75',
                'expected_version': str(draft.version),
            },
        )
        self.assertEqual(response.status_code, 302)

        for step in (3, 4, 5):
            draft.refresh_from_db()
            response = self.client.post(
                reverse('sdm:pegawai_wizard_resume', kwargs={
                    'step': step, 'draft_id': draft.pk,
                }),
                {'expected_version': str(draft.version)},
            )
            self.assertEqual(response.status_code, 302)

        draft.refresh_from_db()
        response = self.client.post(
            reverse('sdm:pegawai_intake_finalize', kwargs={'draft_id': draft.pk}),
            {'expected_version': str(draft.version)},
        )
        self.assertEqual(response.status_code, 302)

        employee = Pegawai.objects.get(nomor_pegawai='NEW-HC-001')
        assignment = employee.penempatan.get()
        self.assertEqual(assignment.unit_kerja, self.root)
        self.assertEqual(assignment.alokasi_fte, Decimal('0.75'))
        self.assertTrue(PeristiwaSDM.objects.filter(
            actor=self.manager,
            jenis_peristiwa='employee_created',
            target_id=str(employee.pk),
        ).exists())

    def test_tampered_foreign_unit_does_not_create_employee(self):
        self.client.force_login(self.manager)

        response = self.client.post(reverse('sdm:pegawai_create'), {
            'nomor_pegawai': 'NEW-HC-002',
            'nama_lengkap': 'Pegawai Terlarang',
            'kategori': 'NON_PPA',
            'profesi': 'Administrasi',
            'jabatan': 'Staf',
            'status': 'AKTIF',
            'unit_kerja': self.other.pk,
            'tanggal_mulai': self.today.isoformat(),
            'tanggal_selesai': '',
            'alokasi_fte': '1.00',
        })

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Pegawai.objects.filter(nomor_pegawai='NEW-HC-002').exists())

    def test_directory_requires_a_valid_view_grant(self):
        user = self._user('unscoped-user')
        self.client.force_login(user)

        response = self.client.get(reverse('sdm:pegawai_list'))

        self.assertEqual(response.status_code, 403)

    def test_employee_detail_hides_health_documents_and_health_activity(self):
        DokumenPegawai.objects.create(
            employee=self.visible,
            document_type='HEALTH',
            title='Rahasia MCU Pegawai',
            sensitivity='health',
        )
        PeristiwaSDM.objects.create(
            actor=self.reader,
            jenis_peristiwa='hc_health_record_view',
            target_tipe='employee',
            target_id=str(self.visible.pk),
            alasan='Konteks klinis privat',
        )
        self.client.force_login(self.reader)

        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Rahasia MCU Pegawai')
        self.assertNotContains(response, 'hc_health_record_view')
        self.assertNotContains(response, 'Konteks klinis privat')

    def test_employee_detail_fails_closed_for_misclassified_health_document(self):
        DokumenPegawai.objects.create(
            employee=self.visible,
            document_type='HEALTH',
            title='MCU Salah Klasifikasi',
            sensitivity='personnel',
        )
        self.client.force_login(self.reader)

        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'MCU Salah Klasifikasi')

    def test_employee_edit_updates_identity_and_records_activity(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse('sdm:pegawai_edit', kwargs={'employee_id': self.visible.pk}),
            {
                'nomor_pegawai': self.visible.nomor_pegawai,
                'nama_lengkap': 'Nama Diperbarui',
                'kategori': self.visible.kategori,
                'profesi': self.visible.profesi,
                'jabatan': self.visible.jabatan,
                'status': self.visible.status,
            },
        )

        self.assertEqual(response.status_code, 302)
        self.visible.refresh_from_db()
        self.assertEqual(self.visible.nama_lengkap, 'Nama Diperbarui')
        self.assertTrue(PeristiwaSDM.objects.filter(
            actor=self.manager,
            jenis_peristiwa='employee_updated',
            target_id=str(self.visible.pk),
        ).exists())

    def test_view_only_grant_cannot_edit_employee(self):
        self.client.force_login(self.reader)

        response = self.client.get(
            reverse('sdm:pegawai_edit', kwargs={'employee_id': self.visible.pk})
        )

        self.assertEqual(response.status_code, 403)

    def test_detail_shows_only_assignments_in_the_granted_scope(self):
        PenempatanPegawai.objects.create(
            pegawai=self.visible,
            unit_kerja=self.other,
            tanggal_mulai=self.today - timedelta(days=2),
            alokasi_fte=Decimal('0.25'),
        )
        self.client.force_login(self.reader)

        response = self.client.get(
            reverse('sdm:pegawai_detail', kwargs={'employee_id': self.visible.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'DIR-HC — Direktorat HC')
        self.assertNotContains(response, 'DIR-OTHER — Unit Rahasia')
