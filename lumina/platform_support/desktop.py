"""
lumina/platform_support/desktop.py — 跨平台桌面能力入口。

业务代码只依赖这里暴露的方法，不直接调用 pbcopy/osascript/open 等平台命令。
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass

from .runtime import IS_LINUX, IS_MACOS, IS_WINDOWS

logger = logging.getLogger("lumina")


def _which(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=False, capture_output=True, text=True, **kwargs)


@dataclass
class DesktopServices:
    enable_notifications: bool = True

    def clipboard_get(self) -> str:
        if IS_MACOS:
            return subprocess.check_output(["pbpaste"], timeout=3, text=True)
        if IS_WINDOWS:
            result = _run(["powershell", "-Command", "Get-Clipboard"], timeout=5)
            return result.stdout.strip()
        if IS_LINUX:
            wl_paste = _which("wl-paste")
            if wl_paste:
                return subprocess.check_output([wl_paste, "--no-newline"], timeout=3, text=True)
            xclip = _which("xclip")
            if xclip:
                return subprocess.check_output([xclip, "-selection", "clipboard", "-o"], timeout=3, text=True)
            xsel = _which("xsel")
            if xsel:
                return subprocess.check_output([xsel, "--clipboard", "--output"], timeout=3, text=True)
        return ""

    def clipboard_set(self, text: str) -> None:
        if IS_MACOS:
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return
        if IS_WINDOWS:
            ps_script = f"Set-Clipboard -Value @\"\n{text}\n\"@"
            subprocess.run(["powershell", "-Command", ps_script], check=True, timeout=5)
            return
        if IS_LINUX:
            wl_copy = _which("wl-copy")
            if wl_copy:
                subprocess.run([wl_copy], input=text.encode(), check=True, timeout=5)
                return
            xclip = _which("xclip")
            if xclip:
                subprocess.run([xclip, "-selection", "clipboard"], input=text.encode(), check=True, timeout=5)
                return
            xsel = _which("xsel")
            if xsel:
                subprocess.run([xsel, "--clipboard", "--input"], input=text.encode(), check=True, timeout=5)
                return

    def paste_to_foreground(self) -> None:
        if IS_MACOS:
            script = 'tell application "System Events" to keystroke "v" using command down'
            subprocess.run(["osascript", "-e", script], check=False)
            return
        if IS_WINDOWS:
            subprocess.run(
                [
                    "powershell", "-Command",
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "[System.Windows.Forms.SendKeys]::SendWait('^v')",
                ],
                check=False,
                timeout=5,
            )
            return
        if IS_LINUX:
            xdotool = _which("xdotool")
            if xdotool:
                subprocess.run([xdotool, "key", "--clearmodifiers", "ctrl+v"], check=False, timeout=5)
                return
            ydotool = _which("ydotool")
            if ydotool:
                subprocess.run([ydotool, "key", "29:1", "47:1", "47:0", "29:0"], check=False, timeout=5)

    def notify(self, title: str, message: str) -> None:
        if not self.enable_notifications:
            return
        try:
            if IS_MACOS:
                script = (
                    f'display notification "{message}" '
                    f'with title "{title}" '
                    f'sound name "default"'
                )
                subprocess.Popen(
                    ["osascript", "-e", script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            if IS_WINDOWS:
                ps_script = (
                    "Add-Type -AssemblyName System.Windows.Forms; "
                    "Add-Type -AssemblyName System.Drawing; "
                    "$n = New-Object System.Windows.Forms.NotifyIcon; "
                    "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                    "$n.BalloonTipTitle = @'\n" + title + "\n'@; "
                    "$n.BalloonTipText = @'\n" + message + "\n'@; "
                    "$n.Visible = $true; "
                    "$n.ShowBalloonTip(5000); "
                    "Start-Sleep -Milliseconds 5500; "
                    "$n.Dispose();"
                )
                subprocess.Popen(
                    ["powershell", "-Command", ps_script],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                return
            if IS_LINUX:
                notify_send = _which("notify-send")
                if notify_send:
                    subprocess.Popen(
                        [notify_send, title, message],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
        except Exception as exc:
            logger.debug("Notification failed: %s", exc)

    def open_url(self, url: str) -> bool:
        try:
            return bool(webbrowser.open(url))
        except Exception as exc:
            logger.debug("Open URL failed: %s", exc)
            return False


def get_desktop_services(*, enable_notifications: bool = True) -> DesktopServices:
    return DesktopServices(enable_notifications=enable_notifications)
