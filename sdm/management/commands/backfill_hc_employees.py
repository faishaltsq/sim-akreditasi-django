"""Create Human Capital employee identities from existing accounts (exact match only)."""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import UserProfile
from sdm.models import Pegawai


NAKES_ROLES = {'STAF_NAKES', 'KEPALA_UNIT', 'KOORDINATOR_POKJA', 'ADMIN_RS'}


class Command(BaseCommand):
    help = (
        'Backfill sdm.Pegawai from existing accounts so legacy credential routes '
        'keep working. Dry-run by default; never overwrites an existing identity.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument(
            '--role', action='append', dest='roles',
            help='Limit to these roles (repeatable). Defaults to all roles.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        roles = set(options['roles'] or [])
        profiles = UserProfile.objects.select_related('user').order_by('pk')
        if roles:
            profiles = profiles.filter(role__in=roles)

        linked_user_ids = set(
            Pegawai.objects.exclude(akun_id=None).values_list('akun_id', flat=True)
        )
        used_numbers = set(
            Pegawai.objects.exclude(nomor_pegawai='').values_list(
                'nomor_pegawai', flat=True
            )
        )

        created = skipped = duplicates = 0
        pending = []
        for profile in profiles:
            if profile.user_id in linked_user_ids:
                skipped += 1
                continue

            number = (profile.nip_nrp or '').strip()
            if number and number in used_numbers:
                duplicates += 1
                number = ''

            pending.append((profile, number))
            if number:
                used_numbers.add(number)

        if not apply:
            self.stdout.write(
                'DRY-RUN '
                f'profiles={profiles.count()} '
                f'create={len(pending)} '
                f'already_linked={skipped} '
                f'duplicate_numbers_blanked={duplicates}'
            )
            return

        with transaction.atomic():
            for profile, number in pending:
                Pegawai.objects.create(
                    akun_id=profile.user_id,
                    nama_lengkap=(
                        (profile.full_name or '').strip()
                        or profile.user.get_full_name()
                        or profile.user.username
                    )[:200],
                    nomor_pegawai=number,
                    kategori='PPA' if profile.profesi else 'NON_PPA',
                    profesi=(profile.profesi or '')[:120],
                    jabatan=(profile.jabatan or '')[:150],
                )
                created += 1

        self.stdout.write(
            'APPLIED '
            f'created={created} '
            f'already_linked={skipped} '
            f'duplicate_numbers_blanked={duplicates}'
        )
