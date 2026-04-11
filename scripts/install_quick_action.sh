#!/usr/bin/env bash
# 安装 Lumina Finder Quick Action（右键菜单）
#   - 用 Lumina 翻译 PDF
#   - 用 Lumina 总结 PDF
# 安装后在 Finder 中选中 PDF 文件 → 右键 → 快速操作
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICES_DIR="$HOME/Library/Services"
LUMINA_BIN="$HOME/.lumina/lumina"

# ── 查找 lumina 可执行文件 ──────────────────────────────────────────────────
# 优先级：~/.lumina/lumina → PATH → App bundle 内置 → 开发模式 uv run
_APP_BUNDLE_BIN="/Applications/Lumina.app/Contents/MacOS/lumina"
# 脚本也可能从 bundle 内部调用（Contents/Resources/scripts/），此时 PROJECT_DIR 是 Contents/Resources
_BUNDLE_BIN_RELATIVE="$(dirname "$PROJECT_DIR")/MacOS/lumina"

if [[ -x "$LUMINA_BIN" ]]; then
    LUMINA_CMD="$LUMINA_BIN"
elif [[ -f "$PROJECT_DIR/pyproject.toml" ]] && command -v uv &>/dev/null; then
    # 开发模式：生成 uv run 包装脚本，优先于 App bundle
    # 写死 uv 完整路径，避免 Automator 的 shell 环境 PATH 里找不到 uv
    UV_BIN="$(command -v uv)"
    WRAPPER="$HOME/.lumina/lumina-dev"
    mkdir -p "$HOME/.lumina"
    printf '#!/usr/bin/env bash\ncd "%s"\nexec "%s" run lumina "$@"\n' "$PROJECT_DIR" "$UV_BIN" > "$WRAPPER"
    chmod +x "$WRAPPER"
    LUMINA_CMD="$WRAPPER"
    echo "注意：使用开发模式（uv run），包装脚本已写入 $WRAPPER"
elif command -v lumina &>/dev/null; then
    LUMINA_CMD="$(command -v lumina)"
elif [[ -x "$_APP_BUNDLE_BIN" ]]; then
    LUMINA_CMD="$_APP_BUNDLE_BIN"
elif [[ -x "$_BUNDLE_BIN_RELATIVE" ]]; then
    LUMINA_CMD="$_BUNDLE_BIN_RELATIVE"
else
    echo "错误：未找到 lumina 可执行文件。"
    echo "请先运行 bash scripts/install_full.sh 或 bash scripts/install_lite.sh"
    exit 1
fi

mkdir -p "$SERVICES_DIR"

