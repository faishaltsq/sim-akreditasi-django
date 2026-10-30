"""PMK No. 13 Tahun 2025: Buku Kinerja Elektronik (Logbook 5 Tahunan).

Covers the 5-year credentialing cycle introduced by Peraturan Menteri
Kesehatan Nomor 13 Tahun 2025: registry wiring, 5-year trailing window
aggregation, the 3-domain official PDF layout, and the grouped draft editor.
"""
import hashlib
from datetime import timedelta
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import (
    DokumenPegawai,
    DrafDokumenKredensial,
    EntriLogbookKlinis,
    HcGrant,
    Pegawai,
    PenempatanPegawai,
    VerifikasiLogbook,
    VersiDokumen,
)
from sdm.models.kredensial import DokumenSyaratKredensial
from sdm.services.dokumen_kredensial import (
    REGISTRY,
    generate_draft,
    render_pdf,
)
from sdm.services.logbook import logbook_recap_5tahun
from sdm.storage_backend import SupabasePrivateStorage
from sdm.tests.test_storage_backend import FakeResponse, FakeSession


def pdf_text(pdf):
    """Readable text of a generated PDF. Test-only: pypdf is transitive."""
    from pypdf import PdfReader

    return '\n'.join(
        page.extract_text() or '' for page in PdfReader(BytesIO(pdf)).pages
    )


class Logbook5TahunBase(TestCase):
    def setUp(self):
        self.today = timezone.localdate()
        self.unit = UnitKerja.objects.create(name='Ruang Anak', code='HC-ANK5')
        self.manager = self._hc_user('pmk13-manager')
        self.employee = Pegawai.objects.create(
            nama_lengkap='Ners Lima Tahun', kategori='PPA', profesi='Perawat',
            nomor_pegawai='PGW-5THN', jabatan='Perawat Klinik II',
        )
        PenempatanPegawai.objects.create(
            pegawai=self.employee, unit_kerja=self.unit,
            tanggal_mulai=self.today - timedelta(days=10),
            alokasi_fte=Decimal('1.00'),
        )
        self.session = FakeSession(FakeResponse(200, {}))
        self.storage = SupabasePrivateStorage(
            base_url='https://project.supabase.co',
            api_key='service-key',
            bucket='hc-private',
            session=self.session,
        )

    def _hc_user(self, username):
        user = get_user_model().objects.create_user(username=username)
        UserProfile.objects.create(user=user, role='ADMIN_RS', unit_kerja=self.unit)
        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.can_review_hc_credentials = True
        config.can_manage_hc_documents = True
        config.save(update_fields=[
            'can_view_hc', 'can_review_hc_credentials',
            'can_manage_hc_documents', 'updated_at',
        ])
        # HcGrant adalah sumber otoritatif require_hc_capability: satu grant
        # tanpa batas unit (unit_kerja=None) memberi scope global.
        for capability in (
            'can_view_hc', 'can_review_hc_credentials', 'can_manage_hc_documents',
        ):
            HcGrant.objects.create(
                user=user, capability=capability, unit_kerja=None,
                valid_from=self.today - timedelta(days=1),
            )
        return user

    def _entry(self, *, days_ago, mandiri=0, supervisi=0, kolaborasi=0, label='Tindakan 5 Tahun'):
        return EntriLogbookKlinis.objects.create(
            employee=self.employee,
            tanggal=self.today - timedelta(days=days_ago),
            unit_kerja=self.unit, tindakan=label,
            jumlah_mandiri=mandiri, jumlah_supervisi=supervisi,
            jumlah_kolaborasi=kolaborasi,
        )


