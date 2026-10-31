from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.views import LoginView as BaseLoginView
from django.utils.decorators import method_decorator
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q

from .models import UserProfile, VALID_PERMISSION_KEYS
from .forms import UserCreateForm, UserEditForm, UserProfileForm
from akreditasi.models import AuditLog, UnitKerja
from sdm.models import HcGrant
from sdm.models.akses import HC_CAPABILITY_CHOICES
from sdm.services.akses_hc import aktifkan_role_untuk, pemberi_akses, sinkronkan_grant
from akreditasi.input_parsing import json_body, parse_int
from akreditasi.security_utils import rate_limit


@method_decorator(rate_limit(max_calls=8, window=60, scope='login'), name='dispatch')
class RateLimitedLoginView(BaseLoginView):
    """View login dengan proteksi anti brute-force: maksimal 8 request per 60 detik."""
    template_name = 'accounts/login.html'


def admin_only(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return profile and profile.can_manage_users


def _is_super_admin(user) -> bool:
    """Cek apakah user adalah superuser Django atau memiliki peran SUPER_ADMIN."""
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.role == 'SUPER_ADMIN')


def _caller_role_level(user) -> int:
    """Tingkat hierarki peran pemanggil; superuser/SUPER_ADMIN selalu di puncak (5)."""
    if _is_super_admin(user):
        return UserProfile.ROLE_HIERARCHY.get('SUPER_ADMIN', 5)
    profile = getattr(user, 'profile', None)
    return profile.role_level if profile else 0


def _can_assign_role(caller, target_role: str) -> bool:
    """Pemanggil hanya boleh menetapkan peran yang lebih rendah dari tingkatnya sendiri.
    Non-superuser / non-SUPER_ADMIN tidak dapat menetapkan peran setara atau lebih tinggi,
    dan tidak dapat membuat akun SUPER_ADMIN.
    """
    if _is_super_admin(caller):
        return True
    if target_role == 'SUPER_ADMIN':
        return False
    target_level = UserProfile.ROLE_HIERARCHY.get(target_role, 0)
    return target_level < _caller_role_level(caller)


def _can_modify_account(caller, target_user) -> bool:
    """Hanya boleh mengubah akun dengan tingkat hierarki lebih rendah.
    Superuser / SUPER_ADMIN boleh mengubah akun setara atau lebih rendah.
    """
    if _is_super_admin(caller):
        return True
    target_profile = getattr(target_user, 'profile', None)
    target_level = target_profile.role_level if target_profile else 0
    return target_level < _caller_role_level(caller)


def _is_last_active_superuser(target_user) -> bool:
    """True bila target adalah satu-satunya superuser / SUPER_ADMIN aktif."""
    is_target_super = target_user.is_superuser or (
        hasattr(target_user, 'profile') and target_user.profile.role == 'SUPER_ADMIN'
    )
    if not is_target_super:
        return False
    active_supers = User.objects.filter(is_active=True).filter(
        Q(is_superuser=True) | Q(profile__role='SUPER_ADMIN')
    ).exclude(pk=target_user.pk).exists()
    return not active_supers


@login_required
@user_passes_test(admin_only)
def user_list(request):
    role_filter = request.GET.get('role', 'ALL')
    search_q = request.GET.get('q', '').strip()

    users_qs = User.objects.select_related('profile__unit_kerja').prefetch_related('profile__pokja_access').all().order_by('-date_joined')

    if role_filter != 'ALL':
        users_qs = users_qs.filter(profile__role=role_filter)

    if search_q:
        users_qs = users_qs.filter(
            Q(username__icontains=search_q) |
            Q(profile__full_name__icontains=search_q) |
            Q(profile__jabatan__icontains=search_q) |
            Q(email__icontains=search_q)
        )

    # Pastikan setiap User punya profile
    for u in users_qs:
        if not hasattr(u, 'profile'):
            UserProfile.objects.get_or_create(
                user=u,
                defaults={'role': 'SUPER_ADMIN' if u.is_superuser else 'ASESOR'}
            )

    return render(request, 'accounts/user_list.html', {
        'users': users_qs,
        'role_choices': UserProfile.ROLE_CHOICES,
        'selected_role': role_filter,
        'search_q': search_q,
    })


