"""
URL configuration for the tickets app.
"""

from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    # Ticket listing and dashboard
    path('', views.TicketListView.as_view(), name='list'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('search/', views.search_tickets_api, name='search_api'),
    path('export/', views.ticket_export, name='export'),
    
    # Ticket CRUD
    path('create/', views.TicketCreateView.as_view(), name='create'),
    path('<str:ticket_id>/', views.TicketDetailView.as_view(), name='detail'),
    path('<str:ticket_id>/edit/', views.TicketUpdateView.as_view(), name='edit'),
    
    # Ticket actions
    path('<str:ticket_id>/assign/', views.ticket_assign, name='assign'),
    path('<str:ticket_id>/status/', views.ticket_status_change, name='status_change'),
    
    # Bulk actions
    path('bulk-action/', views.ticket_bulk_action, name='bulk_action'),
    
    # Templates
    path('templates/', views.template_list, name='template_list'),
    path('templates/create/', views.template_create, name='template_create'),
    path('templates/<int:pk>/edit/', views.template_edit, name='template_edit'),
    path('templates/<int:pk>/delete/', views.template_delete, name='template_delete'),
    
    # Categories
    path('categories/', views.category_list, name='category_list'),
    
    # Attachments
    path('attachments/<int:attachment_id>/download/', views.download_attachment, name='download_attachment'),
]