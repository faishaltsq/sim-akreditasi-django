"""Tests for the Identitas Pribadi & BPJS module (Task 2).

Covers the editable personal-data slice, the BPJS participation model, the
card upload route, and the can_view_personal gate that keeps restricted data
away from viewers without the capability.
"""
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
    DataBpjsPegawai,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PeristiwaSDM,
    ProfilPribadiPegawai,
)
from sdm.services.intake import build_staff_profile


class ProfilPribadiBpjsTests(TestCase):
    def setUp(self):
        self.unit = UnitKerja.objects.create(name='Unit Identitas', code='HC-IDS')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Perawat Identitas', kategori='PPA', profesi='Perawat'
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee,
            unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        self.manager = self._make_user(
            'manajer-sdm',
            ['can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents'],
        )
        self.viewer = self._make_user('peninjau-sdm', ['can_view_hc'])
        self.client.force_login(self.manager)

    def _make_user(self, username, caps):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(
            user=user, role='ADMIN_RS', unit_kerja=self.unit
        )
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        for cap in caps:
            setattr(config, cap, True)
        config.save(update_fields=list(caps) + ['updated_at'])
        for cap in caps:
            HcGrant.objects.create(
                user=user, capability=cap, unit_kerja=self.unit, granted_by=user
            )
        return user

    def _payload(self, **overrides):
        payload = {
            'nama_depan': 'Dewi',
            'nama_belakang': 'Lestari',
            'tempat_lahir': 'Semarang',
            'tanggal_lahir': '1995-04-12',
            'gender': 'PEREMPUAN',
            'golongan_darah': 'O',
            'agama': 'ISLAM',
            'status_pernikahan': 'BELUM_KAWIN',
            'telepon': '081234567890',
            'email_terverifikasi': 'dewi@rs.test',
            'alamat_ktp': 'Jl. Pemuda 10',
            'rt_rw': '003/005',
            'kelurahan': 'Sekayu',
            'kecamatan': 'Semarang Tengah',
            'kabupaten_kota': 'Kota Semarang',
            'provinsi': 'Jawa Tengah',
            'kode_pos': '50132',
            'alamat_domisili': 'Jl. Pemuda 10',
            'alamat_sama_dengan_ktp': 'on',
            'no_bpjs_kesehatan': '0001234567890',
            'status_bpjs_kesehatan': 'AKTIF',
            'faskes_1': 'Puskesmas Sekayu',
            'kelas_rawat': 'KELAS_2',
            'tanggungan_keluarga': '2',
            'no_bpjs_tk': 'KPJ1234567',
            'status_bpjs_tk': 'AKTIF',
            'tmt_bpjs_tk': '2020-03-01',
            'program_jkm': 'on',
            'program_jkk': 'on',
            'program_jht': 'on',
        }
        payload.update(overrides)
        return payload

    def test_post_saves_new_address_fields_and_bpjs(self):
        response = self.client.post(
            reverse('sdm:profil_pribadi_edit', args=[self.employee.pk]),
            self._payload(),
        )
        self.assertEqual(response.status_code, 302)
        personal = ProfilPribadiPegawai.objects.get(employee=self.employee)
        self.assertEqual(personal.golongan_darah, 'O')
        self.assertEqual(personal.rt_rw, '003/005')
        self.assertEqual(personal.kelurahan, 'Sekayu')
        self.assertEqual(personal.kecamatan, 'Semarang Tengah')
        self.assertEqual(personal.kabupaten_kota, 'Kota Semarang')
        self.assertEqual(personal.provinsi, 'Jawa Tengah')
        self.assertEqual(personal.kode_pos, '50132')
        bpjs = DataBpjsPegawai.objects.get(employee=self.employee)
        self.assertEqual(bpjs.no_bpjs_kesehatan, '0001234567890')
        self.assertEqual(bpjs.status_bpjs_kesehatan, 'AKTIF')
        self.assertEqual(bpjs.kelas_rawat, 'KELAS_2')
        self.assertEqual(bpjs.no_bpjs_tk, 'KPJ1234567')
        self.assertTrue(bpjs.program_jkm)
        self.assertFalse(bpjs.program_jp)
        self.assertEqual(
            PeristiwaSDM.objects.filter(kategori='UPDATE_PROFILE').count(), 1
        )

    def test_invalid_post_does_not_create_records(self):
        response = self.client.post(
            reverse('sdm:profil_pribadi_edit', args=[self.employee.pk]),
            self._payload(kode_pos='ABC'),
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            ProfilPribadiPegawai.objects.filter(employee=self.employee).exists()
        )
        self.assertFalse(
            DataBpjsPegawai.objects.filter(employee=self.employee).exists()
        )

    def test_viewer_without_manage_capability_is_denied(self):
        self.client.force_login(self.viewer)
        response = self.client.post(
            reverse('sdm:profil_pribadi_edit', args=[self.employee.pk]),
            self._payload(),
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            ProfilPribadiPegawai.objects.filter(employee=self.employee).exists()
        )

    def test_build_staff_profile_hides_bpjs_from_viewer(self):
        DataBpjsPegawai.objects.create(
            employee=self.employee,
            no_bpjs_kesehatan='0009998887777',
            status_bpjs_kesehatan='AKTIF',
        )
        viewer_profile = build_staff_profile(self.employee, viewer=self.viewer)
        self.assertIsNone(viewer_profile['bpjs_kesehatan'])
        self.assertIsNone(viewer_profile['bpjs_tk'])
        manager_profile = build_staff_profile(self.employee, viewer=self.manager)
        self.assertIsNotNone(manager_profile['bpjs_kesehatan'])
        self.assertEqual(
            manager_profile['bpjs_kesehatan'].no_bpjs_kesehatan,
            '0009998887777',
        )

    def test_bpjs_card_upload_links_document_version(self):
        upload = SimpleUploadedFile(
            'kartu-bpjs-tk.pdf', b'%PDF-1.4 fake', content_type='application/pdf'
        )
        response = self.client.post(
            reverse(
                'sdm:bpjs_kartu_upload',
                args=[self.employee.pk, 'BPJS_TK'],
            ),
            {'file': upload},
        )
        self.assertEqual(response.status_code, 302)
        bpjs = DataBpjsPegawai.objects.get(employee=self.employee)
        self.assertIsNotNone(bpjs.kartu_tk_versi)
        self.assertIsNone(bpjs.kartu_kesehatan_versi)
        self.assertEqual(
            bpjs.kartu_tk_versi.document.jenis_berkas, 'BPJS_TK'
        )

    def test_bpjs_card_upload_rejects_unknown_kind(self):
        response = self.client.post(
            reverse(
                'sdm:bpjs_kartu_upload',
                args=[self.employee.pk, 'KTP'],
            ),
            {},
        )
        self.assertEqual(response.status_code, 404)

    def test_bpjs_card_upload_requires_a_file(self):
        response = self.client.post(
            reverse(
                'sdm:bpjs_kartu_upload',
                args=[self.employee.pk, 'BPJS_KESEHATAN'],
            ),
            {},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(
            DataBpjsPegawai.objects.filter(employee=self.employee).exists()
        )
