"""Kontrak bentuk snapshot Integrated Control.

`_kontrol_data_block()` membaca key dengan `snapshot[...][...]` tanpa guard,
jadi setiap cabang di `kontrol_data.py` — termasuk early-return saat data
kosong — WAJIB mengembalikan key yang sama. Bila tidak, endpoint ringkasan AI
jatuh dengan KeyError (pernah terjadi: `bed_total`).
"""
from django.contrib.auth import get_user_model
from django.test import TestCase

from akreditasi import kontrol_data


class SnapshotShapeTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        U = get_user_model()
        cls.user = U.objects.filter(is_superuser=True).first() or U.objects.create_superuser(
            username='snap', email='snap@example.test', password='x')

    def _snapshot(self):
        return kontrol_data.build_unit_snapshot(None, profile=None, year=2026)

    def test_data_block_tidak_keyerror_saat_data_kosong(self):
        from akreditasi.ai_service import _kontrol_data_block
        snapshot = self._snapshot()
        try:
            teks = _kontrol_data_block(snapshot)
        except KeyError as exc:
            self.fail('snapshot kosong memicu KeyError: %s' % exc)
        self.assertIn('Risiko terdaftar', teks)
        self.assertIn('Okupansi bed', teks)

    def test_block_emr_punya_key_lengkap_di_semua_cabang(self):
        wajib = {
            'active_by_jenis', 'active_total', 'cppt_gap', 'assessment_gap',
            'bed_occupancy_pct', 'bed_scope', 'bed_total',
            'cppt_total', 'assessment_total',
        }
        blok = kontrol_data._emr_block([])
        self.assertEqual(wajib - set(blok), set(),
                         'key hilang di _emr_block: %s' % (wajib - set(blok)))

    def test_ringkasan_ai_tidak_crash_saat_data_kosong(self):
        """Kegagalan AI boleh 502 (JSON), tapi tidak boleh 500 karena KeyError.

        500 = exception tak tertangani di dalam view (bug bentuk snapshot).
        502 = jalur gagal-AI yang memang by design dan mengembalikan JSON.
        """
        from django.urls import reverse
        self.client.force_login(self.user)
        r = self.client.post(reverse('akreditasi:kontrol_ringkasan_ai'),
                             {'portal': 'risiko'})
        self.assertNotEqual(r.status_code, 500,
                            'ringkasan AI crash 500 saat data kosong')
        if r.status_code == 502:
            self.assertIn('application/json', r['Content-Type'],
                          '502 harus berupa JSON terstruktur, bukan halaman error')
