from django.shortcuts import redirect
from functools import wraps
from django.contrib.auth.decorators import login_required

def role_required(allowed_roles=None):
    if allowed_roles is None:
        allowed_roles = []

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):

            if request.user.role not in allowed_roles:
                return redirect("index")

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator