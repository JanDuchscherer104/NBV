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
    with pytest.raises(ValueError, match="nonempty titles and bodies"):
        ExplanationSection("", "body")
    with pytest.raises(ValueError, match="nonempty titles and bodies"):
        ExplanationSection("title", "")


def test_source_and_external_reference_fields_fail_closed() -> None:
    with pytest.raises(ValueError, match="nonempty source fields"):
        _explanation(source_fields=("",))
    with pytest.raises(ValueError, match="nonempty labels and URLs"):
        _explanation(external_references=(("", "https://example.com"),))
    with pytest.raises(ValueError, match="nonempty labels and URLs"):
        _explanation(external_references=(("source", ""),))


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
    immediate, cumulative, endpoint = gain.equations
    assert r"r_t^e" in immediate.tex
    assert r"\sum" in cumulative.tex
    assert r"J_t^e" in cumulative.tex
    assert endpoint.tex != immediate.tex
    assert cumulative.tex != endpoint.tex
    assert len(geometry.equations) == 2
    assert geometry.equations[0].tex != geometry.equations[1].tex
    assert "support" in geometry.equations[0].tex
    assert "trajectory" in geometry.equations[1].tex


def test_invalid_theory_warns_and_allows_remaining_guide(monkeypatch: pytest.MonkeyPatch) -> None:
    warnings: list[str] = []
    rendered: list[str] = []
    monkeypatch.setattr(shared, "resolve_theory", lambda _theory: (_ for _ in ()).throw(TheoryResolutionError("bad")))
    monkeypatch.setattr(shared.st, "warning", warnings.append)
    monkeypatch.setattr(shared.st, "markdown", lambda value, **_kwargs: rendered.append(str(value)))
    explanation = _explanation(
        sections=(ExplanationSection("Metric", "A descriptive value."),),
        theory=TheoryReferences(symbol_ids=("missing.symbol",)),
        external_references=(("Reference", "https://example.com/reference"),),
    )
    shared._render_scientific_guide(explanation, log_y_key=None)
    assert warnings and "Canonical theory unavailable" in warnings[0]
    rendered_text = "\n".join(rendered)
    assert "Metric" in rendered_text
    assert "inspection.rows" in rendered_text
    assert "https://example.com/reference" in rendered_text


def test_render_plot_keeps_answer_visible_and_guide_reusable() -> None:
    source = Path(shared.__file__).read_text(encoding="utf-8")
    assert 'st.markdown(f"**Answer:** {explanation.answer}")' in source
    assert "render_explanation_popover(" in source
    assert "_render_scientific_guide(explanation" in source
    assert "_render_theory(explanation.theory)" in source
