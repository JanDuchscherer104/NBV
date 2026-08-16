from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[3] / "scripts" / "codex_transcript_extract.py"
SPEC = importlib.util.spec_from_file_location("codex_transcript_extract", SCRIPT_PATH)
assert SPEC is not None
extractor = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = extractor
SPEC.loader.exec_module(extractor)


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_extracts_user_messages_and_skips_bootstrap_context(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_path = sessions_root / "2026" / "05" / "09" / "rollout.jsonl"
    project_root = tmp_path / "ARIA-NBV"
    write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-05-09T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "s1", "timestamp": "2026-05-09T10:00:00Z", "cwd": project_root.as_posix()},
            },
            {
                "timestamp": "2026-05-09T10:00:01Z",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": "# AGENTS.md instructions for /tmp/ARIA-NBV\n\n<INSTRUCTIONS>skip</INSTRUCTIONS>",
                },
            },
            {
                "timestamp": "2026-05-09T10:00:02Z",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": "Use the full ARIA-NBV transcript store for decision mining.",
                },
            },
            {
                "timestamp": "2026-05-09T10:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Use the full ARIA-NBV transcript store for decision mining.",
                        }
                    ],
                },
            },
        ],
    )

    chats, users, plans, counts = extractor.gather_records([sessions_root], project_root)

    assert counts["candidate_sessions"] == 1
    assert len(chats) == 1
    assert chats[0]["role"] == "user"
    assert chats[0]["text"] == "Use the full ARIA-NBV transcript store for decision mining."
    assert len(users) == 1
    assert users[0]["text"] == "Use the full ARIA-NBV transcript store for decision mining."
    assert plans == []


def test_marker_fallback_includes_session_without_repo_cwd(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_path = sessions_root / "2026" / "05" / "09" / "rollout.jsonl"
    project_root = tmp_path / "ARIA-NBV"
    write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-05-09T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "s1", "cwd": "/tmp/not-this-repo"},
            },
            {
                "timestamp": "2026-05-09T10:00:01Z",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": "ARIA-NBV should keep transcript distillates reviewable.",
                },
            },
        ],
    )

    _chats, users, _plans, counts = extractor.gather_records([sessions_root], project_root)

    assert counts["candidate_sessions"] == 1
    assert counts["sessions_matched_by_marker"] == 1
    assert users[0]["cwd"] == "/tmp/not-this-repo"


def test_marker_fallback_excludes_other_repo_checkout(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_path = sessions_root / "2026" / "05" / "09" / "rollout.jsonl"
    project_root = Path.home() / "repos" / "ARIA-NBV"
    write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-05-09T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "s1", "cwd": (Path.home() / "repos" / "prml-vslam").as_posix()},
            },
            {
                "timestamp": "2026-05-09T10:00:01Z",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": "Compare this scaffold against ARIA-NBV.",
                },
            },
        ],
    )

    chats, users, plans, counts = extractor.gather_records([sessions_root], project_root)

    assert counts["candidate_sessions"] == 0
    assert chats == []
    assert users == []
    assert plans == []


def test_pairs_only_plan_mode_request_user_input_answers(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_path = sessions_root / "2026" / "05" / "09" / "rollout.jsonl"
    project_root = tmp_path / "ARIA-NBV"
    question_args = {
        "questions": [
            {
                "id": "raw_policy",
                "header": "Raw Data",
                "question": "How should raw transcript data be stored?",
                "options": [{"label": "User plus plans only (Recommended)", "description": "narrow"}],
            }
        ]
    }
    write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-05-09T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "s1", "cwd": project_root.as_posix()},
            },
            {
                "timestamp": "2026-05-09T10:00:01Z",
                "type": "event_msg",
                "payload": {"type": "task_started", "turn_id": "t1", "collaboration_mode_kind": "plan"},
            },
            {
                "timestamp": "2026-05-09T10:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "request_user_input",
                    "call_id": "call-plan",
                    "arguments": json.dumps(question_args),
                },
            },
            {
                "timestamp": "2026-05-09T10:00:03Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-plan",
                    "output": json.dumps(
                        {"answers": {"raw_policy": {"answers": ["User plus plans only (Recommended)"]}}}
                    ),
                },
            },
            {
                "timestamp": "2026-05-09T10:00:04Z",
                "type": "event_msg",
                "payload": {"type": "task_started", "turn_id": "t2", "collaboration_mode_kind": "default"},
            },
            {
                "timestamp": "2026-05-09T10:00:05Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "request_user_input",
                    "call_id": "call-default",
                    "arguments": json.dumps(question_args),
                },
            },
            {
                "timestamp": "2026-05-09T10:00:06Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "call-default",
                    "output": json.dumps({"answers": {"raw_policy": {"answers": ["Full raw extracts"]}}}),
                },
            },
        ],
    )

    _chats, _users, plans, counts = extractor.gather_records([sessions_root], project_root)

    assert counts["plan_answers_deduped"] == 1
    assert plans[0]["question"]["id"] == "raw_policy"
    assert plans[0]["answers"] == ["User plus plans only (Recommended)"]
    assert plans[0]["turn_id"] == "t1"


