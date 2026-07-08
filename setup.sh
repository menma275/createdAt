#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "=== Raspberry Pi System & Python Virtual Environment Setup ==="

# 1. Install system dependencies via apt
echo "-> Updating package lists..."
sudo apt-get update

echo "-> Installing system dependencies (apt.txt)..."
# Read packages from apt.txt and install them, ensuring python3-venv/dev are also present
sudo apt-get install -y python3-venv python3-dev $(cat dependencies/apt.txt | grep -v '^#')

# 2. Setup Python Virtual Environment (venv)
if [ ! -d "venv" ]; then
    echo "-> Creating Python virtual environment (venv)..."
    python3 -m venv venv
else
    echo "-> Virtual environment (venv) already exists."
fi

# 3. Activate virtual environment and install python dependencies
echo "-> Activating virtual environment..."
source venv/bin/activate

echo "-> Upgrading pip, setuptools, and wheel..."
pip install --upgrade pip setuptools wheel

echo "-> Installing Python packages (requirments.txt)..."
pip install -r dependencies/requirments.txt

echo "=== Setup Completed Successfully! ==="
echo "To activate the environment and run the application, execute:"
echo "  source venv/bin/activate"
echo "  python main.py"
