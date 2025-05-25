# tools/vm_details.py
import asyncio
from asyncio.log import logger
from typing import List, Dict, Any
from azure.identity import DefaultAzureCredential
from azure.mgmt.compute.aio import ComputeManagementClient
from azure.mgmt.resource import ResourceManagementClient
from azure.core.exceptions import ResourceNotFoundError
from .config.auth import AzureAuth
from azure.identity.aio import ClientSecretCredential, ManagedIdentityCredential, DefaultAzureCredential
from azure.core.exceptions import HttpResponseError
import os
SPECIFIC_TAGS = ['TEAM', 'AUTOSHUTDOWN']

# VM size to CPU/Memory mapping
VM_SIZE_MAPPING = {
    # E-Series
    "Standard_E8ds_v5": {"CPU": 8, "Memory": "64 GB"},
    "Standard_E16ds_v5": {"CPU": 16, "Memory": "128 GB"},
    "Standard_E32ds_v5": {"CPU": 32, "Memory": "256 GB"},
    "Standard_E64ds_v5": {"CPU": 64, "Memory": "512 GB"},
    # D-Series
    "Standard_D16s_v3": {"CPU": 16, "Memory": "64 GB"},
    "Standard_D32s_v3": {"CPU": 32, "Memory": "128 GB"},
    "Standard_D64s_v3": {"CPU": 64, "Memory": "256 GB"},
    "Standard_D4s_v3":  {"CPU": 4,  "Memory": "16 GB"},
}

async def get_azure_credential(auth_type: str = "default"):
    logger.info(f"Attempting Azure authentication using type: {auth_type}")
    try:
        if auth_type == "spn":
            tenant_id = os.getenv("AZURE_TENANT_ID")
            client_id = os.getenv("AZURE_CLIENT_ID")
            client_secret = os.getenv("AZURE_CLIENT_SECRET")
            if not all([tenant_id, client_id, client_secret]):
                raise ValueError("AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET must be set for SPN auth.")
            return ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
        elif auth_type == "identity":
            identity_client_id = os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID")
            return ManagedIdentityCredential(client_id=identity_client_id) if identity_client_id else ManagedIdentityCredential()
        else:
            return DefaultAzureCredential()
    except Exception as e:
        logger.error(f"Azure authentication failed: {e}", exc_info=True)
        raise ConnectionError(f"Failed to get Azure credentials for auth_type '{auth_type}': {e}")

def find_tag_value(tags: Dict[str, str], target_key: str) -> Any:
    target_key_clean = target_key.strip().lower()
    for k, v in tags.items():
        if k.strip().lower() == target_key_clean:
            return v
    return None

async def list_resource_groups(resource_client: ResourceManagementClient):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: list(resource_client.resource_groups.list()))

def get_vm_specs(vm_size: str) -> Dict[str, Any]:
    return VM_SIZE_MAPPING.get(vm_size, {"CPU": "", "Memory": ""})

async def get_vm_detail(vm_name: str, credential, subscription_id: str) -> Dict[str, Any]:
    compute_client = ComputeManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    try:
        resource_groups = await list_resource_groups(resource_client)

        for rg in resource_groups:
            try:
                vm = await compute_client.virtual_machines.get(rg.name, vm_name)
                instance_view = await compute_client.virtual_machines.instance_view(rg.name, vm_name)
                power_state = next(
                    (status.display_status for status in instance_view.statuses if status.code.startswith('PowerState')),
                    'Unknown'
                )

                tags = vm.tags or {}
                filtered_tags = {tag: find_tag_value(tags, tag) for tag in SPECIFIC_TAGS}

                vm_size = vm.hardware_profile.vm_size
                specs = get_vm_specs(vm_size)

                vm_details = {
                    "VM Name": vm.name,
                    "Resource Group": rg.name,
                    "Location": vm.location,
                    "Power State": power_state,
                    "VM Size": vm_size,
                    "CPU": specs["CPU"],
                    "Memory": specs["Memory"],
                    "OS Type": str(vm.storage_profile.os_disk.os_type),
                    "Tags": filtered_tags
                }
                return vm_details
            except ResourceNotFoundError:
                continue

        return {"VM Name": vm_name, "Error": "VM not found in any resource group."}

    except Exception as e:
        return {"VM Name": vm_name, "Error": str(e)}
    finally:
        await compute_client.close()

async def get_vm_details(vm_names: List[str]) -> List[Dict[str, Any]]:
    auth = AzureAuth()
    credential = auth.get_credential()
    subscription_id = auth.get_subscription_id()

    tasks = [get_vm_detail(vm_name, credential, subscription_id) for vm_name in vm_names]
    results = await asyncio.gather(*tasks)
    return results

async def get_vms_by_team(team_value: str) -> List[Dict[str, Any]]:
    auth = AzureAuth()
    credential = auth.get_credential
    subscription_id = auth.get_subscription_id()

    compute_client = ComputeManagementClient(credential, subscription_id)
    resource_client = ResourceManagementClient(credential, subscription_id)

    matched_vms = []
    try:
        resource_groups = await list_resource_groups(resource_client)

        for rg in resource_groups:
            async for vm in compute_client.virtual_machines.list(rg.name):
                tags = vm.tags or {}
                team_tag = find_tag_value(tags, "TEAM")
                if team_tag and team_tag.strip().lower() == team_value.strip().lower():
                    instance_view = await compute_client.virtual_machines.instance_view(rg.name, vm.name)
                    power_state = next(
                        (status.display_status for status in instance_view.statuses if status.code.startswith('PowerState')),
                        'Unknown'
                    )
                    vm_size = vm.hardware_profile.vm_size
                    specs = get_vm_specs(vm_size)

                    matched_vms.append({
                        "VM Name": vm.name,
                        "Resource Group": rg.name,
                        "Location": vm.location,
                        "Power State": power_state,
                        "VM Size": vm_size,
                        "CPU": specs["CPU"],
                        "Memory": specs["Memory"],
                        "OS Type": str(vm.storage_profile.os_disk.os_type),
                        "TEAM": team_tag
                    })
        return matched_vms
    finally:
        await compute_client.close()
