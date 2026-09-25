from django.urls import path
from . import views
from . import risiko_views

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
    path('unit/hierarki/', views.unit_tree, name='unit_tree'),
    path('unit/<int:unit_id>/edit/', views.unit_edit, name='unit_edit'),
    path('unit/<int:unit_id>/hapus/', views.unit_delete, name='unit_delete'),
    path('pokja/', views.pokja_manage, name='pokja_manage'),

    # Pengaturan
    path('profil/', views.profil_rs_view, name='profil_rs'),
    path('log/', views.audit_log_view, name='audit_log'),

    # Laporan & Ekspor
    path('rekap/', views.rekap_view, name='rekap'),
    path('rekap/export/', views.export_excel, name='export_excel'),
    path('rekap/scoring/', views.auto_scoring_pokja, name='auto_scoring'),
    path('rekap/cetak/<int:cat_id>/', views.cetak_dokumen_pokja, name='cetak_dokumen'),

    # Portal Nakes & KPS (Opsi B)
    path('portal-nakes/', views.portal_nakes, name='portal_nakes'),
    path('portal-nakes/upload-kredensial/', views.upload_kredensial_nakes, name='upload_kredensial'),
    path('portal-nakes/hapus-kredensial/<int:cred_id>/', views.delete_kredensial_nakes, name='delete_kredensial'),
    path('rekap-kps/', views.rekap_kps_unit, name='rekap_kps'),
    path('rekap-kps/verifikasi/<int:cred_id>/', views.verify_kredensial, name='verify_kredensial'),

    # Modul Manajemen Risiko PDCA (Fase 2)
    path('risiko/', risiko_views.risiko_daftar, name='risiko_daftar'),
    path('risiko/baru/', risiko_views.risiko_input, name='risiko_input'),
    path('risiko/<int:risiko_id>/', risiko_views.risiko_detail, name='risiko_detail'),
    path('risiko/<int:risiko_id>/evaluasi/', risiko_views.risiko_evaluasi, name='risiko_evaluasi'),

    # Modul Insiden Keselamatan (Fase 5)
    path('insiden/lapor/', risiko_views.insiden_lapor, name='insiden_lapor'),
]