def _capability_grid():
    """Pasangan (kode, label) untuk seluruh kapabilitas HC."""
    return list(HC_CAPABILITY_CHOICES)


def _hc_context(user=None):
    """Nilai awal bagian Hak Akses HC pada form pengguna."""
    selected, scope, unit_id, descendants = set(), 'RS', '', False
    if user is not None:
        grants = list(HcGrant.objects.filter(user=user, is_active=True).select_related('unit_kerja'))
        selected = {g.capability for g in grants}
        scoped = [g for g in grants if g.unit_kerja_id]
        if scoped:
            scope = 'UNIT'
            unit_id = scoped[0].unit_kerja_id
            descendants = scoped[0].include_descendants
    return {
        'hc_capabilities': _capability_grid(),
        'hc_units': UnitKerja.objects.filter(is_active=True).order_by('level', 'order', 'code'),
        'hc_terpilih': selected,
        'hc_lingkup_terpilih': scope,
        'hc_unit_terpilih': unit_id,
        'hc_include_descendants': descendants,
    }


def _simpan_grant_dari_form(request, target_user):
    """Terapkan pilihan grant dari POST; return (added, removed)."""
    if request.POST.get('hc_akses_diisi') != '1':
        return 0, 0
    if pemberi_akses(request.user) is None:
        return 0, 0

    valid = dict(HC_CAPABILITY_CHOICES)
    selected = {c for c in request.POST.getlist('hc_capability') if c in valid}

    unit = None
    if request.POST.get('hc_lingkup') == 'UNIT':
        raw = request.POST.get('hc_unit') or ''
        unit = UnitKerja.objects.filter(pk=int(raw)).first() if raw.isdigit() else None
        if unit is None:
            messages.error(request, 'Unit lingkup hak akses Human Capital tidak valid.')
            return 0, 0

    aktifkan_role_untuk(target_user, selected)
    return sinkronkan_grant(
        target_user,
        capabilities=selected,
        unit=unit,
        include_descendants=request.POST.get('hc_include_descendants') == 'on',
        valid_until=None,
        actor=request.user,
    )


@login_required
@user_passes_test(admin_only)
def user_create(request):
    if request.method == 'POST':
        user_form = UserCreateForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
            target_role = profile_form.cleaned_data.get('role')
            if not _can_assign_role(request.user, target_role):
                messages.error(
                    request,
                    f"Anda tidak berwenang menetapkan peran '{dict(UserProfile.ROLE_CHOICES).get(target_role, target_role)}'."
                )
                return redirect('accounts:user_list')

            with transaction.atomic():
                user = user_form.save()
                profile = profile_form.save(commit=False)
                profile.user = user
                profile.save()
                profile_form.save_m2m()

                if profile.role == 'SUPER_ADMIN':
                    user.is_staff = True
                    user.is_superuser = True
                    user.save()
                elif profile.role == 'ADMIN_RS':
                    user.is_staff = True
                    user.save()

                hc_added, hc_removed = _simpan_grant_dari_form(request, user)

                AuditLog.objects.create(
                    user=request.user,
                    aksi='CREATE',
                    model_name='User',
                    object_repr=f"{user.username} [{profile.role}]",
                    detail=f"Pengguna baru dibuat: {profile.full_name or user.username} ({profile.get_role_display()}); grant HC +{hc_added}"
                )

                messages.success(request, f"Pengguna '{user.username}' berhasil ditambahkan!")
                return redirect('accounts:user_list')
    else:
        user_form = UserCreateForm()
        profile_form = UserProfileForm(initial={'role': 'KEPALA_UNIT'})

    return render(request, 'accounts/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'title': 'Tambah Pengguna Baru',
        **_hc_context(),
    })


