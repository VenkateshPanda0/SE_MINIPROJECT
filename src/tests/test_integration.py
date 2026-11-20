"""End-to-end checks: spoken text -> dispatcher -> real OSMediaController -> OS request.

Unit tests elsewhere use fake controllers; these use the real backend with
injected senders, so a wrong command-to-request mapping would be caught.
"""

import pytest

from src.main import Dispatcher, listen_once
from src.media_backend import OSMediaController
from src.media_backend.os_backend import (
    APPCOMMAND_MEDIA_PAUSE,
    APPCOMMAND_MEDIA_PLAY,
    VK_MEDIA_NEXT_TRACK,
    VK_MEDIA_PREV_TRACK,
    VK_VOLUME_DOWN,
    VK_VOLUME_UP,
)


@pytest.fixture
def requests():
    """Every OS request made by the backend, in order, as (kind, code)."""
    return []


@pytest.fixture
def dispatcher(requests):
    backend = OSMediaController(
        key_sender=lambda code: requests.append(("key", code)),
        app_command_sender=lambda code: requests.append(("app", code)),
    )
    return Dispatcher(backend, volume_steps=2)


@pytest.mark.parametrize(
    "phrase, expected",
    [
        ("volume up", [("key", VK_VOLUME_UP)] * 2),
        ("Volume Down!", [("key", VK_VOLUME_DOWN)] * 2),
        ("increase volume", [("key", VK_VOLUME_UP)] * 2),
        ("play", [("app", APPCOMMAND_MEDIA_PLAY)]),
        ("pause", [("app", APPCOMMAND_MEDIA_PAUSE)]),
        ("resume", [("app", APPCOMMAND_MEDIA_PLAY)]),
        ("next", [("key", VK_MEDIA_NEXT_TRACK)]),
        ("previous track", [("key", VK_MEDIA_PREV_TRACK)]),
        ("volume-up", [("key", VK_VOLUME_UP)] * 2),
    ],
)
def test_spoken_phrase_makes_expected_os_request(dispatcher, requests, phrase, expected):
    dispatcher.handle_text(phrase)
    assert requests == expected


@pytest.mark.parametrize("phrase", ["dance", "turn it up", "play next", "!!!", "", "   ", None])
def test_unsupported_or_empty_phrase_makes_no_os_request(dispatcher, requests, phrase):
    dispatcher.handle_text(phrase)
    assert requests == []


def test_repeated_play_and_pause_send_explicit_commands(dispatcher, requests):
    """Explicit commands (not a toggle), so repeating one is harmless."""
    for phrase in ("play", "play", "pause", "pause"):
        dispatcher.handle_text(phrase)

    assert requests == [
        ("app", APPCOMMAND_MEDIA_PLAY),
        ("app", APPCOMMAND_MEDIA_PLAY),
        ("app", APPCOMMAND_MEDIA_PAUSE),
        ("app", APPCOMMAND_MEDIA_PAUSE),
    ]


@pytest.mark.parametrize("phrase", ["play", "next", "volume up"])
def test_backend_failure_is_reported_not_raised(phrase):
    def broken(_code):
        raise RuntimeError("no media session")

    backend = OSMediaController(key_sender=broken, app_command_sender=broken)

    result = Dispatcher(backend).handle_text(phrase)

    assert "failed" in result
    assert "no media session" in result


def test_dispatcher_recovers_after_backend_failure(requests):
    state = {"fail": True}

    def flaky(code):
        if state["fail"]:
            raise RuntimeError("player busy")
        requests.append(("app", code))

    backend = OSMediaController(key_sender=flaky, app_command_sender=flaky)
    dispatcher = Dispatcher(backend)

    assert "failed" in dispatcher.handle_text("pause")
    state["fail"] = False
    assert dispatcher.handle_text("pause") == "Playback paused"
    assert requests == [("app", APPCOMMAND_MEDIA_PAUSE)]


def test_listen_once_runs_phrase_through_real_backend(dispatcher, requests):
    class Voice:
        def capture(self):
            return "Pause."

    lines = []
    listen_once(Voice(), dispatcher, output=lines.append)

    assert lines == ["Playback paused"]
    assert requests == [("app", APPCOMMAND_MEDIA_PAUSE)]
