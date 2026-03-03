"""
API serializers for the support ticket system.
"""

from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from apps.tickets.models import Ticket, TicketComment, TicketAttachment, Category
from apps.accounts.models import User

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for user data.
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'full_name',
            'user_type', 'profile_picture', 'phone_number',
            'department', 'job_title', 'company', 'is_active'
        ]
        read_only_fields = ['id', 'email']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed user serializer with statistics.
    """
    ticket_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = UserSerializer.Meta.fields + [
            'last_login', 'date_joined', 'last_activity',
            'email_notifications', 'ticket_assigned_notifications',
            'ticket_updated_notifications', 'ticket_stats'
        ]
        read_only_fields = UserSerializer.Meta.read_only_fields + [
            'last_login', 'date_joined', 'last_activity'
        ]
    
    def get_ticket_stats(self, obj):
        """Get ticket statistics for the user."""
        if obj.is_customer():
            tickets = Ticket.objects.filter(created_by=obj)
        elif obj.is_agent() or obj.is_admin():
            tickets = Ticket.objects.filter(assigned_to=obj)
        else:
            return {}
        
        return {
            'total': tickets.count(),
            'open': tickets.filter(status__in=['new', 'open', 'in_progress']).count(),
            'resolved': tickets.filter(status='resolved').count(),
            'closed': tickets.filter(status='closed').count(),
        }


class CategorySerializer(serializers.ModelSerializer):
    """
    Serializer for ticket categories.
    """
    full_path = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'slug', 'parent',
            'full_path', 'sla_response_time', 'sla_resolution_time',
            'is_active', 'order'
        ]
    
    def get_full_path(self, obj):
        return obj.get_full_path()


class TicketCommentSerializer(serializers.ModelSerializer):
    """
    Serializer for ticket comments.
    """
    user = UserSerializer(read_only=True)
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    attachments = serializers.SerializerMethodField()
    
    class Meta:
        model = TicketComment
        fields = [
            'id', 'ticket', 'user', 'user_name', 'comment_type',
            'content', 'created_at', 'updated_at', 'attachments'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_attachments(self, obj):
        """Get attachments for this comment."""
        attachments = obj.attachments.all()
        return [
            {
                'id': att.id,
                'filename': att.filename,
                'file_size': att.file_size,
                'url': att.file.url if att.file else None
            }
            for att in attachments
        ]


class TicketAttachmentSerializer(serializers.ModelSerializer):
    """
    Serializer for ticket attachments.
    """
    uploaded_by = UserSerializer(read_only=True)
    
    class Meta:
        model = TicketAttachment
        fields = [
            'id', 'ticket', 'comment', 'file', 'filename',
            'file_size', 'content_type', 'uploaded_by', 'uploaded_at'
        ]
        read_only_fields = ['id', 'uploaded_at', 'file_size', 'content_type']


class TicketListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for ticket list views.
    """
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    comment_count = serializers.IntegerField(source='comments.count', read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_id', 'title', 'status', 'priority',
            'created_by', 'assigned_to', 'category', 'category_name',
            'created_at', 'updated_at', 'due_by', 'comment_count',
            'sla_response_breached', 'sla_resolution_breached'
        ]
        read_only_fields = ['ticket_id', 'created_at', 'updated_at']


class TicketDetailSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for single ticket view.
    """
    created_by = UserSerializer(read_only=True)
    assigned_to = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    comments = TicketCommentSerializer(many=True, read_only=True)
    attachments = TicketAttachmentSerializer(many=True, read_only=True)
    tags = serializers.ListField(child=serializers.CharField(), read_only=True)
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_id', 'title', 'description', 'status', 'priority',
            'source', 'created_by', 'assigned_to', 'category', 'tags',
            'created_at', 'updated_at', 'due_by', 'resolved_at', 'closed_at',
            'first_response_at', 'comments', 'attachments', 'cc_emails',
            'sla_response_due', 'sla_resolution_due',
            'sla_response_breached', 'sla_resolution_breached',
            'response_time', 'resolution_time', 'reopen_count'
        ]
        read_only_fields = [
            'ticket_id', 'created_at', 'updated_at', 'resolved_at',
            'closed_at', 'first_response_at', 'sla_response_due',
            'sla_resolution_due', 'response_time', 'resolution_time'
        ]


class TicketCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating new tickets.
    """
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Ticket
        fields = [
            'title', 'description', 'category', 'priority',
            'tags', 'cc_emails'
        ]
    
    def create(self, validated_data):
        """Create a new ticket."""
        tags = validated_data.pop('tags', [])
        request = self.context.get('request')
        
        ticket = Ticket.objects.create(
            **validated_data,
            created_by=request.user,
            source='api',
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        # Add tags
        if tags:
            ticket.tags.add(*tags)
        
        return ticket


class TicketUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating tickets.
    """
    tags = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        write_only=True
    )
    
    class Meta:
        model = Ticket
        fields = [
            'title', 'description', 'status', 'priority',
            'assigned_to', 'category', 'tags', 'internal_notes'
        ]
    
    def update(self, instance, validated_data):
        """Update an existing ticket."""
        tags = validated_data.pop('tags', None)
        
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update tags if provided
        if tags is not None:
            instance.tags.set(*tags)
        
        return instance


class TicketCommentCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating ticket comments.
    """
    class Meta:
        model = TicketComment
        fields = ['content', 'comment_type']
    
    def create(self, validated_data):
        """Create a new comment."""
        ticket_id = self.context.get('ticket_id')
        request = self.context.get('request')
        
        try:
            ticket = Ticket.objects.get(ticket_id=ticket_id)
        except Ticket.DoesNotExist:
            raise serializers.ValidationError({"ticket": "Ticket not found"})
        
        # Check permissions
        if request.user.is_customer() and ticket.created_by != request.user:
            raise serializers.ValidationError({"permission": "Cannot comment on this ticket"})
        
        comment = TicketComment.objects.create(
            ticket=ticket,
            user=request.user,
            **validated_data,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        
        return comment