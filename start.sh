#!/bin/bash

echo "============================================"
echo "Starting Lead Generation Pipeline"
echo "============================================"
echo ""

# Activate virtual environment
source venv/bin/activate

# Start API Backend
echo "Starting API Backend (Port 8000)..."
python backend/api.py &
API_PID=$!

# Wait a moment for API to start
sleep 2

# Start Frontend
echo "Starting Frontend (Port 3000)..."
npm run dev &
FRONTEND_PID=$!

echo ""
echo "============================================"
echo "All services started!"
echo "============================================"
echo ""
echo "Access the application at:"
echo "- Frontend Dashboard: http://localhost:3000"
echo "- API Backend: http://localhost:8000"
echo "- API Docs: http://localhost:8000/docs"
echo "- n8n Editor: http://localhost:5678"
echo ""
echo "Press Ctrl+C to stop all services..."

# Wait for user interrupt
trap "kill $API_PID $FRONTEND_PID; exit" INT
wait
