# tools/resource_groups.py
import logging
from typing import List, Dict, Any, Optional
from azure.identity.aio import DefaultAzureCredential # Use the async version
from azure.mgmt.resource.resources.aio import ResourceManagementClient

logger = logging.getLogger(__name__)

async def list_resource_groups_logic(
    credential: DefaultAzureCredential, # Pass credential in
    subscription_id: str
    ) -> List[Dict[str, Any]]:
    """
    Core logic to list resource group details for a subscription.

    Args:
        credential: An authenticated Azure async credential.
        subscription_id: The Azure Subscription ID.

    Returns:
        A list of dictionaries, each representing a resource group's details.

    Raises:
        Exception: If the Azure API call fails.
    """
    logger.info(f"Executing logic: Listing resource groups for subscription {subscription_id[:4]}...")
    rg_details_list: List[Dict[str, Any]] = []
    count = 0
    async with ResourceManagementClient(credential, subscription_id) as client:
        async for rg in client.resource_groups.list():

            # --- Helper function to safely get enum value or string ---
            def safe_get_value(attr, attr_name: str, rg_name: str) -> Optional[str]:
                 if attr is None:
                     return None
                 if hasattr(attr, 'value'):
                     return attr.value
                 else:
                     logger.debug(f"ResourceGroup {rg_name}: Unexpected type for {attr_name}: {type(attr)}. Treating as string: {attr}")
                     return str(attr)
            # --- End Helper ---

            rg_dict = {
                "id": rg.id,
                "name": rg.name,
                "location": rg.location,
                "tags": rg.tags if rg.tags is not None else {},
                "properties": {
                    # Use helper for provisioning_state
                    "provisioning_state": safe_get_value(getattr(rg.properties, 'provisioning_state', None), 'properties.provisioning_state', rg.name) if rg.properties else None
                },
                "managed_by": rg.managed_by
            }
            rg_details_list.append(rg_dict)
            count += 1
            if count % 20 == 0:
                 logger.info(f"Logic: Processed {count} resource groups...")
        logger.info(f"Logic: Finished iteration. Found {len(rg_details_list)} resource groups.")
        return rg_details_list