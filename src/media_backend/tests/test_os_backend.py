from unittest.mock import MagicMock
import subprocess
import ctypes
from types import SimpleNamespace

import pytest

from src.common import MediaController
from src.media_backend import OSMediaController
from src.media_backend.os_backend import (
    VK_MEDIA_NEXT_TRACK,
    APPCOMMAND_MEDIA_PLAY,
    APPCOMMAND_MEDIA_PAUSE,
    VK_MEDIA_PREV_TRACK,
    VK_VOLUME_DOWN,
    VK_VOLUME_UP,
)


def test_implements_media_controller_interface():
    backend = OSMediaController(key_sender=lambda _: None)
    assert isinstance(backend, MediaController)


def test_volume_up_sends_correct_key():
    mock_sender = MagicMock()
    backend = OSMediaController(key_sender=mock_sender)

    backend.volume_up()
    mock_sender.assert_called_once_with(VK_VOLUME_UP)


def test_volume_down_sends_correct_key():
    mock_sender = MagicMock()
    backend = OSMediaController(key_sender=mock_sender)

    backend.volume_down()
    mock_sender.assert_called_once_with(VK_VOLUME_DOWN)


def test_play_pause_resume_send_distinct_explicit_commands():
    mock_sender = MagicMock()
    backend = OSMediaController(app_command_sender=mock_sender)

    backend.play()
    backend.pause()
    backend.resume()

    assert [call.args[0] for call in mock_sender.call_args_list] == [
        APPCOMMAND_MEDIA_PLAY, APPCOMMAND_MEDIA_PAUSE, APPCOMMAND_MEDIA_PLAY,
    ]


def test_next_track_sends_correct_key():
    mock_sender = MagicMock()
    backend = OSMediaController(key_sender=mock_sender)

    backend.next_track()
    mock_sender.assert_called_once_with(VK_MEDIA_NEXT_TRACK)


def test_previous_track_sends_correct_key():
    mock_sender = MagicMock()
    backend = OSMediaController(key_sender=mock_sender)

    backend.previous_track()
    mock_sender.assert_called_once_with(VK_MEDIA_PREV_TRACK)


def test_default_windows_initializer(monkeypatch):
    monkeypatch.setattr("src.media_backend.os_backend.sys.platform", "win32")
    backend = OSMediaController()
    assert isinstance(backend, MediaController)


@pytest.mark.parametrize("platform", ["linux", "darwin"])
def test_unavailable_platform_fails_instead_of_silent_success(monkeypatch, platform):
    monkeypatch.setattr("src.media_backend.os_backend.sys.platform", platform)
    monkeypatch.setattr("src.media_backend.os_backend.shutil.which", lambda _: None)
    with pytest.raises(RuntimeError):
        OSMediaController()


@pytest.mark.parametrize("method, arguments", [
    ("play", ["play"]), ("pause", ["pause"]), ("resume", ["play"]),
    ("next_track", ["next"]), ("previous_track", ["previous"]),
    ("volume_up", ["volume", "0.05+"]), ("volume_down", ["volume", "0.05-"]),
])
def test_linux_uses_explicit_actions_without_a_shell(monkeypatch, method, arguments):
    monkeypatch.setattr("src.media_backend.os_backend.sys.platform", "linux")
    monkeypatch.setattr("src.media_backend.os_backend.shutil.which", lambda _: "/usr/bin/playerctl")
    runner = MagicMock()
    monkeypatch.setattr("src.media_backend.os_backend.subprocess.run", runner)
    getattr(OSMediaController(), method)()
    runner.assert_called_once_with(
        ["/usr/bin/playerctl", *arguments], check=True, capture_output=True, text=True, timeout=3,
    )


