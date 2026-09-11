from django.contrib import admin
from .models import (
    Framework, UnitKerja, Category, StandardItem,
    EvidenceReq, QualityRecord, EvidenceFile, AuditLog
)


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
