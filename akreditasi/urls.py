from django.urls import path
from . import logbook as logbook_views
from . import views
from . import risiko_views
from . import ai_views
from . import indikator_views
from . import mutu_laporan
from . import kontrol_views
from . import search_views
from . import catalogue_views as catalogue_views

app_name = 'akreditasi'

urlpatterns = [
    # Dasbor Eksekutif — Hospital Integrated Control (tanpa sidebar)
    path('control/', kontrol_views.kontrol_hub, name='kontrol_hub'),
    path('control/risiko/', kontrol_views.kontrol_risiko, name='kontrol_risiko'),
    path('control/emr/', kontrol_views.kontrol_emr, name='kontrol_emr'),
    path('control/dokumen/', kontrol_views.kontrol_dokumen, name='kontrol_dokumen'),
    path('control/layanan/', kontrol_views.kontrol_layanan, name='kontrol_layanan'),
    path('control/ringkasan-ai/', kontrol_views.kontrol_ringkasan_ai, name='kontrol_ringkasan_ai'),

    # Dashboard Utama
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard_alias'),

    # Pencarian terpadu lintas modul (V3)
    path('pencarian/', search_views.pencarian, name='pencarian'),

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
    path('portal-nakes/kredensial/<int:cred_id>/unduh/', views.download_kredensial_nakes, name='download_kredensial'),
    path('portal-nakes/hapus-kredensial/<int:cred_id>/', views.delete_kredensial_nakes, name='delete_kredensial'),
    path('rekap-kps/', views.rekap_kps_unit, name='rekap_kps'),
    path('rekap-kps/verifikasi/<int:cred_id>/', views.verify_kredensial, name='verify_kredensial'),

    # Modul Manajemen Risiko PDCA (Fase 2)
    path('risiko/', risiko_views.risiko_daftar, name='risiko_daftar'),
    path('risiko/baru/', risiko_views.risiko_input, name='risiko_input'),
    path('risiko/perencanaan/', risiko_views.risiko_perencanaan_unit, name='risiko_perencanaan'),
    path('risiko/perencanaan/<int:unit_id>/', risiko_views.risiko_perencanaan_unit, name='risiko_perencanaan_unit'),
    path('risiko/perencanaan/export-csv/', risiko_views.risiko_perencanaan_export_csv, name='risiko_perencanaan_export_csv'),
    path('risiko/laporan/', risiko_views.risiko_laporan, name='risiko_laporan'),
    path('risiko/monitoring-evaluasi/', risiko_views.risiko_monitoring_evaluasi, name='risiko_monev'),
    path('risiko/monitoring-evaluasi/<int:unit_id>/', risiko_views.risiko_monitoring_evaluasi, name='risiko_monev_unit'),
    path('risiko/monitoring-evaluasi/export-csv/', risiko_views.risiko_monev_export_csv, name='risiko_monev_export_csv'),
    path('risiko/fmea-rca/', risiko_views.risiko_fmea_rca, name='risiko_fmea_rca'),
    path('risiko/laporan/<int:unit_id>/', risiko_views.risiko_laporan, name='risiko_laporan_unit'),
    path('risiko/api/indikator-by-unit/', risiko_views.api_indikator_by_unit, name='api_indikator_by_unit'),
    path('api/mutu-indikator/', views.api_mutu_indikator, name='api_mutu_indikator'),
    path('risiko/<int:risiko_id>/', risiko_views.risiko_detail, name='risiko_detail'),
    path('risiko/<int:risiko_id>/edit/', risiko_views.risiko_edit, name='risiko_edit'),
    path('risiko/<int:risiko_id>/hapus/', risiko_views.risiko_hapus, name='risiko_hapus'),
    path('risiko/<int:risiko_id>/perencanaan/', risiko_views.risiko_perencanaan_dokumen, name='risiko_perencanaan_dokumen'),
    path('risiko/<int:risiko_id>/pelaksanaan/', risiko_views.risiko_pelaksanaan_dokumen, name='risiko_pelaksanaan_dokumen'),
    path('risiko/<int:risiko_id>/evaluasi/', risiko_views.risiko_evaluasi, name='risiko_evaluasi'),
    path('risiko/pelaksanaan/', risiko_views.risiko_pelaksanaan_unit, name='risiko_pelaksanaan'),
    path('risiko/pelaksanaan/<int:unit_id>/', risiko_views.risiko_pelaksanaan_unit, name='risiko_pelaksanaan_unit'),
    path('risiko/pelaksanaan/export-csv/', risiko_views.risiko_pelaksanaan_export_csv, name='risiko_pelaksanaan_export_csv'),

    # Laporan Lengkap PDCA (Plan + Do + Monev + RTL)
    path('risiko/laporan-lengkap/', risiko_views.risiko_laporan_lengkap_unit, name='risiko_laporan_lengkap'),
    path('risiko/laporan-lengkap/<int:unit_id>/', risiko_views.risiko_laporan_lengkap_unit, name='risiko_laporan_lengkap_unit'),
    path('risiko/<int:risiko_id>/laporan-lengkap/', risiko_views.risiko_laporan_lengkap, name='risiko_laporan_lengkap_single'),

    # Modul Insiden Keselamatan (Fase 5)
    path('insiden/', risiko_views.insiden_daftar, name='insiden_daftar'),
    path('insiden/lapor/', risiko_views.insiden_lapor, name='insiden_lapor'),
    path('insiden/<int:pk>/', risiko_views.insiden_detail, name='insiden_detail'),
    path('insiden/<int:pk>/status/', risiko_views.insiden_update_status, name='insiden_update_status'),

    # Modul Indikator Mutu — INM + IMP-RS (Renstra 2026–2030)
    path('indikator-mutu/', indikator_views.indikator_dashboard, name='indikator_dashboard'),
    path('indikator-mutu/matriks-inm/', indikator_views.indikator_inm_matrix, name='indikator_inm_matrix'),
    path('indikator-mutu/baru/', indikator_views.indikator_tambah, name='indikator_tambah'),
    path('indikator-mutu/<int:indikator_id>/', indikator_views.indikator_detail, name='indikator_detail'),
    path('indikator-mutu/<int:indikator_id>/edit/', indikator_views.indikator_edit, name='indikator_edit'),
    path('indikator-mutu/<int:indikator_id>/capaian/', indikator_views.indikator_input_capaian, name='indikator_input_capaian'),
    path('indikator-mutu/api/tren/<int:indikator_id>/', indikator_views.api_indikator_tren, name='api_indikator_tren'),
    path('indikator-mutu/api/komparasi-unit/', indikator_views.api_indikator_komparasi_unit, name='api_indikator_komparasi_unit'),

    # Modul Laporan Capaian Indikator Mutu (bulanan / semester / tahunan)
    path('laporan-mutu/', mutu_laporan.laporan_mutu_daftar, name='laporan_mutu_daftar'),
    path('laporan-mutu/baru/', mutu_laporan.laporan_mutu_create, name='laporan_mutu_create'),
    path('laporan-mutu/<int:pk>/', mutu_laporan.laporan_mutu_detail, name='laporan_mutu_detail'),
    path('laporan-mutu/<int:pk>/analisis/', mutu_laporan.laporan_mutu_simpan_analisis, name='laporan_mutu_simpan_analisis'),
    path('laporan-mutu/<int:pk>/tarik-monev/', mutu_laporan.laporan_mutu_tarik_monev, name='laporan_mutu_tarik_monev'),
    path('laporan-mutu/<int:pk>/seksi/', mutu_laporan.laporan_mutu_simpan_seksi, name='laporan_mutu_simpan_seksi'),
    path('laporan-mutu/<int:pk>/verifikasi/', mutu_laporan.laporan_mutu_verifikasi, name='laporan_mutu_verifikasi'),
    path('laporan-mutu/<int:pk>/setujui/', mutu_laporan.laporan_mutu_setujui, name='laporan_mutu_setujui'),
    path('laporan-mutu/<int:pk>/regenerasi/', mutu_laporan.laporan_mutu_regenerasi, name='laporan_mutu_regenerasi'),
    path('laporan-mutu/<int:pk>/cetak/', mutu_laporan.laporan_mutu_cetak, name='laporan_mutu_cetak'),
    path('laporan-mutu/<int:pk>/pdf/', mutu_laporan.laporan_mutu_pdf, name='laporan_mutu_pdf'),

    # Panduan / Dokumentasi Interaktif
    path('panduan/', views.panduan_dokumentasi, name='panduan'),

    # ── Logbook Harian IGD & Rawat Inap (per shift, angka ditarik dari EMR) ──
    path('logbook/', logbook_views.logbook_daftar, name='logbook_daftar'),
    path('logbook/buat/', logbook_views.logbook_buat, name='logbook_buat'),
    path('logbook/<int:pk>/', logbook_views.logbook_detail, name='logbook_detail'),
    path('logbook/<int:pk>/simpan-pasien/', logbook_views.logbook_simpan_pasien, name='logbook_simpan_pasien'),
    path('logbook/<int:pk>/simpan-checklist/', logbook_views.logbook_simpan_checklist, name='logbook_simpan_checklist'),
    path('logbook/<int:pk>/simpan-narasi/', logbook_views.logbook_simpan_narasi, name='logbook_simpan_narasi'),
    path('logbook/<int:pk>/tindakan/', logbook_views.logbook_simpan_tindakan, name='logbook_simpan_tindakan'),
    path('logbook/<int:pk>/tindakan/<uuid:tindakan_id>/hapus/', logbook_views.logbook_hapus_tindakan, name='logbook_hapus_tindakan'),
    path('logbook/<int:pk>/kejadian/', logbook_views.logbook_simpan_kejadian, name='logbook_simpan_kejadian'),
    path('logbook/<int:pk>/bukti/', logbook_views.logbook_unggah_bukti, name='logbook_unggah_bukti'),
    path('logbook/<int:pk>/serah-terima/', logbook_views.logbook_serah_terima, name='logbook_serah_terima'),
    path('logbook/<int:pk>/setujui/', logbook_views.logbook_setujui, name='logbook_setujui'),
    path('logbook/<int:pk>/pdf/', logbook_views.logbook_pdf, name='logbook_pdf'),

    # ── Endpoint AI Asisten Cerdas DeepSeek (backend-only, tidak ada API Key di response) ──
    path('ai/mitigasi-risiko/', ai_views.api_ai_mitigasi_risiko, name='ai_mitigasi_risiko'),
    path('ai/pdca-plan/', ai_views.api_ai_pdca_plan, name='ai_pdca_plan'),
    path('ai/insiden-grading/', ai_views.api_ai_insiden_grading, name='ai_insiden_grading'),
    path('ai/risiko-fmea-saran/', ai_views.api_ai_fmea_saran, name='ai_fmea_saran'),
    path('ai/risiko-rca-saran/', ai_views.api_ai_rca_saran, name='ai_rca_saran'),
    path('ai/evaluasi-risiko/', ai_views.api_ai_evaluasi_risiko, name='ai_evaluasi_risiko'),
    path('ai/investigasi-rtl/', ai_views.api_ai_investigasi_rtl, name='ai_investigasi_rtl'),
    path('ai/rdwos-analisis/', ai_views.api_ai_rdwos_analisis, name='ai_rdwos_analisis'),
    path('ai/rumus-indikator/', ai_views.api_ai_rumus_indikator, name='api_ai_rumus_indikator'),
    path('ai/ep-rekomendasi/', ai_views.api_ai_ep_rekomendasi, name='api_ai_ep_rekomendasi'),
    path('ai/ep-terapkan/', ai_views.api_ai_ep_terapkan, name='api_ai_ep_terapkan'),
    path('ai/ep-lepas/', ai_views.api_ai_ep_lepas, name='api_ai_ep_lepas'),
    path('ai/analisis-masalah-risiko/', ai_views.api_ai_analisis_masalah_risiko, name='api_ai_analisis_masalah_risiko'),
    path('ai/test-connection/', ai_views.api_ai_test_connection, name='ai_test_connection'),
    path('ai/narasi-laporan/', ai_views.api_ai_narasi_laporan, name='api_ai_narasi_laporan'),

    # ── Katalog Standar (Track C UI) ──
    path('katalog/', catalogue_views.katalog_daftar, name='katalog_daftar'),
    path('katalog/pemetaan/', catalogue_views.katalog_pemetaan, name='katalog_pemetaan'),
    path('katalog/validasi/', catalogue_views.katalog_validasi, name='katalog_validasi'),
    path('katalog/pengumuman/', catalogue_views.katalog_pengumuman, name='katalog_pengumuman'),
]
