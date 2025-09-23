# ai_agents/services.py

import logging
import json
import requests
from datetime import datetime

# Import Django settings to get our configuration
from django.conf import settings
from oci.addons.adk import tool, AgentClient, Agent

# Get the logger configured in settings.py
logger = logging.getLogger(__name__)

@tool(
    name="get_po_details",
    description="Given a Purchase Order number (PO_ID), fetches PO details from PeopleSoft API. "
                "Input must be a string PO number like '0000000014'."
)
def get_po_details(po_number: str) -> dict:
    """Fetches Purchase Order details from an external API."""
    API_URL = settings.PEOPLESOFT_API_URL # Get URL from settings
    payload = {"PO_ID": po_number}

    logger.info(f"Attempting to fetch details for PO_ID: {po_number}")
    try:
        logger.debug(f"Making GET request to {API_URL} with params: {payload}")
        response = requests.get(API_URL, params=payload)
        logger.info(f"Received status code: {response.status_code}")
        logger.debug(f"Raw response text: {response.text}")

        if response.status_code == 200:
            po_data = response.json()
            po_hdr_list = po_data.get("ABS_PO", {}).get("PO_HDR", [])

            if not po_hdr_list:
                msg = f"No PO_HDR found for PO_ID {po_number}"
                logger.warning(msg)
                return {"status": "error", "message": msg}

            matching_po = next((po for po in po_hdr_list if po.get("PO_ID") == po_number), None)

            if not matching_po:
                msg = f"PO_ID {po_number} not found in response."
                logger.warning(msg)
                return {"status": "error", "message": msg}

            logger.info(f"Successfully found and processed PO_ID {po_number}")
            return {"status": "success", "po_header": matching_po}
        else:
            msg = f"API call failed for PO_ID {po_number}. Status: {response.status_code}"
            logger.error(f"{msg}, Response: {response.text}")
            return {"status": "error", "code": response.status_code, "message": response.text}

    except Exception as e:
        logger.exception(f"An unexpected error occurred while fetching PO_ID {po_number}")
        return {"status": "error", "message": str(e)}

def run_po_agent(po_number: str) -> dict:
    """
    Initializes and runs the OCI agent to get PO details.
    """
    try:
        client = AgentClient(auth_type="api_key", profile="DEFAULT", region="us-chicago-1")
        agent = Agent(
            client=client,
            agent_endpoint_id=settings.AGENT_ENDPOINT_ID, # Get Endpoint from settings
            instructions=(
                "You are a Purchase Order assistant. "
                "When the user provides a PO number, always call the 'get_po_details' tool "
                "with the PO number string exactly as given. Always use the tool to answer."
            ),
            tools=[get_po_details]
        )
        
        # In a web app, we call the agent directly, not through a general input prompt
        response = agent.run(f"Get details for PO number {po_number}")
        
        # The agent's response might contain text and tool calls.
        # We are interested in the output of the tool call.
        tool_outputs = [call.output for call in response.tool_calls if call.output]
        
        if tool_outputs:
            # Assuming the first tool output is what we need
            return tool_outputs[0]
        else:
            # If the tool wasn't called for some reason, return the text response
            return {"status": "error", "message": response.text}

    except Exception as e:
        logger.exception("Failed to initialize or run the OCI agent.")
        return {"status": "error", "message": f"Agent execution failed: {str(e)}"}
