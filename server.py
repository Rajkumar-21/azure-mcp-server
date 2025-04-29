# server.py
import os
import logging
import json
from typing import List, Optional, Dict, Any

# Azure SDK Imports
from azure.identity.aio import DefaultAzureCredential, ClientSecretCredential, ManagedIdentityCredential
from azure.core.exceptions import HttpResponseError

# MCP Imports
from mcp.server.fastmcp import FastMCP, Context
from dotenv import load_dotenv

# Import logic functions from our tools package
from tools import resource_groups, storage_accounts

# --- Basic Setup ---
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- MCP Server Instance ---
mcp = FastMCP("AzureExplorerStructured")
logger.info("Azure Explorer MCP Server initializing (Structured)...")

# --- Azure Authentication Helper ---
# (Keep the get_azure_credential function exactly as before)
async def get_azure_credential(auth_type: str = "default"):
    """Gets the appropriate Azure credential based on configuration."""
    logger.info(f"Attempting Azure authentication using type: {auth_type}")
    try:
        if auth_type == "spn":
            logger.info("Using Service Principal (ClientSecretCredential)")
            tenant_id = os.getenv("AZURE_TENANT_ID")
            client_id = os.getenv("AZURE_CLIENT_ID")
            client_secret = os.getenv("AZURE_CLIENT_SECRET")
            if not all([tenant_id, client_id, client_secret]):
                raise ValueError("AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET must be set for SPN auth.")
            return ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
        elif auth_type == "identity":
             logger.info("Using Managed Identity (ManagedIdentityCredential)")
             identity_client_id = os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID")
             if identity_client_id:
                 logger.info(f"Using specific managed identity client ID: {identity_client_id}")
                 return ManagedIdentityCredential(client_id=identity_client_id)
             else:
                 logger.info("Using system-assigned managed identity or default user-assigned identity.")
                 return ManagedIdentityCredential()
        else: # default
            logger.info("Using DefaultAzureCredential")
            return DefaultAzureCredential()
    except Exception as e:
        logger.error(f"Azure authentication failed: {e}", exc_info=True)
        raise ConnectionError(f"Failed to get Azure credentials for auth_type '{auth_type}': {e}")

# --- MCP Tool Definitions (Wrappers calling logic functions) ---

