"""
URL configuration for sts project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.views.generic import TemplateView

urlpatterns = [

    # Public home page
    path('', TemplateView.as_view(template_name='home.html'), name='home'),

    # Admin
    path('admin/', admin.site.urls),
    
    # Accounts app - make sure this path exists
    path('accounts/', include('apps.accounts.urls')),
    
    # Tickets app
    path('tickets/', include('apps.tickets.urls')),
    
    # API
    path('api/', include('apps.api.urls')),
    
    # Root redirect to tickets dashboard
    path('', RedirectView.as_view(url='/tickets/dashboard/', permanent=True)),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    
    # Debug toolbar (optional)
    try:
        import debug_toolbar
        urlpatterns += [
            path('__debug__/', include(debug_toolbar.urls)),
        ]
    except ImportError:
        pass