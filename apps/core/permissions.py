"""
Custom permissions for API views.
"""

from rest_framework import permissions


class IsAdminOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow admins to edit.
    """
    
    def has_permission(self, request, view):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions only for admins
        return request.user and (request.user.is_admin() or request.user.is_superuser)


class IsOwnerOrAgentOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow owners, agents or admins to edit.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions for owner, agent or admin
        return (
            obj.created_by == request.user or
            request.user.is_agent() or
            request.user.is_admin() or
            request.user.is_superuser
        )