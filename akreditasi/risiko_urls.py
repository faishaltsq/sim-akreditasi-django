from django.urls import path
from . import risiko_views

urlpatterns = [
    path('risiko/', risiko_views.risiko_daftar, name='risiko_daftar'),
    path('risiko/baru/', risiko_views.risiko_input, name='risiko_input'),
    path('risiko/<int:risiko_id>/', risiko_views.risiko_detail, name='risiko_detail'),
    path('risiko/<int:risiko_id>/evaluasi/', risiko_views.risiko_evaluasi, name='risiko_evaluasi'),
    path('insiden/lapor/', risiko_views.insiden_lapor, name='insiden_lapor'),
]
