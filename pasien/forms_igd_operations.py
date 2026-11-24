from django import forms


class OperationForm(forms.Form):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-select' if isinstance(field.widget, forms.Select) else 'form-control'
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs['rows'] = 2

    def clean(self):
        values = super().clean()
        if set(self.data) - set(self.fields):
            raise forms.ValidationError('Atribut aksi tidak dikenal.')
        return values


class InvestigationForm(OperationForm):
    jenis = forms.ChoiceField(choices=[('LAB','Laboratorium'),('RADIOLOGI','Radiologi / CT'),('EKG','EKG'),('LAINNYA','Lainnya')])
    nama_pemeriksaan = forms.CharField(max_length=255)
    prioritas = forms.ChoiceField(choices=[('RUTIN','Rutin'),('CITO','CITO')])
    catatan_klinis = forms.CharField(label='Indikasi klinis / diagnosis kerja (manual)', max_length=4000, widget=forms.Textarea)


class CpptForm(OperationForm):
    subjektif = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    objektif = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    asesmen = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    plan = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)

    def clean(self):
        values = super().clean()
        if not any(values.values()):
            raise forms.ValidationError('Isi minimal satu bagian SOAP.')
        return values


class ActionPlanForm(OperationForm):
    mode = forms.ChoiceField(required=False, choices=[('MANUAL','Manual'),('MASTER','Master'),('AI','AI')])
    ai_ticket = forms.CharField(required=False, widget=forms.HiddenInput)
    lokasi_anatomis = forms.CharField(required=False,max_length=200)
    catatan_klinis = forms.CharField(required=False,max_length=2000,widget=forms.Textarea)
    action_id = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput)
    jenis = forms.ChoiceField(choices=[('ICD9','ICD-9 (Medis)'),('SIKI','SIKI (Keperawatan)'),('BEBAS','Manual')])
    kode = forms.CharField(required=False, max_length=20)
    nama = forms.CharField(required=False, max_length=200)
    quantity = forms.DecimalField(required=False, max_digits=8, decimal_places=2, min_value=0.01, initial=1)
    tarif = forms.DecimalField(required=False, max_digits=12, decimal_places=2, min_value=0)
    catatan_tarif = forms.CharField(required=False, max_length=4000, widget=forms.Textarea)
    standard_item = forms.IntegerField(required=False, min_value=1, label='ID EP (opsional)')
    ep_status = forms.ChoiceField(required=False,choices=[('BELUM','Belum lengkap'),('TERPENUHI','Terpenuhi — dibuktikan petugas'),('NA','Tidak berlaku')])
    ep_catatan = forms.CharField(required=False,max_length=4000,widget=forms.Textarea,label='Catatan / Referensi Bukti EP')


class ActionIdForm(OperationForm):
    action_id = forms.IntegerField(min_value=1)


class ActionExecutionForm(ActionIdForm):
    occurred_at = forms.DateTimeField(required=False)
    retrospective_reason = forms.CharField(required=False,max_length=2000)


class SignatureForm(OperationForm):
    section = forms.ChoiceField(choices=[('MEDIS','Bagian Medis'),('KEPERAWATAN','Bagian Keperawatan')])
    exemptions = forms.JSONField(required=False, widget=forms.Textarea, label='Pengecualian beralasan (JSON)')


class FinalizationForm(OperationForm):
    outcome = forms.ChoiceField(choices=[('','— Pilih tindakan finalisasi —'),('NONE','Final dokumen saja, tanpa perubahan status pelayanan'),('PULANG','Pulang'),('RANAP','Transfer Rawat Inap'),('CONSULT','Konsultasi Poli (tetap IGD)'),('TRANSFER','Transfer layanan ke Poli'),('RUJUK','Rujuk RS Luar'),('MENINGGAL','Meninggal'),('PAPS','PAPS')])
    resume = forms.CharField(max_length=20000, widget=forms.Textarea)
    bed_id = forms.IntegerField(required=False, min_value=1, label='Bed tujuan (khusus Rawat Inap)')
    dpjp = forms.CharField(required=False, max_length=150)
    edukasi = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    obat = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    kontrol = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))
    paps_alasan = forms.CharField(required=False, max_length=4000)
    paps_nama_penolak = forms.CharField(required=False, max_length=150)


