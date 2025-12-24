# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies (ffmpeg is required for audio)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
# NOTE: Build context must be project root
COPY bot-music-casino/requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy Shared Library
COPY common /app/common

# Copy Bot Code
COPY bot-music-casino /app/bot

# Set Python Path to include root /app so 'common' can be imported
ENV PYTHONPATH=/app

WORKDIR /app/bot

# Run main.py when the container launches
CMD ["python", "main.py"]
