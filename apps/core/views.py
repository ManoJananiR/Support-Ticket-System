from django.shortcuts import render
from django.views.generic import TemplateView
from apps.core.utils import send_notification_async

class HomeView(TemplateView):
    template_name = 'home.html'

    def form_valid(self, form):
        ticket = form.save()
        send_notification_async.delay(ticket.id, 'created')
        return super().form_valid(form)

