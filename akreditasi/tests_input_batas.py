"""Batas input HTTP — mengunci temuan QA 2026-10-27.

Sebelum perbaikan, 10 endpoint menjawab 500 ketika pengguna mengirim nilai
non-numerik lewat query string, form, atau body JSON. Yang diuji di sini
adalah kode status untuk masukan yang tidak valid, bukan isi tampilan.
"""
import json
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounts.models import UserProfile
from akreditasi.models import QualityRecord, UnitKerja
from akreditasi.tests_utils import reset_rate_limit

User = get_user_model()


class InputBatasTestCase(TestCase):
    """Fixture bersama: admin RS yang berwenang di semua modul tulis."""

    def setUp(self):
        reset_rate_limit()
        self.user = User.objects.create_user('qa.input', 'qa.input@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = 'ADMIN_RS'
        profile.save()
        self.client = Client()
        self.client.force_login(self.user)
        self.unit = UnitKerja.objects.create(code='QA-INPUT', name='QA Input', level=2)


class QueryParamNonNumerikTest(InputBatasTestCase):
    def test_export_csv_risiko_menolak_unit_non_angka(self):
        for url in (
            '/risiko/perencanaan/export-csv/?unit=abc',
            '/risiko/pelaksanaan/export-csv/?unit=abc',
            '/risiko/monitoring-evaluasi/export-csv/?unit=abc',
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)

    def test_laporan_risiko_menolak_tahun_non_angka(self):
        response = self.client.get('/risiko/laporan/?tahun=abc')
        self.assertEqual(response.status_code, 200)
        # Nilai rusak jatuh ke tahun bawaan, bukan melempar 500.
        self.assertEqual(response.context['tahun'], '2026')

    def test_fmea_rca_menolak_unit_non_angka(self):
        self.assertEqual(self.client.get('/risiko/fmea-rca/?unit=abc').status_code, 200)

    def test_komparasi_indikator_menolak_tahun_non_angka(self):
        response = self.client.get('/indikator-mutu/api/komparasi-unit/?tahun=abc')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['success'])

    def test_komparasi_indikator_menolak_bulan_di_luar_rentang(self):
        self.assertEqual(
            self.client.get('/indikator-mutu/api/komparasi-unit/?bulan=13').status_code, 400
        )


class BodyJsonNonValidTest(InputBatasTestCase):
    def setUp(self):
        super().setUp()
        # QualityRecord.standard_item adalah OneToOne, jadi tiap tes butuh EP baru.
        from akreditasi.models import Category, Framework, StandardItem, active_framework
        framework = active_framework() or Framework.objects.first()
        category = Category.objects.create(
            name='QA Batas', order=99, framework=framework,
        )
        item = StandardItem.objects.create(
            category=category, sub_standard='QA', sub_title='QA',
            code='QA-IB', description='QA input batas',
        )
        self.record = QualityRecord.objects.create(
            standard_item=item, unit=self.unit, score=0,
        )

    def _post(self, url, payload):
        if isinstance(payload, str):
            return self.client.post(url, data=payload, content_type='application/json')
        return self.client.post(url, data=json.dumps(payload), content_type='application/json')

    def test_quick_score_menolak_skor_non_angka(self):
        response = self._post(f'/ep/record/{self.record.pk}/quick-score/', {'score': 'abc'})
        self.assertEqual(response.status_code, 400)
        self.record.refresh_from_db()
        self.assertEqual(self.record.score, 0)

    def test_quick_score_menolak_body_bukan_json(self):
        response = self._post(f'/ep/record/{self.record.pk}/quick-score/', 'bukan json')
        self.assertEqual(response.status_code, 400)

    def test_inline_edit_est_cost_desimal_tersimpan(self):
        response = self._post(
            f'/ep/record/{self.record.pk}/inline-edit/',
            {'field': 'est_cost', 'value': '2.500.000'},
        )
        self.assertEqual(response.status_code, 200)
        self.record.refresh_from_db()
        self.assertEqual(self.record.est_cost, Decimal('2500000'))

    def test_inline_edit_menolak_body_bukan_json(self):
        response = self._post(f'/ep/record/{self.record.pk}/inline-edit/', 'bukan json')
        self.assertEqual(response.status_code, 400)

    def test_link_berkas_id_tidak_ada_menjawab_404(self):
        response = self._post('/ep/bukti/link/', {'req_id': 999999, 'file_id': 999999})
        self.assertEqual(response.status_code, 404)
        self.assertFalse(response.json()['success'])

    def test_link_berkas_menolak_body_bukan_json(self):
        response = self._post('/ep/bukti/link/', 'bukan json')
        self.assertEqual(response.status_code, 400)


class FormNonNumerikTest(InputBatasTestCase):
    def test_profil_rs_menolak_tahun_non_angka(self):
        response = self.client.post(
            '/profil/', {'name': 'RS Uji', 'akreditasi_tahun': 'bukan-angka'}
        )
        self.assertEqual(response.status_code, 302)

    def test_hierarki_unit_menolak_parent_non_angka(self):
        response = self.client.post(
            f'/accounts/kontrol/unit/{self.unit.pk}/update-hierarchy/',
            {'parent_id': 'abc'},
        )
        self.assertEqual(response.status_code, 400)

    def test_matriks_izin_menolak_payload_tak_dikenal(self):
        response = self.client.post(
            '/accounts/kontrol/permissions/update/',
            data='bukan-payload', content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    def test_fast_track_igd_menolak_usia_non_angka(self):
        response = self.client.post(
            '/pasien/fast-track-igd/', {'nama_pasien': 'Uji', 'estimasi_usia': 'abc'}
        )
        self.assertEqual(response.status_code, 302)


class TemplateRenderTest(InputBatasTestCase):
    def test_detail_kunjungan_bisa_dirender(self):
        """`{% endblock %}` ganda dulu membuat GET detail kunjungan selalu 500."""
        from pasien.models import KunjunganPasien, Pasien
        from datetime import date

        pasien = Pasien.objects.create(
            no_rm='QA-RM-1', nama_lengkap='Uji Template', jenis_kelamin='L',
            tanggal_lahir=date(1990, 1, 1),
        )
        from django.utils import timezone
        kunjungan = KunjunganPasien.objects.create(
            pasien=pasien, no_kunjungan='QA-KUN-1', jenis_kunjungan='IGD',
            status='TRIAGE', triage='MERAH', tanggal_masuk=timezone.now(),
        )
        self.assertEqual(
            self.client.get(f'/pasien/kunjungan/{kunjungan.pk}/').status_code, 200
        )