@login_required
@user_passes_test(admin_only)
def user_edit(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=target_user,
        defaults={'role': 'SUPER_ADMIN' if target_user.is_superuser else 'ASESOR'}
    )

    if not _can_modify_account(request.user, target_user):
        messages.error(request, "Anda tidak berwenang mengubah akun dengan peran setara atau lebih tinggi.")
        return redirect('accounts:user_list')

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=target_user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
            new_role = profile_form.cleaned_data.get('role')
            if not _can_assign_role(request.user, new_role):
                messages.error(
                    request,
                    f"Anda tidak berwenang menetapkan peran '{dict(UserProfile.ROLE_CHOICES).get(new_role, new_role)}'."
                )
                return redirect('accounts:user_list')

            new_is_active = user_form.cleaned_data.get('is_active')
            if _is_last_active_superuser(target_user):
                if not new_is_active or new_role != 'SUPER_ADMIN':
                    messages.error(request, "Super Admin aktif terakhir tidak dapat dinonaktifkan atau diturunkan perannya.")
                    return redirect('accounts:user_list')

            with transaction.atomic():
                user_form.save()
                profile = profile_form.save()

                if profile.role == 'SUPER_ADMIN':
                    target_user.is_staff = True
                    target_user.is_superuser = True
                    target_user.save()
                elif profile.role == 'ADMIN_RS':
                    target_user.is_staff = True
                    target_user.is_superuser = False
                    target_user.save()
                else:
                    target_user.is_superuser = False
                    target_user.save()

                hc_added, hc_removed = _simpan_grant_dari_form(request, target_user)

                AuditLog.objects.create(
                    user=request.user,
                    aksi='UPDATE',
                    model_name='User',
                    object_repr=f"{target_user.username} [{profile.role}]",
                    detail=f"Profil pengguna diperbarui: {profile.get_role_display()}; grant HC +{hc_added} -{hc_removed}"
                )

                messages.success(request, f"Data pengguna '{target_user.username}' berhasil diperbarui!")
                return redirect('accounts:user_list')
    else:
        user_form = UserEditForm(instance=target_user)
        profile_form = UserProfileForm(instance=profile)

    return render(request, 'accounts/user_form.html', {
        'user_form': user_form,
        'profile_form': profile_form,
        'target_user': target_user,
        'title': f'Edit Pengguna: {target_user.username}',
        **_hc_context(target_user),
    })


@login_required
@user_passes_test(admin_only)
@require_POST
def user_delete(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "Anda tidak dapat menghapus akun Anda sendiri!")
        return redirect('accounts:user_list')

    if not _can_modify_account(request.user, target_user):
        messages.error(request, "Akun dengan peran setara atau lebih tinggi tidak dapat dihapus.")
        return redirect('accounts:user_list')

    if _is_last_active_superuser(target_user):
        messages.error(request, "Super Admin aktif terakhir tidak dapat dihapus.")
        return redirect('accounts:user_list')

    username = target_user.username
    target_user.delete()

    AuditLog.objects.create(
        user=request.user,
        aksi='DELETE',
        model_name='User',
        object_repr=username,
        detail="Pengguna dihapus dari sistem"
    )
    messages.success(request, f"Pengguna '{username}' telah dihapus.")
    return redirect('accounts:user_list')


# ============================================================================
# PUSAT KONTROL ADMIN
# ============================================================================

