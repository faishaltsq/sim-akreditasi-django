"""Plan RKK-jenjang & orientasi staf: regresi Fase R dan O."""
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import (
    HcGrant,
    MasterJenjangProfesi,
    MasterProfesiPegawai,
    Pegawai,
    PenempatanPegawai,
)
from sdm.models.orientasi import (
    AsesmenOrientasi,
    PenugasanOrientasi,
    PenyelesaianOrientasi,
    ProgramOrientasi,
)
from sdm.services.orientasi import (
    auto_assign_orientation,
    record_assessment,
    seed_program_baku,
)


class JenjangBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.unit = UnitKerja.objects.create(name='U Jenjang', code='HC-JNK')
        cls.profesi = MasterProfesiPegawai.objects.create(
            code='P-JNK', nama='Perawat', keluarga='KEPERAWATAN_KEBIDANAN',
        )
        cls.j1 = MasterJenjangProfesi.objects.create(
            profesi=cls.profesi, kode='JNK1', nama='Perawat Muda', urutan=1,
        )
        cls.j3 = MasterJenjangProfesi.objects.create(
            profesi=cls.profesi, kode='JNK3', nama='Perawat Senior', urutan=3,
        )

    def _pegawai(self, nama, jenjang=None, akun=None):
        pegawai = Pegawai.objects.create(
            nama_lengkap=nama, kategori='PPA', profesi='Perawat',
            akun=akun, jenjang_master=jenjang,
        )
        PenempatanPegawai.objects.create(
            pegawai=pegawai, unit_kerja=self.unit,
            tanggal_mulai=timezone.localdate() - timezone.timedelta(days=30),
            alokasi_fte=Decimal('1.00'),
        )
        return pegawai


class PreseptorerTests(JenjangBase):
    def test_hanya_jenjang_cukup_yang_boleh_verifikasi(self):
        from sdm.services.preseptor import eligible_preceptors

        senior = self._pegawai('Ners Senior', jenjang=self.j3)
        junior = self._pegawai('Ners Junior', jenjang=self.j1)
        kandidat = set(eligible_preceptors(self.unit).values_list('pk', flat=True))
        self.assertIn(senior.pk, kandidat)
        self.assertNotIn(junior.pk, kandidat)

    def test_verifikasi_logbook_oleh_preseptor_jenjang(self):
        from sdm.models.logbook import EntriLogbookKlinis
        from sdm.services.logbook import verify_entry

        junior_user = get_user_model().objects.create_user('jnk-junior')
        senior_user = get_user_model().objects.create_user('jnk-senior')
        junior = self._pegawai('Ners Junior 2', jenjang=self.j1, akun=junior_user)
        senior = self._pegawai('Ners Senior 2', jenjang=self.j3, akun=senior_user)
        entry = EntriLogbookKlinis.objects.create(
            employee=junior, tanggal=timezone.localdate(), unit_kerja=self.unit,
            tindakan='Tindakan uji', jumlah_mandiri=1, created_by=senior_user,
        )
        verify_entry(user=senior_user, entry=entry, status='VERIFIED')
        entry.refresh_from_db()
        self.assertTrue(entry.sudah_diverifikasi)
        with self.assertRaises(Exception):
            verify_entry(user=junior_user, entry=entry, status='REJECTED')


class FilterKatalogJenjangTests(JenjangBase):
    def test_pegawai_pk1_tidak_melihat_tindakan_pk4(self):
        from sdm.forms.logbook import EntriLogbookForm

        j4 = MasterJenjangProfesi.objects.create(
            profesi=self.profesi, kode='JNK4', nama='Perawat Ahli', urutan=4,
        )
        item_j1 = self.profesi.jenjang.model.objects.none()  # placeholder
        from sdm.models import KatalogTindakan
        k1 = KatalogTindakan.objects.create(
            kode='JNK-A', nama='Tindakan Muda', jenjang=self.j1,
        )
        KatalogTindakan.objects.create(
            kode='JNK-B', nama='Tindakan Ahli', jenjang=j4,
        )
        user = get_user_model().objects.create_user('jnk-filter')
        pegawai = self._pegawai('Ners Filter', jenjang=self.j1, akun=user)
        form = EntriLogbookForm(employee=pegawai, user=user)
        qs = form.fields['katalog_tindakan'].queryset
        self.assertIn(k1.pk, qs.values_list('pk', flat=True))
        self.assertNotIn(
            KatalogTindakan.objects.get(kode='JNK-B').pk,
            qs.values_list('pk', flat=True),
        )


