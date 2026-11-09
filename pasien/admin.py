from django.contrib import admin
from .models import (
    Pasien, Ruangan, Bed, KunjunganPasien, AsesmenRisikoKlinis,
    CPPT, BillingItem, DischargeRecord, ResepElektronik, ResepDetail,
    KorelasiEpAsesmen, LampiranAsesmen, TindakanAsesmen
)

class KorelasiEpAsesmenInline(admin.TabularInline):
    model = KorelasiEpAsesmen
    extra = 0
    fields = ['standard_item', 'status', 'catatan', 'diverifikasi_oleh', 'diverifikasi_pada']

class TindakanAsesmenInline(admin.TabularInline):
    model = TindakanAsesmen
    extra = 0
    fields = ['urutan', 'jenis', 'kode', 'nama', 'sumber_data', 'tarif_acuan', 'tarif',
              'catatan_tarif', 'standard_item', 'ep_status']
    raw_id_fields = ['icd9', 'siki', 'standard_item', 'billing_item']

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
    inlines = [KorelasiEpAsesmenInline, TindakanAsesmenInline]

admin.site.register(AsesmenRisikoKlinis)
admin.site.register(CPPT)
admin.site.register(BillingItem)
admin.site.register(DischargeRecord)

@admin.register(LampiranAsesmen)
class LampiranAsesmenAdmin(admin.ModelAdmin):
    list_display = ['nama_asli', 'kunjungan', 'jenis', 'ukuran', 'diunggah_oleh', 'diunggah_pada']
    list_filter = ['jenis']
    search_fields = ['nama_asli', 'kunjungan__no_kunjungan']
    readonly_fields = ['kunjungan', 'jenis', 'file', 'nama_asli', 'ukuran', 'diunggah_oleh', 'diunggah_pada']

    def has_add_permission(self, request):
        return False



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
