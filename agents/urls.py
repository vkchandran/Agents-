from django.urls import path
from .views import GetPOAgentView

urlpatterns = [
    path('',GetPOAgentView, name='agent_Getpo'),
        ]
