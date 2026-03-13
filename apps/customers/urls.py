from django.urls import path
from . import views

app_name = 'customers'

urlpatterns = [
    path('', views.customer_list, name='customer_list'),
    path('add/', views.customer_add, name='customer_add'),
    path('import/', views.customer_import, name='customer_import'),
    path('import/results/', views.import_results, name='import_results'),
    path('import/bulk/', views.bulk_customer_import, name='bulk_customer_import'),
    path('export/', views.customer_export, name='customer_export'),
    path('download-template/', views.download_sample_template, name='download_sample_template'),
    path('password-reset/bulk/', views.customer_bulk_password_reset, name='customer_bulk_password_reset'),
    path('password-reset/results/', views.password_reset_results, name='password_reset_results'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    path('<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('<int:pk>/tickets/', views.customer_tickets, name='customer_tickets'),
    path('<int:pk>/toggle-status/', views.customer_toggle_status, name='customer_toggle_status'),
    path('<int:pk>/reset-password/', views.customer_reset_password, name='customer_reset_password'),
    path('<int:pk>/generate-password/', views.customer_generate_random_password, name='customer_generate_random_password'),
]