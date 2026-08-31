#!/usr/bin/env python3
"""Report read-only Git checkout and optional scaffold readiness status."""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, TypedDict

from git_env_contract import environment_without_inherited_git_overrides

SCRIPT = Path(__file__).resolve()
FRESHNESS_CHECKER = SCRIPT.with_name("check_graphify_freshness.py")
State = Literal[
    "healthy", "unavailable", "uninitialized", "stale", "unusable", "not-applicable"
]
Kind = Literal["bare", "primary", "linked", "standalone", "unavailable"]


class ProbeStatus(TypedDict):
    """Stable status for a capability probe."""

    state: State
    details: list[str]
    next_action: str | None


class UpstreamStatus(ProbeStatus):
    name: str | None
    ahead: int | None
    behind: int | None


class RuntimeStatus(ProbeStatus):
    path: str | None


class RegistrationStatus(TypedDict):
    state: Literal["registered", "unregistered", "unavailable", "not-applicable"]
    details: list[str]
    next_action: str | None
    worktrees: list[str]


class DirtyStatus(TypedDict):
    """Stable working-tree state."""

    state: Literal["clean", "dirty", "unavailable", "not-applicable"]
    details: list[str]
    next_action: str | None


class RepositoryStatus(TypedDict):
    root: str
    bare: bool
    kind: Kind
    registration: RegistrationStatus
    branch: str | None
    branch_state: Literal[
        "named", "detached", "unborn", "unavailable", "not-applicable"
    ]
    symbolic_head: str | None
    head: str | None
    head_state: Literal["present", "unborn", "unavailable", "not-applicable"]
    upstream: UpstreamStatus
    dirty: DirtyStatus
    git_directory: str | None
    common_git_directory: str | None
    warning: str | None


class ReadinessStatus(TypedDict):
    runtime: RuntimeStatus
    submodules: ProbeStatus


class GraphifyStatus(ProbeStatus):
    pass


class StatusResult(TypedDict):
    repository: RepositoryStatus
    readiness: ReadinessStatus
    graphify: GraphifyStatus


class ErrorStatus(TypedDict):
    code: str
    message: str
    details: list[str]
    next_action: str | None


class StatusEnvelope(TypedDict):
    schema_version: Literal[1]
    ok: bool
    result: StatusResult | None
    error: ErrorStatus | None


@dataclass(frozen=True)
class ProbeResult:
    """Preserve a subprocess result without interpreting failure as absence."""

    returncode: int
    stdout: str
    stderr: str


class GitBoundary:
    """Run every Git probe with lock-free, deterministic repository discovery."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()
        self.env = environment_without_inherited_git_overrides()
        self.env["GIT_OPTIONAL_LOCKS"] = "0"
        self.env["GIT_CONFIG_NOSYSTEM"] = "1"
        self.env["GIT_CONFIG_GLOBAL"] = os.devnull
        self.env["GIT_CONFIG_COUNT"] = "2"
        self.env["GIT_CONFIG_KEY_0"] = "core.fsmonitor"
        self.env["GIT_CONFIG_VALUE_0"] = "false"
        self.env["GIT_CONFIG_KEY_1"] = "core.untrackedCache"
        self.env["GIT_CONFIG_VALUE_1"] = "false"

    def run(self, *args: str, git_dir: Path | None = None) -> ProbeResult:
        """Run one Git command and preserve its complete result."""
        command = ["git"]
        if git_dir is not None:
            command.append(f"--git-dir={git_dir}")
        command.extend(args)
        result = subprocess.run(
            command,
            cwd=self.path,
            check=False,
            capture_output=True,
            text=True,
            env=self.env,
        )
        return ProbeResult(result.returncode, result.stdout, result.stderr)


def _text(result: ProbeResult) -> str:
    """Return stdout without hiding a failed probe's diagnostic stream."""
    return result.stdout.strip()


def _details(result: ProbeResult) -> list[str]:
    values = [
        line
        for line in (result.stderr.strip() or result.stdout.strip()).splitlines()
        if line
    ]
    return values or [f"git probe exited with status {result.returncode}"]


def _graphify_process_details(result: ProbeResult) -> list[str]:
    details = [f"Graphify admission probe exit status: {result.returncode}"]
    if stdout := result.stdout.strip():
        details.append(f"Graphify admission probe stdout: {stdout}")
    if stderr := result.stderr.strip():
        details.append(f"Graphify admission probe stderr: {stderr}")
    return details


