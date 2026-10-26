"""
Management command: seed_akun_per_unit

Membuat satu akun untuk SETIAP kombinasi (unit kerja aktif x tingkatan role),
sehingga tidak ada unit maupun tingkatan role yang terlewat.

Idempotensi memakai pasangan (unit_kerja, role) — BUKAN username. Ini penting
karena username lama bisa sudah menempati nama yang sama untuk unit berbeda
(mis. `ka.ranap` milik unit BANGSAL-DEWASA, bukan RANAP). Bila username bentrok,
command memakai fallback `<prefix>.<kode>.<n>`.

Untuk tiap akun:
  - User + UserProfile (role, unit_kerja, profesi, NIP sintetis deterministik)
  - pokja_access (khusus KOORDINATOR_POKJA, diturunkan dari standar_terkait unit)
  - HcGrant (khusus role yang izinnya memang aktif di RolePermissionConfig)
  - Pegawai + PenempatanPegawai (khusus role operasional, FTE 1.00)

Contoh:
    python manage.py seed_akun_per_unit --dry-run
    python manage.py seed_akun_per_unit
    python manage.py seed_akun_per_unit --roles KEPALA_UNIT --units IGD,FARM
"""
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from accounts.models import RolePermissionConfig, UserProfile
from akreditasi.models import Category, UnitKerja
from sdm.models import HcGrant, Pegawai, PenempatanPegawai

User = get_user_model()

DEFAULT_PASSWORD = 'Arima#2026'

# Kapabilitas HC non-kesehatan. Data kesehatan kerja sengaja TIDAK diberikan
# otomatis: sesuai desain modul, itu butuh grant eksplisit terpisah.
HC_BASE_CAPS = [
    'can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents',
    'can_plan_hc_workforce', 'can_manage_hc_recruitment',
    'can_review_hc_credentials', 'can_manage_hc_orientation',
    'can_manage_hc_appraisals', 'can_manage_hc_training',
    'can_view_hc_analytics', 'can_manage_hc_talent', 'can_export_hc',
]

# Tingkatan akun yang dibuat untuk setiap unit kerja.
ROLE_SPECS = [
    {
        'role': 'SUPER_ADMIN',
        'prefix': 'sa',
        'label': 'Super Admin (IT RS)',
        'jabatan': 'Super Admin Sistem — {unit}',
        'is_staff': True,
        'is_super': True,
        'profesi': '',
        'is_pegawai': False,
        # has_permission() short-circuit True untuk SUPER_ADMIN, tapi HcGrant
        # tetap wajib ada agar _active_grants() tidak mengembalikan queryset kosong.
        'hc_capabilities': HC_BASE_CAPS,
    },
    {
        'role': 'ADMIN_RS',
        'prefix': 'admin',
        'label': 'Admin Akreditasi RS (Tim Mutu)',
        'jabatan': 'Admin Akreditasi — {unit}',
        'is_staff': False,
        'is_super': False,
        'profesi': '',
        'is_pegawai': False,
        'hc_capabilities': HC_BASE_CAPS,
    },
    {
        'role': 'KOORDINATOR_POKJA',
        'prefix': 'pokja',
        'label': 'Koordinator Pokja',
        'jabatan': 'Koordinator Pokja — {unit}',
        'is_staff': False,
        'is_super': False,
        'profesi': '',
        'is_pegawai': False,
        'hc_capabilities': [],
    },
    {
        'role': 'KEPALA_UNIT',
        'prefix': 'ka',
        'label': 'Kepala Unit Kerja',
        'jabatan': 'Kepala {unit}',
        'is_staff': False,
        'is_super': False,
        'profesi': '',
        'is_pegawai': True,
        'hc_capabilities': ['can_view_hc'],
    },
    {
        'role': 'STAF_NAKES',
        'prefix': 'nakes',
        'label': 'Staf Nakes / Pelaksana',
        'jabatan': 'Staf Pelaksana — {unit}',
        'is_staff': False,
        'is_super': False,
        'profesi': 'PERAWAT',
        'is_pegawai': True,
        'hc_capabilities': [],
    },
    {
        'role': 'ASESOR',
        'prefix': 'asesor',
        'label': 'Asesor / Viewer (Baca Saja)',
        'jabatan': 'Asesor Eksternal — {unit}',
        'is_staff': False,
        'is_super': False,
        'profesi': '',
        'is_pegawai': False,
        'hc_capabilities': ['can_view_hc', 'can_view_hc_analytics'],
    },
]


