"""RBAC tulis modul Risiko — mengunci temuan QA 2026-10-27.

Sebelum perbaikan, kelima view tulis risiko hanya memakai ``@login_required``
sehingga ASESOR (read-only) dapat mengedit dan menghapus register risiko unit
mana pun. Yang diuji di sini hanya perilaku yang bisa rusak tanpa disadari:
gerbang izin per peran dan lingkup unit.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase

from accounts.models import UserProfile
from akreditasi.models import UnitKerja
from akreditasi.risiko_models import RisikoUnit
from akreditasi.tests_utils import reset_rate_limit

User = get_user_model()


class RisikoTulisRBACTest(TestCase):
    def setUp(self):
        reset_rate_limit()
        self.unit_a = UnitKerja.objects.create(code='QA-RBAC-A', name='Unit A', level=2)
        # Unit B sengaja di luar lingkup unit_a (bukan anak, bukan leluhur).
        UnitKerja.objects.create(code='QA-RBAC-X', name='Instalasi X', level=1)
        self.unit_b = UnitKerja.objects.create(
            code='QA-RBAC-B', name='Unit B', level=3,
            parent=UnitKerja.objects.get(code='QA-RBAC-X'),
        )
        self.risiko_a = self._risk(self.unit_a, 'Risiko unit A')
        self.risiko_b = self._risk(self.unit_b, 'Risiko unit B')

    def _risk(self, unit, jenis):
        return RisikoUnit.objects.create(
            unit=unit, tahun=2026, periode='TAHUNAN',
            kategori_risiko='KLINIS', jenis_risiko=jenis,
            deskripsi_risiko='Uji RBAC', dampak=3, probabilitas=3,
            strategi_mitigasi='KURANGI', rencana_aksi='Uji',
            pj_mitigasi='QA',
        )

    def _user(self, username, role, unit=None):
        user = User.objects.create_user(username, f'{username}@rs.id', 'pass123')
        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = role
        profile.unit_kerja = unit
        profile.save()
        return user

    def _client(self, user):
        client = Client()
        client.force_login(user)
        return client

    def test_asesor_tidak_boleh_mengubah_risiko(self):
        client = self._client(self._user('qa.asesor', 'ASESOR'))

        self.assertEqual(client.get(f'/risiko/{self.risiko_a.pk}/edit/').status_code, 302)
        self.assertEqual(client.get(f'/risiko/{self.risiko_a.pk}/hapus/').status_code, 302)
        self.assertEqual(client.get('/risiko/baru/').status_code, 302)

        client.post(f'/risiko/{self.risiko_a.pk}/hapus/')
        self.assertTrue(RisikoUnit.objects.filter(pk=self.risiko_a.pk).exists())

    def test_admin_rs_boleh_mengubah_risiko(self):
        client = self._client(self._user('qa.admin', 'ADMIN_RS'))

        self.assertEqual(client.get(f'/risiko/{self.risiko_a.pk}/edit/').status_code, 200)
        self.assertEqual(client.get(f'/risiko/{self.risiko_a.pk}/hapus/').status_code, 200)

    def test_kepala_unit_terbatas_pada_lingkup_unitnya(self):
        client = self._client(self._user('qa.kaunit', 'KEPALA_UNIT', self.unit_a))

        self.assertEqual(client.get(f'/risiko/{self.risiko_a.pk}/edit/').status_code, 200)
        # Risiko unit lain di luar lingkup ditolak walau punya izin kelola.
        self.assertEqual(client.get(f'/risiko/{self.risiko_b.pk}/edit/').status_code, 302)
        self.assertEqual(client.get(f'/risiko/{self.risiko_b.pk}/hapus/').status_code, 302)

        client.post(f'/risiko/{self.risiko_b.pk}/hapus/')
        self.assertTrue(RisikoUnit.objects.filter(pk=self.risiko_b.pk).exists())

    def test_superuser_tanpa_profil_tetap_boleh(self):
        admin = User.objects.create_superuser('qa.super', 'qa.super@rs.id', 'pass123')
        client = self._client(admin)

        self.assertEqual(client.get(f'/risiko/{self.risiko_a.pk}/edit/').status_code, 200)