def test_extracts_chat_only_user_and_assistant_messages(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_path = sessions_root / "2026" / "06" / "18" / "rollout.jsonl"
    project_root = tmp_path / "ARIA-NBV"
    write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-06-18T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "s-chat", "cwd": project_root.as_posix()},
            },
            {
                "timestamp": "2026-06-18T10:00:01Z",
                "type": "event_msg",
                "payload": {"type": "task_started", "turn_id": "t-chat"},
            },
            {
                "timestamp": "2026-06-18T10:00:02Z",
                "type": "event_msg",
                "payload": {
                    "type": "user_message",
                    "message": "Please export ARIA-NBV chat transcripts.",
                },
            },
            {
                "timestamp": "2026-06-18T10:00:02Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": "Please export ARIA-NBV chat transcripts.",
                        }
                    ],
                },
            },
            {
                "timestamp": "2026-06-18T10:00:03Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call",
                    "name": "exec_command",
                    "call_id": "tool-1",
                    "arguments": '{"cmd": "echo hidden"}',
                },
            },
            {
                "timestamp": "2026-06-18T10:00:04Z",
                "type": "response_item",
                "payload": {
                    "type": "function_call_output",
                    "call_id": "tool-1",
                    "output": "hidden tool output",
                },
            },
            {
                "timestamp": "2026-06-18T10:00:05Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "phase": "final",
                    "content": [
                        {
                            "type": "output_text",
                            "text": "Implemented the chat transcript export.",
                        }
                    ],
                },
            },
        ],
    )

    chats, users, plans, counts = extractor.gather_records([sessions_root], project_root)

    assert counts["chat_messages_raw"] == 3
    assert counts["chat_messages_deduped"] == 2
    assert [chat["role"] for chat in chats] == ["user", "assistant"]
    assert [chat["text"] for chat in chats] == [
        "Please export ARIA-NBV chat transcripts.",
        "Implemented the chat transcript export.",
    ]
    assert chats[1]["phase"] == "final"
    assert users[0]["text"] == "Please export ARIA-NBV chat transcripts."
    assert plans == []


def test_default_main_writes_raw_chat_manifest(tmp_path: Path) -> None:
    sessions_root = tmp_path / "sessions"
    session_path = sessions_root / "2026" / "06" / "18" / "rollout.jsonl"
    project_root = tmp_path / "ARIA-NBV"
    output_root = tmp_path / "transcripts"
    decisions_file = tmp_path / "DECISIONS.md"
    preferences_file = tmp_path / "human_owner_intent.md"
    decisions_file.write_text("- Existing decision.\n", encoding="utf-8")
    preferences_file.write_text("- Existing preference.\n", encoding="utf-8")
    write_jsonl(
        session_path,
        [
            {
                "timestamp": "2026-06-18T10:00:00Z",
                "type": "session_meta",
                "payload": {"id": "s-write", "cwd": project_root.as_posix()},
            },
            {
                "timestamp": "2026-06-18T10:00:01Z",
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": "ARIA-NBV transcript export is ready."}],
                },
            },
        ],
    )

    result = extractor.main(
        [
            "--sessions-root",
            sessions_root.as_posix(),
            "--project-root",
            project_root.as_posix(),
            "--output-root",
            output_root.as_posix(),
            "--decisions-file",
            decisions_file.as_posix(),
            "--preferences-file",
            preferences_file.as_posix(),
            "--date",
            "2026-06-18",
        ]
    )

    assert result == 0
    raw_path = output_root / "raw" / "2026-06-18" / "chat_messages.jsonl"
    manifest_path = output_root / "distilled" / "2026-06-18" / "manifest.json"
    assert raw_path.exists()
    raw_records = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
    assert raw_records[0]["role"] == "assistant"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["counts"]["chat_messages_deduped"] == 1
    assert raw_path.as_posix() in manifest["outputs"]


def test_distillates_route_promotion_targets() -> None:
    plan_answer = {
        "kind": "plan_mode_answer",
        "content_hash": "abc",
        "question": {
            "id": "raw_policy",
            "question": "How should raw transcript data be stored?",
        },
        "answers": ["User plus plans only (Recommended)"],
        "source": {"root": "default", "session_path": "s.jsonl", "line": 4},
    }

    distillates = extractor.distill_records([], [plan_answer])

    assert len(distillates) == 1
    assert distillates[0]["summary"] == "Plan-mode answer `raw_policy` selected: User plus plans only"
    assert distillates[0]["promotion_target"] == ".agents/memory/state/DECISIONS.md"


def test_review_marks_already_reflected_decisions() -> None:
    distillates = [
        {
            "status": "candidate",
            "category": "durable repo decision",
            "summary": "Transcript mining must not check in full raw Codex transcripts.",
            "prompt": None,
            "promotion_target": ".agents/memory/state/DECISIONS.md",
        }
    ]
    canonical_text = """
    - Transcript mining must not check in full raw Codex transcripts. Repo memory
      may contain only user-authored extracts and reviewed candidate distillates.
    """

    reviewed = extractor.review_distillates(
        distillates,
        canonical_text=canonical_text,
        preference_text="",
    )

    assert reviewed[0]["review_status"] == "already_reflected"
    assert reviewed[0]["canonical_overlap"] >= 0.55


def test_review_marks_unreflected_decisions_for_canonical_review() -> None:
    distillates = [
        {
            "status": "candidate",
            "category": "technical decision",
            "summary": "Plan-mode answer `new_schema` selected: Store typed artifact manifests.",
            "prompt": "How should the new schema be stored?",
            "promotion_target": ".agents/memory/state/DECISIONS.md",
        }
    ]

    reviewed = extractor.review_distillates(
        distillates,
        canonical_text="- Unrelated canonical memory entry.",
        preference_text="",
    )

    assert reviewed[0]["review_status"] == "needs_canonical_review"
