from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .decorators import role_required
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.contrib.auth.hashers import make_password

# Create your views here.
@login_required()
def index(request):
    return render(request, "accounts/user.html")

def login_view(request):
    if request.user.is_authenticated:
        return redirect("index")
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect("index")
        else:
            return render(request, "accounts/login.html", {"message": "Invalid Credentials"})
    return render(request, "accounts/login.html")

def logout_view(request):
    logout(request)
    return redirect('login')

@login_required
@role_required(allowed_roles=['admin'])
def register_user(request):
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.role = form.cleaned_data['role']
            user.save()
            messages.success(request, f"User {user.username} created successfully!")
            return redirect('index')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = CustomUserCreationForm()

    return render(request, "accounts/register_user.html", {"form": form})