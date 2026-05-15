#!/usr/bin/env bash
# Idempotent provision + venv + systemd for RoboWheels on Pi Zero 2 W.
# Run on the Pi after rsync (e.g. bash ~/robowheels/deploy/bootstrap-remote.sh).
set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"
INSTALL_DIR="${INSTALL_DIR:-$HOME/robowheels}"
REBOOT_IF_BOOT_CHANGED="${REBOOT_IF_BOOT_CHANGED:-false}"
BOOT_CHANGED=0

log() { echo "[robowheels-bootstrap] $*"; }
warn() { echo "[robowheels-bootstrap] WARNING: $*" >&2; }

if [[ ! -d "$INSTALL_DIR" ]]; then
  echo "INSTALL_DIR does not exist: $INSTALL_DIR" >&2
  exit 1
fi

if [[ ! -f "$INSTALL_DIR/drive.py" ]]; then
  echo "drive.py not found under $INSTALL_DIR (rsync may have failed)" >&2
  exit 1
fi

# --- APT ---
log "Installing system packages..."
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq
sudo apt-get install -y -qq \
  python3 \
  python3-venv \
  python3-pip \
  python3-dev \
  raspi-config \
  i2c-tools \
  libgpiod2 \
  python3-libgpiod \
  rsync \
  || true

# python3-libgpiod may be named differently on older images
if ! dpkg -s python3-libgpiod &>/dev/null 2>&1; then
  sudo apt-get install -y -qq python3-libgpiod2 2>/dev/null || true
fi

# --- raspi-config (noninteractive) ---
if command -v raspi-config &>/dev/null; then
  log "Enabling I2C and serial via raspi-config..."
  sudo raspi-config nonint do_i2c 0 || warn "do_i2c failed"
  sudo raspi-config nonint do_serial 0 || warn "do_serial failed"
  # Disable serial login console so CRSF can use UART (when supported)
  if raspi-config nonint 2>&1 | grep -q do_serial_cons; then
    sudo raspi-config nonint do_serial_cons 1 || warn "do_serial_cons failed"
  fi
else
  warn "raspi-config not found; enable I2C/UART manually"
fi

# --- Groups ---
for grp in gpio i2c dialout; do
  if getent group "$grp" &>/dev/null; then
    sudo usermod -aG "$grp" "$DEPLOY_USER" || true
  fi
done

# --- USB gadget boot config ---
ensure_boot_line() {
  local file="$1"
  local needle="$2"
  if [[ ! -f "$file" ]]; then
    return 0
  fi
  if grep -qF "$needle" "$file" 2>/dev/null; then
    return 0
  fi
  log "Adding '$needle' to $file"
  echo "$needle" | sudo tee -a "$file" >/dev/null
  BOOT_CHANGED=1
}

for cfg in /boot/firmware/config.txt /boot/config.txt; do
  ensure_boot_line "$cfg" "dtoverlay=dwc2"
done

for cmdline in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
  if [[ -f "$cmdline" ]] && ! grep -q "modules-load=dwc2,g_serial" "$cmdline" 2>/dev/null; then
    if grep -q "modules-load=" "$cmdline" 2>/dev/null; then
      sudo sed -i 's/modules-load=\([^ ]*\)/modules-load=\1,dwc2,g_serial/' "$cmdline" || true
    else
      sudo sed -i 's/^/modules-load=dwc2,g_serial /' "$cmdline" || true
    fi
    BOOT_CHANGED=1
    log "Updated modules-load in $cmdline"
  fi
done

if [[ "$BOOT_CHANGED" -eq 1 ]]; then
  warn "Boot config changed; reboot the Pi before USB gadget serial is available."
  if [[ "$REBOOT_IF_BOOT_CHANGED" == "true" ]]; then
    log "Rebooting (REBOOT_IF_BOOT_CHANGED=true)..."
    sudo reboot
    exit 0
  fi
fi

# --- Python venv ---
log "Creating/updating venv in $INSTALL_DIR/.venv"
cd "$INSTALL_DIR"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -U pip wheel
.venv/bin/pip install -r requirements.txt

# --- systemd ---
SERVICE_SRC="$INSTALL_DIR/deploy/robowheels-drive.service"
if [[ ! -f "$SERVICE_SRC" ]]; then
  echo "Missing $SERVICE_SRC" >&2
  exit 1
fi

log "Installing systemd unit robowheels-drive.service"
sed -e "s|@DEPLOY_USER@|${DEPLOY_USER}|g" \
    -e "s|@INSTALL_DIR@|${INSTALL_DIR}|g" \
    "$SERVICE_SRC" | sudo tee /etc/systemd/system/robowheels-drive.service >/dev/null

sudo systemctl daemon-reload
sudo systemctl enable robowheels-drive.service

log "Restarting robowheels-drive.service"
if ! sudo systemctl restart robowheels-drive.service; then
  warn "Service failed to start; recent logs:"
  sudo journalctl -u robowheels-drive.service -n 50 --no-pager || true
  exit 1
fi

sleep 2
if ! sudo systemctl is-active --quiet robowheels-drive.service; then
  warn "Service is not active after restart; recent logs:"
  sudo journalctl -u robowheels-drive.service -n 50 --no-pager || true
  exit 1
fi

log "Done. Status:"
sudo systemctl status robowheels-drive.service --no-pager -l || true
