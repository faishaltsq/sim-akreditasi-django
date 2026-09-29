from django.db import migrations


def create_monsiskami_superadmin(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    UserProfile = apps.get_model('accounts', 'UserProfile')

    u, created = User.objects.get_or_create(username='monsiskami', defaults={
        'first_name': 'RS',
        'last_name': 'Monsiskami',
        'is_staff': True,
        'is_superuser': True,
    })
    if created:
        u.set_password('Admin@1234')
        u.save()

    UserProfile.objects.get_or_create(user=u, defaults={
        'role': 'SUPER_ADMIN',
    })


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0003_rolepermissionconfig_userprofile_custom_permissions'),
    ]

    operations = [
        migrations.RunPython(create_monsiskami_superadmin, migrations.RunPython.noop),
    ]
