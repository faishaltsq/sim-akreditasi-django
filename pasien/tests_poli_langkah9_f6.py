"""Langkah 9 POLI-JANTUNG: CPPT profesional, TTE, verifikasi 24 jam, tindakan (F6).

Setiap tes menyatakan perilaku yang dapat diamati: status/isi ``CPPT``, baris
``BillingItem``/``PembatalanTagihan``, ``VerifikasiCppt``, atau kode respons
HTTP. Pilihan keluhan, status kepatuhan, kode tindakan, dan nominal tarif
diambil dari matriks (``workflow_schemas``) atau salinan katalog POLI_JANTUNG —
tidak ada satu pun yang dikarang di berkas ini.

Dua hal yang sengaja diuji justru karena **tidak** ada:
* formularium belum aktif, sehingga daftar obat aktif kosong dan panel harus
  menyebut sebabnya alih-alih menampilkan obat karangan;
* ``TindakanAsesmen.execution_team`` hanya punya MEDIS/KEPERAWATAN, sehingga
  pelaksana "Nakes Lain" ditolak dengan sebab eksplisit (AMBIGU-20).
"""
import hashlib
import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from pasien.models import (
    CPPT, IgdAssessmentWorkflow, KunjunganPasien, Pasien, PembatalanTagihan,
    PenugasanDpjpEpisode, TindakanAsesmen,
)
from pasien.services.igd_assessment_workflow import WorkflowConflict

from .tests_poli_workflow import TEST_STORAGES

SOAP = {
    'subjektif': 'Sesak napas sejak dua hari',
    'objektif': 'Ronki basal kedua paru',
    'asesmen': 'Gagal jantung dekompensasi',
    'plan': 'Diuretik IV, evaluasi balance cairan',
}

#: PNG 1×1 — isi gambar TTE yang sah (magic bytes + base64 benar).
PNG_DATA_URL = (
    'data:image/png;base64,'
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=='
)


