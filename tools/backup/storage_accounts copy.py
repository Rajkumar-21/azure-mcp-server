# tools/storage_accounts.py
import logging
from typing import List, Dict, Any, Optional, Tuple
from azure.identity.aio import DefaultAzureCredential # Async
from azure.mgmt.storage.aio import StorageManagementClient # Async
from azure.mgmt.monitor.aio import MonitorManagementClient # Async
from azure.core.exceptions import HttpResponseError
# We don't strictly need the Enum imports if using hasattr/getattr robustly

logger = logging.getLogger(__name__)

# _format_bytes helper function remains the same
def _format_bytes(byte_value: Optional[float]) -> str:
    """Helper to format bytes into GB or TiB."""
    if byte_value is None:
        return "N/A"
    gb = byte_value / (1024 ** 3)
    tib = byte_value / (1024 ** 4)
    if tib >= 1:
        return f"{round(tib, 2)} TiB"
    else:
        return f"{round(gb, 2)} GB"

# --- Updated list_storage_accounts_logic function ---
async def list_storage_accounts_logic(
    credential: DefaultAzureCredential,
    subscription_id: str
    ) -> List[Dict[str, Any]]:
    """
    Core logic to list storage account details for a subscription.
    """
    logger.info(f"Executing logic: Listing storage accounts for subscription {subscription_id[:4]}...")
    accounts_list: List[Dict[str, Any]] = []
    async with StorageManagementClient(credential, subscription_id) as client:
        async for account in client.storage_accounts.list():
            # Extract resource group name from ID (keep this logic)
            try:
                resource_group_name = account.id.split("/")[4]
            except IndexError:
                resource_group_name = "Unknown"
                logger.warning(f"Could not parse resource group name from ID: {account.id}")

            # --- Helper function to safely get enum value or string ---
            def safe_get_value(attr: Any, attr_name: str, account_name: str) -> Optional[str]:
                if attr is None:
                    return None
                if hasattr(attr, 'value'): # Check if it has a 'value' attribute (likely an enum)
                    return attr.value
                else: # Otherwise, treat it as a string or other simple type
                    logger.debug(f"Account {account_name}: Attribute {attr_name} type {type(attr)} has no 'value'. Treating as string: {attr}")
                    return str(attr)
            # --- End Helper ---

            # Safely get potentially missing parent attributes
            account_sku = getattr(account, 'sku', None)
            account_properties = getattr(account, 'properties', None) # <-- Fix: Use getattr here
            account_primary_endpoints = getattr(account, 'primary_endpoints', None)
            account_creation_time = getattr(account, 'creation_time', None)
            account_access_tier = getattr(account, 'access_tier', None)
            account_allow_blob_public_access = getattr(account, 'allow_blob_public_access', None)
            account_allow_shared_key_access = getattr(account, 'allow_shared_key_access', None)
            account_kind = getattr(account, 'kind', None)

            account_dict = {
                "id": account.id,
                "name": account.name,
                "resource_group": resource_group_name,
                "location": account.location, # Location is usually present
                "sku": {
                    "name": getattr(account_sku, 'name', None),
                    "tier": safe_get_value(getattr(account_sku, 'tier', None), 'sku.tier', account.name)
                } if account_sku else None,
                "kind": safe_get_value(account_kind, 'kind', account.name),
                "tags": account.tags if account.tags is not None else {},
                "properties": {
                    # Access sub-properties only if parent 'account_properties' exists
                    "provisioning_state": safe_get_value(getattr(account_properties, 'provisioning_state', None), 'properties.provisioning_state', account.name) if account_properties else None,
                    "primary_endpoints": {
                         "blob": getattr(account_primary_endpoints, 'blob', None),
                         "dfs": getattr(account_primary_endpoints, 'dfs', None),
                         "file": getattr(account_primary_endpoints, 'file', None),
                         "queue": getattr(account_primary_endpoints, 'queue', None),
                         "table": getattr(account_primary_endpoints, 'table', None),
                         "web": getattr(account_primary_endpoints, 'web', None),
                    } if account_primary_endpoints else None,
                    "creation_time": account_creation_time.isoformat() if account_creation_time else None,
                    "account_replication_type": getattr(account_sku, 'name', None), # Use the safely acquired sku name
                    "access_tier": safe_get_value(account_access_tier, 'access_tier', account.name),
                    "allow_blob_public_access": account_allow_blob_public_access,
                    "allow_shared_key_access": account_allow_shared_key_access,
                } if account_properties else None, # Only create properties dict if account_properties exists
            }
            accounts_list.append(account_dict)

    logger.info(f"Logic: Found {len(accounts_list)} storage accounts.")
    return accounts_list

# --- Keep the get_storage_account_usage_logic function as it was before ---
async def get_storage_account_usage_logic(
    credential: DefaultAzureCredential,
    subscription_id: str,
    resource_group_name: str,
    account_name: str
    ) -> str:
    """
    Core logic to get the used capacity for a specific storage account.
    Returns formatted string (e.g., '1.23 TiB', '45.67 GB') or 'N/A'.
    """
    logger.info(f"Executing logic: Getting usage for {account_name} in {resource_group_name}...")
    async with MonitorManagementClient(credential, subscription_id) as monitor_client:
        resource_id = (
            f"/subscriptions/{subscription_id}/resourceGroups/{resource_group_name}"
            f"/providers/Microsoft.Storage/storageAccounts/{account_name}"
        )
        try:
            metrics_data = await monitor_client.metrics.list(
                resource_uri=resource_id,
                timespan="PT12H",
                interval="PT1H",
                metricnames="UsedCapacity",
                aggregation="Average",
                metricnamespace="Microsoft.Storage/storageAccounts"
            )

            latest_average: Optional[float] = None
            if metrics_data.value:
                for item in metrics_data.value:
                    if item.timeseries:
                        for timeseries in item.timeseries:
                            if timeseries.data:
                                for data in reversed(timeseries.data):
                                    if data.average is not None:
                                        latest_average = data.average
                                        break
                                if latest_average is not None: break
                        if latest_average is not None: break
                if latest_average is not None:
                     formatted_capacity = _format_bytes(latest_average)
                     logger.info(f"Logic: Usage for {account_name}: {formatted_capacity}")
                     return formatted_capacity

            logger.warning(f"Logic: No valid 'UsedCapacity' metric data found for {account_name} in the last 12 hours.")
            return "N/A (No recent data)"

        except HttpResponseError as e:
            logger.error(f"❌ Error retrieving UsedCapacity for {account_name}: {e.message}", exc_info=False)
            if "ResourceNotFound" in str(e):
                 return "N/A (Not Found)"
            elif "AuthorizationFailed" in str(e):
                 return "N/A (Permission Denied)"
            else:
                 return f"N/A (API Error: {e.status_code})"
        except Exception as e:
            logger.error(f"❌ Unexpected error retrieving UsedCapacity for {account_name}: {e}", exc_info=True)
            return "N/A (Error)"