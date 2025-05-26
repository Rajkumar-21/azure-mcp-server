# azure_mcp_server/server.py
import os
import logging
import json
from typing import List, Optional, Dict, Any

# Azure SDK Exceptions
from azure.core.exceptions import HttpResponseError, ResourceNotFoundError, ClientAuthenticationError

# MCP Imports
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Import logic functions from our tools package
from tools import resource_groups, storage_accounts, vm_details, trigger_automation_runbooks
from tools.config.auth import AzureAuthenticator # Import the new authenticator

# --- Basic Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- MCP Server Instance ---
mcp = FastMCP("Azure MCP Server")
logger.info("Azure MCP Server initializing with centralized authentication...")

# --- Azure Authenticator Instance (can be shared if stateless, or created per call) ---
# Creating per call is safer if any internal state were to be introduced later.
# authenticator = AzureAuthenticator() # Or create inside each tool

# --- Helper for common error handling and credential acquisition ---
async def _handle_azure_operation(
    ctx: Context,
    operation_name: str,
    subscription_id_param: str,
    auth_type_param: str,
    azure_logic_callable, # The async function from tools.*_logic
    *logic_args # Additional arguments for the logic_callable
):
    """Helper to manage credential acquisition, Azure calls, and error handling."""
    authenticator = AzureAuthenticator() # Create new instance per call

    if not subscription_id_param:
        # Attempt to get from environment if not provided and tool implies it might be optional from env
        # For now, let's assume subscription_id is made mandatory by tools if needed.
        # If you want to fallback to env, add:
        # subscription_id_param = authenticator.get_subscription_id()
        # if not subscription_id_param:
        logger.error(f"Tool {operation_name}: Azure Subscription ID is required but was not provided.")
        ctx.error("Azure Subscription ID is required.")
        return json.dumps({"error": "Azure Subscription ID is required."})

    effective_auth_type = auth_type_param if auth_type_param else "default"
    if effective_auth_type not in ["default", "spn", "identity"]:
        error_msg = f"Error: Invalid auth_type ('{auth_type_param}'). Must be 'default', 'spn', or 'identity'."
        logger.warning(error_msg)
        ctx.error(error_msg)
        return json.dumps({"error": error_msg})

    ctx.info(f"{operation_name} for subscription {subscription_id_param[:4]}... using {effective_auth_type} auth.")
    logger.info(f"Tool: {operation_name} for sub: {subscription_id_param[:4]} (auth: {effective_auth_type})")

    try:
        credential = await authenticator.get_credential(effective_auth_type)
        async with credential: # Ensures credential.close() is called if available
            result = await azure_logic_callable(credential, subscription_id_param, *logic_args)
            # Assuming logic functions return list/dict suitable for json.dumps or a pre-formatted string
            if isinstance(result, (list, dict)):
                 # Check for errors propagated from logic functions
                if isinstance(result, dict) and "Error" in result:
                    ctx.error(f"{operation_name} failed: {result['Error']}")
                    return json.dumps(result)
                if isinstance(result, list) and result and isinstance(result[0], dict) and "Error" in result[0]: # Handle list of errors
                    ctx.error(f"{operation_name} failed: {result[0]['Error']}") # Log first error
                    return json.dumps(result)

                ctx.info(f"Successfully completed {operation_name}.")
                return json.dumps(result, indent=2)
            else: # If logic function returns pre-formatted JSON string or simple string
                ctx.info(f"Successfully completed {operation_name}. Result: {str(result)[:100]}...")
                return str(result) # Expecting JSON string or simple string (like usage)

    except ConnectionError as e: # Catches auth errors from AzureAuthenticator or network issues
        logger.error(f"Tool {operation_name} - Auth/Connection Error: {e}", exc_info=False) # exc_info=False for cleaner logs
        ctx.error(f"Azure Authentication/Connection Error: {e}")
        return json.dumps({"error": f"Error connecting or authenticating with Azure: {e}"})
    except HttpResponseError as e:
        logger.error(f"Tool {operation_name} - Azure API Error: {e.message}", exc_info=False)
        ctx.error(f"Azure API Error during {operation_name}: Status={e.status_code}, Reason={e.reason}")
        return json.dumps({"error": f"Azure API Error: {e.message}"})
    except ValueError as e: # For invalid inputs not caught earlier
        logger.error(f"Tool {operation_name} - Value Error: {e}", exc_info=True)
        ctx.error(f"Invalid value provided for {operation_name}: {e}")
        return json.dumps({"error": f"Invalid value: {e}"})
    except Exception as e:
        logger.error(f"Tool {operation_name} - Unexpected Error: {e}", exc_info=True)
        ctx.error(f"An unexpected error occurred during {operation_name}: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

@mcp.tool()
async def list_resource_groups(
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Lists details for all resource groups in the specified Azure subscription.
    Requires: subscription_id.
    Optional: auth_type ('default', 'spn', 'identity').
    Returns a JSON string.
    """
    return await _handle_azure_operation(
        ctx, "List Resource Groups", subscription_id, auth_type,
        resource_groups.list_resource_groups_logic
    )

@mcp.tool()
async def list_storage_accounts(
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Lists details for all storage accounts in the specified Azure subscription.
    Requires: subscription_id.
    Optional: auth_type ('default', 'spn', 'identity').
    Returns a JSON string.
    """
    return await _handle_azure_operation(
        ctx, "List Storage Accounts", subscription_id, auth_type,
        storage_accounts.list_storage_accounts_logic
    )

@mcp.tool()
async def get_storage_account_usage( # Renamed from list_storage_account_usage for clarity
    subscription_id: str,
    resource_group_name: str,
    storage_account_name: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Gets the used capacity for a specific storage account.
    Requires: subscription_id, resource_group_name, storage_account_name.
    Optional: auth_type.
    Returns a JSON string (e.g., {"used_capacity": "1.23 TiB"}).
    """
    if not all([resource_group_name, storage_account_name]):
        return json.dumps({"error": "Resource Group Name and Storage Account Name are required."})

    # The result from get_storage_account_usage_logic is a string like "1.23 TiB" or "N/A..."
    # We need to wrap it in a JSON structure for consistency.
    async def usage_wrapper(credential, sub_id, rg_name, sa_name):
        usage_str = await storage_accounts.get_storage_account_usage_logic(credential, sub_id, rg_name, sa_name)
        return {"used_capacity": usage_str}

    return await _handle_azure_operation(
        ctx, f"Get Storage Account Usage ({storage_account_name})", subscription_id, auth_type,
        usage_wrapper, # Pass the wrapper
        resource_group_name, storage_account_name
    )

@mcp.tool()
async def list_all_storage_accounts_with_usage( # Renamed from list_storage_account_usage_all
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Lists all storage accounts in the subscription with their used capacity.
    WARNING: This can be SLOW for subscriptions with many storage accounts.
    Requires: subscription_id.
    Optional: auth_type.
    Returns a JSON string.
    """
    authenticator = AzureAuthenticator()
    effective_auth_type = auth_type if auth_type else "default"

    if not subscription_id:
        return json.dumps({"error": "Azure Subscription ID is required."})
    if effective_auth_type not in ["default", "spn", "identity"]:
         return json.dumps({"error": f"Invalid auth_type ('{auth_type}')."})

    ctx.info(f"Listing ALL storage accounts and usage for subscription {subscription_id[:4]}... (auth: {effective_auth_type}) *** WARNING: This may take time. ***")
    logger.info(f"Tool: List All Storage Accounts w/ Usage for sub: {subscription_id[:4]} (auth: {effective_auth_type})")

    try:
        credential = await authenticator.get_credential(effective_auth_type)
        async with credential:
            sa_list = await storage_accounts.list_storage_accounts_logic(credential, subscription_id)
            total_accounts = len(sa_list)
            ctx.info(f"Found {total_accounts} SAs. Fetching usage for each...")
            await ctx.report_progress(0, total_accounts)

            results_with_usage = []
            for i, account_dict in enumerate(sa_list):
                sa_name = account_dict.get("name")
                rg_name = account_dict.get("resource_group")
                ctx.info(f"Fetching usage for {sa_name} in {rg_name} ({i+1}/{total_accounts})...")

                if sa_name and rg_name and sa_name != "Unknown" and rg_name != "Unknown":
                    usage_str = await storage_accounts.get_storage_account_usage_logic(
                        credential, subscription_id, rg_name, sa_name
                    )
                    account_dict["used_capacity"] = usage_str
                else:
                    account_dict["used_capacity"] = "N/A (Info Missing)"
                    ctx.warning(f"Skipping usage for account index {i} (Name: {sa_name}, RG: {rg_name}) due to missing info.")
                results_with_usage.append(account_dict)
                if (i + 1) % 5 == 0 or (i + 1) == total_accounts : # Report progress periodically
                    await ctx.report_progress(i + 1, total_accounts)

            logger.info(f"Finished fetching usage for all {total_accounts} storage accounts.")
            ctx.info("Finished fetching usage for all storage accounts.")
            return json.dumps(results_with_usage, indent=2)

    except ConnectionError as e:
        logger.error(f"Tool All SA Usage - Auth/Connection Error: {e}", exc_info=False)
        ctx.error(f"Azure Auth/Connection Error: {e}")
        return json.dumps({"error": f"Error connecting/authenticating: {e}"})
    except Exception as e:
        logger.error(f"Tool All SA Usage - Unexpected Error: {e}", exc_info=True)
        ctx.error(f"Failed to list all storage account usage: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

@mcp.tool()
async def get_vm_detail_by_name( # Renamed from get_vm_detail
    vm_name: str,
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Gets detailed information for a specific Azure VM by its name.
    The VM is searched across all resource groups in the subscription.
    Requires: vm_name, subscription_id.
    Optional: auth_type ('default', 'spn', 'identity').
    Returns a JSON string containing the VM details or an error.
    """
    if not vm_name:
        return json.dumps({"error": "VM name is required."})

    return await _handle_azure_operation(
        ctx, f"Get VM Detail ({vm_name})", subscription_id, auth_type,
        vm_details.get_vm_detail_logic,
        vm_name # This is the additional arg for get_vm_detail_logic
    )

@mcp.tool()
async def get_vms_by_team_tag(
    team_value: str,
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Lists Azure VMs that have a 'TEAM' tag matching the specified value.
    Requires: team_value, subscription_id.
    Optional: auth_type ('default', 'spn', 'identity').
    Returns a JSON string containing a list of matching VM details or an error.
    """
    if not team_value:
        return json.dumps({"error": "TEAM tag value is required."})

    return await _handle_azure_operation(
        ctx, f"Get VMs by TEAM tag ({team_value})", subscription_id, auth_type,
        vm_details.get_vms_by_team_logic,
        team_value # This is the additional arg for get_vms_by_team_logic
    )



@mcp.tool()
async def trigger_vm_power_status_runbook(
    vm_name_parameter: str, # Parameter for the runbook
    subscription_id: Optional[str] = "<replace subid>", # Default sub ID, can be overridden
    automation_resource_group_name: Optional[str] = "RGName", # RG of the Automation Account
    automation_account_name: Optional[str] = "AccountName", # Can be overridden
    runbook_name: Optional[str] = "RunbookName", # Can be overridden
    auth_type: Optional[str] = "default",
    ctx: Context = None
) -> str:
    """
    Triggers the 'VMPowerStatus' Azure Automation runbook and monitors its execution.
    The runbook is expected to take a 'VMName' parameter.

    Args:
        subscription_id: The Azure Subscription ID where the Automation Account resides.
        automation_resource_group_name: The name of the Resource Group containing the Automation Account.
        vm_name_parameter: The name of the Virtual Machine to be passed as the 'VMName' parameter to the runbook.
        automation_account_name: (Optional) The name of the Azure Automation Account. Defaults to 'UE2PIAC018AAA03'.
        runbook_name: (Optional) The name of the runbook. Defaults to 'VMPowerStatus'.
        auth_type: (Optional) The authentication method ('default', 'spn', 'identity'). Defaults to 'default'.

    Returns:
        A JSON string with the job execution details (ID, status, output/error) or an error message.
    """
    if not automation_resource_group_name:
        return json.dumps({"error": "Automation Account's Resource Group Name (automation_resource_group_name) is required."})
    if not vm_name_parameter:
        return json.dumps({"error": "VM Name parameter (vm_name_parameter) for the runbook is required."})

    # Use provided names or defaults
    effective_automation_account_name = automation_account_name if automation_account_name else "UE2PIAC018AAA03"
    effective_runbook_name = runbook_name if runbook_name else "VMPowerStatus"

    ctx.info(f"Attempting to trigger runbook '{effective_runbook_name}' in account '{effective_automation_account_name}' (RG: {automation_resource_group_name}) for VM '{vm_name_parameter}'.")

    return await _handle_azure_operation(
        ctx,
        f"Trigger Runbook ({effective_runbook_name} for VM {vm_name_parameter})",
        subscription_id,
        auth_type,
        trigger_automation_runbooks.trigger_vm_power_status_runbook_logic,
        # Additional args for the logic function, after credential and subscription_id:
        automation_resource_group_name,
        vm_name_parameter,
        effective_automation_account_name, # Pass to logic
        effective_runbook_name # Pass to logic
    )


# --- main.py (Starlette/Uvicorn setup) ---
# The main.py provided in the problem description for azure_mcp_server
# should still work as it just imports and mounts the `mcp` instance.
# Ensure it's correctly pointing to this server.py file.
# Example: from server import mcp as mcp_instance
# (No changes needed in main.py itself based on these refactorings,
#  assuming it's set up as described in the problem.)

# If running directly (not via main.py/Uvicorn):
# if __name__ == "__main__":
#     logger.info("Starting Azure MCP Server for stdio...")
#     # mcp.run() # For stdio interaction
#     # For SSE server, you'd typically run via Uvicorn and main.py