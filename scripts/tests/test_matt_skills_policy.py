#!/usr/bin/env python3
"""Focused WP3 pin, closure, isolation, conflict, budget and rollback tests."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib


ROOT = Path(__file__).resolve().parents[2]
POLICY_SCRIPT = ROOT / "scripts/scaffold/matt_skills_policy.py"
BOOTSTRAP_SCRIPT = ROOT / "scripts/scaffold/bootstrap_matt_skills.py"
FIXTURES = ROOT / "scripts/tests/fixtures/matt_policy"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = _load("matt_skills_policy", POLICY_SCRIPT)
bootstrap = _load("bootstrap_matt_skills", BOOTSTRAP_SCRIPT)


def _checkout(manifest: dict, temporary: Path) -> Path:
    provided = os.environ.get("MATT_SKILLS_CHECKOUT")
    if provided:
        return Path(provided)
    checkout = temporary / "upstream"
    subprocess.run(
        ["git", "clone", "--quiet", manifest["source"]["url"], str(checkout)],
        check=True,
    )
    subprocess.run(
        ["git", "checkout", "--quiet", manifest["source"]["commit"]],
        cwd=checkout,
        check=True,
    )
    return checkout


def _install_copy(checkout: Path, skills_root: Path) -> None:
    for name, skill_path in policy.discover_catalog(checkout).items():
        shutil.copytree((checkout / skill_path).parent, skills_root / name)


def _prompt_input(
    repo: Path, home: Path, codex_home: Path, project_config: Path
) -> list[dict]:
    codex_home.mkdir(parents=True)
    (codex_home / "config.toml").write_text(
        project_config.read_text(encoding="utf-8")
        + f'\n[projects.{json.dumps(str(repo))}]\ntrust_level = "trusted"\n',
        encoding="utf-8",
    )
    env = os.environ.copy()
    env.update({"HOME": str(home), "CODEX_HOME": str(codex_home), "LC_ALL": "C.UTF-8"})
    raw = subprocess.check_output(
        ["codex", "debug", "prompt-input", ""], cwd=repo, env=env
    )
    return json.loads(raw)


def main() -> None:
    manifest = policy.load_manifest()
    with tempfile.TemporaryDirectory(prefix="aria-wp3-test-") as raw_temp:
        temporary = Path(raw_temp)
        checkout = _checkout(manifest, temporary)
        assert not policy.validate_manifest(manifest, checkout)
        assert not policy.validate_codex_binary()
        bootstrap._check_installer(manifest)

        wrong_integrity = copy.deepcopy(manifest)
        wrong_integrity["installer"]["npm_integrity"] = "sha512-wrong"
        assert any(
            "integrity differs" in error
            for error in policy.validate_manifest(wrong_integrity, checkout)
        )

        vector = temporary / "vector"
        vector.mkdir()
        (vector / "a").write_bytes(b"alpha\n")
        (vector / "b").write_bytes(b"beta\x00")
        assert policy.closure_digest(vector, ["b", "a"]) == (
            "a8ac18f622eb90a1143f34f97fc2a8fc721387b7994841e2e0ebf607ccb23483"
        )

        wrong_commit = copy.deepcopy(manifest)
        wrong_commit["source"]["commit"] = "0" * 40
        assert any(
            "source.commit must be exactly" in error
            for error in policy.validate_manifest(wrong_commit, checkout)
        )

        tdd_source = checkout / "skills/engineering/tdd/SKILL.md"
        tdd_bytes = tdd_source.read_bytes()
        tdd_source.write_bytes(tdd_bytes + b"\n[missing](missing.md)\n")
        assert any(
            "invalid closure for tdd" in error
            for error in policy.validate_manifest(manifest, checkout)
        )
        tdd_source.write_bytes(tdd_bytes)

        duplicate_source = checkout / "skills/duplicate-tdd/SKILL.md"
        duplicate_source.parent.mkdir()
        duplicate_source.write_bytes(tdd_bytes)
        assert any(
            "duplicate Matt skill ids" in error
            for error in policy.validate_manifest(manifest, checkout)
        )
        duplicate_source.unlink()
        duplicate_source.parent.rmdir()

        skills_root = temporary / "home/.agents/skills"
        skills_root.mkdir(parents=True)
        _install_copy(checkout, skills_root)
        install_errors, installed = policy.validate_installation(
            manifest, checkout, skills_root
        )
        assert not install_errors
        assert set(manifest["policy"]["allowlist"]) <= set(installed)

        missing_skill = skills_root / "ask-matt"
        held_skill = temporary / "held-ask-matt"
        missing_skill.rename(held_skill)
        errors, _ = policy.validate_installation(manifest, checkout, skills_root)
        assert any(
            "selected Matt id has no installed path: ask-matt" in error
            for error in errors
        )
        held_skill.rename(missing_skill)

        unrelated = skills_root / "unrelated-user-skill"
        unrelated.mkdir()
        (unrelated / "SKILL.md").write_text(
            "---\nname: unrelated-user-skill\ndescription: Preserve me.\n---\n",
            encoding="utf-8",
        )
        config = temporary / "repo/.codex/config.toml"
        config.parent.mkdir(parents=True)
        preserved_config = (
            "[features]\n"
            "multi_agent = true\n\n"
            "[[skills.config]]\n"
            f"path = {json.dumps(str(unrelated / 'SKILL.md'))}\n"
            "enabled = true\n"
        )
        config.write_text(preserved_config, encoding="utf-8")
        block = policy.render_config_block(manifest, checkout, skills_root)
        policy.update_project_config(config, block)
        assert not policy.validate_project_config(
            config, manifest, checkout, skills_root
        )
        assert config.read_text(encoding="utf-8").count("unrelated-user-skill") == 1

        enabled_unlisted = config.read_text(encoding="utf-8").replace(
            f"path = {json.dumps(str(skills_root.resolve() / 'code-review/SKILL.md'))}\nenabled = false",
            f"path = {json.dumps(str(skills_root.resolve() / 'code-review/SKILL.md'))}\nenabled = true",
        )
        config.write_text(enabled_unlisted, encoding="utf-8")
        assert any(
            "expected enabled=False" in error
            for error in policy.validate_project_config(
                config, manifest, checkout, skills_root
            )
        )
        policy.update_project_config(config, block)

        repo = temporary / "repo"
        subprocess.run(["git", "init", "--quiet", str(repo)], check=True)
        payload = _prompt_input(
            repo, temporary / "home", temporary / "codex-home", config
        )
        prompt_errors = policy.validate_prompt_input(
            manifest, payload, skills_root, set(policy.discover_catalog(checkout))
        )
        assert not prompt_errors, prompt_errors

        policy.update_project_config(config, None)
        assert config.read_text(encoding="utf-8") == preserved_config
        assert unrelated.is_dir()

        changed = skills_root / "tdd/tests.md"
        original = changed.read_bytes()
        changed.write_bytes(original + b"changed\n")
        errors, _ = policy.validate_installation(manifest, checkout, skills_root)
        assert any("installed closure mismatch for tdd" in error for error in errors)
        changed.write_bytes(original)

        missing = skills_root / "tdd/mocking.md"
        missing_bytes = missing.read_bytes()
        missing.unlink()
        errors, _ = policy.validate_installation(manifest, checkout, skills_root)
        assert any(
            "missing installed closure file for tdd" in error for error in errors
        )
        missing.write_bytes(missing_bytes)

        duplicate = skills_root / "nested/tdd"
        duplicate.parent.mkdir()
        shutil.copytree(skills_root / "tdd", duplicate)
        errors, _ = policy.validate_installation(manifest, checkout, skills_root)
        assert any("duplicate installed skill ids" in error for error in errors)
        shutil.rmtree(duplicate.parent)

        escaped = skills_root / "tdd/tests.md"
        escaped.unlink()
        escaped.symlink_to(checkout / "skills/engineering/tdd/tests.md")
        errors, _ = policy.validate_installation(manifest, checkout, skills_root)
        assert any("path escapes" in error for error in errors)
        escaped.unlink()
        escaped.write_bytes(original)

        collision_root = temporary / "collision-root"
        collision_root.mkdir()
        (collision_root / "ask-matt").mkdir()
        sentinel = collision_root / "ask-matt/sentinel"
        sentinel.write_text("preserve", encoding="utf-8")
        try:
            bootstrap._deploy_transaction(
                policy.discover_catalog(checkout), skills_root, collision_root
            )
        except policy.PolicyError:
            pass
        else:
            raise AssertionError("bootstrap accepted an existing global path collision")
        assert sentinel.read_text(encoding="utf-8") == "preserve"

        routing = tomllib.loads((FIXTURES / "routing.toml").read_text(encoding="utf-8"))
        records = policy.manifest_records(manifest)
        assert {case["skill"] for case in routing["case"]} == set(records)
        assert all(
            case["model_visible"] == records[case["skill"]].model_visible
            and case["positive"] != case["adjacent_negative"]
            for case in routing["case"]
        )
        conflicts = tomllib.loads(
            (FIXTURES / "conflicts.toml").read_text(encoding="utf-8")
        )
        assert {case["id"] for case in conflicts["case"]} == {
            "dirty-worktree",
            "domain-owner",
            "durable-planning",
            "merge-safety",
            "runtime-writes",
            "teaching-workspace",
            "ticket-owner",
        }
        assert all(
            case["forbidden_outputs"] and case["aria_owner"]
            for case in conflicts["case"]
        )

    print("Matt skill policy self-test passed")


if __name__ == "__main__":
    main()
