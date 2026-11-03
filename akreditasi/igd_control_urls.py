from django.urls import path, reverse
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def igd_control_hub(request):
    return redirect('pasien:igd_dashboard')


@login_required
def igd_alur_triage(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=triage')


@login_required
def igd_alur_asesmen_ppa(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=asesmen')


@login_required
def igd_alur_penunjang(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=penunjang')


@login_required
def igd_alur_tindakan(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=tindakan')


@login_required
def igd_alur_disposisi(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=disposisi')


@login_required
def igd_alur_administrasi(request):
    return redirect(reverse('pasien:igd_dashboard') + '?focus=administrasi')


@login_required
def igd_mutu_logbook(request):
    return redirect(reverse('akreditasi:logbook_daftar') + '?jenis=IGD')


@login_required
def igd_mutu_triage_audit(request):
    return redirect(reverse('pasien:igd_dashboard') + '?audit=door_time')


@login_required
def igd_mutu_indicators(request):
    return redirect('akreditasi:indikator_dashboard')


@login_required
def igd_mutu_inventory(request):
    return redirect(reverse('akreditasi:logbook_daftar') + '?jenis=IGD&focus=troli')


@login_required
def igd_mutu_handover(request):
    return redirect(reverse('akreditasi:logbook_daftar') + '?jenis=IGD&focus=handover')


urlpatterns = [
    path('', igd_control_hub, name='igd_control_hub'),
    path('triage/', igd_alur_triage, name='igd_alur_triage'),
    path('asesmen-ppa/', igd_alur_asesmen_ppa, name='igd_alur_asesmen_ppa'),
    path('penunjang/', igd_alur_penunjang, name='igd_alur_penunjang'),
    path('tindakan/', igd_alur_tindakan, name='igd_alur_tindakan'),
    path('disposisi/', igd_alur_disposisi, name='igd_alur_disposisi'),
    path('administrasi/', igd_alur_administrasi, name='igd_alur_administrasi'),
    path('logbook/', igd_mutu_logbook, name='igd_mutu_logbook'),
    path('triage-audit/', igd_mutu_triage_audit, name='igd_mutu_triage_audit'),
    path('indicators/', igd_mutu_indicators, name='igd_mutu_indicators'),
    path('inventory/', igd_mutu_inventory, name='igd_mutu_inventory'),
    path('handover/', igd_mutu_handover, name='igd_mutu_handover'),
]
