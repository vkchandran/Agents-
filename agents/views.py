# ai_agents/views.py

from django.shortcuts import render
from . import agent_services # Import our new services file
from django.views.generic import TemplateView


class HomeView(TemplateView):
    template_name = 'home.html'

def GetPOAgentView(request):
    context = {}
    if request.method == 'POST':
        po_number = request.POST.get('po_number', '').strip()
        if po_number:
            # Call our service function to run the agent
            result = agent_services.run_po_agent(po_number)
            context['result'] = result
            context['submitted_po'] = po_number
    return render(request, 'getpo_agent.html', context)

def GetVendorAgentView(request):
    context = {}
    if request.method == 'POST':
        vendor_id = request.POST.get('vendor_id', '').strip()
        if vendor_id:
            # Call our service function to run the agent
            result = agent_services.run_vendor_agent(vendor_id)
            context['result'] = result
            context['submitted_vendor'] = vendor_id
    return render(request, 'getvendor_agent.html', context)

def AlertSummaryAgentView(request):
    context = {}
    if request.method == 'POST':
        
        # Call our service function to run the agent
        result = agent_services.run_alertsummary_agent()
        context['result'] = result
        # context['prompt'] = prompt
    return render(request, 'alertsummary_agent.html', context)

def EmailAgentView(request):
    context = {}
    if request.method == 'POST':
        
        # Call our service function to run the agent
        result = agent_services.run_Email_agent()
        context['result'] = result
        # context['prompt'] = prompt
    return render(request, 'email_agent.html', context)

