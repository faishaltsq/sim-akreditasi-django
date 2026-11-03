"""Peta layanan pasien per unit — resolver, blok snapshot, dan halaman harian."""
from django.test import TestCase
from django.utils import timezone

from akreditasi.models import UnitKerja
from pasien.models import KunjunganPasien, Pasien, Ruangan


def _pasien(no_rm='RM-L1'):
    return Pasien.objects.create(
        no_rm=no_rm, nama_lengkap='Pasien Uji',
        tanggal_lahir='1980-01-01', jenis_kelamin='L')


def _unit(code, name, level=3, parent=None):
    unit, _ = UnitKerja.objects.get_or_create(
        code=code, defaults={'name': name, 'level': level, 'parent': parent})
    return unit


class NormalizeLabelTest(TestCase):
    def test_strips_case_punctuation_and_parenthetical(self):
        from akreditasi.layanan_unit import normalize_label
        self.assertEqual(
            normalize_label('Poli Anak (Pediatri)'), 'poli anak')
        self.assertEqual(
            normalize_label('POLI_PENYAKIT_DALAM'), 'poli penyakit dalam')
        self.assertEqual(
            normalize_label('Poli Jantung & Pembuluh Darah'),
            'poli jantung pembuluh darah')

    def test_empty_is_empty(self):
        from akreditasi.layanan_unit import normalize_label
        self.assertEqual(normalize_label(None), '')
        self.assertEqual(normalize_label(''), '')


class ResolveCodeTest(TestCase):
    def setUp(self):
        _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        _unit('POLI-BEDAH', 'Poliklinik Bedah (Umum, Orthopedi, Bedah Saraf)', 3)
        _unit('POLI-BSARAF', 'Poliklinik Bedah Saraf', 4)
        _unit('IGD', 'Instalasi Gawat Darurat (IGD 24 Jam & PONEK)', 3)

    def test_resolves_stored_label(self):
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(
            resolve_code('Poli Jantung & Pembuluh Darah', None, idx),
            'POLI-JANTUNG')

    def test_resolves_choice_code(self):
        """Formulir dan test lama menyimpan kode, bukan label."""
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(
            resolve_code('POLI_PENYAKIT_DALAM', None, idx), 'POLI-PD')

    def test_longest_alias_wins(self):
        """'Poli Bedah Saraf' tidak boleh jatuh ke POLI-BEDAH."""
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(resolve_code('Poli Bedah Saraf', None, idx), 'POLI-BSARAF')
        self.assertEqual(resolve_code('Poli Bedah Umum', None, idx), 'POLI-BEDAH')

    def test_unknown_text_resolves_to_none(self):
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertIsNone(resolve_code('Ruang Entah', None, idx))
        self.assertIsNone(resolve_code('', None, idx))

    def test_igd_short_text(self):
        from akreditasi.layanan_unit import alias_index, resolve_code
        idx = alias_index()
        self.assertEqual(resolve_code('IGD', None, idx), 'IGD')


class UnitCodesTest(TestCase):
    def test_parent_includes_descendants_not_ancestors(self):
        irj = _unit('IRJ', 'Instalasi Rawat Jalan (IRJ)', 2)
        pd = _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3, parent=irj)
        jantung = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4,
                        parent=pd)

        from akreditasi.layanan_unit import unit_codes
        self.assertIn('POLI-JANTUNG', unit_codes(pd))
        self.assertIn('POLI-JANTUNG', unit_codes(irj))
        self.assertIn('POLI-PD', unit_codes(irj))
        # downward only: a poli must not inherit its installation's patients
        self.assertNotIn('IRJ', unit_codes(pd))
        self.assertEqual(unit_codes(jantung), {'POLI-JANTUNG'})


