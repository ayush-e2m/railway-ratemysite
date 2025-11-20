#!/bin/bash

# RateMySite Live Compare Setup Script
echo "🚀 Setting up RateMySite Live Compare..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install Python 3.9 or later."
    exit 1
fi

echo "✅ Python 3 found"

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "⬆️ Upgrading pip..."
pip install --upgrade pip

# Install dependencies
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p static/downloads
mkdir -p logs

# Run tests
echo "🧪 Running tests..."
python test_app.py

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 Setup complete! You can now run the application with:"
    echo "   python app.py"
    echo ""
    echo "📝 For Railway deployment:"
    echo "   1. Push this code to GitHub"
    echo "   2. Connect your repo to Railway"
    echo "   3. Deploy automatically"
    echo ""
    echo "🔗 The app will be available at http://localhost:5000"
else
    echo "❌ Setup failed. Please check the error messages above."
    exit 1
fi
