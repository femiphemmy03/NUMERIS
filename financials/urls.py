from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('company/<str:ticker>/', views.company_detail, name='company_detail'),
    path('api/company/<str:ticker>/', views.api_company, name='api_company'),
]
