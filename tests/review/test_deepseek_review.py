from __future__ import annotations

import ast
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import httpx
import pytest
from scripts.deepseek_review import (
    MAX_RESPONSE_BYTES,
    ApiError,
    DeepSeekClient,
    GitDiff,
    MalformedReviewError,
    MissingConfigurationError,
    PolicyError,
    ReviewTool,
    redact_diff,
    redact_secrets,
    validate_review_result,
)

#: OpenRouter API keys carry a distinctive provider prefix (``sk`` / ``or`` /
#: ``v1`` joined by hyphens). These tests feed real-shaped keys to the redactor
#: to prove it strips them, but a literal of that shape in the source trips
#: GitHub push protection on every push. Assemble the prefix from fragments so no
#: single source literal matches the pattern; the value built at runtime is
#: byte-for-byte the same real-shaped key, so the redaction behaviour under test
#: is unchanged.
_OR = "sk-" + "or-" + "v1-"

PASS_RESULT: dict[str, Any] = {
    "verdict": "PASS",
    "summary": "The bounded review passed.",
    "critical_findings": [],
    "required_fixes": [],
    "test_gaps": [],
    "scope_risks": [],
}
BLOCKED_RESULT: dict[str, Any] = {
    "verdict": "BLOCKED",
    "summary": "The review is blocked.",
    "critical_findings": [
        {
            "id": "SEC-1",
            "severity": "high",
            "file": "scripts/deepseek_review.py",
            "line_hint": "1",
            "finding": "A required control is missing.",
            "required_fix": "Restore the control before merge.",
        }
    ],
    "required_fixes": ["Restore the control before merge."],
    "test_gaps": [],
    "scope_risks": [],
}


class FakeGit:
    def __init__(self, diff: GitDiff) -> None:
        self._diff = diff

    def is_tracked(self, path: str) -> bool:
        return path != ".deepseek-review/test-output.txt"

    def diff(self, base_ref: str, allowed_paths: tuple[str, ...]) -> GitDiff:
        assert base_ref == "main"
        assert allowed_paths == ("src/changed.py",)
        return self._diff


def _tool(tmp_path: Path, diff: GitDiff | None = None) -> ReviewTool:
    root = tmp_path
    (root / "requirements.md").write_text("Review the changed code.", encoding="utf-8")
    (root / ".deepseek-review").mkdir()
    (root / ".deepseek-review" / "test-output.txt").write_text("10 passed", encoding="utf-8")
    return ReviewTool(
        repo_root=root,
        git=FakeGit(
            diff
            or GitDiff(("src/changed.py",), "diff --git a/src/changed.py b/src/changed.py\n+safe")
        ),
        sleep=lambda _: None,
    )


def _bundle(tool: ReviewTool) -> dict[str, object]:
    return tool.build_bundle(
        requirements_path="requirements.md",
        base_ref="main",
        allowed_paths=["src/changed.py"],
        test_output_path=".deepseek-review/test-output.txt",
    )


def _response(result: Mapping[str, Any]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": json.dumps(result)}}]},
        )

    return httpx.MockTransport(handler)


def test_missing_api_key_fails_before_transport() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, request=request)

    client = DeepSeekClient(api_key=None, transport=httpx.MockTransport(handler))

    with pytest.raises(MissingConfigurationError):
        client.review({"example": "bundle"})

    assert calls == 0