# ── 安装单个 Quick Action（文件输入，Finder 专用）──────────────────────────
# install_workflow <名称> <shell脚本内容> [文件类型UTI，默认 com.adobe.pdf]
install_workflow() {
    local name="$1"
    local shell_script="$2"
    local file_type="${3:-com.adobe.pdf}"
    local workflow_path="$SERVICES_DIR/${name}.workflow"

    rm -rf "$workflow_path"
    mkdir -p "$workflow_path/Contents"

    # 生成 NSSendFileTypes 段
    if [[ "$file_type" == "none" ]]; then
        local filetypes_xml=""
    else
        local filetypes_xml="            <key>NSSendFileTypes</key>
            <array>
                <string>${file_type}</string>
            </array>"
    fi

    # Info.plist
    cat > "$workflow_path/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>${name}</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSRequiredContext</key>
            <dict>
                <key>NSApplicationIdentifier</key>
                <string>com.apple.finder</string>
            </dict>
${filetypes_xml}
        </dict>
    </array>
</dict>
</plist>
PLIST

    # 临时写入 shell 脚本
    local tmp_sh="$workflow_path/Contents/_action.sh"
    printf '%s' "$shell_script" > "$tmp_sh"

    # 用 Python 生成 document.wflow（用 plistlib 保证格式正确，UUID 随机生成）
    python3 - "$tmp_sh" "$workflow_path/Contents/document.wflow" <<'PYEOF'
import sys, uuid, plistlib

shell_script_path = sys.argv[1]
output_path = sys.argv[2]

with open(shell_script_path) as f:
    shell_content = f.read()

# 输入类型：文件系统对象（Finder 选中文件传入）
input_type_id  = "com.apple.Automator.fileSystemObject"
output_type_id = "com.apple.Automator.nothing"

action_uuid     = str(uuid.uuid4()).upper()
input_uuid      = str(uuid.uuid4()).upper()
output_uuid     = str(uuid.uuid4()).upper()

d = {
    "AMApplicationBuild":   "521",
    "AMApplicationVersion": "2.10",
    "AMDocumentVersion":    "2",
    "actions": [
        {
            "action": {
                "AMAccepts": {
                    "Container": "List",
                    "Optional": True,
                    "Types": ["com.apple.cocoa.string"],
                },
                "AMActionVersion": "2.0.3",
                "AMApplication": ["自动操作"],
                "AMParameterProperties": {
                    "COMMAND_STRING": {},
                    "CheckedForUserDefaultShell": {},
                    "inputMethod": {},
                    "shell": {},
                    "source": {},
                },
                "AMProvides": {
                    "Container": "List",
                    "Types": ["com.apple.cocoa.string"],
                },
                "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                "ActionName": "运行Shell脚本",
                "ActionParameters": {
                    "COMMAND_STRING": shell_content,
                    "CheckedForUserDefaultShell": True,
                    "inputMethod": 1,
                    "shell": "/bin/bash",
                    "source": "",
                },
                "BundleIdentifier": "com.apple.RunShellScript",
                "CFBundleVersion": "2.0.3",
                "CanShowSelectedItemsWhenRun": False,
                "CanShowWhenRun": True,
                "Category": ["AMCategoryUtilities"],
                "Class Name": "RunShellScriptAction",
                "InputUUID":  input_uuid,
                "OutputUUID": output_uuid,
                "UUID":       action_uuid,
                "Keywords": ["Shell", "脚本", "命令", "运行", "Unix"],
                "UnlocalizedApplications": ["Automator"],
                "UnlockTimeout": 0,
                "arguments": {
                    "0": {"default value": 0,     "name": "inputMethod",              "required": "0", "type": "0", "uuid": "0"},
                    "1": {"default value": False,  "name": "CheckedForUserDefaultShell","required": "0", "type": "0", "uuid": "1"},
                    "2": {"default value": "",     "name": "source",                   "required": "0", "type": "0", "uuid": "2"},
                    "3": {"default value": "",     "name": "COMMAND_STRING",            "required": "0", "type": "0", "uuid": "3"},
                    "4": {"default value": "/bin/sh", "name": "shell",                 "required": "0", "type": "0", "uuid": "4"},
                },
                "isViewVisible": 1,
                "location": "309.000000:305.000000",
                "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib",
            },
            "isViewVisible": 1,
        }
    ],
    "connectors": {},
    "workflowMetaData": {
        "applicationBundleID": "com.apple.finder",
        "applicationBundleIDsByPath": {"/System/Library/CoreServices/Finder.app": "com.apple.finder"},
        "applicationPath": "/System/Library/CoreServices/Finder.app",
        "applicationPaths": ["/System/Library/CoreServices/Finder.app"],
        "inputTypeIdentifier":          input_type_id,
        "outputTypeIdentifier":         output_type_id,
        "presentationMode":             15,
        "processesInput":               False,
        "serviceApplicationBundleID":   "com.apple.finder",
        "serviceApplicationPath":       "/System/Library/CoreServices/Finder.app",
        "serviceInputTypeIdentifier":   input_type_id,
        "serviceOutputTypeIdentifier":  output_type_id,
        "serviceProcessesInput":        False,
        "systemImageName":              "NSTouchBarSend",
        "useAutomaticInputType":        False,
        "workflowTypeIdentifier":       "com.apple.Automator.servicesMenu",
    },
}

with open(output_path, "wb") as f:
    plistlib.dump(d, f, fmt=plistlib.FMT_XML)
PYEOF

    rm -f "$tmp_sh"
    echo "✓ 已安装：${workflow_path}"
}

