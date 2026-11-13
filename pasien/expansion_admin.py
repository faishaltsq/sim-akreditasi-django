from django.contrib import admin
from .models import PharmacyServiceGrant,MedicationSafetyReview,PpraReviewRequest,PrescriptionOperation


@admin.register(PharmacyServiceGrant)
class PharmacyGrantAdmin(admin.ModelAdmin):
    list_display=('user','unit','can_ppra_review')

    def has_add_permission(self,request):
        return request.user.is_superuser

    def has_change_permission(self,request,obj=None):
        return request.user.is_superuser

    def has_delete_permission(self,request,obj=None):
        return request.user.is_superuser


class ClinicalEvidenceAdmin(admin.ModelAdmin):
    def has_add_permission(self,request):
        return False

    def has_change_permission(self,request,obj=None):
        return False

    def has_delete_permission(self,request,obj=None):
        return False


for model in (MedicationSafetyReview,PpraReviewRequest,PrescriptionOperation):
    admin.site.register(model,ClinicalEvidenceAdmin)