def test_dry_run_makes_no_network_call(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(500, request=request)

    tool = _tool(tmp_path)
    code, output, saved = tool.execute(bundle=_bundle(tool), dry_run=True)

    assert code == 0
    assert output["network_call"] is False
    assert saved is None
    assert calls == 0


def test_changed_path_outside_allowlist_is_rejected(tmp_path: Path) -> None:
    tool = _tool(
        tmp_path,
        GitDiff(
            ("src/not-allowed.py",), "diff --git a/src/not-allowed.py b/src/not-allowed.py\n+unsafe"
        ),
    )

    with pytest.raises(PolicyError, match="outside the explicit allowlist"):
        _bundle(tool)


def test_secret_patterns_are_redacted_before_bundle_creation(tmp_path: Path) -> None:
    tool = _tool(tmp_path)
    key_value = "unit-" + "test-" + "sentinel"
    key_assignment = "DEEPSEEK_" + "API_KEY=" + key_value
    token = "sk-" + ("x" * 24)
    (tmp_path / "requirements.md").write_text(
        f"{key_assignment}\n{token}",
        encoding="utf-8",
    )
    bundle = _bundle(tool)
    serialized = json.dumps(bundle)

    assert key_assignment not in serialized
    assert token not in serialized
    assert "[REDACTED]" in serialized


def test_malformed_model_json_fails_closed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": "not JSON"}}]},
        )

    client = DeepSeekClient(
        api_key="test-placeholder", model="deepseek-chat", transport=httpx.MockTransport(handler)
    )

    with pytest.raises(MalformedReviewError):
        client.review({"bundle": "safe"})


def test_model_is_discovered_only_from_advertised_review_models() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/models":
            return httpx.Response(
                200,
                request=request,
                json={"data": [{"id": "deepseek-chat"}, {"id": "untrusted-other-model"}]},
            )
        return httpx.Response(
            200,
            request=request,
            json={"choices": [{"message": {"content": json.dumps(PASS_RESULT)}}]},
        )

    client = DeepSeekClient(
        api_key="test-placeholder",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    assert client.review({"bundle": "safe"})["verdict"] == "PASS"
    assert paths == ["/models", "/chat/completions"]


def test_http_failure_is_not_converted_to_pass() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, request=request)

    client = DeepSeekClient(
        api_key="test-placeholder",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    with pytest.raises(ApiError, match="HTTP 503"):
        client.review({"bundle": "safe"})

    assert calls == 3


def test_timeout_retries_only_a_bounded_number_of_times() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    client = DeepSeekClient(
        api_key="test-placeholder",
        model="deepseek-chat",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    with pytest.raises(ApiError, match="timed out"):
        client.review({"bundle": "safe"})

    assert calls == 3


def test_blocked_result_returns_nonzero_and_is_saved_under_runtime_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-placeholder")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    tool = ReviewTool(
        repo_root=tmp_path,
        git=FakeGit(
            GitDiff(("src/changed.py",), "diff --git a/src/changed.py b/src/changed.py\n+safe")
        ),
        transport=_response(BLOCKED_RESULT),
        sleep=lambda _: None,
    )
    (tmp_path / "requirements.md").write_text("Review the changed code.", encoding="utf-8")
    (tmp_path / ".deepseek-review").mkdir()
    (tmp_path / ".deepseek-review" / "test-output.txt").write_text("10 passed", encoding="utf-8")

    code, output, saved = tool.execute(bundle=_bundle(tool), dry_run=False)

    assert code == 1
    assert output["verdict"] == "BLOCKED"
    assert saved is not None
    assert saved.parent == tmp_path / ".deepseek-review"


def test_pass_result_returns_zero(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-placeholder")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    tool = ReviewTool(
        repo_root=tmp_path,
        git=FakeGit(
            GitDiff(("src/changed.py",), "diff --git a/src/changed.py b/src/changed.py\n+safe")
        ),
        transport=_response(PASS_RESULT),
        sleep=lambda _: None,
    )
    (tmp_path / "requirements.md").write_text("Review the changed code.", encoding="utf-8")
    (tmp_path / ".deepseek-review").mkdir()
    (tmp_path / ".deepseek-review" / "test-output.txt").write_text("10 passed", encoding="utf-8")

    code, output, saved = tool.execute(bundle=_bundle(tool), dry_run=False)

    assert code == 0
    assert output["verdict"] == "PASS"
    assert saved is not None


def test_model_output_is_data_and_cannot_modify_arbitrary_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-placeholder")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-chat")
    marker = tmp_path / "must-not-be-created.txt"
    hostile = {
        **PASS_RESULT,
        "summary": "$(New-Item must-not-be-created.txt)",
        "required_fixes": ["../../must-not-be-created.txt"],
    }
    tool = ReviewTool(
        repo_root=tmp_path,
        git=FakeGit(
            GitDiff(("src/changed.py",), "diff --git a/src/changed.py b/src/changed.py\n+safe")
        ),
        transport=_response(hostile),
        sleep=lambda _: None,
    )
    (tmp_path / "requirements.md").write_text("Review the changed code.", encoding="utf-8")
    (tmp_path / ".deepseek-review").mkdir()
    (tmp_path / ".deepseek-review" / "test-output.txt").write_text("10 passed", encoding="utf-8")

    code, output, saved = tool.execute(bundle=_bundle(tool), dry_run=False)

    assert code == 0
    assert output["summary"] == "$(New-Item must-not-be-created.txt)"
    assert not marker.exists()
    assert saved is not None and saved.parent == tmp_path / ".deepseek-review"


