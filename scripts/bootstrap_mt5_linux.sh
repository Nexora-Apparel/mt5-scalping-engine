#!/usr/bin/env bash
# Experimental MT5 setup for an x86_64 Ubuntu/Debian VM.
# Uses MetaQuotes' official Linux installation script rather than the Windows web
# installer directly. It does NOT configure an account, enable order submission, or trade.
set -Eeuo pipefail

if [[ "$(uname -m)" != "x86_64" ]]; then
  echo "ERROR: This setup expects an x86_64/AMD VM. Do not use it on ARM/Ampere." >&2
  exit 2
fi
if ! command -v sudo >/dev/null 2>&1; then
  echo "ERROR: sudo is required for the official installer dependencies." >&2
  exit 2
fi

export DEBIAN_FRONTEND=noninteractive
echo "[1/5] Installing headless display and download dependencies..."
sudo apt-get update
sudo apt-get install -y xvfb xauth xdotool openbox curl ca-certificates wget

mkdir -p "$HOME/mt5-setup-logs"
# Start an isolated local-only X display and lightweight window manager for the
# official installer and any Wine Mono/Gecko prompts. No display port is exposed.
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
export DISPLAY=":${display_num}"
openbox --display "$DISPLAY" >"$HOME/mt5-setup-logs/openbox.log" 2>&1 &
openbox_pid=$!
cleanup() {
  kill "$openbox_pid" >/dev/null 2>&1 || true
  kill "$xvfb_pid" >/dev/null 2>&1 || true
}
trap cleanup EXIT
sleep 2

echo "[2/5] Downloading MetaQuotes' official Linux installer..."
installer="$HOME/mt5-setup-logs/mt5linux.sh"
curl --fail --location --retry 3 --output "$installer" \
  "https://download.terminal.free/cdn/web/metaquotes.software.corp/mt5/mt5linux.sh"
chmod 700 "$installer"

# The official script may show interactive setup dialogs. On this isolated display,
# periodically press Enter to accept the default/continue action. No broker account is
# configured, and the EA's order switch/emergency stop remain closed.
echo "[3/5] Running the official MetaTrader Linux installer..."
bash "$installer" >"$HOME/mt5-setup-logs/official-installer.log" 2>&1 &
installer_pid=$!

mt5_root="$HOME/.mt5/drive_c/Program Files/MetaTrader 5"
terminal="$mt5_root/terminal64.exe"
editor="$mt5_root/metaeditor64.exe"
for attempt in $(seq 1 120); do
  if [[ -f "$terminal" && -f "$editor" ]]; then
    break
  fi
  if (( attempt % 2 == 0 )); then
    xdotool key --clearmodifiers Return >/dev/null 2>&1 || true
  fi
  if (( attempt % 12 == 0 )); then
    echo "Still waiting for official MT5 installation (attempt $attempt/120)..."
  fi
  sleep 5
done

if [[ ! -f "$terminal" || ! -f "$editor" ]]; then
  echo "ERROR: MT5 terminal/MetaEditor did not appear within 10 minutes." >&2
  echo "Official installer log tail:" >&2
  tail -n 100 "$HOME/mt5-setup-logs/official-installer.log" >&2 || true
  echo "No account was configured and no trades were placed." >&2
  exit 4
fi

echo "[4/5] Preparing the portable Experts folder..."
export WINEPREFIX="$HOME/.mt5"
export WINEARCH=win64
mkdir -p "$mt5_root/MQL5/Experts"
source_url="https://raw.githubusercontent.com/Nexora-Apparel/mt5-scalping-engine/main/MQL5/Experts/NexoraScalper.mq5"
curl --fail --location --retry 3 --output "$mt5_root/MQL5/Experts/NexoraScalper.mq5" "$source_url"

echo "[5/5] Compiling NexoraScalper with MetaEditor..."
compile_log="$mt5_root/MQL5/Experts/NexoraScalper.log"
compiled="$mt5_root/MQL5/Experts/NexoraScalper.ex5"
rm -f "$compile_log" "$compiled"
timeout 120s wine "$editor" '/compile:C:\Program Files\MetaTrader 5\MQL5\Experts\NexoraScalper.mq5' /log \
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
timeout 30s wineserver -k >/dev/null 2>&1 || true
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
if [[ ! -f "$compiled" ]]; then
  echo "ERROR: Compiled EX5 file was not created." >&2
  exit 7
fi

kill "$installer_pid" >/dev/null 2>&1 || true
echo
echo "MT5 terminal installed and NexoraScalper compiled successfully."
echo "Safety state: no account configured; EnableDemoOrders=false; EmergencyStop=true."
echo "Do not enable trading until Strategy Tester review and a demo-only validation."
echo "Setup logs: $HOME/mt5-setup-logs/"
