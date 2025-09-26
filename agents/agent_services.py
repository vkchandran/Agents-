# ai_agents/services.py

import logging
import json
import requests
from datetime import datetime
import asyncio
# Import Django settings to get our configuration
from django.conf import settings
from oci.addons.adk import tool, AgentClient, Agent

# Get the logger configured in settings.py
logger = logging.getLogger(__name__)

# ============ GetPODetailsAgent =============================

@tool(
    name="get_po_details",
    description="Given a Purchase Order number (PO_ID), fetches PO details from PeopleSoft API. "
                "Input must be a string PO number like '0000000014'."
)
def get_po_details(po_number: str) -> dict:
    """Fetches Purchase Order details from an external API."""
    API_URL = settings.PEOPLESOFT_API_URL.get("GET_PO_PEOPLESOFT_API_URL") # Get URL from settings
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
    # This outer try/except catches initialization errors
    try:
        client = AgentClient(auth_type="api_key", profile="DEFAULT", region="us-chicago-1")
        agent = Agent(
            client=client,
            agent_endpoint_id=settings.AGENT_ENDPOINT_ID.get("GetPO_AGENT_ENDPOINT_ID"),
            # instructions=(
            #     "You are a Purchase Order assistant. "
            #     "When the user provides a PO number, always call the 'get_po_details' tool "
            #     "with the PO number string exactly as given. Always use the tool to answer."
            # ),
            instructions="Access the PeopleSoft FSCM Instance and invoke the rest API to get the   details",
            tools=[get_po_details]
        )
        
        logger.info(f"Running PO agent for: {po_number}")

        # 1. Create and set the event loop for the current thread.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            response = agent.run(f"Get details for PO number {po_number}")
            # FIX: Use the correct method to get the agent's text response
            agent_content = response.final_output
            
            # Return a clean JSON object for the frontend
            return {"status": "success", "message": agent_content}
        
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            return {"status": "error", "message": f"Agent call failed: {str(e)}"}
        
        finally:
            loop.close()

    except Exception as e:
        logger.exception("Failed to initialize the OCI agent.")
        return {"status": "error", "message": f"Agent initialization failed: {str(e)}"}
    

# ================== GetVendorDetailsAgent ===========================

@tool(
    name="get_vendor_details",
    description="Fetches detailed information for a specific Vendor ID from PeopleSoft."
)
def get_vendor_details(vendor_id: str) -> dict:
    API_URL = settings.PEOPLESOFT_API_URL.get("GET_VENDOR_PEOPLESOFT_API_URL")

    payload = {
        "VENDOR_ID": vendor_id
    }

    logger.info(f"Attempting to fetch details for VENDOR_ID: {vendor_id}")
    try:
        logger.debug(f"Making GET request to {API_URL} with params: {payload}")
        response = requests.get(API_URL, params=payload)
        logger.info(f"Received status code: {response.status_code}")

        # Log the raw response text at a debug level for inspection
        logger.debug(f"Raw response text: {response.text}")

        if response.status_code == 200:
            vendor_data = response.json()
            vendor_hdr_list = vendor_data.get("ABS_SUPPLIER", {}).get("VENDOR", [])

            if not vendor_hdr_list:
                logger.warning(f"API response for VENDOR_ID {vendor_id} did not contain a VENDOR list.")
                return {
                    "status": "error",
                    "message": f"No VENDOR found for VENDOR_ID {vendor_id}"
                }

            matching_vendor = next((vendor for vendor in vendor_hdr_list if vendor.get("VENDOR_ID") == vendor_id), None)

            if not matching_vendor:
                logger.warning(f"Could not find a matching VENDOR_ID {vendor_id} in the response list.")
                return {
                    "status": "error",
                    "message": f"VENDOR_ID {vendor_id} not found in response."
                }

            logger.info(f"Successfully found and processed VENDOR_ID {vendor_id}")
            print(matching_vendor) # Kept for immediate console output
            return {
                "status": "success",
                "vendor_header": matching_vendor
            }

        else:
            logger.error(f"API call failed for VENDOR_ID {vendor_id}. Status: {response.status_code}, Response: {response.text}")
            return {
                "status": "error",
                "code": response.status_code,
                "message": response.text
            }

    except Exception as e:
        # CHANGED: Use logger.exception to automatically include the stack trace
        logger.exception(f"An unexpected error occurred while fetching VENDOR_ID {vendor_id}")
        return {
            "status": "error",
            "message": str(e)
        }


def run_vendor_agent(vendor_id: str) -> dict:
    """
    Initializes and runs the OCI agent to get Vendor details.
    """
    # This outer try/except catches initialization errors
    try:
        client = AgentClient(auth_type="api_key", profile="DEFAULT", region="us-chicago-1")
        agent = Agent(
            client=client,
            agent_endpoint_id=settings.AGENT_ENDPOINT_ID.get("GetVendor_AGENT_ENDPOINT_ID"),
            instructions="Access the PeopleSoft FSCM Instance and invoke the rest API to get the vendor  details for a specific Vendor",
            tools=[get_vendor_details]
        )
        
        logger.info(f"Running Vendor agent for: {vendor_id}")

        # 1. Create and set the event loop for the current thread.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            response = agent.run(vendor_id)
            # FIX: Use the correct method to get the agent's text response
            agent_content = response.final_output
            
            # Return a clean JSON object for the frontend
            return {"status": "success", "message": agent_content}
        
        except Exception as e:
            logger.error(f"Agent execution failed: {e}", exc_info=True)
            return {"status": "error", "message": f"Agent call failed: {str(e)}"}
        
        finally:
            loop.close()

    except Exception as e:
        logger.exception("Failed to initialize the OCI agent.")
        return {"status": "error", "message": f"Agent initialization failed: {str(e)}"}
    