from django.urls import path
from . import admin_views

urlpatterns = [
    path('customers/', admin_views.admin_customer_list, name='admin_customer_list'),
    path('customers/add/', admin_views.admin_add_customer, name='admin_add_customer'),
    path('customers/<int:customer_id>/edit/', admin_views.admin_edit_customer, name='admin_edit_customer'),
    path('customers/export/excel/', admin_views.export_customers_excel, name='export_customers_excel'),
    path('customers/export/csv/', admin_views.export_customers_csv, name='export_customers_csv'),
]