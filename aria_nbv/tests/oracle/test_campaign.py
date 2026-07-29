from __future__ import annotations

from pathlib import Path

import pytest

from aria_nbv.oracle.pipelines.campaign import (
    CampaignRuntimeConfig,
    CampaignSceneExhaustedError,
    CampaignSourceIneligibleError,
    CampaignSourceSelection,
    CandidateProfileConfig,
    RolloutCampaign,
    RolloutCampaignConfig,
)
from aria_nbv.oracle.pipelines.root_selection import RankedSnippet, RootInventory, SceneRootCandidates
from aria_nbv.targets.protocol import TargetInputProtocol


def _inventory(count: int) -> RootInventory:
    scenes = []
    for index in range(count):
        scene_id = str(80000 + index)
        scenes.append(
            SceneRootCandidates(
                scene_id=scene_id,
                mesh_path=Path(f"/meshes/scene_ply_{scene_id}.ply"),
                candidates=(
                    RankedSnippet(
                        sample_key=f"AriaSyntheticEnvironment_{scene_id}_AtekDataSample_000000",
                        shard_path=Path(f"/efm/{scene_id}/shards-0000.tar"),
                        rank_digest=f"{index:064x}",
                    ),
                ),
            )
        )
    return RootInventory(seed=17, scenes=tuple(scenes))


def test_default_campaign_assigns_balanced_challengers_and_stable_panel() -> None:
    inventory = _inventory(100)
    config = RolloutCampaignConfig(seed=17)
    campaign = RolloutCampaign(config)

    first = campaign.planned_profiles_by_scene(inventory)
    second = campaign.planned_profiles_by_scene(inventory)

    assert first == second
    assert sum(len(profiles) for profiles in first.values()) == 240
    assert all(config.realistic_profile in profiles for profiles in first.values())
    assert sum(len(profiles) == 4 for profiles in first.values()) == 20
    non_panel = [profiles for profiles in first.values() if len(profiles) == 2]
    challenger_counts = {name: sum(name in profiles for profiles in non_panel) for name in config.challenger_profiles}
    assert max(challenger_counts.values()) - min(challenger_counts.values()) <= 1


def test_campaign_rejects_candidate_budget_and_target_caps() -> None:
    with pytest.raises(ValueError, match="exactly 60"):
        CandidateProfileConfig(
            candidate_mixture=RolloutCampaignConfig()
            .profiles["realistic_core_60"]
            .candidate_mixture.model_copy(
                update={
                    "components": RolloutCampaignConfig().profiles["realistic_core_60"].candidate_mixture.components[:1]
                }
            )
        )

    with pytest.raises(ValueError, match="admit every"):
        RolloutCampaignConfig(target_sampler={"max_targets_per_sample": 1})

    with pytest.raises(ValueError, match="at least one challenger"):
        RolloutCampaignConfig(challenger_profiles=())


def test_run_stops_after_fresh_shard_budget_and_writes_status(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = _inventory(2)
    config = RolloutCampaignConfig(
        expected_scene_count=2,
        paired_panel_scene_count=0,
        output_root=tmp_path / "output",
        evidence_dir=tmp_path / "evidence",
        collection_dir=tmp_path / "collection",
        runtime=CampaignRuntimeConfig(max_new_shards=1, keep_free_disk_gib=0.0),
    )
    campaign = RolloutCampaign(config)
    calls: list[tuple[str, str]] = []

    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.discover_ase_root_inventory",
        lambda **_: inventory,
    )
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.write_root_inventory",
        lambda *_, **__: config.root_inventory_path,
    )

    def select_source(scene: SceneRootCandidates) -> CampaignSourceSelection:
        return CampaignSourceSelection(
            scene_id=scene.scene_id,
            candidate=scene.selected,
            store_dir=tmp_path / "sources" / scene.scene_id,
            split="train",
            target_ids=(f"target-{scene.scene_id}",),
        )

    def run_profile(source: CampaignSourceSelection, *, profile_name: str) -> bool:
        calls.append((source.scene_id, profile_name))
        return False

    monkeypatch.setattr(campaign, "_select_source", select_source)
    monkeypatch.setattr(campaign, "_run_profile_shard", run_profile)

    result = campaign.run()

    assert result.reason == "max_new_shards"
    assert result.new_shards == 1
    assert len(calls) == 1
    assert result.status_path.is_file()


