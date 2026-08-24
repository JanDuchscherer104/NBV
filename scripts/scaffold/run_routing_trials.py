#!/usr/bin/env python3
"""Run bounded Codex routing trials against an exact Git head.

Live trials require ``ARIA_NBV_ROUTING_TRIAL_PROXY_URL`` to name a local,
Responses-compatible credential broker. Host credentials never enter the
Bubblewrap namespace that executes a trial or its model-based verifier.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Event, Lock
from typing import Any, BinaryIO
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
PROMPTS_RELATIVE = Path("scripts/scaffold/fixtures/routing_prompts.jsonl")
RUBRIC_RELATIVE = Path("scripts/scaffold/fixtures/routing.json")
REPORT_SCHEMA_RELATIVE = Path(
    "scripts/scaffold/fixtures/routing_trial_report.schema.json"
)
VERIFIER_SCHEMA_RELATIVE = Path("scripts/scaffold/fixtures/routing_verdict.schema.json")
PROMPTS_PATH = ROOT / PROMPTS_RELATIVE
RUBRIC_PATH = ROOT / RUBRIC_RELATIVE
REPORT_SCHEMA = ROOT / REPORT_SCHEMA_RELATIVE
VERIFIER_SCHEMA = ROOT / VERIFIER_SCHEMA_RELATIVE
TRUSTED_RENDER_SCRIPT_RELATIVE = Path(
    ".agents/skills/typst-authoring/scripts/render_png.sh"
)
TRUSTED_RENDER_SCRIPT = ROOT / TRUSTED_RENDER_SCRIPT_RELATIVE
EVALUATOR_FIXTURE_PATHS = (
    PROMPTS_RELATIVE,
    RUBRIC_RELATIVE,
    REPORT_SCHEMA_RELATIVE,
    VERIFIER_SCHEMA_RELATIVE,
    TRUSTED_RENDER_SCRIPT_RELATIVE,
)
EVALUATOR_EXCLUDED_PATHS = (
    *EVALUATOR_FIXTURE_PATHS,
    Path("scripts/tests"),
    Path(".agents/memory"),
    Path(".omx"),
)
EVENT_EVIDENCE_MAX_ITEMS = 64
EVENT_EVIDENCE_MAX_FIELD_CHARS = 2_048
EVENT_EVIDENCE_MAX_TOTAL_CHARS = 32_768
# Bound both a single JSONL record and the complete untrusted event stream.
# Codex can emit one large event containing tool output, but evidence extraction
# must not scan an unbounded stream just because every individual line fits.
EVENT_EVIDENCE_MAX_RAW_LINE_BYTES = 2_097_152
EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES = 4_194_304
TRIAL_STDERR_MAX_BYTES = 1_048_576
TRIAL_RESPONSE_MAX_CHARS = 16_384
VERIFIER_REPORT_MAX_BYTES = 1_048_576
SUBMISSION_GATE_DIAGNOSTIC = (
    "error: assertion failed: submission mode requires explicit aria-thesis-data"
)
SUBMISSION_GATE_SOURCE = "typst/thesis/experiment_data.typ:"
PROCESS_TERMINATE_GRACE_SECONDS = 5
VERDICT_MAX_ITEMS = 64
READ_ONLY_SANDBOX = "read-only"
WORKSPACE_WRITE_SANDBOX = "workspace-write"
ROUTING_TRIAL_PROXY_URL_ENV = "ARIA_NBV_ROUTING_TRIAL_PROXY_URL"
ROUTING_TRIAL_PROXY_PROVIDER = "aria_nbv_routing_trials"
SANDBOX_PROXY_URL = "http://127.0.0.1:43124/v1"
_EXECUTION_MODES = (READ_ONLY_SANDBOX, WORKSPACE_WRITE_SANDBOX)
_TRUNCATION_SUFFIX = "...<truncated>"
_EXECUTION_IDENTITY_FIELDS = {
    "command_execution": ("command",),
    "function_call": ("name",),
    "mcp_tool_call": ("server", "tool", "tool_name", "name"),
    "tool_call": ("tool", "tool_name", "name"),
    "web_search": ("query", "path"),
}
_GENERIC_EXECUTION_IDENTITY_FIELDS = (
    "command",
    "server",
    "tool",
    "tool_name",
    "name",
    "query",
    "path",
)
_EVIDENCE_FIELDS = (
    "command",
    "server",
    "tool",
    "tool_name",
    "name",
    "arguments",
    "args",
    "input",
    "query",
    "path",
    "cwd",
    "status",
    "exit_code",
    "error",
)
DEFAULT_TRIAL_IDS = (
    "context7-graphify-api-change",
    "local-file-lookup",
    "context7-not-needed-target-rri-section",
    "package-contract-owner",
    "semantic-recall-reviewed-history",
    "concrete-failure",
    "durable-workpackage-completion",
    "oracle-evidence-construction",
    "oracle-private-scoring",
    "oracle-scene-rri-scoring",
    "oracle-target-rri-scoring",
    "oracle-label-dtos",
    "oracle-label-pipeline",
    "geometry-pose-generation",
    "geometry-rendering-camera",
    "geometry-vin-frame-contract",
    "zarr-rollout-storage-api",
    "zarr-offline-vin-storage-api",
)

ACADEMIC_AUTHORING_TRIAL_IDS = (
    "academic-writing-related-work-synthesis",
    "typst-authoring-layout-repair",
    "scientific-review-frozen-claim",
    "thesis-claim-revision",
    "empirical-result-revision",
    "rollout-report-owner-not-writing-skill",
)


def _copy_bounded_stream(
    stream: BinaryIO,
    destination: BinaryIO,
    *,
    maximum_bytes: int,
    overflow: Event,
    on_overflow: Callable[[], None],
    lock: Any,
    written: list[int],
) -> None:
    """Copy one process stream under its byte bound and flag overflow."""
    while chunk := stream.read(64 * 1024):
        with lock:
            remaining = maximum_bytes - written[0]
            if remaining <= 0:
                overflow.set()
                on_overflow()
                return
            destination.write(chunk[:remaining])
            written[0] += min(len(chunk), remaining)
            if len(chunk) > remaining:
                overflow.set()
                on_overflow()
                return


def _stop_process_group(process: Any) -> None:
    """Terminate one started process group without allowing cleanup to hang."""
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except (AttributeError, ProcessLookupError, PermissionError):
        process.terminate()
    try:
        process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (AttributeError, ProcessLookupError, PermissionError):
            process.kill()
        try:
            process.wait(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            pass


def _run_bounded_process(
    *,
    command: list[str],
    prompt: str,
    cwd: Path,
    events_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    """Run one model process while preserving bounded stdout and stderr receipts."""
    output_overflow = Event()
    events_overflow = Event()
    stderr_overflow = Event()
    output_lock = Lock()
    event_bytes = [0]
    stderr_bytes = [0]
    returncode = 125
    timed_out = False
    launch_error = False
    process: Any | None = None
    with events_path.open("wb") as events, stderr_path.open("wb") as stderr:
        try:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=os.environ.copy(),
                start_new_session=True,
            )
            assert process.stdin is not None
            assert process.stdout is not None
            assert process.stderr is not None
            process.stdin.write(prompt.encode("utf-8"))
            process.stdin.close()

            def signal_process_group(signal_number: int) -> None:
                try:
                    os.killpg(process.pid, signal_number)
                except (AttributeError, ProcessLookupError, PermissionError):
                    process.terminate()

            def stop_process() -> None:
                _stop_process_group(process)

            def terminate_for(overflow: Event) -> None:
                overflow.set()
                output_overflow.set()
                signal_process_group(signal.SIGTERM)

            with ThreadPoolExecutor(max_workers=2) as executor:
                copies = (
                    executor.submit(
                        _copy_bounded_stream,
                        process.stdout,
                        events,
                        maximum_bytes=EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES,
                        overflow=events_overflow,
                        on_overflow=lambda: terminate_for(events_overflow),
                        lock=output_lock,
                        written=event_bytes,
                    ),
                    executor.submit(
                        _copy_bounded_stream,
                        process.stderr,
                        stderr,
                        maximum_bytes=TRIAL_STDERR_MAX_BYTES,
                        overflow=stderr_overflow,
                        on_overflow=lambda: terminate_for(stderr_overflow),
                        lock=output_lock,
                        written=stderr_bytes,
                    ),
                )
                deadline = time.monotonic() + timeout_seconds
                while process.poll() is None:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        stop_process()
                        returncode = 124
                        timed_out = True
                        break
                    if output_overflow.is_set():
                        stop_process()
                        returncode = 125
                        break
                    try:
                        returncode = process.wait(timeout=min(remaining, 0.1))
                    except subprocess.TimeoutExpired:
                        continue
                else:
                    returncode = process.returncode
                for copy in copies:
                    copy.result(timeout=PROCESS_TERMINATE_GRACE_SECONDS)
        except subprocess.TimeoutExpired:
            if process is not None:
                _stop_process_group(process)
            launch_error = True
            timed_out = True
            returncode = 124
        except OSError:
            if process is not None:
                _stop_process_group(process)
            launch_error = True
            returncode = 125
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "output_overflow": output_overflow.is_set(),
        "launch_error": launch_error,
        "stream_capture": {
            "events": {
                "observed_bytes": event_bytes[0],
                "maximum_bytes": EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES,
                "overflowed": events_overflow.is_set(),
            },
            "stderr": {
                "observed_bytes": stderr_bytes[0],
                "maximum_bytes": TRIAL_STDERR_MAX_BYTES,
                "overflowed": stderr_overflow.is_set(),
            },
        },
    }


def run_git(*args: str, cwd: Path = ROOT) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _source_bytes(source: bytes | Path) -> bytes:
    return source if isinstance(source, bytes) else source.read_bytes()


def load_prompts(source: bytes | Path = PROMPTS_PATH) -> dict[str, str]:
    prompts: dict[str, str] = {}
    text = _source_bytes(source).decode("utf-8")
    for line_number, line in enumerate(text.splitlines(), start=1):
        record = json.loads(line)
        if not isinstance(record, dict) or set(record) != {"id", "task"}:
            raise ValueError(f"prompt line {line_number}: expected only id and task")
        prompt_id = record["id"]
        task = record["task"]
        if not isinstance(prompt_id, str) or not isinstance(task, str):
            raise TypeError(f"prompt line {line_number}: id and task must be strings")
        if prompt_id in prompts:
            raise ValueError(f"prompt line {line_number}: duplicate id {prompt_id!r}")
        prompts[prompt_id] = task
    return prompts


def load_rubric(source: bytes | Path = RUBRIC_PATH) -> dict[str, dict[str, Any]]:
    data = json.loads(_source_bytes(source).decode("utf-8"))
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list):
        raise TypeError("rubric fixtures must be a list")
    rubric: dict[str, dict[str, Any]] = {}
    for fixture in fixtures:
        if not isinstance(fixture, dict) or not isinstance(fixture.get("id"), str):
            raise TypeError("every rubric fixture needs a string id")
        trial_id = fixture["id"]
        if trial_id in rubric:
            raise ValueError(f"duplicate rubric fixture id {trial_id!r}")
        rubric[trial_id] = fixture
    return rubric


def select_trial_ids(
    args: argparse.Namespace, prompts: dict[str, str]
) -> tuple[str, ...]:
    """Return one explicit routing suite without silently combining suites."""
    if args.all and args.academic_authoring:
        raise ValueError("--all and --academic-authoring cannot be combined")
    if args.all:
        return tuple(prompts)
    if args.academic_authoring:
        return ACADEMIC_AUTHORING_TRIAL_IDS
    return tuple(args.ids or DEFAULT_TRIAL_IDS)


def read_git_blob(commit: str, path: Path, *, root: Path = ROOT) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path.as_posix()}"],
        cwd=root,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        raise ValueError(f"cannot read {path.as_posix()} at {commit}")
    return result.stdout


def attest_evaluator_fixtures(
    *, tested_commit: str, rubric_commit: str, root: Path = ROOT
) -> dict[Path, bytes]:
    fixtures: dict[Path, bytes] = {}
    for path in EVALUATOR_FIXTURE_PATHS:
        rubric_bytes = read_git_blob(rubric_commit, path, root=root)
        tested_bytes = read_git_blob(tested_commit, path, root=root)
        if tested_bytes != rubric_bytes:
            raise ValueError(
                f"tested commit {tested_commit} differs from rubric commit "
                f"{rubric_commit} at {path.as_posix()}"
            )
        fixtures[path] = rubric_bytes
    return fixtures


def _build_codex_command(
    *,
    checkout: Path,
    output_schema: Path,
    model: str | None,
    effort: str | None,
    proxy_url: str,
    sandbox: str = READ_ONLY_SANDBOX,
) -> list[str]:
    command = [
        "codex",
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
        sandbox,
        "--json",
        "--output-schema",
        str(output_schema),
        "-C",
        str(checkout),
        "-c",
        'approval_policy="never"',
        "-c",
        f'model_provider="{ROUTING_TRIAL_PROXY_PROVIDER}"',
        "-c",
        (
            f"model_providers.{ROUTING_TRIAL_PROXY_PROVIDER}="
            '{name="ARIA-NBV routing-trial proxy",'
            f'base_url={json.dumps(proxy_url)},wire_api="responses",'
            "requires_openai_auth=false}"
        ),
    ]
    if model:
        command.extend(["--model", model])
    if effort:
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
    command.append("-")
    return command


def _read_bounded_regular_file(path: Path, *, maximum_bytes: int) -> bytes | None:
    """Read one bounded regular receipt without following a model-created link."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return None
    try:
        is_regular = stat.S_ISREG(os.fstat(descriptor).st_mode)
    except OSError:
        os.close(descriptor)
        return None
    if not is_regular:
        os.close(descriptor)
        return None
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as stream:
            return stream.read(maximum_bytes + 1)
    except OSError:
        return None