# ── 安装单个文本选区 Service（任意应用选中文字触发）────────────────────────
# install_text_workflow <名称> <shell脚本内容>
install_text_workflow() {
    local name="$1"
    local shell_script="$2"
    local workflow_path="$SERVICES_DIR/${name}.workflow"

    rm -rf "$workflow_path"
    mkdir -p "$workflow_path/Contents"

    # Info.plist：NSSendTypes=NSStringPboardType，不限 App
    cat > "$workflow_path/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
    "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>NSServices</key>
    <array>
        <dict>
            <key>NSMenuItem</key>
            <dict>
                <key>default</key>
                <string>${name}</string>
            </dict>
            <key>NSMessage</key>
            <string>runWorkflowAsService</string>
            <key>NSSendTypes</key>
            <array>
                <string>NSStringPboardType</string>
            </array>
        </dict>
    </array>
</dict>
</plist>
PLIST

    local tmp_sh="$workflow_path/Contents/_action.sh"
    printf '%s' "$shell_script" > "$tmp_sh"

    # 用 Python 生成 document.wflow，inputMethod=0（stdin 接收选中文字）
    python3 - "$tmp_sh" "$workflow_path/Contents/document.wflow" <<'PYEOF'
import sys, uuid, plistlib

shell_script_path = sys.argv[1]
output_path = sys.argv[2]

with open(shell_script_path) as f:
    shell_content = f.read()

# 文本输入 workflow 类型
input_type_id  = "com.apple.Automator.text"
output_type_id = "com.apple.Automator.nothing"

action_uuid = str(uuid.uuid4()).upper()
input_uuid  = str(uuid.uuid4()).upper()
output_uuid = str(uuid.uuid4()).upper()

d = {
    "AMApplicationBuild":   "521",
    "AMApplicationVersion": "2.10",
    "AMDocumentVersion":    "2",
    "actions": [
        {
            "action": {
                "AMAccepts": {
                    "Container": "List",
                    "Optional": True,
                    "Types": ["com.apple.cocoa.string"],
                },
                "AMActionVersion": "2.0.3",
                "AMApplication": ["自动操作"],
                "AMParameterProperties": {
                    "COMMAND_STRING": {},
                    "CheckedForUserDefaultShell": {},
                    "inputMethod": {},
                    "shell": {},
                    "source": {},
                },
                "AMProvides": {
                    "Container": "List",
                    "Types": ["com.apple.cocoa.string"],
                },
                "ActionBundlePath": "/System/Library/Automator/Run Shell Script.action",
                "ActionName": "运行Shell脚本",
                "ActionParameters": {
                    "COMMAND_STRING": shell_content,
                    "CheckedForUserDefaultShell": True,
                    "inputMethod": 0,
                    "shell": "/bin/bash",
                    "source": "",
                },
                "BundleIdentifier": "com.apple.RunShellScript",
                "CFBundleVersion": "2.0.3",
                "CanShowSelectedItemsWhenRun": False,
                "CanShowWhenRun": True,
                "Category": ["AMCategoryUtilities"],
                "Class Name": "RunShellScriptAction",
                "InputUUID":  input_uuid,
                "OutputUUID": output_uuid,
                "UUID":       action_uuid,
                "Keywords": ["Shell", "脚本", "命令", "运行", "Unix"],
                "UnlocalizedApplications": ["Automator"],
                "UnlockTimeout": 0,
                "arguments": {
                    "0": {"default value": 0,     "name": "inputMethod",               "required": "0", "type": "0", "uuid": "0"},
                    "1": {"default value": False,  "name": "CheckedForUserDefaultShell","required": "0", "type": "0", "uuid": "1"},
                    "2": {"default value": "",     "name": "source",                    "required": "0", "type": "0", "uuid": "2"},
                    "3": {"default value": "",     "name": "COMMAND_STRING",             "required": "0", "type": "0", "uuid": "3"},
                    "4": {"default value": "/bin/sh", "name": "shell",                  "required": "0", "type": "0", "uuid": "4"},
                },
                "isViewVisible": 1,
                "location": "309.000000:305.000000",
                "nibPath": "/System/Library/Automator/Run Shell Script.action/Contents/Resources/Base.lproj/main.nib",
            },
            "isViewVisible": 1,
        }
    ],
    "connectors": {},
    "workflowMetaData": {
        "inputTypeIdentifier":         input_type_id,
        "outputTypeIdentifier":        output_type_id,
        "presentationMode":            15,
        "processesInput":              False,
        "serviceInputTypeIdentifier":  input_type_id,
        "serviceOutputTypeIdentifier": output_type_id,
        "serviceProcessesInput":       False,
        "systemImageName":             "NSTouchBarSend",
        "useAutomaticInputType":       False,
        "workflowTypeIdentifier":      "com.apple.Automator.servicesMenu",
    },
}

with open(output_path, "wb") as f:
    plistlib.dump(d, f, fmt=plistlib.FMT_XML)
PYEOF

    rm -f "$tmp_sh"
    echo "✓ 已安装：${workflow_path}"
}

