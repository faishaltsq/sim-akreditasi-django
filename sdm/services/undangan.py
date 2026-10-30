"""Account invitation service contracts (Task B6)."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import F, Q
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from sdm.akses import require_hc_capability
from sdm.models import Pegawai, PeristiwaSDM, UndanganAkunPegawai

# Roles an HC employee operator may delegate through intake. An allowlist is
# required: a new privileged role added to UserProfile must not become
# delegable by omission from a denylist.
DELEGABLE_INTENDED_ROLES = frozenset({'STAF_NAKES', 'ASESOR'})


def invite_staff_account(
    *, actor, employee, email, role, idempotency_key, intended_is_active=True
):
    """Create/reuse a single-use activation invitation. Does not send password."""
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees', employee=employee)

    email = (email or '').strip().lower()
    if not email:
        raise ValidationError({'email': 'Email wajib diisi.'})

    if role not in DELEGABLE_INTENDED_ROLES:
        raise PermissionDenied(
            'Peran tidak dapat ditetapkan melalui undangan intake.'
        )

    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    expiry = timezone.now() + timedelta(hours=72)

    with transaction.atomic():
        locked_employee = Pegawai.objects.select_for_update().get(pk=employee.pk)
        require_hc_capability(
            actor, 'can_manage_hc_employees', employee=locked_employee
        )

        if idempotency_key:
            recorded = UndanganAkunPegawai.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if recorded is not None:
                same_request = (
                    recorded.employee_id == locked_employee.pk
                    and recorded.email == email
                    and recorded.intended_role == role
                    and recorded.intended_is_active == bool(intended_is_active)
                )
                if not same_request:
                    raise ValidationError({
                        'idempotency': (
                            'Kunci idempotensi sudah dipakai untuk undangan lain.'
                        )
                    })
                return recorded

        existing = (
            UndanganAkunPegawai.objects.filter(
                employee=locked_employee, email=email, state='SENT'
            )
            .order_by('-created_at')
            .first()
        )
        if (
            existing and existing.is_active
            and existing.intended_role == role
            and existing.intended_is_active == bool(intended_is_active)
        ):
            return existing

        UndanganAkunPegawai.objects.filter(
            employee=locked_employee, email=email, state='SENT'
        ).update(state='REVOKED', revoked_at=timezone.now())

        defaults = {
            'employee': locked_employee,
            'email': email,
            'intended_role': role,
            'intended_is_active': bool(intended_is_active),
            'token_digest': token_digest,
            'expiry': expiry,
            'state': 'SENT',
            'created_by': actor,
        }
        if idempotency_key:
            invitation, created = UndanganAkunPegawai.objects.get_or_create(
                idempotency_key=idempotency_key, defaults=defaults
            )
            if not created:
                same_request = (
                    invitation.employee_id == locked_employee.pk
                    and invitation.email == email
                    and invitation.intended_role == role
                    and invitation.intended_is_active == bool(intended_is_active)
                )
                if not same_request:
                    raise ValidationError({
                        'idempotency': (
                            'Kunci idempotensi sudah dipakai untuk undangan lain.'
                        )
                    })
                return invitation
        else:
            invitation = UndanganAkunPegawai.objects.create(**defaults)

        invitation.raw_token = token

        def _deliver(invitation_pk=invitation.pk, raw=token, acting=actor):
            pending = UndanganAkunPegawai.objects.get(pk=invitation_pk)
            try:
                _send_invitation_email(pending, raw, acting)
            except Exception as exc:
                pending.state = 'FAILED'
                pending.last_error = str(exc)[:500]
                pending.failed_at = timezone.now()
                pending.save(update_fields=[
                    'state', 'last_error', 'failed_at', 'updated_at',
                ])
                return
            pending.sent_at = timezone.now()
            pending.save(update_fields=['sent_at', 'updated_at'])
            PeristiwaSDM.objects.create(
                actor=acting,
                jenis_peristiwa='account_invitation_sent',
                target_tipe='employee',
                target_id=str(pending.employee_id),
                alasan=(
                    f'role={pending.intended_role}; '
                    f'active={pending.intended_is_active}'
                ),
            )

        transaction.on_commit(_deliver)

    return invitation


def accept_staff_invitation(*, token, password):
    """Activate an account from a single-use, unexpired invitation."""
    digest = hashlib.sha256((token or '').encode()).hexdigest()
    error = None
    accepted_user = None
    User = get_user_model()
    from accounts.models import UserProfile

    with transaction.atomic():
        invitation = (
            UndanganAkunPegawai.objects.select_for_update()
            .select_related('employee')
            .filter(token_digest=digest)
            .first()
        )
        if invitation is None or invitation.state != 'SENT':
            error = 'Tautan aktivasi tidak valid atau sudah digunakan.'
        elif timezone.now() >= invitation.expiry:
            invitation.state = 'EXPIRED'
            invitation.save(update_fields=['state', 'updated_at'])
            error = 'Tautan aktivasi tidak valid atau sudah digunakan.'
        else:
            employee = Pegawai.objects.select_for_update().get(
                pk=invitation.employee_id
            )
            canonical_email = User.objects.normalize_email(invitation.email)
            user = (
                User.objects.select_for_update().get(pk=employee.akun_id)
                if employee.akun_id else None
            )
            collisions = User.objects.filter(
                Q(username__iexact=canonical_email)
                | Q(email__iexact=canonical_email)
            )
            if user:
                collisions = collisions.exclude(pk=user.pk)
            if collisions.exists() or (
                user and (
                    user.email.strip().lower() != canonical_email.lower()
                    or user.has_usable_password()
                    or user.is_staff or user.is_superuser
                    or user.groups.exists() or user.user_permissions.exists()
                    or UserProfile.objects.filter(user=user).exists()
                )
            ):
                error = 'Tautan aktivasi tidak valid atau sudah digunakan.'
            else:
                candidate = user or User(username=canonical_email, email=canonical_email)
                validate_password(password, user=candidate)
                if user:
                    user.set_password(password)
                    user.is_active = invitation.intended_is_active
                    user.save(update_fields=['password', 'is_active'])
                else:
                    user = User.objects.create_user(
                        username=canonical_email,
                        email=canonical_email,
                        password=password,
                        is_active=invitation.intended_is_active,
                    )
                    employee.akun = user
                    employee.save(update_fields=['akun', 'updated_at'])
                UserProfile.objects.create(
                    user=user,
                    role=invitation.intended_role,
                    unit_kerja=_primary_unit(employee),
                )
                invitation.state = 'ACCEPTED'
                invitation.accepted_at = timezone.now()
                invitation.attempt_count = F('attempt_count') + 1
                invitation.save(update_fields=[
                    'state', 'accepted_at', 'attempt_count', 'updated_at',
                ])
                PeristiwaSDM.objects.create(
                    actor=user,
                    jenis_peristiwa='account_invitation_accepted',
                    target_tipe='employee',
                    target_id=str(employee.pk),
                    alasan=(
                        f'role={invitation.intended_role}; '
                        f'active={invitation.intended_is_active}'
                    ),
                )
                accepted_user = user

    if error:
        raise ValidationError(error)
    return accepted_user


def _primary_unit(employee):
    """Return the employee's current placement unit, or None when unplaced."""
    today = timezone.localdate()
    placement = (
        employee.penempatan.filter(tanggal_mulai__lte=today)
        .filter(Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today))
        .select_related('unit_kerja')
        .order_by('-tanggal_mulai', '-pk')
        .first()
    )
    return placement.unit_kerja if placement else None


def _send_invitation_email(invitation, token, actor):
    from django.core.exceptions import ImproperlyConfigured
    from django.urls import reverse

    base = (getattr(settings, 'PUBLIC_BASE_URL', '') or '').rstrip('/')
    if not base:
        raise ImproperlyConfigured(
            'PUBLIC_BASE_URL wajib diisi sebelum undangan akun dikirim.'
        )
    activation_url = base + reverse(
        'accounts:staff_activate', kwargs={'token': token}
    )
    context = {
        'employee': invitation.employee,
        'email': invitation.email,
        'token': token,
        'activation_url': activation_url,
        'actor': actor,
        'site_name': getattr(settings, 'SITE_NAME', 'ARIMA'),
        'expiry_hours': 72,
    }
    subject = render_to_string('accounts/email/invitation_subject.txt', context).strip()
    body = render_to_string('accounts/email/invitation_body.txt', context)
    send_mail(
        subject,
        body,
        getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@arima.local'),
        [invitation.email],
        fail_silently=False,
    )
