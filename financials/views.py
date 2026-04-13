from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from .data_service import get_all_companies, get_company_data


def index(request):
    companies = get_all_companies()
    summaries = []
    for ticker, label in companies:
        data = get_company_data(ticker)
        if data:
            summaries.append({
                "ticker":  data["ticker"],
                "name":    data["name"],
                "sector":  data["sector"],
                "period":  data["period"],
                "signal":  data["signal"],
            })
    return render(request, "financials/index.html", {
        "companies": companies,
        "summaries": summaries,
    })


def company_detail(request, ticker):
    data = get_company_data(ticker.upper())
    if not data:
        return render(request, "financials/not_found.html", {"ticker": ticker})
    return render(request, "financials/detail.html", {"company": data})


def api_company(request, ticker):
    from django.http import JsonResponse
    data = get_company_data(ticker.upper())
    if not data:
        return JsonResponse({"error": "Company not found"}, status=404)
    return JsonResponse({
        "ticker":        data["ticker"],
        "name":          data["name"],
        "revenue_chart": data["revenue_chart"],
        "pat_chart":     data["pat_chart"],
        "segment_chart": data["segment_chart"],
    })
