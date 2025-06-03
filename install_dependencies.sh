#!/bin/bash

echo "Installing Python and system dependencies..."

# Install Python, Selenium, Firefox, and required image libs
sudo dnf install -y python3-pip python3-devel firefox geckodriver \
  libjpeg-turbo-devel zlib-devel

# Set up virtual environment
if [ ! -d "venv" ]; then
  python3 -m venv venv
fi

source venv/bin/activate

# Install Python packages
pip install --upgrade pip
pip install flask apscheduler selenium pillow opencv-python-headless numpy

echo "✅ Setup complete."
echo "➡️  Activate the environment with: source venv/bin/activate"
echo "➡️  Run the app with: python app.py"
