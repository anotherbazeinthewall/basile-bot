# Build stage
FROM public.ecr.aws/docker/library/python:3.12.0-slim-bullseye AS builder

WORKDIR /app

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy only dependency files first
COPY pyproject.toml poetry.lock ./

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-interaction --no-ansi --no-root

# Final stage
FROM public.ecr.aws/docker/library/python:3.12.0-slim-bullseye

# Copy the Lambda adapter
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Copy Python packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages

WORKDIR /app

# Set environment variables in a single layer
ENV AWS_LAMBDA_FUNCTION_HANDLER=server.main:app \
    AWS_LWA_INVOKE_MODE=RESPONSE_STREAM \
    PORT=8000 \
    UVICORN_APP=server.main:app

# Copy application code
COPY . .

# AWS credentials should be handled by IAM roles instead of environment variables
ARG AWS_REGION
ENV AWS_REGION=${AWS_REGION}

EXPOSE 8000

CMD ["python", "server/main.py"]