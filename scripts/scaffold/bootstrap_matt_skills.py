#!/usr/bin/env python3
"""Bootstrap the pinned Matt skill collection and ARIA project isolation."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import matt_skills_policy as policy


def _check_installer(manifest: dict[str, object]) -> None:
    installer = manifest["installer"]
    assert isinstance(installer, dict)
    version = installer["version"]
    expected = installer["npm_integrity"]
    if (
        version != policy.EXPECTED_INSTALLER_VERSION
        or expected != policy.EXPECTED_INSTALLER_INTEGRITY
    ):
        raise policy.PolicyError(
            "installer version or integrity differs from approved pin"
        )
    raw = subprocess.check_output(
        ["npm", "view", f"skills@{version}", "dist.integrity", "--json"],
        text=True,
    )
    observed = json.loads(raw)
    if observed != expected:
        raise policy.PolicyError(
            f"skills@{version} integrity mismatch: expected {expected}, observed {observed}"
        )


def _checkout_source(manifest: dict[str, object], destination: Path) -> Path:
    source = manifest["source"]
    assert isinstance(source, dict)
    if source.get("url") != policy.EXPECTED_URL:
        raise policy.PolicyError("source URL differs from approved Matt upstream")
    checkout = destination / "mattpocock-skills"
    subprocess.run(
        ["git", "clone", "--quiet", policy.EXPECTED_URL, str(checkout)], check=True
    )
    subprocess.run(
        ["git", "checkout", "--quiet", source["commit"]], cwd=checkout, check=True
    )
    return checkout


def _install_to_staging(
    manifest: dict[str, object], checkout: Path, staging_home: Path
) -> Path:
    installer = manifest["installer"]
    assert isinstance(installer, dict)
    env = os.environ.copy()
    env["HOME"] = str(staging_home)
    env["CODEX_HOME"] = str(staging_home / ".codex")
    subprocess.run(
        [
            "npx",
            "--yes",
            f"skills@{installer['version']}",
            "add",
            str(checkout),
            "--global",
            "--agent",
            "codex",
            "--skill",
            "*",
            "--yes",
        ],
        check=True,
        env=env,
    )
    return staging_home / ".agents/skills"


def _deploy_transaction(
    catalog: dict[str, str], staged_root: Path, target_root: Path
) -> None:
    target_root.mkdir(parents=True, exist_ok=True)
    conflicts = [name for name in catalog if (target_root / name).exists()]
    if conflicts:
        raise policy.PolicyError(
            "global skill path collision; rollback or remove the prior Matt installation first: "
            f"{sorted(conflicts)}"
        )
    installed: list[Path] = []
    try:
        for name in sorted(catalog):
            source = staged_root / name
            destination = target_root / name
            if not source.is_dir():
                raise policy.PolicyError(f"installer omitted Matt skill: {name}")
            shutil.copytree(source, destination, symlinks=False)
            installed.append(destination)
    except Exception:
        for destination in reversed(installed):
            shutil.rmtree(destination)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=policy.MANIFEST_PATH)
    parser.add_argument("--source-checkout", type=Path)
    parser.add_argument(
        "--skills-root", type=Path, default=Path.home() / ".agents/skills"
    )
    parser.add_argument(
        "--project-config", type=Path, default=policy.ROOT / ".codex/config.toml"
    )
    args = parser.parse_args()

    manifest = policy.load_manifest(args.manifest)
    _check_installer(manifest)
    with tempfile.TemporaryDirectory(prefix="aria-matt-bootstrap-") as raw_temp:
        temporary = Path(raw_temp)
        checkout = args.source_checkout or _checkout_source(manifest, temporary)
        errors = policy.validate_manifest(manifest, checkout)
        if errors:
            raise policy.PolicyError("; ".join(errors))
        staged_root = _install_to_staging(manifest, checkout, temporary / "home")
        install_errors, _ = policy.validate_installation(
            manifest, checkout, staged_root
        )
        if install_errors:
            raise policy.PolicyError("; ".join(install_errors))
        catalog = policy.discover_catalog(checkout)
        _deploy_transaction(catalog, staged_root, args.skills_root)
        config_existed = args.project_config.exists()
        config_bytes = args.project_config.read_bytes() if config_existed else b""
        try:
            block = policy.render_config_block(manifest, checkout, args.skills_root)
            policy.update_project_config(args.project_config, block)
            config_errors = policy.validate_project_config(
                args.project_config, manifest, checkout, args.skills_root
            )
            if config_errors:
                raise policy.PolicyError("; ".join(config_errors))
        except Exception:
            if config_existed:
                args.project_config.write_bytes(config_bytes)
            elif args.project_config.exists():
                args.project_config.unlink()
            for name in catalog:
                destination = args.skills_root / name
                if destination.exists():
                    shutil.rmtree(destination)
            raise

    print(
        f"Installed pinned Matt collection under {args.skills_root} and activated "
        "the 12-skill ARIA allowlist"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError, policy.PolicyError) as exc:
        print(f"Matt bootstrap failed: {exc}", file=sys.stderr)
        sys.exit(1)
