"""Fail closed unless a V2 collection is frozen and dispatched in its UTC slot."""
from __future__ import annotations

import argparse
import os
from datetime import datetime, timezone
from pathlib import Path

from tools.mt5_xauusd_v2_protocol import V2_IDS, V2ProtocolError, load_frozen_v2


def validate_dispatch(session_id: str, *, now: datetime | None = None, root: Path | None = None) -> dict:
    if session_id not in V2_IDS:
        raise V2ProtocolError("only a preregistered V2 session ID may be dispatched")
    root = root or Path.cwd()
    plan, _, freeze = load_frozen_v2(
        amendment_path=root / "research/xauusd_walk_forward_plan_v2_amendment.json",
        freeze_path=root / "research/xauusd_v2_freeze.json",
        base_plan_path=root / "research/xauusd_walk_forward_plan_v1.json",
        registry_path=root / "research/xauusd_strategy_registry_v1.json",
        repo_root=root,
    )
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() != timezone.utc.utcoffset(now):
        raise V2ProtocolError("dispatch clock must be timezone-aware UTC")
    slot = plan["v2_protocol"]["schedule"][session_id]
    if abs((now.astimezone(timezone.utc) - slot["start"]).total_seconds()) > 600:
        raise V2ProtocolError("current UTC time is outside this session's frozen +/-10 minute dispatch window")
    return {
        "session_id": session_id,
        "frozen_utc": plan["v2_protocol"]["freeze_utc"],
        "scheduled_start_utc": slot["start"].isoformat(),
        "scheduled_end_utc": slot["end"].isoformat(),
        "commission_lock": freeze["commission_evidence_sha256_or_explicit_unverified_lock"],
        "order_submission": False,
        "position_management": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session-id", default=os.environ.get("VELTRIX_SESSION_ID", ""))
    args = parser.parse_args()
    try:
        result = validate_dispatch(args.session_id)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(2, f"V2 COLLECTION DISPATCH BLOCKED: {exc}\\n")
    import json
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
