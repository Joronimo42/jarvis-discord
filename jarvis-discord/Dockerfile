FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements and install them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot script.
COPY run.py .

# Run the bot.
CMD ["python", "run.py"]
