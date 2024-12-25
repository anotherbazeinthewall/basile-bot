#!/bin/bash

# Function to test endpoint with retries
test_endpoint() {
    echo "Starting container..."
    docker-compose up -d

    echo "Waiting for service to be ready..."
    for i in {1..30}; do  # Try for 30 seconds
        response=$(curl -s -w "\n%{http_code}" http://localhost:8000/health)
        http_code=$(echo "$response" | tail -n1)
        body=$(echo "$response" | head -n1)
        
        if [ "$http_code" -eq 200 ]; then
            echo "Service is ready! Response time:"
            time curl http://localhost:8000/health
            return
        fi
        echo "Attempt $i: Service not ready yet (HTTP $http_code)..."
        sleep 1
    done
    echo "Service failed to start within 30 seconds"
}

# Clean up first
docker-compose down

# Run the test
test_endpoint