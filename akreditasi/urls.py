from django.urls import path
from . import views

app_name = 'akreditasi'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ep/baru/', views.ep_create, name='ep_create'),
    path('ep/<int:item_id>/edit/', views.ep_edit, name='ep_edit'),
    path('ep/<int:item_id>/detail/', views.ep_detail, name='ep_detail'),
    path('ep/<int:item_id>/hapus/', views.ep_delete, name='ep_delete'),
    path('ep/record/<int:record_id>/quick-score/', views.quick_score, name='quick_score'),
    path('ep/bukti/upload/<int:req_id>/', views.upload_bukti, name='upload_bukti'),
    path('unit/', views.unit_list_create, name='unit_list'),
    path('rekap/', views.rekap_view, name='rekap'),
    path('rekap/export/', views.export_excel, name='export_excel'),
]
