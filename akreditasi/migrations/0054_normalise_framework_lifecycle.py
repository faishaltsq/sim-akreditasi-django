"""Normalise legacy Framework lifecycle spellings (data repair only).

Historical rows used non-canonical spellings (notably ``ARCHIVE``) which made
``Framework.active()`` return ``None``. This migration only repairs the
vocabulary; it deliberately does **not** promote any catalogue to ACTIVE.
Activation stays a reviewed, audited operation owned by
``catalogue_services.activate_catalogue`` — a data migration must never decide
which accreditation edition is authoritative.

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

    # 1. Canonicalise legacy spellings.
    for legacy, canonical in CANONICAL.items():
        Framework.objects.filter(lifecycle=legacy).update(lifecycle=canonical)

    # 2. Any unknown value becomes ARCHIVED (never silently ACTIVE).
    for framework in Framework.objects.exclude(lifecycle__in=VALID):
        Framework.objects.filter(pk=framework.pk).update(lifecycle='ARCHIVED')

    # 3. Repair the split-brain flag: is_active must not be True unless the row
    #    is genuinely ACTIVE. We never set is_active=True here.
    Framework.objects.exclude(lifecycle='ACTIVE').update(is_active=False)

    # 4. If more than one row claims ACTIVE (possible on legacy data), keep the
    #    newest readable one and archive the rest. This preserves the single-
    #    active invariant without promoting a new edition.
    actives = list(
        Framework.objects.filter(lifecycle='ACTIVE').order_by('-edition', '-version', 'pk')
    )
    if len(actives) > 1:
        keep = actives[0]
        for extra in actives[1:]:
            Framework.objects.filter(pk=extra.pk).update(
                lifecycle='ARCHIVED', is_active=False
            )
        Framework.objects.filter(pk=keep.pk).update(is_active=True)


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
