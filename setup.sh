#!/bin/bash

echo "Setting up AI Assistant for Assistants..."

# Create virtual environment
python -m venv venv

# Activate virtual environment
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    source venv/Scripts/activate
else
    source venv/bin/activate
fi

# Install dependencies
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env file. Please update it with your API keys."
fi

echo "Setup complete!"
echo ""
echo "Next steps:"
echo "1. Add your Google API key to .env"
echo "2. Set up Gmail API credentials (see README.md)"
echo "3. Run: uvicorn app.main:app --reload"