# ── Quick Action 1：翻译 PDF ───────────────────────────────────────────────
TRANSLATE_SCRIPT='#!/usr/bin/env bash
exec 2>>"$HOME/.lumina/qa.log"
echo "=== translate triggered $(date) args=$# ===" >&2
echo "files: $@" >&2
if ! curl -s --noproxy '"'"'*'"'"' --max-time 2 http://127.0.0.1:31821/health >>$HOME/.lumina/qa.log 2>&1; then
    osascript -e '"'"'display notification "请先启动 lumina server" with title "Lumina" subtitle "服务未运行"'"'"'
    echo "health check FAILED" >&2
    exit 1
fi
echo "health check OK" >&2
for f in "$@"; do
    name="$(basename "$f")"
    ext="${name##*.}"
    lower_ext="$(echo "$ext" | tr '"'"'[:upper:]'"'"' '"'"'[:lower:]'"'"')"
    if [[ "$lower_ext" != "pdf" ]]; then continue; fi
    dir="$(dirname "$f")"
    base="$(basename "$f" .pdf)"
    osascript -e "display notification \"正在翻译：${base}.pdf\" with title \"Lumina\""
    LUMINA_LOG_LEVEL=WARNING LUMINA_CMD pdf "$f" -o "$dir" 2>>"$HOME/.lumina/qa.log"
    if [[ $? -eq 0 ]]; then
        osascript -e "display notification \"翻译完成：${base}-mono.pdf\" with title \"Lumina\" subtitle \"双语版：${base}-dual.pdf\""
        open -R "$dir/${base}-mono.pdf" 2>/dev/null || open "$dir"
    else
        osascript -e "display notification \"翻译失败，详情见 $HOME/.lumina/qa.log\" with title \"Lumina\""
    fi
done'
TRANSLATE_SCRIPT="${TRANSLATE_SCRIPT//LUMINA_CMD/$LUMINA_CMD}"
install_workflow "用 Lumina 翻译 PDF" "$TRANSLATE_SCRIPT"

# ── Quick Action 2：总结 PDF ───────────────────────────────────────────────
SUMMARIZE_SCRIPT='#!/usr/bin/env bash
exec 2>>"$HOME/.lumina/qa.log"
echo "=== summarize triggered $(date) args=$# ===" >&2
echo "files: $@" >&2
if ! curl -s --noproxy '"'"'*'"'"' --max-time 2 http://127.0.0.1:31821/health >>$HOME/.lumina/qa.log 2>&1; then
    osascript -e '"'"'display notification "请先启动 lumina server" with title "Lumina" subtitle "服务未运行"'"'"'
    echo "health check FAILED" >&2
    exit 1
