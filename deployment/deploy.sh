#!/bin/bash
set -e # Exit on error
unset AWS_REGION
export AWS_PAGER="cat"

# Determine script and project locations
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
if [[ "$SCRIPT_DIR" == */deployment ]]; then
    PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
else
    PROJECT_ROOT="$SCRIPT_DIR"
fi
DEPLOYMENT_DIR="$SCRIPT_DIR"

# Get default app name from directory
DEFAULT_APP_NAME=$(basename "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')

# Debug and interaction mode handling
DEBUG=false 
NO_INTERACTION=false
while getopts dn opt; do [ "$opt" = d ] && DEBUG=true || [ "$opt" = n ] && NO_INTERACTION=true; done
$DEBUG && set -x

if ! command -v jq &> /dev/null; then
    echo "Please install jq manually: https://stedolan.github.io/jq/download/"
    exit 1
fi

###########################################
# Functions
###########################################

handle_error() { echo "❌ Error during $1: $2" && echo "Please fix the error and try again." && exit 1; }

prompt_with_default() {
    [ "$NO_INTERACTION" = true ] && echo "$2" && return
    read -p "$1 [$2]: " input && echo "${input:-$2}"
}

DEPLOYMENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

save_configuration() {
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
    }' > "$DEPLOYMENT_DIR/config.json"
    
    echo "✓ Configuration saved to deployment/config.json"
}

wait_for_lambda() {
    local function_name=$1
    local max_attempts=10
    local attempt=1
    echo -n "Waiting for Lambda function"
    while [ $attempt -le $max_attempts ]; do
        if aws lambda get-function --function-name $function_name \
            --query '[Configuration.State, Configuration.LastUpdateStatus]' \
            --output text | grep -q "^Active.*[^InProgress]$"; then
            echo " ✓"
            return 0
        fi
        echo -n "."
        sleep 5
        ((attempt++))
    done
    echo " failed ❌"
    echo "Timeout after ${max_attempts} attempts"
    return 1
}

###########################################
# Step 1: Interactive configuration
###########################################
load_configuration() {
    if [ -f "$DEPLOYMENT_DIR/config.json" ]; then
        echo -n "Loading existing configuration... "
        export CONFIG_EXISTS=true
        eval "$(jq -r '.core * .lambda * .derived | to_entries | .[] | "export \(.key | ascii_upcase)=\(.value | @sh)"' "$DEPLOYMENT_DIR/config.json")"
        echo "✓"
    else
        echo -e "\nCreating new configuration"
        echo "------------------------------------------------------------"
        export CONFIG_EXISTS=false
    fi
}

