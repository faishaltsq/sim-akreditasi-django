"""Reviewed configuration administration, separate from clinical performance."""
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone
from .models import LayananProfesional,PemetaanKewenanganLayanan,ProfessionalCareGrant,TarifLayananProfesi,BatasanKewenanganProfesional


class ReviewedConfigurationAdmin(admin.ModelAdmin):
    readonly_fields=('reviewed_by','reviewed_at')

    def has_module_permission(self,request):return request.user.is_active and request.user.is_superuser
    def has_view_permission(self,request,obj=None):return self.has_module_permission(request)
    def has_add_permission(self,request):return self.has_module_permission(request)
    def has_change_permission(self,request,obj=None):return self.has_module_permission(request)
    def has_delete_permission(self,request,obj=None):return False

    def get_form(self,request,obj=None,**kwargs):
        base=super().get_form(request,obj,**kwargs)
        class ReviewedForm(base):
            def clean(self):
                self.instance.reviewed_by=request.user
                self.instance.reviewed_at=timezone.now()
                return super().clean()
        return ReviewedForm


@admin.register(LayananProfesional)
class ServiceAdmin(ReviewedConfigurationAdmin):
    list_display=('code','name','group','authority_kind','note_format','is_active')
    search_fields=('code','name')


@admin.register(PemetaanKewenanganLayanan)
class AuthorityMappingAdmin(ReviewedConfigurationAdmin):
    list_display=('service','catalog_item','source_version','is_active')
    raw_id_fields=('catalog_item',)


@admin.register(ProfessionalCareGrant)
class ScopedGrantAdmin(ReviewedConfigurationAdmin):
    list_display=('user','unit','capability','service','valid_from','valid_until','is_active')
    raw_id_fields=('user',)


@admin.register(TarifLayananProfesi)
class ProfessionalPriceAdmin(ReviewedConfigurationAdmin):
    list_display=('service','unit','profession','grade','payor','jasa_sarana','jasa_pelayanan','is_free','version','review_state','valid_from','valid_until')
    list_filter=('unit','profession','payor','review_state')

    def grants(self,request):
        today=timezone.localdate()
        return ProfessionalCareGrant.objects.filter(user=request.user,capability='MANAGE_TARIFF',is_active=True,valid_from__lte=today,valid_until__gte=today,reviewed_by__isnull=False,reviewed_at__isnull=False).exclude(reviewed_by=request.user).exclude(source_version='')

    def has_module_permission(self,request):return request.user.is_active and request.user.is_staff and self.grants(request).exists()
    def has_add_permission(self,request):return self.has_module_permission(request) and admin.ModelAdmin.has_add_permission(self,request)
    def has_view_permission(self,request,obj=None):
        return self.has_module_permission(request) and (obj is None or self.grants(request).filter(unit=obj.unit).filter(Q(service__isnull=True)|Q(service=obj.service)).exists())
    def has_change_permission(self,request,obj=None):return self.has_view_permission(request,obj) and admin.ModelAdmin.has_change_permission(self,request,obj) and (obj is None or obj.review_state!='APPROVED')
    def get_queryset(self,request):
        scope=Q(pk__in=[])
        for grant in self.grants(request):
            scope|=Q(unit_id=grant.unit_id) & (Q(service_id=grant.service_id) if grant.service_id else Q())
        return super().get_queryset(request).filter(scope)

    def save_model(self,request,obj,form,change):
        from akreditasi.models import AuditLog
        if not self.grants(request).select_for_update().filter(unit=obj.unit).filter(Q(service__isnull=True)|Q(service=obj.service)).exists():raise PermissionDenied('Grant pengelolaan tarif unit/layanan diperlukan.')
        super().save_model(request,obj,form,change)
        AuditLog.objects.create(user=request.user,aksi='UPDATE' if change else 'CREATE',model_name='TarifLayananProfesi',object_repr=f'Tarif #{obj.pk}',detail=f'service={obj.service_id}; unit={obj.unit_id}; version={obj.version}; sarana={obj.jasa_sarana}; pelayanan={obj.jasa_pelayanan}; source={obj.source_version}; state={obj.review_state}')


admin.site.register(BatasanKewenanganProfesional,ReviewedConfigurationAdmin)
