#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
BIN_DIR="$HOME/.local/bin"
APP_DIR="$HOME/.local/share/applications"
LAUNCHER="$BIN_DIR/lumina-file-action"

mkdir -p "$BIN_DIR" "$APP_DIR"

cat > "$LAUNCHER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$PROJECT_DIR"
exec uv run python "$PROJECT_DIR/scripts/lumina_file_action.py" "\$@"
EOF
chmod +x "$LAUNCHER"

create_entry() {
    local name="$1"
    local filename="$2"
    local mime="$3"
    local action="$4"
    cat > "$APP_DIR/$filename" <<EOF
[Desktop Entry]
Type=Application
Name=$name
Exec=$LAUNCHER $action %F
MimeType=$mime
Terminal=true
NoDisplay=true
StartupNotify=false
EOF
}

create_entry "Lumina Translate PDF" "lumina-translate-pdf.desktop" "application/pdf;" "translate"
create_entry "Lumina Summarize PDF" "lumina-summarize-pdf.desktop" "application/pdf;" "summarize"
create_entry "Lumina Polish Text" "lumina-polish-text.desktop" "text/plain;text/markdown;" "polish"

echo "Installed desktop integrations:"
echo "  $APP_DIR/lumina-translate-pdf.desktop"
echo "  $APP_DIR/lumina-summarize-pdf.desktop"
echo "  $APP_DIR/lumina-polish-text.desktop"
echo
echo "You can now use 'Open With' / file manager actions with the Lumina entries."