fi
echo "health check OK" >&2
for f in "$@"; do
    name="$(basename "$f")"
    ext="${name##*.}"
    lower_ext="$(echo "$ext" | tr '"'"'[:upper:]'"'"' '"'"'[:lower:]'"'"')"
    if [[ "$lower_ext" != "pdf" ]]; then continue; fi
    dir="$(dirname "$f")"
    base="$(basename "$f" .pdf)"
    out_file="$dir/${base}-summary.txt"
    osascript -e "display notification \"正在生成摘要：${base}.pdf\" with title \"Lumina\""
    LUMINA_LOG_LEVEL=WARNING LUMINA_CMD summarize "$f" 2>>"$HOME/.lumina/qa.log"
    if [[ $? -eq 0 ]]; then
        osascript -e "display notification \"摘要已保存：${base}-summary.txt\" with title \"Lumina\""
        open -R "$out_file" 2>/dev/null || open "$dir"
    else
        osascript -e "display notification \"生成摘要失败，详情见 $HOME/.lumina/qa.log\" with title \"Lumina\""
    fi
done'
SUMMARIZE_SCRIPT="${SUMMARIZE_SCRIPT//LUMINA_CMD/$LUMINA_CMD}"
install_workflow "用 Lumina 总结 PDF" "$SUMMARIZE_SCRIPT"

# ── Quick Action 3：润色文本（处理 TXT / MD 文件）────────────────────────────
POLISH_SCRIPT='#!/usr/bin/env bash
exec 2>>"$HOME/.lumina/qa.log"
echo "=== polish triggered $(date) args=$# ===" >&2
echo "files: $@" >&2
if ! curl -s --noproxy '"'"'*'"'"' --max-time 2 http://127.0.0.1:31821/health >>$HOME/.lumina/qa.log 2>&1; then
    osascript -e '"'"'display notification "请先启动 lumina server" with title "Lumina" subtitle "服务未运行"'"'"'
    echo "health check FAILED" >&2
    exit 1
