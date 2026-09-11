"""Operator entry points for the WA staging pipeline.

Four subcommands, run by a person in this order:

    uv run --locked python -m scripts.wa_ingest.cli stage    ...
    uv run --locked python -m scripts.wa_ingest.cli extract  ...
    uv run --locked python -m scripts.wa_ingest.cli check    ...
    uv run --locked python -m scripts.wa_ingest.cli promote  ...

`stage` takes a file the operator has already downloaded from the official
source. No subcommand fetches anything, and `promote` refuses unless every
precondition holds, including the owner approval record.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

from scripts.wa_ingest.extraction import (
    EXPECTED_IMPLEMENTATION,
    ExtractionError,
    SectionDraft,
    build_sections_file,
    detect_tool,
    extract_page_range,
    require_tool,
    verify_staged_digest,
)
from scripts.wa_ingest.promotion import PromotionRefusal, check_promotion, promote
from scripts.wa_ingest.staging import (
    SourceIdentity,
    StagingError,
    StagingLayout,
    stage_source,
    write_json,
)

DEFAULT_STAGING_ROOT = Path("corpus/staging")
DEFAULT_ACTIVE_ROOT = Path("tests/fixtures/wa_legislation")


def _identity_from_file(path: Path) -> SourceIdentity:
    """Build the identity from an operator-written JSON file of verified metadata."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise StagingError("identity file must be a JSON object")
    assent = raw.get("assent_date")
    return SourceIdentity(
        act_title=str(raw["act_title"]),
        act_number=str(raw["act_number"]),
        version_suffix=str(raw["version_suffix"]),
        currency_start=date.fromisoformat(str(raw["currency_start"])),
        status_currency=str(raw["status_currency"]),
        status_in_force=bool(raw["status_in_force"]),
        status_date=date.fromisoformat(str(raw["status_date"])),
        official_source_url=str(raw["official_source_url"]),
        retrieved_at=datetime.fromisoformat(str(raw["retrieved_at_utc"]).replace("Z", "+00:00")),
        version_type=str(raw.get("version_type", "consolidated")),
        assent_date=date.fromisoformat(str(assent)) if assent else None,
        currency_end=raw.get("currency_end"),
    )


def _layout(args: argparse.Namespace) -> StagingLayout:
    return StagingLayout(
        root=Path(args.staging_root),
        identity=_identity_from_file(Path(args.identity)),
    )


def _cmd_stage(args: argparse.Namespace) -> int:
    layout = stage_source(
        identity=_identity_from_file(Path(args.identity)),
        downloaded_pdf=Path(args.pdf),
        staging_root=Path(args.staging_root),
    )
    print(f"staged   {layout.pdf_path}")
    print(f"manifest {layout.manifest_path}")
    print("\nNext: add the verified provisions to the manifest, then run `extract`.")
    return 0


def _cmd_extract(args: argparse.Namespace) -> int:
    layout = _layout(args)
    manifest = json.loads(layout.manifest_path.read_text(encoding="utf-8"))
    verify_staged_digest(layout.pdf_path, manifest["sha256"])

    tool = detect_tool()
    require_tool(tool, expected=args.expect_tool)
    print(f"extraction tool: {tool.implementation} {tool.version}")

    ranges = json.loads(Path(args.ranges).read_text(encoding="utf-8"))
    drafts = [
        SectionDraft(
            identifier=str(entry["identifier"]),
            heading=entry.get("heading"),
            text=extract_page_range(
                pdf_path=layout.pdf_path,
                first_page=int(entry["first_page"]),
                last_page=int(entry["last_page"]),
            ),
        )
        for entry in ranges
    ]

    payload = build_sections_file(
        source_id=manifest["source_id"],
        source_document_sha256=manifest["sha256"],
        tool=tool,
        drafts=drafts,
    )
    write_json(layout.sections_path, payload)
    print(f"sections {layout.sections_path}  ({len(drafts)} records, all unverified)")
    print(
        "\nEvery section is `verified: false`. A human must compare each against "
        "the official document and record it (gate G2) before promotion can "
        "accept a true flag."
    )
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    outcome = check_promotion(layout=_layout(args), active_root=Path(args.active_root))
    if isinstance(outcome, PromotionRefusal):
        print(f"REFUSED: {outcome.value}")
        return 1
    print(f"ready to promote -> {outcome.target_directory}")
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    outcome = promote(layout=_layout(args), active_root=Path(args.active_root))
    if isinstance(outcome, PromotionRefusal):
        print(f"REFUSED: {outcome.value}")
        print("The active corpus was not modified.")
        return 1
    print(f"promoted -> {outcome.target_directory}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="wa_ingest",
        description="Stage, extract and promote one official WA source. Fetches nothing.",
    )
    parser.add_argument("--staging-root", default=str(DEFAULT_STAGING_ROOT))
    parser.add_argument("--active-root", default=str(DEFAULT_ACTIVE_ROOT))
    parser.add_argument("--identity", required=True, help="JSON file of verified metadata")
    sub = parser.add_subparsers(dest="command", required=True)

    stage = sub.add_parser("stage", help="copy an already-downloaded official file into staging")
    stage.add_argument("--pdf", required=True, help="path to the file you downloaded")
    stage.set_defaults(handler=_cmd_stage)

    extract = sub.add_parser("extract", help="extract section text from the staged file")
    extract.add_argument("--ranges", required=True, help="JSON list of identifier/page ranges")
    extract.add_argument(
        "--expect-tool",
        default=EXPECTED_IMPLEMENTATION,
        help=(
            "pdftotext implementation you intend to extract with "
            f"(default {EXPECTED_IMPLEMENTATION}, matching the existing corpus)"
        ),
    )
    extract.set_defaults(handler=_cmd_extract)

    check = sub.add_parser("check", help="report whether promotion would be accepted")
    check.set_defaults(handler=_cmd_check)

    promote_cmd = sub.add_parser("promote", help="copy staged files into the active corpus")
    promote_cmd.set_defaults(handler=_cmd_promote)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        handler = args.handler
        return int(handler(args))
    except (StagingError, ExtractionError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
