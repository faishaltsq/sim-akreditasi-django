from django.urls import path

from sdm import activation_views

urlpatterns = [
    path(
        'lamaran/<uuid:application_id>/aktivasi/',
        activation_views.invite_hired_account,
        name='hired_account_invite',
    ),
]