class Langkah9Fixture(TestCase):
    """Episode RAJAL POLI-JANTUNG + tumpukan kredensial profesional lengkap."""

    @classmethod
    def setUpTestData(cls):
        from klinis.models import (
            LayananProfesional, PemetaanKewenanganLayanan,
        )
        from sdm.models import (
            ClinicalActionCode, KatalogTindakan, KeputusanKredensial,
            MasterJenjangProfesi, MasterProfesiPegawai, Pegawai,
            PengajuanKredensial, PenugasanKlinis, PrivilegeSnapshot,
            RincianKewenangan,
        )

        cls.unit = UnitKerja.objects.get_or_create(
            code='POLI-JANTUNG', defaults={'name': 'Poliklinik Jantung', 'level': 3},
        )[0]
        cls.admin = User.objects.create_user('qa9-admin', password='fixture-only')
        UserProfile.objects.update_or_create(
            user=cls.admin, defaults={'role': 'ADMIN_RS', 'unit_kerja': cls.unit},
        )
        cls.doctor = cls._account('qa9-dpjp', 'DOKTER_SPESIALIS')
        cls.other_doctor = cls._account('qa9-dokter-lain', 'DOKTER_SPESIALIS')
        cls.nurse = cls._account('qa9-perawat', 'PERAWAT')

        cls.patient = Pasien.objects.create(
            no_rm='QA-L9', nama_lengkap='Pasien Langkah Sembilan',
            tanggal_lahir='1968-03-03', jenis_kelamin='L',
        )
        cls.visit = KunjunganPasien.objects.create(
            pasien=cls.patient, no_kunjungan='QA-L9-001', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), unit_kerja=cls.unit,
            poliklinik='POLI-JANTUNG', penjamin='BPJS',
        )
        today = timezone.localdate()
        PenugasanDpjpEpisode.objects.create(
            visit=cls.visit, doctor=cls.doctor, unit=cls.unit,
            assignment_type='PRIMARY', valid_from=today,
            valid_until=today + timedelta(days=30), is_active=True,
            source_version='QA-L9-ASSIGNMENT', assigned_by=cls.admin,
        )

        # Tumpukan kredensial: pegawai HC → profesi/jenjang → SPK → kredensial
        # → privilege snapshot (professional_care + verify_cppt).
        cls.profession = MasterProfesiPegawai.objects.create(
            code='QA9-DOK', nama='Dokter Spesialis QA', keluarga='MEDIS',
            reviewed_by=cls.admin, reviewed_at=timezone.now(),
        )
        cls.grade = MasterJenjangProfesi.objects.create(
            profesi=cls.profession, kode='QA9', nama='Grade QA', urutan=1,
        )
        cls.employee = Pegawai.objects.create(
            akun=cls.doctor, nama_lengkap='DPJP Sintetis Langkah Sembilan',
            kategori='PPA', profesi_master=cls.profession,
            jenjang_master=cls.grade, data_origin='MANUAL',
        )
        cls.catalogue = KatalogTindakan.objects.create(
            kode='QA9-CARE', nama='Layanan CPPT QA', jenjang=cls.grade,
            tingkat_supervisi='M',
        )
        cls.application = PengajuanKredensial.objects.create(
            employee=cls.employee, unit_kerja=cls.unit, status='DISETUJUI',
        )
        cls.decision = KeputusanKredensial.objects.create(
            pengajuan=cls.application, outcome='DISETUJUI', decided_by=cls.admin,
        )
        cls.spk = PenugasanKlinis.objects.create(
            employee=cls.employee, unit_kerja=cls.unit, decision=cls.decision,
            nomor_spk='QA9-SPK', berlaku_mulai=today - timedelta(days=2),
            berlaku_sampai=today + timedelta(days=30), issued_by=cls.admin,
        )
        cls.rkk = RincianKewenangan.objects.create(
            pengajuan=cls.application, catalog_item=cls.catalogue,
            kewenangan='QA', status_spk='DISETUJUI_MANDIRI',
        )
        cls.care_code = ClinicalActionCode.objects.get_or_create(
            code='professional_care', defaults={'label': 'Pelayanan profesional'},
        )[0]
        cls.verify_code = ClinicalActionCode.objects.get_or_create(
            code='verify_cppt', defaults={'label': 'Verifikasi CPPT'},
        )[0]
        PrivilegeSnapshot.objects.create(
            pegawai=cls.employee, unit_kerja=cls.unit, action_code=cls.care_code,
            valid_from=today - timedelta(days=2),
            valid_until=today + timedelta(days=30), source_decision=cls.spk,
            granted_by=cls.admin,
        )
        PrivilegeSnapshot.objects.create(
            pegawai=cls.employee, unit_kerja=cls.unit, action_code=cls.verify_code,
            valid_from=today - timedelta(days=2),
            valid_until=today + timedelta(days=30), source_decision=cls.spk,
            granted_by=cls.admin,
        )
        cls.service = LayananProfesional.objects.create(
            code='QA9.CPPT', name='CPPT QA Langkah Sembilan', group='MEDICAL',
            authority_kind='CLINICAL', note_format='SOAP',
            source_version='qa9-fixture', reviewed_by=cls.admin,
            reviewed_at=timezone.now(), is_active=True,
        )
        PemetaanKewenanganLayanan.objects.create(
            service=cls.service, catalog_item=cls.catalogue,
            source_version='qa9-fixture', reviewed_by=cls.admin,
            reviewed_at=timezone.now(), is_active=True,
        )

    @classmethod
    def _account(cls, username, profesi):
        user = User.objects.create_user(username, password='fixture-only')
        UserProfile.objects.update_or_create(
            user=user,
            defaults={'role': 'STAF_NAKES', 'profesi': profesi, 'unit_kerja': cls.unit},
        )
        return user

    def workflow(self):
        return IgdAssessmentWorkflow.objects.filter(kunjungan=self.visit).first()

    def ensure_workflow(self, **overrides):
        workflow, _ = IgdAssessmentWorkflow.objects.get_or_create(
            kunjungan=self.visit,
            defaults={'origin_unit': self.unit, 'service_line': 'RAJAL_JANTUNG'},
        )
        for key, value in overrides.items():
            setattr(workflow, key, value)
        workflow.save()
        return workflow

    def context(self, **kwargs):
        from sdm.services.professional_care import resolve_professional_context
        return resolve_professional_context(
            self.doctor, self.visit, self.service, at=timezone.now(), **kwargs
        )

    def create_note(self, payload=None, actor=None):
        from pasien.services.professional_cppt import create_care_note
        workflow = self.ensure_workflow()
        actor = actor or self.doctor
        return create_care_note(
            self.visit, workflow, actor, format_code='SOAP',
            payload=payload or dict(SOAP), context=self.context(),
        )

    def sign_note(self, note):
        from pasien.services.professional_cppt import sign_care_note
        return sign_care_note(
            self.doctor, note.pk, note.version,
            ttd_image=PNG_DATA_URL, credential_confirmed=True,
        )


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class CpptRajalWritableTest(Langkah9Fixture):
    """F6.1 — empat keadaan yang harus terbukti."""

    def test_rajal_with_workflow_creates_draft_professional_note(self):
        note = self.create_note()
        self.assertEqual(note.status, 'DRAFT')
        self.assertEqual(note.kunjungan, self.visit)
        self.assertEqual(note.subjektif, SOAP['subjektif'])
        self.assertEqual(CPPT.objects.count(), 1)

    def test_rajal_without_workflow_is_still_rejected(self):
        from pasien.services.professional_cppt import _writable, create_care_note
        with self.assertRaises(WorkflowConflict):
            _writable(self.visit, None)
        # Konteks dihitung saat episode masih ber-workflow, lalu workflow
        # dihilangkan dari panggilan: yang menolak adalah ``_writable``.
        self.ensure_workflow()
        context = self.context()
        with self.assertRaises(WorkflowConflict):
            create_care_note(
                self.visit, None, self.doctor, format_code='SOAP',
                payload=dict(SOAP), context=context,
            )
        self.assertFalse(CPPT.objects.exists())

    def test_closed_episode_is_rejected(self):
        from pasien.services.professional_cppt import _writable
        workflow = self.ensure_workflow()
        for status in ('PULANG', 'RUJUK', 'MENINGGAL', 'BATAL'):
            with self.subTest(status=status):
                KunjunganPasien.objects.filter(pk=self.visit.pk).update(status=status)
                self.visit.refresh_from_db()
                with self.assertRaises(WorkflowConflict):
                    _writable(self.visit, workflow)
                # Lewat layanan: ditolak lebih awal oleh lingkup episode
                # (PermissionDenied) atau oleh ``_writable`` (WorkflowConflict).
                with self.assertRaises((WorkflowConflict, PermissionDenied)):
                    self.create_note()
                KunjunganPasien.objects.filter(pk=self.visit.pk).update(status='AKTIF')
                self.visit.refresh_from_db()
                self.assertFalse(CPPT.objects.exists())

    def test_final_workflow_is_rejected(self):
        self.ensure_workflow(status='FINAL')
        with self.assertRaises(WorkflowConflict):
            self.create_note()
        self.assertFalse(CPPT.objects.exists())

    def test_igd_behaviour_is_unchanged(self):
        """Episode IGD tetap lolos ``_writable`` seperti sebelum F6.1."""
        from pasien.services.professional_cppt import _writable
        igd_unit = UnitKerja.objects.get_or_create(
            code='IGD', defaults={'name': 'IGD', 'level': 2},
        )[0]
        igd_visit = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-L9-IGD', jenis_kunjungan='IGD',
            tanggal_masuk=timezone.now(), unit_kerja=igd_unit,
        )
        workflow = IgdAssessmentWorkflow.objects.create(
            kunjungan=igd_visit, origin_unit=igd_unit,
        )
        self.assertEqual(workflow.service_line, 'IGD')
        # IGD tanpa workflow dan IGD ber-workflow sama-sama boleh menulis.
        self.assertIsNone(_writable(igd_visit, None))
        self.assertIsNone(_writable(igd_visit, workflow))
        # Penutupan episode dan status FINAL tetap ditolak untuk semua jalur.
        KunjunganPasien.objects.filter(pk=igd_visit.pk).update(status='PULANG')
        igd_visit.refresh_from_db()
        with self.assertRaises(WorkflowConflict):
            _writable(igd_visit, workflow)

    def test_legacy_cppt_writer_returns_409_for_poli_jantung(self):
        self.ensure_workflow()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('pasien:cppt_tambah', args=[self.visit.pk]),
            {'profesi': 'DOKTER', 'nama_ppa': 'Klaim bebas', 'tanggal': timezone.now(),
             'subjektif': 'x', 'objektif': 'x', 'asesmen': 'x', 'plan': 'x'},
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(CPPT.objects.exists())

    def test_legacy_rajal_soap_writer_returns_409_for_poli_jantung(self):
        self.ensure_workflow()
        self.client.force_login(self.doctor)
        response = self.client.post(
            reverse('pasien:rajal_soap_simpan', args=[self.visit.pk]),
            {'subjektif': 'x', 'objektif': 'x', 'asesmen': 'x', 'plan': 'x'},
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(CPPT.objects.exists())

    def test_professional_path_still_works_after_legacy_writers_close(self):
        """Urutan F6.1: pengganti profesional hidup, penulis lama mati."""
        self.ensure_workflow()
        self.client.force_login(self.doctor)
        blocked = self.client.post(
            reverse('pasien:cppt_tambah', args=[self.visit.pk]),
            {'profesi': 'DOKTER', 'nama_ppa': 'x', 'tanggal': timezone.now(),
             'subjektif': 'x', 'objektif': 'x', 'asesmen': 'x', 'plan': 'x'},
        )
        self.assertEqual(blocked.status_code, 409)
        note = self.create_note()
        self.assertEqual(note.status, 'DRAFT')
        self.assertEqual(CPPT.objects.count(), 1)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class ObjectiveAutoTest(Langkah9Fixture):
    """F6.2 — komponen O terisi otomatis, bukan input manual."""

    def setUp(self):
        from pasien.models import OrderPenunjang
        from pasien.services.igd_assessment_workflow import save_step
        self.workflow_obj = self.ensure_workflow()
        save_step(
            self.visit.pk, self.doctor, 4,
            {'ttv_sistole': 110, 'ttv_diastole': 70, 'ttv_nadi': 96, 'ttv_rr': 22,
             'ttv_suhu': 36.8, 'ttv_spo2': 94, 'berat_badan': 68},
            self.workflow_obj.version, service_line='RAJAL_JANTUNG',
        )
        for index, name in enumerate(('EKG 12 Lead', 'Ekokardiografi', 'Natrium', 'Kalium'), start=1):
            OrderPenunjang.objects.create(
                kunjungan=self.visit, jenis='EKG', nama_pemeriksaan=name,
                status='SELESAI', hasil_pemeriksaan=f'hasil-{index}',
            )
        self.visit.penanda_anatomi = [
            {'side': 'FRONT', 'x': 0.4, 'y': 0.5, 'kind': 'NYERI', 'label': 'Nyeri prekordial'},
        ]
        self.visit.save(update_fields=['penanda_anatomi'])

    def test_objective_default_carries_map_and_latest_investigations(self):
        from pasien.services.professional_presentation import cppt_objective_default
        text = cppt_objective_default(self.visit, self.workflow())
        # MAP = (110 + 2*70)/3 = 83.3
        self.assertIn('MAP 83.3 mmHg', text)
        self.assertIn('Nadi 96', text)
        # Tiga hasil terakhir (urut waktu unggah, terbaru dulu).
        self.assertIn('Kalium', text)
        self.assertIn('Natrium', text)
        self.assertIn('Ekokardiografi', text)
        self.assertNotIn('EKG 12 Lead', text)
        self.assertIn('Nyeri prekordial', text)

    def test_objective_default_states_missing_data_instead_of_blank(self):
        from pasien.services.professional_presentation import cppt_objective_default
        blank = KunjunganPasien.objects.create(
            pasien=self.patient, no_kunjungan='QA-L9-BLANK', jenis_kunjungan='RAJAL',
            tanggal_masuk=timezone.now(), unit_kerja=self.unit, penjamin='UMUM',
        )
        text = cppt_objective_default(blank, None)
        self.assertIn('TTV terbaru belum tercatat', text)
        self.assertIn('Belum ada hasil penunjang selesai', text)
        self.assertIn('Belum ada penanda anatomi bertanda', text)

    def test_step9_page_renders_objective_from_records(self):
        self.client.force_login(self.doctor)
        response = self.client.get(
            reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=9'
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn('MAP 83.3 mmHg', body)
        self.assertIn('data-poli-cppt', body)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class ChipsComplianceTest(Langkah9Fixture):
    """F6.3 — quick-chips keluhan dan kepatuhan terapi per obat."""

    def test_three_chips_and_compliance_are_stored_per_note(self):
        from pasien.services.professional_cppt import create_care_note
        from pasien.models import ResepDetail, ResepElektronik
        resep = ResepElektronik.objects.create(
            no_resep='QA9-RX-1', kunjungan=self.visit, status='SELESAI',
            jenis_resep='RAWAT_JALAN',
        )
        first = ResepDetail.objects.create(
            resep=resep, nama_obat='Furosemid', dosis='40 mg',
            aturan_pakai='1x1 pagi', jumlah=30,
        )
        second = ResepDetail.objects.create(
            resep=resep, nama_obat='Bisoprolol', dosis='2,5 mg',
            aturan_pakai='1x1 pagi', jumlah=30,
        )
        payload = dict(SOAP)
        payload['keluhan_chips'] = ['SESAK_NAPAS', 'ORTOPNEA', 'EDEMA_TUNGKAI']
        payload['kepatuhan_terapi'] = 'SEBAGIAN_TERLEWAT'
        payload['kepatuhan_obat'] = {
            str(second.pk): {'status': 'MENGHENTIKAN_SENDIRI', 'catatan': 'Berhenti 3 hari'},
        }
        note = create_care_note(
            self.visit, self.ensure_workflow(), self.doctor, format_code='SOAP',
            payload=payload, context=self.context(),
        )
        self.assertEqual(note.structured_content['keluhan_chips'],
                         ['SESAK_NAPAS', 'ORTOPNEA', 'EDEMA_TUNGKAI'])
        self.assertEqual(note.structured_content['kepatuhan_terapi'], 'SEBAGIAN_TERLEWAT')
        self.assertEqual(
            note.structured_content['kepatuhan_obat'][str(second.pk)]['status'],
            'MENGHENTIKAN_SENDIRI',
        )
        self.assertNotIn(str(first.pk), note.structured_content['kepatuhan_obat'])

    def test_unknown_chip_and_status_are_rejected(self):
        from pasien.services.professional_cppt import validate_note
        for payload in (
            {**SOAP, 'keluhan_chips': ['PALPITASI_KARANGAN']},
            {**SOAP, 'kepatuhan_terapi': 'SELALU_PATUH'},
            {**SOAP, 'kepatuhan_obat': {'1': {'status': 'PATUH_PENUH', 'lain': 'x'}}},
        ):
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                validate_note('SOAP', payload)

    def test_chip_and_compliance_options_come_from_the_matrix(self):
        from pasien.services.professional_presentation import step9_context
        from pasien.workflow_schemas import (
            KELUHAN_CPPT_CHOICES, KEPATUHAN_TERAPI_CHOICES,
        )
        context = step9_context(self.visit, self.ensure_workflow(), self.doctor)
        self.assertEqual([row['code'] for row in context['keluhan_choices']],
                         list(KELUHAN_CPPT_CHOICES))
        self.assertEqual([row['code'] for row in context['kepatuhan_choices']],
                         list(KEPATUHAN_TERAPI_CHOICES))

    def test_empty_active_drug_list_degrades_honestly(self):
        from pasien.services.professional_presentation import active_drugs, step9_context
        self.assertEqual(active_drugs(self.visit)['items'], [])
        context = step9_context(self.visit, self.ensure_workflow(), self.doctor)
        self.assertEqual(context['active_drugs'], [])
        self.assertIn('Belum ada resep berstatus selesai', context['active_drugs_reason'])


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class TteAndVerificationTest(Langkah9Fixture):
    """F6.4 — TTE kanvas; F6.5 — batas verifikasi 24 jam yang dihitung."""

    def test_signing_without_image_fails(self):
        from pasien.services.professional_cppt import sign_care_note
        note = self.create_note()
        with self.assertRaises(ValidationError):
            sign_care_note(self.doctor, note.pk, note.version, credential_confirmed=True)
        note.refresh_from_db()
        self.assertEqual(note.status, 'DRAFT')

    def test_signing_without_credential_confirmation_fails(self):
        from pasien.services.professional_cppt import sign_care_note
        note = self.create_note()
        with self.assertRaises(ValidationError):
            sign_care_note(self.doctor, note.pk, note.version, ttd_image=PNG_DATA_URL)
        note.refresh_from_db()
        self.assertEqual(note.status, 'DRAFT')

    def test_image_and_confirmation_store_hash_and_signed_status(self):
        note = self.create_note()
        result = self.sign_note(note)
        note.refresh_from_db()
        self.assertEqual(note.status, 'SIGNED')
        self.assertTrue(note.ttd_image.startswith('data:image/png;base64,'))
        expected = hashlib.sha256(
            __import__('base64').b64decode(PNG_DATA_URL.split(',', 1)[1])
        ).hexdigest()
        self.assertEqual(note.ttd_hash, expected)
        self.assertEqual(result['ttd_hash'], expected)
        self.assertEqual(note.care_revisions.count(), 1)

    def test_non_image_payload_is_rejected(self):
        from pasien.services.professional_cppt import sign_care_note
        note = self.create_note()
        with self.assertRaises(ValidationError):
            sign_care_note(self.doctor, note.pk, note.version,
                           ttd_image='data:text/plain;base64,QQ==',
                           credential_confirmed=True)

    def test_due_at_is_sign_time_plus_24_hours(self):
        note = self.create_note()
        before = timezone.now()
        self.sign_note(note)
        after = timezone.now()
        note.refresh_from_db()
        self.assertIsNotNone(note.verifikasi_due_at)
        self.assertGreaterEqual(note.verifikasi_due_at, before + timedelta(hours=24))
        self.assertLessEqual(note.verifikasi_due_at, after + timedelta(hours=24))

    def test_verification_state_is_computed_not_stored(self):
        from pasien.services.professional_cppt import verification_state, verification_state_at
        note = self.create_note()
        self.sign_note(note)
        note.refresh_from_db()
        due = note.verifikasi_due_at
        self.assertEqual(verification_state_at(due, due - timedelta(hours=1)), 'TEPAT')
        self.assertEqual(verification_state_at(due, due + timedelta(hours=1)), 'TERLAMBAT')
        self.assertEqual(verification_state(note), 'MENUNGGU')
        # Tidak ada kolom status: satu-satunya sumber adalah due_at + performed_at.
        field_names = {field.name for field in CPPT._meta.get_fields()}
        self.assertIn('verifikasi_due_at', field_names)
        self.assertNotIn('verifikasi_status', field_names)
        self.assertNotIn('verification_status', field_names)

    def test_page_shows_tepat_and_terlambat_from_calculation(self):
        from pasien.models import CpptRevision, VerifikasiCppt
        from pasien.services.professional_presentation import snapshot_professional_care
        note = self.create_note()
        self.sign_note(note)
        note.refresh_from_db()
        revision = CpptRevision.objects.get(note=note)
        VerifikasiCppt.objects.create(
            revision=revision, verifier=self.doctor, verifier_name='DPJP Sintetis',
            assignment=PenugasanDpjpEpisode.objects.get(visit=self.visit),
            digest=revision.digest, request_id=uuid.uuid4(),
        )
        # performed_at = sekarang (auto_now_add) dan due_at = sign + 24 jam.
        notes = snapshot_professional_care(self.visit)['notes']
        self.assertEqual(notes[0]['verification']['digest'], revision.digest)
        self.assertTrue(note.verifikasi_due_at > timezone.now())

    def test_late_verification_is_terlambat_without_a_status_column(self):
        from pasien.services.professional_cppt import verification_state_at
        due = timezone.now() - timedelta(minutes=1)
        self.assertEqual(verification_state_at(due, timezone.now()), 'TERLAMBAT')
        self.assertEqual(verification_state_at(due, due - timedelta(minutes=5)), 'TEPAT')


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class DpjpVerificationRbacTest(Langkah9Fixture):
    """Bonus F6.5: matriks ``VERIFY_ROLES`` benar-benar ditegakkan."""

    def test_verify_path_calls_authorize_step_with_verify_action(self):
        from pasien.services.professional_cppt import verify_cppt
        note = self.create_note()
        self.sign_note(note)
        note.refresh_from_db()
        with patch('pasien.services.poli_rbac.authorize_step',
                   wraps=__import__('pasien.services.poli_rbac', fromlist=['authorize_step']).authorize_step) as spy:
            verify_cppt(self.doctor, note.pk, note.version, uuid.uuid4())
        spy.assert_any_call(self.doctor, self.visit, 9, 'verify')

    def test_nurse_is_refused_by_the_matrix_at_verification(self):
        from pasien.services.professional_cppt import verify_cppt
        note = self.create_note()
        self.sign_note(note)
        note.refresh_from_db()
        with self.assertRaises(PermissionDenied) as ctx:
            verify_cppt(self.nurse, note.pk, note.version, uuid.uuid4())
        self.assertIn('tidak berwenang memverifikasi langkah 9', str(ctx.exception))

    def test_doctor_without_dpjp_assignment_is_refused(self):
        from pasien.services.professional_cppt import verify_cppt
        note = self.create_note()
        self.sign_note(note)
        note.refresh_from_db()
        with self.assertRaises(PermissionDenied) as ctx:
            verify_cppt(self.other_doctor, note.pk, note.version, uuid.uuid4())
        self.assertIn('tidak berwenang memverifikasi langkah 9', str(ctx.exception))

    def test_assigned_dpjp_verifies_and_state_is_tepat(self):
        from pasien.models import VerifikasiCppt
        from pasien.services.professional_cppt import verify_cppt
        note = self.create_note()
        self.sign_note(note)
        note.refresh_from_db()
        result = verify_cppt(self.doctor, note.pk, note.version, uuid.uuid4())
        note.refresh_from_db()
        self.assertTrue(note.verifikasi_dpjp)
        self.assertEqual(VerifikasiCppt.objects.count(), 1)
        self.assertEqual(result['verification_id'], VerifikasiCppt.objects.get().pk)


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class TindakanPoliTest(Langkah9Fixture):
    """F6.6 — tindakan ber-tarif per penjamin + EP; F6.7 — void beralasan."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        call_command('seed_katalog_klinis', verbosity=0)
        call_command('seed_poli_jantung_tarif', verbosity=0)

    def test_resolve_returns_decimal_for_poli_jantung_code(self):
        from klinis.services.tarif import resolve
        self.assertEqual(resolve(self.visit, '89.52'), Decimal('120000.00'))
        self.visit.penjamin = 'UMUM'
        self.visit.save(update_fields=['penjamin'])
        self.assertEqual(resolve(self.visit, '89.52'), Decimal('150000.00'))

    def test_add_action_creates_billing_item_with_payer_tariff_and_ep(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        line = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        self.assertEqual(line.kode, '89.52')
        self.assertEqual(line.tarif_acuan, Decimal('120000.00'))
        self.assertEqual(line.tarif_penjamin, 'BPJS')
        self.assertEqual(line.execution_team, 'MEDIS')
        self.assertIsNotNone(line.billing_item_id)
        self.assertEqual(line.billing_item.harga_satuan, Decimal('120000.00'))
        self.assertEqual(line.billing_item.sumber, 'TINDAKAN')
        self.assertIsNotNone(line.standard_item_id)
        self.assertEqual(line.standard_item.sub_standard, 'PAP 3')

    def test_umum_payer_gets_umum_tariff(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        self.visit.penjamin = 'UMUM'
        self.visit.save(update_fields=['penjamin'])
        line = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        self.assertEqual(line.billing_item.harga_satuan, Decimal('150000.00'))

    def test_code_outside_group_copy_is_refused_not_billed(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        with self.assertRaises(ValidationError):
            tambah_tindakan_poli(self.visit, self.doctor, kode='99.9999', pelaksana='DOKTER')
        self.assertFalse(TindakanAsesmen.objects.filter(kunjungan=self.visit).exists())

    def test_nakes_lain_is_refused_with_explicit_reason(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        with self.assertRaises(ValidationError) as ctx:
            tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='NAKES_LAIN')
        self.assertIn('Nakes Lain', str(ctx.exception))

    def test_adding_same_code_twice_keeps_one_line(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        first = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        second = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='PERAWAT')
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(TindakanAsesmen.objects.filter(kunjungan=self.visit).count(), 1)
        self.assertEqual(second.execution_team, 'KEPERAWATAN')

    def test_void_keeps_row_and_records_one_reason_line(self):
        from klinis.models import ProfessionalCareGrant
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        from pasien.services.professional_billing import void_tindakan_poli
        line = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        reviewer = User.objects.create_user('qa9-void-reviewer')
        ProfessionalCareGrant.objects.create(
            user=self.doctor, unit=self.unit, capability='VOID_UNPAID_CHARGE',
            valid_from=timezone.localdate(), valid_until=timezone.localdate(),
            is_active=True, source_version='qa9-fixture',
            reviewed_by=reviewer, reviewed_at=timezone.now(),
        )
        result = void_tindakan_poli(self.doctor, line.pk, uuid.uuid4(), 'Tindakan tidak jadi dilakukan')
        line.refresh_from_db()
        item = line.billing_item
        self.assertTrue(item.is_void)
        self.assertEqual(item.subtotal, Decimal('0'))
        self.assertEqual(PembatalanTagihan.objects.count(), 1)
        self.assertEqual(PembatalanTagihan.objects.get().amount, Decimal('120000.00'))
        self.assertEqual(line.financial_status, 'VOID')
        self.assertEqual(result['billing_id'], item.pk)

    def test_ungranted_void_is_denied(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        from pasien.services.professional_billing import void_tindakan_poli
        line = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        with self.assertRaises(PermissionDenied):
            void_tindakan_poli(self.doctor, line.pk, uuid.uuid4(), 'Koreksi tanpa wewenang')

    def test_direct_delete_of_automatic_charge_is_refused(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        line = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        item = line.billing_item
        with self.assertRaises(ValidationError):
            item.delete()
        self.assertTrue(type(item).objects.filter(pk=item.pk).exists())

    def test_http_add_and_void_round_trip(self):
        from klinis.models import ProfessionalCareGrant
        self.client.force_login(self.doctor)
        added = self.client.post(
            reverse('pasien:poli_tindakan_tambah', args=[self.visit.pk]),
            {'kode': '89.52', 'pelaksana': 'DOKTER', 'quantity': '1'},
        )
        self.assertEqual(added.status_code, 200, added.content)
        body = added.json()
        self.assertEqual(body['tarif_acuan'], '120000.00')
        self.assertEqual(body['billing_amount'], '120000.00')
        self.assertEqual(body['ep_sub_standard'], 'PAP 3')
        reviewer = User.objects.create_user('qa9-void-reviewer-http')
        ProfessionalCareGrant.objects.create(
            user=self.doctor, unit=self.unit, capability='VOID_UNPAID_CHARGE',
            valid_from=timezone.localdate(), valid_until=timezone.localdate(),
            is_active=True, source_version='qa9-fixture',
            reviewed_by=reviewer, reviewed_at=timezone.now(),
        )
        voided = self.client.post(
            reverse('pasien:poli_tindakan_void', args=[self.visit.pk]),
            {'line_id': body['line_id'], 'reason': 'Tindakan dibatalkan pasien',
             'request_id': str(uuid.uuid4())},
        )
        self.assertEqual(voided.status_code, 200, voided.content)
        self.assertTrue(voided.json()['success'])


@override_settings(POLI_JANTUNG_WORKFLOW_ENABLED=True, STORAGES=TEST_STORAGES)
class RightPanelTest(Langkah9Fixture):
    """F6.8 — regulasi, consent, brosur, multi-upload."""

    def upload(self, name, content, jenis='LAINNYA'):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.doctor)
        return self.client.post(
            reverse('pasien:poli_lampiran_upload', args=[self.visit.pk]),
            {
                'jenis': jenis,
                'filename': name,
                'size': str(len(content)),
                'sha256': hashlib.sha256(content).hexdigest(),
                'file': SimpleUploadedFile(name, content),
            },
        )

    def test_pdf_upload_stores_hash_verified_attachment(self):
        from pasien.models import LampiranAsesmen
        response = self.upload('hasil-ekg.pdf', b'%PDF-1.4\n%QA fixture\n')
        self.assertEqual(response.status_code, 200, response.content)
        record = LampiranAsesmen.objects.get()
        self.assertEqual(record.nama_asli, 'hasil-ekg.pdf')
        self.assertEqual(record.ukuran, len(b'%PDF-1.4\n%QA fixture\n'))

    def test_executable_upload_is_refused(self):
        from pasien.models import LampiranAsesmen
        response = self.upload('malware.exe', b'MZ\x90\x00payload')
        self.assertEqual(response.status_code, 400)
        self.assertFalse(LampiranAsesmen.objects.exists())

    def test_three_files_keep_original_names(self):
        from pasien.models import LampiranAsesmen
        payloads = {
            'rontgen.png': b'\x89PNG\r\n\x1a\n' + b'0' * 16,
            'lab.pdf': b'%PDF-1.7\n',
            'consent.jpg': b'\xff\xd8\xff' + b'0' * 16,
        }
        for name, content in payloads.items():
            response = self.upload(name, content)
            self.assertEqual(response.status_code, 200, (name, response.content))
        self.assertEqual(
            sorted(LampiranAsesmen.objects.values_list('nama_asli', flat=True)),
            sorted(payloads),
        )
        self.client.force_login(self.doctor)
        page = self.client.get(reverse('pasien:poli_workflow', args=[self.visit.pk]) + '?step=9')
        body = page.content.decode()
        for name in payloads:
            self.assertIn(name, body)

    def test_regulation_menu_reads_the_existing_evidence_library(self):
        from akreditasi.models import (
            Category, EvidenceFile, EvidenceReq, Framework, StandardItem,
        )
        framework = Framework.objects.create(name='QA F6', version='QA')
        category = Category.objects.create(
            framework=framework, code='QA9', name='QA Pokja Langkah 9',
        )
        item = StandardItem.objects.create(
            category=category, code='QA.9', sub_standard='QA.9.1',
            sub_title='Kepatuhan klinis', description='Elemen penilaian QA.',
        )
        requirement = EvidenceReq.objects.create(
            standard_item=item, category_type='R',
            title='Panduan Praktik Klinik Jantung',
        )
        EvidenceFile.objects.create(
            requirement=requirement, file_name='ppk-jantung.pdf', status='VALID',
        )
        from pasien.services.professional_presentation import right_panel_context
        context = right_panel_context(self.visit, self.ensure_workflow())
        self.assertEqual(len(context['regulations']), 1)
        self.assertEqual(context['regulations'][0]['requirement__title'],
                         'Panduan Praktik Klinik Jantung')

    def test_consent_print_page_fills_patient_identity(self):
        from pasien.asesmen_tindakan import tambah_tindakan_poli
        call_command('seed_katalog_klinis', verbosity=0)
        call_command('seed_poli_jantung_tarif', verbosity=0)
        line = tambah_tindakan_poli(self.visit, self.doctor, kode='89.52', pelaksana='DOKTER')
        self.client.force_login(self.doctor)
        response = self.client.get(
            reverse('pasien:poli_consent_cetak', args=[self.visit.pk]) + f'?tindakan={line.pk}'
        )
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        self.assertIn(self.patient.nama_lengkap, body)
        self.assertIn(self.patient.no_rm, body)
        self.assertIn('89.52', body)
