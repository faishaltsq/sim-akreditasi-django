"""Repair the STARKES edition identity that the 2024 import left inconsistent.

Three defects accumulated in production and none of them is repaired by
``0054_normalise_framework_lifecycle``:

1. ``import_instrumen_2024`` created the 2024 catalogue without setting
   ``edition``, so it inherited the model default ``'2022'``. Every
   edition-ordered comparison then ranked the retired 2022 catalogue above the
   live 2024 one.
2. ``_replace`` only wrote ``is_active`` and never ``lifecycle``, so the import
   that was supposed to activate 2024 left the whole table non-ACTIVE.
3. The archived 2022 catalogue carries ``version='2024-archived'`` (the import
   stamps ``<version>-archived``; its version had already been bumped to 2024),
   which sorts above the plain ``'2024'``.

This migration repairs identity and lifecycle only. It never touches
``StandardItem``, ``QualityRecord``, ``EvidenceFile`` or ``EvidenceReq``, so no
score, note or evidence link can move between editions here.
"""

from django.db import migrations

# Catalogues whose name declares an edition newer than what `edition` records.
EDITION_FROM_NAME = (
    ('STARKES Edisi 2024', '2024'),
    ('STARKES Edisi 2022', '2022'),
)


def repair(apps, schema_editor):
    Framework = apps.get_model('akreditasi', 'Framework')

    rows = list(Framework.objects.all())
    if not rows:
        return

    # 1. Re-derive `edition` from the catalogue name, which is the only field
    #    that was authored correctly by the importer.
    for framework in rows:
        for marker, edition in EDITION_FROM_NAME:
            if framework.name.startswith(marker):
                if framework.edition != edition:
                    Framework.objects.filter(pk=framework.pk).update(edition=edition)
                    framework.edition = edition
                break

    # 2. Pick the catalogue that should be live: a non-superseded row, newest
    #    edition first. `-archived`/`-lama` rows are superseded by definition.
    live = [
        fw for fw in rows
        if not (fw.version or '').endswith(('-archived', '-lama'))
    ]
    if not live:
        live = rows

    def rank(framework):
        edition = (framework.edition or '').strip()
        version = (framework.version or '').split('-')[0]
        return (
            int(edition) if edition.isdigit() else -1,
            int(version) if version.isdigit() else -1,
            framework.pk,
        )

    keep = max(live, key=rank)

    # 3. Restore the single-ACTIVE invariant.
    Framework.objects.exclude(pk=keep.pk).update(lifecycle='ARCHIVED', is_active=False)
    Framework.objects.filter(pk=keep.pk).update(lifecycle='ACTIVE', is_active=True)


def reverse(apps, schema_editor):
    """No-op: the previous state was itself the defect being repaired."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('akreditasi', '0056_drop_unique_active_framework'),
    ]

    operations = [
        migrations.RunPython(repair, reverse),
    ]
