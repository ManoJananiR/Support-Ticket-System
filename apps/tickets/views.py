"""
Views for ticket management with role-based access control.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Avg, F, OuterRef, Subquery, IntegerField
from django.db.models.functions import TruncDate
from django.utils import timezone
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse, FileResponse
from django.views.decorators.http import require_POST
from django.core.exceptions import PermissionDenied
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.conf import settings
from django.db import transaction
from datetime import timedelta
import csv
import logging

from .models import Ticket, TicketComment, TicketAttachment, Category, TicketHistory, TicketTemplate
from .forms import (
    TicketCreateForm, TicketUpdateForm, TicketCommentForm, 
    TicketBulkActionForm, TicketTemplateForm, AgentTicketUpdateForm
)
from apps.accounts.models import User
from apps.accounts.forms import AgentCreateForm, AgentEditForm
from apps.core.utils import log_activity

logger = logging.getLogger(__name__)

class TicketListView(LoginRequiredMixin, ListView):
    """
    View for listing tickets with filtering and pagination.
    """
    model = Ticket
    template_name = 'tickets/ticket_list.html'
    context_object_name = 'tickets'
    paginate_by = 20
    
    def get_queryset(self):
        """
        Get filtered queryset based on user role and search parameters.
        """
        queryset = Ticket.objects.select_related(
            'created_by', 'assigned_to', 'category'
        ).prefetch_related('tags')
        
        # Filter based on user role
        user = self.request.user
        if user.is_customer():
            # Customers see only their own tickets
            queryset = queryset.filter(created_by=user)
        elif user.is_agent():
            # Agents see tickets assigned to them
            queryset = queryset.filter(assigned_to=user)
        elif user.is_admin():
            # Admins see all tickets (with optional filters)
            queryset = queryset
        
        # Check for unassigned filter in URL
        if self.request.GET.get('assigned_to__isnull') == 'True':
            queryset = queryset.filter(assigned_to__isnull=True)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """
        Add additional context data.
        """
        context = super().get_context_data(**kwargs)
        
        # Add statistics
        tickets = self.get_queryset()
        context['stats'] = {
            'total': tickets.count(),
            'open': tickets.filter(status__in=['new', 'open', 'in_progress', 'pending']).count(),
            'resolved': tickets.filter(status='resolved').count(),
            'overdue': tickets.filter(due_by__lt=timezone.now()).exclude(
                status__in=['resolved', 'closed']
            ).count(),
        }
        
        # Add page title based on role and filters
        user = self.request.user
        if self.request.GET.get('assigned_to__isnull') == 'True':
            context['page_title'] = 'Unassigned Tickets'
        elif user.is_customer():
            context['page_title'] = 'My Tickets'
        elif user.is_agent():
            context['page_title'] = 'Assigned Tickets'
        elif user.is_admin():
            context['page_title'] = 'All Tickets'
        
        # Add available actions based on user role
        context['can_bulk_edit'] = self.request.user.is_admin()
        
        # Add empty state message
        if not context['tickets']:
            if self.request.GET.get('assigned_to__isnull') == 'True':
                context['empty_message'] = 'No unassigned tickets found.'
                context['empty_icon'] = 'fa-inbox'
            else:
                context['empty_message'] = 'No tickets found.'
                context['empty_icon'] = 'fa-ticket-alt'
        
        return context
    
class TicketDetailView(LoginRequiredMixin, DetailView):
    """
    View for displaying ticket details with comments and attachments.
    """
    model = Ticket
    template_name = 'tickets/ticket_detail.html'
    context_object_name = 'ticket'
    slug_field = 'ticket_id'
    slug_url_kwarg = 'ticket_id'
    
    def get_object(self, queryset=None):
        """
        Get ticket object and check permissions.
        """
        ticket = super().get_object(queryset)
        user = self.request.user
        
        # Check if user has permission to view this ticket
        if user.is_customer() and ticket.created_by != user:
            raise PermissionDenied("You don't have permission to view this ticket.")
        
        if user.is_agent() and ticket.assigned_to and ticket.assigned_to != user:
            # Agents can view but with warning
            messages.warning(self.request, "You are viewing a ticket assigned to another agent.")
        
        return ticket
    
    def get_context_data(self, **kwargs):
        """
        Add comments and forms to context.
        """
        context = super().get_context_data(**kwargs)
        ticket = self.object
        
        # Get comments
        context['comments'] = ticket.comments.select_related('user').order_by('created_at')
        
        # Get attachments
        context['attachments'] = ticket.attachments.select_related('uploaded_by').order_by('-uploaded_at')
        
        # Add forms
        context['comment_form'] = TicketCommentForm(user=self.request.user, ticket=ticket)
        
        # Check if user can edit ticket
        if self.request.user.is_admin():
            context['can_edit'] = True
        elif self.request.user.is_agent() and ticket.assigned_to == self.request.user:
            context['can_edit'] = True
        else:
            context['can_edit'] = False
        
        # Get ticket history
        context['history'] = ticket.history.select_related('user').order_by('-timestamp')[:10]
        
        # Add agents list for assignment dropdown (for admins)
        if self.request.user.is_admin():
            context['agents'] = User.objects.filter(
                user_type__in=['agent', 'admin'], 
                is_active=True
            ).order_by('first_name', 'last_name')
        
        return context
    
    def post(self, request, *args, **kwargs):
        """
        Handle comment submission.
        """
        self.object = self.get_object()
        ticket = self.object
        
        form = TicketCommentForm(
            request.POST, 
            request.FILES, 
            user=request.user, 
            ticket=ticket,
            request=request
        )
        
        if form.is_valid():
            comment = form.save()
            
            # Handle file attachments if any
            files = request.FILES.getlist('attachments')
            for file in files:
                attachment = TicketAttachment(
                    ticket=ticket,
                    comment=comment,
                    file=file,
                    uploaded_by=request.user
                )
                attachment.save()
            
            messages.success(request, 'Your comment has been added.')
            return redirect('tickets:detail', ticket_id=ticket.ticket_id)
        else:
            # Re-render the page with form errors
            context = self.get_context_data()
            context['comment_form'] = form
            return self.render_to_response(context)

class TicketCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    View for creating new tickets - FOR CUSTOMERS AND ADMINS
    """
    model = Ticket
    form_class = TicketCreateForm
    template_name = 'tickets/ticket_form.html'
    
    def test_func(self):
        """Customers AND ADMINS can create tickets"""
        user = self.request.user
        return user.is_customer() or user.is_admin()
    
    def handle_no_permission(self):
        """Redirect if not authorized"""
        messages.error(self.request, "Only customers and admins can create new tickets.")
        return redirect('tickets:dashboard')
    
    def get_form_kwargs(self):
        """
        Pass user and request to form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['request'] = self.request
        return kwargs
    
    def get_context_data(self, **kwargs):
        """
        Add templates to context.
        """
        context = super().get_context_data(**kwargs)
        context['templates'] = TicketTemplate.objects.filter(is_active=True)
        context['is_create'] = True
        context['is_admin'] = self.request.user.is_admin()
        
        # Add agents list for admin assignment
        if self.request.user.is_admin():
            from apps.accounts.models import User
            context['agents'] = User.objects.filter(
                user_type__in=['agent', 'admin'], 
                is_active=True
            ).order_by('first_name', 'last_name')
        
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            ticket = form.save()
            
            # Admin can optionally assign immediately
            if self.request.user.is_admin():
                agent_id = self.request.POST.get('assign_to')
                if agent_id:
                    try:
                        from apps.accounts.models import User
                        agent = User.objects.get(id=agent_id, user_type__in=['agent', 'admin'])
                        ticket.assigned_to = agent
                        ticket.save()
                    except User.DoesNotExist:
                        pass
            
            # Create history entry
            action = 'created_by_admin' if self.request.user.is_admin() else 'created'
            TicketHistory.objects.create(
                ticket=ticket,
                user=self.request.user,
                action=action,
                changes={'title': ticket.title},
                ip_address=self.get_client_ip()
            )
            
            messages.success(self.request, f'Ticket {ticket.ticket_id} has been created successfully.')
            
        return redirect('tickets:detail', ticket_id=ticket.ticket_id)
    
    def get_client_ip(self):
        """Get client IP address."""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
class TicketUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    View for updating tickets - different forms for different roles
    """
    model = Ticket
    template_name = 'tickets/ticket_edit.html'  # Changed from 'tickets/ticket_form.html'
    slug_field = 'ticket_id'
    slug_url_kwarg = 'ticket_id'
    
    def get_form_class(self):
        """Return different form based on user role"""
        user = self.request.user
        if user.is_agent():
            return AgentTicketUpdateForm  # Agents get restricted form
        else:
            return TicketUpdateForm  # Admins get full form
    
    def test_func(self):
        """
        Check if user has permission to update the ticket.
        """
        ticket = self.get_object()
        user = self.request.user
        
        # Agents can only edit tickets assigned to them
        if user.is_agent():
            return ticket.assigned_to == user
        
        # Admins can edit any ticket
        return user.is_admin()
    
    def handle_no_permission(self):
        """Handle users without permission"""
        messages.error(self.request, "You don't have permission to edit this ticket.")
        return redirect('tickets:dashboard')  # Redirect to dashboard
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_agent'] = self.request.user.is_agent()
        context['is_admin'] = self.request.user.is_admin()
        return context
    
    def form_valid(self, form):
        with transaction.atomic():
            ticket = form.save()
            
            # Track changes for history
            changes = {}
            if hasattr(form, 'changed_data'):
                changed_fields = []
                for field in form.changed_data:
                    changed_fields.append(field)
                if changed_fields:
                    changes['fields_updated'] = changed_fields
            
            # Create history entry
            TicketHistory.objects.create(
                ticket=ticket,
                user=self.request.user,
                action='updated',
                changes=changes,
                ip_address=self.get_client_ip()
            )
            
            messages.success(self.request, f'Ticket {ticket.ticket_id} has been updated.')
        
        # Redirect to dashboard after successful update
        return redirect('tickets:dashboard')
    
    def form_invalid(self, form):
        """Handle invalid form submission"""
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
    
    def get_client_ip(self):
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    
@login_required
@require_POST
def ticket_assign(request, ticket_id):
    """
    Assign ticket to an agent and send email notification.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Check permissions
    if not request.user.is_admin():
        return HttpResponseForbidden("Only admins can assign tickets.")
    
    agent_id = request.POST.get('agent_id')
    if not agent_id:
        messages.error(request, "Please select an agent.")
        return redirect('tickets:detail', ticket_id=ticket_id)
    
    try:
        agent = User.objects.get(id=agent_id, user_type__in=['agent', 'admin'])
        old_agent = ticket.assigned_to
        ticket.assign_to_agent(agent)
        
        # Create history entry
        TicketHistory.objects.create(
            ticket=ticket,
            user=request.user,
            action='assigned',
            changes={'assigned_to': agent.get_full_name()},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        messages.success(request, f'Ticket assigned to {agent.get_full_name()}')
        
    except User.DoesNotExist:
        messages.error(request, "Invalid agent selected.")
    
    return redirect('tickets:detail', ticket_id=ticket_id)

@login_required
@require_POST
def ticket_status_change(request, ticket_id):
    """
    Change ticket status - with transaction optimization
    """
    # Get the ticket with select_for_update to lock it
    ticket = get_object_or_404(Ticket.objects.select_for_update(skip_locked=True), ticket_id=ticket_id)
    
    # Check permissions
    if not request.user.can_manage_tickets() and request.user != ticket.created_by:
        return HttpResponseForbidden("You don't have permission to change ticket status.")
    
    new_status = request.POST.get('status')
    if new_status not in dict(Ticket.STATUS_CHOICES):
        messages.error(request, "Invalid status.")
        return redirect('tickets:detail', ticket_id=ticket_id)
    
    try:
        # Use atomic transaction but keep it short
        with transaction.atomic():
            old_status = ticket.status
            ticket.status = new_status
            
            # Handle special status changes
            if new_status == 'resolved' and not ticket.resolved_at:
                ticket.resolved_at = timezone.now()
            elif new_status == 'closed' and not ticket.closed_at:
                ticket.closed_at = timezone.now()
            elif new_status == 'reopened':
                ticket.reopened_at = timezone.now()
                ticket.reopen_count += 1
            
            ticket.save()
            
            # Create history entry (do this quickly)
            TicketHistory.objects.create(
                ticket=ticket,
                user=request.user,
                action='status_changed',
                changes={'old_status': old_status, 'new_status': new_status},
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        messages.success(request, f'Ticket status changed to {ticket.get_status_display()}')
        
    except Exception as e:
        logger.error(f"Error changing ticket status: {str(e)}")
        messages.error(request, "An error occurred. Please try again.")
    
    return redirect('tickets:detail', ticket_id=ticket_id)

@login_required
def ticket_export(request):
    """
    Export tickets to CSV.
    """
    if not request.user.is_admin():
        return HttpResponseForbidden("Only admins can export tickets.")
    
    # Get filtered tickets
    queryset = Ticket.objects.select_related('created_by', 'assigned_to', 'category')
    tickets = queryset.all()
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tickets_export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Ticket ID', 'Title', 'Status', 'Priority', 'Category', 
        'Created By', 'Assigned To', 'Created At', 'Resolved At',
        'Response Time (hours)', 'Resolution Time (hours)'
    ])
    
    for ticket in tickets:
        writer.writerow([
            ticket.ticket_id,
            ticket.title,
            ticket.get_status_display(),
            ticket.get_priority_display(),
            ticket.category.name if ticket.category else '',
            ticket.created_by.email,
            ticket.assigned_to.email if ticket.assigned_to else '',
            ticket.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            ticket.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if ticket.resolved_at else '',
            ticket.time_to_first_response.total_seconds() / 3600 if ticket.time_to_first_response else '',
            ticket.time_to_resolution.total_seconds() / 3600 if ticket.time_to_resolution else '',
        ])
    
    logger.info(f"Tickets exported by {request.user.email}")
    return response


@login_required
def dashboard(request):
    """Main dashboard view with statistics and charts."""
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
    
    # Get tickets by status
    tickets_by_status = []
    status_counts = tickets.values('status').annotate(count=Count('id')).order_by('status')
    status_dict = dict(Ticket.STATUS_CHOICES)
    for item in status_counts:
        tickets_by_status.append({
            'status': item['status'],
            'get_status_display': status_dict.get(item['status'], item['status']),
            'count': item['count']
        })
    
    # Tickets by priority
    tickets_by_priority = []
    priority_counts = tickets.values('priority').annotate(count=Count('id')).order_by('priority')
    priority_dict = dict(Ticket.PRIORITY_CHOICES)
    for item in priority_counts:
        tickets_by_priority.append({
            'priority': item['priority'],
            'get_priority_display': priority_dict.get(item['priority'], item['priority']),
            'count': item['count']
        })
    
    # Daily trend (last 7 days)
    last_week = now - timedelta(days=7)
    daily_trend = tickets.filter(
        created_at__gte=last_week
    ).annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    context = {
        'total_tickets': tickets.count(),
        'open_tickets': tickets.filter(status__in=['new', 'open', 'in_progress', 'pending']).count(),
        'resolved_tickets': tickets.filter(status='resolved').count(),
        'closed_tickets': tickets.filter(status='closed').count(),
        'overdue_tickets': tickets.filter(
            due_by__lt=now
        ).exclude(status__in=['resolved', 'closed']).count(),
        'tickets_by_status': tickets_by_status,
        'tickets_by_priority': tickets_by_priority,
        'daily_trend': daily_trend,
        'recent_tickets': tickets.select_related(
            'created_by', 'assigned_to'
        ).order_by('-created_at')[:10],
        'sla_performance': {
            'response_breached': tickets.filter(sla_response_breached=True).count(),
            'resolution_breached': tickets.filter(sla_resolution_breached=True).count(),
            'on_track': tickets.exclude(
                Q(sla_response_breached=True) | Q(sla_resolution_breached=True)
            ).filter(
                status__in=['new', 'open', 'in_progress']
            ).count(),
        }
    }
    
    # Add agent stats if admin
    if user.is_admin():
        agents = User.objects.filter(user_type='agent', is_active=True)
        
        agent_stats_list = []
        for agent in agents:
            assigned_count = Ticket.objects.filter(assigned_to=agent).count()
            resolved_count = Ticket.objects.filter(assigned_to=agent, status='resolved').count()
            
            avg_response = Ticket.objects.filter(
                assigned_to=agent,
                response_time__isnull=False
            ).aggregate(avg=Avg('response_time'))['avg']
            
            agent_stats_list.append({
                'id': agent.id,
                'email': agent.email,
                'first_name': agent.first_name,
                'last_name': agent.last_name,
                'get_full_name': agent.get_full_name(),
                'profile_picture': agent.profile_picture,
                'is_active': agent.is_active,
                'assigned_tickets': assigned_count,
                'resolved_tickets': resolved_count,
                'avg_response_time': avg_response,
            })
        
        agent_stats_list.sort(key=lambda x: x['resolved_tickets'], reverse=True)
        context['agent_stats'] = agent_stats_list
    
    return render(request, 'dashboard/dashboard.html', context)


@login_required
def ticket_delete(request, ticket_id):
    """Allow admins to delete tickets"""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can delete tickets.")
    
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    if request.method == 'POST':
        ticket_id_str = ticket.ticket_id
        ticket.delete()
        messages.success(request, f'Ticket {ticket_id_str} has been deleted successfully.')
        return redirect('tickets:list')
    
    return render(request, 'tickets/ticket_confirm_delete.html', {'ticket': ticket})


@login_required
def agent_list(request):
    """List all agents with their statistics."""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can view agent list.")
    
    agents = User.objects.filter(user_type='agent', is_active=True)
    
    # Create a list of agent stats dictionaries
    agent_stats = []
    for agent in agents:
        assigned_count = Ticket.objects.filter(assigned_to=agent).count()
        resolved_count = Ticket.objects.filter(assigned_to=agent, status='resolved').count()
        
        agent_stats.append({
            'agent': agent,
            'assigned_tickets': assigned_count,
            'resolved_tickets': resolved_count,
            'full_name': agent.get_full_name() or agent.email,
        })
    
    # Get unassigned tickets for quick assignment
    unassigned_tickets = Ticket.objects.filter(assigned_to__isnull=True).exclude(
        status__in=['resolved', 'closed']
    )[:10]
    
    return render(request, 'tickets/agent_list.html', {
        'agent_stats': agent_stats,
        'agents': agents,
        'unassigned_tickets': unassigned_tickets
    })


@login_required
def agent_create(request):
    """Create a new agent."""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can create agents.")
    
    if request.method == 'POST':
        form = AgentCreateForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save(commit=False)
            user.user_type = 'agent'
            user.is_staff = True
            user.save()
            messages.success(request, f'Agent {user.get_full_name()} created successfully.')
            return redirect('tickets:agent_list')
    else:
        form = AgentCreateForm()
    
    return render(request, 'tickets/agent_form.html', {'form': form, 'is_create': True})


@login_required
def agent_edit(request, pk):
    """Edit an existing agent."""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can edit agents.")
    
    agent = get_object_or_404(User, pk=pk, user_type='agent')
    
    if request.method == 'POST':
        form = AgentEditForm(request.POST, request.FILES, instance=agent)
        if form.is_valid():
            form.save()
            messages.success(request, f'Agent updated successfully.')
            return redirect('tickets:agent_list')
    else:
        form = AgentEditForm(instance=agent)
    
    return render(request, 'tickets/agent_form.html', {'form': form, 'is_create': False})


@login_required
def agent_tickets(request, pk):
    """View tickets assigned to a specific agent."""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can view agent tickets.")
    
    agent = get_object_or_404(User, pk=pk, user_type='agent')
    tickets = Ticket.objects.filter(assigned_to=agent).order_by('-created_at')
    
    # Calculate statistics
    tickets_open = tickets.filter(status__in=['new', 'open', 'in_progress', 'pending']).count()
    tickets_resolved = tickets.filter(status='resolved').count()
    tickets_closed = tickets.filter(status='closed').count()
    
    return render(request, 'tickets/agent_tickets.html', {
        'agent': agent,
        'tickets': tickets,
        'tickets_open': tickets_open,
        'tickets_resolved': tickets_resolved,
        'tickets_closed': tickets_closed,
    })


@login_required
@require_POST
def bulk_assign(request):
    """Assign a ticket to an agent."""
    if not request.user.is_admin():
        return HttpResponseForbidden("Only admins can assign tickets.")
    
    ticket_id = request.POST.get('ticket_id')
    agent_id = request.POST.get('agent_id')
    
    if not ticket_id or not agent_id:
        messages.error(request, "Please select both a ticket and an agent.")
        return redirect('tickets:agent_list')
    
    try:
        ticket = Ticket.objects.get(id=ticket_id)
        agent = User.objects.get(id=agent_id, user_type='agent')
        
        ticket.assigned_to = agent
        ticket.save()
        
        messages.success(request, f'Ticket {ticket.ticket_id} assigned to {agent.get_full_name()}')
    except (Ticket.DoesNotExist, User.DoesNotExist):
        messages.error(request, "Invalid ticket or agent.")
    
    return redirect('tickets:agent_list')


@login_required
def download_attachment(request, attachment_id):
    """
    Download a ticket attachment.
    """
    attachment = get_object_or_404(TicketAttachment, id=attachment_id)
    ticket = attachment.ticket
    
    # Check permissions
    user = request.user
    if user.is_customer() and ticket.created_by != user:
        return HttpResponseForbidden("You don't have permission to download this attachment.")
    
    response = FileResponse(attachment.file, as_attachment=True, filename=attachment.filename)
    return response