#!/usr/bin/env bash
set -e

# Support curl ... | bash interactive execution by attaching tty
if [ ! -t 0 ] && [ -e /dev/tty ]; then
  exec < /dev/tty
fi

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

echo -e "${CYAN}${BOLD}"
echo "=========================================================="
echo "          Frigate AI Proxy - Automated Installer          "
echo "=========================================================="
echo -e "${NC}"

# Check Docker prerequisite
if ! command -v docker >/dev/null 2>&1; then
  echo -e "${RED}[ERROR] Docker is not installed or not in PATH.${NC}"
  echo "Please install Docker before continuing: https://docs.docker.com/get-docker/"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo -e "${RED}[ERROR] Docker daemon is not running.${NC}"
  echo "Please start Docker and re-run this script."
  exit 1
fi

# 3-Second Countdown
echo -e "${YELLOW}Default setup: Glimpse (Elorian) + JEV (TypeSafe)${NC}"
echo -e "Press ${BOLD}ANY KEY within 3 seconds${NC} to configure custom OpenAI-compatible endpoints."
echo -e "Otherwise, continuing with Glimpse + JEV defaults in..."

CHOSEN_MODE="default"
for i in 3 2 1; do
  printf "  %s%d...%s " "${CYAN}" "$i" "${NC}"
  if read -t 1 -n 1 -s _key 2>/dev/null; then
    CHOSEN_MODE="custom"
    printf "\n"
    break
  fi
done
printf "\n\n"

if [ "$CHOSEN_MODE" = "custom" ]; then
  echo -e "${BLUE}${BOLD}--- Custom OpenAI-Compatible Configuration ---${NC}"
  read -r -p "Enter Vision Model Base URL [https://api.openai.com/v1]: " CUSTOM_URL
  VLM_BASE_URL="${CUSTOM_URL:-https://api.openai.com/v1}"

  read -r -p "Enter Vision Model Name [gpt-4o-mini]: " CUSTOM_MODEL
  VLM_MODEL="${CUSTOM_MODEL:-gpt-4o-mini}"

  read -r -sp "Enter Vision Model API Key: " VLM_API_KEY
  echo ""

  read -r -p "Enable TypeSafe JEV threat scoring? (y/N): " ENABLE_JEV
  case "$ENABLE_JEV" in
    [yY][eE][sS]|[yY])
      ENABLE_THREAT_SCORING="true"
      THREAT_BASE_URL="https://api.typesafe.ai/v1"
      THREAT_MODEL="jev-latest"
      echo -e "\n${CYAN}Get your JEV key: Sign in at https://console.typesafe.ai/keys -> Create API Key${NC}"
      read -r -sp "Enter JEV API Key: " THREAT_API_KEY
      echo ""
      ;;
    *)
      ENABLE_THREAT_SCORING="false"
      THREAT_BASE_URL="https://api.typesafe.ai/v1"
      THREAT_MODEL="jev-latest"
      THREAT_API_KEY=""
      ;;
  esac

else
  echo -e "${GREEN}${BOLD}[✓] Proceeding with Glimpse (Elorian) + JEV (TypeSafe) defaults.${NC}\n"
  VLM_BASE_URL="https://api.elorian.ai/v1"
  VLM_MODEL="glimpse"
  ENABLE_THREAT_SCORING="true"
  THREAT_BASE_URL="https://api.typesafe.ai/v1"
  THREAT_MODEL="jev-latest"

  # Elorian API Key
  echo -e "${BOLD}1. Elorian API Key (Vision Model: Glimpse)${NC}"
  echo -e "   ${CYAN}How to get: Sign in at https://platform.elorian.ai -> API Keys -> Create Key${NC}"
  while [ -z "$VLM_API_KEY" ]; do
    read -r -sp "   Enter your Elorian API Key: " VLM_API_KEY
    echo ""
    if [ -z "$VLM_API_KEY" ]; then
      echo -e "   ${RED}API key cannot be empty. Please enter your Elorian key.${NC}"
    fi
  done

  # TypeSafe JEV API Key
  echo ""
  echo -e "${BOLD}2. JEV API Key (TypeSafe System One Threat Scoring)${NC}"
  echo -e "   ${CYAN}How to get: Sign in at https://console.typesafe.ai/keys -> Create API Key${NC}"
  while [ -z "$THREAT_API_KEY" ]; do
    read -r -sp "   Enter your TypeSafe JEV API Key: " THREAT_API_KEY
    echo ""
    if [ -z "$THREAT_API_KEY" ]; then
      echo -e "   ${RED}API key cannot be empty. Please enter your JEV key.${NC}"
    fi
  done
fi

echo ""
echo -e "${BLUE}${BOLD}--- Deploying Docker Container ---${NC}"

CONTAINER_NAME="frigate-ai-proxy"
IMAGE_NAME="ghcr.io/israelsaba/frigate-ai-proxy:latest"

if docker ps -a --format '{{.Names}}' | grep -Eq "^${CONTAINER_NAME}\$"; then
  echo -e "${YELLOW}Stopping and removing existing ${CONTAINER_NAME} container...${NC}"
  docker rm -f "$CONTAINER_NAME" >/dev/null 2>&1
fi

echo -e "Starting ${CONTAINER_NAME} on port 8000..."
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  -p 8000:8000 \
  -e FRIGATE_PROXY_LOG_LEVEL=INFO \
  -e FRIGATE_PROXY_MAX_OUTPUT_TOKENS=600 \
  -e FRIGATE_PROXY_MAX_SAMPLED_IMAGES=20 \
  -e FRIGATE_PROXY_VLM_BASE_URL="$VLM_BASE_URL" \
  -e FRIGATE_PROXY_VLM_MODEL="$VLM_MODEL" \
  -e FRIGATE_PROXY_VLM_API_KEY="$VLM_API_KEY" \
  -e FRIGATE_PROXY_ENABLE_THREAT_SCORING="$ENABLE_THREAT_SCORING" \
  -e FRIGATE_PROXY_THREAT_SCORING_BASE_URL="$THREAT_BASE_URL" \
  -e FRIGATE_PROXY_THREAT_SCORING_MODEL="$THREAT_MODEL" \
  -e FRIGATE_PROXY_THREAT_SCORING_API_KEY="$THREAT_API_KEY" \
  "$IMAGE_NAME" >/dev/null

echo -e "${GREEN}[✓] Container started successfully.${NC}"

# Verification
echo -e "Verifying service health..."
HEALTHY=false
for _ in $(seq 1 10); do
  if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
    HEALTHY=true
    break
  fi
  sleep 1
done

if [ "$HEALTHY" = true ]; then
  echo -e "${GREEN}${BOLD}[✓] Frigate AI Proxy is online and healthy at http://localhost:8000${NC}"
else
  echo -e "${YELLOW}[!] Container is running, but health check is still initializing. Check logs with: docker logs ${CONTAINER_NAME}${NC}"
fi

echo ""
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo -e "${GREEN}${BOLD}             Installation Complete!                       ${NC}"
echo -e "${GREEN}${BOLD}==========================================================${NC}"
echo -e "Add this to your Frigate ${BOLD}config.yml${NC}:"
echo ""
echo -e "${CYAN}genai:"
echo "  ai_proxy:"
echo "    provider: openai"
echo "    base_url: http://frigate-ai-proxy:8000/v1"
echo "    api_key: unused"
if [ "$ENABLE_THREAT_SCORING" = "true" ]; then
  echo "    model: ${VLM_MODEL}-threat"
else
  echo "    model: ${VLM_MODEL}"
fi
echo "    roles:"
echo "      - descriptions${NC}"
echo ""
