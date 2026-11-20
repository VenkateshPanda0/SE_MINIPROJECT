import sys
import shutil
# Only fixed executable/argument lists are used, never a shell.
import subprocess  # nosec B404
from typing import Callable

from src.common import MediaController

# Virtual Key Codes for Windows Multimedia Keys
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
APPCOMMAND_MEDIA_PLAY = 46
APPCOMMAND_MEDIA_PAUSE = 47


def _default_windows_key_sender(key_code: int) -> None:
    """Simulate a multimedia key press and release on Windows."""
    import ctypes

    # key down followed by key up (KEYEVENTF_KEYUP = 2)
    ctypes.windll.user32.keybd_event(key_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(key_code, 0, 2, 0)


def _default_windows_app_sender(command: int) -> None:
    """Send an explicit play/pause request to the foreground application."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.GetForegroundWindow.restype = wintypes.HWND
    send = user32.SendMessageTimeoutW
    send.argtypes = [
        wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
        wintypes.UINT, wintypes.UINT, ctypes.POINTER(ctypes.c_size_t),
    ]
    send.restype = wintypes.LPARAM
    window = user32.GetForegroundWindow()
    if not window:
        raise RuntimeError("Focus a supported media player before issuing playback commands")
    result = ctypes.c_size_t()
    if not send(window, 0x0319, window, command << 16, 0x0002, 1000,
                ctypes.byref(result)):
        raise RuntimeError("The media player did not respond to the playback request")
    if not result.value:
        raise RuntimeError("The foreground application does not support this playback command")


class OSMediaController(MediaController):
    """Platform media adapter implementing MediaController via OS key events."""

    def __init__(
        self,
        key_sender: Callable[[int], None] | None = None,
        app_command_sender: Callable[[int], None] | None = None,
    ) -> None:
        self._playerctl = None
        if key_sender is not None or app_command_sender is not None or sys.platform == "win32":
            self._send_key = key_sender or _default_windows_key_sender
            self._send_app_command = app_command_sender or _default_windows_app_sender
        elif sys.platform.startswith("linux"):
            self._playerctl = shutil.which("playerctl")
            if self._playerctl is None:
                raise RuntimeError("Linux requires playerctl and an MPRIS-compatible media player")
        else:
            raise RuntimeError(f"Unsupported media-control platform: {sys.platform}")

    def _linux_action(self, *arguments: str) -> None:
        try:
            # Executable resolved from PATH; arguments are internal constants, never speech.
            subprocess.run(  # nosec B603
                [self._playerctl, *arguments], check=True, capture_output=True,
                text=True, timeout=3,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(
                "Media request failed; check the player and desktop session"
            ) from exc

    def volume_up(self) -> None:
        if self._playerctl:
            self._linux_action("volume", "0.05+")
        else:
            self._send_key(VK_VOLUME_UP)

    def volume_down(self) -> None:
        if self._playerctl:
            self._linux_action("volume", "0.05-")
        else:
            self._send_key(VK_VOLUME_DOWN)

    def play(self) -> None:
        if self._playerctl:
            self._linux_action("play")
        else:
            self._send_app_command(APPCOMMAND_MEDIA_PLAY)

    def pause(self) -> None:
        if self._playerctl:
            self._linux_action("pause")
        else:
            self._send_app_command(APPCOMMAND_MEDIA_PAUSE)

    def resume(self) -> None:
        self.play()

    def next_track(self) -> None:
        if self._playerctl:
            self._linux_action("next")
        else:
            self._send_key(VK_MEDIA_NEXT_TRACK)

    def previous_track(self) -> None:
        if self._playerctl:
            self._linux_action("previous")
        else:
            self._send_key(VK_MEDIA_PREV_TRACK)
