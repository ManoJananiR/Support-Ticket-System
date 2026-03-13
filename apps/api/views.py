"""
API views for the support ticket system.
"""

from rest_framework import generics, permissions, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Count
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .serializers import (
    UserSerializer, UserDetailSerializer, CategorySerializer,
    TicketListSerializer, TicketDetailSerializer, TicketCreateSerializer,
    TicketUpdateSerializer, TicketCommentSerializer, TicketCommentCreateSerializer
)
from apps.tickets.models import Ticket, TicketComment, Category
from apps.accounts.models import User
from apps.tickets.filters import TicketFilter
from apps.core.permissions import IsAdminOrReadOnly, IsOwnerOrAgentOrAdmin


class StandardResultsSetPagination(PageNumberPagination):
    """Standard pagination for API results."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for viewing users.
    """
    queryset = User.objects.filter(is_active=True).order_by('email')
    serializer_class = UserSerializer
    pagination_class = StandardResultsSetPagination
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Use different serializers for list and detail views."""
        if self.action == 'retrieve':
            return UserDetailSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Get current user details."""
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def agents(self, request):
        """Get all agents."""
        agents = self.queryset.filter(user_type__in=['agent', 'admin'])
        page = self.paginate_queryset(agents)
        serializer = self.get_serializer(page, many=True)
        return self.get_paginated_response(serializer.data)


class CategoryViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing categories.
    """
    queryset = Category.objects.filter(is_active=True).order_by('order', 'name')
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = 'slug'
    
    def perform_create(self, serializer):
        """Set additional fields on create."""
        serializer.save()


class TicketViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing tickets.
    """
    queryset = Ticket.objects.all().order_by('-created_at')
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = TicketFilter
    lookup_field = 'ticket_id'
    
    def get_queryset(self):
        """Filter queryset based on user role."""
        user = self.request.user
        
        queryset = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'category'
        ).prefetch_related('comments', 'tags')
        
        if user.is_customer():
            return queryset.filter(created_by=user)
        elif user.is_agent():
            return queryset.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True)
            )
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == 'list':
            return TicketListSerializer
        elif self.action == 'create':
            return TicketCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TicketUpdateSerializer
        return TicketDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action == 'create':
            permission_classes = [permissions.IsAuthenticated]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsOwnerOrAgentOrAdmin]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Create a new ticket."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def assign(self, request, ticket_id=None):
        """Assign ticket to an agent."""
        ticket = self.get_object()
        
        if not request.user.can_manage_tickets():
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        agent_id = request.data.get('agent_id')
        if not agent_id:
            return Response(
                {"error": "agent_id required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            agent = User.objects.get(id=agent_id, user_type__in=['agent', 'admin'])
            ticket.assign_to_agent(agent)
            
            serializer = self.get_serializer(ticket)
            return Response(serializer.data)
        except User.DoesNotExist:
            return Response(
                {"error": "Agent not found"},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def status(self, request, ticket_id=None):
        """Change ticket status."""
        ticket = self.get_object()
        
        if not request.user.can_manage_tickets() and request.user != ticket.created_by:
            return Response(
                {"error": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )
        
        new_status = request.data.get('status')
        if not new_status or new_status not in dict(Ticket.STATUS_CHOICES):
            return Response(
                {"error": "Invalid status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket.status = new_status
        ticket.save()
        
        serializer = self.get_serializer(ticket)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def comments(self, request, ticket_id=None):
        """Get all comments for a ticket."""
        ticket = self.get_object()
        comments = ticket.comments.select_related('user').order_by('created_at')
        
        page = self.paginate_queryset(comments)
        serializer = TicketCommentSerializer(page, many=True)
        return self.get_paginated_response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def comments(self, request, ticket_id=None):
        """Add a comment to a ticket."""
        ticket = self.get_object()
        
        serializer = TicketCommentCreateSerializer(
            data=request.data,
            context={'request': request, 'ticket_id': ticket_id}
        )
        
        if serializer.is_valid():
            comment = serializer.save()
            return Response(
                TicketCommentSerializer(comment).data,
                status=status.HTTP_201_CREATED
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def attachments(self, request, ticket_id=None):
        """Get all attachments for a ticket."""
        ticket = self.get_object()
        attachments = ticket.attachments.all().order_by('-uploaded_at')
        
        from .serializers import TicketAttachmentSerializer
        serializer = TicketAttachmentSerializer(attachments, many=True)
        return Response(serializer.data)


class DashboardStatsView(generics.GenericAPIView):
    """
    API endpoint for dashboard statistics.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, format=None):
        """Get dashboard statistics."""
        user = request.user
        now = timezone.now()
        
        # Base queryset based on user role
        if user.is_admin():
            tickets = Ticket.objects.all()
        elif user.is_agent():
            tickets = Ticket.objects.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True)
            )
        else:
            tickets = Ticket.objects.filter(created_by=user)
        
        stats = {
            'total': tickets.count(),
            'by_status': tickets.values('status').annotate(count=Count('id')),
            'by_priority': tickets.values('priority').annotate(count=Count('id')),
            'overdue': tickets.filter(
                due_by__lt=now
            ).exclude(status__in=['resolved', 'closed']).count(),
            'sla_breached': {
                'response': tickets.filter(sla_response_breached=True).count(),
                'resolution': tickets.filter(sla_resolution_breached=True).count(),
            }
        }
        
        # Recent activity
        recent_tickets = tickets.order_by('-created_at')[:5].values(
            'ticket_id', 'title', 'status', 'created_at'
        )
        stats['recent_tickets'] = list(recent_tickets)
        
        return Response(stats)


@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def search_tickets(request):
    """
    Search tickets API endpoint.
    """
    query = request.GET.get('q', '')
    if len(query) < 2:
        return Response({'results': []})
    
    user = request.user
    tickets = Ticket.objects.filter(
        Q(ticket_id__icontains=query) |
        Q(title__icontains=query) |
        Q(description__icontains=query)
    )
    
    # Apply role-based filtering
    if user.is_customer():
        tickets = tickets.filter(created_by=user)
    elif user.is_agent():
        tickets = tickets.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True)
        )
    
    tickets = tickets.select_related('created_by')[:20]
    
    results = [
        {
            'id': ticket.id,
            'ticket_id': ticket.ticket_id,
            'title': ticket.title,
            'status': ticket.get_status_display(),
            'priority': ticket.get_priority_display(),
            'created_by': ticket.created_by.get_full_name(),
            'created_at': ticket.created_at.isoformat(),
        }
        for ticket in tickets
    ]
    
    return Response({'results': results})