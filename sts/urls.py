from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    # Public home page
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    
    # Django Admin
    path('admin/', admin.site.urls),
    
    # Custom Admin URLs (for customer management)
    path('admin/accounts/', include('apps.accounts.admin_urls')),
    
    # Accounts app
    path('accounts/', include('apps.accounts.urls')),

    path('customers/', include('apps.customers.urls')),
    
    # Tickets app
    path('tickets/', include('apps.tickets.urls')),
    
    # API
    path('api/', include('apps.api.urls')),
]

# Debug Toolbar URLs (only in development)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    try:
        import debug_toolbar
        urlpatterns += [
            path('__debug__/', include(debug_toolbar.urls)),
        ]
    except ImportError:
        pass