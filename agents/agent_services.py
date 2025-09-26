import os
import re
import logging
import json
import requests
from datetime import datetime
import asyncio
from django.conf import settings
from oci.addons.adk import tool, AgentClient, Agent
import imaplib, email
from datetime import datetime,timedelta
from email import policy
from django.http import JsonResponse
import oci
from email.header import decode_header, make_header
from . import config_STAGE as l_env

logger = logging.getLogger(__name__)
DAYS_INTERVAL = int(os.getenv("DAYS_INTERVAL", "1"))

# OCI setup
oci_config = oci.config.from_file(l_env.OCI_CONFIG)
object_storage = oci.object_storage.ObjectStorageClient(oci_config)
namespace = object_storage.get_namespace().data
bucket_name = settings.OCI_BUCKET_NAME

# ============  EmailAgent ======================

class EmailData:
    def __init__(self, from_email, to_email, subject, attachment_name, odu_doc_id="0", l_uid="0"):
        self.FROM_EMAIL = from_email
        self.TO_EMAIL = to_email
        self.SUBJECT_LINE = subject
        self.ATTACHMENT_NAMES = attachment_name
        self.ODU_DOC_ID = odu_doc_id
        self.PROCESSED = 'N'
        self.L_UID = l_uid

    def insert(self):
        payload = {
            "FROM_EMAIL": self.FROM_EMAIL,
            "TO_EMAIL": self.TO_EMAIL,
            "SUBJECT_LINE": self.SUBJECT_LINE,
            "ATTACHMENT_NAMES": self.ATTACHMENT_NAMES,
            "ODU_DOC_ID": self.ODU_DOC_ID,
            "PROCESSED": self.PROCESSED,
            "L_UID": self.L_UID
        }
        try:
            logging.debug(f"Inserting payload: {payload}")
            response = requests.post(l_env.APEX_API_URL_EMAIL, json=payload)
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to insert email details for UID {self.L_UID}: {e}")
            return False

def sanitize_filename(uid, original_name):
    name, ext = os.path.splitext(f"{uid}_{original_name}")
    name = re.sub(r'[^a-zA-Z0-9]+', '_', name).strip('_')[:54]
    return f"{name}{ext}"

def upload_to_oci_object_storage(object_name, file_data):
    try:
        object_storage.put_object(namespace, bucket_name, object_name, file_data)
        logging.info(f"Uploaded '{object_name}' to bucket '{bucket_name}'")
    except Exception as e:
        logging.error(f"Upload failed for '{object_name}': {e}")

@tool(description="Connects to email server, scans inbox for unseen invoice emails, and uploads attachments to OCI Object Storage.")
def process_from_email():
    global mail
    # CHANGED: Added a list to store details of each processed invoice.
    summary = {
        "processed_emails": 0,
        "processed_attachments": 0,
        "errors": 0,
        "processed_invoices": []
    }
    try:
        mail = imaplib.IMAP4_SSL(settings.SMTP_HOST)
        mail.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        mail.select('inbox')
        logging.info("Connected to email server and selected inbox.")
    except Exception as e:
        logging.error(f"Email server connection failed: {e}")
        return {"error": str(e)}

    logging.info("Starting invoice scan...")

    try:
        since_date = (datetime.now() - timedelta(days=DAYS_INTERVAL)).strftime("%d-%b-%Y")
        result, data = mail.search(None, f'(UNSEEN SINCE "{since_date}")')

        if result != 'OK':
            logging.error("Email search failed.")
            return {"error": "Email search failed"}

        for num in data[0].split():
            email_uid = num.decode()
            result, data = mail.fetch(num, '(RFC822)')
            if result == 'OK':
                msg = email.message_from_bytes(data[0][1])
                # Decode headers to handle special characters
                email_from = str(make_header(decode_header(msg.get('From'))))
                email_subject = str(make_header(decode_header(msg.get('Subject'))))

                summary["processed_emails"] += 1

                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart' or part.get('Content-Disposition') is None:
                        continue
                    
                    file_name = part.get_filename()
                    if not file_name:
                        continue
                    
                    # Decode filename
                    decoded_filename = str(make_header(decode_header(file_name)))

                    summary["processed_attachments"] += 1

                    unique_file_name = sanitize_filename(email_uid, decoded_filename)
                    file_data = part.get_payload(decode=True)
                    upload_to_oci_object_storage(unique_file_name, file_data)

                    # CHANGED: Capture the details of the processed invoice.
                    invoice_details = {
                        "from": email_from,
                        "subject": email_subject,
                        "filename": decoded_filename
                    }
                    summary["processed_invoices"].append(invoice_details)

                    email_record = EmailData(email_from, settings.SMTP_USER, email_subject, unique_file_name, l_uid=email_uid)
                    if email_record.insert():
                        logging.info(f"Inserted email UID {email_uid} with attachment '{decoded_filename}'")
                    else:
                        summary["errors"] += 1
            else:
                summary["errors"] += 1

    except Exception as e:
        summary["errors"] += 1
        logging.error(f"Invoice check error: {e}")

    # CHANGED: Return the detailed list along with the summary counts.
    return {
        "message": "Email processing completed",
        "processed_emails": summary["processed_emails"],
        "attachments_uploaded": summary["processed_attachments"],
        "errors": summary["errors"],
        "invoices": summary["processed_invoices"] # <-- This is the new detailed list
    }

