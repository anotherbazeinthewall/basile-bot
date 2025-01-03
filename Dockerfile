# Build stage
FROM public.ecr.aws/docker/library/python:3.12-alpine AS builder

WORKDIR /app

# Install build dependencies
RUN apk add --no-cache \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev \
    cargo \
    rust \
    git \
    && pip install --no-cache-dir pipenv

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Install dependencies directly with Pipenv
RUN pipenv install --deploy --system \
    && pip install --no-cache-dir --force-reinstall boto3 botocore \
    && find /usr/local -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true \
    && find /usr/local -type f -name "*.pyc" -delete \
    && find /usr/local -type f -name "*.pyo" -delete \
    && find /usr/local -type f -name "*.egg-info" -exec rm -rf {} + \
    && find /usr/local -type f -name "*.txt" -delete \
    && find /usr/local -type f -name "*.md" -delete \
    && find /usr/local -type f -name "*.h" -delete \
    && find /usr/local -type d -name "test" -exec rm -rf {} + \
    && find /usr/local -type d -name "examples" -exec rm -rf {} + \
    && pip cache purge

# Final stage
FROM public.ecr.aws/docker/library/python:3.12-alpine

# Install runtime dependencies
RUN apk add --no-cache \
    libstdc++ \
    libffi

# Copy the Lambda adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

# Set environment variables in a single layer
ENV AWS_LAMBDA_FUNCTION_HANDLER=backend.server:app \
    AWS_LWA_INVOKE_MODE=RESPONSE_STREAM \
    PORT=8000 \
    UVICORN_APP=backend.server:app \
    # Python optimizations
    PYTHONOPTIMIZE=2 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONMALLOC=malloc \
    PYTHONHASHSEED=random \
    PYTHONNOUSERSITE=1 \
    # Process optimizations
    WEB_CONCURRENCY=1 \
    WORKERS_PER_CORE=1 \
    MAX_WORKERS=1

WORKDIR /app

# Copy application files (excluding those in .dockerignore)
COPY . .

# AWS credentials should be handled by IAM roles instead of environment variables
ARG AWS_REGION
ENV AWS_REGION=${AWS_REGION}

EXPOSE 8000

# Use optimized Python runtime with all optimizations enabled
CMD ["python", "-OO", "backend/server.py"]
