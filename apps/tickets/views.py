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
    TicketBulkActionForm, TicketTemplateForm
)
from apps.accounts.forms import AgentCreateForm, AgentEditForm
from apps.accounts.models import User
from apps.core.utils import send_ticket_notification, log_activity

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
            # Agents see tickets assigned to them or unassigned
            queryset = queryset.filter(
                Q(assigned_to=user) | Q(assigned_to__isnull=True)
            )
        # Admins see all tickets
        
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
        
        # Add available actions based on user role
        context['can_bulk_edit'] = self.request.user.can_manage_tickets()
        
        from apps.accounts.models import User
        context['agents'] = User.objects.filter(
            user_type__in=['agent', 'admin'], 
            is_active=True
        ).order_by('first_name', 'last_name')
        
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
        context['can_edit'] = (
            self.request.user.is_admin() or 
            self.request.user == ticket.assigned_to or
            (self.request.user.is_agent() and not ticket.assigned_to)
        )
        
        # Get ticket history
        context['history'] = ticket.history.select_related('user').order_by('-timestamp')[:10]
        
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
            ticket=ticket
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
            
            # Send notifications
            send_ticket_notification(ticket, 'comment_added', comment)
            
            messages.success(request, 'Your comment has been added.')
            return redirect('tickets:detail', ticket_id=ticket.ticket_id)
        else:
            # Re-render the page with form errors
            context = self.get_context_data()
            context['comment_form'] = form
            return self.render_to_response(context)


