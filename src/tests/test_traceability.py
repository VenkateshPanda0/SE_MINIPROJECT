"""Guard the SRS requirements traceability matrix (RTM) against stale evidence.

NFR-04 requires "RTM has a test reference for every FR". The RTM names tests
and files as evidence; if one is renamed or deleted the matrix silently stops
being true. These checks fail instead.
"""

import ast
from pathlib import Path
import re

import pytest

SRC = Path(__file__).resolve().parents[1]
ROOT = SRC.parent
SRS = ROOT / "docs" / "SRS.md"
REFERENCE = re.compile(r"`((?:[\w/]+\.py(?:::)?)?(?:test_\w+)?)`")


def _rtm_section() -> str:
    text = SRS.read_text(encoding="utf-8")
    start = text.index("## 8. Requirements traceability matrix")
    end = text.index("\n## ", start + 1)
    return text[start:end]


def _references() -> list[tuple[str | None, str | None]]:
    """Return (file, test name) pairs cited in backticks in the RTM."""
    found = []
    for token in REFERENCE.findall(_rtm_section()):
        if not token:
            continue
        path, _, name = token.partition("::")
        if path.startswith("test_"):
            path, name = "", path
        elif not path.endswith(".py"):
            continue
        found.append((path or None, name or None))
    return found


def _test_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _all_test_names() -> set[str]:
    names: set[str] = set()
    for path in SRC.rglob("test_*.py"):
        names |= _test_names(path)
    return names


def test_rtm_cites_automated_evidence():
    assert len(_references()) >= 10


@pytest.mark.parametrize("path, name", _references(), ids=lambda v: str(v))
def test_rtm_reference_exists(path, name):
    if path is not None:
        # The RTM says paths are relative to src/; repo-level files (scripts/, .github/)
        # are also cited, so fall back to the repository root.
        target = next((base / path for base in (SRC, ROOT) if (base / path).is_file()), None)
        assert target is not None, f"RTM cites missing file {path}"
        if name is not None:
            assert name in _test_names(target), f"RTM cites {name}, not defined in {path}"
    else:
        assert name in _all_test_names(), f"RTM cites {name}, which no test file defines"


def test_every_functional_requirement_row_has_evidence():
    """NFR-04: the RTM has a cited test for every FR row.

    Non-functional rows may rest on review or inspection, so they are not required to.
    """
    rows = [
        line for line in _rtm_section().splitlines()
        if re.match(r"\|\s*FR-", line)
    ]
    assert rows, "RTM rows not found"
    for row in rows:
        evidence = row.split("|")[3]
        assert re.search(r"`[^`]+`", evidence), f"RTM row has no cited evidence: {row[:60]}"
