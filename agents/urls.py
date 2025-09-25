from django.urls import path
from .views import HomeView,GetPOAgentView

urlpatterns = [
    path('',HomeView.as_view(),name='home'),
    path('getpo-agent',GetPOAgentView, name='getpo_agent'),
        ]