configure_interactively() {
    local defaults=(
        "AWS Account ID;$(aws sts get-caller-identity --query Account --output text || echo '')"
        "AWS Region;$(aws configure get region || echo 'us-west-2')"
        "Application name;$DEFAULT_APP_NAME"
        "Lambda memory size (MB);512"
        "Lambda timeout (seconds);900"
    )
    
    local variables=(AWS_ACCOUNT_ID AWS_REGION APP_NAME MEMORY_SIZE TIMEOUT)
    
    for i in "${!defaults[@]}"; do
        IFS=";" read -r prompt default <<< "${defaults[$i]}"
        eval "${variables[$i]}=$(prompt_with_default "$prompt" "${!variables[$i]:-$default}")"
    done
    
    APP_NAME=$(echo "$APP_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9-]/-/g')
    FUNCTION_NAME="${APP_NAME}-lambda-function"
    ROLE_NAME="${APP_NAME}-lambda-role"
    POLICY_NAME="${APP_NAME}-bedrock-policy"
    REPO_NAME="$APP_NAME"
}

show_review() {
    cat << REVIEW
------------------------------------------------------------
${1:-REVIEW CURRENT SETTINGS}:
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
}

handle_configuration() {
    load_configuration
    [ "$CONFIG_EXISTS" = false ] && configure_interactively
    show_review
    
    if [ "$NO_INTERACTION" = false ]; then
        read -p "Do you want to proceed with these settings? [Y/n] " confirm
        if [[ "$confirm" =~ ^[Nn] ]]; then
            if [ "$CONFIG_EXISTS" = true ]; then
                read -p "Do you want to reconfigure settings? [Y/n] " reconfig
                if [[ "$reconfig" =~ ^[Yy]$ ]] || [ -z "$reconfig" ]; then
                    configure_interactively
                    show_review "REVIEW UPDATED SETTINGS"
                    read -p "Do you want to save these settings? [Y/n] " confirm
                    [[ "$confirm" =~ ^[Nn] ]] && { echo "Setup cancelled."; exit 1; }
                else
                    echo "Setup cancelled."; exit 1
                fi
            else
                echo "Setup cancelled."; exit 1
            fi
        fi
    fi
    
    save_configuration
    echo -e "Configuration saved to deployment/config.json\n------------------------------------------------------------"
}

handle_configuration

###########################################
# Step 2: Validate AWS credentials
###########################################

echo -n "Verifying AWS credentials... "
aws sts get-caller-identity &>/dev/null && echo "✓" || { echo "❌"; echo "Please configure valid AWS credentials and try again."; exit 1; }

###########################################
# Step 3: Local build and test
###########################################

echo -e "\n📋 Building and testing locally..."
cd "$PROJECT_ROOT"
docker-compose up --build -d

echo "Testing local endpoint..."
for i in {1..6}; do
    if curl -s http://localhost:8000/health | grep -q "healthy"; then
        echo "Health check successful!"
        break
    fi
    [ $i -eq 6 ] && { echo "Health check failed."; docker-compose down; exit 1; }
    sleep 5
done

docker-compose down
echo "Local testing complete."

###########################################
# Step 4: ECR Setup
###########################################

echo -e "\n📋 Setting up ECR..."
ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
REPO_URI="$ECR_REGISTRY/$REPO_NAME"

# Create repository if it doesn't exist
aws ecr describe-repositories --repository-names "$REPO_NAME" &>/dev/null \
    || aws ecr create-repository --repository-name "$REPO_NAME" --region "$AWS_REGION" \
    && echo "Using repository: $REPO_NAME"

# Tag repository
ECR_REPOSITORY_ARN=$(aws ecr describe-repositories \
    --repository-names "$REPO_NAME" \
    --query "repositories[0].repositoryArn" \
    --output text) \
    && aws ecr tag-resource \
        --resource-arn "$ECR_REPOSITORY_ARN" \
        --tags Key=Application,Value="$APP_NAME" \
        || echo "Warning: Failed to tag ECR repository"
save_configuration
echo "ECR setup complete. Repository URI: $REPO_URI"

###########################################
# Step 5: Docker Build and Push
###########################################

echo -e "\n📋 Building and pushing Docker image..."
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $ECR_REGISTRY
(cd "$PROJECT_ROOT" && docker buildx build --platform=linux/amd64 --provenance=false -t $REPO_NAME .)
docker tag $REPO_NAME:latest $REPO_URI:latest
docker push $REPO_URI:latest
echo "Docker image pushed to $REPO_URI"

###########################################
# Step 6: IAM Setup
###########################################

echo -e "\n📋 Setting up IAM roles and policies..."

# Create policy documents inline
TRUST_POLICY=$(jq -n '{
    Version: "2012-10-17",
    Statement: [{
        Effect: "Allow",
        Principal: { Service: "lambda.amazonaws.com" },
        Action: "sts:AssumeRole"
    }]
}')

BEDROCK_POLICY=$(jq -n '{
    Version: "2012-10-17",
    Statement: [{
        Effect: "Allow",
        Action: [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
        Resource: "*"
    }]
}')

# Setup IAM role
if ! aws iam get-role --role-name "$ROLE_NAME" &>/dev/null; then
    echo "Creating IAM role: $ROLE_NAME"
    aws iam create-role \
    --role-name "$ROLE_NAME" \
        --assume-role-policy-document "$TRUST_POLICY" \
    --tags Key=Application,Value="$APP_NAME" \
        >/dev/null || handle_error "IAM role creation" $?
    sleep 5
else
    echo "Using existing IAM role: $ROLE_NAME"
    aws iam tag-role --role-name "$ROLE_NAME" --tags Key=Application,Value="$APP_NAME" 2>/dev/null || true
fi

# Setup Bedrock policy
POLICY_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:policy/$POLICY_NAME"
if ! aws iam get-policy --policy-arn "$POLICY_ARN" &>/dev/null; then
    echo "Creating IAM policy: $POLICY_NAME"
    aws iam create-policy \
        --policy-name "$POLICY_NAME" \
        --policy-document "$BEDROCK_POLICY" \
        >/dev/null || handle_error "IAM policy creation" $?
else
    echo "Using existing IAM policy: $POLICY_NAME"
fi

# Attach policies
echo "Attaching policies to role..."
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam attach-role-policy --role-name "$ROLE_NAME" --policy-arn "$POLICY_ARN"
ROLE_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:role/$ROLE_NAME"
save_configuration

echo "IAM setup complete. Role ARN: $ROLE_ARN"

###########################################
# Step 7: Lambda Deployment
###########################################

echo -e "\n📋 Setting up Lambda function..."

# Common Lambda configuration
LAMBDA_CONFIG=(
    --timeout $TIMEOUT
    --memory-size $MEMORY_SIZE
        --environment "Variables={AWS_LAMBDA_FUNCTION_HANDLER=server.app}"
)

# Function URL configuration
URL_CONFIG=(
    --cors '{"AllowOrigins": ["*"], "AllowMethods": ["*"], "AllowHeaders": ["*"]}'
    --invoke-mode RESPONSE_STREAM
)

# Deploy Lambda function
if aws lambda get-function --function-name $FUNCTION_NAME &>/dev/null; then
    echo "Updating existing function $FUNCTION_NAME..."
wait_for_lambda $FUNCTION_NAME
    aws lambda update-function-code --function-name $FUNCTION_NAME --image-uri $REPO_URI:latest
    wait_for_lambda $FUNCTION_NAME
    aws lambda update-function-configuration --function-name $FUNCTION_NAME "${LAMBDA_CONFIG[@]}"
else
    echo "Creating new Lambda function $FUNCTION_NAME..."
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --package-type Image \
        --code ImageUri=$REPO_URI:latest \
        --role $ROLE_ARN \
        "${LAMBDA_CONFIG[@]}"
fi

wait_for_lambda $FUNCTION_NAME

# Tag Lambda function
echo "Tagging Lambda function..."
LAMBDA_ARN="arn:aws:lambda:$AWS_REGION:$AWS_ACCOUNT_ID:function:$FUNCTION_NAME"
aws lambda tag-resource --resource "$LAMBDA_ARN" --tags Key=Application,Value="$APP_NAME" \
    || echo "Warning: Failed to tag Lambda function"

# Setup Function URL
echo "Setting up Lambda Function URL..."
if ! FUNCTION_URL=$(aws lambda get-function-url-config --function-name $FUNCTION_NAME --query 'FunctionUrl' --output text 2>/dev/null); then
    echo "Creating new Function URL..."
    FUNCTION_URL=$(aws lambda create-function-url-config \
        --function-name $FUNCTION_NAME \
        --auth-type NONE \
        "${URL_CONFIG[@]}" \
        --query 'FunctionUrl' \
        --output text)
else
    echo "Updating existing Function URL configuration..."
    aws lambda update-function-url-config --function-name $FUNCTION_NAME "${URL_CONFIG[@]}" >/dev/null
fi

# Ensure Function URL permissions
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id FunctionURLAllowPublicAccess \
    --action lambda:InvokeFunctionUrl \
    --principal "*" \
    --function-url-auth-type NONE \
    --output text 2>/dev/null || true
FUNCTION_URL="${FUNCTION_URL%/}"
save_configuration
echo "Lambda function setup complete. URL: $FUNCTION_URL"

###########################################
# Step 8: Final Status and Testing
###########################################

echo -e "\n📋 Testing health endpoint..."
echo -n "Testing endpoint $FUNCTION_URL/health"
attempt=1
max_attempts=10
wait_time=10

while [ $attempt -le $max_attempts ]; do
    # Store both HTTP status code and response
    HTTP_STATUS=$(curl -s -w "%{http_code}" -o /tmp/curl_response "$FUNCTION_URL/health")
    HTTP_RESPONSE=$(</tmp/curl_response)
    
    if [ "$HTTP_STATUS" = "200" ]; then
        echo "✓"
        echo "Health check successful! Lambda is ready at $FUNCTION_URL"
        break
    fi
    
    echo -n "."
    if [ $attempt -eq $max_attempts ]; then
        echo " ❌"
        echo "Health check failed after $max_attempts attempts."
        echo "Last status: $HTTP_STATUS"
        echo "Last response: $HTTP_RESPONSE"
        echo "Checking Lambda logs..."
        aws logs tail "/aws/lambda/$FUNCTION_NAME" --since 5m
        exit 1
    fi
    
    sleep $wait_time
    attempt=$((attempt + 1))
done

###########################################
# Step 9: Configure Warm-up Rule
###########################################

echo -e "\n📋 Setting up warm-up rule..."
RULE_NAME="${APP_NAME}-warmup"
LAMBDA_ARN="arn:aws:lambda:${AWS_REGION}:${AWS_ACCOUNT_ID}:function:${FUNCTION_NAME}"

# Create or update the CloudWatch Events rule
echo "Configuring CloudWatch Events rule..."
RULE_ARN=$(aws events put-rule \
    --name "$RULE_NAME" \
    --schedule-expression "rate(5 minutes)" \
    --description "Keeps ${FUNCTION_NAME} warm by invoking it periodically" \
    --tags "Key=Application,Value=$APP_NAME" \
    --query 'RuleArn' \
    --output text) \
    || handle_error "CloudWatch Events rule setup" $?

# Update Lambda permissions
aws lambda remove-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "WarmupPermission" \
    --region "$AWS_REGION" 2>/dev/null || true
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "WarmupPermission" \
    --action "lambda:InvokeFunction" \
    --principal events.amazonaws.com \
    --source-arn "$RULE_ARN" \
    || handle_error "Lambda permission update" $?

# Update CloudWatch Events target
aws events remove-targets \
    --rule "$RULE_NAME" \
    --ids "1" 2>/dev/null || true
aws events put-targets \
    --rule "$RULE_NAME" \
    --targets "Id=1,Arn=$LAMBDA_ARN,Input=$(echo '{"warmup":true}' | jq -c -R .)" \
    || handle_error "CloudWatch Events target update" $?

echo "✓ Warm-up rule configured successfully"
echo " - Rule Name: $RULE_NAME"
echo " - Schedule: Every 5 minutes"
echo " - Target: $FUNCTION_NAME"

###########################################
# Step 10: COMPLETE!!!
###########################################

echo "🎉 Setup Complete! Your application is available at $FUNCTION_URL"