class ResolveVisitIdsTest(TestCase):
    def setUp(self):
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.pasien = _pasien()
        self.mine = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-MINE', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        self.other = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-OTHER', jenis_kunjungan='RAJAL',
            poliklinik='Poli Penyakit Dalam',
            tanggal_masuk=timezone.now(), status='DAFTAR')

    def test_only_matching_visits_returned(self):
        from akreditasi.layanan_unit import resolve_visit_ids
        ids = resolve_visit_ids(KunjunganPasien.objects.all(), self.unit)
        self.assertEqual(ids, [self.mine.pk])

    def test_ruangan_match_for_inpatient(self):
        from akreditasi.layanan_unit import resolve_visit_ids
        bangsal = _unit('BANGSAL-DEWASA', 'Bangsal Dewasa Non-Bedah', 3)
        ruang = Ruangan.objects.create(
            kode='R-K1', nama='Bangsal Mawar (Kelas I)', kelas='1',
            jenis='RANAP', kapasitas=1)
        dari_bed = KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-BED', jenis_kunjungan='RANAP',
            poliklinik='Bangsal Mawar', bed=None,
            tanggal_masuk=timezone.now(), status='RANAP')
        from pasien.models import Bed
        bed = Bed.objects.create(ruangan=ruang, kode_bed='B1', status='TERISI')
        dari_bed.bed = bed
        dari_bed.save(update_fields=['bed'])

        ids = resolve_visit_ids(KunjunganPasien.objects.all(), bangsal)
        self.assertEqual(ids, [dari_bed.pk])


class RuanganMappingTest(TestCase):
    def test_every_ruangan_has_a_unit(self):
        """Ruangan baru tanpa entri RUANGAN_UNIT_CODE tidak muncul di dasbor."""
        from akreditasi.layanan_unit import RUANGAN_UNIT_CODE

        _unit('BANGSAL-DEWASA', 'Bangsal Dewasa Non-Bedah', 3)
        _unit('BANGSAL-VIP', 'Bangsal Perawatan VIP / Super VIP', 3)
        _unit('ICU', 'Instalasi Rawat Intensif Terpadu (ICU & HCU)', 3)
        _unit('IGD', 'Instalasi Gawat Darurat (IGD 24 Jam & PONEK)', 3)
        _unit('IBS', 'Instalasi Bedah Sentral (Kamar Operasi / OK)', 3)

        for kode, nama, jenis in (
            ('R-K1', 'Bangsal Mawar (Kelas I)', 'RANAP'),
            ('R-K2', 'Bangsal Melati (Kelas II)', 'RANAP'),
            ('R-K3', 'Bangsal Dahlia (Kelas III)', 'RANAP'),
            ('VIP-A', 'Paviliun Anggrek VIP', 'RANAP'),
            ('ICU-01', 'Intensive Care Unit (ICU)', 'ICU'),
            ('IGD-01', 'Ruang Resusitasi & Triase IGD', 'IGD'),
            ('IGD-02', 'Ruang Observasi IGD', 'IGD'),
            ('OK-01', 'Kamar Bedah Sentral', 'OK'),
        ):
            Ruangan.objects.create(
                kode=kode, nama=nama, kelas='1', jenis=jenis, kapasitas=1)

        known = set(UnitKerja.objects.values_list('code', flat=True))
        for ruang in Ruangan.objects.all():
            with self.subTest(ruangan=ruang.kode):
                self.assertIn(
                    ruang.kode, RUANGAN_UNIT_CODE,
                    f'Ruangan {ruang.kode} belum dipetakan ke unit kerja — '
                    f'tambahkan ke RUANGAN_UNIT_CODE di akreditasi/layanan_unit.py')
                self.assertIn(RUANGAN_UNIT_CODE[ruang.kode], known)


