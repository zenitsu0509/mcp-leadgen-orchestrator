#!/bin/bash

echo "============================================"
echo "Lead Generation Pipeline - Setup"
echo "============================================"
echo ""

echo "Creating virtual environment..."
py -3.11 -m venv .venv

echo ""
echo "Activating virtual environment..."
source .venv/Scripts/activate
echo ""
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "Creating data directory..."
mkdir -p data

echo ""
echo "Initializing database..."
python backend/database.py

echo ""
echo "Installing Node.js dependencies..."
npm install

echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env and configure your settings"
echo "2. Add your GROQ_API_KEY to .env"
echo "3. Run './start.sh' to launch all services"
echo ""
