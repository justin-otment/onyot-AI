#!/bin/bash
set -e

# Find a random .ovpn config from the mounted folder
CONFIG=$(find /vpn/externals/VPNs -type f -name "*.tcp" | shuf -n 1)

if [[ -z "$CONFIG" ]]; then
  echo "❌ No VPN config file found. Exiting..."
  exit 1
fi

echo "🔁 Selected VPN config: $CONFIG"

# Start OpenVPN in background
openvpn --config "$CONFIG" --auth-user-pass /vpn/externals/VPNs/auth.txt &
VPN_PID=$!

# Wait a bit for VPN to establish
sleep 10

# Now run your script
echo "🚀 Starting scraper script..."
exec xvfb-run -a python /app/Skip\ Tracing/truppl_parser.py
