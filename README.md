# basile-bot

basile-bot is a self-contained experiment in simulating a chat CLI in the browser while achieving scale-to-zero pricing in the cloud. The bot leverages Claude 3.5 Haiku via AWS Bedrock to reference my resume, LinkedIn profile, and GitHub account while answering questions about my professional experience. The application serves as a template for future web development projects that prioritize terminal-like interactions with spotty-utilization patterns and low tolerance for cold-start delays.

### Frontend

The frontend leverages an Xterm.js terminal with WebGL rendering and Pyodide to create a high-performance Python CLI experience in the browser. The architecture employs:

- A Web Worker-based Pyodide runtime for non-blocking Python execution
- Message-based architecture for reliable terminal I/O and state management
- Custom stream processor for real-time response handling
- WebGL-accelerated terminal rendering for smooth output

All application logic is concentrated in `frontend/client.py`, with the JavaScript infrastructure providing terminal operations, Python runtime management, and error handling behind the scenes. The template obfuscates Pyodide's unique operations (like print or input) to simplify network requests and async operations, creating both a development and user experience that closely mirrors programming with a local Python environment. Theoretically, all that's needed to use this frontend template for a new application is a new `client.py`.

### Backend

The application employs a FastAPI backend with streaming response capabilities to provide a tight API for core application logic. The architecture features:

- Modular service layer for processing data from GitHub, LinkedIn, and hosted resume
- Bedrock client configuration with graceful credential fallback
- Optimized file serving with conditional caching strategies
- Configurable CORS and streaming response headers for production deployment

The design prioritizes simplicity and reusability while maintaining efficient scaling capabilities and robust error handling.

### Deployment

The application uses a containerized deployment strategy with AWS Lambda, enabling true scale-to-zero with minimal cold starts. A five-minute warmup rule keeps the container responsive while staying within Lambda's free tier. The Docker setup supports local testing with mounted credentials, while the Lambda Web Adapter enables response streaming. The deployment automation (`deploy.sh`, `destroy.sh`) provides:

- Interactive configuration with state persistence
- Comprehensive AWS resource management (IAM, Lambda, ECR, EventBridge)
- Health checks and deployment verification
- Graceful error handling and rollback capabilities
- Local testing validation before deployment

## Getting Started

### Prerequisites

- Docker
- pipenv (for dependency management)
- AWS credentials with Bedrock access (us-west-2)

### Deployment Prerequisites

Required AWS permissions:

- IAM: Role/policy management and attachment
- Lambda: Function management, URL configuration, logging
- ECR: Repository management, image pushing
- EventBridge: Rule management, Lambda trigger configuration

AWS managed policies that grant required permissions:

- AWSLambda_FullAccess
- AmazonECR_FullAccess
- IAMFullAccess
- CloudWatchEventsFullAccess

## Local Development

Clone and modify as needed. Core application logic lives in:

- `frontend/client.py`: Frontend terminal interface
- `backend/server.py`: FastAPI backend
- `backend/modules/`: Backend service modules

Project uses pipenv for dependency management. Docker configuration optimized for minimal image size using Alpine base.

## License

MIT License

Feel free to review and adapt to your specific use case. Unless your name is Alex Basile, you might not find the basile-bot useful as is ;) 