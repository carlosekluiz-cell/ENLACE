#!/bin/bash
# Pulso Agent Installer
# https://enlace.network
#
# Usage: curl -sL https://enlace.network/install.sh | bash
#
# This script:
# 1. Downloads the Pulso Agent binary for your architecture
# 2. Installs it to /usr/local/bin/
# 3. Creates a dedicated non-root service user (pulso-agent)
# 4. Writes a default config to /etc/pulso-agent/agent.toml (mode 0640)
# 5. Installs the hardened systemd unit (Type=notify + watchdog)
#
# It will NOT enable or start the service while the config still contains
# placeholder credentials — edit the config first.

set -e

AGENT_VERSION="0.1.0"
BASE_URL="https://releases.enlace.network/agent"
CONFIG_DIR="/etc/pulso-agent"
CONFIG_FILE="${CONFIG_DIR}/agent.toml"
DATA_DIR="/var/lib/pulso-agent"
SERVICE_USER="pulso-agent"
UNIT_FILE="/etc/systemd/system/pulso-agent.service"

echo "╔══════════════════════════════════════════╗"
echo "║     Pulso Agent Installer v${AGENT_VERSION}         ║"
echo "║     enlace.network                       ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Detect architecture
ARCH=$(uname -m)
case "$ARCH" in
    x86_64)  BINARY="pulso-agent-linux-x86_64" ;;
    aarch64) BINARY="pulso-agent-linux-arm64" ;;
    armv7l)  BINARY="pulso-agent-linux-armv7" ;;
    *)       echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

echo "Detected: $ARCH"
echo "Downloading Pulso Agent..."

# Download binary
curl -fSL "${BASE_URL}/${AGENT_VERSION}/${BINARY}" -o /tmp/pulso-agent
chmod +x /tmp/pulso-agent

# Install
sudo mv /tmp/pulso-agent /usr/local/bin/pulso-agent
echo "✓ Installed to /usr/local/bin/pulso-agent"

# Create dedicated non-root service user
if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
    sudo useradd --system --no-create-home --home-dir "$DATA_DIR" \
        --shell /usr/sbin/nologin "$SERVICE_USER"
    echo "✓ Created service user ${SERVICE_USER}"
fi

# Create config and data directories
sudo mkdir -p "$CONFIG_DIR" "$DATA_DIR"
sudo chown "${SERVICE_USER}:${SERVICE_USER}" "$DATA_DIR"
sudo chmod 750 "$DATA_DIR"

# Write default config if absent (root-owned, group-readable by the service
# user only — it holds SNMP communities and device passwords)
if [ ! -f "$CONFIG_FILE" ]; then
    AGENT_ID=$(cat /proc/sys/kernel/random/uuid)
    sudo tee "$CONFIG_FILE" > /dev/null << EOF
# Pulso Agent configuration — https://enlace.network/docs/agent
# Credentials in this file stay on this machine and are NEVER sent to the
# cloud. Keep it non-world-readable (chmod 640).

agent_id = "${AGENT_ID}"
data_dir = "${DATA_DIR}"

# Polling interval in seconds (minimum 10).
poll_interval_secs = 60

# How many OLTs to poll concurrently per cycle.
poll_concurrency = 4

# Operator UTC offset in hours (0 = UK winter, 1 = BST, -3 = Brazil).
utc_offset_hours = 0

[cloud]
endpoint = "https://api.enlace.network/v1/telemetry"
api_key = "YOUR_API_KEY"
send_interval_secs = 300
verify_tls = true

# Self-observability: /healthz and /metrics on loopback.
[metrics]
enabled = true
bind = "127.0.0.1:9464"

[[olts]]
name = "OLT-Principal"
ip = "10.0.0.1"
vendor = "auto"
model = ""

[olts.snmp]
version = "v2c"
community = "public"
port = 161
timeout_ms = 5000
max_repetitions = 50