class SnapshotLayananTest(TestCase):
    def setUp(self):
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.pasien = _pasien('RM-SNAP')

    def test_layanan_lists_only_this_unit(self):
        from akreditasi.kontrol_data import build_unit_snapshot

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-MINE', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-OTHER', jenis_kunjungan='RAJAL',
            poliklinik='Poli Penyakit Dalam',
            tanggal_masuk=timezone.now(), status='DAFTAR')

        snap = build_unit_snapshot(self.unit)
        self.assertEqual(snap['layanan']['total'], 1)
        self.assertEqual(
            [i['no_kunjungan'] for i in snap['layanan']['items']], ['K-MINE'])
        self.assertTrue(snap['layanan']['mapped'])

    def test_emr_block_matches_unit_that_has_staff(self):
        """Defect 2: kehadiran staf tidak boleh mengosongkan blok EMR."""
        from accounts.models import UserProfile
        from django.contrib.auth import get_user_model
        from akreditasi.kontrol_data import build_unit_snapshot

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-AKTIF', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='ASESMEN')

        before = build_unit_snapshot(self.unit)['emr']['active_total']
        self.assertEqual(before, 1)

        user = get_user_model().objects.create_user('kep.snap', 'ks@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)

        after = build_unit_snapshot(self.unit)['emr']['active_total']
        self.assertEqual(after, 1, 'blok EMR kosong setelah staf ditugaskan')

    def test_unit_without_service_is_unmapped_not_zero(self):
        from akreditasi.kontrol_data import build_unit_snapshot
        komite = _unit('KOMITE-MUTU', 'Komite Mutu PMKP & Keselamatan Pasien', 2)
        snap = build_unit_snapshot(komite)
        self.assertFalse(snap['layanan']['mapped'])
        self.assertEqual(snap['layanan']['items'], [])

    def test_today_means_admitted_today(self):
        """Kunjungan ranap lama tidak boleh muncul sebagai layanan hari ini."""
        from datetime import timedelta
        from akreditasi.kontrol_data import build_unit_snapshot

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-LAMA', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now() - timedelta(days=3), status='RANAP')

        snap = build_unit_snapshot(self.unit)
        self.assertEqual(snap['layanan']['total'], 0)
        self.assertTrue(snap['layanan']['mapped'])

    def test_previous_day_is_reachable(self):
        from datetime import timedelta
        from akreditasi.kontrol_data import _layanan_block

        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-KEMARIN', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now() - timedelta(days=1), status='PULANG')

        kemarin = timezone.localdate() - timedelta(days=1)
        blk = _layanan_block(self.unit, on_date=kemarin)
        self.assertEqual(blk['total'], 1)
        self.assertEqual(blk['items'][0]['no_kunjungan'], 'K-KEMARIN')


class LayananPageTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache

        cache.clear()
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.other = _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        self.pasien = _pasien('RM-PAGE')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-PAGE-1', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah', dpjp='dr. Faisal, Sp.JP',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-PAGE-2', jenis_kunjungan='RAJAL',
            poliklinik='Poli Penyakit Dalam',
            tanggal_masuk=timezone.now(), status='DAFTAR')

        user = get_user_model().objects.create_user('kep.page', 'kp@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)
        self.client.force_login(user)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_lists_only_own_unit(self):
        from django.urls import reverse

        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertEqual(res.status_code, 200)
        body = res.content.decode()
        self.assertIn('K-PAGE-1', body)
        self.assertNotIn('K-PAGE-2', body)

    def test_unit_scoped_user_cannot_switch_unit(self):
        from django.urls import reverse

        res = self.client.get(
            reverse('akreditasi:kontrol_layanan'), {'unit': self.other.pk})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['unit'].pk, self.unit.pk)

    def test_anonymous_redirected(self):
        from django.urls import reverse

        self.client.logout()
        res = self.client.get(reverse('akreditasi:kontrol_layanan'))
        self.assertEqual(res.status_code, 302)

    def test_invalid_date_falls_back_to_today(self):
        from django.urls import reverse

        res = self.client.get(
            reverse('akreditasi:kontrol_layanan'), {'tanggal': 'bukan-tanggal'})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['tanggal'], timezone.localdate())

    def test_no_sidebar_shell(self):
        from django.urls import reverse

        body = self.client.get(reverse('akreditasi:kontrol_layanan')).content.decode()
        self.assertNotIn('sidebar-desktop', body)
        self.assertNotIn('id="mobileSidebar"', body)
        self.assertIn('static/css/kontrol.', body)