class Logbook5TahunRegistryTests(Logbook5TahunBase):
    def test_logbook_5tahun_in_choices_and_registry(self):
        choice_keys = [key for key, _label in DokumenSyaratKredensial.JENIS_CHOICES]
        self.assertIn('LOGBOOK_5TAHUN', choice_keys)
        self.assertIn('LOGBOOK_5TAHUN', REGISTRY)
        spec = REGISTRY['LOGBOOK_5TAHUN']
        self.assertEqual(spec['sertifikat_jenis'], 'LOGBOOK')
        manual_keys = [key for key, _hint in spec['manual_fields']]
        # Ranah 2: kecukupan SKP, 4 kategori pengembangan profesi berkelanjutan.
        self.assertIn('skp_pelayanan', manual_keys)
        self.assertIn('skp_pelatihan', manual_keys)
        self.assertIn('skp_seminar', manual_keys)
        self.assertIn('skp_publikasi', manual_keys)
        self.assertIn('target_skp_dirjen', manual_keys)
        self.assertIn('total_skp_diperoleh', manual_keys)
        # Ranah 3: etik, disiplin, rekam jejak bebas perundungan per tahun.
        self.assertIn('etik_perundungan_t1', manual_keys)
        self.assertIn('etik_perundungan_t5', manual_keys)
        # Pasal 180: checklist penilaian & rekomendasi Tim Ad Hoc.
        self.assertIn('checklist_kualifikasi_str_sip', manual_keys)
        self.assertIn('checklist_target_volume_pelayanan', manual_keys)
        self.assertIn('checklist_kecukupan_skp', manual_keys)
        self.assertIn('checklist_kesehatan_fisik_mental', manual_keys)
        self.assertIn('checklist_etik_disiplin_perundungan', manual_keys)
        self.assertIn('rekomendasi_tim_adhoc', manual_keys)
        self.assertIn('nama_ketua_tim_adhoc', manual_keys)
        self.assertIn('nip_ketua_tim_adhoc', manual_keys)
        self.assertIn('nama_pimpinan_fasyankes', manual_keys)

    def test_registry_still_covers_the_seven_legacy_types(self):
        for jenis in (
            'CV', 'LOGBOOK_36BULAN', 'PENGANTAR_KSM', 'KEANGGOTAAN',
            'MALPRACTICE_RECORD', 'BEBAS_SANKSI', 'SEHAT_PSIKOLOGIS',
        ):
            self.assertIn(jenis, REGISTRY)


class Logbook5TahunRecapTests(Logbook5TahunBase):
    def test_recap_buckets_entries_into_five_annual_windows(self):
        # 5 years = 1825 days trailing. T1 is the oldest window.
        self._entry(days_ago=1700, mandiri=10, label='Tindakan T1')
        self._entry(days_ago=1300, mandiri=20, label='Tindakan T2')
        self._entry(days_ago=900, mandiri=30, label='Tindakan T3')
        self._entry(days_ago=500, mandiri=40, label='Tindakan T4')
        self._entry(days_ago=100, mandiri=50, label='Tindakan T5')

        recap = logbook_recap_5tahun(self.employee)

        self.assertEqual(recap['tahun_labels'], ['T1', 'T2', 'T3', 'T4', 'T5'])
        self.assertEqual(recap['total_5tahun'], 150)
        self.assertEqual(recap['mandiri'], 150)
        self.assertEqual(recap['supervisi'], 0)
        self.assertEqual(recap['kolaborasi'], 0)
        by_label = {row['label']: row for row in recap['per_tindakan']}
        self.assertEqual(by_label['Tindakan T1']['tahunan'], [10, 0, 0, 0, 0])
        self.assertEqual(by_label['Tindakan T3']['tahunan'], [0, 0, 30, 0, 0])
        self.assertEqual(by_label['Tindakan T5']['tahunan'], [0, 0, 0, 0, 50])
        self.assertEqual(recap['tahunan'], [10, 20, 30, 40, 50])

    def test_recap_excludes_entries_older_than_five_years(self):
        self._entry(days_ago=1900, mandiri=999, label='Tindakan Basi')
        self._entry(days_ago=100, mandiri=5, label='Tindakan Baru')

        recap = logbook_recap_5tahun(self.employee)

        self.assertEqual(recap['total_5tahun'], 5)
        labels = [row['label'] for row in recap['per_tindakan']]
        self.assertNotIn('Tindakan Basi', labels)

    def test_recap_splits_supervision_modes_per_action(self):
        self._entry(days_ago=100, mandiri=7, supervisi=3, kolaborasi=2,
                    label='Tindakan Campuran')
        recap = logbook_recap_5tahun(self.employee)
        row = recap['per_tindakan'][0]
        self.assertEqual(row['mandiri'], 7)
        self.assertEqual(row['supervisi'], 3)
        self.assertEqual(row['kolaborasi'], 2)
        self.assertEqual(row['total'], 12)
        self.assertEqual(row['tahunan'], [0, 0, 0, 0, 12])

    def test_recap_reports_verified_count(self):
        entry = self._entry(days_ago=100, mandiri=4, label='Tindakan Terverifikasi')
        VerifikasiLogbook.objects.create(
            entri=entry, verifikator=self.manager,
            status=VerifikasiLogbook.VERIFIED, catatan='ok',
            verified_at=timezone.now(),
        )
        recap = logbook_recap_5tahun(self.employee)
        self.assertEqual(recap['terverifikasi'], 4)
        self.assertEqual(recap['total_5tahun'], 4)


