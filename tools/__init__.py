# azure_mcp_server/tools/__init__.py
from . import resource_groups
from . import storage_accounts
from . import vm_details
from . import trigger_automation_runbooks # Add this line
from .config import auth # If you also import auth from here