"""Unit test untuk Modul Logbook 36 Bulan Kredensial."""
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DrafDokumenKredensial,
    EntriLogbookKlinis,
    Pegawai,
    PenempatanPegawai,
)
from sdm.services.dokumen_kredensial import (
    REGISTRY,
    finalize,
    generate_draft,
    render_pdf,
)
from sdm.storage_backend import SupabasePrivateStorage
from sdm.tests.test_dokumen_kredensial import pdf_text
from sdm.tests.test_storage_backend import FakeResponse, FakeSession


class Logbook36BulanModulTests(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Bangsal Anak', code='HC-ANK-TEST')
        User = get_user_model()
        self.user = User.objects.create_user(username='perawat.siska')
        UserProfile.objects.create(user=self.user, role='STAF_NAKES', unit_kerja=self.unit)

        self.pegawai = Pegawai.objects.create(
            nama_lengkap='Siska Lestari, S.Kep., Ners',
            kategori='PPA',
            profesi='Perawat',
            nomor_pegawai='NIP-19950812-202101-2-001',
            jabatan='Perawat Klinik I (PK I)',
            akun=self.user,
        )
        PenempatanPegawai.objects.create(
            pegawai=self.pegawai,
            unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=100),
            alokasi_fte=Decimal('1.00'),
        )

    def _storage(self):
        session = FakeSession(FakeResponse(200, content=b''))
        storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co',
            api_key='service-key',
            bucket='hc-private',
            session=session,
        )
        served = {}

        def fetch_object(storage_key, **kwargs):
            return served[storage_key]

        storage.fetch_object = fetch_object
        self.served = served
        original_upload = storage.upload

        def upload(file_obj, **kwargs):
            payload = file_obj.getvalue()
            stored = original_upload(file_obj, **kwargs)
            served[stored.storage_key] = payload
            return stored

        storage.upload = upload
        return session, storage

    def test_logbook_36bulan_manual_fields_registered(self):
        spec = REGISTRY['LOGBOOK_36BULAN']
        fields = [k for k, _v in spec['manual_fields']]
        self.assertIn('jenjang_klinis_diusulkan', fields)
        self.assertIn('evaluasi_tahun_1', fields)
        self.assertIn('evaluasi_tahun_2', fields)
        self.assertIn('evaluasi_tahun_3', fields)
        self.assertIn('catatan_penilaian', fields)
        self.assertIn('nama_preseptor', fields)
        self.assertIn('nama_kepala_instalasi', fields)

    def test_render_pdf_includes_evaluasi_siklus_and_signatures(self):
        EntriLogbookKlinis.objects.create(
            employee=self.pegawai,
            unit_kerja=self.unit,
            tanggal=self.today - timedelta(days=30),
            tindakan='Pengkajian & Triase Anak',
            jumlah_mandiri=350,
            jumlah_kolaborasi=20,
            jumlah_supervisi=10,
            pasien_ref='RM-PED-01',
        )

        draf = generate_draft(self.pegawai, 'LOGBOOK_36BULAN', user=self.user)
        draf.isian = {
            'jenjang_klinis_diusulkan': 'Perawat Klinik II (PK II)',
            'evaluasi_tahun_1': 'Adaptasi dan keterampilan dasar baik.',
            'evaluasi_tahun_2': 'Kemandirian kegawatdaruratan sangat baik.',
            'evaluasi_tahun_3': 'Penguatan EBP dan bimbingan peer.',
            'catatan_penilaian': 'Rekomendasi naik jenjang ke PK II disetujui.',
            'nama_preseptor': 'Ns. M. Zainuddin, M.Kep., Sp.Mat',
            'nama_kepala_instalasi': 'Dr. Nurlaela, M.Kep.',
        }
        draf.save()

        pdf = render_pdf(draf)
        self.assertTrue(pdf.startswith(b'%PDF'))
        text = pdf_text(pdf)
        self.assertIn('Jenjang Klinis Diusulkan', text)
        self.assertIn('Perawat Klinik II (PK II)', text)
        self.assertIn('Pengkajian & Triase Anak', text)
        self.assertIn('Catatan Evaluasi Siklus Berkala (36 Bulan)', text)
        self.assertIn('Adaptasi dan keterampilan dasar baik.', text)
        self.assertIn('Kemandirian kegawatdaruratan sangat baik.', text)
        self.assertIn('Penguatan EBP dan bimbingan peer.', text)
        self.assertIn('Ns. M. Zainuddin, M.Kep., Sp.Mat', text)
        self.assertIn('Dr. Nurlaela, M.Kep.', text)

    def test_dokumen_kredensial_finalize_saves_post_data_and_sets_final(self):
        draf = generate_draft(self.pegawai, 'LOGBOOK_36BULAN', user=self.user)
        self.client.force_login(self.user)
        session, storage = self._storage()

        from unittest.mock import patch
        with patch('sdm.views.get_private_storage', return_value=storage), \
                patch('sdm.storage.get_private_storage', return_value=storage):
            resp = self.client.post(
                reverse('sdm:dokumen_kredensial_finalize', args=['LOGBOOK_36BULAN']),
                {
                    'jenjang_klinis_diusulkan': 'Perawat Klinik II (PK II)',
                    'evaluasi_tahun_1': 'Evaluasi T1 dari POST langsung.',
                    'nama_preseptor': 'Ns. Zainuddin',
                },
            )
            self.assertRedirects(
                resp,
                reverse('sdm:dokumen_kredensial_download', args=['LOGBOOK_36BULAN']),
            )

        draf.refresh_from_db()
        self.assertEqual(draf.status, 'FINAL')
        self.assertIsNotNone(draf.versi_dokumen_id)
        self.assertEqual(draf.isian.get('jenjang_klinis_diusulkan'), 'Perawat Klinik II (PK II)')
        self.assertEqual(draf.isian.get('evaluasi_tahun_1'), 'Evaluasi T1 dari POST langsung.')
        self.assertEqual(draf.isian.get('nama_preseptor'), 'Ns. Zainuddin')

    def test_pengajuan_saya_shows_terpenuhi_when_draft_final(self):
        draf = generate_draft(self.pegawai, 'LOGBOOK_36BULAN', user=self.user)
        session, storage = self._storage()
        from unittest.mock import patch
        with patch('sdm.storage.get_private_storage', return_value=storage):
            finalize(draf, user=self.user)

        self.client.force_login(self.user)
        resp = self.client.get(reverse('sdm:kredensial_pengajuan_sendiri'))
        self.assertEqual(resp.status_code, 200)

        # Cek context supporting_documents
        supporting = resp.context['supporting_documents']
        logbook_row = next(r for r in supporting if r['jenis'] == 'LOGBOOK_36BULAN')
        self.assertTrue(logbook_row['ada'])
        self.assertTrue(logbook_row['has_final'])

        content = resp.content.decode('utf-8')
        self.assertIn('Terpenuhi', content)
        self.assertIn(reverse('sdm:dokumen_kredensial_download', args=['LOGBOOK_36BULAN']), content)