def routing_trial_proxy_url() -> str:
    """Return the required local model broker endpoint for untrusted trials."""
    value = os.environ.get(ROUTING_TRIAL_PROXY_URL_ENV)
    if not value:
        raise ValueError(
            f"routing trials require {ROUTING_TRIAL_PROXY_URL_ENV} to name a "
            "local Responses-compatible credential broker"
        )
    parsed = urlparse(value)
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("routing trial proxy URL has an invalid port") from error
    if (
        parsed.scheme != "http"
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or port is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.params
        or parsed.query
        or parsed.fragment
        or any(character.isspace() or character in {'"', "\\"} for character in value)
    ):
        raise ValueError(
            "routing trial proxy URL must be an unauthenticated http URL bound "
            "to 127.0.0.1 or ::1 with an explicit port"
        )
    return value.rstrip("/")


@contextlib.contextmanager
def broker_socket_relay(proxy_url: str) -> Any:
    """Expose exactly one host-loopback broker as a private Unix socket."""
    executable = shutil.which("socat")
    if executable is None:
        raise RuntimeError("routing trials require socat for broker isolation")
    parsed = urlparse(proxy_url)
    assert parsed.hostname is not None and parsed.port is not None
    upstream = (
        f"TCP6:[{parsed.hostname}]:{parsed.port}"
        if parsed.hostname == "::1"
        else f"TCP:{parsed.hostname}:{parsed.port}"
    )
    with tempfile.TemporaryDirectory(prefix="aria-routing-broker-") as temporary:
        socket_path = Path(temporary) / "proxy.sock"
        process = subprocess.Popen(
            [
                executable,
                f"UNIX-LISTEN:{socket_path},fork,mode=600",
                upstream,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        deadline = time.monotonic() + 5
        while not socket_path.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        if not socket_path.exists() or process.poll() is not None:
            _stop_process_group(process)
            raise RuntimeError("routing broker socket failed to start")
        try:
            yield socket_path
        finally:
            _stop_process_group(process)


def _sandboxed_codex_command(
    *,
    codex_command: list[str],
    checkout: Path,
    broker_socket: Path,
    schema_path: Path,
    sandbox: str,
) -> list[str]:
    """Run Codex without host credentials or mutable evaluator inputs."""
    if not schema_path.is_file():
        raise RuntimeError("routing trials require the canonical report schema")
    subject_bind = "--ro-bind" if sandbox == READ_ONLY_SANDBOX else "--bind"
    sandbox_command = list(codex_command)
    codex_mount: list[str] = []
    if sandbox_command[0] == "codex":
        executable = shutil.which("codex")
        if executable is None:
            raise RuntimeError("routing trials require the Codex executable")
        resolved_executable = Path(executable).resolve()
        if not resolved_executable.is_file():
            raise RuntimeError("routing trials require a regular Codex executable")
        sandbox_command[0] = "/opt/codex/codex"
        codex_mount = [
            "--dir",
            "/opt",
            "--dir",
            "/opt/codex",
            "--ro-bind",
            str(resolved_executable),
            "/opt/codex/codex",
        ]
    relay_command = [
        "/bin/sh",
        "-ec",
        (
            "socat TCP-LISTEN:43124,bind=127.0.0.1,reuseaddr,fork "
            'UNIX-CONNECT:/broker/proxy.sock & sleep 0.1; exec "$@"'
        ),
        "routing-broker-relay",
        *sandbox_command,
    ]
    return [
        "bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--clearenv",
        "--setenv",
        "PATH",
        "/usr/local/bin:/usr/bin:/bin",
        "--setenv",
        "HOME",
        "/home/codex",
        "--setenv",
        "CODEX_HOME",
        "/codex-home",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/etc",
        "/etc",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/sbin",
        "/sbin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/home",
        "--dir",
        "/home/codex",
        "--dir",
        "/codex-home",
        "--dir",
        "/schema",
        "--dir",
        "/broker",
        *codex_mount,
        "--ro-bind",
        str(schema_path),
        str(Path("/schema") / schema_path.name),
        "--ro-bind",
        str(broker_socket.parent),
        "/broker",
        subject_bind,
        str(checkout),
        "/workspace",
        "--chdir",
        "/workspace",
        *relay_command,
    ]


def execution_contract(rubric: dict[str, Any]) -> dict[str, Any]:
    """Return the bounded execution contract for one hidden routing fixture."""
    sandbox = rubric.get("execution_mode", READ_ONLY_SANDBOX)
    if sandbox not in _EXECUTION_MODES:
        raise ValueError(f"unsupported routing execution mode: {sandbox!r}")
    prefixes = rubric.get("required_changed_path_prefixes", [])
    required_paths = rubric.get("required_changed_paths", [])
    if not isinstance(prefixes, list) or not all(
        isinstance(prefix, str) and prefix for prefix in prefixes
    ):
        raise ValueError("routing changed-path prefixes must be non-empty strings")
    if not isinstance(required_paths, list) or not all(
        isinstance(path, str) and path for path in required_paths
    ):
        raise ValueError("routing changed paths must be non-empty strings")
    typst_proof = rubric.get("typst_proof", False)
    if not isinstance(typst_proof, bool):
        raise TypeError("routing typst_proof must be boolean")
    if sandbox == WORKSPACE_WRITE_SANDBOX and (
        not prefixes or not required_paths or not typst_proof
    ):
        raise ValueError(
            "workspace-write routing trials require exact source paths and Typst proof"
        )
    if sandbox == READ_ONLY_SANDBOX and (prefixes or required_paths or typst_proof):
        raise ValueError("read-only routing trials cannot require edit proof")
    return {
        "sandbox": sandbox,
        "required_changed_path_prefixes": prefixes,
        "required_changed_paths": required_paths,
        "typst_proof": typst_proof,
    }


def _changed_paths(checkout: Path, baseline_head: str) -> tuple[str, ...]:
    """Return all tracked or untracked subject paths diverging from one baseline."""
    changed = set(
        run_git("diff", "--name-only", baseline_head, cwd=checkout).splitlines()
    )
    changed.update(
        run_git("ls-files", "--others", "--exclude-standard", cwd=checkout).splitlines()
    )
    changed.update(
        run_git(
            "ls-files",
            "--others",
            "--ignored",
            "--exclude-standard",
            cwd=checkout,
        ).splitlines()
    )
    return tuple(sorted(path for path in changed if path))


def _pdf_page_count(pdf: Path) -> int | None:
    """Return a bounded Poppler page count, or ``None`` when it is unavailable."""
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf)],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    for line in result.stdout.splitlines():
        if line.startswith("Pages:"):
            try:
                count = int(line.removeprefix("Pages:").strip())
            except ValueError:
                return None
            return count if count > 0 else None
    return None


