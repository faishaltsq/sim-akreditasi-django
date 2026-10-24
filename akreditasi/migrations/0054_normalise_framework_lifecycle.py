"""Normalise Framework lifecycle and restore the single-ACTIVE invariant.

Two historical defects are repaired here:

1. Migration ``0052`` added ``Framework.lifecycle`` with ``default='ARCHIVE'`` —
   a value absent from ``choices``. Every pre-existing catalogue therefore
   became ``'ARCHIVE'``, which is not ``'ACTIVE'``, so ``Framework.active()``
   returned ``None``. That silently emptied the sidebar, broke edition-scoped
   screens, and made ``ep_list`` fall back to an unscoped query (the
   "standar tergabung" symptom).
2. ``is_active`` could be ``True`` on a non-ACTIVE row (split-brain).

This migration only repairs vocabulary and the invariant for **existing** data.
It promotes the newest readable catalogue to ACTIVE **when the table is
non-empty and nothing is ACTIVE** — restoring the state that ``0052`` destroyed.
On an empty catalogue table it does nothing, so a fresh install still requires
an explicit, reviewed activation.

No StandardItem / QualityRecord / EvidenceFile row is touched.
"""

from django.db import migrations


CANONICAL = {
    'ARCHIVE': 'ARCHIVED',
    'ARCHIVED_LEGACY': 'ARCHIVED',
    'INACTIVE': 'ARCHIVED',
    'PUBLISHED': 'ACTIVE',
    'LIVE': 'ACTIVE',
}

VALID = ('DRAFT', 'VALIDATED', 'ACTIVE', 'ARCHIVED')


def normalise(apps, schema_editor):
    Framework = apps.get_model('akreditasi', 'Framework')

    # 1. Canonicalise legacy spellings (notably the 'ARCHIVE' default).
    for legacy, canonical in CANONICAL.items():
        Framework.objects.filter(lifecycle=legacy).update(lifecycle=canonical)

    # 2. Any unknown value becomes ARCHIVED (never silently ACTIVE).
    for framework in Framework.objects.exclude(lifecycle__in=VALID):
        Framework.objects.filter(pk=framework.pk).update(lifecycle='ARCHIVED')

    # 3. Restore the single-ACTIVE invariant for pre-existing data.
    #    Nothing is promoted on an empty catalogue table.
    if not Framework.objects.exists():
        return

    actives = list(
        Framework.objects.filter(lifecycle='ACTIVE').order_by('-edition', '-version', 'pk')
    )
    if not actives:
        # 0052 wiped the only catalogue to 'ARCHIVE'; promote the newest
        # readable one back to ACTIVE so the application has a working edition.
        candidate = (
            Framework.objects.exclude(lifecycle__in=('DRAFT', 'VALIDATED'))
            .order_by('-edition', '-version', 'pk')
            .first()
        )
        if candidate is None:
            candidate = Framework.objects.order_by('-edition', '-version', 'pk').first()
        Framework.objects.filter(pk=candidate.pk).update(lifecycle='ACTIVE')
        actives = [candidate]

    # 4. Exactly one ACTIVE: keep the newest, archive the rest.
    keep = actives[0]
    Framework.objects.exclude(pk=keep.pk).update(lifecycle='ARCHIVED', is_active=False)

    # 5. Repair the split-brain flag: is_active is only legal on ACTIVE rows.
    Framework.objects.filter(pk=keep.pk).update(is_active=True)
    Framework.objects.exclude(pk=keep.pk).update(is_active=False)


def reverse(apps, schema_editor):
    """No-op: lifecycle vocabulary repair is not safely reversible."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0053_add_presensi_models'),
    ]

    operations = [
        migrations.RunPython(normalise, reverse),
    ]
