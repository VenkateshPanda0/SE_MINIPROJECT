"""Run the same quality gates locally and in CI, preserving reviewable reports."""

import argparse
import json
from pathlib import Path
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", action="store_true", help="Also query dependency advisories")
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    for name in ("bandit.json", "coverage.json", "coverage.xml", "pytest.xml", "audit.json"):
        (reports / name).unlink(missing_ok=True)

    def run(*arguments: str) -> bool:
        print(f"\nRunning: {' '.join(arguments)}", flush=True)
        return subprocess.run([sys.executable, "-m", *arguments], cwd=root).returncode == 0

    results = {}
    results["style"] = run("flake8", "--jobs", "1", "src", "scripts")
    results["security"] = run(
        "bandit", "-r", "src", "-x", "*/tests/*", "-f", "json", "-o", "reports/bandit.json",
    )
    if (reports / "bandit.json").exists():
        report = json.loads((reports / "bandit.json").read_text())
        results["security"] &= not report.get("errors") and not report.get("results")
    else:
        results["security"] = False
    results["tests"] = run("coverage", "run", "-m", "pytest", "-q", "--junitxml=reports/pytest.xml")
    results["coverage"] = run("coverage", "report", "-m")
    results["coverage_json"] = run("coverage", "json", "-o", "reports/coverage.json")
    coverage_path = reports / "coverage.json"
    if coverage_path.exists():
        totals = json.loads(coverage_path.read_text())["totals"]
        results["statement_coverage"] = totals["percent_statements_covered"] >= 90
        results["branch_coverage"] = totals["percent_branches_covered"] >= 90
    else:
        results["statement_coverage"] = results["branch_coverage"] = False
    results["coverage_xml"] = run("coverage", "xml", "-o", "reports/coverage.xml")
    results["coverage_html"] = run("coverage", "html")
    if options.audit:
        results["dependencies"] = run(
            "pip_audit", "-r", "requirements-dev.txt", "-r", "requirements-audio.txt",
            "--progress-spinner", "off",
            "-f", "json", "-o", "reports/audit.json", "--cache-dir", "reports/audit-cache",
        )
    (reports / "checks.json").write_text(json.dumps(results, indent=2) + "\n")
    print(json.dumps(results, indent=2))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