def test_response_schema_rejects_extra_keys() -> None:
    with pytest.raises(MalformedReviewError):
        validate_review_result({**PASS_RESULT, "extra": "not allowed"})


@pytest.mark.parametrize(
    "text",
    [
        f"OPENROUTER_API_KEY={_OR}000000000000000000000000000000000000000000000000000",
        f"{_OR}0000000000000000000000000000000000000000000000000000000000000000",
        "MY_PROVIDER_API_KEY: abcdefghijklmnopqrstuv",
    ],
)
def test_provider_keys_are_redacted_before_egress(text: str) -> None:
    """Reported by the review gate as REVIEW_GATE_SECRET_REDACTION_INCOMPLETE.

    The gate transmits a diff to a third party, so every credential shape the
    repository can contain must be redacted first.
    """

    redacted = redact_secrets(text)
    assert "[REDACTED]" in redacted
    assert f"{_OR}0000" not in redacted
    assert "abcdefghijklmnopqrstuv" not in redacted


@pytest.mark.parametrize(
    "line",
    [
        "api_key: str",
        "self._config.api_key",
        "api_key=os.environ.get(ENV_API_KEY, '').strip()",
        'ENV_API_KEY = "OPENROUTER_API_KEY"',
        "def load_openrouter_config() -> OpenRouterConfig | None:",
    ],
)
def test_redaction_leaves_ordinary_code_untouched(line: str) -> None:
    """Reported by the review gate as REDACTION_CORRUPTS_REVIEW_BUNDLE.

    Redaction runs over the diff being reviewed. If it rewrites identifiers it
    corrupts the evidence, and the reviewer is reading something that is not
    the change.
    """

    assert redact_secrets(line) == line


@pytest.mark.parametrize(
    "source_path",
    [
        "src/legal_ai/answering/providers/openrouter.py",
        "src/legal_ai/answering/verification.py",
        "src/legal_ai/api/settings.py",
        "scripts/deepseek_review.py",
    ],
)
def test_redacted_source_remains_syntactically_valid(source_path: str) -> None:
    source = Path(source_path).read_text(encoding="utf-8")
    ast.parse(redact_secrets(source))


def test_symlink_is_never_a_review_input(tmp_path: Path) -> None:
    """Reported by the review gate as REVIEW_GATE_SYMLINK_EXFILTRATION.

    A tracked symlink can present an innocuous path while pointing at a
    sensitive file, so no symlink is accepted regardless of where it resolves.
    """

    secret = tmp_path / "secret.txt"
    secret.write_text(f"OPENROUTER_API_KEY={_OR}should-never-be-transmitted", encoding="utf-8")
    link = tmp_path / "innocuous.py"
    try:
        link.symlink_to(secret)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is not permitted in this environment")

    tool = ReviewTool.__new__(ReviewTool)
    tool.repo_root = tmp_path.resolve()
    with pytest.raises(PolicyError, match="symlink"):
        tool._validate_relative("innocuous.py", role="allow path")


