from django.urls import path
from . import views

app_name = 'tickets'

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Admin - Agent Management
    path('agents/', views.agent_list, name='agent_list'),
    path('agents/create/', views.agent_create, name='agent_create'),
    path('agents/<int:pk>/edit/', views.agent_edit, name='agent_edit'),
    path('agents/<int:pk>/tickets/', views.agent_tickets, name='agent_tickets'),
    path('agents/bulk-assign/', views.bulk_assign, name='bulk_assign'),
    
    # Export
    path('export/', views.ticket_export, name='export'),
    
    # Ticket listing and creation
    path('', views.TicketListView.as_view(), name='list'),
    path('create/', views.TicketCreateView.as_view(), name='create'),
    
    # Ticket detail and edit - THESE MUST BE LAST
    path('<str:ticket_id>/', views.TicketDetailView.as_view(), name='detail'),
    path('<str:ticket_id>/edit/', views.TicketUpdateView.as_view(), name='edit'),
    path('<str:ticket_id>/assign/', views.ticket_assign, name='assign'),
    path('<str:ticket_id>/status/', views.ticket_status_change, name='status_change'),
]