from django.contrib import admin
from .models import (KategoriPenunjang,ItemPenunjang,KelasTerapiObat,GenerikObat,ProdukFarmasi,
    KomposisiProdukFarmasi,KeanggotaanFormularium,MedicationPolicy)


class IngredientInline(admin.TabularInline):
    model=KomposisiProdukFarmasi
    extra=0


class FormularyInline(admin.TabularInline):
    model=KeanggotaanFormularium
    extra=0


@admin.register(ProdukFarmasi)
class ProductAdmin(admin.ModelAdmin):
    list_display=('kode','nama','kind','active','source_version','reviewed_by','price')
    search_fields=('kode','nama','kfa_code')
    list_filter=('active','kind')
    inlines=(IngredientInline,FormularyInline)


@admin.register(ItemPenunjang)
class AncillaryItemAdmin(admin.ModelAdmin):
    list_display=('kode','nama','jenis_order','destination','active','reviewed_by')
    list_filter=('active','jenis_order')
    search_fields=('kode','nama')


for model in (KategoriPenunjang,KelasTerapiObat,GenerikObat,MedicationPolicy):
    admin.site.register(model)