class OrientasiFlowTests(JenjangBase):
    def test_seed_baku_dan_auto_assign_idempoten(self):
        dibuat = seed_program_baku()
        self.assertGreaterEqual(dibuat, 5)
        self.assertEqual(seed_program_baku(), 0)
        pegawai = self._pegawai('Ners Orie')
        hasil = auto_assign_orientation(pegawai, actor=None, unit_kerja=self.unit)
        jenis = sorted(p.program.jenis for p in hasil)
        self.assertEqual(jenis, ['KHUSUS', 'UMUM'])
        ulang = auto_assign_orientation(pegawai, actor=None, unit_kerja=self.unit)
        self.assertEqual(len(ulang), 0)
        # Pipeline lengkap terbentuk: 5 penyelesaian per penugasan.
        self.assertTrue(all(
            a.completions.count() >= 2
            for a in PenugasanOrientasi.objects.filter(employee=pegawai)
        ))

    def test_asesmen_remedi_lalu_lulus_mengubah_status(self):
        seed_program_baku()
        pegawai = self._pegawai('Ners Ases')
        auto_assign_orientation(pegawai, actor=None, unit_kerja=self.unit)
        assignment = PenugasanOrientasi.objects.get(
            employee=pegawai, program__jenis='KHUSUS',
        )
        PenyelesaianOrientasi.objects.filter(
            assignment=assignment,
        ).update(selesai=True, selesai_at=timezone.now())

        remedi = record_assessment(assignment, nilai=Decimal('70'), penguji=None)
        self.assertFalse(remedi.lulus)
        self.assertEqual(remedi.percobaan, 1)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'BERJALAN')

        lulus = record_assessment(assignment, nilai=Decimal('80'), penguji=None)
        self.assertTrue(lulus.lulus)
        self.assertEqual(lulus.percobaan, 2)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, 'SELESAI')

    def test_sertifikat_hanya_untuk_selesai_dan_terarsip(self):
        seed_program_baku()
        pegawai = self._pegawai('Ners Sert')
        auto_assign_orientation(pegawai, actor=None, unit_kerja=self.unit)
        assignment = PenugasanOrientasi.objects.get(
            employee=pegawai, program__jenis='KHUSUS',
        )
        from sdm.services.orientasi import render_sertifikat_pdf
        with self.assertRaises(Exception):
            render_sertifikat_pdf(assignment)  # belum selesai

        PenyelesaianOrientasi.objects.filter(
            assignment=assignment,
        ).update(selesai=True, selesai_at=timezone.now())
        record_assessment(assignment, nilai=Decimal('90'), penguji=None)

        pdf = render_sertifikat_pdf(assignment)
        self.assertTrue(pdf.startswith(b'%PDF'))

        from sdm.models import DokumenPegawai, VersiDokumen
        storage = (
            __import__('sdm.tests.test_storage_backend', fromlist=[
                'FakeSession', 'FakeResponse',
            ])
        )
        from sdm.storage_backend import SupabasePrivateStorage

        session = storage.FakeSession(storage.FakeResponse(200, content=b''))
        st = SupabasePrivateStorage(
            base_url='https://project.supabase.co', api_key='k',
            bucket='b', session=session,
        )
        from sdm.services.orientasi import archive_certificate

        hc_user = get_user_model().objects.create_user('jnk-arch')
        from accounts.models import RolePermissionConfig

        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=hc_user, capability='can_manage_hc_documents',
            unit_kerja=self.unit,
        )
        with patch(
            'sdm.storage.get_private_storage', return_value=st,
        ):
            version = archive_certificate(assignment, actor=hc_user)
        self.assertTrue(
            DokumenPegawai.objects.filter(
                employee=pegawai, jenis_berkas='SERTIFIKAT_KOMPETENSI',
            ).exists()
        )
        self.assertTrue(
            VersiDokumen.objects.filter(pk=version.pk).exists()
        )

    def test_dashboard_filter_dan_rekap_pdf(self):
        seed_program_baku()
        pegawai = self._pegawai('Ners Dash')
        auto_assign_orientation(pegawai, actor=None, unit_kerja=self.unit)
        user = get_user_model().objects.create_user('jnk-dash')
        from accounts.models import RolePermissionConfig
        from sdm.models import HcGrant

        config = RolePermissionConfig.get_config_for_role('ADMIN_RS')
        config.can_view_hc = True
        config.save(update_fields=['can_view_hc', 'updated_at'])
        HcGrant.objects.create(
            user=user, capability='can_manage_hc_orientation',
            unit_kerja=self.unit,
        )
        self.client.force_login(user)
        resp = self.client.get(
            reverse('sdm:orientasi_list'), {'status': 'BERJALAN'},
        )
        self.assertEqual(resp.status_code, 200)
        resp = self.client.get(reverse('sdm:orientasi_rekap_pdf'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