def _command(path: Path, *args: str) -> str:
    return shlex.join(["git", "-C", str(path), *args])


def _graphify_command(path: Path, *args: str) -> str:
    return f"cd {shlex.quote(str(path))} && {shlex.join(args)}"


def _probe_failure(
    result: ProbeResult, *, next_action: str | None = None
) -> ProbeStatus:
    return {
        "state": "unavailable",
        "details": _details(result),
        "next_action": next_action,
    }


def _registered_worktrees(
    boundary: GitBoundary, common: Path
) -> tuple[ProbeResult, list[Path]]:
    result = boundary.run("worktree", "list", "--porcelain", git_dir=common)
    if result.returncode:
        return result, []
    paths = [
        Path(line.removeprefix("worktree ")).resolve()
        for line in result.stdout.splitlines()
        if line.startswith("worktree ")
    ]
    return result, paths


def _upstream_status(
    state: Literal["healthy", "unavailable", "not-applicable"],
    *,
    details: list[str],
    next_action: str | None,
    name: str | None = None,
    ahead: int | None = None,
    behind: int | None = None,
) -> UpstreamStatus:
    return {
        "state": state,
        "details": details,
        "next_action": next_action,
        "name": name,
        "ahead": ahead,
        "behind": behind,
    }


def _upstream(
    boundary: GitBoundary, branch: str | None, *, bare: bool
) -> UpstreamStatus:
    if bare:
        return _upstream_status(
            "not-applicable",
            details=["bare repositories do not have a working-tree upstream"],
            next_action=None,
        )
    if branch is None:
        return _upstream_status(
            "unavailable",
            details=["detached HEAD has no branch upstream"],
            next_action=_command(boundary.path, "branch", "--show-current"),
        )
    upstream_result = boundary.run(
        "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"
    )
    upstream = _text(upstream_result)
    if upstream_result.returncode:
        remote_ref_result = boundary.run(
            "show-ref", "--verify", "--quiet", f"refs/remotes/origin/{branch}"
        )
        next_action = (
            _command(
                boundary.path,
                "branch",
                "--set-upstream-to=origin/" + branch,
                branch,
            )
            if remote_ref_result.returncode == 0
            else _command(boundary.path, "remote", "-v")
        )
        return _upstream_status(
            "unavailable",
            details=_details(upstream_result)
            + (
                [] if remote_ref_result.returncode == 0 else _details(remote_ref_result)
            ),
            next_action=next_action,
        )
    counts_result = boundary.run(
        "rev-list", "--left-right", "--count", f"HEAD...{upstream}"
    )
    counts = counts_result.stdout.split()
    if (
        counts_result.returncode
        or len(counts) != 2
        or not all(value.isdigit() for value in counts)
    ):
        return _upstream_status(
            "unavailable",
            details=_details(counts_result),
            next_action=_command(
                boundary.path,
                "rev-list",
                "--left-right",
                "--count",
                f"HEAD...{upstream}",
            ),
            name=upstream,
        )
    return _upstream_status(
        "healthy",
        details=[],
        next_action=None,
        name=upstream,
        ahead=int(counts[0]),
        behind=int(counts[1]),
    )


def _runtime_action(boundary: GitBoundary, kind: Kind) -> str | None:
    """Return the topology-valid, non-executed runtime setup action."""
    if (
        kind == "linked"
        and (boundary.path / "scripts" / "setup_worktree_env.sh").is_file()
    ):
        return _graphify_command(boundary.path, "bash", "scripts/setup_worktree_env.sh")
    if (
        kind in {"primary", "standalone"}
        and (boundary.path / "aria_nbv" / "pyproject.toml").is_file()
    ):
        return _graphify_command(
            boundary.path / "aria_nbv", "uv", "sync", "--extra", "dev"
        )
    return None


