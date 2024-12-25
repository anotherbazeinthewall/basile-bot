# Build stage
FROM public.ecr.aws/docker/library/python:3.12-slim-bullseye AS builder

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy requirements file
COPY requirements.txt .

# Install dependencies to a specific directory
RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install --no-cache-dir -r requirements.txt && \
    find /opt/venv -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true && \
    find /opt/venv -type f -name "*.pyc" -delete && \
    find /opt/venv -type f -name "*.pyo" -delete && \
    find /opt/venv -type f -name "*.dist-info" -exec rm -rf {} + && \
    find /opt/venv -type f -name "*.egg-info" -exec rm -rf {} + && \
    find /opt/venv -type f -name "*.txt" -delete && \
    find /opt/venv -type f -name "*.md" -delete && \
    find /opt/venv -type f -name "*.h" -delete && \
    find /opt/venv -type d -name "tests" -exec rm -rf {} + && \
    find /opt/venv -type d -name "test" -exec rm -rf {} +

# Final stage
FROM public.ecr.aws/docker/library/python:3.12-slim-bullseye

# Copy the Lambda adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables in a single layer
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH="/opt/venv/lib/python3.12/site-packages" \
    AWS_LAMBDA_FUNCTION_HANDLER=server.main:app \
    AWS_LWA_INVOKE_MODE=RESPONSE_STREAM \
    PORT=8000 \
    UVICORN_APP=server.main:app \
    # Python optimizations
    PYTHONOPTIMIZE=2 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Disable pip cache and bytecode writing
    PIP_NO_CACHE_DIR=1 \
    # Reduce memory usage
    PYTHONMALLOC=malloc \
    PYTHONHASHSEED=random \
    # Reduce startup time
    PYTHONPROFILEIMPORTTIME=0

WORKDIR /app

# Copy all application files (excluding those in .dockerignore)
COPY . .

# AWS credentials should be handled by IAM roles instead of environment variables
ARG AWS_REGION
ENV AWS_REGION=${AWS_REGION}

EXPOSE 8000

# Use optimized Python runtime with all optimizations enabled
CMD ["/opt/venv/bin/python", "-OO", "server/main.py"]