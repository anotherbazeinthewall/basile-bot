#!/bin/bash
set -e # Exit on error

# Change to script's directory
cd "$(dirname "$0")"
# Get project root directory (one level up)
PROJECT_ROOT="$(cd .. && pwd)"

# Debug mode handling
DEBUG=false
while getopts "d" opt; do
    case $opt in
        d) DEBUG=true ;;
    esac
done
$DEBUG && set -x

export AWS_PAGER="cat"

###########################################
# Function Definitions
###########################################

# Function to handle errors
handle_error() {
    echo "Error occurred during: $1"
    echo "Error message: $2"
    read -p "Continue with teardown? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Teardown cancelled."
        exit 1
    fi
}

# Load config if it exists
load_configuration() {
    if [ -f config.json ]; then
        echo "Loading configuration..."
        # Load core variables
        AWS_ACCOUNT_ID=$(jq -r '.core.aws_account_id' config.json)
        AWS_REGION=$(jq -r '.core.aws_region' config.json)
        APP_NAME=$(jq -r '.core.app_name' config.json)
        
        # Load derived variables
        FUNCTION_NAME=$(jq -r '.derived.function_name' config.json)
        ROLE_NAME=$(jq -r '.derived.role_name' config.json)
        POLICY_NAME=$(jq -r '.derived.policy_name' config.json)
        REPO_NAME=$(jq -r '.derived.repo_name' config.json)
        
        # Verify required variables
        if [ -z "$AWS_ACCOUNT_ID" ] || [ "$AWS_ACCOUNT_ID" = "null" ] || \
           [ -z "$FUNCTION_NAME" ] || [ "$FUNCTION_NAME" = "null" ] || \
           [ -z "$ROLE_NAME" ] || [ "$ROLE_NAME" = "null" ] || \
           [ -z "$POLICY_NAME" ] || [ "$POLICY_NAME" = "null" ] || \
           [ -z "$REPO_NAME" ] || [ "$REPO_NAME" = "null" ]; then
            echo "❌ Error: Missing required configuration variables."
            echo "Please ensure the configuration file is complete."
            exit 1
        fi
        echo "✓ Configuration loaded successfully"
        return 0
    else
        echo "❌ Error: config.json not found. Cannot teardown without configuration."
        exit 1
    fi
}

###########################################
# Main Script
###########################################

echo "🧹 Starting resource cleanup..."
echo "------------------------------------------------------------"

# Load configuration
load_configuration

echo "Starting teardown of $APP_NAME resources..."
echo "This will remove ALL resources created by the setup scripts."
read -p "Are you sure you want to proceed? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Teardown cancelled."
    exit 1
fi

# 1. Delete Lambda function URL
echo -e "\n📋 Step 1: Deleting Lambda function URL..."
if aws lambda get-function-url-config --function-name $FUNCTION_NAME 2>/dev/null; then
    aws lambda delete-function-url-config --function-name $FUNCTION_NAME || handle_error "Lambda URL deletion" "$?"
    echo "✓ Function URL deleted"
else
    echo "→ No function URL to delete"
fi

# 2. Delete Lambda function
echo -e "\n📋 Step 2: Deleting Lambda function..."
if aws lambda get-function --function-name $FUNCTION_NAME 2>/dev/null; then
    aws lambda delete-function --function-name $FUNCTION_NAME || handle_error "Lambda function deletion" "$?"
    echo "✓ Lambda function deleted"
else
    echo "→ No Lambda function to delete"
fi

# 3. Delete IAM role policies
echo -e "\n📋 Step 3: Detaching and deleting IAM policies..."
if [ ! -z "$ROLE_NAME" ]; then
    # Detach AWS managed policy
    aws iam detach-role-policy \
        --role-name $ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole \
        || handle_error "Detaching Lambda execution policy" "$?"
    
    # Detach and delete custom Bedrock policy
    POLICY_ARN="arn:aws:iam::$AWS_ACCOUNT_ID:policy/$POLICY_NAME"
    if aws iam get-policy --policy-arn $POLICY_ARN 2>/dev/null; then
        aws iam detach-role-policy --role-name $ROLE_NAME --policy-arn $POLICY_ARN \
            || handle_error "Detaching Bedrock policy" "$?"
        
        # Delete all non-default versions of the policy
        for version in $(aws iam list-policy-versions --policy-arn $POLICY_ARN --query 'Versions[?IsDefaultVersion==`false`].VersionId' --output text); do
            aws iam delete-policy-version --policy-arn $POLICY_ARN --version-id $version \
                || handle_error "Deleting policy version $version" "$?"
        done
        
        aws iam delete-policy --policy-arn $POLICY_ARN || handle_error "Deleting Bedrock policy" "$?"
        echo "✓ Custom Bedrock policy deleted"
    else
        echo "→ No custom Bedrock policy to delete"
    fi
fi

# 4. Delete IAM role
echo -e "\n📋 Step 4: Deleting IAM role..."
if [ ! -z "$ROLE_NAME" ] && aws iam get-role --role-name $ROLE_NAME 2>/dev/null; then
    aws iam delete-role --role-name $ROLE_NAME || handle_error "IAM role deletion" "$?"
    echo "✓ IAM role deleted"
else
    echo "→ No IAM role to delete"
fi

# 5. Delete ECR repository
echo -e "\n📋 Step 5: Deleting ECR repository..."
if [ ! -z "$REPO_NAME" ] && aws ecr describe-repositories --repository-names $REPO_NAME 2>/dev/null; then
    aws ecr delete-repository --repository-name $REPO_NAME --force || handle_error "ECR repository deletion" "$?"
    echo "✓ ECR repository deleted"
else
    echo "→ No ECR repository to delete"
fi

# 6. Clean up local configuration
echo -e "\n📋 Step 6: Cleaning up local configuration..."
rm -f config.json
rm -f trust-policy.json
rm -f bedrock-policy.json
echo "✓ Local configuration files deleted"

echo -e "\n✨ Teardown complete! All $APP_NAME resources have been removed."