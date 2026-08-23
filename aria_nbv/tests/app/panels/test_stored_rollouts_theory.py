"""Focused regressions for the shared stored-rollout theory presentation seam."""

from __future__ import annotations

from pathlib import Path

import pytest

from aria_nbv.app.panels._stored_rollouts import shared
from aria_nbv.app.panels._stored_rollouts.shared import ExplanationSection, ScientificExplanation
from aria_nbv.app.scientific_labels import TheoryReferences, TheoryResolutionError, resolve_theory


def _explanation(**kwargs: object) -> ScientificExplanation:
    values: dict[str, object] = {
        "question": "What does this show?",
        "answer": "It shows persisted scientific evidence.",
        "sections": (),
        "evidence_role": "provenance",
        "source_fields": ("inspection.rows",),
    }
    values.update(kwargs)
    return ScientificExplanation(**values)  # type: ignore[arg-type]


def test_author_shaped_explanations_may_omit_optional_sections() -> None:
    explanation = _explanation()
    assert explanation.sections == ()


def test_supplied_explanation_sections_remain_strictly_nonempty() -> None:
    with pytest.raises(ValueError, match="ordered nonempty"):
        _explanation(sections=(ExplanationSection("", "body"),))
    with pytest.raises(ValueError, match="ordered nonempty"):
        _explanation(sections=(ExplanationSection("title", ""),))


def test_gain_and_geometry_theory_references_resolve_from_current_registry() -> None:
    root = Path(__file__).parents[4]
    gain = resolve_theory(
        TheoryReferences(
            equation_ids=(
                "rl.target_root_gain_reward",
                "rl.cumulative_target_root_gain",
                "entity.endpoint_gain",
            ),
            symbol_ids=("entity.target_reward", "entity.target_root_gain_cumulative", "entity.endpoint_gain"),
        ),
        root=root,
    )
    geometry = resolve_theory(
        TheoryReferences(
            equation_ids=(
                "spatial.candidate_proposal_support_normalization",
                "spatial.rollout_trajectory_normalization",
            )
        ),
        root=root,
    )
    assert [item.identifier for item in gain.equations] == [
        "rl.target_root_gain_reward",
        "rl.cumulative_target_root_gain",
        "entity.endpoint_gain",
    ]
    assert {item.identifier for item in gain.symbols} == {
        "entity.target_reward",
        "entity.target_root_gain_cumulative",
        "entity.endpoint_gain",
    }
    assert len(geometry.equations) == 2


def test_invalid_theory_warns_and_allows_remaining_guide(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    monkeypatch.setattr(shared, "resolve_theory", lambda _theory: (_ for _ in ()).throw(TheoryResolutionError("bad")))
    monkeypatch.setattr(shared.st, "warning", warnings.append)
    shared._render_theory(TheoryReferences(symbol_ids=("missing.symbol",)))
    assert warnings and "Canonical theory unavailable" in warnings[0]


def test_render_plot_keeps_answer_visible_and_guide_reusable() -> None:
    source = Path(shared.__file__).read_text(encoding="utf-8")
    assert 'st.markdown(f"**Answer:** {explanation.answer}")' in source
    assert "_render_interpretation_guide(explanation" in source
    assert "_render_theory(explanation.theory)" in source
