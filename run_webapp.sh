#!/bin/bash

# QA LLM Evaluator Web App Launcher
echo "🚌 Starting QA LLM Evaluator Web Application..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📋 Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found. Please create one with your API keys:"
    echo "   GEMINI_API_KEY=your_api_key_here"
    echo "   BEARER_TOKEN=your_bearer_token_here"
    echo ""
fi

# Create static directory if it doesn't exist
mkdir -p static

# Run the web application
echo "🌐 Starting web server..."
echo "📱 Access the application at: http://localhost:5000"
echo "🔄 Press Ctrl+C to stop the server"
echo ""

python web_app.py
