from __future__ import annotations

from typing import Callable

import speech_recognition as sr


class VoiceInput:
    """Capture one microphone phrase and convert it to text (FR1)."""

    def __init__(
        self,
        recognizer: sr.Recognizer | None = None,
        microphone_factory: Callable[[], sr.Microphone] | None = None,
        *,
        listen_timeout: float = 5.0,
        phrase_time_limit: float = 5.0,
        operation_timeout: float = 5.0,
    ) -> None:
        if listen_timeout <= 0:
            raise ValueError("listen_timeout must be greater than 0")
        if phrase_time_limit <= 0:
            raise ValueError("phrase_time_limit must be greater than 0")
        if operation_timeout <= 0:
            raise ValueError("operation_timeout must be greater than 0")

        self._recognizer = recognizer or sr.Recognizer()
        self._recognizer.operation_timeout = operation_timeout
        self._microphone_factory = microphone_factory or sr.Microphone
        self._listen_timeout = listen_timeout
        self._phrase_time_limit = phrase_time_limit

    def is_microphone_available(self) -> bool:
        """Return True if the microphone can be opened (PyAudio present, input device found).

        Lets the application fail once, with a clear message, instead of retrying a
        device that can never work. Recognition itself is not attempted.
        """
        try:
            with self._microphone_factory():
                return True
        except (AttributeError, OSError):
            return False

    def capture(self) -> str | None:
        """Return the recognized phrase, or None when no usable phrase exists."""
        try:
            with self._microphone_factory() as source:
                audio = self._recognizer.listen(
                    source,
                    timeout=self._listen_timeout,
                    phrase_time_limit=self._phrase_time_limit,
                )
            text = self._recognizer.recognize_google(audio)
        except (
            AttributeError,
            OSError,
            sr.WaitTimeoutError,
            sr.UnknownValueError,
            sr.RequestError,
        ):
            return None

        text = text.strip()
        return text or None
