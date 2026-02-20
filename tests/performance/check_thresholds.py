"""
Validate Locust CSV output against threshold configuration.

After a Locust run completes, CI invokes this script to decide whether
the build passes or fails.  It reads the ``*_stats.csv`` file that
Locust generates, extracts the **Aggregated** row, and compares two
metrics against limits defined in :file:`thresholds.yml`:

- **Error rate (%)** — ``Failure Count / Request Count × 100``
- **P95 latency (ms)** — the 95th-percentile response time

Exit codes follow a three-state convention so that CI can distinguish
"thresholds breached" from "script crashed":

- ``0`` — all thresholds passed
- ``1`` — at least one threshold was breached
- ``2`` — the script itself failed (missing file, bad YAML, etc.)

Key Concepts Demonstrated:
- CSV-based performance gating without external tooling
- Defensive parsing (multiple p95 column name variants, safe float
  conversion) to tolerate Locust version differences
- Human-readable summary table printed to stdout for CI logs
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

import yaml

# Three-state exit codes so CI can tell "test failed" from "script crashed".
EXIT_PASS = 0
EXIT_THRESHOLD_BREACH = 1
EXIT_SCRIPT_ERROR = 2


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments for the threshold checker."""
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
    """
    Read threshold limits from a YAML file.

    Args:
        path: Path to a YAML file containing ``max_error_rate_percent``
            and ``max_p95_ms`` keys.

    Returns:
        A dictionary with the two threshold values as floats.

    Raises:
        ValueError: If either key is missing or non-numeric.
    """
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
    """
    Find and return the ``Aggregated`` summary row from a Locust stats CSV.

    Locust writes one row per endpoint plus a final ``Aggregated`` row
    that summarises all traffic.  This function scans for that row by
    checking both the ``Name`` and ``Type`` columns, since the column
    layout varies between Locust versions.

    Args:
        stats_path: Path to the ``*_stats.csv`` file produced by Locust.

    Returns:
        The aggregated row as an ordered dictionary of column→value pairs.

    Raises:
        ValueError: If no ``Aggregated`` row is found.
    """
    with stats_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    for row in rows:
        if row.get("Name") == "Aggregated" or row.get("Type") == "Aggregated":
            return row

    raise ValueError("Could not find 'Aggregated' row in stats CSV")


def _parse_float(value: Any, field_name: str) -> float:
    """
    Coerce *value* to ``float``, stripping ``%`` suffixes if present.

    Args:
        value: The raw CSV cell value (may be ``None``, empty, or
            contain a trailing ``%``).
        field_name: Human-readable name used in error messages.

    Returns:
        The numeric value as a float.

    Raises:
        ValueError: If the value is missing, empty, or non-numeric.
    """
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
    """
    Extract the 95th-percentile latency from an aggregated stats row.

    Different Locust versions label this column differently, so we try
    several known variants in order.

    Args:
        row: The ``Aggregated`` row dictionary from the CSV.

    Returns:
        The P95 latency in milliseconds.

    Raises:
        ValueError: If none of the known column names are found.
    """
    candidates = ("95%", "95%ile", "95th percentile", "p95")
    for candidate in candidates:
        if candidate in row and row[candidate] not in (None, ""):
            return _parse_float(row[candidate], candidate)
    raise ValueError("Could not find p95 column in stats CSV")


def _compute_error_rate_percent(row: dict[str, str]) -> float:
    """
    Compute the error rate as a percentage from request and failure counts.

    Args:
        row: The ``Aggregated`` row dictionary from the CSV.

    Returns:
        ``(Failure Count / Request Count) × 100``.

    Raises:
        ValueError: If counts are missing or ``Request Count`` is zero.
    """
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
    """Print a human-readable results table to stdout for CI logs."""
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
    """
    Entry point: load thresholds, parse CSV, compare, and print results.

    Returns:
        ``EXIT_PASS`` (0) if all thresholds are met,
        ``EXIT_THRESHOLD_BREACH`` (1) if any are exceeded, or
        ``EXIT_SCRIPT_ERROR`` (2) on unexpected failures.
    """
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