class RajalFinalizationForm(OperationForm):
    """Penutupan episode rawat jalan: kondisi akhir berasal dari langkah 10 (DPJP)."""
    resume = forms.CharField(max_length=20000, widget=forms.Textarea)
    edukasi = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    obat = forms.CharField(required=False, max_length=10000, widget=forms.Textarea)
    kontrol = forms.DateField(required=False, widget=forms.DateInput(attrs={'type':'date'}))


class AddendumForm(OperationForm):
    section = forms.ChoiceField(choices=[('MEDIS','Medis'),('KEPERAWATAN','Keperawatan')])
    reason = forms.CharField(min_length=8, max_length=2000, widget=forms.Textarea)
    text = forms.CharField(min_length=1, max_length=20000, widget=forms.Textarea)


class InvestigationResultForm(OperationForm):
    order_id = forms.IntegerField(min_value=1)
    #: F4.2 (ADR-5): empat status order; form hasil hanya menulis dua yang
    #: bermakna bagi unit pelaksana — DRAFT dan BATAL ditulis oleh pemesan.
    status = forms.ChoiceField(choices=[('DIPROSES','Dalam proses'),('SELESAI','Hasil tersedia')])
    hasil_pemeriksaan = forms.CharField(required=False,max_length=20000,widget=forms.Textarea)
    #: F4.3: interpretasi klinis + LVEF terpisah dari status.
    interpretasi = forms.CharField(required=False,max_length=20000,widget=forms.Textarea)
    lvef = forms.IntegerField(required=False,min_value=0,max_value=100,label='LVEF (%)')
    is_critical_value = forms.BooleanField(required=False)
    critical_value_catatan = forms.CharField(required=False,max_length=200)
    #: F4.4: jejak pelaporan nilai kritis. Wajib lengkap bila is_critical_value.
    critical_found_at = forms.DateTimeField(required=False)
    critical_reported_at = forms.DateTimeField(required=False)
    critical_reported_to = forms.CharField(required=False,max_length=150)
    critical_readback_at = forms.DateTimeField(required=False)
    critical_readback_by = forms.IntegerField(required=False,min_value=1)

    def __init__(self, *args, **kwargs):
        #: F4.3 hanya berlaku untuk episode kardiologi (S7-L1-02/04). Jalur IGD
        #: tetap persis seperti sebelumnya: hasil cukup, interpretasi opsional.
        self.require_interpretation = kwargs.pop('require_interpretation', False)
        super().__init__(*args, **kwargs)

    def clean(self):
        values = super().clean()
        if values.get('status') == 'SELESAI' and not values.get('hasil_pemeriksaan'):
            self.add_error('hasil_pemeriksaan','Hasil wajib sebelum status selesai.')
        # F4.3: hasil terbaca pada episode kardiologi wajib punya interpretasi
        # klinis; angka hasil saja tidak menjawab pertanyaan klinis dan tidak
        # dapat diaudit sebagai tafsir.
        if (self.require_interpretation and values.get('status') == 'SELESAI'
                and not (values.get('interpretasi') or '').strip()):
            self.add_error('interpretasi','Interpretasi klinis wajib sebelum status selesai.')
        if values.get('is_critical_value') and not values.get('critical_value_catatan'):
            self.add_error('critical_value_catatan','Catatan hasil kritis wajib.')
        # F4.4 (S7-L1-05): nilai kritis tanpa jejak pelaporan bukan laporan —
        # tidak ada bukti DPJP menerima, tidak ada bukti read-back.
        if values.get('is_critical_value'):
            for name, label in (
                ('critical_found_at', 'Jam temuan'),
                ('critical_reported_at', 'Jam lapor ke DPJP'),
                ('critical_reported_to', 'Penerima laporan'),
                ('critical_readback_at', 'Jam read-back'),
                ('critical_readback_by', 'Verifikator read-back'),
            ):
                if not values.get(name):
                    self.add_error(name, f'{label} wajib untuk nilai kritis.')
            found, reported = values.get('critical_found_at'), values.get('critical_reported_at')
            if found and reported and reported < found:
                self.add_error('critical_reported_at','Jam lapor tidak boleh sebelum jam temuan.')
            readback = values.get('critical_readback_at')
            if reported and readback and readback < reported:
                self.add_error('critical_readback_at','Read-back tidak boleh sebelum jam lapor.')
        return values
