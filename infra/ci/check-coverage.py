#!/usr/bin/env python3
"""Ratcheting coverage gate for the agentic/CI stack.

Compares current coverage against a stored baseline and FAILS on regression
(current < baseline) for any tracked key. Eligible builds on `main` may raise
the baseline by passing --update.

Keys:
  python : Python unit coverage (coverage.py `coverage.json` -> totals.percent_covered)
  ts     : TypeScript unit coverage (vitest `coverage-summary.json` -> total.lines.pct)
  e2e    : Playwright critical-path spec count (junit XML testcase count)

Usage:
  python infra/ci/check-coverage.py \
      --python coverage.json \
      --ts agentic/src/control-center-ui/coverage/coverage-summary.json \
      --e2e playwright-results.xml \
      --baseline infra/ci/coverage.baseline.json \
      [--update]
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description="Ratcheting coverage gate")
    p.add_argument("--python", help="Path to Python coverage.json")
    p.add_argument("--ts", help="Path to vitest coverage-summary.json")
    p.add_argument("--e2e", help="Path to Playwright junit results XML")
    p.add_argument("--baseline", required=True, help="Path to coverage.baseline.json")
    p.add_argument("--update", action="store_true",
                   help="Write a raised baseline when current > baseline")
    return p.parse_args()


def read_json(path):
    return json.loads(Path(path).read_text())


def python_pct(path):
    data = read_json(path)
    return float(data["totals"]["percent_covered"])


def ts_pct(path):
    data = read_json(path)
    return float(data["total"]["lines"]["pct"])


def e2e_count(path):
    tree = ET.parse(path)
    root = tree.getroot()
    # junit may wrap in <testsuites> or start at <testsuite>
    cases = root.findall(".//testcase")
    return float(len(cases))


def main():
    args = parse_args()
    baseline = read_json(args.baseline)

    current = {}
    if args.python:
        current["python"] = python_pct(args.python)
    if args.ts:
        current["ts"] = ts_pct(args.ts)
    if args.e2e:
        current["e2e"] = e2e_count(args.e2e)

    regressed = False
    raised = False

    print(f"{'KEY':<8}{'BASELINE':>12}{'CURRENT':>12}  STATUS")
    print("-" * 46)
    for key, cur in current.items():
        base = float(baseline.get(key, 0.0))
        if cur < base - 1e-9:
            status = "REGRESSION"
            regressed = True
        elif cur > base + 1e-9:
            status = "raised"
            raised = True
        else:
            status = "ok"
        print(f"{key:<8}{base:>12.2f}{cur:>12.2f}  {status}")

    if regressed:
        print("\nCoverage regression detected. Build failed.", file=sys.stderr)
        sys.exit(1)

    if args.update and raised:
        new_baseline = dict(baseline)
        for key, cur in current.items():
            if cur > float(baseline.get(key, 0.0)):
                new_baseline[key] = cur
        Path(args.baseline).write_text(json.dumps(new_baseline, indent=2) + "\n")
        print("\nBaseline raised and written to", args.baseline)

    print("\nCoverage gate passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
