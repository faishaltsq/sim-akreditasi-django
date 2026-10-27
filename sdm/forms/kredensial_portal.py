"""D-1: portal submission form with no self-selection and no unit picking."""
from django import forms
from django.db.models import Q
from django.utils import timezone

from akreditasi.models import UnitKerja
from sdm.models import PengajuanKredensial

SELECT_CLASS = 'form-select form-select-sm'


class PengajuanPortalForm(forms.ModelForm):
    """Own-account submission: employee and unit come from the session.

    The employee is never a field here — a portal user cannot submit for
    somebody else, and the unit is derived from their placement.
    """

    class Meta:
        model = PengajuanKredensial
        fields = ['jenis', 'spesialisasi_teks']
        widgets = {
            'jenis': forms.Select(attrs={'class': SELECT_CLASS}),
            'spesialisasi_teks': forms.TextInput(attrs={
                'class': SELECT_CLASS, 'maxlength': 150,
                'placeholder': 'mis. Spesialis Jantung & Pembuluh Darah (Sp.JP)',
            }),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.employee = getattr(user, 'pegawai_hc', None)
        kode_jenjang = getattr(
            getattr(self.employee, 'jenjang_master', None), 'kode', ''
        ) or ''
        if not kode_jenjang.startswith(('SP-', 'SUBSP-', 'DU-SP', 'DU-KONS')):
            del self.fields['spesialisasi_teks']
        self.fields['unit_kerja'] = forms.ModelChoiceField(
            queryset=UnitKerja.objects.none(),
            label='Unit Kerja',
            required=False,
            widget=forms.Select(attrs={'class': SELECT_CLASS}),
        )
        if self.employee is None:
            return
        today = timezone.localdate()
        placements = self.employee.penempatan.filter(
            unit_kerja__is_active=True,
            tanggal_mulai__lte=today,
        ).filter(
            Q(tanggal_selesai__isnull=True) | Q(tanggal_selesai__gte=today)
        ).order_by('-tanggal_mulai', '-pk')
        unit_ids = list(placements.values_list('unit_kerja_id', flat=True))
        if not unit_ids:
            # Fall back to the most recent placement so the portal still works
            # for staff between placements; the view warns about it.
            unit_ids = list(
                self.employee.penempatan.order_by('-tanggal_mulai', '-pk')
                .values_list('unit_kerja_id', flat=True)[:1]
            )
        self.fields['unit_kerja'].queryset = UnitKerja.objects.filter(
            pk__in=unit_ids
        ).order_by('level', 'order', 'code')
        if len(unit_ids) == 1:
            self.fields['unit_kerja'].initial = unit_ids[0]
