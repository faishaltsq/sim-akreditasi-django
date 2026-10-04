from django.contrib import admin
from .models import Pasien, Ruangan, Bed, KunjunganPasien, AsesmenRisikoKlinis, CPPT, BillingItem, DischargeRecord, ResepElektronik, ResepDetail

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


class ResepDetailInline(admin.TabularInline):
    model = ResepDetail
    extra = 1
    fields = ['nama_obat', 'bentuk_sediaan', 'dosis', 'aturan_pakai', 'jumlah', 'harga_satuan', 'catatan_khusus']


@admin.register(ResepElektronik)
class ResepElektronikAdmin(admin.ModelAdmin):
    list_display = ['no_resep', 'kunjungan', 'jenis_resep', 'status', 'tanggal_resep', 'dokter_peresep']
    list_filter = ['status', 'jenis_resep']
    search_fields = ['no_resep', 'kunjungan__pasien__nama_lengkap']
    inlines = [ResepDetailInline]
