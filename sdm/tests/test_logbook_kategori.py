"""Kategori, rincian harian, dan kompatibilitas entri logbook klinis."""
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from sdm.forms.logbook import EntriLogbookForm
from sdm.models import EntriLogbookKlinis
from sdm.services.logbook import logbook_recap
from sdm.tests.test_logbook import LogbookBase


class LogbookKategoriTests(LogbookBase):
    def setUp(self):
        super().setUp()
        self.owner = self._plain_user('log-kategori-owner')
        self.employee = self._employee(user=self.owner)

    def _entry(self, **kwargs):
        return EntriLogbookKlinis(
            employee=self.employee, tanggal=self.today, unit_kerja=self.unit,
            tindakan='Konsultasi lintas profesi', **kwargs,
        )

    def _form(self, **kwargs):
        data = {
            'tanggal': self.today.isoformat(),
            'unit_kerja': str(self.unit.pk),
            'modus': 'bebas',
            'tindakan': 'Konsultasi lintas profesi',
            'jumlah_mandiri': 0,
            'jumlah_supervisi': 0,
            'jumlah_kolaborasi': 2,
        }
        data.update(kwargs)
        return EntriLogbookForm(data, employee=self.employee, user=self.owner)

    def test_kolaborasi_dengan_rincian_harian_valid_dan_tampil(self):
        waktu = timezone.localtime().replace(second=0, microsecond=0)
        form = self._form(
            kategori='K', waktu=waktu.strftime('%Y-%m-%dT%H:%M'),
            pasien_ref='AB / RM **42', shift='PAGI',
        )
        self.assertTrue(form.is_valid(), form.errors)
        entry = form.save(commit=False)
        entry.employee = self.employee
        entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.kategori, 'K')
        self.assertEqual(entry.jumlah_kolaborasi, 2)
        self.assertEqual(entry.waktu, waktu)
        self.assertEqual(entry.pasien_ref, 'AB / RM **42')
        self.assertEqual(entry.shift, 'PAGI')
        self.client.force_login(self.owner)
        response = self.client.get(reverse('sdm:logbook_list'))
        self.assertContains(response, 'Kolaborasi')
        self.assertContains(response, 'AB / RM **42')
        self.assertContains(response, waktu.strftime('%H:%M'))
        self.assertContains(response, 'Pagi')

    def test_tiga_jumlah_nol_ditolak_model_dan_form(self):
        entry = self._entry()
        with self.assertRaises(ValidationError) as caught:
            entry.full_clean()
        self.assertIn('jumlah_mandiri', caught.exception.message_dict)
        form = self._form(jumlah_kolaborasi=0)
        self.assertFalse(form.is_valid())
        self.assertIn('lebih dari nol', str(form.errors))

    def test_kategori_tidak_dikirim_memakai_default_m(self):
        form = self._form(jumlah_mandiri=1, jumlah_kolaborasi=0)
        self.assertTrue(form.is_valid(), form.errors)
        entry = form.save(commit=False)
        entry.employee = self.employee
        entry.save()
        entry.refresh_from_db()
        self.assertEqual(entry.kategori, 'M')

    def test_kategori_tidak_valid_ditolak(self):
        form = self._form(kategori='X')
        self.assertFalse(form.is_valid())
        self.assertIn('kategori', form.errors)

    def test_rekap_kolaborasi_memakai_satu_query_agregat(self):
        self._entry(jumlah_mandiri=2, jumlah_supervisi=3, jumlah_kolaborasi=4).save()
        self._entry(kategori='K', jumlah_kolaborasi=5).save()
        self._entry(kategori='K', jumlah_kolaborasi=99,
                    waktu=timezone.now() - timedelta(days=1250)).save()
        # Jendela rekap tetap mengikuti tanggal, bukan waktu yang opsional.
        old = self._entry(kategori='K', jumlah_kolaborasi=100)
        old.tanggal = self.today - timedelta(days=1250)
        old.save()
        with self.assertNumQueries(1):
            recap = logbook_recap(self.employee)
        self.assertEqual(recap['mandiri'], 2)
        self.assertEqual(recap['supervisi'], 3)
        self.assertEqual(recap['kolaborasi'], 108)
        self.assertEqual(recap['total'], 113)
        self.assertEqual(recap['per_tindakan'], [{
            'label': 'Konsultasi lintas profesi', 'mandiri': 2,
            'supervisi': 3, 'kolaborasi': 108,
        }])

    def test_entri_lama_tanpa_waktu_tetap_tampil_dan_direkap(self):
        entry = self._entry(jumlah_mandiri=3)
        entry.save()
        entry.refresh_from_db()
        self.assertIsNone(entry.waktu)
        self.assertEqual(entry.kategori, 'M')
        self.client.force_login(self.owner)
        response = self.client.get(reverse('sdm:logbook_list'))
        self.assertContains(response, entry.tindakan)
        self.assertContains(response, 'Belum dicatat')
        recap = logbook_recap(self.employee)
        self.assertEqual(recap['total'], 3)
        self.assertEqual(recap['kolaborasi'], 0)
        self.assertEqual(recap['per_tindakan'][0]['kolaborasi'], 0)
