from django.contrib import admin
from django.utils.html import format_html
from .models import (
    Framework, UnitKerja, Category, StandardItem,
    EvidenceReq, QualityRecord, EvidenceFile, AuditLog, RumahSakitProfile
)
from .risiko_models import RenstraRoadmap, RenstraFokusItem


@admin.register(Framework)
class FrameworkAdmin(admin.ModelAdmin):
    list_display = ('name', 'cycle_type', 'version')


@admin.register(UnitKerja)
class UnitKerjaAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'pic_name')
    search_fields = ('name', 'code')


class EvidenceReqInline(admin.TabularInline):
    model = EvidenceReq
    extra = 1


class QualityRecordInline(admin.StackedInline):
    model = QualityRecord
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'framework', 'order', 'percentage')
    list_filter = ('framework',)
    ordering = ('order',)


@admin.register(StandardItem)
class StandardItemAdmin(admin.ModelAdmin):
    list_display = ('code', 'sub_standard', 'category', 'order')
    list_filter = ('category__framework', 'category')
    search_fields = ('code', 'description')
    inlines = [EvidenceReqInline, QualityRecordInline]


@admin.register(EvidenceReq)
class EvidenceReqAdmin(admin.ModelAdmin):
    list_display = ('standard_item', 'category_type', 'title', 'is_mandatory')
    list_filter = ('category_type',)


@admin.register(QualityRecord)
class QualityRecordAdmin(admin.ModelAdmin):
    list_display = ('standard_item', 'unit', 'score', 'budget_status', 'updated_at')
    list_filter = ('score', 'budget_status', 'unit')


@admin.register(EvidenceFile)
class EvidenceFileAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'requirement', 'version', 'status', 'uploaded_at')
    list_filter = ('status',)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'aksi', 'model_name', 'object_repr')
    list_filter = ('aksi', 'model_name')
    readonly_fields = ('timestamp',)


@admin.register(RumahSakitProfile)
class RumahSakitProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'kode_rs', 'kota', 'tipe', 'akreditasi_tahun')


# ── Renstra Roadmap Admin ─────────────────────────────────────────────────────

class RenstraFokusItemInline(admin.TabularInline):
    model = RenstraFokusItem
    extra = 1
    fields = ['nomor', 'nama_fokus', 'indikator_mutu', 'kode_ref', 'target_label', 'satuan', 'unit_kerja_label']
    raw_id_fields = ['indikator_mutu']


@admin.register(RenstraRoadmap)
class RenstraRoadmapAdmin(admin.ModelAdmin):
    list_display = ['tahun', 'preview_badge', 'isu_strategis', 'sub_tema', 'total_fokus', 'urutan', 'aktif']
    list_editable = ['urutan', 'aktif']
    list_filter = ['aktif']
    search_fields = ['isu_strategis', 'sub_tema', 'deskripsi']
    inlines = [RenstraFokusItemInline]

    def preview_badge(self, obj):
        return format_html(
            '<span style="background:{}; color:#fff; padding:4px 10px; border-radius:4px; font-weight:600; font-size:12px;">'
            '<i class="bi {}" style="margin-right:4px;"></i>{}</span>',
            obj.warna_hex, obj.ikon, obj.tahun
        )
    preview_badge.short_description = 'Preview Badge'

    def total_fokus(self, obj):
        return obj.fokus_items.count()
    total_fokus.short_description = 'Jml Fokus'


@admin.register(RenstraFokusItem)
class RenstraFokusItemAdmin(admin.ModelAdmin):
    list_display = ['roadmap', 'nomor', 'nama_fokus', 'indikator_mutu', 'target_label', 'unit_kerja_label']
    list_filter = ['roadmap__tahun']
    search_fields = ['nama_fokus', 'kode_ref', 'unit_kerja_label']
    raw_id_fields = ['indikator_mutu']
