# azure_mcp_server/tools/config/auth.py
import os
import logging
from typing import Optional
from azure.identity.aio import DefaultAzureCredential, ClientSecretCredential, ManagedIdentityCredential
from azure.core.exceptions import ClientAuthenticationError
from dotenv import load_dotenv

load_dotenv()  # Load .env file if present, for local development
logger = logging.getLogger(__name__)

class AzureAuthenticator:
    def __init__(self):
        """Initializes the AzureAuthenticator."""
        pass

    async def get_credential(self, auth_type: str = "default"):
        """
        Retrieves and tests an Azure ASYNC credential based on the specified auth_type.
        The caller is responsible for closing the credential if it supports an `async close()` method
        (e.g., by using `async with await authenticator.get_credential(...) as credential:`).
        """
        logger.info(f"Attempting to get and test Azure credential using auth_type: {auth_type}")
        credential_instance = None # Keep a reference for potential close on error
        try:
            if auth_type == "spn":
                tenant_id = os.getenv("AZURE_TENANT_ID")
                client_id = os.getenv("AZURE_CLIENT_ID")
                client_secret = os.getenv("AZURE_CLIENT_SECRET")
                if not all([tenant_id, client_id, client_secret]):
                    err_msg = "For SPN auth, AZURE_TENANT_ID, AZURE_CLIENT_ID, and AZURE_CLIENT_SECRET environment variables must be set."
                    logger.error(err_msg)
                    raise EnvironmentError(err_msg)
                credential_instance = ClientSecretCredential(tenant_id=tenant_id, client_id=client_id, client_secret=client_secret)
                logger.info("Configured ClientSecretCredential for SPN auth.")
            elif auth_type == "identity":
                identity_client_id = os.getenv("AZURE_MANAGED_IDENTITY_CLIENT_ID")
                if identity_client_id:
                    credential_instance = ManagedIdentityCredential(client_id=identity_client_id)
                    logger.info(f"Configured ManagedIdentityCredential with client ID: {identity_client_id}.")
                else:
                    credential_instance = ManagedIdentityCredential()
                    logger.info("Configured ManagedIdentityCredential for system-assigned or default user-assigned identity.")
            elif auth_type == "default":
                credential_instance = DefaultAzureCredential()
                logger.info("Configured DefaultAzureCredential.")
            else:
                err_msg = f"Invalid auth_type '{auth_type}' specified. Must be 'default', 'spn', or 'identity'."
                logger.error(err_msg)
                raise ValueError(err_msg)

            logger.debug(f"Testing {auth_type} credential by acquiring token for 'https://management.azure.com/.default'...")
            # Test the credential. This also "warms it up".
            # The credential object returned is the one to be used by the caller with `async with`.
            await credential_instance.get_token("https://management.azure.com/.default")
            logger.info(f"Successfully tested and obtained token using {auth_type} credential.")
            return credential_instance

        except ClientAuthenticationError as e:
            msg = f"Azure authentication failed for auth_type '{auth_type}'. Ensure your environment is correctly configured for this auth method (e.g., logged in with Azure CLI for 'default', correct SPN variables, or Managed Identity assigned with permissions). Details: {e.message}"
            logger.error(msg, exc_info=False)
            raise ConnectionError(msg) from e
        except EnvironmentError as e: # For missing SPN variables
            logger.error(f"Configuration environment error for auth_type '{auth_type}': {e}", exc_info=False)
            raise ConnectionError(f"Configuration error for '{auth_type}': {e}") from e
        except ValueError as e: # For invalid auth_type
             logger.error(f"Invalid configuration for auth_type '{auth_type}': {e}", exc_info=False)
             raise ConnectionError(f"Invalid configuration: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected error during Azure credential retrieval for auth_type '{auth_type}': {e}", exc_info=True)
            if credential_instance and hasattr(credential_instance, "close"):
                try:
                    await credential_instance.close()
                except Exception as close_ex:
                    logger.error(f"Error closing credential during exception handling: {close_ex}", exc_info=True)
            raise ConnectionError(f"Unexpected error getting credentials for '{auth_type}': {e}") from e

    def get_subscription_id(self) -> Optional[str]:
        """
        Retrieves the Azure subscription ID from the AZURE_SUBSCRIPTION_ID environment variable.
        Returns None if not set, allowing tools to make it a required parameter.
        """
        subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        if not subscription_id:
            logger.info("AZURE_SUBSCRIPTION_ID environment variable is not set. Tools may require it as an explicit parameter.")
        else:
            logger.debug(f"Retrieved AZURE_SUBSCRIPTION_ID from environment: {subscription_id[:4]}...") # Log only prefix
        return subscription_id