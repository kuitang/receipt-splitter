FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Create and set the working directory
WORKDIR /code

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    libmagic-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

# Install gunicorn for production server
RUN pip install gunicorn

# Copy project
COPY . /code/

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port 8000
EXPOSE 8000

# Run the application
CMD ["gunicorn", "receipt_splitter.wsgi:application", "--bind", "0.0.0.0:8000"]