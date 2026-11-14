from django.contrib import admin
from . import expansion_admin
from . import professional_admin
from .models import (
    KelompokLayanan,
    MasterIcd10,
    MasterIcd9,
    KasusTersering,
    KasusTindakan,
    SdkiDiagnosis,
    SlkiLuaran,
    SikiIntervensi,
    Pemetaan3S,
    AturanEpAsesmen,
    AturanEpTindakan,
)


@admin.register(KelompokLayanan)
class KelompokLayananAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'unit_kerja', 'urutan')
    search_fields = ('kode', 'nama')
    list_filter = ('unit_kerja',)
    ordering = ('urutan', 'kode')


@admin.register(MasterIcd10)
class MasterIcd10Admin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'spesialisasi', 'triase_default', 'risiko_default', 'created_at')
    search_fields = ('kode', 'nama', 'spesialisasi')
    list_filter = ('triase_default', 'risiko_default', 'spesialisasi')
    ordering = ('kode',)


@admin.register(MasterIcd9)
class MasterIcd9Admin(admin.ModelAdmin):
    list_display = ('kode', 'nama', 'invasif', 'requires_consent')
    search_fields = ('kode', 'nama')
    list_filter = ('invasif', 'requires_consent')
    ordering = ('kode',)


@admin.register(KasusTersering)
class KasusTerseringAdmin(admin.ModelAdmin):
    list_display = ('kelompok', 'urutan', 'icd10', 'sdki_kode', 'kewenangan', 'perlu_verifikasi')
    search_fields = ('kelompok__nama', 'icd10__kode', 'icd10__nama', 'sdki_kode', 'sdki_nama')
    list_filter = ('kelompok', 'perlu_verifikasi', 'kewenangan')
    raw_id_fields = ('icd10',)
    ordering = ('kelompok__urutan', 'urutan')


@admin.register(KasusTindakan)
class KasusTindakanAdmin(admin.ModelAdmin):
    list_display = ('kasus', 'icd9', 'urutan', 'tarif_umum', 'tarif_bpjs', 'satuan')
    search_fields = ('kasus__kelompok__nama', 'kasus__icd10__kode', 'icd9__kode', 'icd9__nama')
    list_filter = ('kasus__kelompok',)
    raw_id_fields = ('kasus', 'icd9')
    ordering = ('kasus', 'urutan')


@admin.register(SdkiDiagnosis)
class SdkiDiagnosisAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama')
    search_fields = ('kode', 'nama')
    ordering = ('kode',)


@admin.register(SlkiLuaran)
class SlkiLuaranAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama')
    search_fields = ('kode', 'nama')
    ordering = ('kode',)


@admin.register(SikiIntervensi)
class SikiIntervensiAdmin(admin.ModelAdmin):
    list_display = ('kode', 'nama')
    search_fields = ('kode', 'nama')
    ordering = ('kode',)


@admin.register(Pemetaan3S)
class Pemetaan3SAdmin(admin.ModelAdmin):
    list_display = ('sdki', 'slki', 'siki', 'prioritas')
    search_fields = ('sdki__kode', 'sdki__nama', 'slki__kode', 'siki__kode')
    raw_id_fields = ('sdki', 'slki', 'siki')
    ordering = ('sdki', 'prioritas')


@admin.register(AturanEpAsesmen)
class AturanEpAsesmenAdmin(admin.ModelAdmin):
    list_display = ('sub_standard', 'label', 'wajib', 'urutan')
    search_fields = ('sub_standard', 'label')
    list_filter = ('wajib',)
    ordering = ('urutan', 'sub_standard')


@admin.register(AturanEpTindakan)
class AturanEpTindakanAdmin(admin.ModelAdmin):
    list_display = ('jenis', 'kode', 'sub_standard', 'wajib', 'urutan')
    search_fields = ('kode', 'sub_standard', 'label')
    list_filter = ('jenis', 'wajib')
    ordering = ('jenis', 'kode', 'urutan')
