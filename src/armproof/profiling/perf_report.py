from __future__ import annotations

from dataclasses import dataclass
import re


_ROW = re.compile(
    r"^\s*(?P<children>\d+(?:\.\d+)?)%\s+"
    r"(?P<self>\d+(?:\.\d+)?)%\s+.+?\s+\[[^]]+\]\s+"
    r"(?P<symbol>.+?)\s*$"
)


@dataclass(frozen=True)
class PerfAttribution:
    """Non-additive callchain attribution derived from ``perf report``."""

    event: str
    samples: int
    lost_samples: int
    matching_rows: int
    maximum_children_share: float
    maximum_children_symbol: str | None


def parse_perf_attribution(report: str, symbol_pattern: str) -> PerfAttribution:
    """Return the largest matching inclusive share without double-counting."""

    event_match = re.search(
        r"^# Samples: ([\d,]+(?:\.\d+)?)([KMG]?) of event '([^']+)'$",
        report,
        re.M,
    )
    lost_match = re.search(r"^# Total Lost Samples: ([\d,]+)$", report, re.M)
    if event_match is None or lost_match is None:
        raise ValueError("perf report is missing sample metadata")

    pattern = re.compile(symbol_pattern)
    matches: list[tuple[float, str]] = []
    parsed_rows = 0
    for line in report.splitlines():
        row = _ROW.match(line)
        if row is None:
            continue
        parsed_rows += 1
        symbol = row.group("symbol")
        if pattern.search(symbol):
            matches.append((float(row.group("children")) / 100.0, symbol))
    if parsed_rows == 0:
        raise ValueError("perf report contains no flat attribution rows")

    maximum = max(matches, default=(0.0, None), key=lambda item: item[0])
    sample_value = float(event_match.group(1).replace(",", ""))
    sample_multiplier = {"": 1, "K": 1_000, "M": 1_000_000, "G": 1_000_000_000}
    return PerfAttribution(
        event=event_match.group(3),
        samples=int(sample_value * sample_multiplier[event_match.group(2)]),
        lost_samples=int(lost_match.group(1).replace(",", "")),
        matching_rows=len(matches),
        maximum_children_share=maximum[0],
        maximum_children_symbol=maximum[1],
    )
