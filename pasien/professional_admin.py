from django.contrib import admin
from .models import CpptRevision,VerifikasiCppt,PembatalanTagihan,PenugasanDpjpEpisode


class CareEvidenceAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):return False
    def has_change_permission(self,request,obj=None):return False
    def has_delete_permission(self,request,obj=None):return False


admin.site.register(CpptRevision,CareEvidenceAdmin)
admin.site.register(VerifikasiCppt,CareEvidenceAdmin)
admin.site.register(PembatalanTagihan,CareEvidenceAdmin)


@admin.register(PenugasanDpjpEpisode)
class EpisodeDpjpAdmin(admin.ModelAdmin):
    list_display=('visit','doctor','unit','assignment_type','valid_from','valid_until','is_active','source_version')
    readonly_fields=('assigned_by','assigned_at')
    raw_id_fields=('visit','doctor')
    def has_module_permission(self,request):return request.user.is_active and request.user.is_superuser
    def has_view_permission(self,request,obj=None):return self.has_module_permission(request)
    def has_add_permission(self,request):return self.has_module_permission(request)
    def has_change_permission(self,request,obj=None):return self.has_module_permission(request)
    def has_delete_permission(self,request,obj=None):return False
    def get_form(self,request,obj=None,**kwargs):
        base=super().get_form(request,obj,**kwargs)
        class AssignedForm(base):
            def clean(self):
                self.instance.assigned_by=request.user
                return super().clean()
        return AssignedForm
