"""Tests for the Jadwal Praktek Dokter sub-module.

Covers the rules the STARKES paperwork depends on: patient/room conflict
detection, credential warnings, idempotent daily generation, leave cascade,
APM status synchronisation, and the rendered schedules.
"""
from datetime import date, time

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from pasien.models import JadwalDokterPoli
from sdm.models import (
    HcGrant,
    IzinProfesiPegawai,
    JadwalPraktekHarian,
    JadwalPraktekRutin,
    LogAuditJadwal,
    MasterProfesiPegawai,
    Pegawai,
    PengajuanIzinDokter,
    PenugasanKlinis,
    KeputusanKredensial,
    PengajuanKredensial,
)
from sdm.services.jadwal_praktek import (
    cek_bentrok_jadwal,
    cek_bentrok_ruangan,
    generate_jadwal_harian,
    proses_izin_dokter,
    sync_jadwal_ke_apm,
    validasi_kredensial_dokter,
)

# Monday, 23 November 2026 — a fixed weekday so the generator never depends on
# the day the suite happens to run.
SENIN = date(2026, 11, 23)
SELASA = date(2026, 11, 24)


class JadwalFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(name='Poli Jantung', code='T-JTG')
        cls.unit_lain = UnitKerja.objects.create(name='Poli Bedah', code='T-BDH')
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='T-SPJP', nama='Dokter Spesialis Jantung', keluarga='MEDIS',
        )
        cls.dokter = Pegawai.objects.create(
            nama_lengkap='dr. Uji Jantung', kategori='PPA',
            profesi='Dokter Spesialis Jantung', profesi_master=cls.profesi,
        )
        cls.pengganti = Pegawai.objects.create(
            nama_lengkap='dr. Uji Pengganti', kategori='PPA',
            profesi='Dokter Spesialis Jantung', profesi_master=cls.profesi,
        )


class JadwalRutinModelTests(JadwalFixture):
    def test_kuota_total_sums_both_streams(self):
        jadwal = JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
            kuota_jkn=20, kuota_non_jkn=10,
        )
        self.assertEqual(jadwal.kuota_total, 30)
        self.assertEqual(jadwal.hari_label, 'Senin')

    def test_rejects_end_before_start(self):
        jadwal = JadwalPraktekRutin(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(12, 0), jam_selesai=time(8, 0),
        )
        with self.assertRaises(ValidationError):
            jadwal.full_clean()


class BentrokTests(JadwalFixture):
    def setUp(self):
        JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, ruang_praktek='R1',
            hari=0, jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )

    def test_doctor_overlap_detected_on_same_day(self):
        self.assertTrue(
            cek_bentrok_jadwal(self.dokter.pk, 0, time(11, 0), time(14, 0))
        )

    def test_adjacent_slot_is_not_an_overlap(self):
        self.assertFalse(
            cek_bentrok_jadwal(self.dokter.pk, 0, time(12, 0), time(15, 0))
        )

    def test_different_day_is_free(self):
        self.assertFalse(
            cek_bentrok_jadwal(self.dokter.pk, 1, time(8, 0), time(12, 0))
        )

    def test_room_overlap_detected(self):
        self.assertTrue(
            cek_bentrok_ruangan(self.unit.pk, 'R1', 0, time(9, 0), time(10, 0))
        )

    def test_blank_room_never_conflicts(self):
        self.assertFalse(
            cek_bentrok_ruangan(self.unit.pk, '', 0, time(9, 0), time(10, 0))
        )


class GenerateHarianTests(JadwalFixture):
    def setUp(self):
        self.rutin = JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
            kuota_jkn=20, kuota_non_jkn=10,
        )

    def test_generates_one_row_for_matching_weekday(self):
        self.assertEqual(generate_jadwal_harian(SENIN), 1)
        self.assertTrue(
            JadwalPraktekHarian.objects.filter(tanggal=SENIN, jadwal_rutin=self.rutin).exists()
        )

    def test_is_idempotent_on_second_run(self):
        generate_jadwal_harian(SENIN)
        self.assertEqual(generate_jadwal_harian(SENIN), 0)

    def test_ignores_other_weekdays(self):
        self.assertEqual(generate_jadwal_harian(SELASA), 0)

    def test_inactive_template_is_skipped(self):
        self.rutin.is_active = False
        self.rutin.save(update_fields=['is_active'])
        self.assertEqual(generate_jadwal_harian(SENIN), 0)


