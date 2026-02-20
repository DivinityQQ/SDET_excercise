"""Validate Locust CSV output against threshold configuration."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import yaml

EXIT_PASS = 0
EXIT_THRESHOLD_BREACH = 1
EXIT_SCRIPT_ERROR = 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Locust stats CSV against performance thresholds."
    )
    parser.add_argument(
        "--stats",
        required=True,
        type=Path,
        help="Path to Locust *_stats.csv file",
    )
    parser.add_argument(
        "--thresholds",
        type=Path,
        default=Path("tests/performance/thresholds.yml"),
        help="Path to thresholds YAML file",
    )
    return parser.parse_args()


def _load_thresholds(path: Path) -> dict[str, float]:
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    try:
        max_error_rate = float(data["max_error_rate_percent"])
        max_p95_ms = float(data["max_p95_ms"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            "Thresholds file must define numeric max_error_rate_percent and max_p95_ms"
        ) from exc

    return {
        "max_error_rate_percent": max_error_rate,
        "max_p95_ms": max_p95_ms,
    }


def _load_aggregated_row(stats_path: Path) -> dict[str, str]:
    with stats_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        if row.get("Name") == "Aggregated" or row.get("Type") == "Aggregated":
            return row

    raise ValueError("Could not find 'Aggregated' row in stats CSV")


def _parse_float(value: Any, field_name: str) -> float:
    if value is None:
        raise ValueError(f"Missing field: {field_name}")

    text = str(value).strip().replace("%", "")
    if text == "":
        raise ValueError(f"Empty value for field: {field_name}")

    try:
        return float(text)
    except ValueError as exc:
        raise ValueError(f"Non-numeric value for {field_name}: {value}") from exc


def _extract_p95_ms(row: dict[str, str]) -> float:
    candidates = ("95%", "95%ile", "95th percentile", "p95")
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return _parse_float(row[candidate], candidate)
    raise ValueError("Could not find p95 column in stats CSV")


def _compute_error_rate_percent(row: dict[str, str]) -> float:
    request_count = _parse_float(row.get("Request Count"), "Request Count")
    failure_count = _parse_float(row.get("Failure Count"), "Failure Count")

    if request_count <= 0:
        raise ValueError("Request Count must be > 0 for threshold checks")

    return (failure_count / request_count) * 100.0


def _print_summary(
    *,
    error_rate: float,
    p95_ms: float,
    max_error_rate: float,
    max_p95_ms: float,
    passed: bool,
) -> None:
    print("Performance Threshold Check")
    print("-" * 60)
    print(f"{'Metric':<22}{'Actual':>12}{'Limit':>14}{'Status':>12}")
    print("-" * 60)

    error_status = "PASS" if error_rate <= max_error_rate else "FAIL"
    p95_status = "PASS" if p95_ms <= max_p95_ms else "FAIL"

    print(
        f"{'Error rate (%)':<22}{error_rate:>12.2f}{max_error_rate:>14.2f}{error_status:>12}"
    )
    print(f"{'P95 latency (ms)':<22}{p95_ms:>12.2f}{max_p95_ms:>14.2f}{p95_status:>12}")
    print("-" * 60)
    print(f"Overall: {'PASS' if passed else 'FAIL'}")


def main() -> int:
    args = parse_args()

    try:
        thresholds = _load_thresholds(args.thresholds)
        row = _load_aggregated_row(args.stats)
        error_rate = _compute_error_rate_percent(row)
        p95_ms = _extract_p95_ms(row)

        max_error_rate = thresholds["max_error_rate_percent"]
        max_p95_ms = thresholds["max_p95_ms"]

        passed = error_rate <= max_error_rate and p95_ms <= max_p95_ms
        _print_summary(
            error_rate=error_rate,
            p95_ms=p95_ms,
            max_error_rate=max_error_rate,
            max_p95_ms=max_p95_ms,
            passed=passed,
        )
        return EXIT_PASS if passed else EXIT_THRESHOLD_BREACH
    except Exception as exc:  # pragma: no cover - defensive CLI guard
        print(f"Threshold check failed: {exc}", file=sys.stderr)
        return EXIT_SCRIPT_ERROR


if __name__ == "__main__":
    raise SystemExit(main())
