#!/bin/bash
set -e # Exit on error

# Change to script's directory
cd "$(dirname "$0")"
# Get project root directory (one level up)
PROJECT_ROOT="$(cd .. && pwd)"

# Debug and interaction mode handling
DEBUG=false
NO_INTERACTION=false
while getopts "dn" opt; do
    case $opt in
        d) DEBUG=true ;;
        n) NO_INTERACTION=true ;;
    esac
done
$DEBUG && set -x

export AWS_PAGER="cat"

###########################################
# Function Definitions
###########################################

# Function to handle errors
handle_error() {
    local part=$1
    local error=$2
    echo "❌ Error during $part: $error"
    echo "Please fix the error and try again."
    exit 1
}

# Function to prompt for input with default value
prompt_with_default() {
    local prompt=$1
    local default=$2
    
    if [ "$NO_INTERACTION" = true ]; then
        echo "$default"
        return
    fi
    
    read -p "$prompt [$default]: " input
    echo "${input:-$default}"
}

# Load configuration
load_configuration() {
    if [ -f config.json ]; then
        echo "Loading existing configuration..."
        while IFS="=" read -r key value; do
            if [ ! -z "$key" ]; then
                $DEBUG && echo "Setting: $key=$value"
                export "$key=$value"
            fi
        done < <(jq -r 'paths(scalars) as $p | "\($p | join("_") | ascii_upcase)=\(getpath($p))"' config.json)
        echo "✓ Configuration loaded successfully"
        return 0
    else
        echo "No existing configuration found, will create new one"
        return 1
    fi
}

# Function to save configuration
save_configuration() {
    # Create JSON structure
    jq -n \
    --arg account_id "$AWS_ACCOUNT_ID" \
    --arg region "$AWS_REGION" \
    --arg app_name "$APP_NAME" \
    --arg memory "$MEMORY_SIZE" \
    --arg timeout "$TIMEOUT" \
    --arg function_name "$FUNCTION_NAME" \
    --arg role_name "$ROLE_NAME" \
    --arg policy_name "$POLICY_NAME" \
    --arg repo_name "$REPO_NAME" \
    --arg role_arn "${ROLE_ARN:-}" \
    --arg ecr_registry "${ECR_REGISTRY:-}" \
    --arg repo_uri "${REPO_URI:-}" \
    --arg function_url "${FUNCTION_URL:-}" \
    '{
        core: {
            aws_account_id: $account_id,
            aws_region: $region,
            app_name: $app_name
        },
        lambda: {
            memory_size: $memory,
            timeout: $timeout
        },
        derived: {
            function_name: $function_name,
            role_name: $role_name,
            policy_name: $policy_name,
            repo_name: $repo_name,
            role_arn: $role_arn,
            ecr_registry: $ecr_registry,
            repo_uri: $repo_uri,
            function_url: $function_url
        }
    }' > config.json
    
    echo "✓ Configuration saved to config.json"
}

# Function to wait for Lambda readiness
wait_for_lambda_ready() {
    local function_name=$1
    local max_attempts=30
    local attempt=1
    local wait_time=10
    
    echo "Waiting for Lambda function to be ready for updates..."
    while [ $attempt -le $max_attempts ]; do
        if STATE=$(aws lambda get-function --function-name $function_name --query 'Configuration.State' --output text 2>/dev/null); then
            if [ "$STATE" = "Active" ]; then
                if ! aws lambda get-function --function-name $function_name --query 'Configuration.LastUpdateStatus' --output text | grep -q "InProgress"; then
                    echo "✓ Lambda function is ready for updates"
                    return 0
                fi
            fi
        fi
        echo "Attempt $attempt of $max_attempts: Function not ready yet, waiting ${wait_time} seconds..."
        sleep $wait_time
        attempt=$((attempt + 1))
    done
    echo "❌ Timeout waiting for Lambda function to be ready"
    return 1
}