class IzinCascadeTests(JadwalFixture):
    def setUp(self):
        self.rutin = JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        generate_jadwal_harian(SENIN)

    def test_without_substitute_session_becomes_batal(self):
        izin = PengajuanIzinDokter.objects.create(
            dokter=self.dokter, jenis='CUTI',
            tanggal_mulai=SENIN, tanggal_selesai=SENIN,
        )
        self.assertEqual(proses_izin_dokter(izin), 1)
        jadwal = JadwalPraktekHarian.objects.get(tanggal=SENIN)
        self.assertEqual(jadwal.status_sesi, 'BATAL')
        self.assertTrue(LogAuditJadwal.objects.filter(jenis_aksi='BATAL').exists())

    def test_with_substitute_session_becomes_digantikan(self):
        izin = PengajuanIzinDokter.objects.create(
            dokter=self.dokter, jenis='DIKLAT',
            tanggal_mulai=SENIN, tanggal_selesai=SENIN,
            dokter_pengganti=self.pengganti,
        )
        proses_izin_dokter(izin)
        jadwal = JadwalPraktekHarian.objects.get(tanggal=SENIN)
        self.assertEqual(jadwal.status_sesi, 'DIGANTIKAN')
        self.assertEqual(jadwal.dokter_pengganti, self.pengganti)
        self.assertEqual(jadwal.dokter_efektif, self.pengganti)

    def test_substitute_cannot_be_the_absent_doctor(self):
        izin = PengajuanIzinDokter(
            dokter=self.dokter, jenis='CUTI',
            tanggal_mulai=SENIN, tanggal_selesai=SENIN,
            dokter_pengganti=self.dokter,
        )
        with self.assertRaises(ValidationError):
            izin.full_clean()

    def test_sessions_outside_the_window_are_untouched(self):
        izin = PengajuanIzinDokter.objects.create(
            dokter=self.dokter, jenis='CUTI',
            tanggal_mulai=SELASA, tanggal_selesai=SELASA,
        )
        self.assertEqual(proses_izin_dokter(izin), 0)
        self.assertEqual(
            JadwalPraktekHarian.objects.get(tanggal=SENIN).status_sesi, 'AKTIF'
        )


class KredensialValidationTests(JadwalFixture):
    def test_warns_when_no_spk_and_no_sip(self):
        valid, warnings = validasi_kredensial_dokter(self.dokter.pk)
        self.assertFalse(valid)
        self.assertTrue(any('SPK' in w for w in warnings))
        self.assertTrue(any('SIP' in w for w in warnings))

    def test_clean_when_spk_active(self):
        pengajuan = PengajuanKredensial.objects.create(
            employee=self.dokter, unit_kerja=self.unit, jenis='AWAL',
            status='DISETUJUI',
        )
        keputusan = KeputusanKredensial.objects.create(
            pengajuan=pengajuan, outcome='DISETUJUI',
            decided_by=self._actor(),
        )
        PenugasanKlinis.objects.create(
            employee=self.dokter, unit_kerja=self.unit, decision=keputusan,
            nomor_spk='SPK/TEST/1', berlaku_mulai=date(2025, 1, 1),
            berlaku_sampai=date(2030, 12, 31), is_active=True,
            issued_by=self._actor(),
        )
        _, warnings = validasi_kredensial_dokter(self.dokter.pk)
        self.assertFalse(any('SPK' in w for w in warnings))

    def _aktifkan_spk(self):
        pengajuan = PengajuanKredensial.objects.create(
            employee=self.dokter, unit_kerja=self.unit, jenis='AWAL',
            status='DISETUJUI',
        )
        keputusan = KeputusanKredensial.objects.create(
            pengajuan=pengajuan, outcome='DISETUJUI', decided_by=self._actor(),
        )
        return PenugasanKlinis.objects.create(
            employee=self.dokter, unit_kerja=self.unit, decision=keputusan,
            nomor_spk='SPK/TEST/2', berlaku_mulai=date(2025, 1, 1),
            berlaku_sampai=date(2030, 12, 31), is_active=True,
            issued_by=self._actor(),
        )

    def test_license_master_satisfies_sip_requirement(self):
        """SIP pada master izin profesi harus diakui, bukan dianggap belum ada."""
        self._aktifkan_spk()
        IzinProfesiPegawai.objects.create(
            pegawai=self.dokter, subtype='SIP', nomor_izin='SIP/TEST/1',
            pemberi_izin='Dinkes', profesi='Dokter Spesialis Jantung',
            validity_mode='DATED', tanggal_terbit=date(2025, 1, 1),
            tanggal_berakhir=date(2029, 12, 31), is_local_rs=True,
        )
        valid, warnings = validasi_kredensial_dokter(self.dokter.pk)
        self.assertTrue(valid, warnings)
        self.assertEqual(warnings, [])

    def test_lifetime_license_never_expires(self):
        self._aktifkan_spk()
        IzinProfesiPegawai.objects.create(
            pegawai=self.dokter, subtype='SIP', nomor_izin='SIP/TEST/2',
            pemberi_izin='Dinkes', profesi='Dokter Spesialis Jantung',
            validity_mode='LIFETIME', tanggal_terbit=date(2015, 1, 1),
            is_local_rs=True,
        )
        _, warnings = validasi_kredensial_dokter(self.dokter.pk)
        self.assertFalse(any('SIP' in w for w in warnings))

    def test_expired_license_still_warns(self):
        self._aktifkan_spk()
        IzinProfesiPegawai.objects.create(
            pegawai=self.dokter, subtype='SIP', nomor_izin='SIP/TEST/3',
            pemberi_izin='Dinkes', profesi='Dokter Spesialis Jantung',
            validity_mode='DATED', tanggal_terbit=date(2019, 1, 1),
            tanggal_berakhir=date(2021, 1, 1), is_local_rs=True,
        )
        valid, warnings = validasi_kredensial_dokter(self.dokter.pk)
        self.assertFalse(valid)
        self.assertTrue(any('kedaluwarsa' in w for w in warnings))

    @staticmethod
    def _actor():
        User = get_user_model()
        return User.objects.create_user(
            username=f'actor-{User.objects.count()}', password='x',
        )