class Logbook5TahunPdfRenderTests(Logbook5TahunBase):
    def _filled_draft(self):
        self._entry(days_ago=1700, mandiri=40, label='Triase Anak')
        self._entry(days_ago=100, mandiri=60, supervisi=10, label='Pemberian Terapi')
        draf = generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        draf.isian = {
            'periode_siklus': '2021 s.d. 2026',
            'jenjang_klinis_usulan': 'Perawat Klinik III (PK III)',
            'skp_pelayanan': 'Target 25 SKP (Capaian: 28 SKP)',
            'skp_pelatihan': 'Target 15 SKP (Capaian: 16 SKP)',
            'skp_seminar': 'Target 10 SKP (Capaian: 12 SKP)',
            'skp_publikasi': 'Target 5 SKP (Capaian: 6 SKP)',
            'target_skp_dirjen': '50 SKP',
            'total_skp_diperoleh': '62 SKP',
            'etik_perundungan_t1': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t2': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t3': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t4': 'Baik | Bebas Kasus Perundungan | Layak Lanjut',
            'etik_perundungan_t5': 'Baik | Bebas Kasus Perundungan | Siap Rekredensial',
            'checklist_kualifikasi_str_sip': 'MS',
            'checklist_target_volume_pelayanan': 'MS',
            'checklist_kecukupan_skp': 'MS',
            'checklist_kesehatan_fisik_mental': 'MS',
            'checklist_etik_disiplin_perundungan': 'MS',
            'rekomendasi_tim_adhoc': 'DIKABULKAN SEPENUHNYA',
            'catatan_rekomendasi_adhoc': 'Seluruh syarat terpenuhi tanpa pembatasan.',
            'nama_ketua_tim_adhoc': 'Dr. H. Subagyo, Sp.A',
            'nip_ketua_tim_adhoc': '197505122003121002',
            'nama_pimpinan_fasyankes': 'Dr. dr. H. Fachruddin, Sp.B, MARS',
        }
        draf.save(update_fields=['isian', 'updated_at'])
        return draf

    def test_render_pdf_logbook_5tahun_contains_pmk13_sections(self):
        draf = self._filled_draft()
        pdf = render_pdf(draf)
        self.assertTrue(pdf.startswith(b'%PDF'))
        text = pdf_text(pdf)
        upper = text.upper()
        self.assertIn('BUKU KINERJA ELEKTRONIK', upper)
        self.assertIn('PERATURAN MENTERI KESEHATAN NOMOR 13 TAHUN 2025', upper)
        self.assertIn('RANAH 1', upper)
        self.assertIn('RANAH 2', upper)
        self.assertIn('RANAH 3', upper)
        self.assertIn('PENGEMBANGAN PROFESI BERKELANJUTAN', upper)
        self.assertIn('BEBAS PERUNDUNGAN', upper)
        self.assertIn('PASAL 180', upper)
        self.assertIn('DIKABULKAN SEPENUHNYA', text)
        self.assertIn('TIM AD HOC', upper)
        self.assertIn('SATUSEHAT', upper)
        self.assertIn('2021 s.d. 2026', text)

    def test_render_pdf_renders_five_year_action_matrix(self):
        draf = self._filled_draft()
        text = pdf_text(render_pdf(draf))
        self.assertIn('T1', text)
        self.assertIn('T5', text)
        self.assertIn('Triase Anak', text)
        self.assertIn('Pemberian Terapi', text)
        # 40 mandiri in T1 + 70 (60 mandiri + 10 supervisi) in T5 = 110.
        self.assertIn('110', text)

    def test_render_pdf_marks_unfilled_checklist_as_belum_dinilai(self):
        draf = generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        text = pdf_text(render_pdf(draf))
        upper = text.upper()
        self.assertIn('BELUM DINILAI', upper)
        self.assertNotIn('DIKABULKAN SEPENUHNYA', upper)

    def test_finalize_stores_pdf_under_logbook_kind(self):
        from sdm.services.dokumen_kredensial import finalize

        draf = self._filled_draft()
        with patch('sdm.storage.get_private_storage', return_value=self.storage):
            version = finalize(draf, user=self.manager)

        draf.refresh_from_db()
        self.assertEqual(draf.status, 'FINAL')
        self.assertEqual(version.document.jenis_berkas, 'LOGBOOK')
        self.assertEqual(version.content_type, 'application/pdf')
        self.assertEqual(VersiDokumen.objects.count(), 1)
        self.assertEqual(
            DokumenPegawai.objects.filter(
                employee=self.employee, jenis_berkas='LOGBOOK',
            ).count(),
            1,
        )
        # PDF tidak deterministik (timestamp + ID objek ReportLab), jadi hash
        # tidak bisa dibandingkan byte-per-byte. Verifikasi isi: berkas yang
        # diunggah ke storage adalah PDF valid dan memuat seluruh bagian
        # PMK 13/2025. FakeSession merekam setiap request, termasuk body upload.
        uploaded = [
            call for call in self.session.calls
            if call[0].upper() == 'POST' and 'object' in call[1]
        ][-1]
        body = uploaded[2].get('data') or uploaded[2].get('content')
        self.assertTrue(body.startswith(b'%PDF'))
        self.assertEqual(hashlib.sha256(body).hexdigest(), version.sha256)
        text = pdf_text(body).upper()
        for marker in (
            'BUKU KINERJA ELEKTRONIK',
            'PERATURAN MENTERI KESEHATAN NOMOR 13 TAHUN 2025',
            'RANAH 1', 'RANAH 2', 'RANAH 3',
            'PASAL 180', 'TIM AD HOC', 'SATUSEHAT',
        ):
            self.assertIn(marker, text)