def control_center_access(user):
    """Cek apakah user boleh mengakses Pusat Kontrol Admin."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return profile and profile.has_permission('can_access_control_center')


@login_required
@user_passes_test(control_center_access)
def admin_control_center(request):
    from akreditasi.models import UnitKerja
    from akreditasi.system_models import SystemConfig
    from .models import RolePermissionConfig, PERMISSION_DEFAULTS, HC_PERMISSION_LABELS

    sys_config = SystemConfig.get_solo()
    profile = request.user.profile

    # Tab permission: apakah user boleh akses tab Konfigurasi Sistem (ambang batas, tema, freeze)?
    can_manage_system = profile.has_permission('can_manage_system_settings')

    # Ambil semua unit kerja
    all_units = UnitKerja.objects.all().select_related('parent').order_by('level', 'order', 'code')
    root_units = UnitKerja.objects.filter(parent__isnull=True).prefetch_related('children__children').order_by('order', 'code')

    # Ambil konfigurasi izin per role
    role_configs = []
    for role_code, role_label in UserProfile.ROLE_CHOICES:
        cfg = RolePermissionConfig.get_config_for_role(role_code)
        role_configs.append({
            'role_code': role_code,
            'role_label': role_label,
            'config': cfg,
            'is_lockout_safe': role_code == 'SUPER_ADMIN',
        })

    # Field izin untuk template grid
    perm_fields = [
        ('can_view_pdca', 'Lihat PDCA'),
        ('can_edit_pdca', 'Edit PDCA'),
        ('can_score_ep', 'Skor EP'),
        ('can_view_rdwos', 'Akses RDWOS'),
        ('can_upload_rdwos', 'Unggah Bukti'),
        ('can_delete_rdwos', 'Hapus Bukti'),
        ('can_view_risiko', 'Lihat Risiko'),
        ('can_manage_risiko', 'Kelola Risiko'),
        ('can_lapor_insiden', 'Lapor Insiden'),
        ('can_investigate_insiden', 'Investigasi'),
        ('can_view_scoring', 'Lihat Scoring'),
        ('can_export_reports', 'Ekspor/Cetak'),
        ('can_manage_units', 'Kelola Unit'),
        ('can_manage_users', 'Kelola User'),
        ('can_verify_kps', 'Verifikasi KPS'),
        ('can_view_audit_log', 'Audit Log'),
        ('can_access_control_center', 'Pusat Kontrol'),
        ('can_manage_system_settings', 'Konfigurasi Sistem'),
    ]
    perm_fields.extend(HC_PERMISSION_LABELS)

    # Ambil semua user dengan profile
    all_users = User.objects.select_related('profile__unit_kerja').prefetch_related('profile__pokja_access').order_by('profile__role', 'username')

    return render(request, 'accounts/admin_control_center.html', {
        'sys_config': sys_config,
        'config': sys_config,
        'can_manage_system': can_manage_system,
        'all_units': all_units,
        'root_units': root_units,
        'role_configs': role_configs,
        'perm_fields': perm_fields,
        'all_users': all_users,
    })


@login_required
@user_passes_test(control_center_access)
@require_POST
def update_unit_hierarchy(request, unit_id):
    from akreditasi.models import UnitKerja
    import json

    unit = get_object_or_404(UnitKerja, id=unit_id)
    parent_id = request.POST.get('parent_id', '').strip()
    order_val = request.POST.get('order', '0')
    tipe_unit = request.POST.get('tipe_unit', unit.tipe_unit)
    is_active = request.POST.get('is_active', 'true')

    # Reparenting
    new_parent = None
    if parent_id and parent_id != '' and parent_id != '0':
        parent_pk = parse_int(parent_id)
        if parent_pk is None:
            from django.http import JsonResponse
            return JsonResponse({'error': 'ID induk unit tidak valid.'}, status=400)
        new_parent = get_object_or_404(UnitKerja, id=parent_pk)
        # Anti-circular: cek apakah new_parent adalah descendant dari unit ini
        curr = new_parent
        while curr:
            if curr.id == unit.id:
                from django.http import JsonResponse
                return JsonResponse({'error': 'Tidak bisa menjadikan sub-unit sebagai induk dari unit ini (circular dependency).'}, status=400)
            curr = curr.parent

    with transaction.atomic():
        unit.parent = new_parent
        unit.order = parse_int(order_val, 0)
        unit.tipe_unit = tipe_unit
        unit.is_active = is_active.lower() in ('true', '1', 'on', 'yes')
        unit.save()

        AuditLog.objects.create(
            user=request.user,
            aksi='UPDATE',
            model_name='UnitKerja',
            object_repr=f"[{unit.code}] {unit.name}",
            detail=f"Hierarki diubah: parent={new_parent}, order={unit.order}, tipe={unit.tipe_unit}, aktif={unit.is_active}"
        )

    from django.http import JsonResponse
    return JsonResponse({'success': True, 'unit_id': unit.id, 'level': unit.level})


@login_required
@user_passes_test(control_center_access)
@require_POST
def update_role_permissions(request):
    from .models import RolePermissionConfig, LOCKOUT_SAFE_PERMS

    data = json_body(request)
    if data is None:
        # Form-encoded fallback: satu role = satu dict; nilai lain (mis. body
        # teks mentah) bukan payload matriks izin dan harus ditolak, bukan 500.
        data = {}
        for role_code, _ in UserProfile.ROLE_CHOICES:
            fields = {
                key.split('.', 1)[1]: value
                for key, value in request.POST.items()
                if key.startswith(f'{role_code}.')
            }
            if fields:
                data[role_code] = fields
        if not data:
            from django.http import JsonResponse
            return JsonResponse(
                {'success': False, 'error': 'Payload matriks izin tidak valid.'},
                status=400,
            )

    changes = []
    for role_code, _ in UserProfile.ROLE_CHOICES:
        role_data = data.get(role_code, {})
        if not role_data:
            continue
        cfg = RolePermissionConfig.get_config_for_role(role_code)
        for perm_field, value in role_data.items():
            # Super Admin lockout protection
            if role_code == 'SUPER_ADMIN' and perm_field in LOCKOUT_SAFE_PERMS:
                continue  # Tidak boleh diubah
            # Invarian global: non-super admin tidak boleh mengubah LOCKOUT_SAFE_PERMS untuk peran mana pun
            if perm_field in LOCKOUT_SAFE_PERMS and not _is_super_admin(request.user):
                continue
            if hasattr(cfg, perm_field):
                setattr(cfg, perm_field, bool(value))
        cfg.save()
        changes.append(role_code)

    if changes:
        AuditLog.objects.create(
            user=request.user,
            aksi='UPDATE',
            model_name='RolePermissionConfig',
            object_repr=f"Matriks Izin: {', '.join(changes)}",
            detail=f"Matriks hak akses peran diperbarui oleh {request.user.username}"
        )

    from django.http import JsonResponse
    return JsonResponse({'success': True, 'updated_roles': changes})


@login_required
@user_passes_test(control_center_access)
@require_POST
def reset_role_permissions(request):
    from .models import RolePermissionConfig
    RolePermissionConfig.reset_to_defaults()

    AuditLog.objects.create(
        user=request.user,
        aksi='UPDATE',
        model_name='RolePermissionConfig',
        object_repr='Reset ke Default KARS',
        detail=f"Seluruh matriks hak akses direset ke standar KARS oleh {request.user.username}"
    )

    messages.success(request, "Matriks hak akses seluruh peran telah direset ke standar KARS bawaan.")
    return redirect('accounts:admin_control_center')


@login_required
@user_passes_test(control_center_access)
@require_POST
def update_user_custom_permissions(request, user_id):
    import json
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=target_user,
        defaults={'role': 'ASESOR'}
    )

    data = json_body(request)
    if data is None:
        custom_perms = {
            key.split('custom_permissions.', 1)[1] if key.startswith('custom_permissions.') else key: value
            for key, value in request.POST.items()
            if key.startswith('custom_permissions.')
        }
        if custom_perms:
            data = {'custom_permissions': custom_perms}
        else:
            return JsonResponse(
                {'success': False, 'error': 'Payload hak akses tidak valid.'},
                status=400,
            )

    custom_perms = data.get('custom_permissions', {})
    if not isinstance(custom_perms, dict):
        return JsonResponse(
            {'success': False, 'error': 'custom_permissions harus berupa objek.'},
            status=400,
        )

    # 1. Validasi whitelist kunci izin
    for key in custom_perms:
        if not isinstance(key, str) or key not in VALID_PERMISSION_KEYS:
            return JsonResponse(
                {'success': False, 'error': f"Kunci izin tidak dikenal: {key}."},
                status=400,
            )

    # 2. Pemisahan tugas: tidak boleh mengubah hak akses akun sendiri
    if target_user == request.user:
        return JsonResponse(
            {'success': False, 'error': "Anda tidak dapat mengubah hak akses akun Anda sendiri."},
            status=400,
        )

    # 3. Otorisasi pemanggil: harus memiliki wewenang mengelola pengguna / izin
    caller_profile = getattr(request.user, 'profile', None)
    has_manage_users = _is_super_admin(request.user) or (
        caller_profile and caller_profile.has_permission('can_manage_users')
    )
    if not has_manage_users:
        return JsonResponse(
            {'success': False, 'error': "Anda tidak memiliki wewenang untuk mengelola hak akses pengguna."},
            status=400,
        )

    # 4. Hierarki: tidak boleh mengubah izin akun dengan peran setara atau lebih tinggi
    if not _can_modify_account(request.user, target_user):
        return JsonResponse(
            {'success': False, 'error': "Anda tidak berwenang mengubah izin akun dengan peran setara atau lebih tinggi."},
            status=400,
        )

    # 5. Non-superuser tidak dapat memberikan izin yang tidak mereka miliki sendiri
    if not _is_super_admin(request.user):
        for perm_key, val in custom_perms.items():
            if bool(val) and not (caller_profile and caller_profile.has_permission(perm_key)):
                return JsonResponse(
                    {'success': False, 'error': f"Anda tidak dapat memberikan izin yang tidak Anda miliki: {perm_key}."},
                    status=400,
                )

    cleaned_custom_perms = {k: bool(v) for k, v in custom_perms.items()}
    profile.custom_permissions = cleaned_custom_perms
    profile.save(update_fields=['custom_permissions', 'updated_at'])

    AuditLog.objects.create(
        user=request.user,
        aksi='UPDATE',
        model_name='UserProfile',
        object_repr=f"{target_user.username} [{profile.role}]",
        detail=f"Hak akses kustom diperbarui: {json.dumps(cleaned_custom_perms)}"
    )

    return JsonResponse({'success': True, 'user_id': target_user.id})


@login_required
@user_passes_test(control_center_access)
@require_POST
def update_system_config(request):
    """Update ambang batas, KPS, RDWOS, risiko, tema, kop surat."""
    profile = request.user.profile
    if not profile.has_permission('can_manage_system_settings'):
        from django.http import JsonResponse
        return JsonResponse({'error': 'Anda tidak memiliki izin untuk mengubah konfigurasi sistem.'}, status=403)

    from akreditasi.system_models import SystemConfig
    cfg = SystemConfig.get_solo()

    int_fields = [
        'threshold_paripurna', 'threshold_utama', 'threshold_madya', 'threshold_dasar',
        'kps_alert_days', 'max_upload_size_mb',
        'risk_threshold_sangat_tinggi', 'risk_threshold_tinggi', 'risk_threshold_sedang', 'risk_threshold_rendah',
        'ai_max_tokens',
    ]
    str_fields = ['allowed_extensions', 'theme_color', 'kop_surat_text', 'survey_freeze_message',
                  'ai_model_name']
    bool_fields = ['allow_nakes_self_upload', 'ai_enabled',
                   'ai_enable_risiko', 'ai_enable_pdca', 'ai_enable_insiden',
                   'ai_enable_rdwos', 'ai_enable_kps', 'ai_enable_laporan']
    float_fields = ['ai_temperature']

    # API Key: hanya simpan jika user kirim nilai baru (tidak kosong)
    new_api_key = request.POST.get('ai_api_key', '').strip()
    if new_api_key:
        cfg.ai_api_key = new_api_key

    for f in int_fields:
        val = request.POST.get(f)
        if val is not None and val.strip().isdigit():
            setattr(cfg, f, int(val))
    for f in str_fields:
        val = request.POST.get(f)
        if val is not None:
            setattr(cfg, f, val.strip())
    for f in bool_fields:
        val = request.POST.get(f, 'false')
        setattr(cfg, f, val.lower() in ('true', '1', 'on', 'yes'))
    for f in float_fields:
        val = request.POST.get(f)
        if val is not None:
            try:
                setattr(cfg, f, float(val))
            except ValueError:
                pass

    cfg.save()

    AuditLog.objects.create(
        user=request.user,
        aksi='UPDATE',
        model_name='SystemConfig',
        object_repr='Konfigurasi Sistem',
        detail=f"Konfigurasi sistem diperbarui oleh {request.user.username}"
    )

    messages.success(request, "Konfigurasi sistem berhasil disimpan.")
    return redirect('accounts:admin_control_center')


@login_required
@user_passes_test(control_center_access)
@require_POST
def toggle_survey_freeze(request):
    """Toggle Mode Kunci Survei."""
    profile = request.user.profile
    if not profile.has_permission('can_manage_system_settings'):
        from django.http import JsonResponse
        return JsonResponse({'error': 'Anda tidak memiliki izin untuk mengubah Mode Survei.'}, status=403)

    from akreditasi.system_models import SystemConfig
    cfg = SystemConfig.get_solo()
    cfg.survey_freeze_mode = not cfg.survey_freeze_mode
    cfg.save()

    status_str = 'AKTIF (Read-Only)' if cfg.survey_freeze_mode else 'NONAKTIF'
    AuditLog.objects.create(
        user=request.user,
        aksi='UPDATE',
        model_name='SystemConfig',
        object_repr=f"Mode Survei: {status_str}",
        detail=f"Mode Kunci Survei diubah ke {status_str} oleh {request.user.username}"
    )

    messages.success(request, f"Mode Kunci Survei sekarang {status_str}.")
    return redirect('accounts:admin_control_center')
