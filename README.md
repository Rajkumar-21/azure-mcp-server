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
- aiohttp: HTTP client/server for asyncio
- azure-identity: Azure authentication
- azure-mgmt-*: Azure management libraries
- mcp[cli]: Model Context Protocol implementation
- python-dotenv: Environment variable management
- uvicorn: ASGI server implementation

3. Configure environment variables:
Create a `.env` file in the root directory with the following variables (as needed):
```env
AZURE_SUBSCRIPTION_ID=your-subscription-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_ID=your-client-id
AZURE_CLIENT_SECRET=your-client-secret
AZURE_MANAGED_IDENTITY_CLIENT_ID=your-managed-identity-client-id  # Optional
```

## Running the Server

1. Start the MCP server:
```bash
python server.py
```

2. The server will initialize and start listening for MCP requests.

## Available MCP Tools

The MCP server exposes the following tools for Azure resource management:

| Tool Name | Input Parameters | Description | Return Format |
|-----------|-----------------|-------------|---------------|
| list_resource_groups | • subscription_id (required)<br>• auth_type (optional) | Lists all resource groups in a subscription | JSON array of resource groups with their details |
| list_storage_accounts | • subscription_id (required)<br>• auth_type (optional) | Lists all storage accounts in a subscription | JSON array of storage accounts with their configurations |
| list_storage_account_usage | • subscription_id (required)<br>• resource_group_name (required)<br>• storage_account_name (required)<br>• auth_type (optional) | Gets storage capacity usage for a specific account | JSON object with used capacity in GB/TiB |

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