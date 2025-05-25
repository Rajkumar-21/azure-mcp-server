# azure_mcp_server/tools/trigger_automation_runbooks.py
import logging
import json
import uuid
import asyncio # For asyncio.sleep
from typing import Dict, Any, Optional, List
from azure.core.credentials_async import AsyncTokenCredential
from azure.mgmt.automation.aio import AutomationClient
from azure.mgmt.automation.models import JobCreateParameters # For explicit model usage
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError

logger = logging.getLogger(__name__)

async def _get_job_output_content(
    automation_client: AutomationClient, # Pass the client
    resource_group_name: str,
    automation_account_name: str,
    job_id: str # This is the job_name used when creating the job
) -> List[Dict[str, Any]]:
    """
    Retrieves and parses the output content for a given job ID.
    """
    output_records = []
    try:
        logger.info(f"Logic: Fetching output streams for job '{job_id}' in account '{automation_account_name}'.")
        # Ensure job_id is the name you used for the job (which is our UUID)
        stream_list = automation_client.job_stream.list_by_job(
            resource_group_name=resource_group_name,
            automation_account_name=automation_account_name,
            job_name=job_id,
            # You can add a filter if needed, e.g., filter="properties/streamType eq 'Output'"
        )

        async for stream_record in stream_list:
            record_value = None
            if hasattr(stream_record, 'value') and stream_record.value:
                record_value = stream_record.value # This is typically a dict

            # The summary often contains the direct string output for Write-Output
            summary_text = stream_record.summary if hasattr(stream_record, 'summary') else None

            record_details = {
                "stream_id": stream_record.id if hasattr(stream_record, 'id') else None,
                "stream_type": stream_record.stream_type if hasattr(stream_record, 'stream_type') else "Unknown",
                "time": stream_record.time.isoformat() if hasattr(stream_record, 'time') and stream_record.time else None,
                "summary": summary_text,
                "value": record_value
            }
            output_records.append(record_details)

        if not output_records:
            logger.info(f"Logic: No output stream records found for job '{job_id}'.")
            return [{"stream_type": "Info", "summary": "No output stream records were found for this job.", "value": None}]
        logger.info(f"Logic: Successfully fetched {len(output_records)} stream records for job '{job_id}'.")
        return output_records
    except AttributeError as ae: # To catch things like the 'job_streams' error if SDK changes
        logger.error(f"Logic: Attribute error fetching output for job '{job_id}': {ae}. This might indicate an SDK version issue or incorrect client usage.", exc_info=True)
        return [{"stream_type": "Error", "summary": f"SDK/Attribute Error fetching job output: {str(ae)}", "value": None}]
    except HttpResponseError as e:
        logger.error(f"Logic: Azure API error fetching output for job '{job_id}': {e.message}")
        return [{"stream_type": "Error", "summary": f"API Error fetching job output: {e.message}", "value": None}]
    except Exception as e:
        logger.error(f"Logic: Unexpected error fetching output for job '{job_id}': {e}", exc_info=True)
        return [{"stream_type": "Error", "summary": f"Unexpected error fetching job output: {str(e)}", "value": None}]

