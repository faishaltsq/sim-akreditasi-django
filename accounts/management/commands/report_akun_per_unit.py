"""
Regenerate laporan lengkap akun per unit langsung dari database.

Menulis docs/akun_per_unit_report.txt yang memuat:
  - ringkasan cakupan (unit x tingkatan)
  - matriks izin per tingkatan
  - daftar seluruh akun
  - daftar akun lama yang passwordnya TIDAK ikut diubah

Jalankan: python manage.py report_akun_per_unit
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Count

from accounts.models import HC_PERMISSION_LABELS, RolePermissionConfig, UserProfile
from akreditasi.models import UnitKerja
from sdm.models import HcGrant, Pegawai

User = get_user_model()

ROLES = [
    'SUPER_ADMIN', 'ADMIN_RS', 'KOORDINATOR_POKJA',
    'KEPALA_UNIT', 'STAF_NAKES', 'ASESOR',
]

BASE_PERMS = [
    'can_view_pdca', 'can_edit_pdca', 'can_score_ep',
    'can_view_rdwos', 'can_upload_rdwos', 'can_delete_rdwos',
    'can_view_risiko', 'can_manage_risiko',
    'can_lapor_insiden', 'can_investigate_insiden',
    'can_view_scoring', 'can_export_reports',
    'can_manage_units', 'can_manage_users', 'can_verify_kps',
    'can_view_audit_log', 'can_access_control_center',
    'can_manage_system_settings',
]


class Command(BaseCommand):
    help = 'Tulis laporan lengkap akun per unit kerja x tingkatan role.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--password', default='Arima#2026',
            help='Password yang dipakai untuk akun hasil seed.',
        )

    def handle(self, *args, **options):
        from pathlib import Path

        seed_password = options['password']
        units = list(UnitKerja.objects.filter(is_active=True).order_by('level', 'code'))
        profiles = list(
            UserProfile.objects.select_related('user', 'unit_kerja')
            .order_by('role', 'unit_kerja__level', 'unit_kerja__code')
        )

        # (unit_id, role) -> daftar profil
        by_key = {}
        for p in profiles:
            if p.unit_kerja_id:
                by_key.setdefault((p.unit_kerja_id, p.role), []).append(p)

        missing = [
            (u.code, u.name, r) for u in units for r in ROLES
            if (u.pk, r) not in by_key
        ]

        lines = []
        add = lines.append

        add('LAPORAN AKUN PER UNIT KERJA x TINGKATAN ROLE')
        add('Digenerate langsung dari database, bukan dari output command seed.')
        add('')
        add('=' * 78)
        add('1. RINGKASAN CAKUPAN')
        add('=' * 78)
        add(f'Unit kerja aktif          : {len(units)}')
        add(f'Tingkatan role            : {len(ROLES)}')
        add(f'Kombinasi wajib           : {len(units) * len(ROLES)}')
        add(f'Kombinasi terisi          : {len(units) * len(ROLES) - len(missing)}')
        add(f'Kombinasi TERLEWAT        : {len(missing)}')
        add('')
        add(f'Total User di database    : {User.objects.count()}')
        add(f'Total UserProfile         : {UserProfile.objects.count()}')
        add(f'Total HcGrant             : {HcGrant.objects.count()}')
        add(f'Total Pegawai (HC)        : {Pegawai.objects.count()}')
        add('')

        add('Distribusi unit kerja per tingkat hierarki:')
        for row in UnitKerja.objects.filter(is_active=True).values('level').annotate(
            n=Count('id')
        ).order_by('level'):
            add(f'  Level {row["level"]} : {row["n"]} unit')
        add('')

        add('=' * 78)
        add('2. JUMLAH AKUN PER TINGKATAN x LEVEL UNIT')
        add('=' * 78)
        header = f'{"ROLE":<20}' + ''.join(f'{"L" + str(lv):>6}' for lv in (1, 2, 3, 4, 5)) + f'{"TOTAL":>8}'
        add(header)
        add('-' * len(header))
        for role in ROLES:
            row = f'{role:<20}'
            total = 0
            for lv in (1, 2, 3, 4, 5):
                n = len([p for p in profiles if p.role == role
                         and p.unit_kerja and p.unit_kerja.level == lv])
                row += f'{n:>6}'
                total += n
            row += f'{total:>8}'
            add(row)
        add('')

        add('=' * 78)
        add('3. IZIN YANG BENAR-BENAR AKTIF PER TINGKATAN')
        add('=' * 78)
        add('Dihitung lewat has_permission() milik UserProfile, bukan dari tabel default.')
        add('')
        for role in ROLES:
            sample = next((p for p in profiles if p.role == role and p.unit_kerja_id), None)
            if sample is None:
                add(f'{role}: tidak ada sampel')
                continue
            active = [c for c in BASE_PERMS + [c for c, _ in HC_PERMISSION_LABELS]
                      if sample.has_permission(c)]
            add(f'{role}  ({len(active)} izin aktif)')
            for c in active:
                add(f'    - {c}')
            add('')

        add('=' * 78)
        add('4. AKSES HUMAN CAPITAL PER TINGKATAN')
        add('=' * 78)
        add('HcGrant hanya dibuat bila RolePermissionConfig mengizinkan kapabilitasnya.')
        add('Role tanpa izin HC tidak diberi grant — bukan bug, tapi konsekuensi config.')
        add('')
        for role in ROLES:
            n = HcGrant.objects.filter(user__profile__role=role).count()
            users = len([p for p in profiles if p.role == role])
            cfg = RolePermissionConfig.objects.filter(role=role).first()
            caps = [c for c, _ in HC_PERMISSION_LABELS if cfg and getattr(cfg, c, False)]
            add(f'{role}')
            add(f'  akun            : {users}')
            add(f'  HcGrant         : {n}')
            add(f'  izin HC di role : {", ".join(caps) if caps else "(tidak ada)"}')
            add('')

        add('=' * 78)
        add('5. DAFTAR SELURUH AKUN')
        add('=' * 78)
        add(f'{"USERNAME":<26}{"ROLE":<20}{"UNIT":<18}{"LV":>3}  PASSWORD')
        add('-' * 84)
        # Klasifikasi berdasarkan marker email yang HANYA ditulis command seed,
        # bukan berdasarkan prefix username. Prefix seperti `ka.`/`admin.` juga
        # dipakai akun lama, sehingga pendeteksian via prefix salah klasifikasi.
        seeded = []
        legacy = []
        for p in profiles:
            uname = p.user.username
            unit_code = p.unit_kerja.code if p.unit_kerja else '-'
            lv = p.unit_kerja.level if p.unit_kerja else 0
            is_seeded = p.user.email.endswith('@arima.local')
            (seeded if is_seeded else legacy).append(p)
            add(f'{uname:<26}{p.role:<20}{unit_code:<18}{lv:>3}  '
                f'{seed_password if is_seeded else "(password lama)"}')
        add('')

        add('=' * 78)
        add('6. AKUN LAMA YANG PASSWORDNYA TIDAK DIUBAH')
        add('=' * 78)
        add('Akun ini sudah ada sebelum seed, jadi dilewati (tidak dibuat ulang dan')
        add('passwordnya sengaja tidak direset). Login memakai password aslinya.')
        add('')
        for p in legacy:
            unit_code = p.unit_kerja.code if p.unit_kerja else '-'
            add(f'  {p.user.username:<26}{p.role:<20}{unit_code}')
        add('')

        if missing:
            add('=' * 78)
            add('7. KOMBINASI YANG MASIH KOSONG')
            add('=' * 78)
            for code, name, role in missing:
                add(f'  {code:<18}{role:<20}{name}')
        else:
            add('=' * 78)
            add('7. KOMBINASI YANG MASIH KOSONG')
            add('=' * 78)
            add('  Tidak ada. Semua kombinasi unit x tingkatan sudah terisi.')

        path = Path('docs/akun_per_unit_report.txt')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(f'Laporan ditulis ke: {path}'))
        self.stdout.write(f'  baris          : {len(lines)}')
        self.stdout.write(f'  akun seed      : {len(seeded)}')
        self.stdout.write(f'  akun lama      : {len(legacy)}')
        self.stdout.write(f'  kombinasi kosong: {len(missing)}')
