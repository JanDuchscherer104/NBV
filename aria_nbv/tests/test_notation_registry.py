from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_notation_keys_match_their_typst_facades() -> None:
    notation = yaml.safe_load((ROOT / "docs" / "notation.yml").read_text(encoding="utf-8"))

    for key, entry in notation["symbols"].items():
        assert entry["typst"] == f"#symb.{key}"
    for key, entry in notation["equations"].items():
        assert entry["typst"] == f"#eqs.{key}"

    assert "rri.cd_value" not in notation["symbols"]
    assert {
        "oracle.err",
        "oracle.dist_pm",
        "oracle.dist_mp",
        "entity.target_reward",
        "rl.observed_cumulative_root_gain",
    } <= notation["symbols"].keys()
    assert "rl.observed_cumulative_root_gain" in notation["equations"]

    for key in (
        "oracle.dist_pm",
        "oracle.dist_mp",
        "rl.observed_cumulative_root_gain",
    ):
        assert "\\\\" not in notation["symbols"][key]["tex"]