# Function to apply tags
apply_tags() {
    local resource_arn=$1
    local region=$2
    aws resourcegroupstaggingapi tag-resources \
        --resource-arn-list "$resource_arn" \
        --tags "Application=$APP_NAME" \
        --region "$region"
}

###########################################
# Main Script
###########################################

echo "🚀 Starting Basile Bot Setup"
echo "This script will run all setup parts in sequence."
echo "------------------------------------------------------------"

# Check for jq
echo "Checking for jq..."
if ! command -v jq &> /dev/null; then
    echo "jq is required but not installed. Installing..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install jq
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        sudo apt-get update && sudo apt-get install -y jq
    else
        echo "Please install jq manually: https://stedolan.github.io/jq/download/"
        exit 1
    fi
fi
echo "✓ jq is available"

# Load existing configuration
echo "Loading configuration..."
if ! load_configuration; then
    echo "Starting with fresh configuration"
fi
echo "------------------------------------------------------------"

# Step 1: Interactive configuration
echo "Starting interactive configuration..."

# Get default AWS account ID
DEFAULT_AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text || echo "")

# Get default AWS region from the CLI configuration
DEFAULT_AWS_REGION=$(aws configure get region || echo "us-west-2")

AWS_ACCOUNT_ID=$(prompt_with_default "AWS Account ID" "${AWS_ACCOUNT_ID:-$DEFAULT_AWS_ACCOUNT_ID}")
AWS_REGION=$(prompt_with_default "AWS Region" "${AWS_REGION:-$DEFAULT_AWS_REGION}")
APP_NAME=$(prompt_with_default "Application name" "${APP_NAME:-basile-bot}")
MEMORY_SIZE=$(prompt_with_default "Lambda memory size (MB)" "${MEMORY_SIZE:-1024}")
TIMEOUT=$(prompt_with_default "Lambda timeout (seconds)" "${TIMEOUT:-900}")

# Sanitize application name
APP_NAME=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')

# Derived variables
FUNCTION_NAME="${APP_NAME}-lambda-function"
ROLE_NAME="${APP_NAME}-lambda-role"
POLICY_NAME="${APP_NAME}-bedrock-policy"
REPO_NAME="$APP_NAME"

# Review configuration
echo
cat << REVIEW
Review your settings:
------------------------------------------------------------
AWS Account ID: $AWS_ACCOUNT_ID
AWS Region: $AWS_REGION
Application Name: $APP_NAME
Function Name: $FUNCTION_NAME
Role Name: $ROLE_NAME
Policy Name: $POLICY_NAME
Repository Name: $REPO_NAME
Memory Size: $MEMORY_SIZE MB
Timeout: $TIMEOUT seconds
------------------------------------------------------------
REVIEW

if [ "$NO_INTERACTION" = false ]; then
    read -p "Do you want to save these settings? [Y/n] " confirm
    if [[ "$confirm" =~ ^[Nn] ]]; then
        echo "Setup cancelled."
        exit 1
    fi
fi

# Save configuration
save_configuration
echo "Configuration saved to deployment/config.json"
echo "------------------------------------------------------------"

# Step 2: Validate AWS credentials
echo "Verifying AWS credentials..."
if aws sts get-caller-identity &>/dev/null; then
    echo "✓ AWS credentials are valid"
else
    echo "⚠️ Warning: Could not verify AWS credentials"
    echo "Please ensure you have valid AWS credentials configured before proceeding"
    exit 1
fi

# Step 3: Local build and test
echo -e "\n📋 Building and testing locally..."
(cd "$PROJECT_ROOT" && docker-compose up --build -d)

echo "Testing local endpoint..."
max_attempts=6
attempt=1
wait_time=5

while [ $attempt -le $max_attempts ]; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo "Health check successful!"
        break
    fi
    [ $attempt -eq $max_attempts ] && { echo "Health check failed."; docker-compose down; exit 1; }
    sleep $wait_time
    attempt=$((attempt + 1))
