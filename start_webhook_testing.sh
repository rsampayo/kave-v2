#!/bin/bash

# Start the webhook testing environment
# This script starts both the FastAPI app and ngrok tunnel

# Check if ngrok is installed
if ! command -v ngrok &> /dev/null; then
    echo "Error: ngrok is not installed or not in PATH"
    echo "Please install ngrok from https://ngrok.com/download"
    exit 1
fi

# Check if required Python packages are installed
python -c "import httpx, pydantic, pydantic_settings" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Installing required Python packages..."
    pip install httpx pydantic pydantic-settings
fi

# Create docs directory if it doesn't exist
if [ ! -d "docs" ]; then
    mkdir -p docs
fi

# Start the webhook testing environment
echo "Starting webhook testing environment..."
python -m scripts.start_local_with_webhook 