from django.urls import path
from .views import HomeVIew,GetPOAgentView

urlpatterns = [
    path('',HomeViewas_view(),name='home'),
    path('getpo-agent',GetPOAgentView, name='getpo_agent'),
        ]