class Logbook5TahunUiTests(Logbook5TahunBase):
    def setUp(self):
        super().setUp()
        self.employee.akun = self.manager
        self.employee.save(update_fields=['akun'])
        self.client.force_login(self.manager)

    def test_dokumen_edit_renders_grouped_pmk13_sections(self):
        generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        resp = self.client.get(
            reverse('sdm:dokumen_kredensial_edit', args=['LOGBOOK_5TAHUN'])
        )
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Buku Kinerja Elektronik', content)
        self.assertIn('Pengembangan Profesi Berkelanjutan', content)
        self.assertIn('Bebas Perundungan', content)
        self.assertIn('Tim Ad Hoc', content)
        self.assertIn('Pasal 180', content)

    def test_manual_fields_carry_group_metadata(self):
        generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        resp = self.client.get(
            reverse('sdm:dokumen_kredensial_edit', args=['LOGBOOK_5TAHUN'])
        )
        groups = [group['kode'] for group in resp.context['field_groups']]
        self.assertEqual(
            groups,
            ['periode', 'skp', 'etik', 'adhoc', 'tanda_tangan'],
        )

    def test_post_persists_all_three_domains(self):
        generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        resp = self.client.post(
            reverse('sdm:dokumen_kredensial_edit', args=['LOGBOOK_5TAHUN']),
            {
                'periode_siklus': '2021 s.d. 2026',
                'skp_pelayanan': 'Target 25 SKP',
                'etik_perundungan_t1': 'Bebas perundungan',
                'rekomendasi_tim_adhoc': 'DIKABULKAN SEPENUHNYA',
            },
        )
        self.assertEqual(resp.status_code, 302)
        draf = DrafDokumenKredensial.objects.get(
            pegawai=self.employee, jenis='LOGBOOK_5TAHUN',
        )
        self.assertEqual(draf.isian['periode_siklus'], '2021 s.d. 2026')
        self.assertEqual(draf.isian['skp_pelayanan'], 'Target 25 SKP')
        self.assertEqual(draf.isian['etik_perundungan_t1'], 'Bebas perundungan')
        self.assertEqual(
            draf.isian['rekomendasi_tim_adhoc'], 'DIKABULKAN SEPENUHNYA',
        )

    def test_post_keeps_fields_absent_from_the_payload(self):
        """Field yang tidak dikirim form tidak boleh terhapus diam-diam."""
        generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        url = reverse('sdm:dokumen_kredensial_edit', args=['LOGBOOK_5TAHUN'])
        self.client.post(url, {
            'nama_ketua_tim_adhoc': 'Dr. Subagyo',
            'nip_ketua_tim_adhoc': '197505122003121002',
        })
        # POST kedua hanya membawa sebagian field, seperti form yang berubah.
        self.client.post(url, {'periode_siklus': '2021 s.d. 2026'})
        draf = DrafDokumenKredensial.objects.get(
            pegawai=self.employee, jenis='LOGBOOK_5TAHUN',
        )
        self.assertEqual(draf.isian['periode_siklus'], '2021 s.d. 2026')
        self.assertEqual(draf.isian['nama_ketua_tim_adhoc'], 'Dr. Subagyo')
        self.assertEqual(draf.isian['nip_ketua_tim_adhoc'], '197505122003121002')

    def test_post_clears_field_submitted_as_empty(self):
        """Mengosongkan textarea di form tetap menghapus nilainya."""
        generate_draft(self.employee, 'LOGBOOK_5TAHUN', user=self.manager)
        url = reverse('sdm:dokumen_kredensial_edit', args=['LOGBOOK_5TAHUN'])
        self.client.post(url, {'catatan_rekomendasi_adhoc': 'Catatan awal'})
        self.client.post(url, {'catatan_rekomendasi_adhoc': ''})
        draf = DrafDokumenKredensial.objects.get(
            pegawai=self.employee, jenis='LOGBOOK_5TAHUN',
        )
        self.assertNotIn('catatan_rekomendasi_adhoc', draf.isian)
