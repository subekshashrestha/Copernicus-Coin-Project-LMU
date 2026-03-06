#!/bin/bash

echo "========================================="
echo "Running Build Script - Installing Packages"
echo "========================================="

cd /home/site/wwwroot

# Create virtual environment
python3 -m venv .venv

# Activate it
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install all dependencies
pip install -r requirements.txt

echo "========================================="
echo "Build Complete!"
echo "========================================="
