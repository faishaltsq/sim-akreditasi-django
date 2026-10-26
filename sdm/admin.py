from django.contrib import admin
from django.db import transaction

from .models import (
    AturanDokumen,
    HcGrant,
    HasilFormasi,
    InsidenK3Pegawai,
    JamKerjaEfektif,
    KatalogTindakan,
    Lowongan,
    MasterJenjangProfesi,
    PemetaanStandarSDM,
    PengajuanKredensial,
    PenugasanKlinis,
    PeriodeKinerja,
    PeristiwaSDM,
    ProgramDiklat,
    ProgramOrientasi,
    RencanaFormasi,
    SnapshotAnalitikSDM,
    StandarKetenagaan,
)


@admin.register(HcGrant)
class HcGrantAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'capability', 'unit_kerja', 'include_descendants',
        'valid_from', 'valid_until', 'is_active', 'granted_by',
    )
    list_filter = ('capability', 'is_active', 'include_descendants')
    search_fields = ('user__username', 'user__email', 'unit_kerja__code')
    readonly_fields = ('created_at', 'granted_by')
    fields = (
        'user', 'capability', 'unit_kerja', 'include_descendants',
        'valid_from', 'valid_until', 'is_active', 'granted_by', 'created_at',
    )
    ordering = ('-created_at',)

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return False

    @staticmethod
    def _scope_description(grant):
        unit_id = grant.unit_kerja_id if grant.unit_kerja_id is not None else 'hospital'
        valid_until = grant.valid_until.isoformat() if grant.valid_until else 'open-ended'
        return (
            f'user_id={grant.user_id}; capability={grant.capability}; '
            f'unit={unit_id}; descendants={grant.include_descendants}; '
            f'valid={grant.valid_from.isoformat()}..{valid_until}'
        )

    def save_model(self, request, obj, form, change):
        before = None
        if change:
            before = HcGrant.objects.filter(pk=obj.pk).values(
                'is_active', 'user_id', 'capability', 'unit_kerja_id',
                'include_descendants', 'valid_from', 'valid_until',
            ).first()

        if not change and obj.granted_by_id is None:
            obj.granted_by = request.user

        with transaction.atomic():
            super().save_model(request, obj, form, change)
            PeristiwaSDM.objects.create(
                actor=request.user,
                jenis_peristiwa='hc_grant_updated' if change else 'hc_grant_created',
                target_tipe='hc_grant',
                target_id=str(obj.pk),
                status_sebelum=(
                    'active' if before['is_active'] else 'revoked'
                ) if before else '',
                status_sesudah='active' if obj.is_active else 'revoked',
                alasan=self._scope_description(obj),
            )


@admin.register(PeristiwaSDM)
class PeristiwaSDMAdmin(admin.ModelAdmin):
    list_display = (
        'jenis_peristiwa', 'actor', 'target_tipe', 'target_id', 'created_at',
    )
    list_filter = ('jenis_peristiwa', 'target_tipe', 'created_at')
    search_fields = ('target_id', 'actor__username', 'correlation_id')
    ordering = ('-created_at', '-pk')
    readonly_fields = (
        'actor', 'jenis_peristiwa', 'target_tipe', 'target_id',
        'status_sebelum', 'status_sesudah', 'alasan', 'correlation_id',
        'created_at',
    )

    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AturanDokumen)
class AturanDokumenAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'kategori', 'profesi', 'validity_policy', 'version', 'is_active')
    list_filter = ('document_type', 'validity_policy', 'is_active', 'kategori')
    search_fields = ('name', 'profesi')
    ordering = ('document_type', 'name', '-version')


@admin.register(PemetaanStandarSDM)
class PemetaanStandarSDMAdmin(admin.ModelAdmin):
    list_display = ('rule', 'standard_item', 'framework', 'reviewer_name', 'reviewed_at', 'is_active')
    list_filter = ('is_active', 'framework')
    search_fields = ('rule__name', 'standard_item__code', 'reviewer_name')
    autocomplete_fields = ()


@admin.register(RencanaFormasi)
class RencanaFormasiAdmin(admin.ModelAdmin):
    list_display = ('unit_kerja', 'profesi', 'periode_mulai', 'periode_selesai', 'status')
    list_filter = ('status', 'metode')
    search_fields = ('unit_kerja__code', 'profesi')
    readonly_fields = ('calculation_version', 'approved_by', 'approved_at')
    autocomplete_fields = ('jam_kerja_efektif',)


@admin.register(JamKerjaEfektif)
class JamKerjaEfektifAdmin(admin.ModelAdmin):
    list_display = (
        'tahun', 'versi', 'hari_produktif', 'menit_efektif_per_tahun',
        'is_approved', 'is_active',
    )
    list_filter = ('tahun', 'is_approved', 'is_active')
    search_fields = ('sumber',)
    readonly_fields = ('approved_by', 'approved_at', 'created_at', 'updated_at')