done

(cd "$PROJECT_ROOT" && docker-compose down)
echo "Local testing complete."

# Step 4: ECR Setup
echo -e "\n📋 Setting up ECR..."
ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
REPO_URI="$ECR_REGISTRY/$REPO_NAME"

if ! aws ecr describe-repositories --repository-names $REPO_NAME &>/dev/null; then
    aws ecr create-repository --repository-name $REPO_NAME --region $AWS_REGION
    echo "Created repository: $REPO_NAME"
else
    echo "ECR repository $REPO_NAME already exists."
fi

# Tag the ECR repository
echo "Tagging ECR repository..."
ECR_REPOSITORY_ARN=$(aws ecr describe-repositories \
    --repository-names "$REPO_NAME" \
    --region "$AWS_REGION" \
    --query "repositories[0].repositoryArn" --output text)

if [ -n "$ECR_REPOSITORY_ARN" ]; then
    aws ecr tag-resource \
        --resource-arn "$ECR_REPOSITORY_ARN" \
        --tags Key=Application,Value="$APP_NAME" \
        || echo "Warning: Failed to tag ECR repository"
    echo "✓ Tagged ECR repository: $ECR_REPOSITORY_ARN"
else
    echo "❌ Failed to get ECR repository ARN"
fi

# Save the repository URI to the configuration
save_configuration
echo "ECR setup complete. Repository URI: $REPO_URI"

# Step 5: Docker Build and Push
echo -e "\n📋 Building and pushing Docker image..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
(cd "$PROJECT_ROOT" && docker buildx build --platform=linux/amd64 --provenance=false -t $REPO_NAME .)
docker tag $REPO_NAME:latest $REPO_URI:latest
docker push $REPO_URI:latest
echo "Docker image pushed to $REPO_URI"

# Step 6: IAM Setup
echo -e "\n📋 Setting up IAM roles and policies..."
# Create the trust policy document
cat > trust-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "Service": "lambda.amazonaws.com"
            },
            "Action": "sts:AssumeRole"
        }
    ]
}
EOF

# Create the Bedrock policy document
cat > bedrock-policy.json << EOF
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            "Resource": "*"
        }
    ]
}
EOF

# Create or validate the IAM role
if ! aws iam get-role --role-name $ROLE_NAME &>/dev/null; then
    aws iam create-role --role-name $ROLE_NAME --assume-role-policy-document file://trust-policy.json
    echo "Created IAM role: $ROLE_NAME"
    # Add a delay to allow IAM role to propagate
    echo "Waiting for IAM role to propagate..."
    sleep 10
else
    echo "IAM role $ROLE_NAME already exists."
fi

# Tag the IAM role
echo "Tagging IAM role..."
aws iam tag-role \
    --role-name "$ROLE_NAME" \
    --tags Key=Application,Value="$APP_NAME" \
    || echo "Warning: Failed to tag IAM role"
echo "✓ Tagged IAM role: $ROLE_NAME"

# Create or validate the Bedrock policy
POLICY_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:policy/$POLICY_NAME"
if ! aws iam get-policy --policy-arn $POLICY_ARN &>/dev/null; then
    aws iam create-policy --policy-name $POLICY_NAME --policy-document file://bedrock-policy.json
    echo "Created IAM policy: $POLICY_NAME"
else
    echo "IAM policy $POLICY_NAME already exists."
fi

# Attach the required policies to the IAM role
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name $ROLE_NAME --policy-arn $POLICY_ARN
ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME"

# Save the configuration
save_configuration

# Wait for IAM role and policy attachments to propagate
echo "Waiting for IAM role and policy attachments to propagate..."
sleep 10
echo "IAM setup complete. Role ARN: $ROLE_ARN"

# Step 7: Lambda Deployment
echo -e "\n📋 Setting up Lambda function..."

