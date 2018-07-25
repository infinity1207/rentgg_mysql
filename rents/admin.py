from django.contrib import admin
from rents.models import Customer, Product, Rent, RentDetail, Revert, RevertDetail, Receipt

# Register your models here.
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('name', 'tel', 'address', 'debt')
    search_fields = ('name', 'tel')

class RentDetailInline(admin.TabularInline):
    model = RentDetail
    extra = 1

class RentAdmin(admin.ModelAdmin):
    list_display = ['summary', 'rent_date']
    list_filter = ['rent_date']
    search_fields = ['customer__name']
    inlines = [RentDetailInline]

class RevertDetailInline(admin.TabularInline):
    model = RevertDetail
    extra = 1

class RevertAdmin(admin.ModelAdmin):
    list_display = ['summary', 'revert_date']
    list_filter = ['revert_date']
    search_fields = ['customer__name']
    inlines = [RevertDetailInline]

class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_price', 'unit')

class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('summary', 'receipt_date')

admin.site.register(Customer, CustomerAdmin)
admin.site.register(Product, ProductAdmin)

admin.site.register(Rent, RentAdmin)
admin.site.register(Revert, RevertAdmin)

admin.site.register(Receipt, ReceiptAdmin)
