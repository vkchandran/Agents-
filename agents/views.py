# ai_agents/views.py

from django.shortcuts import render
from . import services # Import our new services file
from django.views.generic import Templateview


class HomeView(TemplateView):
    template_name = 'home.html'

def GetPOAgentView(request):
    context = {}
    if request.method == 'POST':
        po_number = request.POST.get('po_number', '').strip()
        if po_number:
            # Call our service function to run the agent
            result = services.run_po_agent(po_number)
            context['result'] = result
            context['submitted_po'] = po_number

    return render(request, 'getpo_agent.html', context)
