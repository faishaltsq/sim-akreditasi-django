from django.urls import path
from . import views

app_name = 'pasien'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('daftar/', views.pasien_daftar, name='pasien_daftar'),
    path('baru/', views.pasien_daftar_baru, name='pasien_baru'),
    path('<int:pk>/', views.pasien_detail, name='pasien_detail'),
    path('kunjungan/', views.kunjungan_daftar, name='kunjungan_daftar'),
    path('kunjungan/baru/', views.kunjungan_baru, name='kunjungan_baru'),
    path('kunjungan/<int:pk>/', views.kunjungan_detail, name='kunjungan_detail'),
    path('kunjungan/<int:kunjungan_pk>/cppt/', views.cppt_tambah, name='cppt_tambah'),
    path('kunjungan/<int:kunjungan_pk>/billing/', views.billing_tambah, name='billing_tambah'),
    path('kunjungan/<int:kunjungan_pk>/discharge/', views.discharge_proses, name='discharge_proses'),
    path('kunjungan/<int:kunjungan_pk>/discharge-planning/', views.discharge_planning_set, name='discharge_planning_set'),
    path('kunjungan/<int:kunjungan_pk>/resume-pdf/', views.resume_pdf, name='resume_pdf'),
    path('api/icd10/', views.api_icd10, name='api_icd10'),
    path('api/parse-qr/', views.api_parse_qr, name='api_parse_qr'),
    path('kunjungan/<int:kunjungan_pk>/resep/buat/', views.resep_buat, name='resep_buat'),
    path('kunjungan/<int:kunjungan_pk>/satusehat-sync/', views.satusehat_sync_view, name='satusehat_sync'),
    path('resep/<int:resep_pk>/proses/', views.resep_update_status, name='resep_update_status'),
    path('farmasi/', views.farmasi_antrean, name='farmasi_antrean'),
    path('bed-management/', views.bed_management, name='bed_management'),
]
