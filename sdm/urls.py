from django.urls import path

from sdm import views


app_name = 'sdm'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('pegawai/', views.pegawai_list, name='pegawai_list'),
    path('pegawai/baru/', views.pegawai_create, name='pegawai_create'),
    path('pegawai/<uuid:employee_id>/', views.pegawai_detail, name='pegawai_detail'),
    path(
        'pegawai/<uuid:employee_id>/edit/',
        views.pegawai_edit,
        name='pegawai_edit',
    ),
    path(
        'pegawai/<uuid:employee_id>/dokumen/baru/',
        views.dokumen_upload,
        name='dokumen_upload',
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
    path('kredensial/baru/', views.kredensial_create, name='kredensial_create'),
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
        'kredensial/<uuid:request_id>/putuskan/',
        views.kredensial_decide,
        name='kredensial_decide',
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
        'orientasi/<uuid:assignment_id>/',
        views.orientasi_detail,
        name='orientasi_detail',
    ),
    path('kinerja/', views.kinerja_list, name='kinerja_list'),
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
    path('analitik/', views.analitik_dashboard, name='analitik_dashboard'),
    path('analitik/ekspor/', views.analitik_export, name='analitik_export'),
    path(
        'analitik/ekspor/pdf/',
        views.analitik_export_pdf,
        name='analitik_export_pdf',
    ),
]
