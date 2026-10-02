from django.contrib import admin
from .models import Pasien, Ruangan, Bed, KunjunganPasien, AsesmenRisikoKlinis, CPPT, BillingItem, DischargeRecord

@admin.register(Pasien)
class PasienAdmin(admin.ModelAdmin):
    list_display = ['no_rm', 'nama_lengkap', 'jenis_kelamin', 'tanggal_lahir', 'no_bpjs', 'created_at']
    search_fields = ['no_rm', 'nama_lengkap', 'nik', 'no_bpjs']

@admin.register(Ruangan)
class RuanganAdmin(admin.ModelAdmin):
    list_display = ['kode', 'nama', 'kelas', 'jenis', 'kapasitas']
    list_filter = ['kelas', 'jenis']

@admin.register(Bed)
class BedAdmin(admin.ModelAdmin):
    list_display = ['kode_bed', 'ruangan', 'status']
    list_filter = ['status', 'ruangan__kelas']

@admin.register(KunjunganPasien)
class KunjunganPasienAdmin(admin.ModelAdmin):
    list_display = ['no_kunjungan', 'pasien', 'jenis_kunjungan', 'tanggal_masuk', 'status', 'dpjp']
    list_filter = ['jenis_kunjungan', 'status', 'penjamin']
    search_fields = ['no_kunjungan', 'pasien__nama_lengkap', 'pasien__no_rm']

admin.site.register(AsesmenRisikoKlinis)
admin.site.register(CPPT)
admin.site.register(BillingItem)
admin.site.register(DischargeRecord)
