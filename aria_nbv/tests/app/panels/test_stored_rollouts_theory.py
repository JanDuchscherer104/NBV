"""Focused regressions for the shared stored-rollout theory presentation seam."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
import streamlit as st

from aria_nbv.app.panels._stored_rollouts import candidate_generation, overview_topology, reconstruction_return, shared
from aria_nbv.app.panels._stored_rollouts.shared import ExplanationSection, ScientificExplanation
from aria_nbv.app.scientific_labels import TheoryReferences, TheoryResolutionError, resolve_theory


def _explanation(**kwargs: Any) -> ScientificExplanation:
    values: dict[str, Any] = {
        "question": "What does this show?",
        "answer": "It shows persisted scientific evidence.",
        "sections": (),
        "evidence_role": "provenance",
        "source_fields": ("inspection.rows",),
    }
    values.update(kwargs)
    return ScientificExplanation(**values)


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
    monkeypatch.setattr(st, "warning", warnings.append)
    monkeypatch.setattr(st, "markdown", lambda value, **_kwargs: rendered.append(str(value)))
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


def test_render_plot_delegates_answer_to_one_guide_owner() -> None:
    source = Path(shared.__file__).read_text(encoding="utf-8")
    assert 'st.markdown(f"**Answer:** {explanation.answer}")' not in source
    assert source.count('explanation_item("Answer", explanation.answer)') == 1
    assert "render_explanation_popover(" in source
    assert "_render_scientific_guide(explanation" in source
    assert "_render_theory(explanation.theory)" in source


def test_stored_rollout_plot_answers_are_not_generic() -> None:
    generic = "This plot answers the question using the persisted evidence rows"
    for module in (candidate_generation, overview_topology, reconstruction_return, shared):
        module_path = module.__file__
        assert module_path is not None
        assert generic not in Path(module_path).read_text(encoding="utf-8")


def test_candidate_population_literal_questions_have_authored_answers() -> None:
    source = Path(candidate_generation.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    literal_questions = {
        node.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_candidate_population_explanation"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    }
    assert literal_questions <= set(candidate_generation._CANDIDATE_POPULATION_ANSWERS)


def test_scientific_guide_has_one_ordered_narrative_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    rendered: list[str] = []
    monkeypatch.setattr(st, "markdown", lambda value, **_kwargs: rendered.append(str(value)))
    shared._render_scientific_guide(_explanation(), log_y_key=None)
    text = "\n".join(rendered)
    assert text.index("### Core idea") < text.index("**Question**") < text.index("**Answer**")
    assert text.count("**Answer**") == 1


def test_corpus_selection_diagnostics_are_probability_entropy_only_and_theory_backed() -> None:
    assert reconstruction_return._SELECTION_DIAGNOSTIC_METRICS == ("selected_probability", "selected_entropy")
    assert "selected_target_rri" not in reconstruction_return._SELECTION_DIAGNOSTIC_METRICS
    for metric in reconstruction_return._SELECTION_DIAGNOSTIC_METRICS:
        explanation = reconstruction_return._selection_diagnostic_explanation(metric)
        assert explanation.theory == reconstruction_return._temporal_theory(metric)
        assert explanation.theory is not None
        assert explanation.theory.equation_ids == ("action.robust_temperature_softmax",)
