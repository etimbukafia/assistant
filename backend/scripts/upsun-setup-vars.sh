#!/bin/bash
# =============================================================================
# Upsun Variable Setup Script
#
# Reads from your .env file and uploads to Upsun.
#
# Usage:
#   ./scripts/upsun-setup-vars.sh [--staging|--production]
#
# Prerequisites:
#   - Upsun CLI installed and authenticated
#   - .env file exists with your values
#
# Docs: https://docs.upsun.com/development/variables/set-variables.html
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/../.env"

# Check if .env exists
if [ ! -f "$ENV_FILE" ]; then
    echo "Error: .env file not found at $ENV_FILE"
    echo "Copy .env.example to .env and fill in your values first."
    exit 1
fi

# Load .env file
set -a
source "$ENV_FILE"
set +a

echo "=== Upsun Variable Setup ==="
echo "Reading from: $ENV_FILE"
echo ""

# Environment argument
ENV_TYPE="${1:-staging}"
case "$ENV_TYPE" in
    --staging)
        BRANCH="staging"
        ;;
    --production)
        BRANCH="main"
        ;;
    *)
        BRANCH="staging"
        ;;
esac

echo "Target environment: $BRANCH"
echo ""

# =============================================================================
# Helper function
# =============================================================================
create_var() {
    local level="$1"
    local name="$2"
    local value="$3"
    local sensitive="${4:-false}"
    local visible_build="${5:-true}"
    local visible_runtime="${6:-true}"
    local branch="$7"

    if [ -z "$value" ]; then
        echo "  SKIP: $name (empty value)"
        return
    fi

    local cmd="upsun variable:create --level $level --prefix env --name $name --value '$value' --sensitive $sensitive --visible-build $visible_build --visible-runtime $visible_runtime --no-interaction"

    if [ "$level" = "environment" ] && [ -n "$branch" ]; then
        cmd="$cmd -e $branch --inheritable false"
    fi

    if eval "$cmd" 2>/dev/null; then
        echo "  OK: $name"
    else
        echo "  EXISTS: $name (updating...)"
        upsun variable:update "env:$name" --value "$value" --no-interaction 2>/dev/null || true
    fi
}

# =============================================================================
# PROJECT-LEVEL VARIABLES (shared across all environments)
# =============================================================================

echo "Creating project-level variables..."

# Google / Gemini (sensitive)
create_var "project" "GOOGLE_API_KEY" "$GOOGLE_API_KEY" "true" "true" "true"

# Gmail OAuth credentials (sensitive)
create_var "project" "GOOGLE_CLIENT_ID" "$GOOGLE_CLIENT_ID" "true" "true" "true"
create_var "project" "GOOGLE_CLIENT_SECRET" "$GOOGLE_CLIENT_SECRET" "true" "false" "true"

# LLM Configuration
create_var "project" "LLM_PROVIDER" "$LLM_PROVIDER" "false" "true" "true"
create_var "project" "LLM_EMAIL_PROVIDER" "$LLM_EMAIL_PROVIDER" "false" "true" "true"
create_var "project" "LLM_EMAIL_MODEL" "$LLM_EMAIL_MODEL" "false" "true" "true"
create_var "project" "LLM_CHAT_PROVIDER" "$LLM_CHAT_PROVIDER" "false" "true" "true"
create_var "project" "LLM_CHAT_MODEL" "$LLM_CHAT_MODEL" "false" "true" "true"

# Database (sensitive)
create_var "project" "DATABASE_URL" "$DATABASE_URL" "true" "false" "true"

# Supabase
create_var "project" "SUPABASE_URL" "$SUPABASE_URL" "false" "true" "true"
create_var "project" "SUPABASE_ANON_KEY" "$SUPABASE_ANON_KEY" "true" "true" "true"
create_var "project" "SUPABASE_JWT_SECRET" "$SUPABASE_JWT_SECRET" "true" "false" "true"

# Security (sensitive)
create_var "project" "ENCRYPTION_KEY" "$ENCRYPTION_KEY" "true" "false" "true"

# Polar Payment (sensitive)
create_var "project" "POLAR_API_KEY" "$POLAR_API_KEY" "true" "false" "true"
create_var "project" "POLAR_WEBHOOK_SECRET" "$POLAR_WEBHOOK_SECRET" "true" "false" "true"
create_var "project" "POLAR_ORGANIZATION_ID" "$POLAR_ORGANIZATION_ID" "false" "true" "true"
create_var "project" "POLAR_PRO_PRODUCT_ID" "$POLAR_PRO_PRODUCT_ID" "false" "true" "true"

# Google Cloud Pub/Sub
create_var "project" "GOOGLE_CLOUD_PROJECT_ID" "$GOOGLE_CLOUD_PROJECT_ID" "false" "true" "true"
create_var "project" "GMAIL_PUBSUB_TOPIC" "$GMAIL_PUBSUB_TOPIC" "false" "true" "true"

echo ""

# =============================================================================
# ENVIRONMENT-SPECIFIC VARIABLES
# =============================================================================

echo "Creating $BRANCH environment variables..."

# These need to be set per-environment
create_var "environment" "ENV" "$ENV" "false" "true" "true" "$BRANCH"
create_var "environment" "FRONTEND_URL" "$FRONTEND_URL" "false" "true" "true" "$BRANCH"
create_var "environment" "GMAIL_OAUTH_REDIRECT_URI" "$GMAIL_OAUTH_REDIRECT_URI" "false" "true" "true" "$BRANCH"
create_var "environment" "CORS_ORIGINS" "$CORS_ORIGINS" "false" "true" "true" "$BRANCH"

# Cloudflare (staging only, sensitive)
if [ "$BRANCH" = "staging" ]; then
    create_var "environment" "CF_ACCESS_CLIENT_ID" "$CF_ACCESS_CLIENT_ID" "true" "false" "true" "$BRANCH"
    create_var "environment" "CF_ACCESS_CLIENT_SECRET" "$CF_ACCESS_CLIENT_SECRET" "true" "false" "true" "$BRANCH"
fi

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Redeploy: upsun environment:redeploy -e $BRANCH"
echo "2. Verify: upsun var -e $BRANCH"
