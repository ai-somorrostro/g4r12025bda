# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the scrapper code
COPY . .

# Create directories for data and logs
RUN mkdir -p /app/data /app/logs

# Run the scraper
CMD ["python", "data-extraction.py"]
