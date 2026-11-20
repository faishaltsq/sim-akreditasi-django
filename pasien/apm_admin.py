"""Django admin untuk modul APM-BPJS multi-kanal (rujukan, konfigurasi, log audit)."""
from django.contrib import admin

from .models import (
    AntreanBpjsTaskLog,
    JadwalDokterPoli,
    KonfigurasiApm,
    KonfigurasiBiometrikPoli,
    LogBiometrik,
    LogRisikoApm,
    RujukanBpjs,
    WhatsAppLog,
)


@admin.register(JadwalDokterPoli)
class JadwalDokterPoliAdmin(admin.ModelAdmin):
    list_display = [
        'nama_dokter', 'poliklinik', 'hari_praktik', 'jam_mulai', 'jam_selesai',
        'kuota_maksimal', 'durasi_per_pasien_menit', 'status_ketersediaan',
        'kode_poli_bpjs', 'kode_dokter_bpjs',
    ]
    list_filter = ['poliklinik', 'status_ketersediaan', 'hari_praktik']
    list_editable = ['status_ketersediaan', 'kuota_maksimal']
    search_fields = ['nama_dokter', 'gelar']
    fieldsets = (
        ('Identitas Dokter', {'fields': ('nama_dokter', 'gelar', 'foto_dokter', 'foto_url')}),
        ('Jadwal & Kuota', {'fields': (
            'poliklinik', 'hari_praktik', 'jam_mulai', 'jam_selesai',
            'kuota_maksimal', 'durasi_per_pasien_menit', 'status_ketersediaan',
        )}),
        ('Kode Bridging BPJS', {
            'fields': ('kode_poli_bpjs', 'kode_dokter_bpjs'),
            'description': (
                'Wajib diisi agar pendaftaran BPJS bisa menerbitkan SEP dan antrean. '
                'Tanpa kode ini sistem menolak dengan MAPPING_MISSING (by design).'
            ),
        }),
        ('Publikasi', {'fields': ('keterangan',)}),
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


@admin.register(WhatsAppLog)
class WhatsAppLogAdmin(AppendOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['created_at', 'jenis_pesan', 'status', 'provider', 'percobaan', 'nomor_tujuan']
    list_filter = ['jenis_pesan', 'status', 'provider']
    search_fields = ['nomor_tujuan', 'kunjungan__no_kunjungan']
    readonly_fields = [field.name for field in WhatsAppLog._meta.fields]
    date_hierarchy = 'created_at'


@admin.register(AntreanBpjsTaskLog)
class AntreanBpjsTaskLogAdmin(AppendOnlyAdminMixin, admin.ModelAdmin):
    list_display = ['kunjungan', 'task_id', 'nama_task', 'waktu', 'status_kirim']
    list_filter = ['task_id', 'status_kirim']
    search_fields = ['kunjungan__no_kunjungan']
    readonly_fields = [field.name for field in AntreanBpjsTaskLog._meta.fields]