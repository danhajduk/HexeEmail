from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from email_node.patterns import (  # noqa: E402
    PatternGenerationClient,
    PatternGenerationPipeline,
    PatternGenerationRequest,
    PatternGenerationService,
    PatternGenerationWriter,
)


def build_service(*, target_api_base_url: str) -> PatternGenerationService:
    client = PatternGenerationClient(target_api_base_url=target_api_base_url)
    pipeline = PatternGenerationPipeline(client)
    writer = PatternGenerationWriter()
    return PatternGenerationService(pipeline, writer)


async def run_cli(argv: list[str] | None = None, *, service_factory=build_service) -> int:
    parser = argparse.ArgumentParser(description="Generate a Phase 4 pattern template from a sample email JSON file.")
    parser.add_argument("--input", required=True, help="Path to the sample email JSON file.")
    parser.add_argument("--target-api-base-url", default="http://127.0.0.1:9002", help="AI node API base URL.")
    parser.add_argument("--allow-overwrite", action="store_true", help="Allow overwriting an existing draft template.")
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    try:
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("input JSON must be an object")
        request = PatternGenerationRequest.model_validate(payload)
        service = service_factory(target_api_base_url=args.target_api_base_url)
        result = await service.generate(request, allow_overwrite=bool(args.allow_overwrite))
    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1

    print(f"SUCCESS: {result['template_id']} -> {result['file_path']}")
    return 0


def main() -> int:
    return asyncio.run(run_cli())


if __name__ == "__main__":
    raise SystemExit(main())
