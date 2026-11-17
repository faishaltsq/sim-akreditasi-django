from django.contrib import admin, messages
from django.core.exceptions import ValidationError
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
    list_filter=('active','jenis_order','destination','group__parent__parent')
    list_select_related=('destination','group')
    search_fields=('kode','nama')
    actions=('activate_selected',)

    @admin.action(description='Aktifkan item terpilih dengan unit tujuan dan reviewer saat ini')
    def activate_selected(self,request,queryset):
        activated,rejected=0,[]
        for item in queryset:
            item.active=True;item.reviewed_by=request.user
            try:
                item.full_clean()
            except ValidationError as exc:
                rejected.append(item.kode);continue
            item.save(update_fields=['active','reviewed_by']);activated+=1
        if rejected:
            self.message_user(request,f'Ditolak karena unit tujuan/sumber belum lengkap: {", ".join(rejected[:20])}',messages.WARNING)
        if activated:
            self.message_user(request,f'{activated} item katalog penunjang diaktifkan.',messages.SUCCESS)


for model in (KategoriPenunjang,KelasTerapiObat,GenerikObat,MedicationPolicy):
    admin.site.register(model)
