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
    # ── Clinical Workflow Dashboards ──
    path('pendaftaran/', views.pendaftaran_dashboard, name='pendaftaran_dashboard'),
    path('pendaftaran/<int:pk>/route/', views.pendaftaran_route, name='pendaftaran_route'),
    path('igd/', views.igd_dashboard, name='igd_dashboard'),
    path('igd/kunjungan/<int:pk>/ttv/', views.igd_ttv_update, name='igd_ttv_update'),
    path('rajal/', views.rajal_dashboard, name='rajal_dashboard'),
    path('rajal/kunjungan/<int:pk>/antrean/', views.rajal_antrean_status, name='rajal_antrean_status'),
    path('rajal/kunjungan/<int:pk>/soap/', views.rajal_soap_simpan, name='rajal_soap_simpan'),
    path('kunjungan/<int:pk>/disposisi/', views.kunjungan_disposisi, name='kunjungan_disposisi'),
    path('kunjungan/<int:pk>/order-penunjang/', views.order_penunjang_buat, name='order_penunjang_buat'),
    # ── Bed Reservation & Room Booking ──
    path('kunjungan/<int:kunjungan_id>/booking-kamar/', views.booking_kamar_buat, name='booking_kamar_buat'),
    path('booking-kamar/<int:booking_id>/batal/', views.booking_kamar_batal, name='booking_kamar_batal'),
    path('booking-kamar/<int:booking_id>/checkin/', views.booking_kamar_checkin, name='booking_kamar_checkin'),
    path('api/bed-tersedia/', views.api_bed_tersedia, name='api_bed_tersedia'),
    # ── General Consent Rawat Inap ──
    path('kunjungan/<int:kunjungan_id>/general-consent/', views.general_consent_simpan, name='general_consent_simpan'),
    path('kunjungan/<int:pk>/cetak-general-consent/', views.cetak_general_consent, name='cetak_general_consent'),
    # ── Print / Cetak Views ──
    path('api/cek-nik/', views.api_cek_nik, name='api_cek_nik'),
    path('kunjungan/<int:pk>/cetak-gelang/', views.cetak_gelang, name='cetak_gelang'),
    path('kunjungan/<int:pk>/cetak-sep/', views.cetak_sep, name='cetak_sep'),
    path('kunjungan/<int:pk>/cetak-spri/', views.cetak_spri, name='cetak_spri'),
    path('kunjungan/<int:pk>/cetak-skdp/', views.cetak_skdp, name='cetak_skdp'),
    path('kunjungan/<int:pk>/cetak-tracer/', views.cetak_tracer, name='cetak_tracer'),
    # ── Registration & Admission Utilities ──
    path('fast-track-igd/', views.fast_track_igd, name='fast_track_igd'),
    path('api/cek-bpjs/', views.api_cek_bpjs, name='api_cek_bpjs'),
    path('kunjungan/<int:pk>/batal/', views.kunjungan_batal, name='kunjungan_batal'),
    # ── Laboratorium & LIS ──
    path('laboratorium/', views.laboratorium_dashboard, name='laboratorium_dashboard'),
    path('order-penunjang/<int:pk>/update/', views.order_penunjang_update, name='order_penunjang_update'),
    # ── IGD Clinical Assessment (Revisi 02) ──
    path('kunjungan/<int:pk>/asesmen-awal-igd/', views.igd_asesmen_awal_save, name='igd_asesmen_awal_save'),
    path('kunjungan/<int:pk>/cppt-quick/', views.igd_cppt_quick_add, name='igd_cppt_quick_add'),
    path('kunjungan/<int:pk>/cetak-resume-igd/', views.cetak_resume_igd, name='cetak_resume_igd'),
]
