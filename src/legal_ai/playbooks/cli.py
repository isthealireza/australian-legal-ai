"""Explicit playbook seed CLI. Never activates product playbooks."""

from __future__ import annotations

import argparse
import os
import sys

from sqlalchemy import create_engine

from legal_ai.casework.repository import CaseworkRepository
from legal_ai.playbooks.definitions.wa_motor_property_damage_v1 import (
    DISPLAY_NAME,
    PLAYBOOK_KEY,
    PLAYBOOK_VERSION,
    wa_motor_property_damage_v1_definition,
)
from legal_ai.playbooks.grounding import FailClosedGroundingGate
from legal_ai.playbooks.repository import PlaybookRepository
from legal_ai.playbooks.service import PlaybookService


def _build_service(database_url: str) -> PlaybookService:
    engine = create_engine(database_url)
    return PlaybookService(
        playbook_repository=PlaybookRepository(engine),
        casework_repository=CaseworkRepository(engine),
        grounding_gate=FailClosedGroundingGate(),
    )


def seed_wa_motor_v1(*, database_url: str, actor: str = "cli:seed-wa-motor-v1") -> int:
    service = _build_service(database_url)
    result = service.seed_draft_definition(
        playbook_key=PLAYBOOK_KEY,
        version=PLAYBOOK_VERSION,
        display_name=DISPLAY_NAME,
        definition=wa_motor_property_damage_v1_definition(),
        actor=actor,
    )
    status = result.version.status.value
    if result.already_present:
        print(
            f"SEED_NOOP {PLAYBOOK_KEY} v{PLAYBOOK_VERSION} "
            f"status={status} sha256={result.version.content_sha256}"
        )
    else:
        print(
            f"SEED_CREATED {PLAYBOOK_KEY} v{PLAYBOOK_VERSION} "
            f"status={status} sha256={result.version.content_sha256} "
            f"id={result.version.playbook_version_id}"
        )
    if status != "DRAFT":
        print("error: seed must remain DRAFT", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="legal_ai.playbooks.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    seed = sub.add_parser("seed-wa-motor-v1", help="Seed WA motor v1 as DRAFT (never activates)")
    seed.add_argument(
        "--actor",
        default="cli:seed-wa-motor-v1",
        help="ActorRef recorded on the draft seed",
    )
    args = parser.parse_args(argv)

    database_url = os.environ.get("DATABASE_URL") or os.environ.get("LEGAL_AI_DATABASE_URL")
    if not database_url:
        print("error: DATABASE_URL (or LEGAL_AI_DATABASE_URL) is required", file=sys.stderr)
        return 2

    if args.command == "seed-wa-motor-v1":
        return seed_wa_motor_v1(database_url=database_url, actor=args.actor)
    parser.error(f"unknown command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