@pytest.mark.parametrize("failure", [
    OSError("missing"), subprocess.CalledProcessError(1, "playerctl"),
    subprocess.TimeoutExpired("playerctl", 3),
])
def test_linux_backend_failures_are_not_reported_as_success(monkeypatch, failure):
    monkeypatch.setattr("src.media_backend.os_backend.sys.platform", "linux")
    monkeypatch.setattr("src.media_backend.os_backend.shutil.which", lambda _: "/usr/bin/playerctl")
    monkeypatch.setattr(
        "src.media_backend.os_backend.subprocess.run", MagicMock(side_effect=failure),
    )
    with pytest.raises(RuntimeError, match="Media request failed"):
        OSMediaController().play()


@pytest.mark.parametrize("failure, expected_detail", [
    (
        subprocess.CalledProcessError(1, "playerctl", stderr="No players found\n"),
        "No players found",
    ),
    (subprocess.CalledProcessError(1, "playerctl", stderr=""), "exited with status 1"),
    (subprocess.CalledProcessError(2, "playerctl", stderr=None), "exited with status 2"),
    (subprocess.TimeoutExpired("playerctl", 3), "playerctl timed out"),
    (OSError("missing"), "playerctl could not be started"),
])
def test_linux_failure_message_says_why_playerctl_failed(monkeypatch, failure, expected_detail):
    monkeypatch.setattr("src.media_backend.os_backend.sys.platform", "linux")
    monkeypatch.setattr("src.media_backend.os_backend.shutil.which", lambda _: "/usr/bin/playerctl")
    monkeypatch.setattr(
        "src.media_backend.os_backend.subprocess.run", MagicMock(side_effect=failure),
    )
    with pytest.raises(RuntimeError) as caught:
        OSMediaController().pause()
    message = str(caught.value)
    assert message.startswith("Media request failed")
    assert expected_detail in message


def test_linux_failure_detail_uses_only_the_first_stderr_line_and_is_bounded(monkeypatch):
    monkeypatch.setattr("src.media_backend.os_backend.sys.platform", "linux")
    monkeypatch.setattr("src.media_backend.os_backend.shutil.which", lambda _: "/usr/bin/playerctl")
    noisy = "x" * 500 + "\nsecond line that must not be shown"
    monkeypatch.setattr(
        "src.media_backend.os_backend.subprocess.run",
        MagicMock(side_effect=subprocess.CalledProcessError(1, "playerctl", stderr=noisy)),
    )
    with pytest.raises(RuntimeError) as caught:
        OSMediaController().next_track()
    assert "second line" not in str(caught.value)
    assert len(str(caught.value)) < 250


@pytest.mark.parametrize("window, delivered, handled", [
    (0, 1, 1), (123, 0, 1), (123, 1, 0), (123, 1, 1),
])
def test_native_windows_playback_reports_delivery_and_support(
    monkeypatch, window, delivered, handled,
):
    from src.media_backend.os_backend import _default_windows_app_sender

    user32 = MagicMock()
    user32.GetForegroundWindow.return_value = window

    def send(hwnd, message, sender, command, flags, timeout, result):
        assert (hwnd, message, sender, command) == (window, 0x0319, window, 47 << 16)
        assert (flags, timeout) == (2, 1000)
        result._obj.value = handled
        return delivered

    user32.SendMessageTimeoutW.side_effect = send
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: user32, raising=False)
    if window and delivered and handled:
        _default_windows_app_sender(APPCOMMAND_MEDIA_PAUSE)
    else:
        with pytest.raises(RuntimeError):
            _default_windows_app_sender(APPCOMMAND_MEDIA_PAUSE)


def test_native_windows_key_is_pressed_and_released(monkeypatch):
    from src.media_backend.os_backend import _default_windows_key_sender

    user32 = MagicMock()
    monkeypatch.setattr(ctypes, "windll", SimpleNamespace(user32=user32), raising=False)
    _default_windows_key_sender(VK_VOLUME_UP)
    assert [call.args for call in user32.keybd_event.call_args_list] == [
        (VK_VOLUME_UP, 0, 0, 0), (VK_VOLUME_UP, 0, 2, 0),
    ]
