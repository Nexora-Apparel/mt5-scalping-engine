"""Offline replay of legacy historical XAUUSD quote-state mechanics only."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.mt5_xauusd_tick_replay import (
    ReplayError, load_verified_ticks, replay_historical_quote_mechanics,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        ticks, profile = load_verified_ticks(
            args.csv, args.manifest, allow_legacy_historical=True
        )
        result = replay_historical_quote_mechanics(ticks, profile)
    except (ReplayError, OSError, ValueError) as exc:
        parser.exit(2, f"MECHANICS REPLAY FAIL: {exc}\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
