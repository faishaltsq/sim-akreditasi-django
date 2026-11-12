from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien


class IgdWorkflowTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.get_or_create(
            code='IGD', defaults={'name': 'IGD', 'level': 2},
        )[0]
        cls.user = User.objects.create_superuser('workflow_doctor', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.user,
            defaults={'role': 'STAF_NAKES', 'profesi': 'DOKTER_UMUM', 'unit_kerja': cls.unit},
        )
        cls.patient = Pasien.objects.create(
            no_rm='QA-IGD-WORKFLOW', nama_lengkap='Pasien Uji Workflow',
            tanggal_lahir='1990-01-01', jenis_kelamin='L',
        )
        cls.visit = KunjunganPasien.objects.create(
            pasien=cls.patient, no_kunjungan='QA-IGD-WORKFLOW',
            jenis_kunjungan='IGD', tanggal_masuk=timezone.now(), unit_kerja=cls.unit,
        )

    def setUp(self):
        self.client.force_login(self.user)

    def save_triage(self, **data):
        return self.client.post(
            reverse('pasien:igd_asesmen_medis_save', args=[self.visit.pk]), data,
        )

    def test_category_five_does_not_mark_patient_doa(self):
        response = self.save_triage(triase_skala='ATS', triase_kategori='KATEGORI_5')
        self.assertEqual(response.status_code, 302)
        self.visit.refresh_from_db()
        self.assertNotEqual(self.visit.triage, 'HITAM')
        self.assertNotIn(self.visit.status, ('MENINGGAL', 'PULANG'))
        self.assertIsNone(self.visit.waktu_kematian)

    def test_invalid_category_is_rejected_without_mutation(self):
        response = self.save_triage(triase_skala='ATS', triase_kategori='KATEGORI_15', cara_datang='AMBULANS')
        self.assertEqual(response.status_code, 400)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.triase_kategori, '')
        self.assertEqual(self.visit.cara_datang, '')

    def test_unknown_historical_scale_does_not_infer_operational_color(self):
        self.visit.triage = 'KUNING'
        self.visit.save()
        response = self.save_triage(triase_kategori='KATEGORI_5')
        self.assertEqual(response.status_code, 302)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.triage, 'KUNING')
        self.assertEqual(self.visit.triase_skala, '')

    def test_esi_level_does_not_use_ats_color_conversion(self):
        response = self.save_triage(triase_skala='ESI', triase_kategori='KATEGORI_3')
        self.assertEqual(response.status_code, 302)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.triage, '')
        self.assertEqual(self.visit.triase_skala, 'ESI')


class IgdDraftFoundationTest(IgdWorkflowTest):
    def save_step(self, step, data, version=0):
        from pasien.services.igd_assessment_workflow import save_step
        return save_step(self.visit.pk, self.user, step, data, version)

    def test_step_patch_preserves_other_fields_and_existing_billing(self):
        from pasien.models import BillingItem
        self.visit.anamnesis_rpd = 'Riwayat lama'
        self.visit.save()
        item = BillingItem.objects.create(kunjungan=self.visit, kategori='JASA_MEDIS',
                                          nama_item='Tindakan historis', harga_satuan=10000, sumber='ASESMEN')
        workflow = self.save_step(3, {'anamnesis_rps': 'Keluhan baru'})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.anamnesis_rpd, 'Riwayat lama')
        self.assertEqual(self.visit.anamnesis_rps, 'Keluhan baru')
        self.assertEqual(workflow.version, 1)
        self.assertTrue(BillingItem.objects.filter(pk=item.pk).exists())

    def test_stale_version_cannot_overwrite_newer_draft(self):
        self.save_step(3, {'anamnesis_rps': 'Versi pertama'})
        with self.assertRaisesMessage(ValueError, 'versi'):
            self.save_step(3, {'anamnesis_rps': 'Timpa'})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.anamnesis_rps, 'Versi pertama')

    def test_wrong_step_field_rejected_without_creating_workflow(self):
        from pasien.models import IgdAssessmentWorkflow
        with self.assertRaises(ValueError):
            self.save_step(3, {'status': 'PULANG'})
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_blank_numeric_is_not_zero_and_valid_zero_is_preserved(self):
        workflow = self.save_step(4, {'ttv_skala_nyeri': '0', 'ttv_sistole': ''})
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.ttv_skala_nyeri, 0)
        self.assertIsNone(self.visit.ttv_sistole)
        self.assertEqual(workflow.observations.get().data['ttv_skala_nyeri'], 0)

    def test_invalid_vital_rolls_back_all_values(self):
        from pasien.models import IgdAssessmentWorkflow
        with self.assertRaises(ValueError):
            self.save_step(4, {'ttv_spo2': '101', 'ttv_nadi': '80'})
        self.visit.refresh_from_db()
        self.assertIsNone(self.visit.ttv_nadi)
        self.assertFalse(IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).exists())

    def test_repeated_observation_preserves_initial_measurement(self):
        workflow = self.save_step(4, {'ttv_nadi': '100'})
        self.save_step(10, {'ttv_nadi': '80'}, version=workflow.version)
        self.assertEqual(list(workflow.observations.order_by('pk').values_list('phase', flat=True)), ['INITIAL', 'EVALUATION'])
        self.assertEqual(workflow.observations.order_by('pk').first().data['ttv_nadi'], 100)
        self.visit.refresh_from_db()
        self.assertEqual(self.visit.ttv_nadi, 80)

    def test_final_workflow_blocks_legacy_mutations(self):
        from pasien.models import IgdAssessmentWorkflow
        IgdAssessmentWorkflow.objects.create(kunjungan=self.visit, origin_unit=self.unit, status='FINAL')
        for name in ('igd_asesmen_medis_save', 'igd_asesmen_awal_save', 'kunjungan_asesmen_awal',
                     'igd_asesmen_copy_prev', 'asesmen_hapus', 'igd_ttv_update'):
            with self.subTest(name=name):
                response = self.client.post(reverse('pasien:' + name, args=[self.visit.pk]),
                                            {'anamnesis_rps': 'Timpa final', 'konfirmasi': 'HAPUS'})
                self.assertEqual(response.status_code, 409)

    def test_cross_unit_clinician_is_denied(self):
        from django.core.exceptions import PermissionDenied
        other = UnitKerja.objects.get_or_create(code='QA-OTHER', defaults={'name': 'Unit Lain', 'level': 2})[0]
        user = User.objects.create_user('workflow_outsider')
        UserProfile.objects.update_or_create(user=user, defaults={'role': 'STAF_NAKES', 'profesi': 'DOKTER_UMUM', 'unit_kerja': other})
        from pasien.services.igd_assessment_workflow import save_step
        with self.assertRaises(PermissionDenied):
            save_step(self.visit.pk, user, 3, {'anamnesis_rps': 'Tidak boleh'}, 0)
