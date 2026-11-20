import time

import pytest
import speech_recognition as sr

from src.voice_input import VoiceInput


class FakeMicrophone:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FakeRecognizer:
    def __init__(self, result="Volume Up"):
        self.result = result
        self.listen_args = None

    def listen(self, source, timeout, phrase_time_limit):
        self.listen_args = (source, timeout, phrase_time_limit)
        return "audio"

    def recognize_google(self, audio):
        return self.result


def build_voice_input(recognizer):
    return VoiceInput(
        recognizer=recognizer,
        microphone_factory=FakeMicrophone,
        listen_timeout=2.0,
        phrase_time_limit=3.0,
    )


def test_capture_returns_trimmed_transcription():
    recognizer = FakeRecognizer("  Volume Up  ")

    assert build_voice_input(recognizer).capture() == "Volume Up"
    assert recognizer.listen_args[1:] == (2.0, 3.0)


@pytest.mark.parametrize(
    "error",
    [
        sr.WaitTimeoutError,
        sr.UnknownValueError,
        sr.RequestError,
        OSError,
        AttributeError,
    ],
)
def test_capture_returns_none_for_unusable_input(error):
    class ErrorRecognizer(FakeRecognizer):
        def listen(self, source, timeout, phrase_time_limit):
            if error is sr.WaitTimeoutError:
                raise error()
            return super().listen(source, timeout, phrase_time_limit)

        def recognize_google(self, audio):
            if error is sr.UnknownValueError:
                raise error()
            raise error("speech service unavailable")

    assert build_voice_input(ErrorRecognizer()).capture() is None


def test_microphone_available_when_it_can_be_opened():
    opened = []

    class TrackingMicrophone(FakeMicrophone):
        def __enter__(self):
            opened.append("enter")
            return super().__enter__()

        def __exit__(self, *exc_info):
            opened.append("exit")
            return super().__exit__(*exc_info)

    voice = VoiceInput(recognizer=FakeRecognizer(), microphone_factory=TrackingMicrophone)

    assert voice.is_microphone_available() is True
    assert opened == ["enter", "exit"]


@pytest.mark.parametrize("error", [AttributeError, OSError])
def test_microphone_unavailable_when_pyaudio_or_device_is_missing(error):
    def broken_factory():
        raise error("no audio device")

    voice = VoiceInput(recognizer=FakeRecognizer(), microphone_factory=broken_factory)

    assert voice.is_microphone_available() is False


def test_microphone_check_does_not_hide_unexpected_errors():
    def buggy_factory():
        raise ValueError("programming error")

    voice = VoiceInput(recognizer=FakeRecognizer(), microphone_factory=buggy_factory)

    with pytest.raises(ValueError):
        voice.is_microphone_available()


def test_capture_returns_none_for_blank_transcription():
    assert build_voice_input(FakeRecognizer("   ")).capture() is None


@pytest.mark.parametrize("name", ["listen_timeout", "phrase_time_limit"])
@pytest.mark.parametrize("value", [0, -1])
def test_invalid_timeouts_are_rejected(name, value):
    kwargs = {name: value}

    with pytest.raises(ValueError):
        VoiceInput(microphone_factory=FakeMicrophone, **kwargs)


def test_capture_can_succeed_after_a_temporary_failure():
    recognizer = FakeRecognizer("Play")
    voice = build_voice_input(recognizer)
    original = recognizer.listen

    def timeout(*args, **kwargs):
        raise sr.WaitTimeoutError()

    recognizer.listen = timeout
    assert voice.capture() is None
    recognizer.listen = original
    assert voice.capture() == "Play"
    assert recognizer.operation_timeout == 5.0


def test_voice_capture_meets_component_response_target_over_100_runs():
    """Use fakes to verify VoiceInput itself adds negligible processing latency.

    The end-to-end performance check (capture through dispatcher) belongs in
    the dispatcher integration suite. This component-level check deliberately
    avoids microphone hardware and the external speech service.
    """
    durations = []

    for _ in range(100):
        started = time.perf_counter()

        assert build_voice_input(FakeRecognizer()).capture() == "Volume Up"

        durations.append(time.perf_counter() - started)

    assert sum(duration < 2 for duration in durations) >= 95