[[mikrotiks]]
name = "MK-Core"
ip = "10.0.0.254"
port = 8728
username = "pulso"
password = "CHANGE_ME"
EOF
    sudo chown "root:${SERVICE_USER}" "$CONFIG_FILE"
    sudo chmod 0640 "$CONFIG_FILE"
    echo "✓ Default config written to ${CONFIG_FILE} (mode 0640)"
else
    echo "✓ Existing config kept at ${CONFIG_FILE}"
    # Tighten permissions on pre-existing configs too — it holds credentials
    sudo chown "root:${SERVICE_USER}" "$CONFIG_FILE"
    sudo chmod 0640 "$CONFIG_FILE"
fi

# Install the hardened systemd unit. Prefer the unit shipped alongside this
# script (repo checkout / release tarball); otherwise write an identical copy.
SCRIPT_DIR=$(cd "$(dirname "$0")" 2>/dev/null && pwd || echo "")
if [ -n "$SCRIPT_DIR" ] && [ -f "${SCRIPT_DIR}/pulso-agent.service" ]; then
    sudo install -m 0644 "${SCRIPT_DIR}/pulso-agent.service" "$UNIT_FILE"
    echo "✓ Installed hardened unit from ${SCRIPT_DIR}/pulso-agent.service"
else
    sudo tee "$UNIT_FILE" > /dev/null << 'EOF'
[Unit]
Description=Pulso Agent — ISP Network Intelligence Collector
Documentation=https://enlace.network/docs/agent
After=network-online.target
Wants=network-online.target

[Service]
# Type=notify: the agent sends READY=1 after startup and WATCHDOG=1 pings
# at half the WatchdogSec interval (sd_notify implemented in src/systemd.rs)
Type=notify
ExecStart=/usr/local/bin/pulso-agent -v --config /etc/pulso-agent/agent.toml
Restart=on-failure
RestartSec=10
WatchdogSec=300

# Non-root service user (created by install.sh)
User=pulso-agent
Group=pulso-agent

# Security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/pulso-agent
PrivateTmp=true

# Resource limits
LimitNOFILE=4096
MemoryMax=256M

# Logging (tracing writes to stderr; stdout is reserved for data output)
StandardOutput=journal
StandardError=journal
SyslogIdentifier=pulso-agent

[Install]
WantedBy=multi-user.target
EOF
    echo "✓ Installed hardened unit (embedded copy)"
fi

sudo systemctl daemon-reload
echo "✓ Systemd service created"

# Never enable+start with placeholder credentials: a crash/warn loop on
# first boot is exactly what this installer used to cause.
if sudo grep -qE 'YOUR_API_KEY|CHANGE_ME' "$CONFIG_FILE"; then
    echo ""
    echo "═══════════════════════════════════════════"
    echo "  ⚠ Config still contains placeholder credentials —"
    echo "    the service was NOT enabled or started."
    echo ""
    echo "  Next steps:"
    echo ""
    echo "  1. Edit config:   sudo nano ${CONFIG_FILE}"
    echo "     - Set your API key (from enlace.network)"
    echo "     - Add your OLT IP and SNMP community"
    echo "     - Add your MikroTik IP and credentials"
    echo ""
    echo "  2. Test:           sudo -u ${SERVICE_USER} pulso-agent -vv --once --dry-run --config ${CONFIG_FILE}"
    echo ""
    echo "  3. Start service:  sudo systemctl enable --now pulso-agent"
    echo ""
    echo "  Docs: https://enlace.network/docs/agent"
    echo "═══════════════════════════════════════════"
else
    sudo systemctl enable --now pulso-agent
    echo ""
    echo "═══════════════════════════════════════════"
    echo "  ✓ Service enabled and started."
    echo ""
    echo "  Status:   systemctl status pulso-agent"
    echo "  Logs:     journalctl -u pulso-agent -f"
    echo "  Health:   curl -s http://127.0.0.1:9464/healthz"
    echo "  Metrics:  curl -s http://127.0.0.1:9464/metrics"
    echo ""
    echo "  Docs: https://enlace.network/docs/agent"
    echo "═══════════════════════════════════════════"
fi
