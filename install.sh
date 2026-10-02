#!/usr/bin/env bash
# Install the widget for the current user (no root needed except for the optional pacman dependency).
#   ./install.sh              install + launcher + app-menu entry
#   ./install.sh --autostart  ...and start it at login
#   ./install.sh --uninstall
set -euo pipefail

SRC="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
DEST="$SHARE/cachy-widget"
BIN="$HOME/.local/bin"
APPS="$SHARE/applications"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"

if [[ "${1:-}" == "--uninstall" ]]; then
  rm -rf "$DEST" "$BIN/cachy-widget" "$APPS/cachy-widget.desktop" "$AUTOSTART/cachy-widget.desktop"
  echo "Removed. (Settings in ~/.config/cachy-widget were left alone.)"
  exit 0
fi

if ! python3 -c 'import PyQt6.QtWidgets' 2>/dev/null; then
  echo "PyQt6 is missing. Installing it with pacman (needs sudo)…"
  sudo pacman -S --needed --noconfirm python-pyqt6
fi

mkdir -p "$DEST" "$BIN" "$APPS"
rm -rf "$DEST/cachy_widget"
cp -r "$SRC/cachy_widget" "$DEST/"
find "$DEST" -name __pycache__ -prune -exec rm -rf {} +

cat > "$BIN/cachy-widget" <<WRAP
#!/usr/bin/env bash
export PYTHONPATH="$DEST\${PYTHONPATH:+:\$PYTHONPATH}"
exec python3 -m cachy_widget "\$@"
WRAP
chmod +x "$BIN/cachy-widget"
install -m 644 "$SRC/packaging/cachy-widget.desktop" "$APPS/cachy-widget.desktop"

if [[ "${1:-}" == "--autostart" ]]; then
  mkdir -p "$AUTOSTART"
  install -m 644 "$SRC/packaging/cachy-widget.desktop" "$AUTOSTART/cachy-widget.desktop"
  echo "Autostart enabled."
fi

case ":$PATH:" in *":$BIN:"*) ;; *) echo "Note: add $BIN to your PATH to run 'cachy-widget' from a terminal." ;; esac
echo "Installed. Launch 'CachyOS Weather' from your app menu, or run: cachy-widget"
echo "KDE Plasma users: run scripts/kde-desktop-rule.sh once so it sits on the desktop on Wayland."
