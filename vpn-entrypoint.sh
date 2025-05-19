#!/bin/bash
set -e

echo "📁 Listing available VPN files..."
find /vpn/externals/VPNs -type f

CONFIG=$(find /vpn/externals/VPNs -type f -name "*.tcp" | shuf -n 1)

if [[ -z "$CONFIG" ]]; then
  echo "❌ No VPN config file found. Exiting..."
  exit 1
fi

echo "🔁 Selected VPN config: $CONFIG"

openvpn --config "$CONFIG" --auth-user-pass /vpn/externals/VPNs/auth.txt &
VPN_PID=$!

sleep 10

echo "🚀 Starting scraper script..."
exec xvfb-run -a python /app/Skip\ Tracing/truppl_parser.py
