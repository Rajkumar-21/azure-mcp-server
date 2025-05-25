# azure_mcp_server/tools/vm_details.py
import asyncio
import logging # Use standard logging
from typing import List, Dict, Any, Optional
from azure.core.credentials_async import AsyncTokenCredential # For type hinting
from azure.mgmt.compute.aio import ComputeManagementClient
from azure.mgmt.resource.resources.aio import ResourceManagementClient # Ensure async client
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
import os

logger = logging.getLogger(__name__) # Use standard logging

SPECIFIC_TAGS = ['TEAM', 'AUTOSHUTDOWN'] # Keep as is

# VM size to CPU/Memory mapping (Keep as is or expand)
VM_SIZE_MAPPING = {
    "Standard_E8ds_v5": {"CPU": 8, "Memory": "64 GB"}, "Standard_E16ds_v5": {"CPU": 16, "Memory": "128 GB"},
    "Standard_E32ds_v5": {"CPU": 32, "Memory": "256 GB"}, "Standard_E64ds_v5": {"CPU": 64, "Memory": "512 GB"},
    "Standard_D16s_v3": {"CPU": 16, "Memory": "64 GB"}, "Standard_D32s_v3": {"CPU": 32, "Memory": "128 GB"},
    "Standard_D64s_v3": {"CPU": 64, "Memory": "256 GB"}, "Standard_D4s_v3":  {"CPU": 4,  "Memory": "16 GB"},
}

# Removed get_azure_credential function - this is handled by AzureAuthenticator in server.py

def _find_tag_value(tags: Optional[Dict[str, str]], target_key: str) -> Optional[str]:
    if not tags:
        return None
    target_key_clean = target_key.strip().lower()
    for k, v in tags.items():
        if k.strip().lower() == target_key_clean:
            return v
    return None

async def _list_resource_groups_from_client(resource_mgmt_client: ResourceManagementClient) -> List[Any]: # Returns list of ResourceGroup objects
    """Helper to list all resource groups using an active async client."""
    rgs = []
    async for rg in resource_mgmt_client.resource_groups.list():
        rgs.append(rg)
    return rgs

def _get_vm_specs(vm_size: Optional[str]) -> Dict[str, Any]:
    if not vm_size:
        return {"CPU": "N/A", "Memory": "N/A"}
    return VM_SIZE_MAPPING.get(vm_size, {"CPU": "Unknown", "Memory": "Unknown"})

async def get_vm_detail_logic(
    credential: AsyncTokenCredential,
    subscription_id: str,
    vm_name: str
) -> Dict[str, Any]:
    """
    Core logic to get detailed information for a specific Azure VM.
    Searches for the VM across all resource groups in the subscription.
    """
    logger.info(f"Logic: Getting details for VM '{vm_name}' in subscription '{subscription_id[:4]}...'")
    # Credential itself is managed by the caller (server.py tool method)
    async with ComputeManagementClient(credential, subscription_id) as compute_client, \
               ResourceManagementClient(credential, subscription_id) as resource_client:
        try:
            resource_groups = await _list_resource_groups_from_client(resource_client)
            logger.debug(f"Logic: Found {len(resource_groups)} resource groups to search for VM '{vm_name}'.")

            for rg in resource_groups:
                try:
                    logger.debug(f"Logic: Checking for VM '{vm_name}' in resource group '{rg.name}'...")
                    vm = await compute_client.virtual_machines.get(rg.name, vm_name, expand='instanceView')
                    # instance_view = await compute_client.virtual_machines.instance_view(rg.name, vm_name) # Already got with expand

                    power_state = 'Unknown'
                    if vm.instance_view and vm.instance_view.statuses:
                        power_state_status = next(
                            (s.display_status for s in vm.instance_view.statuses if s.code and s.code.startswith('PowerState/')),
                            None
                        )
                        if power_state_status:
                            power_state = power_state_status

                    tags = vm.tags or {}
                    filtered_tags = {tag_key: _find_tag_value(tags, tag_key) for tag_key in SPECIFIC_TAGS}
                    # Ensure all SPECIFIC_TAGS keys are present, even if value is None
                    for tag_key in SPECIFIC_TAGS:
                        if tag_key not in filtered_tags:
                             filtered_tags[tag_key] = None


                    vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else None
                    specs = _get_vm_specs(vm_size)
                    os_type = str(vm.storage_profile.os_disk.os_type) if vm.storage_profile and vm.storage_profile.os_disk else "Unknown"

                    vm_details = {
                        "VM Name": vm.name,
                        "Id": vm.id,
                        "Resource Group": rg.name,
                        "Location": vm.location,
                        "Power State": power_state,
                        "VM Size": vm_size or "N/A",
                        "CPU": specs["CPU"],
                        "Memory": specs["Memory"],
                        "OS Type": os_type,
                        "Tags": tags, # Return all tags
                        "Filtered Tags": filtered_tags # And specific ones
                    }
                    logger.info(f"Logic: Found VM '{vm_name}' in RG '{rg.name}'.")
                    return vm_details
                except ResourceNotFoundError:
                    logger.debug(f"Logic: VM '{vm_name}' not found in resource group '{rg.name}'.")
                    continue # Try next resource group
                except HttpResponseError as http_err:
                    # Handle cases where a VM might exist but is in a failed state or inaccessible
                    logger.warning(f"Logic: HTTP error when trying to get VM '{vm_name}' in RG '{rg.name}': {http_err.message}")
                    continue


            logger.warning(f"Logic: VM '{vm_name}' not found in any resource group in subscription '{subscription_id[:4]}...'.")
            return {"Error": f"VM '{vm_name}' not found in subscription '{subscription_id}'."}

        except Exception as e:
            logger.error(f"Logic: Error getting VM details for '{vm_name}': {e}", exc_info=True)
            return {"Error": f"An unexpected error occurred while fetching details for VM '{vm_name}': {str(e)}"}

