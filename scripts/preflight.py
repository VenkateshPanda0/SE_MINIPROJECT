"""Read-only checks for local demo prerequisites; never record or send audio."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import speech_recognition as sr


def main() -> int:
    checks = {"python": sys.version_info >= (3, 12)}
    checks["supported_platform"] = sys.platform == "win32" or sys.platform.startswith("linux")
    checks["pyaudio"] = importlib.util.find_spec("pyaudio") is not None
    if checks["pyaudio"]:
        try:
            audio = sr.Microphone.get_pyaudio().PyAudio()
            try:
                checks["microphone"] = audio.get_default_input_device_info()["maxInputChannels"] > 0
            finally:
                audio.terminate()
        except (OSError, AttributeError):
            checks["microphone"] = False
    else:
        checks["microphone"] = False
    if sys.platform.startswith("linux"):
        executable = shutil.which("playerctl")
        checks["playerctl"] = executable is not None
        try:
            result = subprocess.run(
                [executable, "--list-all"], check=True, capture_output=True,
                text=True, timeout=3,
            ) if executable else None
            checks["active_player"] = result is not None and bool(result.stdout.strip())
        except (OSError, subprocess.SubprocessError):
            checks["active_player"] = False
    reports = Path(__file__).resolve().parents[1] / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "preflight.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))
    print("This does not verify microphone permission, internet access, or real media actions.")
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
