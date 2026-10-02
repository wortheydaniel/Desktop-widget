#!/usr/bin/env bash
# KDE Plasma (Wayland or X11): add a KWin window rule that keeps the widget below other windows,
# off the taskbar/pager/Alt-Tab, and (optionally) pins it to a screen position.
#   scripts/kde-desktop-rule.sh            # rule without a fixed position (drag it where you like)
#   scripts/kde-desktop-rule.sh 1500 80    # also pin to x=1500, y=80
#   scripts/kde-desktop-rule.sh --remove
set -euo pipefail
RC="$HOME/.config/kwinrulesrc"
UUID="c4c4e0a1-5a11-4c3e-9d57-8a2f6b1d0c01"
kw()  { kwriteconfig6 --file kwinrulesrc "$@"; }
kr()  { kreadconfig6 --file kwinrulesrc "$@"; }
reload() { (qdbus6 org.kde.KWin /KWin reconfigure || qdbus org.kde.KWin /KWin reconfigure) >/dev/null 2>&1 || true; }

rules="$(kr --group General --key rules || true)"
without="$(tr ',' '\n' <<<"$rules" | grep -vx "$UUID" | grep -v '^$' | paste -sd, - || true)"

if [[ "${1:-}" == "--remove" ]]; then
  kw --group General --key rules "$without"
  kw --group General --key count "$(tr ',' '\n' <<<"$without" | grep -c . || true)"
  kw --group "$UUID" --delete-group 2>/dev/null || sed -i "/^\[$UUID\]/,/^$/d" "$RC"
  reload; echo "Rule removed."; exit 0
fi

new="${without:+$without,}$UUID"
kw --group General --key rules "$new"
kw --group General --key count "$(tr ',' '\n' <<<"$new" | grep -c .)"
g() { kw --group "$UUID" "$@"; }
g --key Description "CachyOS Weather widget"
g --key wmclass "cachy-widget"
g --key wmclasscomplete false
g --key wmclassmatch 1
for k in below skiptaskbar skippager skipswitcher; do
  g --key "$k" true
  g --key "${k}rule" 2   # 2 = force
done
if [[ $# -ge 2 ]]; then
  g --key position "$1,$2"
  g --key positionrule 3   # 3 = apply initially, so you can still drag it afterwards
fi
reload
echo "Rule installed. Restart the widget for it to apply."
