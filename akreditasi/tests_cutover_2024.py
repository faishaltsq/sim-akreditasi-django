"""Regresi gerbang cutover STARKES 2024 (F0.9).

Dua kegagalan nyata yang dijaga di sini:

1. ``starkes_2024_cutover`` dulu memanggil ``import_instrumen_2024`` dengan
   opsi ``replace``/``mapping_report`` yang tidak dimiliki command itu, jadi
   cutover selalu berhenti dengan ``TypeError`` sebelum menyentuh database.
2. Setelah impor berhasil, framework 2024 dibuat tanpa mengarsipkan yang lama,
   sehingga dua katalog bisa sama-sama ``is_active=True``.

Keduanya tidak terdeteksi karena tidak ada satu pun tes yang menyentuh command
ini. Berkas ini menutup celah tersebut.
"""
from io import StringIO
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from akreditasi.models import AktivasiKatalog, Framework, StandardItem

FIXTURE = str(Path(settings.BASE_DIR) / 'fixtures' / 'standar_akreditasi_2024.json')


class Starkes2024CutoverTest(TestCase):
    def test_dry_run_tidak_menyentuh_database(self):
        sebelum = (
            Framework.objects.count(),
            StandardItem.objects.count(),
            AktivasiKatalog.objects.count(),
        )
        out = StringIO()
        call_command('starkes_2024_cutover', fixture=FIXTURE, stdout=out)

        self.assertIn('DRY RUN', out.getvalue())
        sesudah = (
            Framework.objects.count(),
            StandardItem.objects.count(),
            AktivasiKatalog.objects.count(),
        )
        self.assertEqual(sebelum, sesudah, 'dry run tidak boleh menulis apa pun')

    def test_apply_mengaktifkan_2024_dan_mencatat_aktivasi(self):
        out = StringIO()
        call_command(
            'starkes_2024_cutover',
            fixture=FIXTURE,
            apply=True,
            skip_backup_check=True,
            backup_reference='uji-backup-2024',
            stdout=out,
        )

        aktif = Framework.objects.filter(is_active=True)
        self.assertEqual(aktif.count(), 1, 'harus tepat satu katalog aktif')
        self.assertEqual(aktif.first().version, '2024')
        self.assertEqual(aktif.first().lifecycle, 'ACTIVE')

        self.assertGreater(StandardItem.objects.count(), 0)

        receipt = AktivasiKatalog.objects.get()
        self.assertEqual(receipt.status, 'ACTIVE')
        self.assertEqual(receipt.backup_reference, 'uji-backup-2024')
        self.assertEqual(receipt.framework_id, aktif.first().pk)

    def test_reset_scores_menolak_tanpa_referensi_backup(self):
        with self.assertRaisesMessage(Exception, 'backup-reference'):
            call_command(
                'starkes_2024_cutover',
                fixture=FIXTURE,
                apply=True,
                skip_backup_check=True,
                reset_scores=True,
                stdout=StringIO(),
            )