def test_fresh_attempt_paths_preserve_existing_attempts(tmp_path: Path) -> None:
    parent = tmp_path / "attempts"
    first = RolloutCampaign._fresh_attempt_dir(parent, "abcdef")
    (first / "evidence.txt").write_text("preserve", encoding="utf-8")
    second = RolloutCampaign._fresh_attempt_dir(parent, "abcdef")

    assert first != second
    assert (first / "evidence.txt").read_text(encoding="utf-8") == "preserve"


def test_derived_writer_uses_v1_sampler_and_one_source_row(tmp_path: Path) -> None:
    config = RolloutCampaignConfig(output_root=tmp_path / "output", evidence_dir=tmp_path / "evidence")
    campaign = RolloutCampaign(config)
    source = CampaignSourceSelection(
        scene_id="81286",
        candidate=RankedSnippet(
            sample_key="AriaSyntheticEnvironment_81286_AtekDataSample_000000",
            shard_path=tmp_path / "shards-0000.tar",
            rank_digest="a" * 64,
        ),
        store_dir=tmp_path / "source",
        split="train",
        target_ids=("observed-target",),
    )

    writer = campaign._derive_writer_config(
        source,
        profile=config.profiles[config.realistic_profile],
        final_dir=tmp_path / "rollout",
    )

    assert writer.store.target_protocol_version is TargetInputProtocol.V1_OBSERVED
    assert writer.observed_target_task_sampler.max_targets_per_sample is None
    assert writer.max_targets_per_sample is None
    assert writer.max_samples == 1
    assert writer.source.limit == 1


def test_source_selection_advances_only_for_typed_ineligibility(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first, second = (
        RankedSnippet(
            sample_key=f"AriaSyntheticEnvironment_81286_AtekDataSample_{index:06d}",
            shard_path=tmp_path / f"shards-{index:04d}.tar",
            rank_digest=str(index) * 64,
        )
        for index in range(2)
    )
    scene = SceneRootCandidates(
        scene_id="81286",
        mesh_path=tmp_path / "scene_ply_81286.ply",
        candidates=(first, second),
    )
    config = RolloutCampaignConfig(
        output_root=tmp_path / "output",
        evidence_dir=tmp_path / "evidence",
        collection_dir=tmp_path / "collection",
    )
    campaign = RolloutCampaign(config)
    campaign._prepare_paths()
    attempts: list[str] = []

    def build_source(_scene: SceneRootCandidates, candidate: RankedSnippet) -> CampaignSourceSelection:
        attempts.append(candidate.sample_key)
        if candidate is first:
            raise CampaignSourceIneligibleError("no IoU-admitted target")
        return CampaignSourceSelection(
            scene_id=scene.scene_id,
            candidate=candidate,
            store_dir=tmp_path / "source",
            split="train",
            target_ids=("observed-target",),
        )

    monkeypatch.setattr(campaign, "_build_and_validate_source", build_source)

    selected = campaign._select_source(scene)

    assert selected.candidate is second
    assert attempts == [first.sample_key, second.sample_key]
    assert campaign._events()[0]["event"] == "source_rejected"


def test_source_operational_failure_propagates_without_reserve_storm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    scene = _inventory(1).scenes[0]
    config = RolloutCampaignConfig(
        expected_scene_count=1,
        paired_panel_scene_count=0,
        output_root=tmp_path / "output",
        evidence_dir=tmp_path / "evidence",
        collection_dir=tmp_path / "collection",
    )
    campaign = RolloutCampaign(config)
    campaign._prepare_paths()
    attempts = 0

    def fail_operationally(*_: object, **__: object) -> CampaignSourceSelection:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("global CUDA initialization failed")

    monkeypatch.setattr(campaign, "_build_and_validate_source", fail_operationally)

    with pytest.raises(RuntimeError, match="global CUDA"):
        campaign._select_source(scene)

    assert attempts == 1
    assert campaign._events() == []


def test_run_bounds_systemic_rollout_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = _inventory(4)
    config = RolloutCampaignConfig(
        expected_scene_count=4,
        paired_panel_scene_count=0,
        output_root=tmp_path / "output",
        evidence_dir=tmp_path / "evidence",
        collection_dir=tmp_path / "collection",
        runtime=CampaignRuntimeConfig(max_failed_units=2, keep_free_disk_gib=0.0),
    )
    campaign = RolloutCampaign(config)
    attempts = 0

    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.discover_ase_root_inventory", lambda **_: inventory)
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.write_root_inventory",
        lambda *_, **__: config.root_inventory_path,
    )
    monkeypatch.setattr(
        campaign,
        "_select_source",
        lambda scene: CampaignSourceSelection(
            scene_id=scene.scene_id,
            candidate=scene.selected,
            store_dir=tmp_path / "source" / scene.scene_id,
            split="train",
            target_ids=("observed-target",),
        ),
    )

    def fail_rollout(*_: object, **__: object) -> bool:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("systemic renderer failure")

    monkeypatch.setattr(campaign, "_run_profile_shard", fail_rollout)

    result = campaign.run()

    assert result.reason == "failure_limit"
    assert result.failed_shards == 2
    assert result.failed_scenes == 0
    assert attempts == 2


