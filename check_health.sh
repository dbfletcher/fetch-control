#!/bin/bash
export LC_ALL=C.UTF-8  # <--- Add this line here
CONTAINER_IP="192.168.50.60"
PUBLIC_URL="https://fcs-fetch.com"

# ANSI Color Codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo "--- Project Fetch: Production Health Report ---"

# 1. Test Local Nginx
echo -n "Local Web Gallery:  "
curl -s --head http://$CONTAINER_IP/media/lowres/ | head -n 1 | grep "200" > /dev/null \
    && echo -e "${GREEN}ONLINE${NC}" || echo -e "${RED}OFFLINE${NC}"

# 2. Test MariaDB
echo -n "MariaDB Database:   "
ssh root@$CONTAINER_IP "mariadb-admin ping" > /dev/null 2>&1 \
    && echo -e "${GREEN}ONLINE${NC}" || echo -e "${RED}OFFLINE${NC}"

# 3. Test Systemd Timer (Worker)
echo -n "Image Worker Timer: "
ssh root@$CONTAINER_IP "systemctl is-active fetch-image-worker.timer" > /dev/null 2>&1 \
    && echo -e "${GREEN}ACTIVE${NC}" || echo -e "${RED}INACTIVE${NC}"

# 4. Test Cloudflare Service (Connector)
echo -n "Cloudflare Tunnel:  "
ssh root@$CONTAINER_IP "systemctl is-active cloudflared" > /dev/null 2>&1 \
    && echo -e "${GREEN}HEALTHY${NC}" || echo -e "${RED}DISCONNECTED${NC}"

# 5. Test Public HTTPS Endpoint
echo -n "Public URL (HTTPS): "
curl -s --head $PUBLIC_URL | head -n 1 | grep "200" > /dev/null \
    && echo -e "${GREEN}REACHABLE${NC}" || echo -e "${RED}UNREACHABLE${NC}"

# 6. Check Disk Usage
echo -n "Disk Usage (20GB):  "
ssh root@$CONTAINER_IP "df -h / | awk 'NR==2 {print \$5}'"
