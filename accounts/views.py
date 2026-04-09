from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import User


def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        email    = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user:
            login(request, user)
            return redirect(request.GET.get('next', 'index'))
        messages.error(request, 'Invalid email or password.')
    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('login')


def register_view(request):
    # Only existing admins can create new accounts
    if not request.user.is_authenticated or not request.user.is_admin:
        return redirect('login')
    if request.method == 'POST':
        email     = request.POST.get('email', '').strip()
        full_name = request.POST.get('full_name', '').strip()
        password  = request.POST.get('password', '')
        role      = request.POST.get('role', 'viewer')
        # Superadmins can create any role; admins can only create viewers
        if request.user.role == 'admin' and role != 'viewer':
            role = 'viewer'
        if User.objects.filter(email=email).exists():
            messages.error(request, 'A user with that email already exists.')
        elif len(password) < 8:
            messages.error(request, 'Password must be at least 8 characters.')
        else:
            User.objects.create_user(email=email, full_name=full_name,
                                     password=password, role=role)
            messages.success(request, f'Account created for {email}.')
            return redirect('portal_users')
    return render(request, 'accounts/register.html')
