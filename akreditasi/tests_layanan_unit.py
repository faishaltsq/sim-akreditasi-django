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
