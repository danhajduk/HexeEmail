from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from email_node.patterns import ProbationEvaluator, ProbationPromotionPolicy, ProbationStore  # noqa: E402
from providers.gmail.models import GmailPhase3DetectedEmail  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect ORDER probation templates and evaluations.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    state_parser = subparsers.add_parser("state", help="Show probation template state.")
    state_parser.add_argument("template_id")

    eval_parser = subparsers.add_parser("evaluations", help="Show probation evaluations.")
    eval_parser.add_argument("template_id")

    evaluate_parser = subparsers.add_parser("evaluate", help="Run a probation evaluation on a Phase 3 sample JSON file.")
    evaluate_parser.add_argument("template_id")
    evaluate_parser.add_argument("phase3_json")

    eligibility_parser = subparsers.add_parser("eligibility", help="Show current promotion eligibility.")
    eligibility_parser.add_argument("template_id")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = ProbationStore()

    if args.command == "state":
        state = store.load_state(args.template_id)
        print(json.dumps(state.model_dump(mode="json") if state is not None else None, indent=2))
        return 0

    if args.command == "evaluations":
        payload = {
            "evaluations": store.list_evaluations(args.template_id),
            "shadow": store.list_shadow_comparisons(args.template_id),
        }
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "evaluate":
        payload = json.loads(Path(args.phase3_json).read_text(encoding="utf-8"))
        phase3 = GmailPhase3DetectedEmail.model_validate(payload)
        evaluation = ProbationEvaluator(probation_store=store).evaluate(phase3, template_id=args.template_id)
        print(json.dumps(evaluation.model_dump(mode="json"), indent=2))
        return 0

    if args.command == "eligibility":
        state = store.load_state(args.template_id)
        if state is None:
            print("null")
            return 0
        policy = ProbationPromotionPolicy()
        payload = {
            "template_id": state.template_id,
            "is_promotion_eligible": policy.is_promotion_eligible(state),
            "should_remain_on_probation": policy.should_remain_on_probation(state),
            "should_mark_for_refinement": policy.should_mark_for_refinement(state),
            "should_reject_template": policy.should_reject_template(state),
        }
        print(json.dumps(payload, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
