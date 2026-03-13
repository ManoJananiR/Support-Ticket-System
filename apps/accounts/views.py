from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import UserProfileForm, UserNotificationSettingsForm  # Removed UserRegistrationForm
from django.urls import reverse_lazy
from .models import User
from django.contrib.auth.views import LoginView
from django.contrib import messages
from .models import User
from django.contrib.auth import authenticate, login

class CustomLoginView(LoginView):
    template_name = 'accounts/login.html'
    
    def form_valid(self, form):
        """Security check complete. Log the user in."""
        user = form.get_user()
        
        # Check if user exists in database and is active
        if not user or not user.pk:
            messages.error(self.request, "Invalid login credentials. Please check your email and password.")
            return self.form_invalid(form)
        
        # Check if user is active
        if not user.is_active:
            messages.error(self.request, "This account is inactive. Please contact administrator.")
            return self.form_invalid(form)
        
        # Log the user in
        login(self.request, user)
        
        # Redirect based on user type
        if user.is_admin():
            return redirect('tickets:dashboard')
        elif user.is_agent():
            return redirect('tickets:dashboard')
        else:  # customer
            return redirect('tickets:dashboard')
    
    def form_invalid(self, form):
        """Handle invalid form (wrong credentials)"""
        messages.error(self.request, "Invalid email or password. Please try again.")
        return super().form_invalid(form)
    
    def get_success_url(self):
        user = self.request.user
        if user.is_admin():
            return reverse_lazy('tickets:dashboard')
        elif user.is_agent():
            return reverse_lazy('tickets:dashboard')
        else:
            return reverse_lazy('tickets:dashboard')
            
@login_required
def profile(request):
    """User profile view."""
    return render(request, 'accounts/profile.html', {'user': request.user})


@login_required
def profile_edit(request):
    """Edit user profile."""
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'accounts/profile_edit.html', {'form': form})


@login_required
def change_password(request):
    """Change user password."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})

@login_required
def settings(request):
    """User settings view for notifications and preferences."""
    if request.method == 'POST':
        form = UserNotificationSettingsForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Settings updated successfully.')
            return redirect('accounts:settings')
    else:
        form = UserNotificationSettingsForm(instance=request.user)
    
    return render(request, 'accounts/settings.html', {'form': form})