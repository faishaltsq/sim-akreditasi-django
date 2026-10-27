from datetime import datetime

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q

from akreditasi.models import UnitKerja
from sdm.models.akses import HC_CAPABILITY_CHOICES
from sdm.services.akses_hc import aktifkan_role_untuk, sinkronkan_grant

CAPABILITAS_KREDENSIAL = (
    'can_view_hc',
    'can_manage_hc_documents',
    'can_review_hc_credentials',
    'hc_verify_credentials',
    'hc_review_subkomite',
    'hc_recommend_komite',
    'hc_approve_credentials',
)


class Command(BaseCommand):
    help = 'Berikan kapabilitas Human Capital ke satu akun.'

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--capability', action='append', dest='capabilities',
                            help='Kode kapabilitas; boleh diulang. Default: semua kapabilitas kredensial.')
        parser.add_argument('--all', action='store_true', help='Semua kapabilitas HC.')
        parser.add_argument('--unit', help='Kode atau PK unit kerja. Default: RS-wide (NULL).')
        parser.add_argument('--include-descendants', action='store_true')
        parser.add_argument('--valid-until', help='YYYY-MM-DD.')
        parser.add_argument('--no-role', action='store_true',
                            help='Jangan aktifkan izin role; hanya buat grant.')

    def handle(self, *args, **options):
        username = options['username']
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Pengguna '{username}' tidak ditemukan.")

        valid = dict(HC_CAPABILITY_CHOICES)
        if options['all']:
            capabilities = set(valid)
        elif options['capabilities']:
            unknown = [c for c in options['capabilities'] if c not in valid]
            if unknown:
                raise CommandError(
                    'Kapabilitas tidak dikenal: ' + ', '.join(sorted(unknown))
                    + '. Pilihan: ' + ', '.join(sorted(valid))
                )
            capabilities = set(options['capabilities'])
        else:
            capabilities = set(CAPABILITAS_KREDENSIAL)

        unit = None
        if options['unit']:
            arg = options['unit']
            unit = UnitKerja.objects.filter(
                Q(code=arg) | Q(pk=int(arg) if arg.isdigit() else -1)
            ).first()
            if unit is None:
                raise CommandError(f"Unit kerja '{arg}' tidak ditemukan.")

        valid_until = None
        if options['valid_until']:
            try:
                valid_until = datetime.strptime(options['valid_until'], '%Y-%m-%d').date()
            except ValueError:
                raise CommandError('--valid-until harus berformat YYYY-MM-DD.')

        role_on = set()
        if not options['no_role']:
            role_on = aktifkan_role_untuk(user, capabilities)

        added, removed = sinkronkan_grant(
            user,
            capabilities=capabilities,
            unit=unit,
            include_descendants=options['include_descendants'],
            valid_until=valid_until,
            actor=None,
        )

        self.stdout.write(
            f'{username}: +{added} grant, -{removed} grant, {len(capabilities)} kapabilitas, '
            f'lingkup {unit.code if unit else "RS"}, '
            f'role diaktifkan: {", ".join(sorted(role_on)) or "-"}'
        )
