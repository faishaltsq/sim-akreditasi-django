from django.urls import path

from sdm import rekrutmen_laporan_views as views

app_name = 'rekrutmen_laporan'
urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('rekap.pdf', views.dashboard_export, name='dashboard_export'),
    path('lamaran/<uuid:application_id>/bukti.zip', views.bukti_audit, name='bukti_audit'),
]
