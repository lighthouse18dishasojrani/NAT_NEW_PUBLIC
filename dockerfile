FROM python:3.12.4

# Install system dependencies including telnet and ping
RUN apt-get update && \
    apt-get install -y \
    libaio1 \
    wget \
    unzip \
    x11-apps \
    telnet \
    inetutils-ping && \
    rm -rf /var/lib/apt/lists/*  # Cleanup

# Set the working directory inside the container
WORKDIR /app

# Create and activate a virtual environment
RUN python -m venv /app/venv

# Upgrade pip and install required packages in the virtual environment
RUN /app/venv/bin/pip install --upgrade pip

# Copy the requirements file to the working directory
COPY requirements.txt /app/

# Install the required Python packages in the virtual environment
RUN /app/venv/bin/pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY . /app/

# Set the PYTHONPATH environment variable
ENV PYTHONPATH=/app

# Set PATH to prioritize the virtual environment
ENV PATH="/app/venv/bin:$PATH"

# Expose the required port
EXPOSE 8000

# Start the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
