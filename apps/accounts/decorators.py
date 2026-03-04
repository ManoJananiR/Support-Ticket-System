"""
Decorators for role-based access control.
"""

from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from functools import wraps


def role_required(allowed_roles=[]):
    """
    Decorator to check if user has required role.
    Usage: @role_required(['admin', 'agent'])
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(request, 'Please login to access this page.')
                return redirect('accounts:login')
            
            # Check if user has any of the allowed roles
            if request.user.user_type in allowed_roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied("You don't have permission to access this page.")
        return _wrapped_view
    return decorator


def customer_required(view_func):
    """Decorator for customer-only views."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('accounts:login')
        if request.user.is_customer():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("This page is only for customers.")
    return _wrapped_view


def agent_required(view_func):
    """Decorator for agent-only views."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('accounts:login')
        if request.user.is_agent() or request.user.is_admin():
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("This page is only for agents.")
    return _wrapped_view


def admin_required(view_func):
    """Decorator for admin-only views."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please login to access this page.')
            return redirect('accounts:login')
        if request.user.is_admin() or request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        raise PermissionDenied("This page is only for administrators.")
    return _wrapped_view