def _typst_proof_sandbox_command(
    *, checkout: Path, proof_dir: Path, command: list[str]
) -> list[str]:
    """Run trusted proof tooling against candidate Typst only inside Bubblewrap."""
    docs_root = checkout / "docs"
    typst_cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "typst"
    )
    typst_executable = shutil.which("typst")
    typst_mount: list[str] = []
    sandbox_command = list(command)
    if typst_executable is not None:
        typst_mount = [
            "--dir",
            "/opt",
            "--dir",
            "/opt/typst",
            "--ro-bind",
            str(Path(typst_executable).resolve()),
            "/opt/typst/typst",
        ]
        if sandbox_command[0] == "typst":
            sandbox_command[0] = "/opt/typst/typst"
    cache_mount = (
        ["--ro-bind", str(typst_cache), "/cache/typst"] if typst_cache.is_dir() else []
    )
    return [
        "bwrap",
        "--unshare-all",
        "--die-with-parent",
        "--clearenv",
        "--setenv",
        "PATH",
        "/opt/typst:/usr/bin:/bin",
        "--setenv",
        "XDG_CACHE_HOME",
        "/cache",
        "--ro-bind",
        "/usr",
        "/usr",
        "--ro-bind",
        "/etc",
        "/etc",
        "--symlink",
        "usr/bin",
        "/bin",
        "--symlink",
        "usr/sbin",
        "/sbin",
        "--symlink",
        "usr/lib",
        "/lib",
        "--symlink",
        "usr/lib64",
        "/lib64",
        "--proc",
        "/proc",
        "--dev",
        "/dev",
        "--tmpfs",
        "/tmp",
        "--dir",
        "/project",
        "--dir",
        "/cache",
        *typst_mount,
        *cache_mount,
        "--ro-bind",
        str(docs_root),
        "/project/docs",
        "--dir",
        "/trusted",
        "--ro-bind",
        str(TRUSTED_RENDER_SCRIPT),
        "/trusted/render_png.sh",
        "--bind",
        str(proof_dir),
        "/receipt",
        "--chdir",
        "/project",
        *sandbox_command,
    ]


