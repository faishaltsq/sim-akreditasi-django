"""Siklus ARIMA: sinkron → mandiri → atasan → kalibrasi → feedback → final."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu
from akreditasi.models import UnitKerja
from sdm.models import (
    ButirPenilaian,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    PenilaianKinerja,
    PeriodeKinerja,
    TahapPenilaian,
)
from sdm.services.kinerja import finalize_appraisal
from sdm.services.sinkron_kinerja import sinkronkan_data
from sdm.services.workflow_kinerja import current_stage


class SiklusBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Unit Siklus', code='SKL')
        self.user = self._user('hr-siklus')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Pegawai Siklus', kategori='PPA', profesi='Perawat',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=200),
            alokasi_fte=Decimal('1.00'),
        )
        self.period = PeriodeKinerja.objects.create(
            nama='Siklus S1',
            tanggal_mulai=self.today - timedelta(days=180),
            tanggal_selesai=self.today - timedelta(days=1),
        )
        self.appraisal = PenilaianKinerja.objects.create(
            periode=self.period, employee=self.employee, reviewer=self.user,
        )

    def _user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_manage_hc_appraisals = True
        config.save(update_fields=['can_manage_hc_appraisals', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='can_manage_hc_appraisals', unit_kerja=self.unit,
        )
        return user

    def _indikator(self, kode='INM-TEST-1', target=Decimal('80.00'), arah='MIN'):
        # Seed post-migrate membuat indikator RS-wide tanpa data; hapus agar
        # pilar A deterministik (maks 4 butir, NULL unit sort pertama).
        IndikatorMutu.objects.all().delete()
        indikator = IndikatorMutu.objects.create(
            nama_indikator='Kepatuhan cuci tangan',
            kode_indikator=kode, unit=self.unit, jenis='INM',
            dimensi_mutu='AMAN', numerator='Jumlah kepatuhan',
            denominator='Jumlah peluang', target_nilai=target,
            arah_target=arah,
        )
        CatatanIndikator.objects.create(
            indikator=indikator, bulan=self.period.tanggal_mulai.month,
            tahun=self.period.tanggal_mulai.year,
            nilai_numerator=Decimal('80'), nilai_denominator=Decimal('100'),
        )
        return indikator


class SinkronisasiTests(SiklusBase):
    def test_sinkron_membuat_butir_pilar_dan_tahap_pertama(self):
        indikator = self._indikator()

        dibuat, diperbarui = sinkronkan_data(self.appraisal, actor=self.user)

        self.assertGreaterEqual(dibuat, 1)
        butir_a = ButirPenilaian.objects.get(
            appraisal=self.appraisal, indikator=indikator,
        )
        # Capaian 80/100 = 80% >= target 80 (arah MIN) → skor 5,00.
        self.assertEqual(butir_a.score, Decimal('5.00'))
        self.assertTrue(str(butir_a.realisasi).startswith('80'))
        self.assertEqual(
            ButirPenilaian.objects.filter(
                appraisal=self.appraisal, kategori='PERILAKU',
            ).count(), 3,
        )
        self.assertEqual(
            ButirPenilaian.objects.filter(
                appraisal=self.appraisal, kategori='RISIKO',
            ).count(), 3,
        )
        self.assertEqual(current_stage(self.appraisal), 'DATA_TERKUMPUL')

    def test_sinkron_ulang_tambah_tidak_duplikat_dan_tidak_override_skor(self):
        indikator = self._indikator()
        sinkronkan_data(self.appraisal, actor=self.user)
        ButirPenilaian.objects.filter(
            appraisal=self.appraisal, indikator=indikator,
        ).update(score=Decimal('2.00'))
        butir_c = ButirPenilaian.objects.filter(
            appraisal=self.appraisal, kategori='PERILAKU',
        ).first()
        butir_c.score = Decimal('4.00')
        butir_c.save(update_fields=['score'])
        jumlah_awal = ButirPenilaian.objects.filter(appraisal=self.appraisal).count()

        sinkronkan_data(self.appraisal, actor=self.user)

        self.assertEqual(
            ButirPenilaian.objects.filter(appraisal=self.appraisal).count(),
            jumlah_awal,
        )
        butir_a = ButirPenilaian.objects.get(
            appraisal=self.appraisal, indikator=indikator,
        )
        self.assertEqual(butir_a.score, Decimal('2.00'))
        butir_c.refresh_from_db()
        self.assertEqual(butir_c.score, Decimal('4.00'))
        self.assertEqual(current_stage(self.appraisal), 'DATA_TERKUMPUL')

    def test_final_gagal_tanpa_sinkron_tapi_lulus_setelah_siklus_penuh(self):
        with self.assertRaises(ValidationError):
            finalize_appraisal(self.appraisal, actor=self.user)

        self._indikator()
        sinkronkan_data(self.appraisal, actor=self.user)
        ButirPenilaian.objects.filter(appraisal=self.appraisal).exclude(
            kategori='TARGET',
        ).update(score=Decimal('4.00'))
        for tahap in ('SELF_ASSESSMENT', 'REVIEW_ATASAN', 'KALIBRASI_MUTU', 'FEEDBACK'):
            TahapPenilaian.objects.create(
                appraisal=self.appraisal, tahap=tahap, aktor=self.user,
            )

        finalized = finalize_appraisal(self.appraisal, actor=self.user)

        self.assertEqual(finalized.status, 'FINAL')
        self.assertIsNotNone(finalized.kategori_akhir)
        self.assertEqual(
            TahapPenilaian.objects.filter(
                appraisal=self.appraisal, tahap='TERKUNCI',
            ).count(), 1,
        )


class WorkflowStageTests(SiklusBase):
    def test_current_stage_kosong_sebelum_sinkron(self):
        self.assertIsNone(current_stage(self.appraisal))

    def test_advance_stage_menolak_mundur(self):
        from sdm.services.workflow_kinerja import advance_stage

        TahapPenilaian.objects.create(
            appraisal=self.appraisal, tahap='REVIEW_ATASAN', aktor=self.user,
        )
        with self.assertRaises(ValidationError):
            advance_stage(
                self.appraisal, tahap='DATA_TERKUMPUL', actor=self.user,
            )
