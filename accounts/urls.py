from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Manajemen Pengguna (CRUD)
    path('users/', views.user_list, name='user_list'),
    path('users/baru/', views.user_create, name='user_create'),
    path('users/<int:user_id>/edit/', views.user_edit, name='user_edit'),
    path('users/<int:user_id>/hapus/', views.user_delete, name='user_delete'),

    # Pusat Kontrol Admin
    path('kontrol/', views.admin_control_center, name='admin_control_center'),
    path('kontrol/unit/<int:unit_id>/update-hierarchy/', views.update_unit_hierarchy, name='update_unit_hierarchy'),
    path('kontrol/permissions/update/', views.update_role_permissions, name='update_role_permissions'),
    path('kontrol/permissions/reset/', views.reset_role_permissions, name='reset_role_permissions'),
    path('kontrol/user/<int:user_id>/permissions/', views.update_user_custom_permissions, name='update_user_custom_permissions'),
    path('kontrol/system/update/', views.update_system_config, name='update_system_config'),
    path('kontrol/system/toggle-freeze/', views.toggle_survey_freeze, name='toggle_survey_freeze'),
]