class ApmSyncTests(JadwalFixture):
    def test_batal_marks_apm_row_as_libur(self):
        apm = JadwalDokterPoli.objects.create(
            nama_dokter=self.dokter.nama_lengkap, poliklinik='POLI_JANTUNG',
            hari_praktik='Senin', jam_mulai=time(8, 0), jam_selesai=time(12, 0),
            pegawai=self.dokter,
        )
        jadwal = JadwalPraktekHarian.objects.create(
            tanggal=SENIN, dokter_rencana=self.dokter, unit_kerja=self.unit,
            jam_mulai_rencana=time(8, 0), jam_selesai_rencana=time(12, 0),
            status_sesi='BATAL',
        )
        sync_jadwal_ke_apm(jadwal)
        apm.refresh_from_db()
        self.assertEqual(apm.status_ketersediaan, 'LIBUR')

    def test_rows_without_employee_link_are_untouched(self):
        apm = JadwalDokterPoli.objects.create(
            nama_dokter='dr. Tanpa Tautan', poliklinik='POLI_JANTUNG',
            hari_praktik='Senin', jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        jadwal = JadwalPraktekHarian.objects.create(
            tanggal=SENIN, dokter_rencana=self.dokter, unit_kerja=self.unit,
            jam_mulai_rencana=time(8, 0), jam_selesai_rencana=time(12, 0),
            status_sesi='BATAL',
        )
        sync_jadwal_ke_apm(jadwal)
        apm.refresh_from_db()
        self.assertEqual(apm.status_ketersediaan, 'BUKA')


class JadwalViewTests(JadwalFixture):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_plan_hc_workforce = True
        config.save()

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='pengelola-jadwal', password='x')
        UserProfile.objects.create(user=self.user, role='ADMIN_RS', unit_kerja=self.unit)
        HcGrant.objects.create(
            user=self.user, capability='can_view_hc', unit_kerja=self.unit,
        )
        HcGrant.objects.create(
            user=self.user, capability='can_plan_hc_workforce', unit_kerja=self.unit,
        )
        self.client.force_login(self.user)

    def test_rutin_list_renders_and_shows_warning_badge(self):
        JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        response = self.client.get(reverse('sdm:jadwal_praktek_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'dr. Uji Jantung')
        self.assertContains(response, 'SPK/RKK tidak aktif')

    def test_harian_page_generates_sessions(self):
        JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        response = self.client.get(
            reverse('sdm:jadwal_praktek_harian'), {'tanggal': SENIN.isoformat()}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.dokter.nama_lengkap)

    def test_create_rejects_overlapping_schedule(self):
        JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        response = self.client.post(reverse('sdm:jadwal_praktek_create'), {
            'dokter': self.dokter.pk,
            'unit_kerja': self.unit.pk,
            'hari': '0',
            'jam_mulai': '10:00',
            'jam_selesai': '13:00',
            'durasi_per_pasien_menit': '15',
            'kuota_jkn': '20',
            'kuota_non_jkn': '10',
            'batas_daftar_menit': '60',
            'is_active': 'on',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Bentrok jadwal')
        self.assertEqual(JadwalPraktekRutin.objects.count(), 1)

    def test_approving_leave_updates_session_and_logs_audit(self):
        rutin = JadwalPraktekRutin.objects.create(
            dokter=self.dokter, unit_kerja=self.unit, hari=0,
            jam_mulai=time(8, 0), jam_selesai=time(12, 0),
        )
        generate_jadwal_harian(SENIN)
        izin = PengajuanIzinDokter.objects.create(
            dokter=self.dokter, jenis='CUTI',
            tanggal_mulai=SENIN, tanggal_selesai=SENIN,
        )
        response = self.client.post(
            reverse('sdm:jadwal_praktek_izin_approve', args=[izin.pk])
        )
        self.assertEqual(response.status_code, 302)
        izin.refresh_from_db()
        self.assertEqual(izin.status, 'DISETUJUI')
        self.assertEqual(
            JadwalPraktekHarian.objects.get(tanggal=SENIN, jadwal_rutin=rutin).status_sesi,
            'BATAL',
        )
        self.assertTrue(LogAuditJadwal.objects.exists())
