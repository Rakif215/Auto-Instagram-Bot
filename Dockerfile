# Use the official Python 3.12 slim image to keep things small but standard
FROM python:3.12-slim

# Set non-interactive to avoid prompts during apt-get
ENV DEBIAN_FRONTEND=noninteractive

# Update system and install FFmpeg and fonts
RUN apt-get update -y && apt-get install -y \
    ffmpeg \
    fonts-liberation \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Set up the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -U pip setuptools && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure data and output directories exist
RUN mkdir -p data output logs music videos fonts

# The background bot process will run main.py --schedule
CMD ["python", "main.py", "--schedule"]
