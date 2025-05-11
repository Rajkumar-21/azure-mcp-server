# Azure MCP Server

A Model Context Protocol (MCP) server implementation for Azure resource management and exploration. This server provides a structured interface to interact with Azure resources using the Model Context Protocol, making it easier to manage and monitor Azure infrastructure programmatically.

## Overview

The Azure MCP Server is a Python-based implementation that serves as a bridge between MCP clients and Azure services. It provides a set of tools and endpoints to manage various Azure resources such as Resource Groups and Storage Accounts, with built-in authentication handling and structured response formats.

## Features

- Asynchronous Azure operations using modern Azure SDK
- Multiple authentication methods support (Default, Service Principal, Managed Identity)
- Structured response format using MCP protocol
- Comprehensive error handling and logging
- Environment variable configuration support

## Prerequisites

- Python 3.13 or higher
- Azure Subscription
- Azure CLI (recommended for local development)

## Setup and Installation

1. Clone the repository:
```powershell
git clone <repository-url>
cd azure-mcp-server
```

2. Install uv (Universal Virtualenv):
```powershell
curl -LsSf https://astral.sh/uv/install.ps1 | powershell
```

3. Create virtual environment and install dependencies:
```powershell
# Create and activate virtual environment
uv venv
.\.venv\Scripts\Activate.ps1

# Install dependencies from pyproject.toml
uv pip sync pyproject.toml
```

The project uses the following key dependencies:
```
[project]
name = "azure-mcp-server"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.13"
dependencies = [
    "aiohttp>=3.11.18",
    "azure-identity>=1.21.0",
    "azure-mgmt-monitor>=6.0.2",
    "azure-mgmt-resource>=23.3.0",
    "azure-mgmt-storage>=22.2.0",
    "httpx>=0.28.1",
    "mcp[cli]>=1.6.0",
    "python-dotenv>=1.1.0",
    "starlette>=0.46.2",
    "uvicorn>=0.34.2",
]
```

3. Configure environment variables:
Create a `.env` file in the root directory with the following variables (replace based on `auth_type` needed):
```env
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_MANAGED_IDENTITY_CLIENT_ID=your-managed-identity-client-id  # Optional
```

## Running the Server

1. Start the MCP server:

* Using Stdio Transport
    ```
    uv run server.py
    ```
* Using SSE Transport

    If you want to expose mcp server as SSE comment below section in **server.py**

    ```
    # Keep this commented out or remove if running via main.py/Uvicorn
    if __name__ == "__main__":
        logger.info("Starting Azure Explorer MCP Server for stdio...")
        mcp.run()

    ```
    Now run below command to run below command:
    ```
    uv run main.py
    ```
    It should start Uvicorn, listening on `http://127.0.0.1:8000`

```
INFO:__main__:Starting Uvicorn ASGI server on 127.0.0.1:8000
INFO:     Started server process [your_pid]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```
This server is now running and ready to accept MCP connections over the SSE transport. It is NOT using stdio anymore.

**How to Test SSE Connection**

Since the server is now running independently and listening on HTTP for SSE connections, you cannot use `mcp dev server.py` (which forces stdio). 

You need a client configured to connect via SSE.

Here are a few ways:

**Method A: MCP Inspector (Standalone Mode)**

* Keep uv run main.py running in one terminal.
* Open a new terminal. Make sure the virtual environment is active there too.
* Launch the Inspector standalone (without mcp dev):

    ```
    npx @modelcontextprotocol/inspector
    ```

(Note: This uses npx to run the inspector directly. You don't pass your server script here.)

* The MCP Inspector UI will appear, but it won't be connected initially.
* In the "Server Connection" pane at the top:
  * Select `SSE` from the "Transport" dropdown.
  * Enter the URL where your server is running: `http://127.0.0.1:8000/sse` (or the appropriate URL if you changed host/port).
  * Click the **"Connect"** button (it might look like a plug icon or similar).
* **Check Connection**: The UI should indicate a successful connection. You should also see log messages in the terminal running uv run main.py indicating a client connected (like GET requests).
* **Test Tools**: Now navigate to the "Tools" tab in the Inspector, select your Azure tools (list_resource_groups, list_storage_accounts, etc.), enter arguments (like subscription_id, auth_type), and click "Call Tool". The results should appear in the output pane.


**Method B: VS Code (Using GitHub Copilot Chat Agent)**

If you use VS Code, the GitHub Copilot Chat extension can act as an MCP Host/Client.

* Keep uv run main.py running.
* Open VS Code.
* Open VS Code Settings (JSON): Press Ctrl+Shift+P (or Cmd+Shift+P), type "Preferences: Open User Settings (JSON)", and select it.
* Add MCP Server Configuration: Add or modify the mcp.servers section in your settings.json. Crucially, specify the url and transport:

```json
"mcp": {
        "servers": {
                "azure-mcp-server": {
                "url": "http://127.0.0.1:8080/sse", // replace hostname based on the host
                "type": "sse"
            }
        }
    }
```

* Save settings.json.
* Reload VS Code: Press Ctrl+Shift+P, type "Developer: Reload Window", and select it.
* Open Copilot Chat: Open the chat view (usually an icon in the activity bar).
* Check Connection: You might see messages about MCP servers connecting in the Output panel (select "GitHub Copilot Chat" or "MCP" from the dropdown).
* Interact with Tools: In the Copilot Chat input, type @workspace /tools list to see if your Azure tools are listed. Then, try invoking one, e.g., @workspace /invoke list_resource_groups `subscription_id=YOUR_SUB_ID` `auth_type=default`




## Available MCP Tools

The MCP server exposes the following tools for Azure resource management:

| Tool Name | Input Parameters | Description | Return Format |
|-----------|-----------------|-------------|---------------|
| list_resource_groups | • subscription_id (required)<br>• auth_type (required) | Lists all resource groups in a subscription | JSON array of resource groups with their details |
| list_storage_accounts | • subscription_id (required)<br>• auth_type (required) | Lists all storage accounts in a subscription | JSON array of storage accounts with their configurations |
| list_storage_account_usage | • subscription_id (required)<br>• resource_group_name (required)<br>• storage_account_name (required)<br>• auth_type (required) | Gets storage capacity usage for a specific account | JSON object with used capacity in GB/TiB |
| list_storage_account_usage_all | • subscription_id (required)<br>• auth_type (required) | Gets storage capacity usage for a specific account | JSON object with used capacity in GB/TiB |

Note: For all tools, the `auth_type` parameter accepts:
- `"default"`: Uses DefaultAzureCredential (default)
- `"spn"`: Uses Service Principal authentication
- `"identity"`: Uses Managed Identity authentication

## Authentication Methods

The server supports three authentication methods:

1. **Default Azure Credential** (default)
   - Uses `DefaultAzureCredential` from Azure Identity library
   - Suitable for local development and testing

2. **Service Principal** (spn)
   - Uses `ClientSecretCredential`
   - Requires AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET

3. **Managed Identity** (identity)
   - Uses `ManagedIdentityCredential`
   - Suitable for Azure-hosted deployments
   - Optionally accepts AZURE_MANAGED_IDENTITY_CLIENT_ID

## Error Handling

The server implements comprehensive error handling for:
- Azure API errors
- Authentication failures
- Invalid requests
- Resource not found scenarios

All errors are logged and returned in a structured format following the MCP protocol.

## Logging

The server uses Python's built-in logging module with the following features:
- Configurable log levels (default: INFO)
- Detailed operation logging
- Authentication attempt logging
- Error and exception logging

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

See the [LICENSE](LICENSE) file for details.