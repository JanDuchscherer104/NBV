#!/usr/bin/env python3
"""Build and admit the locked PyTorch3D provider for the local CUDA runtime."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
import tomllib
from collections.abc import Sequence
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit, urlunsplit


def _run(
    command: Sequence[str],
    *,
    env: dict[str, str] | None = None,
    capture: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        env=env,
        text=True,
        capture_output=capture,
    )


def _target_runtime(python: Path) -> dict[str, Any]:
    program = (
        "import json, platform, sys, torch; "
        "print(json.dumps({'platform': sys.platform, 'machine': platform.machine(), "
        "'cuda_available': torch.cuda.is_available(), "
        "'capability': list(torch.cuda.get_device_capability()) "
        "if torch.cuda.is_available() else None}))"
    )
    result = _run((str(python), "-c", program), capture=True)
    payload = json.loads(result.stdout)
    if not isinstance(payload, dict):
        raise RuntimeError("target Python returned invalid runtime metadata")
    return payload


def _locked_linux_pytorch3d(lock_path: Path) -> tuple[str, str]:
    payload = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    packages = payload.get("package", [])
    candidates = [
        package
        for package in packages
        if package.get("name") == "pytorch3d"
        and any(
            "sys_platform == 'linux'" in marker
            and "platform_machine == 'x86_64'" in marker
            for marker in package.get("resolution-markers", [])
        )
    ]
    if len(candidates) != 1:
        raise RuntimeError("uv.lock must contain one Linux x86_64 PyTorch3D source")
    source = candidates[0].get("source", {}).get("git")
    if not isinstance(source, str):
        raise RuntimeError("locked Linux PyTorch3D source is not a Git URL")
    parsed = urlsplit(source)
    revisions = parse_qs(parsed.query).get("rev", [])
    commit = parsed.fragment
    if (
        parsed.scheme != "https"
        or len(revisions) != 1
        or revisions[0] != commit
        or len(commit) not in {40, 64}
        or any(character not in "0123456789abcdef" for character in commit)
    ):
        raise RuntimeError("locked Linux PyTorch3D source is not an exact Git commit")
    url = urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))
    return url, commit


def _cuda_home(value: Path | None) -> Path:
    if value is not None:
        home = value.expanduser().resolve()
    elif os.getenv("CUDA_HOME"):
        home = Path(os.environ["CUDA_HOME"]).expanduser().resolve()
    else:
        nvcc = shutil.which("nvcc")
        if not nvcc:
            raise RuntimeError("CUDA_HOME is unset and nvcc is not on PATH")
        home = Path(nvcc).resolve().parent.parent
    if not (home / "bin/nvcc").is_file():
        raise RuntimeError(f"CUDA toolkit is missing {home / 'bin/nvcc'}")
    return home


def _preflight(command: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        (str(command),),
        check=False,
        env=env,
        text=True,
        capture_output=True,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "aria_nbv",
    )
    parser.add_argument("--cuda-home", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    project_root = args.project_root.expanduser().resolve()
    python = project_root / ".venv/bin/python"
    preflight = project_root / ".venv/bin/nbv-pytorch3d-backend"
    lock_path = project_root / "uv.lock"
    if not python.is_file() or not preflight.is_file() or not lock_path.is_file():
        raise RuntimeError("run uv sync --locked before configuring the CUDA provider")

    runtime = _target_runtime(python)
    if runtime.get("platform") != "linux" or runtime.get("machine") != "x86_64":
        raise RuntimeError("the CUDA provider setup supports Linux x86_64 only")
    if runtime.get("cuda_available") is not True:
        raise RuntimeError("the target Torch runtime cannot access CUDA")
    capability = runtime.get("capability")
    if not (
        isinstance(capability, list)
        and len(capability) == 2
        and all(isinstance(part, int) for part in capability)
    ):
        raise RuntimeError("the target Torch runtime returned no CUDA capability")

    env = os.environ.copy()
    env["PYTORCH3D_BACKEND"] = "cuda"
    admitted = _preflight(preflight, env)
    if admitted.returncode == 0 and not args.force:
        print(admitted.stdout.strip())
        print("PyTorch3D CUDA provider is already admitted.")
        return 0

    cuda_home = _cuda_home(args.cuda_home)
    url, commit = _locked_linux_pytorch3d(lock_path)
    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv is not on PATH")
    cache_root = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    cache_root.mkdir(parents=True, exist_ok=True)
    env.update(
        {
            "CUDA_HOME": str(cuda_home),
            "FORCE_CUDA": "1",
            "TORCH_CUDA_ARCH_LIST": f"{capability[0]}.{capability[1]}",
            "MAX_JOBS": env.get("MAX_JOBS", "4"),
        }
    )
    with tempfile.TemporaryDirectory(prefix="aria-nbv-pytorch3d-", dir=cache_root) as temp_dir:
        build_env = {**env, "TMPDIR": temp_dir}
        _run(
            (
                uv,
                "pip",
                "install",
                "--python",
                str(python),
                "--reinstall",
                "--no-deps",
                "--no-cache",
                "--no-build-isolation-package",
                "pytorch3d",
                f"pytorch3d @ git+{url}@{commit}",
            ),
            env=build_env,
        )

    admitted = _preflight(preflight, env)
    if admitted.returncode != 0:
        diagnostic = admitted.stderr.strip() or admitted.stdout.strip()
        raise RuntimeError(f"PyTorch3D CUDA admission failed after rebuild: {diagnostic}")
    print(admitted.stdout.strip())
    print("PyTorch3D CUDA provider rebuilt from the exact uv.lock source and admitted.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
