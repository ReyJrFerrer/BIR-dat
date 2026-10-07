"""Repeatable local review/export commands using the same application core."""

import argparse
import json
from pathlib import Path

from .conversion import build_snapshot
from .dat import filename, serialize
from .domain import Review
from .pdf import render
from .review import audit, load_reference
from .workbook import read_workbook


def main() -> None:
    parser = argparse.ArgumentParser(description="Local BIR alphalist review and conversion")
    commands = parser.add_subparsers(dest="command", required=True)
    serve = commands.add_parser("serve", help="Start the local web application")
    serve.add_argument("--port", type=int, default=8000)
    inspect = commands.add_parser("review", help="Write a validation/audit JSON summary")
    source = inspect.add_mutually_exclusive_group(required=True)
    source.add_argument("--reference", choices=["validated", "workbook"])
    source.add_argument("--workbook", type=Path)
    inspect.add_argument("--output", type=Path, required=True, help="New output directory")
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn

        uvicorn.run(
            "alphalist.web:app", host="127.0.0.1", port=args.port, workers=1, access_log=False
        )
        return
    try:
        review = (
            load_reference(args.reference)
            if args.reference
            else Review(read_workbook(args.workbook.read_bytes(), args.workbook.name))
        )
        args.output.mkdir(parents=True, exist_ok=False)
        snapshot = build_snapshot(review)
        (args.output / "review.json").write_text(
            json.dumps(audit(review), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (args.output / ("alphalist.pdf" if snapshot.valid else "alphalist-draft.pdf")).write_bytes(
            render(snapshot, draft=not snapshot.valid)
        )
        if snapshot.valid:
            (args.output / filename(snapshot)).write_bytes(serialize(snapshot))
        print(
            f"{len(snapshot.records)} employees. "
            + ("Internal checks passed." if snapshot.valid else "Needs correction; draft only.")
        )
        print(f"Outputs: {args.output.resolve()}")
    except (ValueError, OSError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
