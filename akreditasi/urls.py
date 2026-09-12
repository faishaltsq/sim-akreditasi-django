from django.urls import path
from . import views

app_name = 'akreditasi'

urlpatterns = [
    # Dashboard Utama
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alias'),

    # Matriks PDCA (Halaman Inti per Pokja)
    path('matriks/', views.matriks_pdca, name='matriks_pdca'),

    # EP CRUD
    path('ep/baru/', views.ep_create, name='ep_create'),
    path('ep/<int:item_id>/edit/', views.ep_edit, name='ep_edit'),
    path('ep/<int:item_id>/detail/', views.ep_detail, name='ep_detail'),
    path('ep/<int:item_id>/hapus/', views.ep_delete, name='ep_delete'),
    path('ep/list/', views.ep_list, name='ep_list'),

    # Quick Score & Inline Edit (AJAX)
    path('ep/record/<int:record_id>/quick-score/', views.quick_score, name='quick_score'),
    path('ep/record/<int:record_id>/inline-edit/', views.inline_edit_pdca, name='inline_edit'),

    # Modal Manajemen Bukti (AJAX JSON)
    path('ep/<int:item_id>/bukti-data/', views.modal_bukti_data, name='modal_bukti_data'),
    path('ep/bukti/upload/<int:req_id>/', views.upload_bukti, name='upload_bukti'),
    path('ep/bukti/upload-ajax/<int:req_id>/', views.upload_bukti_ajax, name='upload_bukti_ajax'),
    path('ep/bukti/link/', views.link_existing_doc, name='link_existing_doc'),
    path('ep/bukti/unlink/<int:file_id>/', views.unlink_doc, name='unlink_doc'),

    # Repositori Dokumen Bukti RDWOS
    path('dokumen/', views.dokumen_hub, name='dokumen_hub'),

    # Manajemen Data
    path('unit/', views.unit_list_create, name='unit_list'),
    path('pokja/', views.pokja_manage, name='pokja_manage'),

    # Pengaturan
    path('profil/', views.profil_rs_view, name='profil_rs'),
    path('log/', views.audit_log_view, name='audit_log'),

    # Laporan & Ekspor
    path('rekap/', views.rekap_view, name='rekap'),
    path('rekap/export/', views.export_excel, name='export_excel'),
]
