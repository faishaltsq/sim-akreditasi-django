from django.urls import path

from sdm import views
from sdm import import_views
from sdm import intake_views
from sdm import portal_views
from sdm import rekrutmen_portal_views


app_name = 'sdm'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pegawai/', views.pegawai_list, name='pegawai_list'),
    path('pegawai/impor/', import_views.import_upload, name='pegawai_import'),
    path('pegawai/impor/template/', import_views.import_template, name='pegawai_import_template'),
    path('pegawai/impor/<uuid:batch_id>/', import_views.import_preview, name='pegawai_import_preview'),
    path('pegawai/impor/<uuid:batch_id>/terapkan/', import_views.import_apply, name='pegawai_import_apply'),
    path('pegawai/impor/<uuid:batch_id>/hasil/', import_views.import_result, name='pegawai_import_result'),
    path('pegawai/baru/', intake_views.intake_wizard, name='pegawai_create'),
    path('pegawai/input/baru/<int:step>/', intake_views.intake_wizard, name='pegawai_wizard_step'),
    path('pegawai/input/baru/<int:step>/draf/<uuid:draft_id>/', intake_views.intake_wizard, name='pegawai_wizard_resume'),
    path('pegawai/input/baru/<uuid:draft_id>/selesai/', intake_views.intake_finalize, name='pegawai_intake_finalize'),
    path(
        'pegawai/input/lampiran/<uuid:attachment_id>/hapus/',
        intake_views.intake_attachment_remove,
        name='pegawai_intake_attachment_remove',
    ),
    path('pegawai/<uuid:employee_id>/', views.pegawai_detail, name='pegawai_detail'),
    path('pegawai/<uuid:employee_id>/foto/', views.pegawai_avatar, name='pegawai_avatar'),
    path(
        'pegawai/<uuid:employee_id>/edit/',
        views.pegawai_edit,
        name='pegawai_edit',
    ),
    path(
        'pegawai/<uuid:employee_id>/identitas-pribadi/',
        views.profil_pribadi_edit,
        name='profil_pribadi_edit',
    ),
    path(
        'pegawai/<uuid:employee_id>/bpjs/<str:jenis>/',
        views.bpjs_kartu_upload,
        name='bpjs_kartu_upload',
    ),
    path(
        'pegawai/<uuid:employee_id>/riwayat/baru/',
        views.riwayat_create,
        name='riwayat_create',
    ),
    path(
        'pegawai/<uuid:employee_id>/riwayat/<int:riwayat_id>/ubah/',
        views.riwayat_edit,
        name='riwayat_edit',
    ),
    path(
        'pegawai/<uuid:employee_id>/riwayat/<int:riwayat_id>/hapus/',
        views.riwayat_delete,
        name='riwayat_delete',
    ),
    path(
        'pegawai/<uuid:employee_id>/dokumen/baru/',
        views.dokumen_upload,
        name='dokumen_upload',
    ),
    path(
        'pegawai/<uuid:employee_id>/aktivitas/',
        views.pegawai_aktivitas,
        name='pegawai_aktivitas',
    ),
    path(
        'pegawai/<uuid:employee_id>/aktivitas/ekspor-csv/',
        views.pegawai_aktivitas_export,
        name='pegawai_aktivitas_export',
    ),
    path(
        'pegawai/<uuid:employee_id>/aktivitas/baru/',
        views.aktivitas_manual,
        name='aktivitas_manual',
    ),
    path(
        'dokumen/<int:version_id>/tinjau/',
        views.dokumen_review,
        name='dokumen_review',
    ),
    path(
        'dokumen/<int:version_id>/unduh/',
        views.dokumen_download,
        name='dokumen_download',
    ),
    path('formasi/', views.formasi_list, name='formasi_list'),
    path('formasi/peta/', views.formasi_peta, name='formasi_peta'),
    path('kalkulator-fte/', views.kalkulator_fte, name='kalkulator_fte'),
    path('kalkulator-fte/ekspor-csv/', views.kalkulator_fte_export, name='kalkulator_fte_export'),
    path('kalkulator-fte/simpan/', views.kalkulator_fte_simpan, name='kalkulator_fte_simpan'),
    path('formasi/baru/', views.formasi_create, name='formasi_create'),
    path('formasi/<uuid:plan_id>/', views.formasi_detail, name='formasi_detail'),
    path(
        'formasi/<uuid:plan_id>/aktivitas/',
        views.formasi_add_activity,
        name='formasi_add_activity',
    ),
    path(
        'formasi/<uuid:plan_id>/ajukan/',
        views.formasi_submit,
        name='formasi_submit',
    ),
    path(
        'formasi/<uuid:plan_id>/setujui/',
        views.formasi_approve,
        name='formasi_approve',
    ),
    path('rekrutmen/', views.rekrutmen_list, name='rekrutmen_list'),
    # ── Portal pelamar publik (tanpa login; akses via token) ──
    path('rekrutmen/portal/', rekrutmen_portal_views.portal_lowongan,
         name='portal_lowongan'),
    path('rekrutmen/portal/<uuid:vacancy_id>/daftar/', rekrutmen_portal_views.portal_daftar,
         name='portal_daftar'),
    path('rekrutmen/portal/lamaran/<str:token>/', rekrutmen_portal_views.portal_lamaran_status,
         name='portal_lamaran_status'),
    path('rekrutmen/baru/', views.rekrutmen_create, name='rekrutmen_create'),
    path(
        'rekrutmen/<uuid:vacancy_id>/lamaran/',
        views.rekrutmen_add_application,
        name='rekrutmen_add_application',
    ),
    path(
        'rekrutmen/<uuid:vacancy_id>/',
        views.rekrutmen_detail,
        name='rekrutmen_detail',
    ),
    path(
        'rekrutmen/lamaran/<uuid:application_id>/tahap/',
        views.rekrutmen_move,
        name='rekrutmen_move',
    ),
    path('kredensial/', views.kredensial_list, name='kredensial_list'),
    path(
        'kredensial/katalog/',
        views.kredensial_katalog,
        name='kredensial_katalog',
    ),
    path(
        'kredensial/pengajuan/',
        views.kredensial_daftar_pengajuan,
        name='kredensial_daftar_pengajuan',
    ),
    path('kredensial/spk/', views.kredensial_spk_list, name='kredensial_spk_list'),
    path(
        'kredensial/akses-rme/',
        views.kredensial_akses_rme,
        name='kredensial_akses_rme',
    ),
    path('kredensial/peta/', views.kredensial_peta, name='kredensial_peta'),
    path(
        'kredensial/pengajuan-saya/',
        views.kredensial_pengajuan_sendiri,
        name='kredensial_pengajuan_sendiri',
    ),
    path('kredensial/baru/', views.kredensial_create, name='kredensial_create'),
    path(
        'kredensial/pegawai/<uuid:employee_id>/profil.json',
        views.kredensial_pegawai_profil,
        name='kredensial_pegawai_profil',
    ),
    path(
        'kredensial/dokumen/<str:jenis>/generate/',
        views.dokumen_kredensial_generate,
        name='dokumen_kredensial_generate',
    ),
    path(
        'kredensial/dokumen/<str:jenis>/ubah/',
        views.dokumen_kredensial_edit,
        name='dokumen_kredensial_edit',
    ),
    path(
        'kredensial/dokumen/<str:jenis>/finalkan/',
        views.dokumen_kredensial_finalize,
        name='dokumen_kredensial_finalize',
    ),
    path(
        'kredensial/dokumen/<str:jenis>/unduh/',
        views.dokumen_kredensial_download,
        name='dokumen_kredensial_download',
    ),
    path(
        'kredensial/<uuid:request_id>/kewenangan/',
        views.kredensial_add_privilege,
        name='kredensial_add_privilege',
    ),
    path(
        'kredensial/<uuid:request_id>/psv/',
        views.kredensial_psv,
        name='kredensial_psv',
    ),
    path(
        'kredensial/<uuid:request_id>/',
        views.kredensial_detail,
        name='kredensial_detail',
    ),
    path(
        'kredensial/<uuid:request_id>/bestari/',
        views.kredensial_panel_bestari,
        name='kredensial_panel_bestari',
    ),
    path(
        'kredensial/<uuid:request_id>/putuskan/',
        views.kredensial_decide,
        name='kredensial_decide',
    ),
    path(
        'kredensial/<uuid:request_id>/terbitkan/',
        views.kredensial_terbitkan_spk,
        name='kredensial_terbitkan_spk',
    ),
    path(
        'kredensial/<uuid:request_id>/rekomendasikan/',
        views.kredensial_rekomendasikan,
        name='kredensial_rekomendasikan',
    ),
    path(
        'kredensial/spk/<uuid:assignment_id>/cabut/',
        views.kredensial_cabut_spk,
        name='kredensial_cabut_spk',
    ),
    path(
        'kredensial/spk/<uuid:assignment_id>/cetak-rkk/',
        views.kredensial_cetak_rkk,
        name='kredensial_cetak_rkk',
    ),
    path(
        'kredensial/<uuid:request_id>/bukti-audit/',
        views.kredensial_bukti_audit,
        name='kredensial_bukti_audit',
    ),
    path(
        'kredensial/bukti-starkes/',
        views.kredensial_bukti_starkes,
        name='kredensial_bukti_starkes',
    ),
    path(
        'kredensial/<uuid:request_id>/tahap/',
        views.kredensial_tahap,
        name='kredensial_tahap',
    ),
    path(
        'kredensial/<uuid:request_id>/berita-acara-rapat/',
        views.kredensial_berita_acara_rapat,
        name='kredensial_berita_acara_rapat',
    ),
    path(
        'kredensial/<uuid:request_id>/syarat/<uuid:row_id>/tautkan/',
        views.kredensial_syarat_tautkan,
        name='kredensial_syarat_tautkan',
    ),
    path(
        'kredensial/<uuid:request_id>/syarat/<uuid:row_id>/unggah/',
        views.kredensial_syarat_upload,
        name='kredensial_syarat_upload',
    ),
    path(
        'kredensial/spk/<uuid:assignment_id>/cetak/',
        views.kredensial_cetak_spk,
        name='kredensial_cetak_spk',
    ),
    path('orientasi/', views.orientasi_list, name='orientasi_list'),
    path('orientasi/baru/', views.orientasi_create, name='orientasi_create'),
    path(
        'orientasi/aktivitas/<int:completion_id>/selesai/',
        views.orientasi_complete,
        name='orientasi_complete',
    ),
    path(
        'orientasi/<uuid:assignment_id>/asesmen/',
        views.orientasi_asesmen,
        name='orientasi_asesmen',
    ),
    path(
        'orientasi/<uuid:assignment_id>/sertifikat/',
        views.orientasi_sertifikat,
        name='orientasi_sertifikat',
    ),
    path(
        'orientasi/program/<uuid:program_id>/tor/',
        views.orientasi_tor_pdf,
        name='orientasi_tor_pdf',
    ),
    path('orientasi/rekap.pdf', views.orientasi_rekap_pdf, name='orientasi_rekap_pdf'),
    path(
        'orientasi/<uuid:assignment_id>/',
        views.orientasi_detail,
        name='orientasi_detail',
    ),
    path('kinerja/', views.kinerja_list, name='kinerja_list'),
    path('kinerja/periode/baru/', views.kinerja_periode_baru, name='kinerja_periode_baru'),
    path('kinerja/baru/', views.kinerja_buat, name='kinerja_buat'),
    path(
        'kinerja/<uuid:appraisal_id>/',
        views.kinerja_detail,
        name='kinerja_detail',
    ),
    path(
        'kinerja/<uuid:appraisal_id>/sinkron/',
        views.kinerja_sinkron,
        name='kinerja_sinkron',
    ),
    path(
        'kinerja/<uuid:appraisal_id>/finalkan/',
        views.kinerja_finalize,
        name='kinerja_finalize',
    ),
    path('diklat/', views.diklat_list, name='diklat_list'),
    path('diklat/baru/', views.diklat_create, name='diklat_create'),
    path(
        'diklat/peserta/<uuid:participant_id>/sertifikat/',
        views.diklat_certificate,
        name='diklat_certificate',
    ),
    path('k3/', views.k3_list, name='k3_list'),
    path('k3/lapor/', views.k3_report, name='k3_report'),
    path('k3/imunisasi/tambah/', views.k3_imunisasi_tambah, name='k3_imunisasi_tambah'),
    path('k3/mcu/tambah/', views.k3_mcu_tambah, name='k3_mcu_tambah'),
    path('k3/insiden/tambah/', views.k3_insiden_tambah, name='k3_insiden_tambah'),
    path('k3/insiden/<uuid:incident_id>/tindak-lanjut/', views.k3_tindak_lanjut_tambah, name='k3_tindak_lanjut_tambah'),
    path('saya/', portal_views.portal_index, name='portal_index'),
    path(
        'saya/pengajuan/<uuid:request_id>/ubah/',
        views.kredensial_pengajuan_ubah,
        name='kredensial_pengajuan_ubah',
    ),
    path(
        'saya/dokumen/unggah/',
        views.portal_dokumen_upload,
        name='portal_dokumen_upload',
    ),
    path('logbook/', views.logbook_list, name='logbook_list'),
    path('logbook/baru/', views.logbook_create, name='logbook_create'),
    path('logbook/cepat/', views.logbook_cepat, name='logbook_cepat'),
    path(
        'logbook/verifikasi/',
        views.logbook_verifikasi,
        name='logbook_verifikasi',
    ),
    path(
        'logbook/<uuid:entry_id>/verifikasi/',
        views.logbook_verifikasi_aksi,
        name='logbook_verifikasi_aksi',
    ),
    path(
        'logbook/<uuid:entry_id>/ubah/',
        views.logbook_edit,
        name='logbook_edit',
    ),
    path(
        'logbook/<uuid:entry_id>/hapus/',
        views.logbook_delete,
        name='logbook_delete',
    ),
    path('saya/ajukan/', portal_views.portal_request_create, name='portal_request_create'),
    path('saya/ajukan/<uuid:request_id>/batal/', portal_views.portal_request_cancel, name='portal_request_cancel'),
    path('analitik/', views.analitik_dashboard, name='analitik_dashboard'),
    path('analitik/ekspor/', views.analitik_export, name='analitik_export'),
    path(
        'analitik/ekspor/pdf/',
        views.analitik_export_pdf,
        name='analitik_export_pdf',
    ),
    path(
        'laporan/kps/paket/',
        views.kps_report,
        name='kps_report',
    ),
    path(
        'laporan/kps/paket/preview/',
        views.kps_pack_preview,
        name='kps_pack_preview',
    ),
    path(
        'laporan/kps/paket/publikasi/',
        views.kps_pack_publish,
        name='kps_pack_publish',
    ),
]