fi
for f in "$@"; do
    ext="$(echo "${f##*.}" | tr '"'"'[:upper:]'"'"' '"'"'[:lower:]'"'"')"
    if [[ "$ext" != "txt" && "$ext" != "md" ]]; then continue; fi
    dir="$(dirname "$f")"
    base="$(basename "$f" ".$ext")"
    out_file="$dir/${base}-polished.$ext"

    # 语言检测：README 或含 -en 的文件名用英文，否则中文
    fname_lower="$(echo "$base" | tr '"'"'[:upper:]'"'"' '"'"'[:lower:]'"'"')"
    if [[ "$fname_lower" == *readme* || "$fname_lower" == *-en* ]]; then
        LANG_ARG="en"
    else
        LANG_ARG="zh"
    fi

    osascript -e "display notification \"正在润色：$(basename "$f")\" with title \"Lumina\""
    LUMINA_LOG_LEVEL=WARNING LUMINA_CMD polish "$f" --lang "$LANG_ARG" 2>>"$HOME/.lumina/qa.log"
    if [[ $? -eq 0 ]]; then
        osascript -e "display notification \"润色完成：${base}-polished.$ext\" with title \"Lumina\""
        open -R "$out_file" 2>/dev/null || open "$dir"
    else
        osascript -e "display notification \"润色失败，详情见 $HOME/.lumina/qa.log\" with title \"Lumina\""
    fi
done'
POLISH_SCRIPT="${POLISH_SCRIPT//LUMINA_CMD/$LUMINA_CMD}"
install_workflow "用 Lumina 润色文本" "$POLISH_SCRIPT" "public.plain-text"

# ── Service 4：润色选中文字（任意应用，右键菜单）──────────────────────────
# 把选中文字写入临时文件再传给 lumina popup，避免 shell 参数处理多行文本的转义问题。
# lumina popup 会阻塞直到用户关闭弹窗，不需要 &。
POLISH_SELECTION_SCRIPT='#!/usr/bin/env bash
exec 2>>"$HOME/.lumina/qa.log"
echo "=== polish-selection triggered $(date) ===" >&2

tmpfile="$(mktemp /tmp/lumina_popup.XXXXXX)"
cat > "$tmpfile"

if [[ ! -s "$tmpfile" ]]; then
    rm -f "$tmpfile"
    osascript -e '"'"'display notification "请先选中文字" with title "Lumina"'"'"'
    exit 0
fi

if ! curl -s --noproxy '"'"'*'"'"' --max-time 2 http://127.0.0.1:31821/health >>$HOME/.lumina/qa.log 2>&1; then
    rm -f "$tmpfile"
    osascript -e '"'"'display notification "请先启动 lumina server" with title "Lumina" subtitle "服务未运行"'"'"'
    exit 1
fi

LUMINA_CMD popup --action polish --file "$tmpfile" 2>>"$HOME/.lumina/qa.log"
rm -f "$tmpfile"'
POLISH_SELECTION_SCRIPT="${POLISH_SELECTION_SCRIPT//LUMINA_CMD/$LUMINA_CMD}"
install_text_workflow "用 Lumina 润色选中文字" "$POLISH_SELECTION_SCRIPT"

# ── Service 5：翻译选中文字（任意应用，右键菜单）──────────────────────────
TRANSLATE_SELECTION_SCRIPT='#!/usr/bin/env bash
exec 2>>"$HOME/.lumina/qa.log"
echo "=== translate-selection triggered $(date) ===" >&2

tmpfile="$(mktemp /tmp/lumina_popup.XXXXXX)"
cat > "$tmpfile"

if [[ ! -s "$tmpfile" ]]; then
    rm -f "$tmpfile"
    osascript -e '"'"'display notification "请先选中文字" with title "Lumina"'"'"'
    exit 0
fi

if ! curl -s --noproxy '"'"'*'"'"' --max-time 2 http://127.0.0.1:31821/health >>$HOME/.lumina/qa.log 2>&1; then
    rm -f "$tmpfile"
    osascript -e '"'"'display notification "请先启动 lumina server" with title "Lumina" subtitle "服务未运行"'"'"'
    exit 1
fi

LUMINA_CMD popup --action translate --file "$tmpfile" 2>>"$HOME/.lumina/qa.log"
rm -f "$tmpfile"'
TRANSLATE_SELECTION_SCRIPT="${TRANSLATE_SELECTION_SCRIPT//LUMINA_CMD/$LUMINA_CMD}"
install_text_workflow "用 Lumina 翻译选中文字" "$TRANSLATE_SELECTION_SCRIPT"

# 刷新 macOS Services 缓存
/System/Library/CoreServices/pbs -flush 2>/dev/null || true

echo ""
echo "使用方法："
echo "  PDF 文件 → 右键 → 快速操作："
echo "     「用 Lumina 翻译 PDF」  输出 *-mono.pdf 和 *-dual.pdf"
echo "     「用 Lumina 总结 PDF」  输出 *-summary.txt"
echo "  TXT/MD 文件 → 右键 → 快速操作："
echo "     「用 Lumina 润色文本」  输出 *-polished.txt / *-polished.md"
echo "  任意应用选中文字 → 右键 → 服务："
echo "     「用 Lumina 润色选中文字」  弹窗显示润色结果，可一键复制"
echo "     「用 Lumina 翻译选中文字」  弹窗显示翻译结果，可一键复制"
echo ""
echo "前提：lumina server 需已在运行。"
echo "  启动：$LUMINA_CMD server"
echo "  开机自启：launchctl load ~/Library/LaunchAgents/com.lumina.server.plist"
