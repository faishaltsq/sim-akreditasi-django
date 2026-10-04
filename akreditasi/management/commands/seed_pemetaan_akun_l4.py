"""
Management command: seed_pemetaan_akun_l4
Menerapkan Fase 3 (Pemetaan standar_terkait ke unit kerja)
dan Fase 5 (Unit baru L4 + 8 Akun Demo Unit-Scoped).
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from akreditasi.models import UnitKerja
from accounts.models import UserProfile


# Pemetaan standar_terkait per unit (Fase 3)
STANDAR_MAPPING = {
    'FARM': {
        'TKRS': ['TKRS 9', 'TKRS 10', 'TKRS 11'],
        'PKPO': ['PKPO 1', 'PKPO 2', 'PKPO 3', 'PKPO 3.1', 'PKPO 4', 'PKPO 5', 'PKPO 6', 'PKPO 7', 'PKPO 8', 'PKPO 9'],
        'PPI': ['PPI 5', 'PPI 7', 'PPI 7.1', 'PPI 8'],
        'MFK': ['MFK 3', 'MFK 4', 'MFK 7', 'MFK 9'],
        'KPS': ['KPS 1', 'KPS 4', 'KPS 12'],
    },
    'DEPO-RAJAL': {
        'PKPO': ['PKPO 3', 'PKPO 3.1', 'PKPO 4', 'PKPO 5', 'PKPO 6', 'PKPO 8'],
        'PPI': ['PPI 2', 'PPI 8'],
        'MFK': ['MFK 3', 'MFK 4'],
    },
    'LAB-BDRS': {
        'TKRS': ['TKRS 9', 'TKRS 11'],
        'PP': ['PP 5', 'PP 6'],
        'PPI': ['PPI 2', 'PPI 7.1'],
        'MFK': ['MFK 3', 'MFK 6'],
        'KPS': ['KPS 1', 'KPS 12'],
    },
    'PATKLIN': {
        'PP': ['PP 5', 'PP 6'],
        'PPI': ['PPI 2', 'PPI 7.1'],
        'MFK': ['MFK 3', 'MFK 6'],
    },
    'RAD-IMAGING': {
        'TKRS': ['TKRS 9', 'TKRS 11'],
        'PP': ['PP 7'],
        'MFK': ['MFK 2', 'MFK 6'],
        'KPS': ['KPS 1', 'KPS 12'],
    },
    'IRJ': {
        'ARK': ['ARK 1', 'ARK 3', 'ARK 5'],
        'HPK': ['HPK 1', 'HPK 3', 'HPK 4'],
        'PP': ['PP 1', 'PP 2', 'PP 8'],
        'KE': ['KE 1', 'KE 2', 'KE 3'],
    },
    'IGD': {
        'ARK': ['ARK 1', 'ARK 2', 'ARK 4', 'ARK 6'],
        'PAP': ['PAP 1', 'PAP 3', 'PAP 8'],
        'SKP': ['SKP 1', 'SKP 2', 'SKP 6'],
        'MFK': ['MFK 4', 'MFK 5'],
        'PPI': ['PPI 2', 'PPI 7'],
    },
    'IBS': {
        'PAB': ['PAB 1', 'PAB 2', 'PAB 3', 'PAB 4', 'PAB 5', 'PAB 6', 'PAB 7', 'PAB 8', 'PAB 9', 'PAB 10'],
        'PAP': ['PAP 1', 'PAP 2'],
        'SKP': ['SKP 1', 'SKP 4', 'SKP 5'],
        'PPI': ['PPI 2', 'PPI 5', 'PPI 7'],
        'MFK': ['MFK 4', 'MFK 6', 'MFK 7'],
    },
    'RUANG-OK': {
        'PAB': ['PAB 3', 'PAB 5', 'PAB 7', 'PAB 8', 'PAB 9', 'PAB 10'],
        'SKP': ['SKP 4', 'SKP 5'],
        'PPI': ['PPI 2', 'PPI 5', 'PPI 7'],
        'MFK': ['MFK 4', 'MFK 6'],
    },
    'INTENSIF': {
        'PAP': ['PAP 1', 'PAP 3', 'PAP 4', 'PAP 5', 'PAP 8'],
        'SKP': ['SKP 1', 'SKP 2', 'SKP 3', 'SKP 6'],
        'PPI': ['PPI 2', 'PPI 7'],
        'MFK': ['MFK 4', 'MFK 6', 'MFK 7'],
    },
    'BANGSAL-DEWASA': {
        'PAP': ['PAP 1', 'PAP 2', 'PAP 8', 'PAP 9'],
        'HPK': ['HPK 1', 'HPK 2', 'HPK 3', 'HPK 4'],
        'SKP': ['SKP 1', 'SKP 2', 'SKP 6'],
        'PPI': ['PPI 2', 'PPI 4', 'PPI 7'],
    },
    'RUANG-PRIA': {
        'PAP': ['PAP 1', 'PAP 2', 'PAP 8'],
        'HPK': ['HPK 1', 'HPK 2'],
        'SKP': ['SKP 1', 'SKP 6'],
        'PPI': ['PPI 2', 'PPI 4'],
    },
    'REKAM-MEDIS': {
        'MRMIK': ['MRMIK 1', 'MRMIK 2', 'MRMIK 3', 'MRMIK 4', 'MRMIK 5', 'MRMIK 6', 'MRMIK 7'],
        'HPK': ['HPK 1', 'HPK 3'],
        'ARK': ['ARK 2', 'ARK 5'],
    },
    'ADMISI': {
        'ARK': ['ARK 1', 'ARK 2'],
        'HPK': ['HPK 1', 'HPK 4'],
        'MRMIK': ['MRMIK 2', 'MRMIK 3'],
    },
    'CSSD': {
        'PPI': ['PPI 2', 'PPI 5'],
        'MFK': ['MFK 4', 'MFK 6', 'MFK 9'],
    },
    'SUB-IPSRS': {
        'MFK': ['MFK 1', 'MFK 2', 'MFK 4', 'MFK 6', 'MFK 7', 'MFK 8', 'MFK 10'],
        'PPI': ['PPI 2'],
    },
    'SUB-KESLING': {
        'MFK': ['MFK 2', 'MFK 3', 'MFK 4'],
        'PPI': ['PPI 2', 'PPI 4', 'PPI 6'],
    },
    'KMKP': {
        'PMKP': ['PMKP 1', 'PMKP 2', 'PMKP 3', 'PMKP 4', 'PMKP 5', 'PMKP 6', 'PMKP 7', 'PMKP 8', 'PMKP 9', 'PMKP 10'],
        'SKP': ['SKP 1', 'SKP 2', 'SKP 3', 'SKP 4', 'SKP 5', 'SKP 6'],
        'TKRS': ['TKRS 7', 'TKRS 10'],
    },
    'BAG-SDM': {
        'KPS': ['KPS 1', 'KPS 2', 'KPS 3', 'KPS 4', 'KPS 5', 'KPS 6', 'KPS 7', 'KPS 8', 'KPS 9', 'KPS 10', 'KPS 11', 'KPS 12'],
        'TKRS': ['TKRS 4', 'TKRS 8', 'TKRS 9'],
    },
    'BAG-DIKLIT': {
        'IPKP': ['IPKP 1', 'IPKP 2', 'IPKP 3'],
        'KPS': ['KPS 5', 'KPS 6'],
    },
    'TIM-PONEK': {
        'PROGNAS': ['PROGNAS 1', 'PROGNAS 2', 'PROGNAS 3', 'PROGNAS 4', 'PROGNAS 5'],
    },
    'HUMAS-CS': {
        'HPK': ['HPK 1', 'HPK 4'],
        'KE': ['KE 1', 'KE 2', 'KE 3'],
        'ARK': ['ARK 2'],
    },
}

# Unit-unit baru yang perlu di-ensure (Fase 5)
NEW_UNITS = [
    {
        'code': 'PATKLIN',
        'name': 'Unit Patologi Klinik & Mikrobiologi',
        'parent_code': 'LAB-BDRS',
        'level': 4,
        'tipe_unit': 'RUANGAN',
        'order': 1,
    },
    {
        'code': 'RUANG-OK',
        'name': 'Unit Kamar Operasi (OK Sentral)',
        'parent_code': 'IBS',
        'level': 3,
        'tipe_unit': 'RUANGAN',
        'order': 1,
    },
    {
        'code': 'ADMISI',
        'name': 'Unit Pendaftaran & Admisi Pasien',
        'parent_code': 'REKAM-MEDIS',
        'level': 4,
        'tipe_unit': 'RUANGAN',
        'order': 1,
    },
    {
        'code': 'TIM-PONEK',
        'name': 'Tim PONEK 24 Jam & Program Nasional',
        'parent_code': 'KMKP',
        'level': 3,
        'tipe_unit': 'KOMITE',
        'order': 9,
    },
    {
        'code': 'HUMAS-CS',
        'name': 'Unit Humas, PKRS & Customer Service',
        'parent_code': 'TU-SEKRETARIAT',
        'level': 3,
        'tipe_unit': 'BAGIAN',
        'order': 3,
    },
]

# 8 Akun demo unit-scoped (Fase 5)
DEMO_USERS = [
    {
        'username': 'ka.depo.rajal',
        'name': 'Ka. Depo Farmasi Rawat Jalan',
        'role': 'KEPALA_UNIT',
        'unit_code': 'DEPO-RAJAL',
    },
    {
        'username': 'ka.laboratorium',
        'name': 'Ka. Instalasi Laboratorium',
        'role': 'KEPALA_UNIT',
        'unit_code': 'LAB-BDRS',
    },
    {
        'username': 'ka.kamar.operasi',
        'name': 'Ka. Unit Kamar Operasi (OK)',
        'role': 'KEPALA_UNIT',
        'unit_code': 'RUANG-OK',
    },
    {
        'username': 'ka.ranap',
        'name': 'Ka. Bangsal Rawat Inap Dewasa',
        'role': 'KEPALA_UNIT',
        'unit_code': 'BANGSAL-DEWASA',
    },
    {
        'username': 'ka.rekam.medis',
        'name': 'Ka. Instalasi Rekam Medis',
        'role': 'KEPALA_UNIT',
        'unit_code': 'REKAM-MEDIS',
    },
    {
        'username': 'ka.cssd',
        'name': 'Ka. Instalasi Pusat Sterilisasi (CSSD)',
        'role': 'KEPALA_UNIT',
        'unit_code': 'CSSD',
    },
    {
        'username': 'koordinator.mutu',
        'name': 'Koordinator Komite Mutu & Keselamatan Pasien',
        'role': 'KOORDINATOR_POKJA',
        'unit_code': 'KMKP',
    },
    {
        'username': 'staf.sdm',
        'name': 'Staf Bagian SDM & Diklat',
        'role': 'STAF_NAKES',
        'unit_code': 'BAG-SDM',
    },
]


class Command(BaseCommand):
    help = 'Terapkan pemetaan standar_terkait (Fase 3) dan buat unit baru + akun demo L4 (Fase 5)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Memulai Fase 3 & Fase 5..."))
        User = get_user_model()

        # 1. Buat unit baru (Fase 5)
        for udata in NEW_UNITS:
            parent = UnitKerja.objects.filter(code=udata['parent_code']).first()
            unit, created = UnitKerja.objects.get_or_create(
                code=udata['code'],
                defaults={
                    'name': udata['name'],
                    'parent': parent,
                    'level': udata['level'],
                    'tipe_unit': udata['tipe_unit'],
                    'order': udata['order'],
                    'is_active': True,
                }
            )
            if created:
                self.stdout.write(f"  + Unit dibuat: [{unit.code}] {unit.name} (L{unit.level})")
            else:
                unit.name = udata['name']
                unit.parent = parent
                unit.level = udata['level']
                unit.save()
                self.stdout.write(f"  * Unit diperbarui: [{unit.code}] {unit.name} (L{unit.level})")

        # 2. Terapkan pemetaan standar_terkait (Fase 3)
        updated_mappings = 0
        for code, mapping in STANDAR_MAPPING.items():
            unit = UnitKerja.objects.filter(code=code).first()
            if unit:
                unit.standar_terkait = mapping
                unit.save()
                updated_mappings += 1
                self.stdout.write(f"  ✓ Standar mapped: [{unit.code}] -> {list(mapping.keys())}")
            else:
                self.stdout.write(self.style.WARNING(f"  ! Unit [{code}] tidak ditemukan untuk pemetaan"))

        # 3. Buat 8 Akun demo (Fase 5)
        users_created = 0
        users_updated = 0
        for udata in DEMO_USERS:
            unit = UnitKerja.objects.filter(code=udata['unit_code']).first()
            user, created = User.objects.get_or_create(
                username=udata['username'],
                defaults={
                    'first_name': udata['name'][:30],
                    'is_staff': False,
                    'is_superuser': False,
                    'password': make_password('Unit@1234'),
                    'last_login': timezone.now(),
                }
            )
            if created:
                users_created += 1
            else:
                user.first_name = udata['name'][:30]
                user.set_password('Unit@1234')
                user.save()
                users_updated += 1

            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'role': udata['role'],
                    'unit_kerja': unit,
                }
            )
            profile.role = udata['role']
            profile.unit_kerja = unit
            profile.save()
            self.stdout.write(f"  👤 Akun: {user.username} | Role: {profile.role} | Unit: {unit.code if unit else 'None'}")

        self.stdout.write(self.style.SUCCESS(
            f"\nSelesai!\n"
            f"- Unit mapped: {updated_mappings} unit\n"
            f"- Akun demo: {users_created} dibuat baru, {users_updated} diperbarui (Total 8 akun siap pakai)"
        ))