# Check if the Lambda function exists
if aws lambda get-function --function-name $FUNCTION_NAME &>/dev/null; then
    echo "Function $FUNCTION_NAME exists, updating function..."
    wait_for_lambda_ready $FUNCTION_NAME
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --image-uri $REPO_URI:latest
    wait_for_lambda_ready $FUNCTION_NAME
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --environment "Variables={AWS_LAMBDA_FUNCTION_HANDLER=server.app}"
else
    echo "Creating Lambda function $FUNCTION_NAME..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$REPO_URI:latest \
        --role $ROLE_ARN \
        --timeout $TIMEOUT \
        --memory-size $MEMORY_SIZE \
        --environment "Variables={AWS_LAMBDA_FUNCTION_HANDLER=server.app}"
fi

# Wait for the function to be ready
wait_for_lambda_ready $FUNCTION_NAME

# Tag the Lambda function
echo "Tagging Lambda function..."
LAMBDA_ARN="arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$FUNCTION_NAME"
aws lambda tag-resource \
    --resource "$LAMBDA_ARN" \
    --tags Key=Application,Value="$APP_NAME" \
    || echo "Warning: Failed to tag Lambda function"
echo "✓ Tagged Lambda function: $FUNCTION_NAME"

# Setup Function URL
echo "Setting up Lambda Function URL..."
if ! FUNCTION_URL=$(aws lambda get-function-url-config --function-name $FUNCTION_NAME --query 'FunctionUrl' --output text 2>/dev/null); then
    echo "Creating new Function URL..."
    FUNCTION_URL=$(aws lambda create-function-url-config \
        --function-name $FUNCTION_NAME \
        --auth-type NONE \
        --cors '{"AllowOrigins": ["*"], "AllowMethods": ["*"], "AllowHeaders": ["*"]}' \
        --invoke-mode RESPONSE_STREAM \
        --query 'FunctionUrl' \
        --output text)
    
    # Add permission for Function URL
    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id FunctionURLAllowPublicAccess \
        --action lambda:InvokeFunctionUrl \
        --principal "*" \
        --function-url-auth-type NONE \
        --output text
    echo "Created new Function URL: $FUNCTION_URL"
else
    echo "Updating existing Function URL configuration..."
    aws lambda update-function-url-config \
        --function-name $FUNCTION_NAME \
        --cors '{"AllowOrigins": ["*"], "AllowMethods": ["*"], "AllowHeaders": ["*"]}' \
        --invoke-mode RESPONSE_STREAM \
        >/dev/null
    echo "Using existing Function URL: $FUNCTION_URL"
    
    # Ensure permissions exist even for existing URL
    aws lambda add-permission \
        --function-name $FUNCTION_NAME \
        --statement-id FunctionURLAllowPublicAccess \
        --action lambda:InvokeFunctionUrl \
        --principal "*" \
        --function-url-auth-type NONE \
        --output text 2>/dev/null || true
fi

# Remove trailing slash if present
FUNCTION_URL="${FUNCTION_URL%/}"

# Save the configuration
save_configuration
echo "Lambda function setup complete."

# Step 8: Final Status and Testing
echo -e "\nTesting health endpoint..."
max_attempts=12
attempt=1
wait_time=20
echo "Testing endpoint: $FUNCTION_URL/health"

while [ $attempt -le $max_attempts ]; do
    echo "Attempt $attempt of $max_attempts: Calling health endpoint..."
    # Store both HTTP status code and response
    HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/curl_response "$FUNCTION_URL/health")
    HTTP_RESPONSE=$(</tmp/curl_response)
    
    if [ "$HTTP_STATUS" = "200" ]; then
        echo "Health check successful! Lambda is ready at $FUNCTION_URL"
        break
    else
        echo "Response status: $HTTP_STATUS"
        echo "Response body: $HTTP_RESPONSE"
    fi
    
    [ $attempt -eq $max_attempts ] && {
        echo "Health check failed after $max_attempts attempts."
        echo "Last status: $HTTP_STATUS"
        echo "Last response: $HTTP_RESPONSE"
        echo "Checking Lambda logs..."
        aws logs tail "/aws/lambda/$FUNCTION_NAME" --since 5m
        exit 1
    }
    
    echo "Waiting ${wait_time} seconds before next attempt..."
    sleep $wait_time
    attempt=$((attempt + 1))
