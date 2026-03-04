from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenVerifyView
)
from . import views

router = DefaultRouter()
router.register(r'tickets', views.TicketViewSet)
router.register(r'users', views.UserViewSet)
router.register(r'categories', views.CategoryViewSet)

app_name = 'api'

urlpatterns = [
    # JWT Authentication
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/verify/', TokenVerifyView.as_view(), name='token_verify'),
    
    # API endpoints
    path('', include(router.urls)),
    path('dashboard/stats/', views.DashboardStatsView.as_view(), name='dashboard-stats'),
]