#!/usr/bin/env python3
"""Summarise AI token usage from output/logs/ai-usage.jsonl.

Usage:
    python scripts/ai-usage.py          # per-day totals
    python scripts/ai-usage.py --calls  # also break down by call label
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

LOG = Path(__file__).parent.parent / "output" / "logs" / "ai-usage.jsonl"


def main() -> None:
    if not LOG.exists():
        print(f"No usage log yet at {LOG}")
        return

    rows = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not rows:
        print("Usage log is empty.")
        return

    by_day: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_day[r.get("ts", "")[:10]].append(r)

    def tokens(r: dict) -> int:
        return r.get("in", 0) + r.get("cache_write", 0) + r.get("cache_read", 0)

    print(f"{'day':12} {'calls':>5} {'in+cache':>10} {'out':>8} {'cost':>9} {'mins':>6}")
    print("-" * 56)
    for day in sorted(by_day):
        rs = by_day[day]
        print(
            f"{day:12} {len(rs):5d} {sum(tokens(r) for r in rs):10,} "
            f"{sum(r.get('out', 0) for r in rs):8,} "
            f"${sum(r.get('cost_usd', 0) for r in rs):8.3f} "
            f"{sum(r.get('secs', 0) for r in rs) / 60:6.1f}"
        )

    if "--calls" in sys.argv:
        by_kind: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            by_kind[r.get("label", "-").split(":")[0].rstrip("0123456789-")].append(r)
        print(f"\n{'call kind':20} {'calls':>5} {'in+cache':>10} {'out':>8} {'cost':>9}")
        print("-" * 56)
        for kind in sorted(by_kind, key=lambda k: -sum(r.get("cost_usd", 0) for r in by_kind[k])):
            rs = by_kind[kind]
            print(
                f"{kind or '(none)':20} {len(rs):5d} {sum(tokens(r) for r in rs):10,} "
                f"{sum(r.get('out', 0) for r in rs):8,} "
                f"${sum(r.get('cost_usd', 0) for r in rs):8.3f}"
            )


if __name__ == "__main__":
    main()
