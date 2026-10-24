"""Account invitation service contracts (Task B6)."""

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
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

# Role codes an HC employee operator may NOT delegate (privilege escalation guard).
FORBIDDEN_INTENDED_ROLES = {'SUPER_ADMIN', 'ADMIN_RS', 'DIREKTUR', 'KOORDINATOR_POKJA'}


def invite_staff_account(*, actor, employee, email, role, idempotency_key):
    """Create/reuse a single-use activation invitation. Does not send password."""
    require_hc_capability(actor, 'can_view_hc')
    require_hc_capability(actor, 'can_manage_hc_employees', employee=employee)

    User = get_user_model()
    email = (email or '').strip().lower()
    if not email:
        raise ValidationError({'email': 'Email wajib diisi.'})

    if role in FORBIDDEN_INTENDED_ROLES:
        raise PermissionDenied(f'Peran {role} tidak dapat ditetapkan melalui undangan intake.')

    # Reuse an unexpired SENT invitation for the same employee+email (idempotent).
    existing = (
        UndanganAkunPegawai.objects.filter(employee=employee, email=email, state='SENT')
        .order_by('-created_at')
        .first()
    )
    if existing and existing.is_active:
        return existing

    # Revoke any prior SENT invitation for same employee+email.
    UndanganAkunPegawai.objects.filter(
        employee=employee, email=email, state='SENT'
    ).update(state='REVOKED', revoked_at=timezone.now())

    token = secrets.token_urlsafe(32)
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    expiry = timezone.now() + timedelta(hours=72)

    invitation = UndanganAkunPegawai.objects.create(
        employee=employee,
        email=email,
        intended_role=role,
        token_digest=token_digest,
        expiry=expiry,
        state='SENT',
        created_by=actor,
    )
    invitation.raw_token = token  # transient, used by caller to complete activation

    # Deliver after commit; failure leaves invitation in FAILED state for resend.
    try:
        _send_invitation_email(invitation, token, actor)
        invitation.state = 'SENT'
        invitation.sent_at = timezone.now()
        invitation.save(update_fields=['state', 'sent_at', 'updated_at'])
    except Exception as exc:  # pragma: no cover - mail backend dependent
        invitation.state = 'FAILED'
        invitation.last_error = str(exc)[:500]
        invitation.save(update_fields=['state', 'last_error', 'updated_at'])
        raise

    PeristiwaSDM.objects.create(
        actor=actor,
        jenis_peristiwa='account_invitation_sent',
        target_tipe='employee',
        target_id=str(employee.pk),
        alasan=f'email={email}; role={role}',
    )
    return invitation


def accept_staff_invitation(*, token, password):
    """Activate account from a single-use, unexpired invitation."""
    User = get_user_model()
    token_digest = hashlib.sha256(token.encode()).hexdigest()

    try:
        invitation = UndanganAkunPegawai.objects.select_related('employee').get(
            token_digest=token_digest, state='SENT'
        )
    except UndanganAkunPegawai.DoesNotExist:
        raise ValidationError({'token': 'Token undangan tidak valid atau sudah digunakan.'})

    if not invitation.is_active:
        invitation.state = 'EXPIRED'
        invitation.save(update_fields=['state', 'updated_at'])
        raise ValidationError({'token': 'Undangan telah kadaluarsa.'})

    invitation.attempt_count = F('attempt_count') + 1
    invitation.save(update_fields=['attempt_count'])

    # Django password validation.
    from django.contrib.auth.password_validation import validate_password
    try:
        validate_password(password)
    except ValidationError as exc:
        invitation.save(update_fields=['attempt_count', 'updated_at'])
        raise ValidationError({'password': list(exc.messages)})

    email = invitation.email
    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({'email': 'Email sudah terdaftar.'})

    with transaction.atomic():
        invitation.refresh_from_db()
        if invitation.state != 'SENT' or not invitation.is_active:
            raise ValidationError({'token': 'Undangan telah kadaluarsa atau digunakan.'})

        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            is_active=True,
        )
        from accounts.models import UserProfile
        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={
                'role': invitation.intended_role or 'STAF_NAKES',
            },
        )
        if invitation.intended_role:
            profile.role = invitation.intended_role
            profile.save(update_fields=['role', 'updated_at'])

        employee = invitation.employee
        if not employee.akun_id:
            employee.akun = user
            employee.save(update_fields=['akun', 'updated_at'])

        invitation.state = 'ACCEPTED'
        invitation.accepted_at = timezone.now()
        invitation.save(update_fields=['state', 'accepted_at', 'updated_at'])

    return user


def _send_invitation_email(invitation, token, actor):
    context = {
        'employee': invitation.employee,
        'email': invitation.email,
        'token': token,
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
