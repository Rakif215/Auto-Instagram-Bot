#!/bin/bash
# VPS Setup Script for Trending HubX Automation
# Run this script on your new Ubuntu VPS to install all dependencies.

echo "========================================================"
echo "🎬 Starting VPS Setup for Trending HubX Automation..."
echo "========================================================"

# 1. Update system
echo "⏳ Updating system packages..."
sudo apt-update -y && sudo apt upgrade -y

# 2. Install FFmpeg and system dependencies
echo "⏳ Installing FFmpeg and required packages..."
sudo apt install -y ffmpeg python3-pip python3-venv git htop tmux

# 3. Create project directory
echo "⏳ Setting up project directory..."
mkdir -p ~/projects
cd ~/projects

# Note: The user will need to clone their repo or upload files here.
echo "========================================================"
echo "✅ System setup complete!"
echo ""
echo "Next Steps:"
echo "1. Upload your code to ~/projects/image_automation"
echo "2. Create a virtual environment: python3 -m venv venv"
echo "3. Activate it: source venv/bin/activate"
echo "4. Install Python packages: pip install -r requirements.txt"
echo "5. Create your .env file with your API keys"
echo "6. Setup the cronjob with: crontab -e"
echo "========================================================"