def _readiness(boundary: GitBoundary, kind: Kind) -> ReadinessStatus:
    runtime_path = boundary.path / "aria_nbv" / ".venv" / "bin" / "python"
    if runtime_path.is_file() and os.access(runtime_path, os.X_OK):
        try:
            result = subprocess.run(
                [
                    str(runtime_path),
                    "-c",
                    "import sys; raise SystemExit(not bool(sys.executable))",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            runtime: RuntimeStatus = {
                "state": "unusable",
                "details": [f"configured package runtime could not start: {error}"],
                "next_action": _runtime_action(boundary, kind),
                "path": str(runtime_path),
            }
        else:
            probe = ProbeResult(result.returncode, result.stdout, result.stderr)
            runtime = {
                "state": "healthy" if result.returncode == 0 else "unusable",
                "details": [] if result.returncode == 0 else _details(probe),
                "next_action": None
                if result.returncode == 0
                else _runtime_action(boundary, kind),
                "path": str(runtime_path),
            }
    else:
        runtime = {
            "state": "uninitialized",
            "details": ["configured package runtime is absent or not executable"],
            "next_action": _runtime_action(boundary, kind),
            "path": str(runtime_path),
        }
    submodule_result = boundary.run("submodule", "status", "--recursive")
    if submodule_result.returncode:
        submodules = _probe_failure(
            submodule_result,
            next_action=_command(boundary.path, "submodule", "status", "--recursive"),
        )
    else:
        lines = [line for line in submodule_result.stdout.splitlines() if line]
        if any(line[0] in "-U" for line in lines):
            submodules = {
                "state": "uninitialized",
                "details": lines,
                "next_action": _command(
                    boundary.path, "submodule", "update", "--init", "--recursive"
                ),
            }
        elif any(line[0] == "+" for line in lines):
            submodules = {
                "state": "stale",
                "details": lines,
                "next_action": _command(
                    boundary.path, "submodule", "update", "--init", "--recursive"
                ),
            }
        else:
            submodules = {"state": "healthy", "details": lines, "next_action": None}
    return {"runtime": runtime, "submodules": submodules}


def _aria_graphify_action(boundary: GitBoundary, kind: Kind) -> str | None:
    """Return the setup-owned maintenance action for an existing checkout."""
    if not (boundary.path / "scripts" / "setup_codex_worktree_env.sh").is_file():
        return None
    return _graphify_command(boundary.path, "make", "graphify-maintain")


def _graphify(boundary: GitBoundary, *, bare: bool, kind: Kind) -> GraphifyStatus:
    """Report Graphify admission without executing maintenance or mutation."""
    if bare:
        return {
            "state": "unavailable",
            "details": ["Graphify requires a non-bare checkout"],
            "next_action": _command(boundary.path, "worktree", "list", "--porcelain"),
        }
    output = boundary.path / "graphify-out"
    if not output.exists():
        return {
            "state": "unavailable",
            "details": ["Graphify output is absent"],
            "next_action": _aria_graphify_action(boundary, kind),
        }
    required = (boundary.path / "graphify-input" / "index.md", output / "graph.json")
    if not all(item.is_file() for item in required):
        return {
            "state": "uninitialized",
            "details": ["Graphify output is incomplete"],
            "next_action": _aria_graphify_action(boundary, kind),
        }
    try:
        result = subprocess.run(
            [sys.executable, str(FRESHNESS_CHECKER), "--json"],
            cwd=boundary.path,
            check=False,
            capture_output=True,
            text=True,
            env=boundary.env,
        )
    except OSError as error:
        return {
            "state": "unusable",
            "details": [f"freshness checker could not run: {error}"],
            "next_action": _aria_graphify_action(boundary, kind),
        }
    probe = ProbeResult(result.returncode, result.stdout, result.stderr)
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, TypeError):
        return {
            "state": "unusable",
            "details": _details(probe),
            "next_action": _aria_graphify_action(boundary, kind),
        }
    if not isinstance(payload, dict):
        return {
            "state": "unusable",
            "details": [
                "Graphify admission payload is not an object",
                *_graphify_process_details(probe),
            ],
            "next_action": _aria_graphify_action(boundary, kind),
        }
    state = payload.get("state")
    raw_details = payload.get("reasons", [])
    owner_action = payload.get("next_action")
    owner_details = [f"Graphify admission state: {state}"]
    owner_details.extend(
        [item for item in raw_details if isinstance(item, str)]
        if isinstance(raw_details, list)
        else [str(raw_details)]
    )
    if isinstance(owner_action, str) and owner_action:
        owner_details.append(f"Graphify admission owner note: {owner_action}")
    contract: dict[str, tuple[int, State]] = {
        "fresh": (0, "healthy"),
        "usable-stale": (1, "stale"),
        "unusable": (1, "unusable"),
    }
    expected = contract.get(state) if isinstance(state, str) else None
    if expected is None:
        return {
            "state": "unusable",
            "details": [
                *owner_details,
                "Graphify admission returned an unknown state",
                *_graphify_process_details(probe),
            ],
            "next_action": _aria_graphify_action(boundary, kind),
        }
    expected_returncode, mapped = expected
    if probe.returncode != expected_returncode:
        return {
            "state": "unusable",
            "details": [
                *owner_details,
                (
                    f"Graphify admission state {state!r} requires exit status "
                    f"{expected_returncode}, got {probe.returncode}"
                ),
                *_graphify_process_details(probe),
            ],
            "next_action": _aria_graphify_action(boundary, kind),
        }
    return {
        "state": mapped,
        "details": owner_details,
        "next_action": None
        if mapped == "healthy"
        else _aria_graphify_action(boundary, kind),
    }


def _identity(boundary: GitBoundary) -> tuple[RepositoryStatus, GitBoundary, bool]:
    bare_result = boundary.run("rev-parse", "--is-bare-repository")
    bare_text = _text(bare_result)
    if bare_result.returncode or bare_text not in {"true", "false"}:
        raise RuntimeError("Git bare-repository identity is unavailable")
    bare = bare_text == "true"
    top_result = boundary.run("rev-parse", "--show-toplevel")
    top = _text(top_result)
    if bare:
        root = boundary.path
    elif top_result.returncode or not top:
        raise RuntimeError("Git worktree root identity is unavailable")
    else:
        root = Path(top).resolve()
        boundary = GitBoundary(root)
    git_dir_result = boundary.run("rev-parse", "--git-dir")
    common_result = boundary.run("rev-parse", "--git-common-dir")
    if git_dir_result.returncode or common_result.returncode:
        raise RuntimeError("Git directory identity is unavailable")
    git_dir = (boundary.path / _text(git_dir_result)).resolve()
    common = (boundary.path / _text(common_result)).resolve()
    worktrees_result, worktrees = _registered_worktrees(boundary, common)
    worktree_strings = sorted(str(path) for path in worktrees)
    registration: RegistrationStatus
    if bare:
        registration = {
            "state": "not-applicable",
            "details": ["bare repositories are not registered working trees"],
            "next_action": _command(boundary.path, "worktree", "list", "--porcelain"),
            "worktrees": worktree_strings,
        }
    elif worktrees_result.returncode:
        registration = {
            "state": "unavailable",
            "details": _details(worktrees_result),
            "next_action": _command(boundary.path, "worktree", "list", "--porcelain"),
            "worktrees": [],
        }
    else:
        registered = root in worktrees
        registration = {
            "state": "registered" if registered else "unregistered",
            "details": [] if registered else ["current worktree is not registered"],
            "next_action": None
            if registered
            else _command(boundary.path, "worktree", "repair", str(root)),
            "worktrees": worktree_strings,
        }
    symbolic_result = boundary.run("symbolic-ref", "--short", "-q", "HEAD")
    symbolic_text = _text(symbolic_result)
    symbolic_head = (
        symbolic_text if symbolic_result.returncode == 0 and symbolic_text else None
    )
    head_result = boundary.run("rev-parse", "--verify", "--quiet", "HEAD")
    head_text = _text(head_result)
    head = head_text if head_result.returncode == 0 and head_text else None
    if head is not None:
        head_state: Literal["present", "unborn", "unavailable", "not-applicable"] = (
            "present"
        )
    elif symbolic_head is not None:
        head_state = "unborn"
    else:
        head_state = "unavailable"
    branch_state: Literal[
        "named", "detached", "unborn", "unavailable", "not-applicable"
    ]
    if bare:
        branch_state = "unborn" if head_state == "unborn" else "not-applicable"
    elif symbolic_head is not None:
        branch_state = "unborn" if head_state == "unborn" else "named"
    else:
        branch_state = "detached" if head is not None else "unavailable"
    linked = not bare and (boundary.path / ".git").is_file() and git_dir != common
    if bare:
        kind: Kind = "bare"
    elif linked:
        kind = "linked"
    elif registration["state"] == "unavailable":
        kind = "unavailable"
    elif len(worktrees) > 1 and root == worktrees[0]:
        kind = "primary"
    else:
        kind = "standalone"
    if bare:
        dirty: DirtyStatus = {
            "state": "not-applicable",
            "details": ["bare repositories have no working files"],
            "next_action": None,
        }
    else:
        status_result = boundary.run(
            "status", "--porcelain=v1", "--untracked-files=all"
        )
        if status_result.returncode:
            dirty = {
                "state": "unavailable",
                "details": _details(status_result),
                "next_action": _command(
                    boundary.path, "status", "--porcelain=v1", "--untracked-files=all"
                ),
            }
        else:
            dirty = {
                "state": "dirty" if status_result.stdout else "clean",
                "details": [],
                "next_action": None,
            }
        if dirty["state"] == "dirty":
            dirty["details"] = ["working tree has tracked or untracked changes"]
            dirty["next_action"] = _command(boundary.path, "status", "--short")
    warning = (
        "bare repositories have no working files and must not be used as current source"
        if bare
        else None
    )
    repository: RepositoryStatus = {
        "root": str(root),
        "bare": bare,
        "kind": kind,
        "registration": registration,
        "branch": symbolic_head,
        "branch_state": branch_state,
        "symbolic_head": symbolic_head,
        "head": head,
        "head_state": head_state,
        "upstream": _upstream(boundary, symbolic_head, bare=bare),
        "dirty": dirty,
        "git_directory": str(git_dir),
        "common_git_directory": str(common),
        "warning": warning,
    }
    return repository, boundary, bare


def inspect(path: Path) -> StatusEnvelope:
    """Return a fixed success/error envelope for one checkout path."""
    boundary = GitBoundary(path)
    try:
        repository, boundary, bare = _identity(boundary)
        result: StatusResult = {
            "repository": repository,
            "readiness": {
                "runtime": {
                    "state": "unavailable",
                    "details": [],
                    "next_action": None,
                    "path": None,
                },
                "submodules": {
                    "state": "not-applicable",
                    "details": [],
                    "next_action": None,
                },
            }
            if bare
            else _readiness(boundary, repository["kind"]),
            "graphify": _graphify(boundary, bare=bare, kind=repository["kind"]),
        }
    except (OSError, RuntimeError, ValueError) as error:
        return {
            "schema_version": 1,
            "ok": False,
            "result": None,
            "error": {
                "code": "repository_identity_unavailable",
                "message": str(error),
                "details": [],
                "next_action": f"git -C {shlex.quote(str(boundary.path))} rev-parse --show-toplevel",
            },
        }
    return {"schema_version": 1, "ok": True, "result": result, "error": None}


def render_text(envelope: StatusEnvelope) -> str:
    """Render a concise status while retaining explicit unavailable fields."""
    if not envelope["ok"]:
        error = envelope["error"]
        assert error is not None
        return f"Agent status: unavailable — {error['message']}\nNext action: {error['next_action'] or 'none'}"
    result = envelope["result"]
    assert result is not None
    repository = result["repository"]
    upstream = repository["upstream"]
    divergence = (
        f"ahead {upstream['ahead']}, behind {upstream['behind']}"
        if upstream["ahead"] is not None and upstream["behind"] is not None
        else upstream["state"]
    )
    warning = f"\nWarning: {repository['warning']}" if repository["warning"] else ""
    next_action = (
        repository["registration"]["next_action"]
        or result["graphify"]["next_action"]
        or result["readiness"]["runtime"]["next_action"]
        or upstream["next_action"]
        or repository["dirty"]["next_action"]
        or "none"
    )
    return "\n".join(
        [
            f"Repository: {repository['root']} ({repository['kind']})",
            f"Branch: {repository['branch'] or repository['branch_state']}; HEAD: {repository['head'] or repository['head_state']}; upstream: {upstream['name'] or upstream['state']} ({divergence})",
            f"Registration: {repository['registration']['state']}; dirty: {repository['dirty']['state']}; runtime: {result['readiness']['runtime']['state']}; submodules: {result['readiness']['submodules']['state']}; Graphify: {result['graphify']['state']}{warning}",
            f"Next action: {next_action}",
        ]
    )


def main(argv: list[str] | None = None) -> int:
    """Print status; optional capability failures remain successful diagnoses."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit the stable JSON envelope"
    )
    parser.add_argument(
        "--path", type=Path, default=Path.cwd(), help="checkout or bare repository path"
    )
    args = parser.parse_args(argv)
    envelope = inspect(args.path)
    print(json.dumps(envelope, sort_keys=True) if args.json else render_text(envelope))
    return 0 if envelope["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
