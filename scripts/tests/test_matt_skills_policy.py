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
from types import ModuleType
from typing import Any, cast
from unittest import mock


ROOT = Path(__file__).resolve().parents[2]
POLICY_SCRIPT = ROOT / "scripts/scaffold/matt_skills_policy.py"
BOOTSTRAP_SCRIPT = ROOT / "scripts/scaffold/bootstrap_matt_skills.py"
FIXTURES = ROOT / "scripts/tests/fixtures/matt_policy"
JsonDict = dict[str, Any]
PromptInput = list[JsonDict]


def _load(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


policy = _load("matt_skills_policy", POLICY_SCRIPT)
bootstrap = _load("bootstrap_matt_skills", BOOTSTRAP_SCRIPT)


def _checkout(manifest: JsonDict, temporary: Path) -> Path:
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
) -> PromptInput:
    return cast(
        PromptInput,
        policy.run_clean_home_prompt_input(
            repo,
            home,
            codex_home,
            project_config.read_text(encoding="utf-8"),
        ),
    )


def _prompt_fixture(
    manifest: JsonDict, skills_root: Path
) -> tuple[PromptInput, set[str], set[str]]:
    aria_names = set(
        json.loads(policy.WP6_SKILLS_PATH.read_text(encoding="utf-8"))["active_skills"]
    )
    matt_names = set(manifest["budget"]["model_visible_allowlist"])
    lines = [
        "### Skill roots",
        f"- `r0` = `{ROOT / '.agents/skills'}`",
        f"- `r1` = `{skills_root}`",
        "### Available skills",
    ]
    for name in sorted(aria_names):
        description = policy._frontmatter(ROOT / ".agents/skills" / name / "SKILL.md")[
            "description"
        ]
        lines.append(f"- {name}: {description} (file: r0/{name}/SKILL.md)")
    for name in sorted(matt_names):
        description = policy._frontmatter(skills_root / name / "SKILL.md")[
            "description"
        ]
        lines.append(f"- {name}: {description} (file: r1/{name}/SKILL.md)")
    payload: PromptInput = [
        {
            "role": "developer",
            "content": [{"type": "input_text", "text": "\n".join(lines)}],
        }
    ]
    return payload, aria_names, matt_names


