# Use an official Python runtime as a parent image
# Using python 3.13 slim version for smaller image size
FROM python:3.13-slim

# Set the working directory in the container
WORKDIR /app

# Install uv using pip (uv needs pip to install itself initially)
# Using --no-cache-dir to keep the image smaller
RUN pip install --no-cache-dir uv

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt ./

# Install dependencies using uv and the lock file for reproducibility
# Use --system to install packages into the system site-packages
# Use --no-cache to avoid caching downloads inside the image layer
RUN uv pip install --system --no-cache -r requirements.txt

# Copy the rest of the application code into the container
# This includes main.py, server.py, and the tools/ directory
COPY . .

# Inform Docker that the container listens on port 8000 (defined in main.py)
# This does not publish the port, just documents it.
EXPOSE 8000

# Define environment variables for Azure Authentication (placeholders)
# --- IMPORTANT ---
# These should NOT be hardcoded here. They should be passed in
# securely at runtime (e.g., via docker run -e, Kubernetes secrets,
# Azure Container Apps secrets/environment variables).
# Add placeholders for documentation purposes.
# ENV AZURE_TENANT_ID="YOUR_TENANT_ID_RUNTIME"
# ENV AZURE_CLIENT_ID="YOUR_CLIENT_ID_RUNTIME"
# ENV AZURE_CLIENT_SECRET="YOUR_CLIENT_SECRET_RUNTIME"
# ENV AZURE_MANAGED_IDENTITY_CLIENT_ID="YOUR_MANAGED_IDENTITY_CLIENT_ID_RUNTIME" # Optional

# Command to run the application using Uvicorn when the container starts
# Runs the 'app' object from the 'main' module (main.py)
# Listens on all interfaces (0.0.0.0) inside the container on port 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]