def run_Email_agent():
    """
    Initializes and runs the OCI agent to get Vendor details.
    """
    # This outer try/except catches initialization errors
    client = AgentClient(auth_type="api_key", profile="DEFAULT", region="us-chicago-1")
    agent = Agent(
        client=client,
        agent_endpoint_id=settings.AGENT_ENDPOINT_ID.get("Email_AGENT_ENDPOINT_ID"),
        instructions="You process invoice emails and extract relevant data using tools.",
        tools=[process_from_email]
    )

       
    try:
        logger.info(f"Running Email agent")

        # 1. Create and set the event loop for the current thread.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            
            response = agent.run("process and check last one day emails and summarize")
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
    

# ============ AlertSummaryAgent =============================

ALERT_KEYWORDS = ['alert', 'notification', 'important', 'critical', 'warning']

@tool(description="Reads today's emails, scans for alerts and notifications, and summarizes key information.")
def summarize_daily_alerts():
    """
    Connects to an IMAP email server, fetches emails from the current day,
    filters them based on keywords, and returns a formatted summary string.
    """
    summary = {
        "total_emails": 0,
        "alert_emails": 0,
        "alerts": []
    }

    try:
        mail = imaplib.IMAP4_SSL(settings.SMTP_HOST)
        mail.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        mail.select('inbox')
        logger.info("Connected to email server and selected inbox.")
    except Exception as e:
        logger.error(f"Failed to connect to email server: {e}")
        return f"I'm sorry, I was unable to connect to the email server. Please check the configuration. Error: {e}"

    try:
        # IMAP standard format for date is DD-Mon-YYYY
        today_date = datetime.now().strftime("%d-%b-%Y")
        result, data = mail.search(None, f'(SINCE "{today_date}")')

        if result != 'OK':
            logger.error("Email search failed.")
            return "I'm sorry, I failed while trying to search the inbox."

        email_ids = data[0].split()
        if not email_ids:
            logger.info("No emails found for today.")
            return "I checked the inbox but found no new emails for today."

        for num in email_ids:
            summary["total_emails"] += 1
            result, msg_data = mail.fetch(num, '(RFC822)')

            if result != 'OK':
                logger.warning(f"Failed to fetch email with ID {num}.")
                continue

            msg = email.message_from_bytes(msg_data[0][1], policy=policy.default)
            subject = msg.get('Subject', '')
            sender = msg.get('From', '')
            body = ""

            # Extract plain text body
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
            else:
                if msg.get_content_type() == "text/plain":
                    body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')

            full_text = f"{subject}\n{body}".lower()

            # Check for alert keywords
            if any(keyword in full_text for keyword in ALERT_KEYWORDS):
                summary["alert_emails"] += 1
                summary["alerts"].append({
                    "from": sender,
                    "subject": subject
                })

    except Exception as e:
        logger.error(f"Failed during email processing: {e}")
        # CHANGED: Return a user-friendly error string
        return f"An unexpected error occurred while processing emails: {e}"

    finally:
        try:
            mail.logout()
            logger.info("Logged out from email server.")
        except Exception as e:
            logger.error(f"Failed to logout from email server: {e}")

    # Build the final output string for the agent
    alert_info = "\n".join([f"- From: {a['from']}, Subject: {a['subject']}" for a in summary["alerts"]])
    message = (
        f"📊 Daily Email Alert Summary:\n\n"
        f"I scanned a total of {summary['total_emails']} emails today and found "
        f"{summary['alert_emails']} that appear to be alerts or notifications.\n\n"
        f"🔔 Here are the key alerts:\n{alert_info if alert_info else 'No specific alert emails were found.'}"
    )
    logger.info("Email alert summary completed successfully.")

    # CHANGED: Return only the formatted string, not the dictionary
    return message

def run_alertsummary_agent():
    """
    Initializes and runs the OCI agent to get Vendor details.
    """
    # This outer try/except catches initialization errors
    client = AgentClient(auth_type="api_key", profile="DEFAULT", region="us-chicago-1")
    agent = Agent(
        client=client,
        agent_endpoint_id=settings.AGENT_ENDPOINT_ID.get("ALERTSUMMARY_AGENT_ENDPOINT_ID"),
        instructions="You summarize alerts and notifications from emails...",
        tools=[summarize_daily_alerts]
    )
       
    try:
        logger.info(f"Running Alert Summary agent")

        # 1. Create and set the event loop for the current thread.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            
            response = agent.run("give me today details")
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
    