async def get_vms_by_team_logic(
    credential: AsyncTokenCredential,
    subscription_id: str,
    team_value: str
) -> List[Dict[str, Any]]:
    """
    Core logic to list VMs that have a 'TEAM' tag matching the given team_value.
    """
    logger.info(f"Logic: Searching for VMs with TEAM tag '{team_value}' in subscription '{subscription_id[:4]}...'")
    matched_vms = []
    # Credential itself is managed by the caller (server.py tool method)
    async with ComputeManagementClient(credential, subscription_id) as compute_client, \
               ResourceManagementClient(credential, subscription_id) as resource_client:
        try:
            resource_groups = await _list_resource_groups_from_client(resource_client)
            logger.debug(f"Logic: Found {len(resource_groups)} RGs to search for VMs with TEAM '{team_value}'.")

            for rg in resource_groups:
                logger.debug(f"Logic: Listing VMs in resource group '{rg.name}' to check TEAM tag...")
                async for vm in compute_client.virtual_machines.list(rg.name):
                    tags = vm.tags or {}
                    current_team_tag_value = _find_tag_value(tags, "TEAM")

                    if current_team_tag_value and current_team_tag_value.strip().lower() == team_value.strip().lower():
                        logger.info(f"Logic: Found matching VM '{vm.name}' in RG '{rg.name}' for TEAM '{team_value}'. Fetching instance view...")
                        try:
                            # Fetch instance view separately for power state for matching VMs
                            vm_instance_view = await compute_client.virtual_machines.instance_view(rg.name, vm.name)
                            power_state = 'Unknown'
                            if vm_instance_view and vm_instance_view.statuses:
                                power_state_status = next(
                                    (s.display_status for s in vm_instance_view.statuses if s.code and s.code.startswith('PowerState/')),
                                    None
                                )
                                if power_state_status:
                                    power_state = power_state_status
                        except Exception as iv_ex:
                            logger.warning(f"Logic: Could not get instance view for VM '{vm.name}': {iv_ex}", exc_info=False)
                            power_state = "Error fetching status"


                        vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else None
                        specs = _get_vm_specs(vm_size)
                        os_type = str(vm.storage_profile.os_disk.os_type) if vm.storage_profile and vm.storage_profile.os_disk else "Unknown"

                        matched_vms.append({
                            "VM Name": vm.name,
                            "Id": vm.id,
                            "Resource Group": rg.name,
                            "Location": vm.location,
                            "Power State": power_state,
                            "VM Size": vm_size or "N/A",
                            "CPU": specs["CPU"],
                            "Memory": specs["Memory"],
                            "OS Type": os_type,
                            "Tags": tags, # Return all tags
                            "TEAM Tag": current_team_tag_value # Explicitly show the matched tag value
                        })
            logger.info(f"Logic: Found {len(matched_vms)} VMs matching TEAM tag '{team_value}'.")
            return matched_vms
        except Exception as e:
            logger.error(f"Logic: Error listing VMs by TEAM tag '{team_value}': {e}", exc_info=True)
            # Return what was found so far, or an empty list if error was early
            # Depending on desired behavior, could also raise or return an error structure
            return [{"Error": f"An error occurred while searching for VMs by TEAM tag: {str(e)}"}] if not matched_vms else matched_vms