class Command(BaseCommand):
    help = (
        'Membuat satu akun untuk setiap kombinasi unit kerja aktif x tingkatan role, '
        'lengkap dengan profil, akses pokja, HcGrant, dan penempatan pegawai.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Hitung dan tampilkan rencana tanpa menulis ke database.',
        )
        parser.add_argument(
            '--password',
            default=DEFAULT_PASSWORD,
            help=f'Password untuk akun yang baru dibuat (default: {DEFAULT_PASSWORD}).',
        )
        parser.add_argument(
            '--roles',
            default='',
            help='Batasi ke role tertentu, dipisah koma. Contoh: KEPALA_UNIT,STAF_NAKES',
        )
        parser.add_argument(
            '--units',
            default='',
            help='Batasi ke kode unit tertentu, dipisah koma. Contoh: IGD,FARM,LAB',
        )
        parser.add_argument(
            '--include-inactive',
            action='store_true',
            help='Ikutkan unit kerja yang is_active=False.',
        )
        parser.add_argument(
            '--sync-grants',
            action='store_true',
            help=(
                'Untuk akun yang sudah ada: lengkapi HcGrant yang belum terbentuk, '
                'tanpa membuat akun baru dan tanpa mengubah password.'
            ),
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        password = options['password']
        sync_grants = options['sync_grants']

        specs = ROLE_SPECS
        role_filter = {r.strip().upper() for r in options['roles'].split(',') if r.strip()}
        if role_filter:
            unknown = role_filter - {s['role'] for s in ROLE_SPECS}
            if unknown:
                raise CommandError(f'Role tidak dikenal: {", ".join(sorted(unknown))}')
            specs = [s for s in specs if s['role'] in role_filter]

        units_qs = UnitKerja.objects.all().order_by('level', 'code')
        if not options['include_inactive']:
            units_qs = units_qs.filter(is_active=True)
        units = list(units_qs)

        unit_filter = {u.strip().upper() for u in options['units'].split(',') if u.strip()}
        if unit_filter:
            found = {u.code.upper() for u in units}
            missing = unit_filter - found
            if missing:
                raise CommandError(f'Kode unit tidak ditemukan: {", ".join(sorted(missing))}')
            units = [u for u in units if u.code.upper() in unit_filter]

        if not units:
            raise CommandError('Tidak ada unit kerja yang cocok dengan filter.')
        if not specs:
            raise CommandError('Tidak ada role yang cocok dengan filter.')

        total_kombinasi = len(units) * len(specs)
        self.stdout.write(self.style.MIGRATE_HEADING(
            f'=== SEED AKUN PER UNIT ===\n'
            f'Unit kerja : {len(units)}\n'
            f'Tingkatan  : {len(specs)} ({", ".join(s["role"] for s in specs)})\n'
            f'Kombinasi  : {total_kombinasi}'
            f'{"   [DRY RUN]" if dry_run else ""}\n'
        ))

        # (unit_id, role) yang sudah punya akun — kunci idempotensi sebenarnya.
        existing = set(
            UserProfile.objects.exclude(unit_kerja__isnull=True)
            .values_list('unit_kerja_id', 'role')
        )
        taken = set(User.objects.values_list('username', flat=True))
        pokja_by_unit = self._pokja_map(units)
        role_caps = self._role_hc_capabilities()

        hashed = None if dry_run else make_password(password)

        dibuat = {s['role']: 0 for s in specs}
        dilewati = {s['role']: 0 for s in specs}
        rows = []
        username_conflicts = 0
        grants_synced = 0

        for unit in units:
            for spec in specs:
                key = (unit.pk, spec['role'])
                if key in existing:
                    dilewati[spec['role']] += 1
                    if sync_grants and not dry_run:
                        n = self._sync_grants_for(unit=unit, role=spec['role'],
                                                  spec=spec, role_caps=role_caps)
                        grants_synced += n
                    continue

                base = f"{spec['prefix']}.{unit.code.lower()}"
                username = self._pick_username(spec['prefix'], unit.code, taken)
                if username != base:
                    username_conflicts += 1

                if not dry_run:
                    self._create_account(
                        spec=spec,
                        unit=unit,
                        username=username,
                        hashed=hashed,
                        pokja_categories=pokja_by_unit.get(unit.pk, []),
                        role_caps=role_caps,
                    )
                    existing.add(key)
                taken.add(username)
                dibuat[spec['role']] += 1
                rows.append((username, spec['role'], unit.code))

        self.stdout.write('\n--- Ringkasan per tingkatan ---')
        for spec in specs:
            r = spec['role']
            self.stdout.write(
                f'  {r:<18} dibuat={dibuat[r]:<5} sudah_ada={dilewati[r]}'
            )

        total_dibuat = sum(dibuat.values())
        total_lewati = sum(dilewati.values())
        self.stdout.write(
            f'\nTotal kombinasi     : {total_kombinasi}\n'
            f'Total akun dibuat   : {total_dibuat}\n'
            f'Total sudah ada     : {total_lewati}\n'
            f'Verifikasi          : {total_dibuat + total_lewati} / {total_kombinasi}'
        )
        if total_dibuat + total_lewati != total_kombinasi:
            raise CommandError('Jumlah tidak seimbang — ada kombinasi terlewat.')
        if username_conflicts:
            self.stdout.write(
                f'Username bentrok     : {username_conflicts} (diberi akhiran .2/.3)'
            )
        if sync_grants:
            self.stdout.write(f'HcGrant disinkronkan : {grants_synced}')

        if dry_run:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN — tidak ada perubahan database.'
            ))
            return

        self._write_report(rows, role_caps)
        self.stdout.write(self.style.SUCCESS(
            f'\nSelesai. Password semua akun baru: {password}'
        ))

    # ------------------------------------------------------------------ util

    @staticmethod
    def _pick_username(prefix, unit_code, taken):
        base = f'{prefix}.{unit_code.lower()}'
        if base not in taken:
            return base
        n = 2
        while f'{base}.{n}' in taken:
            n += 1
        return f'{base}.{n}'

    @staticmethod
    def _role_hc_capabilities():
        """Kapabilitas HC yang benar-benar diizinkan konfigurasi role saat ini."""
        allowed = {}
        for cfg in RolePermissionConfig.objects.all():
            allowed[cfg.role] = {
                cap for cap, _ in HcGrant.CAPABILITY_CHOICES
                if getattr(cfg, cap, False)
            }
        return allowed

    @staticmethod
    def _pokja_map(units):
        """Petakan unit -> Category relevan, diturunkan dari standar_terkait unit."""
        wanted = set()
        for unit in units:
            wanted.update((unit.standar_terkait or {}).keys())
        categories = {c.code: c for c in Category.objects.filter(code__in=wanted)}
        return {
            unit.pk: [categories[c] for c in (unit.standar_terkait or {}) if c in categories]
            for unit in units
        }

    @staticmethod
    def _nip(unit, spec):
        """NIP sintetis deterministik: satu unit + satu role = satu NIP."""
        return f'HC-{unit.code.upper()[:12]}-{spec["prefix"].upper()[:3]}-{unit.pk:05d}'

    def _sync_grants_for(self, *, unit, role, spec, role_caps):
        """Lengkapi HcGrant yang belum ada untuk akun yang sudah terlanjur dibuat.

        Hanya menambah, tidak pernah menghapus grant yang sudah ada — grant
        mungkin diberikan manual oleh operator dan tidak boleh hilang.
        """
        permitted = role_caps.get(role, set())
        if role == 'SUPER_ADMIN':
            # short-circuit has_permission True; grant tetap perlu agar scope aktif.
            permitted = set(spec['hc_capabilities'])

        wanted = [c for c in spec['hc_capabilities'] if c in permitted]
        if not wanted:
            return 0

        profile = (
            UserProfile.objects.filter(unit_kerja_id=unit.pk, role=role)
            .select_related('user')
            .first()
        )
        if profile is None:
            return 0

        today = timezone.localdate()
        added = 0
        for capability in wanted:
            exists = HcGrant.objects.filter(
                user_id=profile.user_id, capability=capability,
                unit_kerja_id=unit.pk, is_active=True,
            ).exists()
            if exists:
                continue
            HcGrant.objects.create(
                user_id=profile.user_id,
                capability=capability,
                unit_kerja=unit,
                include_descendants=False,
                valid_from=today,
                is_active=True,
            )
            added += 1
        return added

    @transaction.atomic
    def _create_account(self, *, spec, unit, username, hashed, pokja_categories, role_caps):
        today = timezone.localdate()
        user = User.objects.create(
            username=username,
            email=f'{username}@arima.local',
            first_name=spec['label'][:30],
            last_name=unit.code[:30],
            is_staff=spec['is_staff'],
            is_superuser=spec['is_super'],
            is_active=True,
            password=hashed,
        )

        profile = UserProfile.objects.create(
            user=user,
            role=spec['role'],
            unit_kerja=unit,
            full_name=f"{spec['label']} — {unit.name}",
            jabatan=spec['jabatan'].format(unit=unit.name),
            profesi=spec['profesi'],
            nip_nrp=self._nip(unit, spec),
            is_active_member=True,
        )

        if spec['role'] == 'KOORDINATOR_POKJA' and pokja_categories:
            profile.pokja_access.set(pokja_categories)

        # HcGrant hanya dibuat bila role memang mengizinkan kapabilitas itu.
        # Grant tanpa izin role akan mati dan menyesatkan saat diaudit.
        permitted = role_caps.get(spec['role'], set())
        for capability in spec['hc_capabilities']:
            if capability not in permitted:
                continue
            HcGrant.objects.create(
                user=user,
                capability=capability,
                unit_kerja=unit,
                include_descendants=False,
                valid_from=today,
                is_active=True,
            )

        if spec['is_pegawai']:
            pegawai = Pegawai.objects.create(
                akun=user,
                nomor_pegawai=profile.nip_nrp,
                nama_lengkap=profile.full_name,
                kategori='PPA',
                profesi=spec['profesi'],
                jabatan=profile.jabatan,
                status='AKTIF',
            )
            PenempatanPegawai.objects.create(
                pegawai=pegawai,
                unit_kerja=unit,
                tanggal_mulai=today,
                alokasi_fte='1.00',
            )

    def _write_report(self, rows, role_caps):
        """Tulis daftar akun + matriks akses ke file untuk referensi operator."""
        from pathlib import Path

        path = Path('docs/akun_per_unit_report.txt')
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            '# Daftar akun hasil seed_akun_per_unit',
            '# format: username<TAB>role<TAB>kode_unit',
            '',
        ]
        lines += [f'{u}\t{r}\t{c}' for u, r, c in rows]
        lines += ['', '# Kapabilitas Human Capital yang diizinkan per role:']
        for role in sorted(role_caps):
            caps = sorted(role_caps[role]) or ['-']
            lines.append(f'#   {role}: {", ".join(caps)}')
        path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        self.stdout.write(f'\nDaftar akun ditulis ke: {path}')
