# Validation and release checklist

Validated on 20 November 2026. Automated implementation checks pass; physical
system acceptance and a hosted GitHub Actions run remain pending.

## Automated evidence

| Check | Result |
| --- | --- |
| Python 3.12, clean virtual environment | Installation and automated gates pass |
| Python 3.14, project virtual environment | Automated gates pass |
| pytest | 167 passing tests (Python 3.12, re-run after the start-up microphone check, parser fix and traceability guard were added) |
| Production statement coverage | 258/259 statements, 99.6% |
| Production branch coverage | 48/50 branches, 96.0% |
| Combined coverage | 306/309 opportunities, 99.0% |
| Flake8 | Pass for source and scripts |
| Bandit 1.9.4 | No findings; no scanning errors |
| pip-audit | No known vulnerabilities in resolved runtime, development, and optional audio dependencies at scan time |
| Physical prerequisites in this environment | Missing PyAudio/PortAudio headers, playerctl, and an available media player; no `/dev/snd` device directory |

Run `python scripts/run_checks.py --audit` to regenerate the evidence in
`reports/`, plus annotated HTML in `htmlcov/`. These generated files are ignored
by Git; CI uploads the corresponding artifacts. The final check summary is
`reports/checks.json`. Advisory results are time-dependent and cannot guarantee
that a package has no vulnerabilities.

Native Windows APIs and Linux playerctl interactions are mocked in automated
tests. Their complete source coverage establishes tested application logic, not
physical playback correctness. Recognition timing tests use deterministic fakes
and exclude real microphone/network/provider latency. SpeechRecognition emits
upstream audio-module deprecation warnings; these are visible in test results.

## Implemented corrections

- Windows play/resume and pause send distinct explicit commands instead of a
  shared toggle. Missing foreground targets, delivery failures, and unsupported
  commands report errors.
- Linux uses playerctl/MPRIS for real actions. Missing tools and unsupported
  platforms fail explicitly rather than silently succeeding.
- Default dispatch makes one volume request, consistent with the SRS; callers
  can configure repeated volume steps.
- Recognition has a five-second external-operation timeout. Input-unavailable
  feedback and a loop delay avoid silent busy looping.
- Start-up exits with status 1 and an explanation when no usable microphone is
  found, instead of looping on "No command heard" forever.
- Punctuation in recognized text is treated as a space (SRS FR-05), so
  `volume-up` is recognized as Volume Up. The alias allow-list is unchanged.
- A traceability test fails the build when the SRS matrix cites a test or file
  that does not exist.
- Recognized transcripts are not printed. Documentation discloses external
  audio processing.
- Recovery, invalid timeout, backend routing, native-message failure, and
  privacy-output tests supplement the original suite.
- Source/security/test/coverage gates share one cross-platform runner. Bandit
  errors fail the gate even when its process exit status is zero.
- GitHub Actions checks Windows/Linux and Python 3.12/3.14, enforcing at least
  90% combined coverage and 90% each for statement and branch coverage.
- Requirements, RTM, architecture, installation, and test documentation reflect
  the implementation. Direct dependencies have exact versions; this is not a
  fully locked transitive dependency graph.

## Physical demo preparation

Recommended runtime: Python 3.12. Install development and audio requirements in
an activated virtual environment. On Debian/Ubuntu, install `portaudio19-dev`,
`python3-dev`, a compiler, and `playerctl` using the system package manager before
installing PyAudio. On Windows, grant microphone permission and focus a media
player that supports explicit WM_APPCOMMAND playback.

```bash
python -m pip install -r requirements-dev.txt
python -m pip install -r requirements-audio.txt
python scripts/preflight.py
python -m src.main
```

Preflight enumerates prerequisite availability without recording/sending audio.
It cannot establish permission, connectivity, speech accuracy, or media control.
The attempted PyAudio installation here failed because `portaudio.h` is absent;
the application therefore cannot be physically demonstrated in this environment.

## Manual acceptance record

Record OS, Python version, microphone, player/version, network conditions,
reviewer, date, observed result, and evidence for each row. Use at least two
tracks for track navigation. Set volume to a moderate level before testing.

| Test | Expected result | Actual status |
| --- | --- | --- |
| Volume Up | Audible/visible volume increase | Pending physical test |
| Volume Down | Audible/visible volume decrease | Pending physical test |
| Play; Play again | Playing; second request must not pause | Pending physical test |
| Pause; Pause again | Paused; second request must not resume | Pending physical test |
| Resume; Resume again | Playing; second request must not pause | Pending physical test |
| Next | Next playlist track selected | Pending physical test |
| Previous | Previous playlist track selected | Pending physical test |
| Unsupported phrase | No media action; safe message | Pending physical test |
| Silence/unintelligible speech | Safe feedback; later command works | Pending physical test |
| Network unavailable, then restored | Safe failure; later capture succeeds | Pending physical test |
| Player closed/unavailable | Failure reported where backend can detect it | Pending physical test |
| Ctrl+C | Clean exit | Pending physical test |
| Real recognition latency | Record separately from processing-only target | Pending physical test |
| Privacy review | No transcripts in CLI/captured output or intentional local persistence | Pending full-system review |

Windows multimedia-key volume/track requests do not confirm that a player acted.
PlaybackState records the last accepted request and does not observe player state.

## Hosted CI and submission

- Push the changes and inspect all four jobs in `.github/workflows/ci.yml`.
- Download and inspect the test, coverage, Bandit, and dependency-audit artifacts.
- Complete the physical test record and address player-specific issues.
- Obtain team/instructor sign-off and tag the accepted release.

No remote push, hosted CI success, physical pass, approval, or production
deployment is claimed by this local validation.