class LayananPageQueryBudgetTest(TestCase):
    BUDGET = 12

    def test_warm_request_within_budget(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        from django.urls import reverse

        cache.clear()
        unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        user = get_user_model().objects.create_user('kep.q', 'kq@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=unit)
        self.client.force_login(user)
        url = reverse('akreditasi:kontrol_layanan')
        self.client.get(url)
        with CaptureQueriesContext(connection) as ctx:
            res = self.client.get(url)
        self.assertEqual(res.status_code, 200)
        self.assertLessEqual(len(ctx.captured_queries), self.BUDGET,
                             f'{len(ctx.captured_queries)} query, anggaran {self.BUDGET}')
        cache.clear()


class LayananBlockTemplateTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache

        cache.clear()
        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.pasien = _pasien('RM-TPL')
        KunjunganPasien.objects.create(
            pasien=self.pasien, no_kunjungan='K-TPL-1', jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(), status='DAFTAR')
        user = get_user_model().objects.create_user('kep.tpl', 'kt@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)
        self.client.force_login(user)

    def tearDown(self):
        from django.core.cache import cache
        cache.clear()

    def test_block_renders_heading_and_date(self):
        from django.urls import reverse

        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        body = res.content.decode()
        self.assertIn('LAYANAN UNIT', body.upper())
        self.assertIn('Poliklinik Jantung &amp; Pembuluh Darah', body)
        self.assertIn('Daftar layanan pasien hari ini', body)
        self.assertIn(timezone.localdate().strftime('%Y'), body)

    def test_generic_strip_is_gone(self):
        from django.urls import reverse

        body = self.client.get(reverse('akreditasi:kontrol_emr')).content.decode()
        self.assertNotIn('kontrol-modlinks', body)
        for label in ('Daftar kunjungan', 'Rawat jalan', 'Rekap KPS'):
            with self.subTest(label=label):
                self.assertNotIn(label, body)

    def test_block_present_on_risk_and_document_dashboards(self):
        from django.urls import reverse

        for name in ('kontrol_risiko', 'kontrol_dokumen'):
            with self.subTest(name=name):
                body = self.client.get(reverse('akreditasi:' + name)).content.decode()
                self.assertIn('LAYANAN UNIT', body.upper())

    def test_unmapped_unit_explains_itself(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache
        from django.urls import reverse

        komite = _unit('KOMITE-MUTU', 'Komite Mutu PMKP & Keselamatan Pasien', 2)
        user = get_user_model().objects.create_user('komite.tpl', 'km@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=komite)
        self.client.force_login(user)
        cache.clear()

        body = self.client.get(reverse('akreditasi:kontrol_emr')).content.decode()
        self.assertIn('belum memiliki pemetaan layanan klinis untuk daftar kunjungan harian', body)
        self.assertNotIn('tidak memiliki layanan pendaftaran pasien', body)
        self.assertNotIn('0 pasien', body)


class IndicatorBlockRegressionTest(TestCase):
    """``tercapai`` adalah @property, bukan kolom — jangan pernah difilter di SQL.

    Bug ini lolos dari test lama karena ``_indicator_block`` keluar lebih awal
    saat belum ada ``CatatanIndikator``; di database nyata yang sudah punya
    catatan, setiap halaman kontrol melempar FieldError dan 500.
    """

    def setUp(self):
        from akreditasi.risiko_models import CatatanIndikator, IndikatorMutu

        self.unit = _unit('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4)
        self.indikator = IndikatorMutu.objects.create(
            unit=self.unit, kode_indikator='INM-REG-1',
            nama_indikator='Kepatuhan Kebersihan Tangan',
            target_nilai=85, arah_target='MIN', aktif=True)
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=1, tahun=timezone.localdate().year,
            nilai_numerator=90, nilai_denominator=100)
        CatatanIndikator.objects.create(
            indikator=self.indikator, bulan=2, tahun=timezone.localdate().year,
            nilai_numerator=70, nilai_denominator=100)

    def test_block_counts_on_target_without_field_error(self):
        from akreditasi.kontrol_data import _indicator_block
        blk = _indicator_block({self.unit.pk}, timezone.localdate().year)
        self.assertEqual(blk['catatan_total'], 2)
        self.assertEqual(blk['on_target'], 1)
        self.assertEqual(blk['below_target'], 1)

    def test_dashboard_renders_with_indicator_rows(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache
        from django.urls import reverse

        cache.clear()
        user = get_user_model().objects.create_user('kep.ind', 'ki@rs.id', 'p')
        UserProfile.objects.create(user=user, role='KEPALA_UNIT', unit_kerja=self.unit)
        self.client.force_login(user)
        res = self.client.get(reverse('akreditasi:kontrol_emr'))
        self.assertEqual(res.status_code, 200)
        cache.clear()


class PendaftaranIGDIntegrationTest(TestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from accounts.models import UserProfile
        from django.core.cache import cache

        cache.clear()
        self.igd_unit = _unit('IGD', 'Instalasi Gawat Darurat (IGD)', 2)
        self.rm_unit = _unit('REKAM-MEDIS', 'Instalasi Rekam Medis & Pendaftaran', 2)

        user_rm = get_user_model().objects.create_user('staf.pendaftaran', 'sp@rs.id', 'p')
        UserProfile.objects.create(user=user_rm, role='STAF_NAKES', unit_kerja=self.rm_unit)
        self.user_rm = user_rm

        user_admin = get_user_model().objects.create_user('admin.rs', 'admin@rs.id', 'p')
        UserProfile.objects.create(user=user_admin, role='SUPER_ADMIN', unit_kerja=None)
        self.user_admin = user_admin

    def test_pendaftaran_baru_ke_igd_muncul_di_kontrol_emr_dan_layanan(self):
        from django.urls import reverse
        from pasien.models import KunjunganPasien

        self.client.force_login(self.user_rm)
        post_data = {
            'is_pasien_baru': '1',
            'no_rm': 'RM-TEST-IGD-01',
            'nama_lengkap': 'Aimto IGD Patient',
            'tanggal_lahir': '1998-07-20',
            'jenis_kelamin': 'L',
            'jenis_kunjungan': 'IGD',
            'triage': 'KUNING',
            'dpjp_igd_baru': 'dr. Jaga IGD',
            'general_consent': '1',
        }
        res = self.client.post(reverse('pasien:kunjungan_baru'), post_data)
        self.assertEqual(res.status_code, 302)

        kunjungan = KunjunganPasien.objects.filter(pasien__nama_lengkap='Aimto IGD Patient').first()
        self.assertIsNotNone(kunjungan)
        self.assertEqual(kunjungan.jenis_kunjungan, 'IGD')
        self.assertEqual(kunjungan.poliklinik, 'IGD')
        self.assertEqual(kunjungan.unit_kerja, self.igd_unit)
        self.assertEqual(kunjungan.triage, 'KUNING')
        self.assertEqual(kunjungan.status, 'TRIAGE')

        # Check kontrol_emr for IGD unit
        self.client.force_login(self.user_admin)
        emr_res = self.client.get(reverse('akreditasi:kontrol_emr'), {'unit': self.igd_unit.pk})
        self.assertEqual(emr_res.status_code, 200)
        self.assertIn('Aimto IGD Patient', emr_res.content.decode())

        # Check kontrol_layanan for IGD unit
        layanan_res = self.client.get(reverse('akreditasi:kontrol_layanan'), {'unit': self.igd_unit.pk})
        self.assertEqual(layanan_res.status_code, 200)
        self.assertIn('Aimto IGD Patient', layanan_res.content.decode())

    def test_routing_ulang_ke_igd_memperbarui_poliklinik_dan_unit_kerja(self):
        from django.urls import reverse
        from pasien.models import KunjunganPasien

        pasien = _pasien('RM-ROUTE-01')
        k = KunjunganPasien.objects.create(
            pasien=pasien,
            no_kunjungan='K-ROUTE-01',
            jenis_kunjungan='RAJAL',
            poliklinik='Poli Jantung & Pembuluh Darah',
            tanggal_masuk=timezone.now(),
            status='DAFTAR'
        )

        self.client.force_login(self.user_rm)
        route_data = {
            'tujuan': 'IGD',
            'triage': 'MERAH',
            'dpjp': 'dr. Pratama',
        }
        res = self.client.post(reverse('pasien:pendaftaran_route', args=[k.pk]), route_data)
        self.assertEqual(res.status_code, 302)

        k.refresh_from_db()
        self.assertEqual(k.jenis_kunjungan, 'IGD')
        self.assertEqual(k.poliklinik, 'IGD')
        self.assertEqual(k.unit_kerja, self.igd_unit)
        self.assertEqual(k.triage, 'MERAH')
        self.assertEqual(k.status, 'TRIAGE')

    def test_overnight_active_igd_patient_appears_in_today_layanan(self):
        from datetime import timedelta
        from django.urls import reverse
        from django.utils import timezone
        from akreditasi.kontrol_data import _layanan_block
        from pasien.models import KunjunganPasien

        pasien_active = _pasien('RM-OVERNIGHT-01')
        k_active = KunjunganPasien.objects.create(
            pasien=pasien_active,
            no_kunjungan='IGD-OVERNIGHT-01',
            jenis_kunjungan='IGD',
            poliklinik='IGD',
            unit_kerja=self.igd_unit,
            tanggal_masuk=timezone.now() - timedelta(days=1),
            status='TRIAGE',
            triage='KUNING',
        )

        pasien_discharged = _pasien('RM-OVERNIGHT-02')
        k_discharged = KunjunganPasien.objects.create(
            pasien=pasien_discharged,
            no_kunjungan='IGD-OVERNIGHT-02',
            jenis_kunjungan='IGD',
            poliklinik='IGD',
            unit_kerja=self.igd_unit,
            tanggal_masuk=timezone.now() - timedelta(days=1),
            status='PULANG',
            triage='HIJAU',
        )

        today_block = _layanan_block(self.igd_unit, on_date=timezone.localdate())
        item_pks = [item['pk'] for item in today_block['items']]
        self.assertIn(k_active.pk, item_pks)
        self.assertNotIn(k_discharged.pk, item_pks)

        # Kontrol EMR and layanan HTML rendering
        self.client.force_login(self.user_admin)
        emr_res = self.client.get(reverse('akreditasi:kontrol_emr'), {'unit': self.igd_unit.pk})
        self.assertEqual(emr_res.status_code, 200)
        self.assertContains(emr_res, '1 pasien')

        layanan_res = self.client.get(reverse('akreditasi:kontrol_layanan'), {'unit': self.igd_unit.pk})
        self.assertEqual(layanan_res.status_code, 200)
        self.assertIn('IGD-OVERNIGHT-01', layanan_res.content.decode())
        self.assertNotIn('IGD-OVERNIGHT-02', layanan_res.content.decode())




class AdmissionDeskTest(TestCase):
    """Loket pendaftaran bukan unit klinis: layanan dan KPI dibaca RS-wide."""

    def test_admission_codes_are_desks(self):
        from akreditasi.layanan_unit import is_admission_desk

        for code, name in (
            ('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission'),
            ('ADMISI', 'Unit Pendaftaran & Admisi Pasien'),
        ):
            with self.subTest(code=code):
                self.assertTrue(is_admission_desk(_unit(code, name, 4)))

    def test_parent_installation_of_a_desk_is_a_desk(self):
        from akreditasi.layanan_unit import is_admission_desk

        parent = _unit('REKAM-MEDIS', 'Instalasi Rekam Medis & Pendaftaran', 3)
        _unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', 4, parent)
        self.assertTrue(is_admission_desk(parent))

    def test_clinical_and_committee_units_are_not_desks(self):
        from akreditasi.layanan_unit import is_admission_desk

        for code, name, level in (
            ('POLI-JANTUNG', 'Poliklinik Jantung & Pembuluh Darah', 4),
            ('KOMITE-MUTU', 'Komite Mutu PMKP & Keselamatan Pasien', 2),
            ('DIREKSI', 'Direksi', 1),
        ):
            with self.subTest(code=code):
                self.assertFalse(is_admission_desk(_unit(code, name, level)))

    def test_none_is_not_a_desk(self):
        from akreditasi.layanan_unit import is_admission_desk

        self.assertFalse(is_admission_desk(None))

    def _visit(self, no, poli, status='DAFTAR', jenis='RAJAL'):
        return KunjunganPasien.objects.create(
            pasien=_pasien('RM-' + no), no_kunjungan=no,
            jenis_kunjungan=jenis, tanggal_masuk=timezone.now(),
            poliklinik=poli, status=status)

    def test_desk_block_is_hospital_wide(self):
        from akreditasi.kontrol_data import _layanan_block

        _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        desk = _unit('PENDAFTARAN-ADMISSION', 'Unit Pendaftaran & Admission', 4)
        self._visit('K-1', 'Poli Penyakit Dalam')
        block = _layanan_block(desk)
        self.assertTrue(block['mapped'])
        self.assertEqual(block['scope'], 'hospital')
        self.assertEqual(block['total'], 1)

    def test_clinical_block_stays_unit_scoped(self):
        from akreditasi.kontrol_data import _layanan_block

        poli = _unit('POLI-PD', 'Poliklinik Penyakit Dalam', 3)
        _unit('POLI-ANAK', 'Poliklinik Anak', 3)
        self._visit('K-2', 'Poli Penyakit Dalam')
        self._visit('K-3', 'Poli Anak')
        block = _layanan_block(poli)
        self.assertTrue(block['mapped'])
        self.assertEqual(block['scope'], 'unit')
        self.assertEqual(block['total'], 1)