def _typst_proof(checkout: Path, trial_dir: Path) -> dict[str, Any]:
    """Prove development rendering and the default submission evidence gate."""
    pdf = trial_dir / "thesis.pdf"
    pages = trial_dir / "thesis-pages"
    development_commands = (
        [
            "typst",
            "compile",
            "docs/typst/thesis/main.typ",
            "/receipt/thesis.pdf",
            "--root",
            "/project/docs",
        ],
        [
            "/trusted/render_png.sh",
            "-i",
            "docs/typst/thesis/main.typ",
            "-o",
            "/receipt/thesis-pages",
            "--root",
            "/project/docs",
            "--ppi",
            "150",
        ],
    )
    returncodes: list[int] = []
    for command in development_commands:
        try:
            result = subprocess.run(
                _typst_proof_sandbox_command(
                    checkout=checkout, proof_dir=trial_dir, command=command
                ),
                cwd=checkout,
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=180,
            )
            returncodes.append(result.returncode)
            if result.returncode:
                break
        except (OSError, subprocess.TimeoutExpired):
            returncodes.append(125)
            break
    submission_gate: dict[str, Any] = {
        "executed": False,
        "returncode": 125,
        "expected_diagnostic": False,
    }
    if returncodes == [0, 0]:
        gate_events = trial_dir / "submission-gate.events.jsonl"
        gate_stderr = trial_dir / "submission-gate.stderr"
        gate_result = _run_bounded_process(
            command=_typst_proof_sandbox_command(
                checkout=checkout,
                proof_dir=trial_dir,
                command=[
                    "typst",
                    "compile",
                    "docs/typst/thesis/main.typ",
                    "/tmp/submission-gate.pdf",
                    "--root",
                    "/project/docs",
                    "--input",
                    "aria-thesis-mode=submission",
                ],
            ),
            prompt="",
            cwd=checkout,
            events_path=gate_events,
            stderr_path=gate_stderr,
            timeout_seconds=180,
        )
        gate_diagnostic = _read_bounded_regular_file(
            gate_stderr, maximum_bytes=TRIAL_STDERR_MAX_BYTES
        )
        expected_diagnostic = False
        if gate_diagnostic is not None:
            try:
                diagnostic_lines = gate_diagnostic.decode("utf-8").splitlines()
            except UnicodeDecodeError:
                diagnostic_lines = []
            for index, line in enumerate(diagnostic_lines):
                if line == SUBMISSION_GATE_DIAGNOSTIC and any(
                    SUBMISSION_GATE_SOURCE in context
                    for context in diagnostic_lines[index + 1 : index + 4]
                ):
                    expected_diagnostic = True
                    break
        submission_gate = {
            "executed": not (
                gate_result["timed_out"]
                or gate_result["launch_error"]
                or gate_result["output_overflow"]
            ),
            "returncode": gate_result["returncode"],
            "expected_diagnostic": expected_diagnostic,
        }
    page_count = _pdf_page_count(pdf) if pdf.is_file() else None
    rendered_pages = tuple(sorted(path.name for path in pages.glob("*.png")))
    rendered_page_numbers = {
        int(path.stem) for path in pages.glob("*.png") if path.stem.isdigit()
    }
    return {
        "passed": (
            returncodes == [0, 0]
            and submission_gate["executed"]
            and submission_gate["returncode"] != 0
            and submission_gate["expected_diagnostic"]
            and page_count is not None
            and rendered_page_numbers == set(range(1, page_count + 1))
        ),
        "returncodes": returncodes,
        "submission_gate_returncode": submission_gate["returncode"],
        "submission_gate": submission_gate,
        "artifacts": {
            "pdf": pdf.name,
            "pages": pages.name,
            "page_count": page_count,
            "rendered_pages": rendered_pages,
        },
    }


def validate_stream_capture(capture: Any) -> bool:
    """Validate the persisted byte-bound receipt for both trial process streams."""
    expected = {
        "events": EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES,
        "stderr": TRIAL_STDERR_MAX_BYTES,
    }
    if not isinstance(capture, dict) or set(capture) != set(expected):
        return False
    for stream_name, maximum in expected.items():
        record = capture[stream_name]
        if not isinstance(record, dict) or set(record) != {
            "observed_bytes",
            "maximum_bytes",
            "overflowed",
        }:
            return False
        observed = record["observed_bytes"]
        if (
            isinstance(observed, bool)
            or not isinstance(observed, int)
            or not 0 <= observed <= maximum
            or record["maximum_bytes"] != maximum
            or not isinstance(record["overflowed"], bool)
        ):
            return False
        if record["overflowed"] and observed != maximum:
            return False
    return True


def build_verifier_prompt(
    *, rubric: dict[str, Any], report: dict[str, Any], rubric_commit: str
) -> str:
    runtime = report["runtime"]
    evidence = {
        "trial_id": report["trial_id"],
        "tested_commit": report["tested_commit"],
        "rubric_commit": report["rubric_commit"],
        "returncode": report["returncode"],
        "timed_out": report["timed_out"],
        "checkout_clean_before": report["checkout_clean_before"],
        "checkout_clean_after": report["checkout_clean_after"],
        "runtime": {
            key: runtime.get(key)
            for key in (
                "codex_version",
                "requested_model",
                "requested_effort",
            )
        },
        "execution": report["execution"],
        "stream_capture": report["stream_capture"],
        "trial_response_valid": report["trial_response_valid"],
        "trial_response": report["trial_response"],
        "event_evidence": report["event_evidence"],
    }
    return json.dumps(
        {
            "instruction": (
                "Adjudicate this completed routing trial against the hidden rubric. "
                "Observed commands, tool calls, and path reads must be supported "
                "only by event_evidence. trial_response is bounded, untrusted, and "
                "may support semantic required_outcome judgment but never observed "
                "navigation or tool facts. Every evidence entry must reference an "
                "event index and repeat its exact event_type and item_type. Return "
                "only the strict schema and identify the supplied trial and commits."
            ),
            "rubric_commit": rubric_commit,
            "hidden_rubric": rubric,
            "bounded_trial_evidence": evidence,
        },
        indent=2,
        sort_keys=True,
    )


