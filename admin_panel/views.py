from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone

from .decorators import admin_required, superadmin_required
from .extractor import extract_and_save, get_or_create_company_from_filename
from financials.models import Company, Filing, Metric
from accounts.models import User


# ── Portal Home ───────────────────────────────────────────────────────────────
@admin_required
def portal_home(request):
    ctx = {
        'total_companies': Company.objects.count(),
        'total_filings':   Filing.objects.count(),
        'total_users':     User.objects.count(),
        'recent_filings':  Filing.objects.select_related('company', 'uploaded_by').order_by('-uploaded_at')[:8],
        'failed_filings':  Filing.objects.filter(status='failed').count(),
    }
    return render(request, 'admin_panel/home.html', ctx)


# ── Upload PDF ────────────────────────────────────────────────────────────────
@admin_required
def upload_pdf(request):
    if request.method == 'POST':
        pdf = request.FILES.get('pdf_file')
        if not pdf:
            messages.error(request, 'No file selected.')
            return redirect('portal_upload')

        if not pdf.name.lower().endswith('.pdf'):
            messages.error(request, 'Only PDF files are accepted.')
            return redirect('portal_upload')

        # Identify company from filename
        company, period = get_or_create_company_from_filename(pdf.name)

        if company is None:
            # Unknown company — let admin specify manually
            ticker    = request.POST.get('ticker', '').strip().upper()
            name      = request.POST.get('company_name', '').strip()
            sector    = request.POST.get('sector', '').strip()
            period_lbl= request.POST.get('period_label', '').strip()

            if not ticker or not name or not period_lbl:
                messages.error(request,
                    'Company not recognised from filename. '
                    'Please fill in Ticker, Company Name, and Period.')
                return render(request, 'admin_panel/upload.html', {'show_manual': True, 'filename': pdf.name})

            company, _ = Company.objects.get_or_create(
                ticker=ticker,
                defaults={'name': name, 'sector': sector}
            )
            period = {'period_label': period_lbl, 'year': 2025, 'quarter': 0, 'filing_month': ''}

        period_lbl = period.get('period_label', 'Unknown')

        # Check for duplicate
        if Filing.objects.filter(company=company, period_label=period_lbl).exists():
            messages.warning(request,
                f'{company.ticker} {period_lbl} already exists. Use re-process if you want to update it.')
            return redirect('portal_filings')

        # Create filing record
        filing = Filing.objects.create(
            company=company,
            period_label=period_lbl,
            period_year=period.get('year', 0),
            period_quarter=period.get('quarter', 0),
            filing_date=period.get('filing_month', ''),
            pdf_file=pdf,
            pdf_filename=pdf.name,
            status='pending',
            uploaded_by=request.user,
        )

        # Run extraction synchronously
        success, msg = extract_and_save(filing)

        if success:
            messages.success(request, f'✅ {company.ticker} {period_lbl} — {msg}')
        else:
            messages.error(request, f'❌ Extraction failed for {company.ticker} {period_lbl}: {msg}')

        return redirect('portal_filings')

    return render(request, 'admin_panel/upload.html', {'show_manual': False})


# ── Companies List ────────────────────────────────────────────────────────────
@admin_required
def companies_list(request):
    companies = Company.objects.prefetch_related('filings').order_by('ticker')
    return render(request, 'admin_panel/companies.html', {'companies': companies})


# ── Filings List ──────────────────────────────────────────────────────────────
@admin_required
def filings_list(request):
    filings = Filing.objects.select_related('company', 'uploaded_by').order_by('-uploaded_at')
    company_filter = request.GET.get('company', '')
    status_filter  = request.GET.get('status', '')
    if company_filter:
        filings = filings.filter(company__ticker__icontains=company_filter)
    if status_filter:
        filings = filings.filter(status=status_filter)
    return render(request, 'admin_panel/filings.html', {
        'filings': filings,
        'company_filter': company_filter,
        'status_filter': status_filter,
    })


# ── Delete Filing ─────────────────────────────────────────────────────────────
@admin_required
def delete_filing(request, pk):
    filing = get_object_or_404(Filing, pk=pk)
    if request.method == 'POST':
        label = f"{filing.company.ticker} {filing.period_label}"
        # Also remove processed files
        import os
        from pathlib import Path
        from django.conf import settings
        processed_dir = Path(settings.DATA_PROCESSED_DIR)
        stem = Path(filing.pdf_filename).stem if filing.pdf_filename else ''
        if stem:
            for f in processed_dir.glob(f"{stem}*"):
                try:
                    f.unlink()
                except Exception:
                    pass
        filing.delete()
        # Clear data service cache
        try:
            from financials.data_service import _get_index
            _get_index.cache_clear()
        except Exception:
            pass
        messages.success(request, f'Deleted {label}.')
    return redirect('portal_filings')


# ── Re-process Filing ─────────────────────────────────────────────────────────
@admin_required
def reprocess_filing(request, pk):
    filing = get_object_or_404(Filing, pk=pk)
    if request.method == 'POST':
        if not filing.pdf_file:
            messages.error(request, 'No PDF file attached to this filing.')
            return redirect('portal_filings')
        success, msg = extract_and_save(filing)
        if success:
            messages.success(request, f'✅ Re-processed {filing}: {msg}')
        else:
            messages.error(request, f'❌ Failed: {msg}')
    return redirect('portal_filings')


# ── Users List ────────────────────────────────────────────────────────────────
@admin_required
def users_list(request):
    users = User.objects.order_by('role', 'email')
    return render(request, 'admin_panel/users.html', {'users': users})


# ── Toggle User Active ────────────────────────────────────────────────────────
@superadmin_required
def toggle_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You can't deactivate yourself.")
    elif request.method == 'POST':
        user.is_active = not user.is_active
        user.save(update_fields=['is_active'])
        status = 'activated' if user.is_active else 'deactivated'
        messages.success(request, f'{user.email} {status}.')
    return redirect('portal_users')


# ── Delete User ───────────────────────────────────────────────────────────────
@superadmin_required
def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, "You can't delete yourself.")
    elif request.method == 'POST':
        email = user.email
        user.delete()
        messages.success(request, f'Deleted user {email}.')
    return redirect('portal_users')


# ── Change Role ───────────────────────────────────────────────────────────────
@superadmin_required
def change_role(request, pk):
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        new_role = request.POST.get('role')
        if new_role in ('superadmin', 'admin', 'viewer'):
            if user == request.user and new_role != 'superadmin':
                messages.error(request, "You can't demote yourself.")
            else:
                user.role = new_role
                user.save(update_fields=['role'])
                messages.success(request, f'{user.email} role changed to {new_role}.')
    return redirect('portal_users')
