"""Tes alur 'Tidak Ada Kejadian' (KEJADIAN_LAIN) pada Logbook IGD.

Memverifikasi tiga properti utama:
  1. POST shift nihil berhasil tanpa mengisi lokasi & deskripsi.
  2. sync_ke_ikp() tidak menghasilkan baris InsidenKeselamatan.
  3. Kejadian nyata tetap membutuhkan lokasi + deskripsi dan terhubung ke IKP.
"""

from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import UserProfile
from akreditasi.logbook_models import LogbookHarian, LogbookKejadian
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import InsidenKeselamatan

TANGGAL = date(2026, 11, 1)


def _unit():
    return UnitKerja.objects.create(code='IGD-TES', name='IGD Test', level=1)


def _user(username, role, unit):
    u = User.objects.create_user(username=username, password='x')
    UserProfile.objects.update_or_create(user=u, defaults={'role': role, 'unit_kerja': unit})
    return u


def _logbook(unit, dibuat_oleh):
    return LogbookHarian.objects.create(
        unit=unit,
        tanggal=TANGGAL,
        shift='PAGI',
        dibuat_oleh=dibuat_oleh,
    )


class TidakAdaKejadianViewTest(TestCase):
    """POST ke logbook_simpan_kejadian dengan jenis KEJADIAN_LAIN."""

    def setUp(self):
        self.unit = _unit()
        self.petugas = _user('petugas-tad', 'STAF_NAKES', self.unit)
        self.logbook = _logbook(self.unit, self.petugas)
        self.url = reverse('akreditasi:logbook_simpan_kejadian', args=[self.logbook.pk])

    def _post(self, data):
        self.client.force_login(self.petugas)
        return self.client.post(self.url, data)

    # ------------------------------------------------------------------
    # 1. Shift nihil tanpa lokasi & deskripsi harus berhasil
    # ------------------------------------------------------------------
    def test_simpan_kejadian_tidak_ada_kejadian_sukses_tanpa_deskripsi_dan_lokasi(self):
        r = self._post({
            'jenis_insiden': 'KEJADIAN_LAIN',
            'tingkat_keparahan': '',   # dikosongkan sengaja — view harus isi default
            'lokasi_kejadian': '',
            'deskripsi_kejadian': '',
        })
        self.assertEqual(r.status_code, 302)

        kj = LogbookKejadian.objects.get(logbook=self.logbook)
        self.assertEqual(kj.jenis_insiden, 'KEJADIAN_LAIN')
        self.assertEqual(kj.tingkat_keparahan, 'TIDAK_CEDERA')
        self.assertIn('nihil', kj.deskripsi_kejadian.lower())
        self.assertFalse(kj.pasien_terpapar)

        # Tidak boleh terhubung ke IKP
        self.assertIsNone(kj.insiden_id, 'Entri nihil tidak boleh punya FK ke InsidenKeselamatan')
        self.assertEqual(InsidenKeselamatan.objects.count(), 0)

    def test_simpan_kejadian_tidak_ada_kejadian_dengan_lokasi_eksplisit(self):
        """Jika perawat tetap isi lokasi, nilai itu yang tersimpan (bukan di-override)."""
        r = self._post({
            'jenis_insiden': 'KEJADIAN_LAIN',
            'tingkat_keparahan': 'TIDAK_CEDERA',
            'lokasi_kejadian': 'Pos Triase',
            'deskripsi_kejadian': '',
        })
        self.assertEqual(r.status_code, 302)
        kj = LogbookKejadian.objects.get(logbook=self.logbook)
        self.assertEqual(kj.lokasi_kejadian, 'Pos Triase')

    # ------------------------------------------------------------------
    # 2. sync_ke_ikp() langsung pada objek KEJADIAN_LAIN → None
    # ------------------------------------------------------------------
    def test_sync_ke_ikp_tidak_menghasilkan_insiden_untuk_kejadian_lain(self):
        kj = LogbookKejadian.objects.create(
            logbook=self.logbook,
            jenis_insiden='KEJADIAN_LAIN',
            tingkat_keparahan='TIDAK_CEDERA',
            lokasi_kejadian='IGD Test',
            deskripsi_kejadian='Laporan nihil programmatic',
            dilaporkan_oleh=self.petugas,
        )
        result = kj.sync_ke_ikp()
        self.assertIsNone(result, 'sync_ke_ikp() harus mengembalikan None untuk KEJADIAN_LAIN')
        self.assertIsNone(kj.insiden_id)
        self.assertEqual(InsidenKeselamatan.objects.count(), 0,
                         'Tidak boleh ada baris baru di InsidenKeselamatan')

    # ------------------------------------------------------------------
    # 3. Kejadian nyata tetap wajib lokasi & terhubung ke IKP
    # ------------------------------------------------------------------
    def test_kejadian_biasa_tanpa_lokasi_ditolak(self):
        self._post({
            'jenis_insiden': 'KTD',
            'tingkat_keparahan': 'MINOR',
            'lokasi_kejadian': '',
            'deskripsi_kejadian': 'Salah pemberian obat',
        })
        self.assertFalse(LogbookKejadian.objects.exists(),
                         'POST tanpa lokasi pada KTD harus ditolak')

    def test_kejadian_biasa_tanpa_deskripsi_ditolak(self):
        self._post({
            'jenis_insiden': 'KNC',
            'tingkat_keparahan': 'MINOR',
            'lokasi_kejadian': 'Ruang bedah',
            'deskripsi_kejadian': '',
        })
        self.assertFalse(LogbookKejadian.objects.exists(),
                         'POST tanpa deskripsi pada KNC harus ditolak')

    def test_kejadian_biasa_lengkap_terhubung_ikp(self):
        r = self._post({
            'jenis_insiden': 'KTD',
            'tingkat_keparahan': 'MODERAT',
            'waktu_kejadian': '14:20',
            'lokasi_kejadian': 'Ruang resusitasi',
            'deskripsi_kejadian': 'Keterlambatan obat trombolitik',
            'tindakan_segera': 'Lapor DPJP',
        })
        self.assertEqual(r.status_code, 302)
        kj = LogbookKejadian.objects.get(logbook=self.logbook)
        self.assertIsNotNone(kj.insiden_id,
                             'Kejadian KTD lengkap harus punya FK ke InsidenKeselamatan')
        self.assertEqual(InsidenKeselamatan.objects.count(), 1)
        ikp = InsidenKeselamatan.objects.first()
        self.assertEqual(ikp.jenis_insiden, 'KTD')

    # ------------------------------------------------------------------
    # 4. Label dropdown harus "Tidak Ada Kejadian"
    # ------------------------------------------------------------------
    def test_label_kejadian_lain_adalah_tidak_ada_kejadian(self):
        choices = dict(InsidenKeselamatan.JENIS_CHOICES)
        self.assertEqual(choices['KEJADIAN_LAIN'], 'Tidak Ada Kejadian')