# list_resource_groups (Keep as before)
@mcp.tool()
async def list_resource_groups(
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
    ) -> str:
    """
    Lists details for all resource groups in the specified Azure subscription.
    Returns a JSON string representing a list of resource group objects.

    Args:
        subscription_id: The Azure Subscription ID to query.
        auth_type: The authentication method to use ('default', 'spn', 'identity'). Defaults to 'default'.
    """
    if not subscription_id:
        return json.dumps({"error": "Azure Subscription ID is required."})

    effective_auth_type = auth_type if auth_type is not None else "default"
    if effective_auth_type not in ["default", "spn", "identity"]:
         error_msg = f"Error: Invalid auth_type provided ('{auth_type}'). Must be 'default', 'spn', or 'identity'."
         logger.warning(error_msg)
         return json.dumps({"error": error_msg})

    logger.info(f"Tool: Listing resource groups for sub: {subscription_id[:4]} (auth: {effective_auth_type})")
    ctx.info(f"Listing resource groups for subscription {subscription_id[:4]}... using {effective_auth_type} auth.")

    try:
        credential = await get_azure_credential(effective_auth_type)
        async with credential:
            rg_list = await resource_groups.list_resource_groups_logic(credential, subscription_id)
            if not rg_list:
                ctx.info(f"No resource groups found in subscription {subscription_id}.")
                return "[]"
            ctx.info(f"Successfully listed details for {len(rg_list)} resource groups.")
            return json.dumps(rg_list, indent=2)
    except ConnectionError as e:
         logger.error(f"Tool Auth/Connection Error: {e}", exc_info=False)
         ctx.error(f"Azure Authentication/Connection Error: {e}")
         return json.dumps({"error": f"Error connecting to Azure: {e}"})
    except HttpResponseError as e:
        logger.error(f"Tool Azure API Error (RG List): {e.message}", exc_info=False)
        ctx.error(f"Azure API Error listing RGs: Status={e.status_code}, Reason={e.reason}")
        return json.dumps({"error": f"Azure API Error: {e.message}"})
    except Exception as e:
        logger.error(f"Tool Error (RG List): {e}", exc_info=True)
        ctx.error(f"Failed to list resource groups: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

# list_storage_accounts (Keep as before)
@mcp.tool()
async def list_storage_accounts(
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
    ) -> str:
    """
    Lists details for all storage accounts in the specified Azure subscription.
    Returns a JSON string representing a list of storage account objects.

    Args:
        subscription_id: The Azure Subscription ID to query.
        auth_type: The authentication method to use ('default', 'spn', 'identity'). Defaults to 'default'.
    """
    if not subscription_id:
        return json.dumps({"error": "Azure Subscription ID is required."})

    effective_auth_type = auth_type if auth_type is not None else "default"
    if effective_auth_type not in ["default", "spn", "identity"]:
         error_msg = f"Error: Invalid auth_type provided ('{auth_type}'). Must be 'default', 'spn', or 'identity'."
         logger.warning(error_msg)
         return json.dumps({"error": error_msg})

    logger.info(f"Tool: Listing storage accounts for sub: {subscription_id[:4]} (auth: {effective_auth_type})")
    ctx.info(f"Listing storage accounts for subscription {subscription_id[:4]}... using {effective_auth_type} auth.")

    try:
        credential = await get_azure_credential(effective_auth_type)
        async with credential:
            sa_list = await storage_accounts.list_storage_accounts_logic(credential, subscription_id)
            if not sa_list:
                ctx.info(f"No storage accounts found in subscription {subscription_id}.")
                return "[]"
            ctx.info(f"Successfully listed details for {len(sa_list)} storage accounts.")
            return json.dumps(sa_list, indent=2)
    except ConnectionError as e:
         logger.error(f"Tool Auth/Connection Error: {e}", exc_info=False)
         ctx.error(f"Azure Authentication/Connection Error: {e}")
         return json.dumps({"error": f"Error connecting to Azure: {e}"})
    except HttpResponseError as e:
        logger.error(f"Tool Azure API Error (SA List): {e.message}", exc_info=False)
        ctx.error(f"Azure API Error listing SAs: Status={e.status_code}, Reason={e.reason}")
        return json.dumps({"error": f"Azure API Error: {e.message}"})
    except Exception as e:
        logger.error(f"Tool Error (SA List): {e}", exc_info=True)
        ctx.error(f"Failed to list storage accounts: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

# list_storage_account_usage (Keep as before)
@mcp.tool()
async def list_storage_account_usage(
    subscription_id: str,
    resource_group_name: str,
    storage_account_name: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
    ) -> str:
    """
    Gets the used capacity for a specific storage account.
    Returns a JSON string containing the usage info (e.g., {"used_capacity": "1.23 TiB"}).

    Args:
        subscription_id: The Azure Subscription ID.
        resource_group_name: The name of the resource group containing the storage account.
        storage_account_name: The name of the storage account.
        auth_type: The authentication method ('default', 'spn', 'identity'). Defaults to 'default'.
    """
    if not all([subscription_id, resource_group_name, storage_account_name]):
        return json.dumps({"error": "Subscription ID, Resource Group Name, and Storage Account Name are required."})

    effective_auth_type = auth_type if auth_type is not None else "default"
    if effective_auth_type not in ["default", "spn", "identity"]:
         error_msg = f"Error: Invalid auth_type provided ('{auth_type}'). Must be 'default', 'spn', or 'identity'."
         logger.warning(error_msg)
         return json.dumps({"error": error_msg})

    logger.info(f"Tool: Getting usage for SA: {storage_account_name} in RG: {resource_group_name} (auth: {effective_auth_type})")
    ctx.info(f"Getting usage for {storage_account_name}...")

    try:
        credential = await get_azure_credential(effective_auth_type)
        async with credential:
            usage_str = await storage_accounts.get_storage_account_usage_logic(
                credential, subscription_id, resource_group_name, storage_account_name
            )
            ctx.info(f"Usage for {storage_account_name}: {usage_str}")
            return json.dumps({"used_capacity": usage_str})
    except ConnectionError as e:
         logger.error(f"Tool Auth/Connection Error: {e}", exc_info=False)
         ctx.error(f"Azure Authentication/Connection Error: {e}")
         return json.dumps({"error": f"Error connecting to Azure: {e}"})
    except Exception as e:
        logger.error(f"Tool Error (SA Usage): {e}", exc_info=True)
        ctx.error(f"Failed to get storage account usage: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

# list_storage_account_usage_all (UPDATED)
@mcp.tool()
async def list_storage_account_usage_all(
    subscription_id: str,
    auth_type: Optional[str] = "default",
    ctx: Context = None
    ) -> str:
    """
    Lists details AND used capacity for ALL storage accounts in the subscription.
    Returns a JSON string representing a list of storage account objects, each with an added 'used_capacity' field.
    *** WARNING: This tool can be VERY SLOW and resource-intensive for subscriptions with many storage accounts,
    as it fetches usage metrics individually for each account. Use with caution. ***

    Args:
        subscription_id: The Azure Subscription ID to query.
        auth_type: The authentication method ('default', 'spn', 'identity'). Defaults to 'default'.
    """
    if not subscription_id:
        return json.dumps({"error": "Azure Subscription ID is required."})

    effective_auth_type = auth_type if auth_type is not None else "default"
    if effective_auth_type not in ["default", "spn", "identity"]:
         error_msg = f"Error: Invalid auth_type provided ('{auth_type}'). Must be 'default', 'spn', or 'identity'."
         logger.warning(error_msg)
         return json.dumps({"error": error_msg})

    logger.info(f"Tool: Getting usage for ALL SAs in sub: {subscription_id[:4]} (auth: {effective_auth_type})")
    # More prominent warning to the client
    ctx.info(f"Listing ALL storage accounts and usage for subscription {subscription_id[:4]}... "
             f"*** WARNING: This may take a significant amount of time. ***")

    try:
        credential = await get_azure_credential(effective_auth_type)
        async with credential:
            # 1. Get all storage accounts
            sa_list = await storage_accounts.list_storage_accounts_logic(credential, subscription_id)
            total_accounts = len(sa_list)
            logger.info(f"Found {total_accounts} storage accounts. Now fetching usage for each...")
            # Report initial progress without message
            await ctx.report_progress(0, total_accounts)
            ctx.info(f"Found {total_accounts} SAs. Fetching usage (updates follow)...") # Separate info message

            # 2. Iterate and get usage for each
            results_with_usage = []
            for i, account_dict in enumerate(sa_list):
                sa_name = account_dict.get("name", "Unknown")
                rg_name = account_dict.get("resource_group", "Unknown")
                # Log progress to server logs
                logger.info(f"Fetching usage for {sa_name} in {rg_name} ({i+1}/{total_accounts})")
                # Report progress to client without message
                await ctx.report_progress(i, total_accounts)
                # Send separate info message to client
                ctx.info(f"Fetching usage for {sa_name} ({i+1}/{total_accounts})...")

                if sa_name != "Unknown" and rg_name != "Unknown":
                    usage_str = await storage_accounts.get_storage_account_usage_logic(
                        credential, subscription_id, rg_name, sa_name
                    )
                    account_dict["used_capacity"] = usage_str # Add usage to the dict
                else:
                     account_dict["used_capacity"] = "N/A (Info Missing)"
                     ctx.warning(f"Skipping usage fetch for account index {i} due to missing name/rg.")

                results_with_usage.append(account_dict)

            logger.info(f"Finished fetching usage for all {total_accounts} storage accounts.")
            # Report final progress without message
            await ctx.report_progress(total_accounts, total_accounts)
            ctx.info("Finished fetching usage for all storage accounts.") # Separate info message

            if not results_with_usage:
                return "[]"

            return json.dumps(results_with_usage, indent=2)

    except ConnectionError as e:
         logger.error(f"Tool Auth/Connection Error: {e}", exc_info=False)
         ctx.error(f"Azure Authentication/Connection Error: {e}")
         return json.dumps({"error": f"Error connecting to Azure: {e}"})
    except HttpResponseError as e:
        logger.error(f"Tool Azure API Error (SA List All Usage): {e.message}", exc_info=False)
        ctx.error(f"Azure API Error listing SAs: Status={e.status_code}, Reason={e.reason}")
        return json.dumps({"error": f"Azure API Error: {e.message}"})
    except Exception as e:
        logger.error(f"Tool Error (SA List All Usage): {e}", exc_info=True)
        ctx.error(f"Failed to list all storage account usage: {e}")
        return json.dumps({"error": f"An unexpected error occurred: {e}"})

# --- No __main__ block if running via main.py ---

# --- Running the Server ---
# Keep this commented out or remove if running via main.py/Uvicorn
if __name__ == "__main__":
    logger.info("Starting Azure Explorer MCP Server for stdio...")
    mcp.run()


# --- main.py (if using Uvicorn for SSE) ---
# No changes needed in main.py if you have it setup as before.
# It just needs to import the 'mcp' app object from this updated server.py