done

# Step 9: Configure Warm-up Rule
echo -e "\n📋 Setting up warm-up rule..."
RULE_NAME="${APP_NAME}-warmup"

# Create or update the CloudWatch Events rule and capture the ARN
RULE_ARN=$(aws events put-rule \
    --name "$RULE_NAME" \
    --schedule-expression "rate(10 minutes)" \
    --region "$AWS_REGION" \
    --description "Keeps ${FUNCTION_NAME} warm by invoking it periodically" \
    --query 'RuleArn' \
    --output text) \
    || handle_error "CloudWatch Events rule creation/update" $?

# Tag the CloudWatch Events rule
echo "Tagging CloudWatch Events rule..."
aws events tag-resource \
    --resource-arn "$RULE_ARN" \
    --tags Key=Application,Value="$APP_NAME" \
    || echo "Warning: Failed to tag CloudWatch Events rule"
echo "✓ Tagged CloudWatch Events rule: $RULE_NAME"

# Check existing Lambda permissions
EXISTING_PERMISSION=$(aws lambda get-policy \
    --function-name "$FUNCTION_NAME" \
    --region "$AWS_REGION" 2>/dev/null | jq -r '.Policy' | jq -r '.Statement[] | select(.Sid == "WarmupPermission")' 2>/dev/null)

if [ ! -z "$EXISTING_PERMISSION" ]; then
    echo "Updating existing Lambda permission..."
    aws lambda remove-permission \
        --function-name "$FUNCTION_NAME" \
        --statement-id "WarmupPermission" \
        --region "$AWS_REGION" \
        || handle_error "Lambda permission removal" $?
else
    echo "Adding new Lambda permission..."
fi

# Add permission for CloudWatch Events to invoke the Lambda function
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "WarmupPermission" \
    --action "lambda:InvokeFunction" \
    --principal events.amazonaws.com \
    --source-arn "$RULE_ARN" \
    --region "$AWS_REGION" \
    || handle_error "Lambda permission update" $?

# Check existing targets
EXISTING_TARGET=$(aws events list-targets-by-rule \
    --rule "$RULE_NAME" \
    --region "$AWS_REGION" 2>/dev/null | jq -r '.Targets[] | select(.Id == "1")' 2>/dev/null)

if [ ! -z "$EXISTING_TARGET" ]; then
    echo "Updating existing CloudWatch Events target..."
    aws events remove-targets \
        --rule "$RULE_NAME" \
        --ids "1" \
        --region "$AWS_REGION" \
        || handle_error "CloudWatch Events target removal" $?
else
    echo "Adding new CloudWatch Events target..."
fi

# Create the input JSON and properly escape it
WARMUP_INPUT="{\"warmup\":true}"
ESCAPED_INPUT=$(echo "$WARMUP_INPUT" | jq -c -R .)

# Add the Lambda function as the target for the CloudWatch Events rule
aws events put-targets \
    --rule "$RULE_NAME" \
    --targets Id=1,Arn="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}",Input=$ESCAPED_INPUT \
    --region "$AWS_REGION" \
    || handle_error "CloudWatch Events target update" $?

# Note: Removed redundant Lambda function tagging since it's already tagged in the Lambda section

echo "✓ Warm-up rule configured successfully"
echo " - Rule Name: $RULE_NAME"
echo " - Schedule: Every 10 minutes"
echo " - Target: $FUNCTION_NAME"
echo "🎉 Setup Complete! Your application is available at $FUNCTION_URL"