#!/usr/bin/env bash
# Experimental MT5 setup for an x86_64 Ubuntu/Debian VM.
# Installs the desktop terminal under Wine and compiles NexoraScalper.
# It does NOT configure an account, enable order submission, or start trading.
set -Eeuo pipefail

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: This setup expects an x86_64/AMD VM. Do not use it on ARM/Ampere." >&2
  exit 2
fi
if ! command -v sudo >/dev/null 2>&1; then
  echo "ERROR: sudo is required to install system packages." >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
echo "[1/5] Installing Wine and Xvfb dependencies..."
sudo apt-get update
sudo apt-get install -y wine wine64 winbind xvfb xauth curl ca-certificates fonts-wine

# Add a modest swap file on tiny Always Free VMs if the machine has less than 2 GiB RAM
# and no active swap. This uses local disk space; it does not buy cloud resources.
mem_kib="$(awk '/MemTotal:/ {print $2}' /proc/meminfo)"
swap_total_kib="$(awk '/SwapTotal:/ {print $2}' /proc/meminfo)"
if [[ "$mem_kib" -lt 2097152 && "$swap_total_kib" -lt 1048576 && ! -e /swapfile ]]; then
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

export WINEPREFIX="$HOME/.nexora-mt5"
export WINEARCH=win64
mkdir -p "$WINEPREFIX" "$HOME/mt5-setup-logs"

# Start a private virtual display because the installer/editor are Windows GUI programs.
display_num=99
while [[ -S "/tmp/.X11-unix/X${display_num}" ]]; do
  display_num=$((display_num + 1))
  if [[ "$display_num" -gt 120 ]]; then
    echo "ERROR: No free X display number found." >&2
    exit 2
  fi
done
Xvfb ":${display_num}" -screen 0 1280x800x24 -nolisten tcp -ac >"$HOME/mt5-setup-logs/xvfb.log" 2>&1 &
xvfb_pid=$!
cleanup() {
  kill "$xvfb_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT
export DISPLAY=":${display_num}"

echo "[2/5] Initializing isolated Wine prefix..."
timeout 60s wineboot --init || true
sleep 3

echo "[3/5] Downloading official MetaTrader installer..."
installer="$HOME/mt5-setup-logs/mt5setup.exe"
curl --fail --location --retry 3 --output "$installer" \
  "https://download.mql5.com/cdn/web/metaquotes.software.corp/mt5/mt5setup.exe"
if [[ "$(stat -c '%s' "$installer")" -lt 1000000 ]]; then
  echo "ERROR: MT5 installer download is unexpectedly small." >&2
  exit 3
fi

# MetaQuotes' web installer may return before its spawned installation process finishes.
# Keep the display alive and poll common install paths rather than trusting the setup exit code.
echo "[4/5] Installing MT5; waiting for terminal64.exe and MetaEditor..."
wine "$installer" /auto '/path:C:\MT5' >"$HOME/mt5-setup-logs/installer.log" 2>&1 &
installer_pid=$!

mt5_root=""
install_roots=(
  "$WINEPREFIX/drive_c/MT5"
  "$WINEPREFIX/drive_c/Program Files/MetaTrader 5"
  "$WINEPREFIX/drive_c/Program Files (x86)/MetaTrader 5"
)
terminal=""
editor=""
for attempt in $(seq 1 120); do
  for candidate_root in "${install_roots[@]}"; do
    if [[ -f "$candidate_root/terminal64.exe" && -f "$candidate_root/metaeditor64.exe" ]]; then
      mt5_root="$candidate_root"
      terminal="$mt5_root/terminal64.exe"
      editor="$mt5_root/metaeditor64.exe"
      break 2
    fi
  done
  if (( attempt % 12 == 0 )); then
    echo "Still waiting for the MT5 terminal installation (attempt $attempt/120)..."
  fi
  sleep 5
done

if [[ ! -f "$terminal" || ! -f "$editor" ]]; then
  echo "ERROR: MT5 desktop terminal did not finish installing within 10 minutes." >&2
  echo "Installer log tail:" >&2
  tail -n 80 "$HOME/mt5-setup-logs/installer.log" >&2 || true
  echo "No account was configured and no trades were placed." >&2
  exit 4
fi

# Initialize portable data folders without logging into an account.
wine "$terminal" /portable >"$HOME/mt5-setup-logs/terminal-init.log" 2>&1 &
terminal_init_pid=$!
sleep 15
kill "$terminal_init_pid" >/dev/null 2>&1 || true
# The Wine wrapper may leave the Windows terminal child running; reset Wine cleanly
# before compiling so the headless terminal does not hold the display open.
wineserver -k >/dev/null 2>&1 || true
sleep 2
wineboot --init || true
mkdir -p "$mt5_root/MQL5/Experts"

source_url="https://raw.githubusercontent.com/Nexora-Apparel/mt5-scalping-engine/main/MQL5/Experts/NexoraScalper.mq5"
curl --fail --location --retry 3 --output "$mt5_root/MQL5/Experts/NexoraScalper.mq5" "$source_url"

rel_root="${mt5_root#"$WINEPREFIX/drive_c/"}"
win_root="C:\\${rel_root//\//\\}"
source_win="${win_root}\\MQL5\\Experts\\NexoraScalper.mq5"
echo "[5/5] Compiling NexoraScalper with MetaEditor..."
compile_log="$mt5_root/MQL5/Experts/NexoraScalper.log"
compiled="$mt5_root/MQL5/Experts/NexoraScalper.ex5"
rm -f "$compile_log" "$compiled"
timeout 120s wine "$editor" "/compile:$source_win" /log \
  >"$HOME/mt5-setup-logs/compile-launch.log" 2>&1 &
compile_pid=$!
for attempt in $(seq 1 60); do
  if [[ -f "$compile_log" && -f "$compiled" ]] && grep -Eiq '0 errors' "$compile_log"; then
    break
  fi
  sleep 2
done
kill "$compile_pid" >/dev/null 2>&1 || true
wait "$compile_pid" >/dev/null 2>&1 || true
wineserver -k >/dev/null 2>&1 || true
sleep 2
if [[ ! -f "$compile_log" ]]; then
  echo "ERROR: MetaEditor did not create a compile log. See $HOME/mt5-setup-logs/." >&2
  exit 5
fi
cat "$compile_log"
if ! grep -Eiq '0 errors' "$compile_log"; then
  echo "ERROR: Compile log did not confirm zero errors." >&2
  exit 6
fi
if [[ ! -f "$mt5_root/MQL5/Experts/NexoraScalper.ex5" ]]; then
  echo "ERROR: Compiled EX5 file was not created." >&2
  exit 7
fi

# Stop only the setup process if it is still running. The installed terminal remains
# unconfigured and the EA keeps EnableDemoOrders=false / EmergencyStop=true by default.
kill "$installer_pid" >/dev/null 2>&1 || true
echo
echo "MT5 terminal installed and NexoraScalper compiled successfully."
echo "Safety state: no account configured; EnableDemoOrders=false; EmergencyStop=true."
echo "Do not enable trading until Strategy Tester review and a demo-only validation."
echo "Setup logs: $HOME/mt5-setup-logs/"
