"""Seed CLI database targeting must be explicit and fail closed."""

from __future__ import annotations

import pytest

from legal_ai.playbooks import cli


def _capture_seed_call(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def fake_seed(*, database_url: str, actor: str = "cli:seed-wa-motor-v1") -> int:
        calls.append((database_url, actor))
        return 0

    monkeypatch.setattr(cli, "seed_wa_motor_v1", fake_seed)
    return calls


def test_namespaced_database_url_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    approved_url = "postgresql+psycopg://approved:test-only@localhost/legal_ai_test"
    monkeypatch.setenv("LEGAL_AI_DATABASE_URL", approved_url)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    calls = _capture_seed_call(monkeypatch)

    assert cli.main(["seed-wa-motor-v1", "--actor", "seed_actor"]) == 0
    assert calls == [(approved_url, "seed_actor")]


def test_generic_database_url_alone_is_rejected_without_disclosure(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    unapproved_url = "postgresql+psycopg://user:do-not-print@localhost/production"
    monkeypatch.delenv("LEGAL_AI_DATABASE_URL", raising=False)
    monkeypatch.setenv("DATABASE_URL", unapproved_url)
    calls = _capture_seed_call(monkeypatch)

    assert cli.main(["seed-wa-motor-v1"]) == 2
    assert calls == []
    captured = capsys.readouterr()
    assert "LEGAL_AI_DATABASE_URL" in captured.err
    assert unapproved_url not in captured.out
    assert unapproved_url not in captured.err
    assert "do-not-print" not in captured.out
    assert "do-not-print" not in captured.err


def test_missing_approved_database_configuration_fails_before_seed(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("LEGAL_AI_DATABASE_URL", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    calls = _capture_seed_call(monkeypatch)

    assert cli.main(["seed-wa-motor-v1"]) == 2
    assert calls == []
    assert "LEGAL_AI_DATABASE_URL" in capsys.readouterr().err