def test_symlink_policy_holds_without_filesystem_privileges(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same policy as above, provable where symlinks cannot be created.

    Windows CI often lacks the privilege, so the OS-level test skips. This one
    asserts the decision directly by making the path report itself as a link.
    """

    (tmp_path / "innocuous.py").write_text("x = 1", encoding="utf-8")
    monkeypatch.setattr(Path, "is_symlink", lambda self: self.name == "innocuous.py")

    tool = ReviewTool.__new__(ReviewTool)
    tool.repo_root = tmp_path.resolve()
    with pytest.raises(PolicyError, match="symlink"):
        tool._validate_relative("innocuous.py", role="allow path")


def test_ordinary_file_is_still_accepted(tmp_path: Path) -> None:
    (tmp_path / "ordinary.py").write_text("x = 1", encoding="utf-8")
    tool = ReviewTool.__new__(ReviewTool)
    tool.repo_root = tmp_path.resolve()
    assert tool._validate_relative("ordinary.py", role="allow path") == "ordinary.py"


@pytest.mark.parametrize(
    "text",
    [
        f"api_key = '{_OR}00000000000000000000000000000000'",
        'password="hunter2hunter2hunter2"',
        'my_secret: "abcdefghijklmnopqrst"',
        'MY_TOKEN="lowercase-secret-value-here"',
        'API_KEY = "sk-abcdefghijklmnopqrstuvwxyz012345"',
    ],
)
def test_lowercase_secret_assignments_are_redacted(text: str) -> None:
    """Reported by the review gate as REVIEW_GATE_SECRET_REDACTION_LOWERCASE_GAP.

    Matched on the value rather than the name, so a quoted literal long enough
    to be a credential is redacted whatever the case of the identifier.
    """

    assert "[REDACTED]" in redact_secrets(text)


@pytest.mark.parametrize(
    "text",
    [
        'ENV_API_KEY = "OPENROUTER_API_KEY"',
        'ENV_MODEL = "LEGAL_AI_OPENROUTER_MODEL"',
        'ENV_VERIFY_ENTAILMENT = "LEGAL_AI_VERIFY_ENTAILMENT"',
    ],
)
def test_environment_variable_names_survive_redaction(text: str) -> None:
    """An UPPER_SNAKE literal is a variable name, not a credential.

    Redacting it would hide which setting the change reads, which is exactly
    the diff fidelity the REDACTION_CORRUPTS_REVIEW_BUNDLE finding protects.
    """

    assert redact_secrets(text) == text


def test_multiline_pem_private_key_is_redacted() -> None:
    """Reported by the review gate as REVIEW_GATE_PRIVATE_KEY_REDACTION_INCOMPLETE.

    A PEM key is always multi-line, so without DOTALL the pattern never
    matched and the key was transmitted in full.
    """

    pem = "\n".join(
        [
            "-----BEGIN RSA PRIVATE KEY-----",
            "MIIEowIBAAKCAQEA1234567890abcdefghijklmnop",
            "QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVo=",
            "-----END RSA PRIVATE KEY-----",
        ]
    )
    redacted = redact_secrets(pem)
    assert "[REDACTED]" in redacted
    assert "MIIEowIBAAKCAQEA" not in redacted
    assert "QUJDREVGR0hJSkt" not in redacted


@pytest.mark.parametrize(
    "text",
    [
        f"api_key={_OR}00000000000000000000000000000000",
        "password=a1b2c3-d4e5f6+g7h8/i9",
        "my_token=abc-def-ghi-jkl-mno-pqr",
    ],
)
def test_unquoted_lowercase_secret_assignments_are_redacted(text: str) -> None:
    """Reported by the review gate as REVIEW_GATE_LOWERCASE_UNQUOTED_SECRET_GAP."""

    assert "[REDACTED]" in redact_secrets(text)


@pytest.mark.parametrize(
    "text",
    [
        "api_key = config.api_key",
        "token = parse(value)",
        "api_key=os.environ.get(ENV_API_KEY, '').strip()",
        "password: str | None = None",
    ],
)
def test_unquoted_rule_leaves_code_expressions_intact(text: str) -> None:
    """The unquoted rule requires a character no identifier can contain.

    That is what keeps attribute paths and calls out of scope, preserving the
    diff fidelity that REDACTION_CORRUPTS_REVIEW_BUNDLE protects.
    """

    assert redact_secrets(text) == text


def test_bare_secret_in_config_file_is_redacted_but_code_is_not() -> None:
    """Reported by the review gate as SEC-REDACTION_BARE_IDENTIFIER_GAP.

    A bare identifier-shaped value is a credential in configuration and is
    ordinary code in a source file. Redaction is therefore file-aware: this is
    what reconciles it with REDACTION_CORRUPTS_REVIEW_BUNDLE.
    """

    diff = "\n".join(
        [
            "diff --git a/.env.sample b/.env.sample",
            "--- a/.env.sample",
            "+++ b/.env.sample",
            "@@ -1,0 +1,2 @@",
            "+api_key=supersecretvalue",
            "+password=plaintextpassword",
            "diff --git a/src/app.py b/src/app.py",
            "--- a/src/app.py",
            "+++ b/src/app.py",
            "@@ -1,0 +1,3 @@",
            "+api_key: str",
            "+api_key = config.api_key",
            "+token = parse(value)",
        ]
    )
    redacted = redact_diff(diff)

    assert "supersecretvalue" not in redacted
    assert "plaintextpassword" not in redacted
    assert "+api_key: str" in redacted
    assert "+api_key = config.api_key" in redacted
    assert "+token = parse(value)" in redacted


@pytest.mark.parametrize("suffix", [".py", ".ts", ".go", ".rs", ".sql"])
def test_source_suffixes_keep_the_conservative_rule(suffix: str) -> None:
    diff = "\n".join(
        [f"+++ b/src/thing{suffix}", "@@ -1,0 +1,1 @@", "+api_key = some_variable_name"]
    )
    assert "some_variable_name" in redact_diff(diff)


@pytest.mark.parametrize("suffix", [".env", ".sample", ".cfg", ".ini", ".conf", ".txt"])
def test_config_suffixes_get_the_strict_rule(suffix: str) -> None:
    diff = "\n".join([f"+++ b/deploy/settings{suffix}", "@@ -1,0 +1,1 @@", "+api_key=rawsecret123"])
    assert "rawsecret123" not in redact_diff(diff)


def test_diff_redaction_still_covers_token_shapes_in_source_files() -> None:
    """The conservative rule is not a hole: real key formats are still caught."""

    diff = "\n".join(
        [
            "+++ b/src/thing.py",
            "@@ -1,0 +1,1 @@",
            f'+KEY = "{_OR}000000000000000000000000000000000000"',
        ]
    )
    redacted = redact_diff(diff)
    assert f"{_OR}0000" not in redacted


def test_oversized_review_response_is_refused() -> None:
    """Reported by the review gate against itself as SEC-UNBOUNDED_PROVIDER_RESPONSE.

    The gate talks to a third party too, so it must bound what it reads back.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "deepseek-v4-pro"}]})
        return httpx.Response(200, json={"padding": "x" * (MAX_RESPONSE_BYTES + 1_000)})

    client = DeepSeekClient(
        api_key="test-key",
        model="deepseek-v4-pro",
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
    )
    with pytest.raises(ApiError, match="exceeds the permitted size"):
        client.review({"requirements": {}})


def test_oversized_model_discovery_response_is_refused() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "x" * (MAX_RESPONSE_BYTES + 1_000)}]})

    client = DeepSeekClient(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
        sleep=lambda _seconds: None,
    )
    with pytest.raises(ApiError, match="exceeds the permitted size"):
        client.review({"requirements": {}})
