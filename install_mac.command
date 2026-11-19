#!/bin/bash
# Double-click once (or run in Terminal). Makes the calendar start automatically at login.
DIR="$(cd "$(dirname "$0")" && pwd)"
PY="$(command -v python3)"
PLIST="$HOME/Library/LaunchAgents/com.desktopcalendar.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>Label</key><string>com.desktopcalendar</string>
<key>ProgramArguments</key><array><string>$PY</string><string>$DIR/calendar_desktop.pyw</string></array>
<key>RunAtLoad</key><true/>
</dict></plist>
EOF
launchctl unload "$PLIST" 2>/dev/null
launchctl load "$PLIST"
echo "Done. Calendar will start at every login. Keep this folder where it is."
