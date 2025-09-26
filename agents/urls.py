from django.urls import path
from .views import HomeView,GetPOAgentView,GetVendorAgentView

urlpatterns = [
    path('',HomeView.as_view(),name='home'),
    path('getpo-agent',GetPOAgentView, name='getpo_agent'),
    path('getvendor-agent',GetVendorAgentView, name='getvendor_agent'),
]
