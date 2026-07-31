#!/usr/bin/env python3
"""Temporary-repository tests for commit-linked Codex transcript provenance."""

from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import codex_transcript_provenance as provenance  # noqa: E402
from ci_impact import CONFIG_PATH, ImpactPolicy  # noqa: E402


class ProvenanceRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.sessions = self.root / "sessions"
        self.repo.mkdir()
        self.sessions.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("config", "user.name", "Transcript Tests")
        (self.repo / "base.txt").write_text("base\n", encoding="utf-8")
        self.git("add", "base.txt")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.thread = "019f-test-thread"
        self._nonce_index = 0

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            text=True,
            capture_output=True,
            check=check,
        )

    def write_session(
        self,
        *,
        cwd: Path | None = None,
        messages: list[tuple[str, str]] | None = None,
        thread: str | None = None,
    ) -> Path:
        thread = thread or self.thread
        path = self.sessions / f"rollout-{thread}.jsonl"
        records: list[dict[str, object]] = [
            {
                "timestamp": "2026-07-30T20:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": thread,
                    "timestamp": "2026-07-30T20:00:00Z",
                    "cwd": str(cwd or self.repo),
                },
            }
        ]
        for index, (role, text) in enumerate(
            messages or [("user", "Implement it"), ("assistant", "Done")]
        ):
            records.append(
                {
                    "timestamp": f"2026-07-30T20:00:{index + 1:02d}Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": role,
                        "content": [{"type": "input_text", "text": text}],
                    },
                }
            )
        path.write_text(
            "".join(json.dumps(record) + "\n" for record in records), encoding="utf-8"
        )
        return path

    def next_nonce(self) -> str:
        self._nonce_index += 1
        return hashlib.sha256(f"nonce-{self._nonce_index}".encode()).hexdigest()

    def capture(
        self,
        *,
        amend: bool = False,
        nonce: str | None = None,
        scope_start: str = "2026-07-30T20:00:00Z",
    ) -> str:
        return provenance.capture(
            self.repo,
            self.thread,
            self.sessions,
            invocation_nonce=nonce or self.next_nonce(),
            scope_start=scope_start,
            amend=amend,
        )

    def commit_capture(self, subject: str = "codex", *, amend: bool = False) -> str:
        nonce = self.next_nonce()
        path = self.capture(amend=amend, nonce=nonce)
        message = self.root / "message"
        message.write_text(subject + "\n", encoding="utf-8")
        provenance.prepare_message(self.repo, message, nonce)
        provenance.validate_message(
            self.repo,
            message,
            invocation_nonce=nonce,
            require_state=True,
        )
        args = ["commit", "--no-verify", "-F", str(message)]
        if amend:
            args.insert(1, "--amend")
        self.git(*args)
        provenance.clear_state(self.repo, nonce, cleanup_artifact=False)
        return path

    def test_01_no_session_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "no exact Codex session"
        ):
            self.capture()

    def test_02_sibling_worktree_is_same_repository(self) -> None:
        sibling = self.root / "sibling"
        self.git("worktree", "add", "-q", "-b", "sibling", str(sibling))
        self.write_session(cwd=sibling)
        self.assertTrue((self.repo / self.capture()).is_file())

    def test_03_foreign_repository_is_rejected(self) -> None:
        foreign = self.root / "foreign"
        subprocess.run(["git", "init", "-q", foreign], check=True)
        self.write_session(cwd=foreign)
        with self.assertRaisesRegex(provenance.ProvenanceError, "no eligible"):
            self.capture()

    def test_03b_mixed_cwd_session_keeps_only_same_repository_records(self) -> None:
        sibling = self.root / "mixed-sibling"
        foreign = self.root / "mixed-foreign"
        self.git("worktree", "add", "-q", "-b", "mixed-sibling", str(sibling))
        subprocess.run(["git", "init", "-q", foreign], check=True)
        records = [
            {
                "timestamp": "2026-07-30T20:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": self.thread,
                    "timestamp": "2026-07-30T20:00:00Z",
                    "cwd": str(self.repo),
                },
            }
        ]
        for index, (cwd, text) in enumerate(
            (
                (self.repo, "primary record"),
                (foreign, "foreign record must disappear"),
                (sibling, "sibling record"),
                (foreign, "later foreign record must disappear"),
            ),
            start=1,
        ):
            records.extend(
                [
                    {
                        "timestamp": f"2026-07-30T20:00:{index:02d}Z",
                        "type": "turn_context",
                        "payload": {"cwd": str(cwd), "turn_id": str(index)},
                    },
                    {
                        "timestamp": f"2026-07-30T20:01:{index:02d}Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"text": text}],
                        },
                    },
                ]
            )
        session = self.sessions / f"rollout-{self.thread}.jsonl"
        session.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        text = "\n".join(message["text"] for message in payload["messages"])
        self.assertIn("primary record", text)
        self.assertIn("sibling record", text)
        self.assertNotIn("foreign record", text)

    def test_03c_explicit_scope_excludes_earlier_same_repo_turns(self) -> None:
        self.write_session(
            messages=[
                ("user", "Unrelated earlier same-repository discussion"),
                ("user", "Implement the commit-relevant change"),
                ("assistant", "Commit-relevant implementation complete"),
            ]
        )
        artifact = self.repo / self.capture(scope_start="2026-07-30T20:00:02Z")
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        texts = [message["text"] for message in payload["messages"]]
        self.assertEqual(
            texts,
            [
                "Implement the commit-relevant change",
                "Commit-relevant implementation complete",
            ],
        )
        self.assertEqual(
            payload["capture_scope"],
            {
                "kind": "timestamp-start",
                "start_timestamp": "2026-07-30T20:00:02.000000Z",
            },
        )
        payload["capture_scope"]["start_timestamp"] = "2026-07-30T20:00:01.000000Z"
        unhashed = dict(payload)
        unhashed.pop("canonical_payload_hash")
        payload["canonical_payload_hash"] = hashlib.sha256(
            provenance._canonical_json(unhashed)
        ).hexdigest()
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "snapshot identity hash mismatch"
        ):
            provenance._validate_payload(
                provenance._canonical_json(payload),
                str(artifact.relative_to(self.repo)),
            )

    def test_03d_embedded_parent_metadata_does_not_replace_session_identity(
        self,
    ) -> None:
        session = self.write_session()
        records = session.read_text(encoding="utf-8").splitlines()
        records.insert(
            1,
            json.dumps(
                {
                    "timestamp": "2026-07-30T20:00:00.500Z",
                    "type": "session_meta",
                    "payload": {
                        "id": "019f-parent-thread",
                        "timestamp": "2026-07-30T19:00:00Z",
                        "cwd": str(self.repo),
                    },
                }
            ),
        )
        session.write_text("\n".join(records) + "\n", encoding="utf-8")
        artifact = self.repo / self.capture()
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["thread_hash"],
            hashlib.sha256(self.thread.encode()).hexdigest()[:12],
        )

    def test_04_injected_context_paths_and_secrets_are_filtered(self) -> None:
        self.write_session(
            messages=[
                ("user", f"Use {self.repo}/file.py token=supersecret"),
                ("assistant", "Implemented"),
            ]
        )
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        text = "\n".join(message["text"] for message in payload["messages"])
        self.assertNotIn(str(self.repo), text)
        self.assertNotIn("supersecret", text)
        self.assertIn("<redacted:repo-path>/file.py", text)
        self.assertIn("<redacted:env-secret>", text)

    def test_04b_pattern_sanitizer_covers_reviewed_sensitive_classes(self) -> None:
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue123"
        private_key = (
            "-----BEGIN PRIVATE KEY-----\nABCDEF0123456789secret\n"
            "-----END PRIVATE KEY-----"
        )
        sensitive = " ".join(
            (
                "AWS_SECRET_ACCESS_KEY=AbCdEf1234567890+/secret",
                "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuv",
                "GITHUB_TOKEN=github_pat_abcdefghijklmnopqrstuv",
                "SLACK_BOT_TOKEN=xoxb-123456789012-abcdefghijkl",
                "Authorization: Bearer bearerTokenValue1234567890",
                "https://alice:password@example.com/private",
                jwt,
                private_key,
                "person@example.com",
                "019f97dd-3be6-7923-af1b-0d871a480744",
                "Aa9_7kLmN2pQr5sTu8vWx1yZ",
                "/mnt/private/cache/file.bin",
                "/tmp/runtime.sock",
                "C:\\Users\\alice\\secret.txt",
                "0123456789abcdef0123456789abcdef01234567",
            )
        )
        self.write_session(messages=[("user", sensitive), ("assistant", "safe")])
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        serialized = json.dumps(payload, sort_keys=True)
        for forbidden in (
            "AbCdEf1234567890",
            "abcdefghijklmnopqrstuv",
            "bearerTokenValue",
            "alice:password",
            "signaturevalue",
            "PRIVATE KEY",
            "person@example.com",
            "019f97dd",
            "Aa9_7kLm",
            "/mnt/private",
            "/tmp/runtime",
            "C:\\Users",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertNotIn("0123456789abcdef0123456789abcdef01234567", serialized)
        self.assertGreater(payload["redactions"]["replacement_count"], 10)

    def test_04ba_keyed_secrets_redact_complete_values_and_json_assignments(
        self,
    ) -> None:
        sensitive = "\n".join(
            (
                'PASSWORD="correct horse battery staple"; '
                '{"OPENAI_API_KEY":"sk live secret with spaces"}',
                "TOKEN=unquoted-secret-value",
                r"SECRET=escaped\ multi\ word",
                'ACCESS_TOKEN="quoted secret"suffix-secret',
                'AUTH_TOKEN=prefix" mixed secret"suffix',
                'API_KEY="quoted',
                "multiline",
                'secret"',
                "GH_TOKEN=line\\",
                "continued",
            )
        )
        self.write_session(messages=[("user", sensitive), ("assistant", "safe")])
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        serialized = json.dumps(payload, sort_keys=True)
        for forbidden in (
            "correct horse battery staple",
            "sk live secret with spaces",
            "unquoted-secret-value",
            r"escaped\ multi\ word",
            r"multi\ word",
            "quoted secret",
            "suffix-secret",
            "mixed secret",
            "multiline",
            "continued",
        ):
            self.assertNotIn(forbidden, serialized)
        self.assertGreaterEqual(payload["redactions"]["classes"]["env-secret"], 8)

    def test_04bb_malformed_keyed_secret_values_fail_before_substitution(
        self,
    ) -> None:
        malformed = (
            'PASSWORD="unterminated secret phrase',
            "PASSWORD='unterminated secret phrase",
            'PASSWORD=prefix" mixed secret',
            "PASSWORD=dangling\\",
            'PASSWORD="quoted multiline\nwithout closure',
            'PASSWORD="line continuation\\\nwithout closure',
            'PASSWORD = \n  "indented without closure',
        )
        never_matches = re.compile(r"(?!x)x")
        with mock.patch.object(
            provenance,
            "KEYED_SECRET_RESIDUAL_PATTERN",
            never_matches,
        ):
            for value in malformed:
                with self.subTest(value=value):
                    with self.assertRaisesRegex(
                        provenance.ProvenanceError,
                        "unterminated quote|incomplete escape",
                    ):
                        provenance._redact(value, ())

        self.write_session(
            messages=[
                ("user", 'PASSWORD = \r\n  "unterminated secret phrase'),
                ("assistant", "safe"),
            ]
        )
        with self.assertRaisesRegex(provenance.ProvenanceError, "unterminated quote"):
            self.capture()

    def test_04bc_multiline_key_separator_whitespace_is_fully_redacted(
        self,
    ) -> None:
        sensitive = (
            '{"PASSWORD":\n  "hunter2"}',
            '{"OPENAI_API_KEY"\r\n:\r\n  "hunter3"}',
            'ACCESS_TOKEN \n = \n  "secret phrase"',
        )
        for value in sensitive:
            with self.subTest(value=value):
                redacted, counts = provenance._redact(value, ())
                self.assertEqual(counts["env-secret"], 1)
                self.assertNotIn("hunter", redacted)
                self.assertNotIn("secret phrase", redacted)
                with self.assertRaisesRegex(provenance.ProvenanceError, "env-secret"):
                    provenance._residual_scan(value)

        self.write_session(
            messages=[
                *(("user", value) for value in sensitive),
                ("assistant", "safe"),
            ]
        )
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        serialized = json.dumps(payload, sort_keys=True)
        for forbidden in ("hunter2", "hunter3", "secret phrase"):
            self.assertNotIn(forbidden, serialized)

    def test_04c_unterminated_reserved_injected_message_is_excluded(self) -> None:
        self.write_session(
            messages=[("user", "<recommended_plugins>unterminated"), ("assistant", "x")]
        )
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        self.assertEqual(
            [(message["role"], message["text"]) for message in payload["messages"]],
            [("assistant", "x")],
        )

    def test_04d_duplicate_keys_skip_the_entire_jsonl_record(self) -> None:
        session = self.sessions / f"rollout-{self.thread}.jsonl"
        meta = json.dumps(
            {
                "timestamp": "2026-07-30T20:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": self.thread,
                    "timestamp": "2026-07-30T20:00:00Z",
                    "cwd": str(self.repo),
                },
            }
        )
        safe = json.dumps(
            {
                "timestamp": "2026-07-30T20:00:05Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"text": "safe record"}],
                },
            }
        )
        duplicate_records = [
            (
                '{"timestamp":"2026-07-30T20:00:01Z",'
                '"type":"ignored","type":"response_item",'
                '"payload":{"type":"message","role":"user",'
                '"content":[{"text":"duplicate top level"}]}}'
            ),
            (
                '{"timestamp":"2026-07-30T20:00:02Z","type":"response_item",'
                '"payload":{"type":"ignored","type":"message","role":"user",'
                '"content":[{"text":"duplicate payload type"}]}}'
            ),
            (
                '{"timestamp":"2026-07-30T20:00:03Z","type":"response_item",'
                '"payload":{"type":"message","role":"assistant","role":"user",'
                '"content":[{"text":"duplicate role"}]}}'
            ),
            (
                '{"timestamp":"2026-07-30T20:00:04Z","type":"response_item",'
                '"payload":{"type":"message","role":"user",'
                '"content":[{"text":"first content"}],'
                '"content":[{"text":"duplicate content"}]}}'
            ),
        ]
        session.write_text(
            "\n".join([meta, *duplicate_records, safe]) + "\n",
            encoding="utf-8",
        )
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        self.assertEqual(
            [(message["role"], message["text"]) for message in payload["messages"]],
            [("assistant", "safe record")],
        )

    def test_04e_reserved_tag_scanner_strips_only_balanced_structures(self) -> None:
        self.write_session(
            messages=[
                (
                    "user",
                    (
                        "keep before "
                        '<Recommended_Plugins source="hook">'
                        "outer <IDENTITY level='nested'>secret</IDENTITY> hidden"
                        "</recommended_plugins> keep after"
                    ),
                ),
                (
                    "assistant",
                    "same <constraints>one<constraints>two</constraints></constraints> end",
                ),
                ("user", "<developer /> self closing"),
                ("user", "<constraints>bad</identity>"),
                ("user", "<<recommended_plugins>>bad</recommended_plugins>"),
                ("user", "<!identity>bad</identity>"),
                ("user", "<recom mended_plugins>split</recommended_plugins>"),
                (
                    "user",
                    "<recommended_plugins flag>bad attributes</recommended_plugins>",
                ),
                ("user", '<identity data="</identity>">confused</identity>'),
                ("user", "<![CDATA[<identity>secret]]>"),
                ("user", "<foo <identity>>secret"),
                ("user", "<x a=<identity>>secret"),
                ("user", "<!-- <identity>secret -->"),
                (
                    "user",
                    '<widget data="<identity>secret</identity>">x</widget>',
                ),
                (
                    "assistant",
                    (
                        'ordinary <widget recommended_plugins="literal">angle</widget> '
                        "and <vector<T>> syntax"
                    ),
                ),
            ]
        )
        payload = json.loads((self.repo / self.capture()).read_text(encoding="utf-8"))
        messages = [message["text"] for message in payload["messages"]]
        self.assertEqual(
            messages,
            [
                "keep before  keep after",
                "same  end",
                (
                    'ordinary <widget recommended_plugins="literal">angle</widget> '
                    "and <vector<T>> syntax"
                ),
            ],
        )

    def test_05_repeated_commits_get_distinct_session_snapshots(self) -> None:
        self.write_session()
        first = self.commit_capture("first codex")
        (self.repo / "second.txt").write_text("second\n", encoding="utf-8")
        self.git("add", "second.txt")
        second = self.commit_capture("second codex")
        self.assertNotEqual(first, second)
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_06_retry_replaces_stale_generated_artifact(self) -> None:
        session = self.write_session()
        nonce = self.next_nonce()
        first = self.capture(nonce=nonce)
        with session.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": "2026-07-30T20:01:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "user",
                            "content": [{"text": "new"}],
                        },
                    }
                )
                + "\n"
            )
        second = self.capture(nonce=nonce)
        self.assertNotEqual(first, second)
        self.assertFalse((self.repo / first).exists())
        self.assertEqual(
            self.git("diff", "--cached", "--name-only").stdout.splitlines(), [second]
        )

    def test_07_amend_replaces_artifact_without_range_deletion(self) -> None:
        session = self.write_session()
        first = self.commit_capture()
        with session.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": "2026-07-30T20:02:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"text": "amended"}],
                        },
                    }
                )
                + "\n"
            )
        second = self.commit_capture("codex amended", amend=True)
        self.assertNotEqual(first, second)
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_07b_invocation_state_rejects_stale_nonce_and_cleans_failure(self) -> None:
        self.write_session()
        nonce = self.next_nonce()
        artifact = self.capture(nonce=nonce)
        message = self.root / "stale-message"
        message.write_text("stale\n", encoding="utf-8")
        with self.assertRaisesRegex(provenance.ProvenanceError, "missing, stale"):
            provenance.prepare_message(self.repo, message, self.next_nonce())
        provenance.prepare_message(self.repo, message, nonce)
        with self.assertRaisesRegex(provenance.ProvenanceError, "missing, stale"):
            provenance.validate_message(
                self.repo,
                message,
                invocation_nonce=self.next_nonce(),
                require_state=True,
            )
        with self.assertRaisesRegex(provenance.ProvenanceError, "another invocation"):
            provenance.clear_state(self.repo, self.next_nonce(), cleanup_artifact=True)
        provenance.clear_state(self.repo, nonce, cleanup_artifact=True)
        self.assertFalse((self.repo / artifact).exists())
        self.assertFalse(provenance._state_path(self.repo).exists())

    def test_07ba_capture_state_rejects_non_object_json(self) -> None:
        provenance._state_path(self.repo).write_text("[]\n", encoding="utf-8")
        with self.assertRaisesRegex(provenance.ProvenanceError, "JSON object"):
            provenance._read_state(self.repo)

    def test_07bb_failed_amend_restores_prior_artifact_and_index(self) -> None:
        session = self.write_session()
        prior = self.commit_capture("prior")
        with session.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": "2026-07-31T00:10:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"text": "new amend state"}],
                        },
                    }
                )
                + "\n"
            )
        nonce = self.next_nonce()
        replacement = self.capture(amend=True, nonce=nonce)
        self.assertNotEqual(prior, replacement)
        provenance.clear_state(self.repo, nonce, cleanup_artifact=True)
        self.assertTrue((self.repo / prior).is_file())
        self.assertFalse((self.repo / replacement).exists())
        self.assertEqual(
            self.git(
                "diff",
                "--cached",
                "--name-only",
                "--",
                provenance.ARTIFACT_PREFIX,
            ).stdout,
            "",
        )

    def test_07c_initial_repository_snapshot_identity_has_no_head(self) -> None:
        repo = self.root / "initial"
        sessions = self.root / "initial-sessions"
        repo.mkdir()
        sessions.mkdir()
        subprocess.run(["git", "init", "-q", repo], check=True)
        thread = "019f-initial-thread"
        path = sessions / f"rollout-{thread}.jsonl"
        path.write_text(
            json.dumps(
                {
                    "timestamp": "2026-07-31T00:00:00Z",
                    "type": "session_meta",
                    "payload": {
                        "id": thread,
                        "timestamp": "2026-07-31T00:00:00Z",
                        "cwd": str(repo),
                    },
                }
            )
            + "\n"
            + json.dumps(
                {
                    "timestamp": "2026-07-31T00:00:01Z",
                    "type": "response_item",
                    "payload": {
                        "type": "message",
                        "role": "user",
                        "content": [{"text": "initial commit"}],
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )
        nonce = secrets.token_hex(32)
        artifact = provenance.capture(
            repo,
            thread,
            sessions,
            invocation_nonce=nonce,
            scope_start="2026-07-31T00:00:00Z",
        )
        payload = json.loads((repo / artifact).read_text(encoding="utf-8"))
        self.assertIsNone(payload["pre_commit_head"])
        self.assertEqual(payload["commit_mode"], "commit")
        message = self.root / "initial-message"
        message.write_text("initial\n", encoding="utf-8")
        provenance.prepare_message(repo, message, nonce)
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.email", "tests@example.invalid"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "config", "user.name", "Transcript Tests"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo), "commit", "--no-verify", "-F", str(message)],
            check=True,
            capture_output=True,
        )
        provenance.validate_range(repo, "0" * 40, "HEAD")

    def test_08_capture_preserves_unrelated_staging(self) -> None:
        self.write_session()
        (self.repo / "owned.txt").write_text("owned\n", encoding="utf-8")
        self.git("add", "owned.txt")
        artifact = self.capture()
        self.assertEqual(
            set(self.git("diff", "--cached", "--name-only").stdout.splitlines()),
            {"owned.txt", artifact},
        )

    def test_09_human_commit_without_trailer_or_artifact_passes(self) -> None:
        (self.repo / "human.txt").write_text("human\n", encoding="utf-8")
        self.git("add", "human.txt")
        self.git("commit", "-qm", "human")
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_10_valid_pointer_schema_and_hashes_pass(self) -> None:
        self.write_session()
        path = self.commit_capture()
        self.assertIn(
            path, self.git("show", "--format=%B", "--no-patch", "HEAD").stdout
        )
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_11_malformed_or_duplicate_trailer_fails(self) -> None:
        self.write_session()
        nonce = self.next_nonce()
        self.capture(nonce=nonce)
        message = self.root / "message"
        message.write_text("x\n\nCodex-Transcript: malformed\n", encoding="utf-8")
        with self.assertRaisesRegex(provenance.ProvenanceError, "exactly one"):
            provenance.validate_message(self.repo, message)
        provenance.prepare_message(self.repo, message, nonce)
        valid_message = message.read_text(encoding="utf-8")
        bad_hash = re.sub(r"sha256=[0-9a-f]{64}", "sha256=" + "0" * 64, valid_message)
        message.write_text(bad_hash, encoding="utf-8")
        with self.assertRaisesRegex(provenance.ProvenanceError, "hash mismatch"):
            provenance.validate_message(self.repo, message)
        message.write_text(valid_message * 2, encoding="utf-8")
        with self.assertRaisesRegex(provenance.ProvenanceError, "exactly one"):
            provenance.validate_message(self.repo, message)
        artifact = self.repo / self.capture(nonce=nonce)
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        payload["schema"] = "invalid"
        artifact.write_text(json.dumps(payload) + "\n", encoding="utf-8")
        self.git("add", str(artifact.relative_to(self.repo)))
        digest = hashlib.sha256(artifact.read_bytes()).hexdigest()
        message.write_text(
            f"x\n\nCodex-Transcript: {artifact.relative_to(self.repo)} sha256={digest}\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(provenance.ProvenanceError, "schema or authority"):
            provenance.validate_message(self.repo, message)

    def test_11b_artifact_json_rejects_duplicates_and_noncanonical_bytes(self) -> None:
        self.write_session()
        path = self.capture()
        canonical = (self.repo / path).read_bytes()
        payload = json.loads(canonical)
        duplicate = canonical.replace(
            b'{"authority":',
            b'{"schema":"duplicate","authority":',
            1,
        )
        with self.assertRaisesRegex(provenance.ProvenanceError, "duplicate JSON key"):
            provenance._validate_payload(duplicate, path)
        reordered_payload = dict(reversed(list(payload.items())))
        cases = (
            json.dumps(reordered_payload, separators=(",", ":")).encode() + b"\n",
            json.dumps(payload, indent=2, sort_keys=True).encode() + b"\n",
            canonical + b" ",
            b"\xef\xbb\xbf" + canonical,
            b"\xff" + canonical,
        )
        for data in cases:
            with self.subTest(data=data[:20]):
                with self.assertRaisesRegex(
                    provenance.ProvenanceError, "canonical JSON|malformed"
                ):
                    provenance._validate_payload(data, path)

    def test_11c_final_canonical_artifact_scan_rejects_residual_secret(self) -> None:
        self.write_session()
        path = self.capture()
        payload = json.loads((self.repo / path).read_text(encoding="utf-8"))
        secret = "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuv"
        payload["messages"][0]["text"] = secret
        payload["messages"][0]["message_hash"] = hashlib.sha256(
            secret.encode()
        ).hexdigest()
        unhashed = dict(payload)
        unhashed.pop("canonical_payload_hash")
        payload["canonical_payload_hash"] = hashlib.sha256(
            provenance._canonical_json(unhashed)
        ).hexdigest()
        data = provenance._canonical_json(payload)
        with self.assertRaisesRegex(provenance.ProvenanceError, "env-secret"):
            provenance._validate_payload(data, path)

    def test_11ca_residual_scan_independently_rejects_keyed_assignments(self) -> None:
        residuals = (
            'PASSWORD="<redacted:env-secret> leaked suffix"',
            '{"OPENAI_API_KEY":"still visible"}',
            "TOKEN=unquoted residual words",
        )
        for residual in residuals:
            with self.subTest(residual=residual):
                with self.assertRaisesRegex(provenance.ProvenanceError, "env-secret"):
                    provenance._residual_scan(residual)

    def test_11d_final_artifact_scanner_rejects_reserved_syntax(self) -> None:
        self.write_session()
        path = self.capture()
        original = json.loads((self.repo / path).read_text(encoding="utf-8"))

        def artifact_with_text(text: str) -> bytes:
            payload = json.loads(json.dumps(original))
            payload["messages"][0]["text"] = text
            payload["messages"][0]["message_hash"] = hashlib.sha256(
                text.encode()
            ).hexdigest()
            payload.pop("canonical_payload_hash")
            payload["canonical_payload_hash"] = hashlib.sha256(
                provenance._canonical_json(payload)
            ).hexdigest()
            return provenance._canonical_json(payload)

        rejected = (
            '<Recommended_Plugins source="hook">x</recommended_plugins>',
            "<constraints>one<constraints>two</constraints></constraints>",
            "<developer />",
            "<constraints>bad</identity>",
            "<<recommended_plugins>>bad</recommended_plugins>",
            "<!identity>bad</identity>",
            "<recom mended_plugins>split</recommended_plugins>",
            "<recommended_plugins flag>bad</recommended_plugins>",
            '<identity data="</identity>">confused</identity>',
            "<recommended_plugins>unterminated",
            "<![CDATA[<identity>secret]]>",
            "<foo <identity>>secret",
            "<x a=<identity>>secret",
            "<!-- <identity>secret -->",
            '<widget data="<identity>secret</identity>">x</widget>',
        )
        for text in rejected:
            with self.subTest(text=text):
                with self.assertRaisesRegex(
                    provenance.ProvenanceError, "runtime context"
                ):
                    provenance._validate_payload(artifact_with_text(text), path)

        ordinary = (
            'ordinary <widget recommended_plugins="literal">angle</widget> '
            r"and <vector<T>> syntax with fixed-\(H\) notation"
        )
        validated = provenance._validate_payload(artifact_with_text(ordinary), path)
        messages = validated["messages"]
        self.assertIsInstance(messages, list)
        assert isinstance(messages, list)
        self.assertTrue(messages)
        first = messages[0]
        self.assertIsInstance(first, dict)
        assert isinstance(first, dict)
        self.assertEqual(first["text"], ordinary)

    def test_12_orphan_artifact_fails_range_validation(self) -> None:
        self.write_session()
        self.capture()
        self.git("commit", "--no-verify", "-qm", "orphan")
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "exactly one transcript trailer"
        ):
            provenance.validate_range(self.repo, self.base, "HEAD")

    def test_12b_control_character_orphan_artifact_fails_range_validation(
        self,
    ) -> None:
        artifact = (
            self.repo
            / provenance.ARTIFACT_PREFIX
            / "2026/07/orphan\nsecond-line\tfield.json"
        )
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}\n", encoding="utf-8")
        self.git("add", "--", str(artifact.relative_to(self.repo)))
        self.git("commit", "--no-verify", "-qm", "control-character orphan")
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "exactly one transcript trailer"
        ):
            provenance.validate_range(self.repo, self.base, "HEAD")

    def test_12c_non_utf8_control_character_path_binds_and_validates(self) -> None:
        raw_repo = os.fsencode(self.repo)
        raw_name = b"non-utf8-\xff\tfield\nline.bin"
        descriptor = os.open(
            raw_repo + b"/" + raw_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(b"content\n")
        subprocess.run(
            [b"git", b"-C", raw_repo, b"add", b"--", raw_name],
            check=True,
            capture_output=True,
        )
        self.write_session()
        self.commit_capture("byte-safe inventory")
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_12d_inventory_framing_separates_legacy_newline_collision(self) -> None:
        first_oid = b"a" * 40
        second_oid = b"b" * 40
        colliding_single_entry = [
            (
                b"100644",
                b"blob",
                first_oid,
                b"left\n100644 blob " + second_oid + b"\tright",
            )
        ]
        colliding_two_entries = [
            (b"100644", b"blob", first_oid, b"left"),
            (b"100644", b"blob", second_oid, b"right"),
        ]
        legacy_bytes = (
            b"100644 blob " + first_oid + b"\tleft\n"
            b"100644 blob " + second_oid + b"\tright\n"
        )
        self.assertEqual(
            provenance._inventory_hash(colliding_two_entries),
            hashlib.sha256(legacy_bytes).hexdigest(),
        )
        self.assertNotEqual(
            provenance._inventory_hash(colliding_single_entry),
            provenance._inventory_hash(colliding_two_entries),
        )

    def test_12e_name_status_parses_copy_and_rename_path_arity(self) -> None:
        source = self.repo / "copy\nsource\tfield.bin"
        source.write_bytes(b"copy and rename content\n")
        self.git("add", "--", str(source.relative_to(self.repo)))
        self.git("commit", "-qm", "copy source")
        source_commit = self.git("rev-parse", "HEAD").stdout.strip()

        artifact = (
            self.repo
            / provenance.ARTIFACT_PREFIX
            / "2026/07/copied\nartifact\tfield.json"
        )
        artifact.parent.mkdir(parents=True)
        shutil.copyfile(source, artifact)
        self.git("add", "--", str(artifact.relative_to(self.repo)))
        self.git("commit", "--no-verify", "-qm", "copy into transcript tree")
        copy_commit = self.git("rev-parse", "HEAD").stdout.strip()
        copy_changes = provenance._name_status_changes(
            self.repo,
            "diff",
            "--name-status",
            "-C",
            "--find-copies-harder",
            source_commit,
            copy_commit,
        )
        self.assertIn(
            (
                "C100",
                (
                    os.fsencode(source.relative_to(self.repo)),
                    os.fsencode(artifact.relative_to(self.repo)),
                ),
            ),
            copy_changes,
        )
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "exactly one transcript trailer"
        ):
            provenance.validate_range(self.repo, source_commit, copy_commit)

        renamed = self.repo / "renamed\noutside\tfield.bin"
        self.git(
            "mv",
            "--",
            str(artifact.relative_to(self.repo)),
            str(renamed.relative_to(self.repo)),
        )
        self.git("commit", "--no-verify", "-qm", "rename out of transcript tree")
        rename_commit = self.git("rev-parse", "HEAD").stdout.strip()
        rename_changes = provenance._name_status_changes(
            self.repo,
            "diff",
            "--name-status",
            "-M",
            copy_commit,
            rename_commit,
        )
        self.assertIn(
            (
                "R100",
                (
                    os.fsencode(artifact.relative_to(self.repo)),
                    os.fsencode(renamed.relative_to(self.repo)),
                ),
            ),
            rename_changes,
        )
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "may not modify or delete"
        ):
            provenance.validate_range(self.repo, copy_commit, rename_commit)

        with mock.patch.object(
            provenance,
            "_run_git_bytes",
            return_value=b"R100\0source\0",
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "malformed"):
                provenance._name_status_changes(self.repo, "diff", "--name-status")
        with mock.patch.object(
            provenance,
            "_run_git_bytes",
            return_value=b"R999\0source\0destination\0",
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "invalid status"):
                provenance._name_status_changes(self.repo, "diff", "--name-status")
        with mock.patch.object(
            provenance,
            "_run_git_bytes",
            return_value=(b"R080\0old\0new\0C000\0copy-source\0copy-destination\0"),
        ):
            self.assertEqual(
                provenance._name_status_changes(self.repo, "diff", "--name-status"),
                [
                    ("R080", (b"old", b"new")),
                    ("C000", (b"copy-source", b"copy-destination")),
                ],
            )

    def test_13_modification_of_existing_artifact_fails(self) -> None:
        self.write_session()
        path = self.commit_capture()
        (self.repo / path).write_text("{}\n", encoding="utf-8")
        self.git("add", path)
        self.git("commit", "--no-verify", "-qm", "modify")
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "may not modify or delete"
        ):
            provenance.validate_range(self.repo, self.base, "HEAD")

    def test_14_deletion_of_existing_artifact_fails(self) -> None:
        self.write_session()
        path = self.commit_capture()
        self.git("rm", "-q", path)
        self.git("commit", "--no-verify", "-qm", "delete")
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "may not modify or delete"
        ):
            provenance.validate_range(self.repo, self.base, "HEAD")

    def test_15_unavailable_session_store_fails_closed(self) -> None:
        missing = self.root / "missing-sessions"
        with self.assertRaisesRegex(
            provenance.ProvenanceError, "no exact Codex session"
        ):
            provenance.capture(
                self.repo,
                self.thread,
                missing,
                invocation_nonce=self.next_nonce(),
                scope_start="2026-07-30T20:00:00Z",
            )

    def test_16_hook_path_drift_and_executability_are_checked(self) -> None:
        hooks = self.repo / "scripts/git_hooks"
        hooks.mkdir(parents=True)
        for name in ("pre-commit", "prepare-commit-msg", "commit-msg", "post-commit"):
            source = ROOT / "scripts/git_hooks" / name
            shutil.copy2(source, hooks / name)
            (hooks / name).chmod(0o755)
        self.git("config", "core.hooksPath", "scripts/git_hooks")
        provenance.check_hooks(self.repo)
        sibling = self.root / "hook-sibling"
        self.git("worktree", "add", "-q", "-b", "hook-sibling", str(sibling))
        resolved = subprocess.run(
            [
                "git",
                "-C",
                str(sibling),
                "rev-parse",
                "--path-format=absolute",
                "--git-path",
                "hooks",
            ],
            text=True,
            capture_output=True,
            check=True,
        ).stdout.strip()
        self.assertEqual(Path(resolved), sibling / "scripts/git_hooks")
        (hooks / "commit-msg").chmod(0o644)
        with self.assertRaisesRegex(provenance.ProvenanceError, "not executable"):
            provenance.check_hooks(self.repo)

    def test_17_post_commit_remains_graphify_only(self) -> None:
        hook = (ROOT / "scripts/git_hooks/post-commit").read_text(encoding="utf-8")
        self.assertIn("graphify_refresh.py", hook)
        self.assertNotIn("codex_transcript", hook)

    def test_18_transcript_only_change_selects_no_tier(self) -> None:
        policy = ImpactPolicy.load(ROOT / CONFIG_PATH)
        path = ".agents/memory/transcripts/commits/2026/07/ct1-123456789abc-1234567890abcdef.json"
        self.assertEqual(policy.select([path]), set())

    def test_19_wrapper_rejects_bypass_partial_and_path_limited_modes(self) -> None:
        prohibited = (
            ["-n", "-m", "x"],
            ["--no-verify", "-m", "x"],
            ["-o", "file.py"],
            ["--only=file.py"],
            ["-i", "file.py"],
            ["--include=file.py"],
            ["--interactive"],
            ["--pathspec-from-file=paths"],
            ["--pathspec-file-nul"],
            ["--", "file.py"],
            ["file.py"],
        )
        for arguments in prohibited:
            with self.subTest(arguments=arguments):
                with self.assertRaises(provenance.ProvenanceError):
                    provenance.validate_commit_args(arguments)
        self.assertFalse(provenance.validate_commit_args(["-qam", "message"]))
        self.assertTrue(provenance.validate_commit_args(["--amend", "--no-edit"]))

    def test_20_no_ff_and_synthetic_merges_only_inherit_artifacts(self) -> None:
        self.write_session()
        default_branch = self.git("branch", "--show-current").stdout.strip()
        self.git("checkout", "-qb", "feature")
        feature_artifact = self.commit_capture("feature codex")
        feature_head = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-q", default_branch)
        (self.repo / "main.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "main.txt")
        self.git("commit", "-qm", "main divergence")
        main_head = self.git("rev-parse", "HEAD").stdout.strip()
        synthetic_tree = self.git(
            "merge-tree", "--write-tree", main_head, feature_head
        ).stdout.strip()
        synthetic = self.git(
            "commit-tree",
            synthetic_tree,
            "-p",
            main_head,
            "-p",
            feature_head,
            "-m",
            "merge-group equivalent",
        ).stdout.strip()
        provenance.validate_range(self.repo, self.base, synthetic)
        bad_merge = self.git(
            "commit-tree",
            synthetic_tree,
            "-p",
            main_head,
            "-p",
            feature_head,
            "-m",
            "merge with trailer\n\nCodex-Transcript: malformed",
        ).stdout.strip()
        with self.assertRaisesRegex(provenance.ProvenanceError, "may not author"):
            provenance.validate_range(self.repo, self.base, bad_merge)
        self.git("merge", "--no-ff", "-q", "-m", "no-ff", "feature")
        self.assertTrue((self.repo / feature_artifact).is_file())
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_21_merge_created_or_deleted_artifacts_fail(self) -> None:
        default_branch = self.git("branch", "--show-current").stdout.strip()
        self.git("checkout", "-qb", "plain-feature")
        (self.repo / "feature.txt").write_text("feature\n", encoding="utf-8")
        self.git("add", "feature.txt")
        self.git("commit", "-qm", "feature")
        self.git("checkout", "-q", default_branch)
        (self.repo / "main.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "main.txt")
        self.git("commit", "-qm", "main")
        self.git("merge", "--no-ff", "--no-commit", "plain-feature")
        artifact = (
            self.repo
            / ".agents/memory/transcripts/commits/2026/07/ct1-123456789abc-1234567890abcdef.json"
        )
        artifact.parent.mkdir(parents=True)
        artifact.write_text("{}\n", encoding="utf-8")
        self.git("add", str(artifact.relative_to(self.repo)))
        self.git("commit", "--no-verify", "-qm", "merge creates artifact")
        with self.assertRaisesRegex(provenance.ProvenanceError, "created or deleted"):
            provenance.validate_range(self.repo, self.base, "HEAD")

    def test_22_merge_cannot_delete_inherited_artifact(self) -> None:
        self.write_session()
        default_branch = self.git("branch", "--show-current").stdout.strip()
        self.git("checkout", "-qb", "artifact-feature")
        artifact = self.commit_capture("feature artifact")
        self.git("checkout", "-q", default_branch)
        (self.repo / "main.txt").write_text("main\n", encoding="utf-8")
        self.git("add", "main.txt")
        self.git("commit", "-qm", "main")
        self.git("merge", "--no-ff", "--no-commit", "artifact-feature")
        self.git("rm", "-q", "-f", artifact)
        self.git("commit", "--no-verify", "-qm", "merge deletes artifact")
        with self.assertRaisesRegex(provenance.ProvenanceError, "created or deleted"):
            provenance.validate_range(self.repo, self.base, "HEAD")

    def assert_prior_artifact_unchanged(self, prior: str, expected: bytes) -> None:
        self.assertEqual((self.repo / prior).read_bytes(), expected)
        self.assertEqual(
            self.git("show", f":{prior}").stdout.encode(),
            expected,
        )
        self.assertEqual(
            self.git(
                "diff", "--cached", "--name-only", "--", provenance.ARTIFACT_PREFIX
            ).stdout,
            "",
        )

    def test_23_amend_preparation_failures_leave_prior_artifact_unchanged(self) -> None:
        session = self.write_session()
        prior = self.commit_capture("prior transaction")
        prior_bytes = (self.repo / prior).read_bytes()

        session.unlink()
        with self.assertRaisesRegex(provenance.ProvenanceError, "no exact Codex"):
            self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

        self.write_session(
            messages=[("user", "<permissions instructions>unterminated")]
        )
        with self.assertRaisesRegex(provenance.ProvenanceError, "no eligible"):
            self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

        self.write_session()
        with mock.patch.object(
            provenance,
            "_snapshot_session",
            side_effect=provenance.ProvenanceError(
                "Codex session changed during capture; retry the commit"
            ),
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "changed"):
                self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

    def test_24_amend_write_add_and_removal_failures_roll_back(self) -> None:
        session = self.write_session()
        prior = self.commit_capture("prior staged transaction")
        prior_bytes = (self.repo / prior).read_bytes()
        with session.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "timestamp": "2026-07-31T01:00:00Z",
                        "type": "response_item",
                        "payload": {
                            "type": "message",
                            "role": "assistant",
                            "content": [{"text": "transaction replacement"}],
                        },
                    }
                )
                + "\n"
            )

        with mock.patch.object(
            provenance,
            "_write_artifact",
            side_effect=provenance.ProvenanceError("injected write failure"),
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "write failure"):
                self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

        original_run_git = provenance._run_git

        def fail_replacement_add(
            repo: Path, *arguments: str, input_text: str | None = None
        ) -> str:
            if arguments[:2] == ("add", "--") and arguments[-1] != prior:
                raise provenance.ProvenanceError("injected git add failure")
            return original_run_git(repo, *arguments, input_text=input_text)

        with mock.patch.object(
            provenance, "_run_git", side_effect=fail_replacement_add
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "git add failure"):
                self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

        removal_failed = False

        def fail_prior_removal(
            repo: Path, *arguments: str, input_text: str | None = None
        ) -> str:
            nonlocal removal_failed
            if (
                not removal_failed
                and arguments[:3] == ("rm", "-q", "-f")
                and arguments[-1] == prior
            ):
                removal_failed = True
                original_run_git(repo, *arguments, input_text=input_text)
                raise provenance.ProvenanceError("injected prior removal failure")
            return original_run_git(repo, *arguments, input_text=input_text)

        with mock.patch.object(provenance, "_run_git", side_effect=fail_prior_removal):
            with self.assertRaisesRegex(provenance.ProvenanceError, "removal failure"):
                self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

        with mock.patch.object(
            provenance,
            "_write_state",
            side_effect=OSError("injected state write failure"),
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "state write"):
                self.capture(amend=True)
        self.assert_prior_artifact_unchanged(prior, prior_bytes)

    def test_25_artifact_paths_reject_symlink_parents_and_destinations(self) -> None:
        self.write_session()
        external = self.root / "external"
        external.mkdir()
        agents = self.repo / ".agents"
        agents.symlink_to(external, target_is_directory=True)
        self.git("add", ".agents")
        self.git("commit", "-qm", "tracked symlink parent")
        with self.assertRaisesRegex(provenance.ProvenanceError, "symlink"):
            self.capture()
        self.assertEqual(list(external.iterdir()), [])

        agents.unlink()
        (self.repo / ".agents/memory/transcripts").mkdir(parents=True)
        commits = self.repo / ".agents/memory/transcripts/commits"
        commits.symlink_to(external, target_is_directory=True)
        with self.assertRaisesRegex(provenance.ProvenanceError, "symlink"):
            self.capture()
        self.assertEqual(list(external.iterdir()), [])

        commits.unlink()
        artifact = self.capture()
        provenance.clear_state(
            self.repo, self._read_latest_nonce(), cleanup_artifact=True
        )
        destination = self.repo / artifact
        destination.parent.mkdir(parents=True, exist_ok=True)
        external_file = external / "outside.json"
        external_file.write_text("outside\n", encoding="utf-8")
        destination.symlink_to(external_file)
        with self.assertRaisesRegex(provenance.ProvenanceError, "symlink"):
            provenance._write_artifact(self.repo, artifact, b"replacement\n")
        self.assertEqual(external_file.read_text(encoding="utf-8"), "outside\n")

        destination.unlink()
        with mock.patch.object(os, "write", side_effect=OSError("short device")):
            with self.assertRaisesRegex(provenance.ProvenanceError, "cannot write"):
                provenance._write_artifact(self.repo, artifact, b"replacement\n")
        self.assertFalse(destination.exists())
        self.assertEqual(list(destination.parent.glob(".*.tmp")), [])

        detached = commits.with_name("commits-detached")

        def swap_parent(stage: str, repo: Path, path_text: str) -> None:
            self.assertEqual(stage, "before-link")
            self.assertEqual(repo, self.repo)
            self.assertEqual(path_text, artifact)
            commits.rename(detached)
            commits.symlink_to(external, target_is_directory=True)

        with mock.patch.object(
            provenance, "_artifact_race_hook", side_effect=swap_parent
        ):
            with self.assertRaisesRegex(provenance.ProvenanceError, "parent changed"):
                provenance._write_artifact(self.repo, artifact, b"race\n")
        self.assertEqual(external_file.read_text(encoding="utf-8"), "outside\n")
        self.assertEqual(list(external.glob("ct1-*.json")), [])
        self.assertEqual(list(detached.rglob("ct1-*.json")), [])
        self.assertEqual(list(detached.rglob(".*.tmp")), [])
        commits.unlink()
        detached.rename(commits)

    def _read_latest_nonce(self) -> str:
        return str(provenance._read_state(self.repo)["invocation_nonce"])

    def test_26_new_sanitizer_classes_cover_capture_and_final_artifact(self) -> None:
        sensitive_cases = (
            "AKIAABCDEFGHIJKLMNOP",
            "0123456789abcdef0123456789abcdef01234567",
            "0123456789abcdef" * 4,
            "/dss/project/private.bin",
            "/gpfs/scratch/run",
            r"\\server\share\private.bin",
        )
        self.write_session(
            messages=[
                *(("user", value) for value in sensitive_cases),
                ("assistant", "safe"),
            ]
        )
        path = self.capture()
        serialized = (self.repo / path).read_text(encoding="utf-8")
        for value in sensitive_cases:
            self.assertNotIn(value, serialized)
        provenance.clear_state(
            self.repo, self._read_latest_nonce(), cleanup_artifact=False
        )

        runtime_cases = tuple(
            form
            for tag in provenance.RUNTIME_TAGS
            for form in (f"<{tag}>hidden</{tag}>", f"<{tag}>unterminated")
        )
        original = json.loads(serialized)
        for value in (*sensitive_cases, *runtime_cases):
            with self.subTest(value=value):
                payload = json.loads(json.dumps(original))
                payload["messages"][0]["text"] = value
                payload["messages"][0]["message_hash"] = hashlib.sha256(
                    value.encode()
                ).hexdigest()
                payload.pop("canonical_payload_hash")
                payload["canonical_payload_hash"] = hashlib.sha256(
                    provenance._canonical_json(payload)
                ).hexdigest()
                with self.assertRaises(provenance.ProvenanceError):
                    provenance._validate_payload(
                        provenance._canonical_json(payload), path
                    )

    def test_27_parent_and_tree_binding_reject_replay(self) -> None:
        self.write_session()
        valid = self.commit_capture("bound commit")
        valid_commit = self.git("rev-parse", "HEAD").stdout.strip()
        valid_message = self.git("show", "-s", "--format=%B", valid_commit).stdout
        valid_parent = self.git("rev-parse", f"{valid_commit}^").stdout.strip()

        (self.repo / "different.txt").write_text("different\n", encoding="utf-8")
        self.git("add", "different.txt")
        different_tree = self.git("write-tree").stdout.strip()
        different_content = self.git(
            "commit-tree",
            different_tree,
            "-p",
            valid_parent,
            "-m",
            valid_message,
        ).stdout.strip()
        with self.assertRaisesRegex(provenance.ProvenanceError, "different content"):
            provenance.validate_range(self.repo, valid_parent, different_content)
        self.git("reset", "-q", valid_commit)

        self.git("checkout", "-qb", "replay-target", valid_parent)
        (self.repo / "target.txt").write_text("target\n", encoding="utf-8")
        self.git("add", "target.txt")
        self.git("commit", "-qm", "new parent")
        replay_parent = self.git("rev-parse", "HEAD").stdout.strip()
        replay = self.git("cherry-pick", "--no-commit", valid_commit)
        self.assertEqual(replay.returncode, 0)
        self.git("commit", "--no-verify", "-q", "-C", valid_commit)
        with self.assertRaisesRegex(provenance.ProvenanceError, "different parent"):
            provenance.validate_range(self.repo, replay_parent, "HEAD")
        self.assertTrue((self.repo / valid).is_file())

    def test_28_rebase_replay_fails_and_squash_recapture_passes(self) -> None:
        self.write_session()
        self.git("checkout", "-qb", "rebase-source")
        self.commit_capture("source provenance")
        self.git("checkout", "-qb", "rebase-target", self.base)
        (self.repo / "target.txt").write_text("target\n", encoding="utf-8")
        self.git("add", "target.txt")
        self.git("commit", "-qm", "target base")
        target = self.git("rev-parse", "HEAD").stdout.strip()
        self.git("checkout", "-q", "rebase-source")
        self.git("rebase", "--onto", target, self.base, "rebase-source")
        with self.assertRaisesRegex(provenance.ProvenanceError, "different parent"):
            provenance.validate_range(self.repo, target, "HEAD")

        self.git("checkout", "-qb", "squash-recapture", self.base)
        (self.repo / "one.txt").write_text("one\n", encoding="utf-8")
        self.git("add", "one.txt")
        self.git("commit", "-qm", "one")
        (self.repo / "two.txt").write_text("two\n", encoding="utf-8")
        self.git("add", "two.txt")
        self.git("commit", "-qm", "two")
        self.git("reset", "--soft", self.base)
        self.commit_capture("squash recaptured")
        provenance.validate_range(self.repo, self.base, "HEAD")

    def test_29_empty_base_and_workflow_event_matrix(self) -> None:
        self.write_session()
        self.commit_capture("manual dispatch head")
        provenance.validate_range(self.repo, "", "HEAD")
        workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
        for expression in (
            "github.event.pull_request.base.sha",
            "github.event.pull_request.head.sha",
            "github.event.merge_group.base_sha",
            "github.event.merge_group.head_sha",
            "github.event.before",
            "github.sha",
        ):
            self.assertIn(expression, workflow)

        root_repo = self.root / "manual-root"
        root_repo.mkdir()
        subprocess.run(["git", "init", "-q", root_repo], check=True)
        (root_repo / "root.txt").write_text("root\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(root_repo), "add", "root.txt"], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(root_repo),
                "-c",
                "user.name=Tests",
                "-c",
                "user.email=tests@example.invalid",
                "commit",
                "-qm",
                "root",
            ],
            check=True,
        )
        provenance.validate_range(root_repo, "", "HEAD")

    def test_30_active_octopus_merge_fails_before_mutation(self) -> None:
        self.write_session()
        (self.repo / "merge-owned.txt").write_text("owned\n", encoding="utf-8")
        self.git("add", "merge-owned.txt")
        staged_before = self.git("ls-files", "--stage").stdout
        merge_head = Path(
            self.git(
                "rev-parse", "--path-format=absolute", "--git-path", "MERGE_HEAD"
            ).stdout.strip()
        )
        merge_head.write_text(f"{self.base}\n{self.base}\n", encoding="ascii")
        with self.assertRaisesRegex(provenance.ProvenanceError, "active merge"):
            self.capture()
        self.assertEqual(self.git("ls-files", "--stage").stdout, staged_before)
        self.assertFalse(provenance._state_path(self.repo).exists())
        transcript_root = self.repo / provenance.ARTIFACT_PREFIX
        self.assertFalse(transcript_root.exists())

    def test_31_realistic_runtime_records_are_filtered_after_extraction(self) -> None:
        session = self.sessions / f"rollout-{self.thread}.jsonl"
        records = [
            {
                "timestamp": "2026-07-31T09:00:00Z",
                "type": "session_meta",
                "payload": {
                    "id": self.thread,
                    "timestamp": "2026-07-31T09:00:00Z",
                    "cwd": str(self.repo),
                },
            },
            {
                "timestamp": "2026-07-31T09:00:01Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "developer",
                    "content": [{"text": "<identity>developer control</identity>"}],
                },
            },
            {
                "timestamp": "2026-07-31T09:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "custom_tool_call_output",
                    "output": "<constraints>tool control</constraints>",
                },
            },
            {
                "timestamp": "2026-07-31T09:00:03Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "text": (
                                "Please preserve this actual prompt.\n"
                                "<recommended_plugins>private plugin data"
                                "</recommended_plugins>\n"
                                "<instructions>injected instructions</instructions>\n"
                                "<environment_context>machine context"
                                "</environment_context>\n"
                                "Continue with the requested implementation."
                            )
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-07-31T09:00:04Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [
                        {
                            "text": (
                                "Before quoted control "
                                "<posture_overlay>hidden</posture_overlay> after control."
                            )
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-07-31T09:00:05Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [{"text": "quoted <scope_guard>unterminated"}],
                },
            },
        ]
        session.write_text(
            "".join(json.dumps(record) + "\n" for record in records),
            encoding="utf-8",
        )
        artifact = self.capture()
        payload = json.loads((self.repo / artifact).read_text(encoding="utf-8"))
        text = "\n".join(message["text"] for message in payload["messages"])
        self.assertIn("Please preserve this actual prompt.", text)
        self.assertIn("Continue with the requested implementation.", text)
        self.assertIn("Before quoted control", text)
        self.assertIn("after control.", text)
        for excluded in (
            "developer control",
            "tool control",
            "private plugin data",
            "injected instructions",
            "machine context",
            "hidden",
            "unterminated",
        ):
            self.assertNotIn(excluded, text)
        self.assertEqual(
            payload["session_snapshot_hash"],
            hashlib.sha256(session.read_bytes()).hexdigest(),
        )
        provenance.clear_state(
            self.repo, self._read_latest_nonce(), cleanup_artifact=True
        )

        excluded_records = [records[0], records[1], records[2], records[-1]]
        session.write_text(
            "".join(json.dumps(record) + "\n" for record in excluded_records),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(provenance.ProvenanceError, "no eligible"):
            self.capture()
        self.assertFalse(provenance._state_path(self.repo).exists())


if __name__ == "__main__":
    unittest.main()
