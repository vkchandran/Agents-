from django.urls import path
from .views import HomeView,GetPOAgentView,GetVendorAgentView,AlertSummaryAgentView,EmailAgentView

urlpatterns = [
    path('',HomeView.as_view(),name='home'),
    path('getpo-agent/',GetPOAgentView, name='getpo_agent'),
    path('getvendor-agent/',GetVendorAgentView, name='getvendor_agent'),
    path('alertsummary-agent/',AlertSummaryAgentView, name='alertsummary_agent'),
    path('email-agent/',EmailAgentView,name='email_agent')
]