class TicketCreateView(LoginRequiredMixin, CreateView):
    """
    View for creating new tickets.
    """
    model = Ticket
    form_class = TicketCreateForm
    template_name = 'tickets/ticket_form.html'
    
    def get_form_kwargs(self):
        """
        Pass user to form.
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
        return context
    
    def form_valid(self, form):
        """
        Handle successful form submission.
        """
        with transaction.atomic():
            ticket = form.save()
            
            # Create history entry
            TicketHistory.objects.create(
                ticket=ticket,
                user=self.request.user,
                action='created',
                changes={'title': ticket.title, 'description': ticket.description[:100]},
                ip_address=self.get_client_ip()
            )
            
            # Send notifications
            send_ticket_notification(ticket, 'created')
            
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
    View for updating tickets.
    """
    model = Ticket
    form_class = TicketUpdateForm
    template_name = 'tickets/ticket_form.html'
    slug_field = 'ticket_id'
    slug_url_kwarg = 'ticket_id'
    
    def test_func(self):
        """
        Check if user has permission to update the ticket.
        """
        ticket = self.get_object()
        user = self.request.user
        
        return (
            user.is_admin() or 
            user == ticket.assigned_to or
            (user.is_agent() and not ticket.assigned_to)
        )
    
    def get_form_kwargs(self):
        """
        Pass user to form.
        """
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        """
        Add context data.
        """
        context = super().get_context_data(**kwargs)
        context['is_create'] = False
        return context
    
    def form_valid(self, form):
        """
        Handle successful form submission.
        """
        with transaction.atomic():
            old_ticket = Ticket.objects.get(pk=self.object.pk)
            ticket = form.save()
            
            # Track changes
            changes = {}
            for field in ['status', 'priority', 'assigned_to', 'category']:
                old_value = getattr(old_ticket, field)
                new_value = getattr(ticket, field)
                if old_value != new_value:
                    changes[field] = {'old': str(old_value), 'new': str(new_value)}
            
            if changes:
                TicketHistory.objects.create(
                    ticket=ticket,
                    user=self.request.user,
                    action='updated',
                    changes=changes,
                    ip_address=self.get_client_ip()
                )
            
            # Handle assignment change
            if old_ticket.assigned_to != ticket.assigned_to:
                if ticket.assigned_to:
                    send_ticket_notification(ticket, 'assigned')
                    messages.info(
                        self.request, 
                        f'Ticket assigned to {ticket.assigned_to.get_full_name()}'
                    )
            
            messages.success(self.request, f'Ticket {ticket.ticket_id} has been updated.')
            
        return redirect('tickets:detail', ticket_id=ticket.ticket_id)
    
    def get_client_ip(self):
        """Get client IP address."""
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
    Assign ticket to an agent.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Check permissions
    if not request.user.can_manage_tickets():
        return HttpResponseForbidden("You don't have permission to assign tickets.")
    
    agent_id = request.POST.get('agent_id')
    if not agent_id:
        messages.error(request, "Please select an agent.")
        return redirect('tickets:detail', ticket_id=ticket_id)
    
    try:
        agent = User.objects.get(id=agent_id, user_type__in=['agent', 'admin'])
        ticket.assign_to_agent(agent)
        
        # Create history entry
        TicketHistory.objects.create(
            ticket=ticket,
            user=request.user,
            action='assigned',
            changes={'assigned_to': agent.get_full_name()},
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
        # Send notification
        send_ticket_notification(ticket, 'assigned')
        
        messages.success(request, f'Ticket assigned to {agent.get_full_name()}')
    except User.DoesNotExist:
        messages.error(request, "Invalid agent selected.")
    
    return redirect('tickets:detail', ticket_id=ticket_id)


@login_required
@require_POST
def ticket_status_change(request, ticket_id):
    """
    Change ticket status.
    """
    ticket = get_object_or_404(Ticket, ticket_id=ticket_id)
    
    # Check permissions
    if not request.user.can_manage_tickets() and request.user != ticket.created_by:
        return HttpResponseForbidden("You don't have permission to change ticket status.")
    
    new_status = request.POST.get('status')
    if new_status not in dict(Ticket.STATUS_CHOICES):
        messages.error(request, "Invalid status.")
        return redirect('tickets:detail', ticket_id=ticket_id)
    
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
    
    # Create history entry
    TicketHistory.objects.create(
        ticket=ticket,
        user=request.user,
        action='status_changed',
        changes={'old_status': old_status, 'new_status': new_status},
        ip_address=request.META.get('REMOTE_ADDR')
    )
    
    # Send notification
    send_ticket_notification(ticket, 'status_changed')
    
    messages.success(request, f'Ticket status changed to {ticket.get_status_display()}')
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
    
    # Add agent stats if admin - USING MANUAL COUNTING TO AVOID ANNOTATION CONFLICTS
    if user.is_admin():
        # Get all active agents
        agents = User.objects.filter(user_type='agent', is_active=True)
        
        # Manual calculation to avoid annotation conflicts
        agent_stats_list = []
        for agent in agents:
            # Count assigned tickets manually
            assigned_count = Ticket.objects.filter(assigned_to=agent).count()
            
            # Count resolved tickets manually
            resolved_count = Ticket.objects.filter(
                assigned_to=agent, 
                status='resolved'
            ).count()
            
            # Calculate average response time
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
        
        # Sort by resolved tickets (most resolved first)
        agent_stats_list.sort(key=lambda x: x['resolved_tickets'], reverse=True)
        context['agent_stats'] = agent_stats_list
    
    return render(request, 'dashboard/dashboard.html', context)

@login_required
def template_list(request):
    """
    List all ticket templates.
    """
    if not request.user.can_manage_tickets():
        return HttpResponseForbidden("You don't have permission to view templates.")
    
    templates = TicketTemplate.objects.all().order_by('name')
    
    context = {
        'templates': templates,
    }
    return render(request, 'tickets/template_list.html', context)


@login_required
def template_create(request):
    """
    Create a new ticket template.
    """
    if not request.user.can_manage_tickets():
        return HttpResponseForbidden("You don't have permission to create templates.")
    
    if request.method == 'POST':
        form = TicketTemplateForm(request.POST, user=request.user)
        if form.is_valid():
            template = form.save()
            messages.success(request, f'Template "{template.name}" created successfully.')
            return redirect('tickets:template_list')
    else:
        form = TicketTemplateForm(user=request.user)
    
    return render(request, 'tickets/template_form.html', {'form': form, 'is_create': True})


@login_required
def template_edit(request, pk):
    """
    Edit an existing ticket template.
    """
    if not request.user.can_manage_tickets():
        return HttpResponseForbidden("You don't have permission to edit templates.")
    
    template = get_object_or_404(TicketTemplate, pk=pk)
    
    if request.method == 'POST':
        form = TicketTemplateForm(request.POST, instance=template, user=request.user)
        if form.is_valid():
            template = form.save()
            messages.success(request, f'Template "{template.name}" updated successfully.')
            return redirect('tickets:template_list')
    else:
        form = TicketTemplateForm(instance=template, user=request.user)
    
    return render(request, 'tickets/template_form.html', {'form': form, 'is_create': False})


@login_required
def template_delete(request, pk):
    """
    Delete a ticket template.
    """
    if not request.user.is_admin():
        return HttpResponseForbidden("Only admins can delete templates.")
    
    template = get_object_or_404(TicketTemplate, pk=pk)
    
    if request.method == 'POST':
        name = template.name
        template.delete()
        messages.success(request, f'Template "{name}" deleted successfully.')
        return redirect('tickets:template_list')
    
    return render(request, 'tickets/template_confirm_delete.html', {'template': template})

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


@login_required
def search_tickets_api(request):
    """
    API endpoint for searching tickets (used for AJAX autocomplete).
    """
    query = request.GET.get('q', '')
    if len(query) < 3:
        return JsonResponse({'results': []})
    
    user = request.user
    tickets = Ticket.objects.filter(
        Q(ticket_id__icontains=query) | Q(title__icontains=query)
    )
    
    # Apply role-based filtering
    if user.is_customer():
        tickets = tickets.filter(created_by=user)
    elif user.is_agent():
        tickets = tickets.filter(
            Q(assigned_to=user) | Q(assigned_to__isnull=True)
        )
    
    tickets = tickets.select_related('created_by')[:10]
    
    results = [
        {
            'id': ticket.id,
            'ticket_id': ticket.ticket_id,
            'title': ticket.title,
            'status': ticket.get_status_display(),
            'created_by': ticket.created_by.get_full_name(),
        }
        for ticket in tickets
    ]
    
    return JsonResponse({'results': results})

@login_required
def agent_list(request):
    """List all agents with their statistics."""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can view agent list.")
    
    agents = User.objects.filter(user_type='agent', is_active=True)
    
    # Create a list of agent stats dictionaries instead of modifying the User objects
    agent_stats = []
    for agent in agents:
        # Calculate statistics without modifying the User object
        assigned_count = Ticket.objects.filter(assigned_to=agent).count()
        resolved_count = Ticket.objects.filter(assigned_to=agent, status='resolved').count()
        
        agent_stats.append({
            'agent': agent,  # Pass the actual agent object
            'assigned_tickets': assigned_count,
            'resolved_tickets': resolved_count,
            'full_name': agent.get_full_name() or agent.email,
        })
    
    # Get unassigned tickets for quick assignment
    unassigned_tickets = Ticket.objects.filter(assigned_to__isnull=True).exclude(
        status__in=['resolved', 'closed']
    )[:10]
    
    return render(request, 'tickets/agent_list.html', {
        'agent_stats': agent_stats,  # Pass the stats list instead of agents
        'agents': agents,  # Keep this if needed elsewhere
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
    
    return render(request, 'tickets/agent_form.html', {'form': form})


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
    
    return render(request, 'tickets/agent_form.html', {'form': form})


@login_required
def agent_tickets(request, pk):
    """View tickets assigned to a specific agent."""
    if not request.user.is_admin():
        raise PermissionDenied("Only admins can view agent tickets.")
    
    agent = get_object_or_404(User, pk=pk, user_type='agent')
    tickets = Ticket.objects.filter(assigned_to=agent).order_by('-created_at')
    
    return render(request, 'tickets/agent_tickets.html', {
        'agent': agent,
        'tickets': tickets
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