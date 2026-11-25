"""Run the frozen V2 validation protocol; holdout and net P/L remain locked."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.mt5_xauusd_v2_protocol import V2_IDS, V2ProtocolError, load_frozen_v2
from tools.mt5_xauusd_walk_forward import run_walk_forward


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--amendment", type=Path, default=Path("research/xauusd_walk_forward_plan_v2_amendment.json"))
    parser.add_argument("--freeze", type=Path, default=Path("research/xauusd_v2_freeze.json"))
    parser.add_argument("--base-plan", type=Path, default=Path("research/xauusd_walk_forward_plan_v1.json"))
    parser.add_argument("--registry", type=Path, default=Path("research/xauusd_strategy_registry_v1.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = Path.cwd()
    try:
        plan, _, _ = load_frozen_v2(
            amendment_path=args.amendment, freeze_path=args.freeze,
            base_plan_path=args.base_plan, registry_path=args.registry,
            repo_root=root,
        )
        catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
        catalog_ids = {item.get("session_id") for item in catalog.get("sessions", [])}
        if not set(V2_IDS).issubset(catalog_ids):
            raise V2ProtocolError("all four frozen V2 validation sessions must be present before evaluation")
        if any(isinstance(sid, str) and sid.startswith("validation_") for sid in catalog_ids):
            raise V2ProtocolError("V1 validation sessions are prohibited from V2 corrected rescoring")
        result = run_walk_forward(
            plan, json.loads(args.registry.read_text(encoding="utf-8")), catalog,
            stage="validation", base_dir=args.catalog.parent,
        )
        result["protocol_version"] = 2
        result["v2_amendment_sha256"] = plan["v2_protocol"]["amendment_sha256"]
        result["implementation_commit_sha"] = plan["v2_protocol"]["implementation_commit_sha"]
        result["freeze_utc"] = plan["v2_protocol"]["freeze_utc"]
        result["commission_status"] = "UNVERIFIED_REQUIRED_INPUT"
        result["net_performance_allowed"] = False
        result["holdout_access"] = "SEALED"
        result["candidate_approval"] = "NOT_APPROVED"
        result["order_submission"] = False
        result["position_management"] = False
    except (OSError, json.JSONDecodeError, V2ProtocolError, KeyError, TypeError, ValueError) as exc:
        parser.exit(2, f"V2 EVALUATION BLOCKED: {exc}\\n")
    rendered = json.dumps(result, indent=2, sort_keys=True) + "\\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
