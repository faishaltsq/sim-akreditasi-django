from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db import transaction
from django.db.models import Q

from .models import UserProfile
from .forms import UserCreateForm, UserEditForm, UserProfileForm
from akreditasi.models import AuditLog


def admin_only(user):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return profile and profile.can_manage_users


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


@login_required
@user_passes_test(admin_only)
def user_create(request):
    if request.method == 'POST':
        user_form = UserCreateForm(request.POST)
        profile_form = UserProfileForm(request.POST)
        if user_form.is_valid() and profile_form.is_valid():
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

                AuditLog.objects.create(
                    user=request.user,
                    aksi='CREATE',
                    model_name='User',
                    object_repr=f"{user.username} [{profile.role}]",
                    detail=f"Pengguna baru dibuat: {profile.full_name or user.username} ({profile.get_role_display()})"
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
    })


@login_required
@user_passes_test(admin_only)
def user_edit(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=target_user,
        defaults={'role': 'SUPER_ADMIN' if target_user.is_superuser else 'ASESOR'}
    )

    if request.method == 'POST':
        user_form = UserEditForm(request.POST, instance=target_user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        if user_form.is_valid() and profile_form.is_valid():
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

                AuditLog.objects.create(
                    user=request.user,
                    aksi='UPDATE',
                    model_name='User',
                    object_repr=f"{target_user.username} [{profile.role}]",
                    detail=f"Profil pengguna diperbarui: {profile.get_role_display()}"
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
    })


@login_required
@user_passes_test(admin_only)
@require_POST
def user_delete(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    if target_user == request.user:
        messages.error(request, "Anda tidak dapat menghapus akun Anda sendiri!")
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