@admin.register(StandarKetenagaan)
class StandarKetenagaanAdmin(admin.ModelAdmin):
    list_display = ('nama', 'unit_kerja', 'profesi', 'jenis', 'nilai', 'satuan', 'is_active')
    list_filter = ('jenis', 'is_active', 'profesi')
    search_fields = ('nama', 'profesi', 'sumber_regulasi', 'unit_kerja__code')
    readonly_fields = ('reviewed_at', 'created_at', 'updated_at')


@admin.register(HasilFormasi)
class HasilFormasiAdmin(admin.ModelAdmin):
    list_display = (
        'rencana', 'required_fte', 'actual_fte', 'gap_fte',
        'sufficiency_pct', 'status_risiko', 'calculated_at',
    )
    list_filter = ('status_risiko',)
    search_fields = ('rencana__unit_kerja__code', 'rencana__profesi')
    readonly_fields = [f.name for f in HasilFormasi._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Lowongan)
class LowonganAdmin(admin.ModelAdmin):
    list_display = ('judul', 'unit_kerja', 'profesi', 'jumlah_kebutuhan', 'status')
    list_filter = ('status',)
    search_fields = ('judul', 'profesi', 'unit_kerja__code')


@admin.register(PengajuanKredensial)
class PengajuanKredensialAdmin(admin.ModelAdmin):
    list_display = ('employee', 'unit_kerja', 'status', 'decided_by', 'decided_at')
    list_filter = ('status',)
    search_fields = ('employee__nama_lengkap', 'unit_kerja__code')


class KatalogTindakanInline(admin.TabularInline):
    model = KatalogTindakan
    extra = 0
    fields = ('kode', 'nama', 'tingkat_supervisi', 'catatan', 'is_active')
    ordering = ('kode',)
    search_fields = ('kode', 'nama')


@admin.register(MasterJenjangProfesi)
class MasterJenjangProfesiAdmin(admin.ModelAdmin):
    list_display = ('profesi', 'kode', 'nama', 'urutan')
    list_filter = ('profesi__keluarga',)
    search_fields = ('kode', 'nama', 'profesi__nama')
    ordering = ('profesi__keluarga', 'profesi__nama', 'urutan')
    inlines = (KatalogTindakanInline,)


@admin.register(KatalogTindakan)
class KatalogTindakanAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'jenjang', 'tingkat_supervisi', 'is_active')
    list_filter = ('is_active', 'jenjang__profesi__keluarga', 'tingkat_supervisi')
    search_fields = ('kode', 'nama')
    ordering = ('kode',)


@admin.register(PenugasanKlinis)
class PenugasanKlinisAdmin(admin.ModelAdmin):
    list_display = ('nomor_spk', 'employee', 'unit_kerja', 'versi', 'berlaku_mulai', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('nomor_spk', 'employee__nama_lengkap')


@admin.register(ProgramOrientasi)
class ProgramOrientasiAdmin(admin.ModelAdmin):
    list_display = ('nama', 'unit_kerja', 'berlaku_hari', 'is_active')
    list_filter = ('is_active',)


@admin.register(PeriodeKinerja)
class PeriodeKinerjaAdmin(admin.ModelAdmin):
    list_display = ('nama', 'tanggal_mulai', 'tanggal_selesai', 'status')
    list_filter = ('status',)


@admin.register(ProgramDiklat)
class ProgramDiklatAdmin(admin.ModelAdmin):
    list_display = ('nama', 'kategori', 'jp', 'professional_credits', 'is_active')
    list_filter = ('is_active', 'kategori')
    search_fields = ('nama',)


@admin.register(InsidenK3Pegawai)
class InsidenK3PegawaiAdmin(admin.ModelAdmin):
    list_display = ('tanggal', 'get_kategori_display', 'unit_kerja', 'status')
    list_filter = ('kategori', 'status')
    search_fields = ('unit_kerja__code',)
    readonly_fields = ('deskripsi',)

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False


@admin.register(SnapshotAnalitikSDM)
class SnapshotAnalitikSDMAdmin(admin.ModelAdmin):
    list_display = ('metrik', 'unit_kerja', 'periode_selesai', 'value', 'is_available', 'generated_at')
    list_filter = ('metrik', 'is_available')
    readonly_fields = (
        'metrik', 'unit_kerja', 'periode_mulai', 'periode_selesai',
        'calculation_version', 'filters', 'source_coverage', 'value',
        'denominator', 'is_available', 'unavailable_reason', 'generated_at',
    )

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
