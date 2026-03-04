from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from .forms import UserRegistrationForm, UserProfileForm,UserNotificationSettingsForm

def register(request):
    """User registration view."""
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful. Please log in.')
            return redirect('accounts:login')
    else:
        form = UserRegistrationForm()
    return render(request, 'accounts/register.html', {'form': form})


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