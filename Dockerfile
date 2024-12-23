FROM public.ecr.aws/docker/library/python:3.12.0-slim-bullseye
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:0.8.4 /lambda-adapter /opt/extensions/lambda-adapter

# Set the working directory
WORKDIR /app

# Define build arguments
ARG AWS_REGION
ARG AWS_ACCESS_KEY_ID
ARG AWS_SECRET_ACCESS_KEY

# Set environment variables
ENV AWS_REGION=${AWS_REGION}
ENV AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
ENV AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
ENV AWS_LAMBDA_FUNCTION_HANDLER=server.main:app
ENV AWS_LWA_INVOKE_MODE=RESPONSE_STREAM
ENV PORT=8000
ENV UVICORN_APP=server.main:app

# Install poetry
RUN pip install poetry

# Copy poetry files
COPY pyproject.toml poetry.lock ./

# Configure poetry to not create a virtual environment in the container
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install --no-interaction --no-ansi --no-root

# Copy application code
COPY . .

# Expose the port FastAPI will run on
EXPOSE 8000

# Run the FastAPI app using the server's main block
CMD ["python", "server/main.py"]