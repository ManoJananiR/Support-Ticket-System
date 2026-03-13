from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.hashers import check_password
from .models import User

class EmailCustomerPasswordBackend(BaseBackend):
    """
    Authentication backend that allows users to authenticate with email 
    and customer_password field.
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        
        try:
            # Try to find user by email
            user = User.objects.get(email=username)
            
            # Check if user is active
            if not user.is_active:
                return None
            
            # Check if account is locked
            if user.account_locked:
                return None
            
            # For customers, check customer_password field
            if user.user_type == 'customer':
                if user.check_customer_password(password):
                    return user
                else:
                    # Increment failed attempts
                    user.increment_failed_attempts()
                    return None
            
            # For agents/admins, use Django's default password
            elif user.user_type in ['agent', 'admin']:
                if user.check_password(password):
                    return user
                else:
                    user.increment_failed_attempts()
                    return None
            
        except User.DoesNotExist:
            # Run the default password hasher once to delay timing attacks
            from django.contrib.auth.hashers import make_password
            make_password(password)
            return None
        
        return None
    
    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None