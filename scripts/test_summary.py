#!/usr/bin/env python3
"""Generate a per-module test & coverage summary for the README.

Reads the artefacts produced by the backend test run:

* ``coverage.xml``  — Cobertura report (``pytest --cov-report=xml``)
* ``junit*.xml``    — JUnit results   (``pytest --junitxml=...``)

…and produces a compact Markdown summary with:

* a headline (total tests, pass/fail, overall line coverage),
* a table of **tests grouped by suite** (unit / integration / e2e per module),
* a table of **line coverage grouped by domain module**.

The summary is injected into ``README.md`` between the markers::

    <!-- TEST-SUMMARY:START -->
    ...generated content...
    <!-- TEST-SUMMARY:END -->

and (when running inside GitHub Actions) is also appended to the run's job
summary via ``$GITHUB_STEP_SUMMARY``.

Usage (from the repository root)::

    python scripts/test_summary.py \
        --coverage backend/coverage-integration.xml \
        --junit backend/junit-unit.xml backend/junit-integration.xml \
        --readme README.md

All arguments are optional; the defaults match the CI layout.
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

START_MARKER = "<!-- TEST-SUMMARY:START -->"
END_MARKER = "<!-- TEST-SUMMARY:END -->"

# Coverage filenames may be relative to the project root (``app/modules/...``)
# or to the configured source root (``modules/...``); both forms are handled by
# stripping a leading ``app/`` before matching. First matching prefix wins.
MODULE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("modules/identity", "identity"),
    ("modules/content", "content"),
    ("modules/files", "files"),
    ("modules/engagement", "engagement"),
    ("modules/notifications", "notifications"),
    ("modules/audit", "audit"),
    ("shared", "shared"),
)
MODULE_ORDER = (
    "identity",
    "content",
    "files",
    "engagement",
    "shared",
    "notifications",
    "audit",
    "core",
)


# --------------------------------------------------------------------------- #
# Coverage parsing                                                            #
# --------------------------------------------------------------------------- #


@dataclass
class Cov:
    covered: int = 0
    total: int = 0

    @property
    def pct(self) -> float:
        return 100.0 * self.covered / self.total if self.total else 0.0


def _module_for(path: str) -> str:
    norm = path.replace("\\", "/")
    if norm.startswith("app/"):
        norm = norm[len("app/") :]
    for prefix, name in MODULE_PREFIXES:
        if norm.startswith(prefix):
            return name
    return "core"


def parse_coverage(coverage_path: Path) -> tuple[dict[str, Cov], Cov]:
    """Return per-module coverage and the overall total."""
    per_module: dict[str, Cov] = {}
    overall = Cov()
    if not coverage_path.exists():
        return per_module, overall

    root = ET.parse(coverage_path).getroot()
    for cls in root.iter("class"):
        filename = cls.get("filename", "")
        module = _module_for(filename)
        bucket = per_module.setdefault(module, Cov())
        for line in cls.iter("line"):
            hits = int(line.get("hits", "0"))
            bucket.total += 1
            overall.total += 1
            if hits > 0:
                bucket.covered += 1
                overall.covered += 1
    return per_module, overall


# --------------------------------------------------------------------------- #
# JUnit parsing                                                               #
# --------------------------------------------------------------------------- #


@dataclass
class Suite:
    total: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def passed(self) -> int:
        return self.total - self.failed - self.skipped - self.errors


@dataclass
class JUnitTotals:
    by_suite: dict[str, Suite] = field(default_factory=dict)
    total: Suite = field(default_factory=Suite)


def _suite_label(classname: str) -> str:
    """Turn ``tests.unit.content.test_use_cases.TestX`` into ``unit / content``."""
    parts = classname.split(".")
    if len(parts) < 2 or parts[0] != "tests":
        return classname or "other"
    kind = parts[1]  # unit | integration | e2e
    if kind == "e2e":
        return "e2e (HTTP)"
    module = parts[2] if len(parts) > 2 else ""
    return f"{kind} / {module}" if module else kind


def parse_junit(junit_paths: list[Path]) -> JUnitTotals:
    totals = JUnitTotals()
    for path in junit_paths:
        if not path.exists():
            continue
        root = ET.parse(path).getroot()
        for case in root.iter("testcase"):
            label = _suite_label(case.get("classname", ""))
            suite = totals.by_suite.setdefault(label, Suite())
            suite.total += 1
            totals.total.total += 1
            child_tags = {c.tag for c in case}
            if "failure" in child_tags:
                suite.failed += 1
                totals.total.failed += 1
            elif "error" in child_tags:
                suite.errors += 1
                totals.total.errors += 1
            elif "skipped" in child_tags:
                suite.skipped += 1
                totals.total.skipped += 1
    return totals


# --------------------------------------------------------------------------- #
# Rendering                                                                   #
# --------------------------------------------------------------------------- #


def _bar(pct: float) -> str:
    filled = round(pct / 10)
    return "█" * filled + "░" * (10 - filled)


def render(coverage: dict[str, Cov], overall: Cov, junit: JUnitTotals) -> str:
    lines: list[str] = []
    t = junit.total
    status = "✅ all passing" if (t.failed + t.errors) == 0 else f"❌ {t.failed + t.errors} failing"
    # Live badges: tests-count (value refreshed by this script every CI run) +
    # the Codecov coverage badge (rendered live from the latest upload).
    colour = "2ea44f" if (t.failed + t.errors) == 0 else "e05d44"
    repo = "JakubPatkowski/Python-Forum-API"
    lines.append(
        f"![tests](https://img.shields.io/badge/tests-{t.passed}%20passing-{colour}"
        "?logo=pytest&logoColor=white) "
        f"[![coverage](https://codecov.io/gh/{repo}/branch/master/graph/badge.svg)]"
        f"(https://app.codecov.io/gh/{repo}) "
        f"[![Test Analytics](https://img.shields.io/badge/Codecov-Test%20Analytics-F01F7A"
        f"?logo=codecov&logoColor=white)](https://app.codecov.io/gh/{repo}/tests/master)"
    )
    lines.append("")
    lines.append(
        f"**{t.total} automated tests** — {t.passed} passed, {t.failed} failed, "
        f"{t.skipped} skipped · **{overall.pct:.0f}% line coverage** · {status}"
    )
    lines.append("")
    lines.append(
        "_Auto-generated from `coverage.xml` + JUnit by "
        "`scripts/test_summary.py` on each backend CI run._"
    )
    lines.append("")

    # Tests by suite
    lines.append("**Tests by suite**")
    lines.append("")
    lines.append("| Suite | Tests | Passed | Failed | Skipped |")
    lines.append("|-------|:-----:|:------:|:------:|:-------:|")
    for label in sorted(junit.by_suite):
        s = junit.by_suite[label]
        lines.append(f"| `{label}` | {s.total} | {s.passed} | {s.failed} | {s.skipped} |")
    lines.append(
        f"| **Total** | **{t.total}** | **{t.passed}** | **{t.failed}** | **{t.skipped}** |"
    )
    lines.append("")

    # Coverage by module
    lines.append("**Line coverage by module**")
    lines.append("")
    lines.append("| Module | Coverage | |")
    lines.append("|--------|:--------:|--|")
    for module in MODULE_ORDER:
        c = coverage.get(module)
        if c is None or c.total == 0:
            continue
        lines.append(f"| `{module}` | {c.pct:.0f}% | `{_bar(c.pct)}` |")
    lines.append(f"| **overall** | **{overall.pct:.0f}%** | `{_bar(overall.pct)}` |")
    lines.append("")
    return "\n".join(lines)


def inject_into_readme(readme: Path, block: str) -> bool:
    if not readme.exists():
        return False
    text = readme.read_text(encoding="utf-8")
    if START_MARKER not in text or END_MARKER not in text:
        return False
    before = text.split(START_MARKER)[0]
    after = text.split(END_MARKER)[1]
    new = f"{before}{START_MARKER}\n\n{block}\n{END_MARKER}{after}"
    if new != text:
        readme.write_text(new, encoding="utf-8")
    return True


# --------------------------------------------------------------------------- #
# Main                                                                        #
# --------------------------------------------------------------------------- #


def _resolve(patterns: list[str]) -> list[Path]:
    out: list[Path] = []
    for p in patterns:
        out.extend(Path(m) for m in glob.glob(p))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", default="backend/coverage-integration.xml")
    parser.add_argument(
        "--junit",
        nargs="*",
        default=["backend/junit-unit.xml", "backend/junit-integration.xml", "backend/junit.xml"],
    )
    parser.add_argument("--readme", default="README.md")
    parser.add_argument(
        "--print",
        action="store_true",
        help="Print the summary to stdout instead of editing README.",
    )
    args = parser.parse_args(argv)

    coverage, overall = parse_coverage(Path(args.coverage))
    junit = parse_junit(_resolve(args.junit))
    block = render(coverage, overall, junit)

    if args.print:
        print(block)
    else:
        ok = inject_into_readme(Path(args.readme), block)
        if ok:
            print(f"Injected test summary into {args.readme}")
        else:
            print(
                f"WARNING: could not inject into {args.readme} "
                "(missing file or markers) — printing instead:\n",
                file=sys.stderr,
            )
            print(block)

    # GitHub Actions job summary.
    gh_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if gh_summary:
        with open(gh_summary, "a", encoding="utf-8") as fh:
            fh.write("## 🧪 Test summary\n\n" + block + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
