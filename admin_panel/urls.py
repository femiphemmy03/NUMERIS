from django.urls import path
from . import views

urlpatterns = [
    path('',                    views.portal_home,      name='portal_home'),
    path('upload/',             views.upload_pdf,       name='portal_upload'),
    path('companies/',          views.companies_list,   name='portal_companies'),
    path('filings/',            views.filings_list,     name='portal_filings'),
    path('filing/<int:pk>/delete/', views.delete_filing,name='portal_delete_filing'),
    path('filing/<int:pk>/reprocess/', views.reprocess_filing, name='portal_reprocess'),
    path('users/',              views.users_list,       name='portal_users'),
    path('users/<int:pk>/toggle/', views.toggle_user,  name='portal_toggle_user'),
    path('users/<int:pk>/delete/', views.delete_user,  name='portal_delete_user'),
    path('users/<int:pk>/role/', views.change_role,    name='portal_change_role'),
]
