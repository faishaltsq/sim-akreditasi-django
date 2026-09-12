from django.contrib import admin
from .models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'full_name', 'unit_kerja', 'jabatan', 'is_active_member')
    list_filter = ('role', 'is_active_member', 'unit_kerja')
    search_fields = ('user__username', 'full_name', 'jabatan')
    filter_horizontal = ('pokja_access',)