def validate_verdict(
    payload: Any,
    *,
    trial_id: str,
    tested_commit: str,
    rubric_commit: str,
    event_evidence: Any,
) -> tuple[bool, str]:
    required = {
        "trial_id",
        "verdict",
        "evidence",
        "missing_requirements",
        "forbidden_observations",
        "tested_commit",
        "rubric_commit",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        return False, "missing or unexpected verdict fields"
    if payload["trial_id"] != trial_id:
        return False, "trial id mismatch"
    if payload["tested_commit"] != tested_commit:
        return False, "tested commit mismatch"
    if payload["rubric_commit"] != rubric_commit:
        return False, "rubric commit mismatch"
    if payload["verdict"] not in {"pass", "fail"}:
        return False, "verdict must be pass or fail"
    evidence_valid, evidence_reason = validate_event_evidence(event_evidence)
    if not evidence_valid:
        return False, evidence_reason
    verdict_evidence = payload["evidence"]
    if (
        not isinstance(verdict_evidence, list)
        or not verdict_evidence
        or len(verdict_evidence) > VERDICT_MAX_ITEMS
    ):
        return False, "verdict evidence must be a non-empty list"
    seen_indices: set[int] = set()
    events = event_evidence["items"]
    required_reference_fields = {"event_index", "event_type", "item_type", "claim"}
    for reference in verdict_evidence:
        if (
            not isinstance(reference, dict)
            or set(reference) != required_reference_fields
        ):
            return False, "verdict evidence reference fields are malformed"
        event_index = reference["event_index"]
        if isinstance(event_index, bool) or not isinstance(event_index, int):
            return False, "event index must be an integer"
        if event_index < 0 or event_index >= len(events):
            return False, "event index is out of range"
        if event_index in seen_indices:
            return False, "event indices must be unique"
        seen_indices.add(event_index)
        event = events[event_index]
        if reference["event_type"] != event["event_type"]:
            return False, "event type does not match referenced evidence"
        if reference["item_type"] != event["item_type"]:
            return False, "item type does not match referenced evidence"
        if (
            not isinstance(reference["claim"], str)
            or not reference["claim"]
            or len(reference["claim"]) > EVENT_EVIDENCE_MAX_FIELD_CHARS
        ):
            return False, "evidence claim must be a non-empty string"
    for field in ("missing_requirements", "forbidden_observations"):
        values = payload[field]
        if (
            not isinstance(values, list)
            or len(values) > VERDICT_MAX_ITEMS
            or not all(
                isinstance(item, str) and len(item) <= EVENT_EVIDENCE_MAX_FIELD_CHARS
                for item in values
            )
        ):
            return False, f"{field} must be a list of strings"
    if payload["verdict"] == "pass" and (
        payload["missing_requirements"] or payload["forbidden_observations"]
    ):
        return False, "pass verdict contains failures"
    return True, "pass" if payload["verdict"] == "pass" else "semantic fail"


def run_verifier(
    *,
    report: dict[str, Any],
    rubric: dict[str, Any],
    rubric_commit: str,
    trial_dir: Path,
    model: str | None,
    effort: str | None,
    proxy_url: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    verifier_events = trial_dir / "verifier-events.jsonl"
    verifier_stderr = trial_dir / "verifier-stderr.txt"
    artifacts = {
        "events": verifier_events.name,
        "stderr": verifier_stderr.name,
    }
    failure_reason: str | None = None
    if report.get("rubric_commit") != rubric_commit:
        failure_reason = "trial report rubric commit mismatch"
    elif report.get("trial_response_valid") is not True:
        failure_reason = "trial response does not match the canonical schema"
    else:
        evidence_valid, evidence_reason = validate_event_evidence(
            report.get("event_evidence")
        )
        if not evidence_valid:
            failure_reason = evidence_reason
    if failure_reason is not None:
        return {
            "passed": False,
            "reason": failure_reason,
            "timed_out": False,
            "returncode": 125,
            "verdict": None,
            "artifacts": artifacts,
        }
    command = _build_codex_command(
        checkout=Path("/workspace"),
        output_schema=Path("/schema/routing_verdict.schema.json"),
        model=model,
        effort=effort,
        proxy_url=SANDBOX_PROXY_URL,
    )
    with (
        tempfile.TemporaryDirectory(prefix="aria-routing-evaluator-") as temporary,
        broker_socket_relay(proxy_url) as broker_socket,
    ):
        evaluator_checkout = Path(temporary) / "workspace"
        evaluator_checkout.mkdir()
        command = _sandboxed_codex_command(
            codex_command=command,
            checkout=evaluator_checkout,
            broker_socket=broker_socket,
            schema_path=VERIFIER_SCHEMA,
            sandbox=READ_ONLY_SANDBOX,
        )
        process_result = _run_bounded_process(
            command=command,
            prompt=build_verifier_prompt(
                rubric=rubric[report["trial_id"]],
                report=report,
                rubric_commit=rubric_commit,
            ),
            cwd=ROOT,
            events_path=verifier_events,
            stderr_path=verifier_stderr,
            timeout_seconds=timeout_seconds,
        )
    timed_out = process_result["timed_out"]
    returncode = process_result["returncode"]
    payload: Any = None
    verdict_read_error: str | None = None
    if not timed_out:
        verdict_text, stream_truncated = read_last_agent_message(verifier_events)
        if verdict_text is None:
            verdict_read_error = "verifier report is unreadable or malformed"
        elif stream_truncated:
            verdict_read_error = "verifier report exceeds the byte bound"
        else:
            try:
                verdict_bytes = verdict_text.encode("utf-8")
                if len(verdict_bytes) > VERIFIER_REPORT_MAX_BYTES:
                    verdict_read_error = "verifier report exceeds the byte bound"
                else:
                    payload = json.loads(verdict_text)
            except (json.JSONDecodeError, UnicodeError):
                verdict_read_error = "verifier report is unreadable or malformed"
    if process_result["output_overflow"]:
        valid, reason = False, "verifier output exceeded its byte bound"
    elif returncode != 0 or timed_out:
        valid, reason = False, "verifier timed out or failed"
    elif verdict_read_error is not None:
        valid, reason = False, verdict_read_error
    else:
        valid, reason = validate_verdict(
            payload,
            trial_id=report["trial_id"],
            tested_commit=report["tested_commit"],
            rubric_commit=rubric_commit,
            event_evidence=report.get("event_evidence"),
        )
    if valid and payload["verdict"] != "pass":
        valid = False
    return {
        "passed": valid,
        "reason": reason,
        "timed_out": timed_out,
        "returncode": returncode,
        "verdict": payload,
        "stream_capture": process_result["stream_capture"],
        "artifacts": artifacts,
    }


def trial_passed(report: dict[str, Any]) -> bool:
    """Return whether one trial satisfies its bounded execution contract."""
    evidence_valid, _ = validate_event_evidence(report.get("event_evidence"))
    execution = report.get("execution")
    if not isinstance(execution, dict):
        return False
    sandbox = execution.get("sandbox")
    baseline_head = execution.get("baseline_head")
    head_after = execution.get("head_after")
    changed_paths = execution.get("changed_paths")
    prefixes = execution.get("required_changed_path_prefixes")
    required_paths = execution.get("required_changed_paths")
    proof = execution.get("typst_proof")
    if (
        sandbox not in _EXECUTION_MODES
        or not isinstance(baseline_head, str)
        or not baseline_head
        or not isinstance(head_after, str)
        or not head_after
        or not isinstance(changed_paths, list)
        or not all(isinstance(path, str) for path in changed_paths)
        or not isinstance(prefixes, list)
        or not all(isinstance(prefix, str) for prefix in prefixes)
        or not isinstance(required_paths, list)
        or not all(isinstance(path, str) for path in required_paths)
    ):
        return False
    if sandbox == READ_ONLY_SANDBOX:
        execution_valid = (
            report.get("checkout_clean_after")
            and head_after == baseline_head
            and not prefixes
            and not required_paths
            and proof is None
            and not changed_paths
        )
    else:
        execution_valid = (
            bool(prefixes)
            and bool(required_paths)
            and head_after == baseline_head
            and all(
                any(path.startswith(prefix) for path in changed_paths)
                for prefix in prefixes
            )
            and all(
                any(path.startswith(prefix) for prefix in prefixes)
                for path in changed_paths
            )
            and all(path in changed_paths for path in required_paths)
            and isinstance(proof, dict)
            and proof.get("passed") is True
        )
    return bool(
        report.get("returncode") == 0
        and report.get("checkout_clean_before")
        and not report.get("output_overflow", False)
        and validate_stream_capture(report.get("stream_capture"))
        and report.get("trial_response_valid") is True
        and execution_valid
        and evidence_valid
        and report.get("adjudication", {}).get("passed", False)
    )


def _truncate_evidence_field(
    value: Any,
) -> tuple[str | int | float | bool | None, bool]:
    if value is None or isinstance(value, (int, float, bool)):
        return value, False
    if isinstance(value, str):
        text = value
    else:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
    if len(text) <= EVENT_EVIDENCE_MAX_FIELD_CHARS:
        return text, False
    keep = EVENT_EVIDENCE_MAX_FIELD_CHARS - len(_TRUNCATION_SUFFIX)
    return text[:keep] + _TRUNCATION_SUFFIX, True


def _has_observed_identity(item_type: Any, source: dict[str, Any]) -> bool:
    if not isinstance(item_type, str):
        return False
    identity_fields = _EXECUTION_IDENTITY_FIELDS.get(
        item_type, _GENERIC_EXECUTION_IDENTITY_FIELDS
    )
    return any(
        isinstance(value, str) and bool(value.strip())
        for value in (source.get(field) for field in identity_fields)
    )


def _event_evidence_record(
    event: Any,
) -> tuple[dict[str, Any] | None, int, bool]:
    if not isinstance(event, dict):
        return None, 0, False
    item = event.get("item")
    source = item if isinstance(item, dict) else event
    item_type = source.get("type")
    if not isinstance(item_type, str):
        return None, 0, False
    present_fields = [field for field in _EVIDENCE_FIELDS if field in source]
    if not _has_observed_identity(item_type, source):
        return None, 0, item_type in _EXECUTION_IDENTITY_FIELDS

    record: dict[str, Any] = {}
    if isinstance(event.get("type"), str):
        record["event_type"], truncated = _truncate_evidence_field(event["type"])
        field_truncations = int(truncated)
    else:
        return None, 0, False
    if isinstance(item_type, str):
        record["item_type"], truncated = _truncate_evidence_field(item_type)
        field_truncations += int(truncated)
    else:
        return None, 0, False
    for field in present_fields:
        bounded, truncated = _truncate_evidence_field(source[field])
        record[field] = bounded
        field_truncations += int(truncated)
    return record, field_truncations, False


def extract_event_evidence(path: Path) -> dict[str, Any]:
    """Extract deterministic execution evidence from a bounded raw stream."""
    items: list[dict[str, Any]] = []
    malformed_lines = 0
    invalid_items = 0
    dropped_items = 0
    field_truncations = 0
    payload_chars = 2  # JSON list brackets.
    read_error = False
    try:
        with path.open("rb") as stream:
            raw_bytes = 0
            while True:
                remaining = EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES - raw_bytes
                if remaining <= 0:
                    if stream.read(1):
                        dropped_items += 1
                    break
                raw_line = stream.readline(
                    min(remaining, EVENT_EVIDENCE_MAX_RAW_LINE_BYTES) + 1
                )
                if not raw_line:
                    break
                if (
                    len(raw_line) > EVENT_EVIDENCE_MAX_RAW_LINE_BYTES
                    or len(raw_line) > remaining
                ):
                    dropped_items += 1
                    break
                raw_bytes += len(raw_line)
                try:
                    line = raw_line.decode("utf-8")
                except UnicodeError:
                    read_error = True
                    break
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    malformed_lines += 1
                    continue
                record, truncated_fields, invalid = _event_evidence_record(event)
                field_truncations += truncated_fields
                invalid_items += int(invalid)
                if record is None:
                    continue
                serialized = json.dumps(record, sort_keys=True, separators=(",", ":"))
                item_chars = len(serialized) + int(bool(items))
                if (
                    len(items) >= EVENT_EVIDENCE_MAX_ITEMS
                    or payload_chars + item_chars > EVENT_EVIDENCE_MAX_TOTAL_CHARS
                ):
                    dropped_items += 1
                    continue
                items.append(record)
                payload_chars += item_chars
    except OSError:
        read_error = True
    while True:
        indexed_items = [
            {**item, "event_index": index} for index, item in enumerate(items)
        ]
        indexed_payload = json.dumps(
            indexed_items, sort_keys=True, separators=(",", ":")
        )
        result = {
            "bounds": {
                "max_items": EVENT_EVIDENCE_MAX_ITEMS,
                "max_field_chars": EVENT_EVIDENCE_MAX_FIELD_CHARS,
                "max_total_chars": EVENT_EVIDENCE_MAX_TOTAL_CHARS,
            },
            "items": indexed_items,
            "payload_chars": len(indexed_payload),
            "malformed_lines": malformed_lines,
            "invalid_items": invalid_items,
            "dropped_items": dropped_items,
            "field_truncations": field_truncations,
            "truncated": bool(dropped_items or field_truncations),
            "read_error": read_error,
        }
        serialized_result = json.dumps(result, sort_keys=True, separators=(",", ":"))
        if len(serialized_result) <= EVENT_EVIDENCE_MAX_TOTAL_CHARS or not items:
            return result
        items.pop()
        dropped_items += 1
        payload_chars = len(json.dumps(items, sort_keys=True, separators=(",", ":")))


def validate_event_evidence(evidence: Any) -> tuple[bool, str]:
    required = {
        "bounds",
        "items",
        "payload_chars",
        "malformed_lines",
        "invalid_items",
        "dropped_items",
        "field_truncations",
        "truncated",
        "read_error",
    }
    if not isinstance(evidence, dict) or set(evidence) != required:
        return False, "raw event evidence is absent or malformed"
    expected_bounds = {
        "max_items": EVENT_EVIDENCE_MAX_ITEMS,
        "max_field_chars": EVENT_EVIDENCE_MAX_FIELD_CHARS,
        "max_total_chars": EVENT_EVIDENCE_MAX_TOTAL_CHARS,
    }
    if evidence["bounds"] != expected_bounds:
        return False, "raw event evidence bounds are invalid"
    counters = (
        "payload_chars",
        "malformed_lines",
        "invalid_items",
        "dropped_items",
        "field_truncations",
    )
    if any(
        isinstance(evidence[field], bool)
        or not isinstance(evidence[field], int)
        or evidence[field] < 0
        for field in counters
    ):
        return False, "raw event evidence counters are invalid"
    if not isinstance(evidence["read_error"], bool) or not isinstance(
        evidence["truncated"], bool
    ):
        return False, "raw event evidence flags are invalid"
    items = evidence["items"]
    if not isinstance(items, list) or not items:
        return False, "raw event evidence is empty"
    if len(items) > EVENT_EVIDENCE_MAX_ITEMS:
        return False, "raw event evidence exceeds the item bound"
    allowed_item_fields = {"event_index", "event_type", "item_type", *_EVIDENCE_FIELDS}
    for event_index, item in enumerate(items):
        if not isinstance(item, dict) or not {"event_type", "item_type"} <= set(item):
            return False, "raw event evidence item identity is malformed"
        if not set(item) <= allowed_item_fields:
            return False, "raw event evidence item fields are malformed"
        if item.get("event_index") != event_index:
            return False, "raw event evidence item index is malformed"
        for value in item.values():
            if not isinstance(value, (str, int, float, bool, type(None))):
                return False, "raw event evidence field type is malformed"
            if isinstance(value, str) and len(value) > EVENT_EVIDENCE_MAX_FIELD_CHARS:
                return False, "raw event evidence field exceeds its bound"
            if isinstance(value, str) and value.endswith(_TRUNCATION_SUFFIX):
                return False, "raw event evidence contains a truncated field"
        if not isinstance(item["event_type"], str) or not item["event_type"]:
            return False, "raw event evidence event type is malformed"
        if not isinstance(item["item_type"], str) or not item["item_type"]:
            return False, "raw event evidence item type is malformed"
        if not _has_observed_identity(item["item_type"], item):
            return False, "raw event evidence item identity is missing"
    payload = json.dumps(items, sort_keys=True, separators=(",", ":"))
    if evidence["payload_chars"] != len(payload):
        return False, "raw event evidence payload length is inconsistent"
    serialized = json.dumps(evidence, sort_keys=True, separators=(",", ":"))
    if len(serialized) > EVENT_EVIDENCE_MAX_TOTAL_CHARS:
        return False, "raw event evidence exceeds the total bound"
    incomplete = (
        evidence["read_error"]
        or evidence["malformed_lines"]
        or evidence["invalid_items"]
        or evidence["dropped_items"]
        or evidence["field_truncations"]
        or evidence["truncated"]
    )
    if incomplete:
        return False, "raw event evidence is incomplete"
    return True, "complete raw event evidence"


def bound_trial_response(
    value: Any, *, force_truncated: bool = False
) -> dict[str, Any]:
    if isinstance(value, str):
        text = value
        response_format = "text"
    else:
        text = json.dumps(value, sort_keys=True, separators=(",", ":"))
        response_format = "json"
    truncated = force_truncated or len(text) > TRIAL_RESPONSE_MAX_CHARS
    if truncated:
        keep = TRIAL_RESPONSE_MAX_CHARS - len(_TRUNCATION_SUFFIX)
        text = text[:keep] + _TRUNCATION_SUFFIX
    return {
        "label": "untrusted_trial_response",
        "format": response_format,
        "content": text,
        "max_chars": TRIAL_RESPONSE_MAX_CHARS,
        "truncated": truncated,
    }


def read_last_agent_message(path: Path) -> tuple[str | None, bool]:
    """Return the bounded terminal agent message from host-captured JSONL."""
    raw = _read_bounded_regular_file(
        path, maximum_bytes=EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES
    )
    if raw is None:
        return None, False
    stream_truncated = len(raw) > EVENT_EVIDENCE_MAX_RAW_STREAM_BYTES
    try:
        lines = raw.decode("utf-8").splitlines()
    except UnicodeError:
        return None, stream_truncated
    terminal_index = len(lines) - 1
    while terminal_index >= 0 and not lines[terminal_index].strip():
        terminal_index -= 1
    if terminal_index < 0:
        return None, stream_truncated
    try:
        terminal_event = json.loads(lines[terminal_index])
    except json.JSONDecodeError:
        return None, stream_truncated
    if (
        not isinstance(terminal_event, dict)
        or terminal_event.get("type") != "turn.completed"
    ):
        return None, stream_truncated
    parsed_events: list[dict[str, Any] | None] = []
    for line in lines[:terminal_index]:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            parsed_events.append(None)
            continue
        parsed_events.append(event if isinstance(event, dict) else None)
    for index in range(terminal_index - 1, -1, -1):
        event = parsed_events[index]
        if event is None:
            continue
        item = event.get("item") if isinstance(event, dict) else None
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            if any(line.strip() for line in lines[index + 1 : terminal_index]):
                return None, stream_truncated
            return item["text"], stream_truncated
    return None, stream_truncated


def read_trial_response_from_events(path: Path) -> tuple[dict[str, Any], bool]:
    """Validate the terminal model message without a model-writable receipt."""
    text, stream_truncated = read_last_agent_message(path)
    if text is None:
        return bound_trial_response({"unavailable": True}), False
    force_truncated = stream_truncated or len(text) > TRIAL_RESPONSE_MAX_CHARS
    try:
        value: Any = json.loads(text)
    except json.JSONDecodeError:
        return bound_trial_response(text, force_truncated=force_truncated), False
    response = bound_trial_response(value, force_truncated=force_truncated)
    return response, validate_trial_response(value, truncated=force_truncated)


def validate_trial_response(value: Any, *, truncated: bool = False) -> bool:
    """Validate the untrusted model receipt against the canonical local contract."""
    try:
        schema = json.loads(REPORT_SCHEMA.read_text(encoding="utf-8"))
        required = set(schema["required"])
        properties = schema["properties"]
    except (json.JSONDecodeError, KeyError, OSError, TypeError):
        return False
    if (
        truncated
        or schema.get("additionalProperties") is not False
        or not isinstance(value, dict)
        or set(value) != required
        or set(properties) != required
    ):
        return False
    for field, definition in properties.items():
        if not isinstance(definition, dict):
            return False
        allowed_types = definition.get("type")
        if isinstance(allowed_types, str):
            allowed = {allowed_types}
        elif isinstance(allowed_types, list) and all(
            isinstance(kind, str) for kind in allowed_types
        ):
            allowed = set(allowed_types)
        else:
            return False
        item = value[field]
        if item is None:
            if "null" not in allowed:
                return False
        elif isinstance(item, str):
            if "string" not in allowed:
                return False
        elif isinstance(item, list):
            items = definition.get("items")
            if (
                "array" not in allowed
                or not isinstance(items, dict)
                or items.get("type") != "string"
                or not all(isinstance(member, str) for member in item)
            ):
                return False
        else:
            return False
    return True


def run_trial(
    *,
    trial_id: str,
    task: str,
    head: str,
    rubric_commit: str,
    rubric: dict[str, Any],
    checkout: Path,
    output_dir: Path,
    codex_version: str,
    model: str | None,
    effort: str | None,
    proxy_url: str,
    timeout_seconds: int,
) -> dict[str, Any]:
    trial_dir = output_dir / trial_id
    trial_dir.mkdir(parents=True, exist_ok=False)
    events_path = trial_dir / "events.jsonl"
    stderr_path = trial_dir / "stderr.txt"
    final_report = trial_dir / "report.json"
    contract = execution_contract(rubric)
    codex_command = _build_codex_command(
        checkout=Path("/workspace"),
        output_schema=Path("/schema/routing_trial_report.schema.json"),
        model=model,
        effort=effort,
        proxy_url=SANDBOX_PROXY_URL,
        sandbox=contract["sandbox"],
    )
    baseline_head = run_git("rev-parse", "HEAD", cwd=checkout)
    changed_before = _changed_paths(checkout, baseline_head)
    started = time.time()
    with broker_socket_relay(proxy_url) as broker_socket:
        command = _sandboxed_codex_command(
            codex_command=codex_command,
            checkout=checkout,
            broker_socket=broker_socket,
            schema_path=REPORT_SCHEMA,
            sandbox=contract["sandbox"],
        )
        process_result = _run_bounded_process(
            command=command,
            prompt=task,
            cwd=checkout,
            events_path=events_path,
            stderr_path=stderr_path,
            timeout_seconds=timeout_seconds,
        )
    head_after = run_git("rev-parse", "HEAD", cwd=checkout)
    changed_after = _changed_paths(checkout, baseline_head)
    proof = None
    if contract["typst_proof"]:
        expected_change = all(
            any(path.startswith(prefix) for path in changed_after)
            for prefix in contract["required_changed_path_prefixes"]
        ) and all(path in changed_after for path in contract["required_changed_paths"])
        proof = (
            _typst_proof(checkout, trial_dir)
            if (
                expected_change
                and process_result["returncode"] == 0
                and not process_result["timed_out"]
                and not process_result["output_overflow"]
                and not process_result["launch_error"]
            )
            else {"passed": False}
        )
    runtime = {
        "codex_version": codex_version,
        "requested_model": model,
        "requested_effort": effort,
        "command_flags": codex_command[1:-1],
    }
    trial_response, trial_response_valid = read_trial_response_from_events(events_path)
    report = {
        "trial_id": trial_id,
        "prompt_sha256": hashlib.sha256(task.encode()).hexdigest(),
        "tested_commit": head,
        "rubric_commit": rubric_commit,
        "runtime": runtime,
        "event_evidence": extract_event_evidence(events_path),
        "started_unix": started,
        "elapsed_seconds": time.time() - started,
        "returncode": process_result["returncode"],
        "timed_out": process_result["timed_out"],
        "output_overflow": process_result["output_overflow"],
        "checkout_clean_before": not changed_before,
        "checkout_clean_after": head_after == baseline_head and not changed_after,
        "stream_capture": process_result["stream_capture"],
        "trial_response_valid": trial_response_valid,
        "execution": {
            **contract,
            "baseline_head": baseline_head,
            "head_after": head_after,
            "changed_paths": list(changed_after),
            "typst_proof": proof,
        },
        "artifacts": {
            "events": events_path.name,
            "stderr": stderr_path.name,
            "trial_response": events_path.name,
        },
        "trial_response": trial_response,
    }
    final_report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return report


def _subject_worktree_admin_dir(checkout: Path) -> Path:
    """Return the linked-worktree administration directory for one subject."""
    git_pointer = checkout / ".git"
    if not git_pointer.is_file():
        raise ValueError("routing subject checkout has no detachable Git pointer")
    prefix = "gitdir: "
    pointer = git_pointer.read_text(encoding="utf-8").strip()
    if not pointer.startswith(prefix):
        raise ValueError("routing subject checkout has an invalid Git pointer")
    return (checkout / pointer.removeprefix(prefix)).resolve()


def prepare_subject_checkout(checkout: Path) -> None:
    """Detach a disposable subject repository from evaluator fixtures and history."""
    for relative_path in EVALUATOR_FIXTURE_PATHS:
        path = checkout / relative_path
        if not path.is_file():
            raise ValueError(
                f"cannot hide evaluator fixture: {relative_path.as_posix()}"
            )
    for relative_path in EVALUATOR_EXCLUDED_PATHS:
        path = checkout / relative_path
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()
    (checkout / ".git").unlink()
    subprocess.run(["git", "init", "-q"], cwd=checkout, check=True)
    subprocess.run(
        ["git", "config", "user.email", "routing-subject@example.invalid"],
        cwd=checkout,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Routing Subject"], cwd=checkout, check=True
    )
    subprocess.run(["git", "add", "--all"], cwd=checkout, check=True)
    subprocess.run(
        ["git", "commit", "-qm", "isolated routing subject"],
        cwd=checkout,
        check=True,
    )


def remove_subject_checkout(
    checkout: Path,
    *,
    subject_root: Path,
    worktree_admin_dir: Path,
    repository: Path = ROOT,
) -> None:
    """Remove one detached subject and only its linked-worktree registration."""
    resolved_checkout = checkout.resolve()
    if not resolved_checkout.is_relative_to(subject_root.resolve()):
        raise ValueError("routing subject escapes its temporary directory")
    common_dir = Path(
        run_git(
            "rev-parse", "--path-format=absolute", "--git-common-dir", cwd=repository
        )
    ).resolve()
    expected_parent = common_dir / "worktrees"
    if worktree_admin_dir.parent != expected_parent:
        raise ValueError(
            "routing subject registration escapes the repository worktree area"
        )
    if checkout.exists():
        if not checkout.is_dir():
            raise ValueError(f"routing subject is not a directory: {checkout}")
        shutil.rmtree(checkout)
    if worktree_admin_dir.exists():
        shutil.rmtree(worktree_admin_dir)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--head", default="HEAD", help="Exact commit-ish to test.")
    parser.add_argument(
        "--id", action="append", dest="ids", help="Trial ID; repeat to select several."
    )
    parser.add_argument("--all", action="store_true", help="Run every frozen prompt.")
    parser.add_argument(
        "--academic-authoring",
        action="store_true",
        help="Run the focused academic-authoring routing suite.",
    )
    parser.add_argument("--list", action="store_true", help="List default trial IDs.")
    parser.add_argument(
        "--model", help="Explicit Codex model; otherwise inherit config."
    )
    parser.add_argument(
        "--effort", help="Explicit reasoning effort; otherwise inherit config."
    )
    parser.add_argument(
        "--jobs", type=int, default=1, help="Concurrent isolated routing trials."
    )
    parser.add_argument("--timeout", type=int, default=600, help="Seconds per trial.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    tested_commit = run_git("rev-parse", args.head)
    rubric_commit = run_git("rev-parse", "HEAD")
    try:
        fixture_bytes = attest_evaluator_fixtures(
            tested_commit=tested_commit,
            rubric_commit=rubric_commit,
        )
    except ValueError as error:
        raise SystemExit(str(error)) from error
    prompts = load_prompts(fixture_bytes[PROMPTS_RELATIVE])
    rubric = load_rubric(fixture_bytes[RUBRIC_RELATIVE])
    if set(prompts) != set(rubric):
        raise SystemExit("routing prompt and rubric ID sets differ")
    try:
        selected = select_trial_ids(args, prompts)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    unknown = sorted(set(selected) - set(prompts))
    if unknown:
        raise SystemExit(f"unknown trial IDs: {unknown}")
    if args.list:
        print("\n".join(selected))
        return 0
    if args.jobs < 1:
        raise SystemExit("--jobs must be positive")
    if shutil.which("bwrap") is None:
        raise SystemExit("routing trials require Bubblewrap (bwrap)")
    try:
        proxy_url = routing_trial_proxy_url()
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if run_git("status", "--porcelain"):
        raise SystemExit("commit the candidate before routing trials")

    short_head = tested_commit[:12]
    short_rubric = rubric_commit[:12]
    output_dir = (
        ROOT / ".agents" / "work" / "routing-trials" / f"{short_head}-{short_rubric}"
    )
    if output_dir.exists():
        raise SystemExit(f"trial output already exists: {output_dir}")
    output_dir.mkdir(parents=True)
    codex_version = subprocess.run(
        ["codex", "--version"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()

    with tempfile.TemporaryDirectory(prefix=f"aria-routing-{short_head}-") as temp:
        checkouts = {
            trial_id: Path(temp) / f"checkout-{trial_id}" for trial_id in selected
        }
        registrations: dict[Path, Path] = {}
        try:
            for checkout in checkouts.values():
                run_git("worktree", "add", "--detach", str(checkout), tested_commit)
                registrations[checkout] = _subject_worktree_admin_dir(checkout)
                prepare_subject_checkout(checkout)
            reports: list[dict[str, Any]] = []
            with ThreadPoolExecutor(max_workers=args.jobs) as executor:
                futures = {
                    executor.submit(
                        run_trial,
                        trial_id=trial_id,
                        task=prompts[trial_id],
                        head=tested_commit,
                        rubric_commit=rubric_commit,
                        rubric=rubric[trial_id],
                        checkout=checkouts[trial_id],
                        output_dir=output_dir,
                        codex_version=codex_version,
                        model=args.model,
                        effort=args.effort,
                        proxy_url=proxy_url,
                        timeout_seconds=args.timeout,
                    ): trial_id
                    for trial_id in selected
                }
                for future in as_completed(futures):
                    trial_id = futures[future]
                    report = future.result()
                    reports.append(report)
                    print(
                        f"{trial_id}: returncode={report['returncode']} "
                        f"clean={report['checkout_clean_after']}"
                    )
            for report in reports:
                adjudication = run_verifier(
                    report=report,
                    rubric=rubric,
                    rubric_commit=rubric_commit,
                    trial_dir=output_dir / report["trial_id"],
                    model=args.model,
                    effort=args.effort,
                    proxy_url=proxy_url,
                    timeout_seconds=args.timeout,
                )
                report["adjudication"] = adjudication
                (output_dir / report["trial_id"] / "report.json").write_text(
                    json.dumps(report, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8",
                )
                print(f"{report['trial_id']}: verdict={adjudication['reason']}")
        finally:
            for checkout, registration in registrations.items():
                remove_subject_checkout(
                    checkout,
                    subject_root=Path(temp),
                    worktree_admin_dir=registration,
                )

    index = {
        "tested_commit": tested_commit,
        "rubric_commit": rubric_commit,
        "codex_version": codex_version,
        "trial_ids": list(selected),
        "reports": [
            {
                "trial_id": report["trial_id"],
                "returncode": report["returncode"],
                "timed_out": report["timed_out"],
                "checkout_clean_after": report["checkout_clean_after"],
                "execution": report["execution"],
                "stream_capture": report["stream_capture"],
                "adjudicated": report.get("adjudication", {}).get("passed", False),
                "verdict": report.get("adjudication", {}).get("verdict"),
                "report": f"{report['trial_id']}/report.json",
            }
            for report in sorted(reports, key=lambda value: value["trial_id"])
        ],
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if all(trial_passed(report) for report in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
