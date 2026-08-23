"""Verify the real Q_H readiness and collation path against G007 identity."""

from __future__ import annotations

import json
import subprocess
from dataclasses import fields
from pathlib import Path

from aria_nbv.data_handling.qh_data.batching import QhBatch
from aria_nbv.dataset_bundle import (
    DatasetBundleSelection,
    QhReadinessContract,
    _build_qh_data_module,
    build_qh_corpus_readiness,
    preview_qh_batch,
)
from aria_nbv.utils import Stage
from aria_nbv.utils.fingerprints import stable_msgspec_hash


WORKTREE = Path(__file__).parents[6]
ROOT_STORE = Path("/home/jd/repos/ARIA-NBV/.data/offline_cache/vin_offline_rollout_campaign100_v10_rebuilt")
STORE = WORKTREE / ".omx/evidence/streamlit-qh/g007/runtime-proof/final-a0b80ae8dc/cuda-rollouts-v1-g007-v10-one-unit/shards/a4cff23e3ebca79b"
IDENTITY_PATH = WORKTREE / ".omx/evidence/streamlit-qh/g007/runtime-proof/final-a0b80ae8dc/qh-identity-batch.json"
OUT_PATH = Path(__file__).with_name("qh-readiness-evidence.json")
CONTRACT = QhReadinessContract(
    experiment_profile="qh_cf0_v1",
    root_evl_profile="evl_v1",
    selected_observation_protocol="none",
)


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=WORKTREE, text=True).strip()


def _run(seed: int) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    selection = DatasetBundleSelection(root_store=ROOT_STORE, rollout_stores=(STORE,))
    readiness = build_qh_corpus_readiness(selection, contract=CONTRACT, batch_size=1, seed=seed)
    preview = preview_qh_batch(selection, contract=CONTRACT, stage=Stage.TRAIN, chain_index=0, batch_size=1, seed=seed)
    datasets, module = _build_qh_data_module(selection, contract=CONTRACT, batch_size=1, seed=seed)
    train = datasets[Stage.TRAIN]
    loader = module.train_dataloader()
    first_batch = next(iter(loader))
    selected_rows = 0
    for batch in loader:
        selected_rows += int(batch.selected_train_mask.sum().item())
    return (
        readiness.to_jsonable(),
        preview.to_jsonable(),
        {
            "actor_state_contract_hash": module.actor_state_contract_hash,
            "learning_contract_hash": module.learning_contract_hash,
            "rollout_contract_hash": stable_msgspec_hash(train.contract),
            "dataset_len": len(train),
            "chain_steps": [int(train[index].num_steps) for index in range(len(train))],
            "batch_fields": [field.name for field in fields(QhBatch)],
            "batch_type": type(first_batch).__name__,
            "batch_candidate_width": int(first_batch.actor.candidate_mask.shape[-1]),
            "batch_size": int(first_batch.actor.candidate_mask.shape[0]),
            "batch_steps": int(first_batch.num_steps[0].item()),
            "batch_root_evl_present": bool(first_batch.actor.static_context.evl_presence.all().item()),
            "trainable_selected_rows": selected_rows,
        },
    )


def main() -> None:
    identity = json.loads(IDENTITY_PATH.read_text())
    readiness0, preview0, actual0 = _run(seed=0)
    _, preview0_repeat, actual0_repeat = _run(seed=0)
    _, preview1, actual1 = _run(seed=1)
    expected = {
        "actor_state_contract_hash": identity["actor_state_contract_hash"],
        "learning_contract_hash": identity["learning_contract_hash"],
        "dataset_len": identity["dataset_len"],
        "batch_candidate_width": identity["batch_candidate_width"],
        "batch_fields": identity["batch_fields"],
        "batch_type": identity["batch_type"],
        "batch_size": identity["batch_size"],
        "batch_steps": identity["batch_steps"],
        "batch_root_evl_present": identity["batch_root_evl_present"],
        "trainable_selected_rows": identity["trainable_selected_rows"],
    }
    comparisons = {
        key: {"expected": expected[key], "actual": actual0[key], "match": expected[key] == actual0[key]}
        for key in expected
    }
    matches = [row["match"] for row in comparisons.values()]
    evidence = {
        "schema_version": "streamlit-qh-g005-v10-readiness-v1",
        "verification_status": "blocked" if not all(matches) else "passed",
        "blockers": [
            f"G007 identity field {key!r} differs: expected {row['expected']!r}, actual {row['actual']!r}."
            for key, row in comparisons.items()
            if not row["match"]
        ],
        "product_head": _git_head(),
        "selection": {
            "root_store": ROOT_STORE.as_posix(),
            "rollout_store": STORE.as_posix(),
            "profile": "qh_cf0_v1",
            "root_evl_profile": "evl_v1",
            "selected_observation_protocol": "none",
            "split": "train",
        },
        "contract_hashes": {
            "actor_state": actual0["actor_state_contract_hash"],
            "learning": actual0["learning_contract_hash"],
            "rollout_data": actual0["rollout_contract_hash"],
        },
        "readiness": readiness0,
        "actual_path": actual0,
        "g007_identity": identity,
        "field_comparison": comparisons,
        "determinism": {
            "same_seed_preview_identical": preview0 == preview0_repeat,
            "same_seed_contract_identity_identical": actual0 == actual0_repeat,
            "changed_seed_preview": {
                "seed_0": preview0,
                "seed_1": preview1,
                "different": preview0 != preview1,
            },
            "changed_seed_contract_identity_identical": actual0 == actual1,
        },
        "commands": {
            "construction": "build_qh_corpus_readiness + preview_qh_batch + _build_qh_data_module (batch_size=1, num_workers=0, seed=0)",
            "script": "verify_v10_qh_path.py",
        },
    }
    OUT_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"path": OUT_PATH.as_posix(), "status": evidence["verification_status"], "blockers": evidence["blockers"]}, indent=2))


if __name__ == "__main__":
    main()