def test_nonfatal_rollout_failure_leaves_campaign_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = _inventory(1)
    config = RolloutCampaignConfig(
        expected_scene_count=1,
        paired_panel_scene_count=0,
        output_root=tmp_path / "output",
        evidence_dir=tmp_path / "evidence",
        collection_dir=tmp_path / "collection",
        runtime=CampaignRuntimeConfig(max_failed_units=2, keep_free_disk_gib=0.0),
    )
    campaign = RolloutCampaign(config)
    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.discover_ase_root_inventory", lambda **_: inventory)
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.write_root_inventory",
        lambda *_, **__: config.root_inventory_path,
    )
    monkeypatch.setattr(
        campaign,
        "_select_source",
        lambda scene: CampaignSourceSelection(
            scene_id=scene.scene_id,
            candidate=scene.selected,
            store_dir=tmp_path / "source" / scene.scene_id,
            split="train",
            target_ids=("observed-target",),
        ),
    )

    def run_profile(_source: CampaignSourceSelection, *, profile_name: str) -> bool:
        if profile_name == config.realistic_profile:
            raise RuntimeError("one shard failed")
        return False

    monkeypatch.setattr(campaign, "_run_profile_shard", run_profile)

    result = campaign.run()

    assert result.reason == "incomplete"
    assert result.failed_shards == 1
    assert result.new_shards == 1


def test_exhausted_scene_is_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    inventory = _inventory(1)
    config = RolloutCampaignConfig(
        expected_scene_count=1,
        paired_panel_scene_count=0,
        output_root=tmp_path / "output",
        evidence_dir=tmp_path / "evidence",
        collection_dir=tmp_path / "collection",
        runtime=CampaignRuntimeConfig(keep_free_disk_gib=0.0),
    )
    campaign = RolloutCampaign(config)
    monkeypatch.setattr("aria_nbv.oracle.pipelines.campaign.discover_ase_root_inventory", lambda **_: inventory)
    monkeypatch.setattr(
        "aria_nbv.oracle.pipelines.campaign.write_root_inventory",
        lambda *_, **__: config.root_inventory_path,
    )
    monkeypatch.setattr(
        campaign,
        "_select_source",
        lambda _scene: (_ for _ in ()).throw(CampaignSceneExhaustedError("no admitted target")),
    )

    result = campaign.run()

    assert result.reason == "incomplete"
    assert result.failed_scenes == 1