async def _create_and_monitor_runbook_job(
    automation_client: AutomationClient, # Pass the client, ensure it's used consistently
    resource_group_name: str,
    automation_account_name: str,
    runbook_name: str,
    parameters: Optional[Dict[str, Any]] = None,
    poll_interval_seconds: int = 10,
    job_timeout_seconds: int = 900
) -> Dict[str, Any]:
    job_guid = str(uuid.uuid4()) # This will be the job_name
    logger.info(f"Logic: Preparing to create job '{job_guid}' for runbook '{runbook_name}' in account '{automation_account_name}'. Parameters: {parameters}")

    # Construct parameters for JobCreateParameters
    # The SDK expects JobCreateParameters which has a 'runbook' field (RunbookAssociationProperty)
    # and 'parameters' field (dict).
    job_create_payload = JobCreateParameters(
        runbook={'name': runbook_name},
        parameters=parameters if parameters else {}
    )

    current_job_details = None # To store the job object returned by create or get

    try:
        # Create the job
        current_job_details = await automation_client.job.create(
            resource_group_name=resource_group_name,
            automation_account_name=automation_account_name,
            job_name=job_guid,
            parameters=job_create_payload
        )
        logger.info(f"Logic: Job '{current_job_details.name}' (GUID: {job_guid}) created. Initial status: {current_job_details.status}, ProvisioningState: {current_job_details.provisioning_state}")

        job_final_status = current_job_details.status
        total_wait_time = 0

        # Polling loop
        while job_final_status not in ["Completed", "Failed", "Suspended", "Stopped"]:
            if total_wait_time >= job_timeout_seconds:
                logger.warning(f"Logic: Job '{job_guid}' timed out after {job_timeout_seconds} seconds. Last status: {job_final_status}")
                job_final_status = "TimedOut" # Custom status for timeout
                break

            logger.info(f"Logic: Waiting {poll_interval_seconds}s before polling job '{job_guid}' status...")
            await asyncio.sleep(poll_interval_seconds)
            total_wait_time += poll_interval_seconds

            logger.debug(f"Logic: Polling job '{job_guid}' status... (Total time waited: {total_wait_time}s)")
            current_job_details = await automation_client.job.get( # Refresh job details
                resource_group_name=resource_group_name,
                automation_account_name=automation_account_name,
                job_name=job_guid # Use the GUID/name
            )
            job_final_status = current_job_details.status
            logger.info(f"Logic: Job '{job_guid}' status: {job_final_status}, ProvisioningState: {current_job_details.provisioning_state}")

        # Job has terminated (completed, failed, suspended, stopped, or timed out)
        result = {
            "job_id": job_guid,
            "runbook_name": runbook_name,
            "automation_account_name": automation_account_name,
            "status": job_final_status, # The final status after polling
            "start_time": current_job_details.start_time.isoformat() if current_job_details.start_time else None,
            "end_time": current_job_details.end_time.isoformat() if current_job_details.end_time else None,
            "creation_time": current_job_details.creation_time.isoformat() if current_job_details.creation_time else None,
            "last_modified_time": current_job_details.last_modified_time.isoformat() if current_job_details.last_modified_time else None,
            "provisioning_state": current_job_details.provisioning_state,
            "parameters_used": parameters,
            "output_streams": [],
            "error_summary": None
        }

        if job_final_status == "Completed":
            logger.info(f"Logic: Job '{job_guid}' completed. Fetching output streams.")
            # Use the same automation_client that was used for creating/getting the job
            result["output_streams"] = await _get_job_output_content(
                automation_client, resource_group_name, automation_account_name, job_guid
            )
        elif job_final_status in ["Failed", "Suspended", "Stopped"]:
            result["error_summary"] = current_job_details.exception if hasattr(current_job_details, 'exception') and current_job_details.exception else f"Job ended with status: {job_final_status}."
            logger.error(f"Logic: Job '{job_guid}' ended with status '{job_final_status}'. Error Summary: {result['error_summary']}. Fetching any available streams.")
            result["output_streams"] = await _get_job_output_content(
                automation_client, resource_group_name, automation_account_name, job_guid
            )
        elif job_final_status == "TimedOut":
            result["error_summary"] = f"Job '{job_guid}' monitoring timed out after {job_timeout_seconds} seconds."
            result["output_streams"] = [{"stream_type": "Error", "summary": result["error_summary"], "value": None}]
        else: # Should not happen if loop logic is correct
             logger.warning(f"Logic: Job '{job_guid}' ended in an unexpected state: {job_final_status}")
             result["error_summary"] = f"Job ended in an unexpected state: {job_final_status}"


        return result

    except ResourceNotFoundError as e:
        error_msg = f"Resource not found error for runbook '{runbook_name}' or Automation Account '{automation_account_name}' in RG '{resource_group_name}'. Details: {e}"
        logger.error(f"Logic: {error_msg}", exc_info=True)
        return {"Error": error_msg}
    except HttpResponseError as e:
        error_msg = f"Azure API error during job lifecycle for runbook '{runbook_name}': {e.message}. Details: {getattr(e, 'error', '')} - {getattr(e, 'response', '')}"
        logger.error(f"Logic: {error_msg}", exc_info=True) # exc_info=True for better debugging of API issues
        return {"Error": error_msg}
    except Exception as e:
        error_msg = f"An unexpected error occurred while processing runbook '{runbook_name}': {str(e)}"
        logger.error(f"Logic: {error_msg}", exc_info=True)
        return {"Error": error_msg}


# --- Specific Runbook Trigger Functions ---
async def trigger_vm_power_status_runbook_logic(
    credential: AsyncTokenCredential,
    subscription_id: str,
    resource_group_name: str, # Resource group of the Automation Account
    vm_name: str,
    automation_account_name: str = "UE2PIAC018AAA03",
    runbook_name: str = "VMPowerStatus"
) -> Dict[str, Any]:
    logger.info(f"Logic: Preparing to trigger runbook '{runbook_name}' for VM '{vm_name}' in account '{automation_account_name}' (RG: {resource_group_name}).")

    if not resource_group_name:
        return {"Error": "Resource group name for the Automation Account is required."}
    if not vm_name:
        return {"Error": "VMName parameter is required for the VMPowerStatus runbook."}

    runbook_parameters = {
        "VMName": vm_name
    }

    # The AutomationClient should be created once and passed around
    async with AutomationClient(credential, subscription_id) as client:
        return await _create_and_monitor_runbook_job(
            automation_client=client, # Pass the opened client
            resource_group_name=resource_group_name,
            automation_account_name=automation_account_name,
            runbook_name=runbook_name,
            parameters=runbook_parameters
        )