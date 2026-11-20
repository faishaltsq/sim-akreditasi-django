"""Django admin untuk modul APM-BPJS multi-kanal (rujukan, konfigurasi, log audit)."""
from django.contrib import admin

from .models import (
    KonfigurasiApm,
    KonfigurasiBiometrikPoli,
    LogBiometrik,
    LogRisikoApm,
    RujukanBpjs,
)


@admin.register(RujukanBpjs)
class RujukanBpjsAdmin(admin.ModelAdmin):
    list_display = [
        'no_rujukan', 'pasien', 'jenis_rujukan', 'tgl_rujukan',
        'ppk_rujukan', 'ppk_tujuan', 'status_validasi', 'divalidasi_oleh_kanal',
    ]
    list_filter = ['status_validasi', 'jenis_rujukan', 'divalidasi_oleh_kanal']
    search_fields = ['no_rujukan', 'pasien__nama_lengkap', 'pasien__no_rm', 'pasien__nik', 'pasien__no_bpjs']
    readonly_fields = ['raw_response', 'created_at', 'divalidasi_pada']
    date_hierarchy = 'tgl_rujukan'


@admin.register(KonfigurasiApm)
class KonfigurasiApmAdmin(admin.ModelAdmin):
    list_display = [
        't_buka_rs', 'buffer_tiba_menit', 'ambang_geser_notif_menit',
        'idle_timeout_detik', 'biometrik_maks_percobaan', 'wa_provider', 'updated_at',
    ]

    def has_add_permission(self, request):
        return not KonfigurasiApm.objects.exists()


@admin.register(KonfigurasiBiometrikPoli)
class KonfigurasiBiometrikPoliAdmin(admin.ModelAdmin):
    list_display = [
        'poliklinik', 'wajib_biometrik', 'aktif',
        'usia_min_pengecualian', 'usia_max_pengecualian', 'updated_at',
    ]
    list_filter = ['wajib_biometrik', 'aktif', 'poliklinik']
    list_editable = ['wajib_biometrik', 'aktif']


class AppendOnlyAdminMixin:
    """Log bukti tidak boleh diubah/dihapus dari admin."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LogBiometrik)
class LogBiometrikAdmin(AppendOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['created_at', 'kunjungan', 'percobaan_ke', 'metode', 'hasil', 'mode', 'perangkat_id']
    list_filter = ['hasil', 'metode', 'mode']
    search_fields = ['kunjungan__no_kunjungan', 'kunjungan__pasien__nama_lengkap']
    readonly_fields = [field.name for field in LogBiometrik._meta.fields]


@admin.register(LogRisikoApm)
class LogRisikoApmAdmin(AppendOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['created_at', 'kode_risiko', 'kanal', 'pemicu', 'severity', 'kunjungan']
    list_filter = ['kode_risiko', 'kanal', 'severity']
    search_fields = ['pemicu', 'kunjungan__no_kunjungan', 'kunjungan__pasien__nama_lengkap']
    readonly_fields = [field.name for field in LogRisikoApm._meta.fields]
    date_hierarchy = 'created_at'