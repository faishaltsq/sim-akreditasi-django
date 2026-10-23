"""Provision Human Capital role permissions and scoped grants.

Human Capital is fail-closed: a role permission is only a gate, and an explicit
`HcGrant` supplies the unit scope. This command applies a conservative default
matrix and can be re-run safely.

Policy applied:
  SUPER_ADMIN, ADMIN_RS  -> all non-health capabilities, hospital scope
  KEPALA_UNIT            -> read + documents/appraisals/orientation, own unit
  others                 -> unchanged (self-service credential access still
                            works through the owner path, no grant needed)

Health capabilities (hc_health_*) are never granted here; they require an
explicit clinical appointment and must be issued individually.
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import RolePermissionConfig, UserProfile
from sdm.models import HcGrant


ROLE_PERMISSIONS = {
    'SUPER_ADMIN': [
        'can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents',
        'can_plan_hc_workforce', 'can_manage_hc_recruitment',
        'can_review_hc_credentials', 'can_manage_hc_orientation',
        'can_manage_hc_appraisals', 'can_manage_hc_training',
        'can_view_hc_analytics', 'can_manage_hc_talent', 'can_export_hc',
    ],
    'ADMIN_RS': [
        'can_view_hc', 'can_manage_hc_employees', 'can_manage_hc_documents',
        'can_plan_hc_workforce', 'can_manage_hc_recruitment',
        'can_review_hc_credentials', 'can_manage_hc_orientation',
        'can_manage_hc_appraisals', 'can_manage_hc_training',
        'can_view_hc_analytics', 'can_manage_hc_talent', 'can_export_hc',
    ],
    'KEPALA_UNIT': [
        'can_view_hc', 'can_manage_hc_documents', 'can_manage_hc_orientation',
        'can_manage_hc_appraisals',
    ],
}

# Capabilities granted per role, plus the scope rule.
GRANT_MATRIX = {
    'SUPER_ADMIN': {'hospital': True, 'capabilities': ROLE_PERMISSIONS['SUPER_ADMIN']},
    'ADMIN_RS': {'hospital': True, 'capabilities': ROLE_PERMISSIONS['ADMIN_RS']},
    'KEPALA_UNIT': {'hospital': False, 'capabilities': ROLE_PERMISSIONS['KEPALA_UNIT']},
}


class Command(BaseCommand):
    help = 'Provision Human Capital role permissions and scoped grants (idempotent).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Write changes. Without this the command only reports.',
        )

    def handle(self, *args, **options):
        apply = options['apply']

        role_changes = []
        for role, capabilities in ROLE_PERMISSIONS.items():
            config = RolePermissionConfig.get_config_for_role(role)
            pending = [c for c in capabilities if not getattr(config, c)]
            if pending:
                role_changes.append((role, config, pending))

        grants = []
        skipped_no_unit = []
        profiles = UserProfile.objects.select_related('user', 'unit_kerja').filter(
            user__is_active=True
        )
        for profile in profiles:
            rule = GRANT_MATRIX.get(profile.role)
            if rule is None:
                continue
            if not rule['hospital'] and profile.unit_kerja_id is None:
                skipped_no_unit.append(profile.user.username)
                continue
            unit_id = None if rule['hospital'] else profile.unit_kerja_id
            for capability in rule['capabilities']:
                grants.append((profile.user_id, capability, unit_id))

        self.stdout.write(self.style.NOTICE('=== RENCANA ==='))
        for role, _config, pending in role_changes:
            self.stdout.write(f'  role {role:16} +{len(pending)} izin')
        per_role = {}
        for profile in profiles:
            if profile.role in GRANT_MATRIX:
                per_role[profile.role] = per_role.get(profile.role, 0) + 1
        for role, count in sorted(per_role.items()):
            self.stdout.write(f'  akun {role:16} {count:3} -> '
                              f'{count * len(GRANT_MATRIX[role]["capabilities"])} grant')
        self.stdout.write(f'  grant baru/diperbarui: {len(grants)}')
        if skipped_no_unit:
            self.stdout.write(
                '  dilewati (tanpa unit): ' + ', '.join(skipped_no_unit)
            )

        if not apply:
            self.stdout.write(self.style.WARNING(
                '\nDRY RUN — jalankan dengan --apply untuk menerapkan.'
            ))
            return

        created = updated = 0
        with transaction.atomic():
            for role, config, pending in role_changes:
                for capability in pending:
                    setattr(config, capability, True)
                config.save(update_fields=pending + ['updated_at'])

            for user_id, capability, unit_id in grants:
                _grant, was_created = HcGrant.objects.update_or_create(
                    user_id=user_id,
                    capability=capability,
                    unit_kerja_id=unit_id,
                    defaults={'is_active': True},
                )
                created += int(was_created)
                updated += int(not was_created)

        self.stdout.write(self.style.SUCCESS(
            f'APPLIED role_roles={len(role_changes)} '
            f'grants_created={created} grants_updated={updated} '
            f'skipped_no_unit={len(skipped_no_unit)}'
        ))