def main() -> None:
    manifest = policy.load_manifest()
    with tempfile.TemporaryDirectory(prefix="aria-wp3-test-") as raw_temp:
        temporary = Path(raw_temp)
        checkout = _checkout(manifest, temporary)
        assert not policy.validate_manifest(manifest, checkout)
        assert not policy.validate_codex_binary()
        assert not policy.validate_codex_prompt_surface()
        with mock.patch.object(
            policy.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(
                ["codex"], returncode=0, stdout="legacy help", stderr=""
            ),
        ):
            assert policy.validate_codex_prompt_surface() == [
                "Codex prompt-input surface is unavailable or mismatched"
            ]
        with mock.patch.object(
            policy.subprocess, "run", side_effect=FileNotFoundError("missing")
        ):
            assert policy.validate_codex_prompt_surface() == [
                "Codex prompt-input surface is unavailable: missing"
            ]
        bootstrap._check_installer(manifest)

        wrong_integrity = copy.deepcopy(manifest)
        wrong_integrity["installer"]["npm_integrity"] = "sha512-wrong"
        assert any(
            "integrity differs" in error
            for error in policy.validate_manifest(wrong_integrity, checkout)
        )
        wrong_integrated_budget = copy.deepcopy(manifest)
        wrong_integrated_budget["budget"]["integrated_description_bytes"] += 1
        assert any(
            "integrated description arithmetic" in error
            for error in policy.validate_manifest(wrong_integrated_budget, checkout)
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

        fixture, aria_names, matt_names = _prompt_fixture(manifest, skills_root)
        matt_catalog = set(policy.discover_catalog(checkout))
        assert not policy.validate_prompt_input(
            manifest, fixture, skills_root, matt_catalog
        )
        fixture_text = fixture[0]["content"][0]["text"]
        duplicate_fixture = copy.deepcopy(fixture)
        duplicate_fixture[0]["content"][0]["text"] = (
            fixture_text
            + "\n"
            + next(
                line
                for line in fixture_text.splitlines()
                if line.startswith("- codebase-design:")
            )
        )
        assert any(
            "collisions" in error
            for error in policy.validate_prompt_input(
                manifest, duplicate_fixture, skills_root, matt_catalog
            )
        )
        omitted_fixture = copy.deepcopy(fixture)
        omitted_fixture[0]["content"][0]["text"] = "\n".join(
            line for line in fixture_text.splitlines() if not line.startswith("- tdd:")
        )
        assert any(
            "integrated model-visible skills differ" in error
            for error in policy.validate_prompt_input(
                manifest, omitted_fixture, skills_root, matt_catalog
            )
        )
        renamed_aria_fixture = copy.deepcopy(fixture)
        renamed_aria_fixture[0]["content"][0]["text"] = fixture_text.replace(
            "- aria-nbv-context:", "- forged-aria-context:", 1
        )
        assert any(
            "integrated model-visible skills differ" in error
            for error in policy.validate_prompt_input(
                manifest, renamed_aria_fixture, skills_root, matt_catalog
            )
        )
        truncated_fixture = copy.deepcopy(fixture)
        truncated_fixture[0]["content"][0]["text"] = fixture_text.replace(
            policy._frontmatter(skills_root / "tdd/SKILL.md")["description"],
            policy._frontmatter(skills_root / "tdd/SKILL.md")["description"][:-1],
        )
        assert any(
            "truncated or changed" in error
            for error in policy.validate_prompt_input(
                manifest, truncated_fixture, skills_root, matt_catalog
            )
        )
        tiny_budget = copy.deepcopy(manifest)
        tiny_budget["budget"]["maximum_description_bytes"] = 1
        assert any(
            "exceed the WP0 budget" in error
            for error in policy.validate_prompt_input(
                tiny_budget, fixture, skills_root, matt_catalog
            )
        )
        assert policy.validate_prompt_input(
            manifest, [], skills_root, matt_catalog
        ) == ["Codex prompt-input payload must be a non-empty JSON list"]

        clean_home = temporary / "clean-home"
        prompt_skills_root = clean_home / ".agents/skills"
        prompt_skills_root.mkdir(parents=True)
        _install_copy(checkout, prompt_skills_root)
        for name in aria_names:
            shutil.copytree(
                ROOT / ".agents/skills" / name,
                prompt_skills_root / name,
            )
        integrated_config = temporary / "integrated-config.toml"
        integrated_config.write_text(
            policy.render_config_block(manifest, checkout, prompt_skills_root),
            encoding="utf-8",
        )
        payload = _prompt_input(
            ROOT,
            clean_home,
            temporary / "clean-codex-home",
            integrated_config,
        )
        prompt_errors = policy.validate_prompt_input(
            manifest,
            payload,
            prompt_skills_root,
            matt_catalog,
            aria_skills_root=prompt_skills_root,
        )
        assert not prompt_errors, prompt_errors
        prompt_entries = policy.prompt_skill_entries(payload)
        integrated = [
            (Path(path).resolve().parent.name, description, path)
            for name, description, path in prompt_entries
            if Path(path).resolve().is_relative_to(prompt_skills_root.resolve())
            and Path(path).resolve().parent.name in aria_names | matt_names
        ]
        assert len(integrated) == len(aria_names) + len(matt_names) == 16
        assert len({name for name, _, _ in integrated}) == 16
        integrated_bytes = sum(
            len(description.encode("utf-8")) for _, description, _ in integrated
        )
        assert integrated_bytes == manifest["budget"]["integrated_description_bytes"]
        assert integrated_bytes <= manifest["budget"]["maximum_description_bytes"]

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
                manifest,
                checkout,
                policy.discover_catalog(checkout),
                skills_root,
                collision_root,
            )
        except policy.PolicyError:
            pass
        else:
            raise AssertionError("bootstrap accepted an existing global path collision")
        assert sentinel.read_text(encoding="utf-8") == "preserve"

        nested_collision_root = temporary / "nested-collision-root"
        nested_collision = nested_collision_root / "nested/user-copy"
        nested_collision.mkdir(parents=True)
        (nested_collision / "SKILL.md").write_text(
            "---\nname: ask-matt\ndescription: Nested collision.\n---\n",
            encoding="utf-8",
        )
        try:
            bootstrap._deploy_transaction(
                manifest,
                checkout,
                policy.discover_catalog(checkout),
                skills_root,
                nested_collision_root,
            )
        except policy.PolicyError as exc:
            assert "ask-matt" in str(exc)
        else:
            raise AssertionError("bootstrap accepted a nested skill id collision")
        assert (nested_collision / "SKILL.md").is_file()

        invalid_staging = temporary / "invalid-staging"
        shutil.copytree(skills_root, invalid_staging)
        invalid_file = invalid_staging / "tdd/tests.md"
        invalid_file.write_bytes(invalid_file.read_bytes() + b"corrupt\n")
        transactional_root = temporary / "transactional-root"
        try:
            bootstrap._deploy_transaction(
                manifest,
                checkout,
                policy.discover_catalog(checkout),
                invalid_staging,
                transactional_root,
            )
        except policy.PolicyError as exc:
            assert "failed validation" in str(exc)
        else:
            raise AssertionError("bootstrap accepted an invalid deployed root")
        assert not transactional_root.exists()

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
