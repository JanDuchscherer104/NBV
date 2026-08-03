.DEFAULT_GOAL := help
.PHONY: help ci ci-impact-self-test graphify-skill-upstream-self-test graphify-projection-self-test graphify-projection-live-check graphify-refresh graphify-optional-check graphify-usable-check graphify-state-check graphify-publish-check scaffold-check agents-db-validate package-smoke qh-ci docs-render-core quarto-docs-ci typst-paper-ci
.PHONY: api-docs-self-test
.PHONY: context-qmd-tree qmd-frontmatter-check
.PHONY: context-index context-get context-contracts context-modules context-classes context-functions
.PHONY: context-match context-qmd-outline context-typst-outline context-typst-includes
.PHONY: context-literature-index context-literature-search migrate-codex-memory codex-transcripts
.PHONY: context-heavy context-uml context-uml-preview context-docstrings context-tree context-dir-tree context-dir-tree-external scaffold-audit scaffold-audit-self-test check-agent-memory new-debrief install-git-hooks install-hooks
.PHONY: agents-db glossary
.PHONY: lrz-probe lrz-resources lrz-resources-gpu lrz-resources-cpu lrz-jobs lrz-dss-init lrz-container-shell lrz-sbatch-cpu lrz-sbatch-single-gpu lrz-sbatch-multigpu
.PHONY: mermaid-lint
.PHONY: offline-info offline-tree offline-samples offline-random-index offline-rerun-random offline-sample-rerun-random
.PHONY: rollouts-info rollouts-stats rollouts-random-index rollouts-rerun-random

# Color codes
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m
RED := \033[0;31m
GIT_CLEAN_ENV := env -u GIT_ALTERNATE_OBJECT_DIRECTORIES -u GIT_COMMON_DIR \
	-u GIT_DIR -u GIT_INDEX_FILE -u GIT_OBJECT_DIRECTORY -u GIT_PREFIX \
	-u GIT_WORK_TREE

# Project directories
PKG_DIR := aria_nbv
SRC_DIR := aria_nbv
TEST_DIR := tests
DOCS_DIR := docs
TYPST ?= typst
TYPST_ROOT ?= docs
TYPST_PAPER ?= $(DOCS_DIR)/typst/seminar_paper/main.typ
TYPST_PAPER_PDF ?= $(DOCS_DIR)/typst/seminar_paper/main.pdf
TYPST_THESIS ?= $(DOCS_DIR)/typst/thesis/main.typ
TYPST_THESIS_PDF ?= $(DOCS_DIR)/typst/thesis/main.pdf
TYPST_SLIDES_DIR ?= $(DOCS_DIR)/typst/seminar_slides
CI_RENDER_DIR ?= $(CURDIR)/.cache/ci-renders
SLIDES ?= slides_4.typ
SLIDES_FILE := $(if $(filter %.typ,$(SLIDES)),$(SLIDES),$(SLIDES).typ)
SLIDES_SRC := $(if $(findstring /,$(SLIDES_FILE)),$(SLIDES_FILE),$(TYPST_SLIDES_DIR)/$(SLIDES_FILE))
SLIDES_PDF ?= $(SLIDES_SRC:.typ=.pdf)

# Python interpreter (uv-managed .venv by default)
VENV_PYTHON ?= $(CURDIR)/aria_nbv/.venv/bin/python
PYTHON_INTERPRETER ?= $(VENV_PYTHON)
FORCE_ACTIV_CONDA_ENV ?= 0  # set to 1 only if you insist on the old conda env check
CONDA_ENV_NAME ?= aria-nbv       # legacy: expected conda env name
QMD_FORMATTER := scripts/format_qmd_lists.py
CONTEXT_DIR ?= docs/_generated/context
CONTEXT_OUT ?= $(CONTEXT_DIR)/context_snapshot.md
CONTEXT_INDEX_OUT ?= $(CONTEXT_DIR)/source_index.md
CONTEXT_UML_OUT ?= $(CONTEXT_DIR)/aria_nbv_uml.mmd
CONTEXT_UML_FILTERED_OUT ?= $(CONTEXT_DIR)/aria_nbv_filtered_uml.mmd
CONTEXT_DOCSTRINGS_OUT ?= $(CONTEXT_DIR)/aria_nbv_class_docstrings.md
CONTEXT_CONTRACTS_OUT ?= $(CONTEXT_DIR)/data_contracts.md
CONTEXT_TREE_OUT ?= $(CONTEXT_DIR)/aria_nbv_tree.md
CONTEXT_MERMAID_EXCLUDE ?= data.downloader,vin.experimental,app
LITERATURE_INDEX_OUT ?= $(CONTEXT_DIR)/literature_index.md
GET_CONTEXT_MODE ?= packages
GET_CONTEXT_QUERY ?=
GET_CONTEXT_ROOT ?=
QMD_OUTLINE_ARGS ?= --compact
TYPST_OUTLINE_ARGS ?= --paper --mode outline
TYPST_INCLUDES_ARGS ?= --paper --mode includes
LITERATURE_SEARCH_QUERY ?=
MIGRATE_CODEX_MEMORY_ARGS ?=
CODEX_TRANSCRIPT_ARGS ?=
MERMAID_RENDER ?= tools/mermaid/scripts/render_mermaid.sh
MMD_DIR ?= external/mmdc-examples
MMD_OUT ?= $(MMD_DIR)
MMD_FORMAT ?= png
MMD_SCALE ?= 4
MERMAID_LINT ?= tools/mermaid/scripts/aria_mermaid_lint.py
MERMAID_LINT_FILES ?= $(shell git ls-files '*.mmd')
LRZ_SKILL_DIR ?= .agents/skills/lrz-ai-systems
LRZ_SCRIPTS_DIR ?= $(LRZ_SKILL_DIR)/scripts
LRZ_RESOURCES_ARGS ?= summary
LRZ_CMD ?=
PACKAGE_SMOKE_RUFF_PATHS := \
	aria_nbv/app/panels/vin_diagnostics_runtime.py \
	aria_nbv/data_handling/vin_store/writer.py \
	aria_nbv/pose_generation/types.py \
	aria_nbv/rendering/candidate_depth_renderer.py \
	tests/data_handling/test_vin_offline_store.py \
	tests/data_handling/test_public_api_contract.py \
	tests/rollouts/test_counterfactuals.py \
	tests/rendering/test_candidate_renderer_cpu_backend.py \
	tests/lightning/test_vin_batch_collate.py \
	tests/app/panels/test_vin_diagnostics_runtime.py \
	tests/vin/test_vin_diagnostics_runtime.py
PACKAGE_SMOKE_TESTS := \
	tests/data_handling/test_vin_offline_store.py \
	tests/data_handling/test_public_api_contract.py \
	tests/rollouts/test_counterfactuals.py \
	tests/rendering/test_candidate_renderer_cpu_backend.py \
	tests/lightning/test_vin_batch_collate.py \
	tests/app/panels/test_vin_diagnostics_runtime.py \
	tests/vin/test_vin_diagnostics_runtime.py
QH_CI_RUFF_PATHS := \
	aria_nbv/data_handling/__init__.py \
	aria_nbv/data_handling/qh_data \
	aria_nbv/lightning/qh_datamodule.py \
	aria_nbv/lightning/qh_module.py \
	aria_nbv/rollouts/qh_reader.py \
	aria_nbv/vin/models/__init__.py \
	tests/data_handling/test_qh.py \
	tests/data_handling/test_public_api_contract.py \
	tests/data_handling/test_vin_offline_store.py \
	tests/rollouts/test_qh_reader.py \
	tests/rollouts/test_public_rollouts_api.py \
	tests/rollouts/test_zarr_store.py \
	tests/vin/test_models_namespace.py \
	tests/lightning/test_candidate_scorer_contract.py \
	tests/lightning/test_optimizer_finite_values.py \
	tests/lightning/test_qh_datamodule.py \
	tests/lightning/test_qh_module.py \
	tests/lightning/test_qh_fast_dev_run.py \
	tests/lightning/test_qh_torchrun_smoke.py \
	tests/lightning/qh_torchrun_worker.py \
	tests/targets/test_protocol.py \
	tests/test_config_field_constraints.py \
	../scripts/tests/test_quartodoc_expand_config.py
QH_CI_TESTS := \
	tests/rollouts/test_qh_reader.py \
	tests/data_handling/test_qh.py \
	tests/lightning/test_qh_datamodule.py \
	tests/lightning/test_qh_module.py \
	tests/lightning/test_qh_fast_dev_run.py \
	tests/lightning/test_qh_torchrun_smoke.py \
	tests/targets/test_protocol.py \
	tests/rollouts/test_zarr_store.py \
	tests/rollouts/test_public_rollouts_api.py \
	tests/data_handling/test_vin_offline_store.py \
	tests/data_handling/test_public_api_contract.py \
	tests/vin/test_models_namespace.py \
	tests/lightning/test_candidate_scorer_contract.py \
	tests/lightning/test_optimizer_finite_values.py \
	tests/test_config_field_constraints.py \
	../scripts/tests/test_quartodoc_expand_config.py
QH_CI_PYTHON ?= uv run --extra dev python
PYTEST_ARGS ?= -n auto

# Read-only operator inspection defaults.
OFFLINE_STORE ?= vin_offline
OFFLINE_SPLIT ?= train
OFFLINE_MAX_SAMPLES ?= 128
OFFLINE_SAMPLE_LIMIT ?= 20
OFFLINE_SEED ?=
ROLLOUT_STORE ?= rollouts_v1_realistic.zarr
ROLLOUT_MIN_HORIZON ?= 2
ROLLOUT_SEED ?=
RERUN_MODE ?= view
RERUN_CONFIG ?= ../.configs/rerun_offline.toml
RERUN_SAVE ?= ../.artifacts/rerun/offline_random.rrd
ROLLOUT_RERUN_SAVE ?= ../.artifacts/rerun/rollout_random.rrd

#  ══════════════════════════════════════════════════════════════════════
#  Agent Context helpers
#  ══════════════════════════════════════════════════════════════════════

.PHONY: _check_python
_check_python:
	@if ! { [ -x "$(PYTHON_INTERPRETER)" ] || command -v "$(PYTHON_INTERPRETER)" >/dev/null 2>&1; }; then \
		echo "$(RED)🚫 Python interpreter not found at $(PYTHON_INTERPRETER)$(NC)"; \
		echo "$(YELLOW)Run: cd aria_nbv && uv sync --all-extras$(NC)"; \
		exit 1; \
	fi
	@echo "$(GREEN)Using python: $(PYTHON_INTERPRETER)$(NC)"

context-package: _check_python ## 🗺️ Summarize symbols per module (classes/functions/constants)
	@$(PYTHON_INTERPRETER) aria_nbv/scripts/get_context.py packages --root aria_nbv/aria_nbv

context-index: ## 🗺️ Regenerate docs/_generated/context/source_index.md
	@./scripts/nbv_context_index.sh "$(CONTEXT_INDEX_OUT)"

context-get: _check_python ## 🗺️ Run AST context helper (GET_CONTEXT_MODE, optional GET_CONTEXT_QUERY / GET_CONTEXT_ROOT)
	@bash -lc 'set -euo pipefail; \
		args=("$(GET_CONTEXT_MODE)"); \
		if [[ -n "$(strip $(GET_CONTEXT_QUERY))" ]]; then \
			args+=("$(GET_CONTEXT_QUERY)"); \
		fi; \
		if [[ -n "$(strip $(GET_CONTEXT_ROOT))" ]]; then \
			args+=("$(GET_CONTEXT_ROOT)"); \
		fi; \
		./scripts/nbv_get_context.sh "$${args[@]}"'

context-contracts: _check_python ## 🗺️ Show data/config contract index for aria_nbv
	@./scripts/nbv_get_context.sh contracts

context-modules: _check_python ## 🗺️ Show aria_nbv module map
	@./scripts/nbv_get_context.sh modules

context-classes: _check_python ## 🗺️ Show class summaries for aria_nbv
	@./scripts/nbv_get_context.sh classes

context-functions: _check_python ## 🗺️ Show public function summaries for aria_nbv
	@./scripts/nbv_get_context.sh functions

context-match: _check_python ## 🗺️ Search AST summaries (set GET_CONTEXT_QUERY=<term>)
	@if [ -z "$(strip $(GET_CONTEXT_QUERY))" ]; then \
		echo "$(RED)GET_CONTEXT_QUERY is required, e.g. make context-match GET_CONTEXT_QUERY=VinPrediction$(NC)"; \
		exit 2; \
	fi
	@./scripts/nbv_get_context.sh match "$(GET_CONTEXT_QUERY)"

context-qmd-outline: _check_python ## 🗺️ Outline Quarto pages (QMD_OUTLINE_ARGS='--compact' by default)
	@./scripts/nbv_qmd_outline.sh $(QMD_OUTLINE_ARGS)

context-typst-outline: _check_python ## 🗺️ Outline Typst paper/slides (TYPST_OUTLINE_ARGS='--paper --mode outline')
	@$(PYTHON_INTERPRETER) ./scripts/nbv_typst_includes.py $(TYPST_OUTLINE_ARGS)

context-typst-includes: _check_python ## 🗺️ Print Typst include edges (TYPST_INCLUDES_ARGS='--paper --mode includes')
	@$(PYTHON_INTERPRETER) ./scripts/nbv_typst_includes.py $(TYPST_INCLUDES_ARGS)

context-literature-index: ## 🗺️ Regenerate docs/_generated/context/literature_index.md
	@./scripts/nbv_literature_index.sh "$(LITERATURE_INDEX_OUT)"

context-literature-search: ## 🗺️ Search literature sources (set LITERATURE_SEARCH_QUERY=<term>)
	@if [ -z "$(strip $(LITERATURE_SEARCH_QUERY))" ]; then \
		echo "$(RED)LITERATURE_SEARCH_QUERY is required, e.g. make context-literature-search LITERATURE_SEARCH_QUERY=GenNBV$(NC)"; \
		exit 2; \
	fi
	@./scripts/nbv_literature_search.sh "$(LITERATURE_SEARCH_QUERY)"

migrate-codex-memory: _check_python ## 🗺️ Migrate legacy .codex notes into .agents/memory
	@$(PYTHON_INTERPRETER) scripts/migrate_codex_memory.py $(MIGRATE_CODEX_MEMORY_ARGS)

codex-transcripts: _check_python ## 🧠 Write ARIA-NBV Codex transcript memory and chat artifacts (set CODEX_TRANSCRIPT_ARGS='--dry-run')
	@$(PYTHON_INTERPRETER) scripts/codex_transcript_extract.py $(CODEX_TRANSCRIPT_ARGS)

scaffold-audit: _check_python ## 🧭 Validate agent skill metadata, handoffs, and routing fixtures
	@$(PYTHON_INTERPRETER) scripts/scaffold_audit.py

scaffold-audit-self-test: _check_python ## 🧭 Run negative probes for scaffold-audit invariants
	@$(PYTHON_INTERPRETER) scripts/scaffold_audit.py --self-test
	@$(PYTHON_INTERPRETER) scripts/tests/test_agent_governance_g002.py

scaffold-check: agents-db-validate check-agent-memory scaffold-audit scaffold-audit-self-test graphify-usable-check ## 🧭 Validate the scaffold with a usable shared Graphify baseline

graphify-skill-upstream-self-test: _check_python ## 🕸️ Verify the project Graphify skill is byte-identical to upstream
	@$(PYTHON_INTERPRETER) scripts/tests/test_graphify_upstream_skill.py

graphify-projection-self-test: _check_python ## 🕸️ Verify the deterministic literature projection builder
	@$(PYTHON_INTERPRETER) scripts/tests/test_build_graphify_projection.py

graphify-projection-live-check: _check_python ## 🕸️ Validate the projection against live owners at exact HEAD
	@$(GIT_CLEAN_ENV) $(PYTHON_INTERPRETER) scripts/build_graphify_projection.py \
		--check --aria-code-ref "$$($(GIT_CLEAN_ENV) git rev-parse HEAD)"

graphify-refresh: _check_python ## 🕸️ Refresh code topology; fail when semantic owners need a full Graphify run
	@command -v graphify >/dev/null 2>&1 || { echo "graphify is required: uv tool install graphifyy" >&2; exit 1; }
	@test -f graphify-out/graph.json || { echo "build the initial graph with the upstream \$$graphify skill" >&2; exit 1; }
	@graph_ref="$$($(PYTHON_INTERPRETER) -c 'import json; print(json.load(open("graphify-out/graph.json"))["built_at_commit"])')"; \
		$(PYTHON_INTERPRETER) scripts/build_graphify_projection.py --output graphify-input --aria-code-ref "$$graph_ref"
	@graphify update .
	@graphify export html
	@$(PYTHON_INTERPRETER) scripts/check_graphify_freshness.py

graphify-optional-check: _check_python ## 🕸️ Validate Graphify when a local snapshot exists
	@$(PYTHON_INTERPRETER) scripts/check_graphify_freshness.py --usable --optional

graphify-usable-check: _check_python ## 🕸️ Require a valid Graphify snapshot for default agent navigation
	@$(PYTHON_INTERPRETER) scripts/check_graphify_freshness.py --usable

graphify-state-check: _check_python ## 🕸️ Require indexed Graphify bytes to match the current worktree
	@$(PYTHON_INTERPRETER) scripts/check_graphify_freshness.py

graphify-publish-check: _check_python ## 🕸️ Require a fresh, committed canonical Graphify snapshot
	@test -f graphify-out/graph.json || { echo "missing committed Graphify snapshot" >&2; exit 1; }
	@git ls-files --error-unmatch graphify-out/graph.json graphify-out/GRAPH_REPORT.md graphify-out/manifest.json graphify-out/graph.html >/dev/null
	@graph_ref="$$($(PYTHON_INTERPRETER) -c 'import json; print(json.load(open("graphify-out/graph.json"))["built_at_commit"])')"; \
		$(PYTHON_INTERPRETER) scripts/build_graphify_projection.py --output graphify-input --aria-code-ref "$$graph_ref"
	@$(PYTHON_INTERPRETER) scripts/check_graphify_freshness.py
	@git diff --exit-code HEAD -- graphify-out/graph.json graphify-out/GRAPH_REPORT.md graphify-out/manifest.json graphify-out/graph.html

ci-impact-self-test: ## 🧭 Verify path-to-CI-family routing and fail-closed behavior
	@$(PYTHON_INTERPRETER) scripts/tests/test_ci_impact.py

api-docs-self-test: ## 📚 Exercise Quartodoc stale-alias recovery with a fake builder
	@./scripts/tests/test_quarto_generate_api_docs.sh

check-agent-memory: _check_python ## 🗺️ Validate agent memory scaffolding and debrief hygiene
	@$(PYTHON_INTERPRETER) scripts/validate_agent_memory.py

new-debrief: _check_python ## 🗺️ Scaffold a dated debrief under .agents/memory/history/ (set TITLE='...')
	@if [ -z "$(TITLE)" ]; then echo "usage: make new-debrief TITLE='short title'" >&2; exit 2; fi
	@$(PYTHON_INTERPRETER) scripts/new_debrief.py "$(TITLE)"

install-git-hooks: ## 🪝 Symlink normal scripts/git_hooks/* into .git/hooks/
	@HOOK_DIR="$$(git rev-parse --git-path hooks 2>/dev/null)"; \
	if [ -z "$$HOOK_DIR" ]; then \
		echo "$(RED)not inside a git tree$(NC)" >&2; exit 1; \
	fi; \
	mkdir -p "$$HOOK_DIR"; \
	for hook in scripts/git_hooks/*; do \
		[ -f "$$hook" ] || continue; \
		name=$$(basename "$$hook"); \
		target="$$HOOK_DIR/$$name"; \
		ln -sf "$(CURDIR)/$$hook" "$$target" && \
			echo "$(GREEN)linked $$target -> $(CURDIR)/$$hook$(NC)"; \
	done

install-hooks: install-git-hooks ## 🪝 Activate normal Codex, Gemini, and git hooks
	@if [ ! -f .codex/hooks.json ]; then \
		cp .codex/hooks.example.json .codex/hooks.json && \
			echo "$(GREEN)copied .codex/hooks.example.json -> .codex/hooks.json$(NC)"; \
	else \
		echo "$(YELLOW).codex/hooks.json already present; leaving as-is$(NC)"; \
	fi
	@echo "$(GREEN)Gemini hooks: .gemini/settings.json (tracked, auto-loaded)$(NC)"

agents-db: _check_python ## 🧠 Inspect or maintain .agents/issues,todos,refactors,resolved (set AGENTS_ARGS='validate')
	@$(PYTHON_INTERPRETER) scripts/agents_db.py $(AGENTS_ARGS)

glossary: _check_python ## 📖 Build shared Quarto/Typst/KG glossary artifacts
	@$(PYTHON_INTERPRETER) scripts/glossary_build.py all

qmd-frontmatter-check: _check_python ## 📖 Validate taxonomy frontmatter for rendered Quarto content
	@$(PYTHON_INTERPRETER) scripts/validate_qmd_frontmatter.py docs/contents

agents-db-validate: _check_python ## Validate the agents DB schema
	@$(PYTHON_INTERPRETER) scripts/agents_db.py validate

#  ══════════════════════════════════════════════════════════════════════
#  Offline / rollout inspection
#  ══════════════════════════════════════════════════════════════════════

offline-info: _check_python ## 🔍 Summarize a VIN offline store
	@cd $(PKG_DIR) && uv run nbv-offline-info summary --store "$(OFFLINE_STORE)" --max-samples "$(OFFLINE_MAX_SAMPLES)"

offline-tree: _check_python ## 🔍 Show VIN offline store manifest tree
	@cd $(PKG_DIR) && uv run nbv-offline-info tree --store "$(OFFLINE_STORE)"

offline-samples: _check_python ## 🔍 Sample rows from a VIN offline store split
	@cd $(PKG_DIR) && uv run nbv-offline-info samples --store "$(OFFLINE_STORE)" --split "$(OFFLINE_SPLIT)" --limit "$(OFFLINE_SAMPLE_LIMIT)"

offline-random-index: _check_python ## 🔍 Print a deterministic random split-local VIN sample index
	@cd $(PKG_DIR) && bash -lc 'set -euo pipefail; \
		seed_args=(); \
		if [[ -n "$(strip $(OFFLINE_SEED))" ]]; then seed_args+=(--seed "$(OFFLINE_SEED)"); fi; \
		uv run nbv-offline-info random-index --store "$(OFFLINE_STORE)" --split "$(OFFLINE_SPLIT)" "$${seed_args[@]}"'

offline-rerun-random: rollouts-rerun-random ## 🔍 Inspect a random rollout row in Rerun

offline-sample-rerun-random: _check_python ## 🔍 Inspect a random VIN offline sample in Rerun
	@cd $(PKG_DIR) && bash -lc 'set -euo pipefail; \
		seed_args=(); \
		if [[ -n "$(strip $(OFFLINE_SEED))" ]]; then seed_args+=(--seed "$(OFFLINE_SEED)"); fi; \
		idx="$$(uv run nbv-offline-info random-index --store "$(OFFLINE_STORE)" --split "$(OFFLINE_SPLIT)" "$${seed_args[@]}")"; \
		offline_store="$(OFFLINE_STORE)"; \
		if [[ "$$offline_store" != /* && "$$offline_store" != */* ]]; then offline_store="../.data/offline_cache/$$offline_store"; \
		elif [[ "$$offline_store" != /* ]]; then offline_store="../$$offline_store"; fi; \
		offline_store="$$(realpath -m "$$offline_store")"; \
		echo "Inspecting offline split=$(OFFLINE_SPLIT) index=$$idx store=$$offline_store"; \
		if [[ "$(RERUN_MODE)" == "view" ]]; then \
			uv run nbv-rerun-inspect --config-path "$(RERUN_CONFIG)" --offline-store "$$offline_store" --split "$(OFFLINE_SPLIT)" --index "$$idx" --view; \
		elif [[ "$(RERUN_MODE)" == "save" ]]; then \
			mkdir -p "$$(dirname "$(RERUN_SAVE)")"; \
			uv run nbv-rerun-inspect --config-path "$(RERUN_CONFIG)" --offline-store "$$offline_store" --split "$(OFFLINE_SPLIT)" --index "$$idx" --save "$(RERUN_SAVE)"; \
		else \
			echo "RERUN_MODE must be view or save, got $(RERUN_MODE)" >&2; exit 2; \
		fi'

rollouts-info: _check_python ## 🔍 Summarize a rollout Zarr store
	@cd $(PKG_DIR) && uv run nbv-rollouts-info --store "$(ROLLOUT_STORE)"

rollouts-stats: _check_python ## 🔍 Summarize rollout-store validity, policy, and selected-path stats
	@cd $(PKG_DIR) && uv run nbv-rollouts-info --store "$(ROLLOUT_STORE)" --stats

rollouts-random-index: _check_python ## 🔍 Print a deterministic random rollout row index
	@cd $(PKG_DIR) && bash -lc 'set -euo pipefail; \
		seed_args=(); \
		if [[ -n "$(strip $(ROLLOUT_SEED))" ]]; then seed_args+=(--seed "$(ROLLOUT_SEED)"); fi; \
		uv run nbv-rollouts-info --store "$(ROLLOUT_STORE)" --random-index --min-horizon "$(ROLLOUT_MIN_HORIZON)" "$${seed_args[@]}"'

rollouts-rerun-random: _check_python ## 🔍 Inspect a random multi-step rollout row in Rerun
	@cd $(PKG_DIR) && bash -lc 'set -euo pipefail; \
		seed_args=(); \
		if [[ -n "$(strip $(ROLLOUT_SEED))" ]]; then seed_args+=(--seed "$(ROLLOUT_SEED)"); fi; \
		idx="$$(uv run nbv-rollouts-info --store "$(ROLLOUT_STORE)" --random-index --min-horizon "$(ROLLOUT_MIN_HORIZON)" "$${seed_args[@]}")"; \
		rollout_store="$(ROLLOUT_STORE)"; \
		if [[ "$$rollout_store" != /* && "$$rollout_store" != */* ]]; then rollout_store="../.data/offline_cache/$$rollout_store"; \
		elif [[ "$$rollout_store" != /* ]]; then rollout_store="../$$rollout_store"; fi; \
		rollout_store="$$(realpath -m "$$rollout_store")"; \
		echo "Inspecting rollout index=$$idx store=$$rollout_store"; \
		if [[ "$(RERUN_MODE)" == "view" ]]; then \
			uv run nbv-rerun-inspect --config-path "$(RERUN_CONFIG)" --rollout-store "$$rollout_store" --rollout-index "$$idx" --rollout-context auto --view; \
		elif [[ "$(RERUN_MODE)" == "save" ]]; then \
			mkdir -p "$$(dirname "$(ROLLOUT_RERUN_SAVE)")"; \
			uv run nbv-rerun-inspect --config-path "$(RERUN_CONFIG)" --rollout-store "$$rollout_store" --rollout-index "$$idx" --rollout-context auto --save "$(ROLLOUT_RERUN_SAVE)"; \
		else \
			echo "RERUN_MODE must be view or save, got $(RERUN_MODE)" >&2; exit 2; \
		fi'

#  ═══════════════════════════════════════════════════════════════════════
#  🔧 LRZ AI Systems operator helpers
#  ═══════════════════════════════════════════════════════════════════════

lrz-probe: ## 🔧 Inspect LRZ login/allocation, DSS containers, partitions, jobs, and GPU visibility
	@$(LRZ_SCRIPTS_DIR)/lrz-probe.sh

lrz-resources: ## 🔧 One-shot Slurm resource query (LRZ_RESOURCES_ARGS='summary' or 'partition lrz-v100x2')
	@$(LRZ_SCRIPTS_DIR)/lrz-resources.sh $(LRZ_RESOURCES_ARGS)

lrz-resources-gpu: ## 🔧 One-shot LRZ GPU partition summary
	@$(LRZ_SCRIPTS_DIR)/lrz-resources.sh gpu

lrz-resources-cpu: ## 🔧 One-shot LRZ CPU partition summary
	@$(LRZ_SCRIPTS_DIR)/lrz-resources.sh cpu

lrz-jobs: ## 🔧 Show current user's LRZ Slurm jobs once
	@$(LRZ_SCRIPTS_DIR)/lrz-resources.sh mine

lrz-dss-init: ## 🔧 Initialize ARIA DSS layout (requires ARIA_DSS=/dss/.../aria-nbv)
	@if [ -z "$(strip $(ARIA_DSS))" ]; then \
		echo "$(RED)ARIA_DSS is required, e.g. make lrz-dss-init ARIA_DSS=/dss/.../aria-nbv$(NC)"; \
		exit 2; \
	fi
	@$(LRZ_SCRIPTS_DIR)/lrz-dss-init.sh "$(ARIA_DSS)"

lrz-container-shell: ## 🔧 Launch Pyxis container shell inside an LRZ Slurm allocation (requires ARIA_DSS)
	@if [ -z "$(strip $(ARIA_DSS))" ]; then \
		echo "$(RED)ARIA_DSS is required, e.g. make lrz-container-shell ARIA_DSS=/dss/.../aria-nbv$(NC)"; \
		exit 2; \
	fi
	@ARIA_DSS="$(ARIA_DSS)" ARIA_REPO="$(ARIA_REPO)" LRZ_CONTAINER_IMAGE="$(LRZ_CONTAINER_IMAGE)" \
		$(LRZ_SCRIPTS_DIR)/lrz-container-shell.sh

lrz-sbatch-cpu: ## 🔧 Submit LRZ CPU batch job (requires ARIA_DSS and LRZ_CMD)
	@if [ -z "$(strip $(ARIA_DSS))" ]; then \
		echo "$(RED)ARIA_DSS is required, e.g. make lrz-sbatch-cpu ARIA_DSS=/dss/.../aria-nbv LRZ_CMD='uv run pytest ...'$(NC)"; \
		exit 2; \
	fi
	@if [ -z '$(strip $(LRZ_CMD))' ]; then \
		echo "$(RED)LRZ_CMD is required, e.g. make lrz-sbatch-cpu ARIA_DSS=/dss/.../aria-nbv LRZ_CMD='uv run pytest ...'$(NC)"; \
		exit 2; \
	fi
	@ARIA_DSS="$(ARIA_DSS)" ARIA_REPO="$(ARIA_REPO)" LRZ_TIME="$(LRZ_TIME)" LRZ_CPUS="$(LRZ_CPUS)" LRZ_MEM="$(LRZ_MEM)" \
		$(LRZ_SCRIPTS_DIR)/lrz-sbatch-cpu.sh '$(LRZ_CMD)'

lrz-sbatch-single-gpu: ## 🔧 Submit LRZ single-GPU batch job (requires ARIA_DSS and LRZ_CMD)
	@if [ -z "$(strip $(ARIA_DSS))" ]; then \
		echo "$(RED)ARIA_DSS is required, e.g. make lrz-sbatch-single-gpu ARIA_DSS=/dss/.../aria-nbv LRZ_CMD='uv run python -c \"print(1)\"'$(NC)"; \
		exit 2; \
	fi
	@if [ -z '$(strip $(LRZ_CMD))' ]; then \
		echo "$(RED)LRZ_CMD is required, e.g. make lrz-sbatch-single-gpu ARIA_DSS=/dss/.../aria-nbv LRZ_CMD='uv run python -c \"print(1)\"'$(NC)"; \
		exit 2; \
	fi
	@ARIA_DSS="$(ARIA_DSS)" ARIA_REPO="$(ARIA_REPO)" LRZ_PARTITION="$(LRZ_PARTITION)" LRZ_GPUS="$(LRZ_GPUS)" LRZ_TIME="$(LRZ_TIME)" LRZ_CPUS="$(LRZ_CPUS)" LRZ_MEM="$(LRZ_MEM)" LRZ_CONTAINER_IMAGE="$(LRZ_CONTAINER_IMAGE)" \
		$(LRZ_SCRIPTS_DIR)/lrz-sbatch-single-gpu.sh '$(LRZ_CMD)'

lrz-sbatch-multigpu: ## 🔧 Submit LRZ multi-GPU torchrun batch job (requires ARIA_DSS and LRZ_CMD)
	@if [ -z "$(strip $(ARIA_DSS))" ]; then \
		echo "$(RED)ARIA_DSS is required, e.g. make lrz-sbatch-multigpu ARIA_DSS=/dss/.../aria-nbv LRZ_GPUS=2 LRZ_CMD='<TRAIN_MODULE_OR_SCRIPT> <ARGS>'$(NC)"; \
		exit 2; \
	fi
	@if [ -z '$(strip $(LRZ_CMD))' ]; then \
		echo "$(RED)LRZ_CMD is required, e.g. make lrz-sbatch-multigpu ARIA_DSS=/dss/.../aria-nbv LRZ_GPUS=2 LRZ_CMD='<TRAIN_MODULE_OR_SCRIPT> <ARGS>'$(NC)"; \
		exit 2; \
	fi
	@ARIA_DSS="$(ARIA_DSS)" ARIA_REPO="$(ARIA_REPO)" LRZ_PARTITION="$(LRZ_PARTITION)" LRZ_GPUS="$(LRZ_GPUS)" LRZ_NODES="$(LRZ_NODES)" LRZ_TIME="$(LRZ_TIME)" LRZ_CPUS="$(LRZ_CPUS)" LRZ_MEM="$(LRZ_MEM)" LRZ_CONTAINER_IMAGE="$(LRZ_CONTAINER_IMAGE)" \
		$(LRZ_SCRIPTS_DIR)/lrz-sbatch-multigpu.sh '$(LRZ_CMD)'

context: _check_python ## 🗺️ Refresh lightweight context artifacts (source index, literature index, data contracts)
	@bash -lc 'set -euo pipefail; \
		context_dir="$(CONTEXT_DIR)"; \
		index_out="$(CONTEXT_INDEX_OUT)"; \
		contracts_out="$(CONTEXT_CONTRACTS_OUT)"; \
		lit_index_out="$(LITERATURE_INDEX_OUT)"; \
		mkdir -p "$$context_dir"; \
		mkdir -p "$$(dirname "$$index_out")"; \
		scripts/nbv_context_index.sh "$$index_out" >/dev/null; \
		scripts/nbv_literature_index.sh "$$lit_index_out" >/dev/null; \
		{ \
			echo "# Data Contracts (aria_nbv)"; \
			echo ""; \
			$(PYTHON_INTERPRETER) aria_nbv/scripts/get_context.py contracts --root aria_nbv/aria_nbv \
				| sed "1{/^# Data Contracts$$/d;}"; \
		} > "$$contracts_out"; \
		echo "Wrote: $$index_out"; \
		echo "Wrote: $$lit_index_out"; \
		echo "Wrote: $$contracts_out"'
	@echo "$(GREEN)Refreshed lightweight context artifacts in $(CONTEXT_DIR)$(NC)"
	@echo "$(BLUE)Heavy fallback: make context-heavy$(NC)"
	@echo "$(BLUE)Tip: rg -n \"<pattern>\" $(CONTEXT_INDEX_OUT)$(NC)"

context-uml: _check_python ## 🗺️ Generate aria_nbv UML artifacts without printing them
	@bash -lc 'set -euo pipefail; \
		context_dir="$(CONTEXT_DIR)"; \
		uml_out="$(CONTEXT_UML_OUT)"; \
		uml_filtered_out="$(CONTEXT_UML_FILTERED_OUT)"; \
		mkdir -p "$$context_dir"; \
		mermaid_tmp="$$(mktemp)"; \
		mermaid_filtered="$$(mktemp)"; \
		$(PYTHON_INTERPRETER) -m syrenka classdiagram aria_nbv/aria_nbv > "$$mermaid_tmp"; \
		exclude_list="$(CONTEXT_MERMAID_EXCLUDE)"; \
		if [[ -z "$$exclude_list" ]]; then \
			cp "$$mermaid_tmp" "$$mermaid_filtered"; \
		else \
			$(PYTHON_INTERPRETER) scripts/filter_mermaid.py \
				--input "$$mermaid_tmp" \
				--output "$$mermaid_filtered" \
				--exclude "$$exclude_list"; \
		fi; \
		cp "$$mermaid_tmp" "$$uml_out"; \
		cp "$$mermaid_filtered" "$$uml_filtered_out"; \
		rm -f "$$mermaid_tmp" "$$mermaid_filtered"; \
		echo "Wrote: $$uml_out"; \
		echo "Wrote: $$uml_filtered_out"'

context-uml-preview: _check_python ## 🗺️ Print the filtered aria_nbv UML to stdout
	@$(MAKE) --no-print-directory context-uml >/dev/null
	@echo "# Mermaid UML Diagram of the aria_nbv:"
	@echo "\`\`\`{mermaid}"
	@cat "$(CONTEXT_UML_FILTERED_OUT)"
	@echo "\`\`\`"

context-docstrings: _check_python ## 🗺️ Generate full aria_nbv class docstrings artifact
	@bash -lc 'set -euo pipefail; \
		context_dir="$(CONTEXT_DIR)"; \
		docstrings_out="$(CONTEXT_DOCSTRINGS_OUT)"; \
		mkdir -p "$$context_dir"; \
		{ \
			echo "# Class Docstrings (aria_nbv)"; \
			echo ""; \
			$(PYTHON_INTERPRETER) aria_nbv/scripts/get_context.py classes --root aria_nbv/aria_nbv --full-doc; \
		} > "$$docstrings_out"; \
		echo "Wrote: $$docstrings_out"'

context-tree: _check_python ## 🗺️ Generate aria_nbv directory tree artifact
	@bash -lc 'set -euo pipefail; \
		context_dir="$(CONTEXT_DIR)"; \
		tree_out="$(CONTEXT_TREE_OUT)"; \
		mkdir -p "$$context_dir"; \
		{ \
			echo "# Directory Tree (aria_nbv)"; \
			echo ""; \
			echo "Directory tree for aria_nbv/aria_nbv/:"; \
			if command -v tree >/dev/null 2>&1; then \
				tree aria_nbv/aria_nbv/ -I "__pycache__"; \
			else \
				find aria_nbv/aria_nbv/ -path "*/__pycache__" -prune -o -print \
					| sed "s#^aria_nbv/aria_nbv/##" \
					| sed "/^$$/d" \
					| sort; \
			fi; \
		} > "$$tree_out"; \
		echo "Wrote: $$tree_out"'

context-heavy: _check_python ## 🗺️ Generate heavyweight fallback artifacts and combined context snapshot
	@$(MAKE) --no-print-directory context
	@$(MAKE) --no-print-directory context-uml
	@$(MAKE) --no-print-directory context-docstrings
	@$(MAKE) --no-print-directory context-tree
	@bash -lc 'set -euo pipefail; \
		out="$(CONTEXT_OUT)"; \
		index_out="$(CONTEXT_INDEX_OUT)"; \
		uml_out="$(CONTEXT_UML_OUT)"; \
		docstrings_out="$(CONTEXT_DOCSTRINGS_OUT)"; \
		contracts_out="$(CONTEXT_CONTRACTS_OUT)"; \
		tree_out="$(CONTEXT_TREE_OUT)"; \
		mkdir -p "$$(dirname "$$out")"; \
		{ \
			echo "# Context Snapshot (make context-heavy)"; \
			echo ""; \
			echo "Generated: $$(date -u +\"%Y-%m-%dT%H:%M:%SZ\")"; \
			echo ""; \
			echo "## Contents"; \
			echo "0) Source index (all context pools)"; \
			echo "1) Environment"; \
			echo "2) Data contracts (aria_nbv)"; \
			echo "3) Mermaid UML (aria_nbv)"; \
			echo "4) Class docstrings (aria_nbv)"; \
			echo "5) Directory tree (aria_nbv)"; \
			echo ""; \
			echo "## 0) Source index (all context pools)"; \
			if [[ -f "$$index_out" ]]; then \
				sed "s/^#/###/" "$$index_out"; \
			else \
				echo "(missing $$index_out)"; \
			fi; \
			echo ""; \
			echo "## 1) Environment"; \
			echo "Python: $(PYTHON_INTERPRETER)"; \
			echo "Venv: $(VENV_PYTHON)"; \
			echo "Recreate: UV_PYTHON=/home/jandu/miniforge3/envs/aria-nbv/bin/python uv sync --extra dev --extra notebook --extra pytorch3d"; \
			echo ""; \
			echo "## 2) Data contracts (aria_nbv)"; \
			if [[ -f "$$contracts_out" ]]; then \
				sed "1{/^# Data Contracts (aria_nbv)$$/d;}" "$$contracts_out"; \
			else \
				echo "(missing $$contracts_out)"; \
			fi; \
			echo ""; \
			echo "## 3) Mermaid UML (aria_nbv)"; \
			echo "\`\`\`{mermaid}"; \
			cat "$$uml_out"; \
			echo "\`\`\`"; \
			echo ""; \
			echo "## 4) Class docstrings (aria_nbv)"; \
			if [[ -f "$$docstrings_out" ]]; then \
				sed "1{/^# Class Docstrings (aria_nbv)$$/d;}" "$$docstrings_out"; \
			else \
				echo "(missing $$docstrings_out)"; \
			fi; \
			echo ""; \
			echo "## 5) Directory tree (aria_nbv)"; \
			if [[ -f "$$tree_out" ]]; then \
				sed "1{/^# Directory Tree (aria_nbv)$$/d;}" "$$tree_out"; \
			else \
				echo "(missing $$tree_out)"; \
			fi; \
		} > "$$out"; \
		echo "Wrote: $$out"'
	@echo "$(GREEN)Wrote heavyweight context snapshot to $(CONTEXT_OUT)$(NC)"

context-external: _check_python ## 🗺️ List classes with full docstrings
	@echo "# Mermaid UML Diagram of the external/efm3d:\n\`\`\`{mermaid}"
	@$(PYTHON_INTERPRETER) -m syrenka classdiagram external/efm3d/efm3d
	@echo "\`\`\`\n---\n"
	@$(PYTHON_INTERPRETER) aria_nbv/scripts/get_context.py classes --root external/efm3d/efm3d --full-doc

	@echo "\n\n"

	echo "# Mermaid UML Diagram of the external/ATEK:\n\`\`\`{mermaid}"
	@$(PYTHON_INTERPRETER) -m syrenka classdiagram external/ATEK/atek
	echo "\`\`\`\n---\n"
	@$(PYTHON_INTERPRETER) aria_nbv/scripts/get_context.py classes --root external/ATEK/atek --full-doc

context-dir-tree: _check_python ## 🗺️ Print directory tree for `aria_nbv/aria_nbv/` (ignore __pycache__)
	@$(MAKE) --no-print-directory _context_dir_tree_print

_context_dir_tree_print:
	@echo "Directory tree for aria_nbv/aria_nbv/:"
	@bash -lc 'tree aria_nbv/aria_nbv/ -I "__pycache__"'

context-dir-tree-external: _check_python ## 🗺️ Print directory tree for `external/efm3d/efm3d` (ignore __pycache__)
	@echo "Directory tree for external/efm3d/efm3d/:"
	@bash -lc 'tree external/efm3d/efm3d/ -I "__pycache__"'
	@echo "\n\n"

	@echo "Directory tree for external/ATEK/atek/:"
	@bash -lc 'tree external/ATEK/atek/ -I "__pycache__"'

context-qmd-tree: ## 🗺️ Print docs/ .qmd structure (ignore __pycache__)
	@echo "Directory tree for docs (.qmd only):"
	@bash -lc 'tree docs -P "*.qmd" -I "__pycache__"'

#  ═══════════════════════════════════════════════════════════════════════
#  📊 Diagrams
#  ═══════════════════════════════════════════════════════════════════════

.PHONY: vin-v2-arch
VIN_V2_ARCH_ARGS ?=
vin-v2-arch: _check_python ## 📊 Generate VIN v2 architecture DOT/SVG/PNG (+ VDX via --drawio)
	@$(PYTHON_INTERPRETER) aria_nbv/scripts/generate_vin_v2_arch.py $(VIN_V2_ARCH_ARGS)

.PHONY: mmdc-render
mmdc-render: ## 📊 Render all .mmd files in a folder (MMD_DIR=..., MMD_OUT=..., MMD_FORMAT=png|svg, MMD_SCALE=4)
	@bash -lc 'set -euo pipefail; \
		in_dir="$(MMD_DIR)"; \
		out_dir="$(MMD_OUT)"; \
		fmt="$(MMD_FORMAT)"; \
		scale="$(MMD_SCALE)"; \
		render="$(MERMAID_RENDER)"; \
		mkdir -p "$$out_dir"; \
		for f in "$$in_dir"/*.mmd; do \
			[ -e "$$f" ] || continue; \
			base="$$(basename "$$f" .mmd)"; \
			out="$$out_dir/$$base.$$fmt"; \
			if [[ "$$fmt" == "svg" ]]; then \
				"$$render" "$$f" "$$out"; \
			else \
				"$$render" "$$f" "$$out" --scale "$$scale"; \
			fi; \
		done'

mermaid-lint: _check_python ## 📊 Lint tracked Mermaid .mmd files (MERMAID_LINT_FILES='a.mmd b.mmd')
	@if [ -z "$(strip $(MERMAID_LINT_FILES))" ]; then \
		echo "$(YELLOW)No Mermaid files to lint$(NC)"; \
	else \
		$(PYTHON_INTERPRETER) $(MERMAID_LINT) $(MERMAID_LINT_FILES); \
	fi

#  ═══════════════════════════════════════════════════════════════════════
#  📚 Documentation hygiene
#  ═══════════════════════════════════════════════════════════════════════

.PHONY: api-docs api-docs-filter api-docs-watch api-docs-refresh docs-lint
api-docs: ## Generate API reference pages via Quartodoc (hard alias failures fail, warnings are non-blocking)
	@./scripts/quarto_generate_api_docs.sh

api-docs-filter: ## Incrementally generate API reference pages matching API_FILTER='data_handling*'
	@if [ -z "$(strip $(API_FILTER))" ]; then \
		echo "Set API_FILTER, for example: make api-docs-filter API_FILTER='data_handling*'"; \
		exit 2; \
	fi
	@QUARTODOC_FILTER="$(API_FILTER)" QUARTODOC_INCREMENTAL=1 ./scripts/quarto_generate_api_docs.sh

api-docs-watch: ## Watch and incrementally regenerate API reference pages matching API_FILTER='data_handling*'
	@if [ -z "$(strip $(API_FILTER))" ]; then \
		echo "Set API_FILTER, for example: make api-docs-watch API_FILTER='data_handling*'"; \
		exit 2; \
	fi
	@QUARTODOC_FILTER="$(API_FILTER)" QUARTODOC_INCREMENTAL=1 QUARTODOC_WATCH=1 ./scripts/quarto_generate_api_docs.sh

api-docs-refresh: ## Incrementally regenerate API docs and render API_PAGES with --no-clean --no-execute
	@API_FILTER="$(API_FILTER)" API_PAGES="$(API_PAGES)" ./scripts/quarto_refresh_api_docs.sh

.PHONY: docs-lint
docs-lint: _check_python ## Format QMD lists, then run Quarto checks
	@echo "$(BLUE)Formatting QMD list spacing…$(NC)"
	@$(PYTHON_INTERPRETER) $(QMD_FORMATTER) $(DOCS_DIR)
	@echo "$(BLUE)Running Quarto check…$(NC)"
	@quarto check

.PHONY: quarto-docs quarto-preview
quarto-docs: ## Render the Quarto website into docs/_site
	@cd docs && quarto render .

quarto-docs-ci: ## Render the Quarto website without executing notebooks
	@quarto render $(DOCS_DIR) --no-execute

quarto-preview: ## Preview the Quarto website locally
	@cd docs && quarto preview

#  ═══════════════════════════════════════════════════════════════════════
#  🧾 Typst builds
#  ═══════════════════════════════════════════════════════════════════════

.PHONY: typst-paper typst-slide thesis-pdf thesis-watch
typst-paper: ## Compile the Typst paper (docs/typst/seminar_paper/main.typ)
	@$(TYPST) compile --root $(TYPST_ROOT) $(TYPST_PAPER) $(TYPST_PAPER_PDF)

typst-paper-ci: ## Compile the Typst paper into an ignored CI artifact path
	@mkdir -p "$(CI_RENDER_DIR)"
	@$(TYPST) compile --root $(TYPST_ROOT) $(TYPST_PAPER) "$(CI_RENDER_DIR)/seminar_paper.pdf"

typst-slide: ## Compile a Typst slide deck (make typst-slide SLIDES=slides_4.typ or SLIDES=docs/typst/thesis_slides/slides_thesis_outlook.typ)
	@$(TYPST) compile --root $(TYPST_ROOT) $(SLIDES_SRC) $(SLIDES_PDF)

thesis-pdf: ## Compile the Typst thesis (docs/typst/thesis/main.typ)
	@$(TYPST) compile --root $(TYPST_ROOT) $(TYPST_THESIS) $(TYPST_THESIS_PDF)

thesis-watch: ## Watch and recompile the Typst thesis
	@$(TYPST) watch --root $(TYPST_ROOT) $(TYPST_THESIS) $(TYPST_THESIS_PDF)

docs-render-core: graphify-projection-self-test graphify-projection-live-check quarto-docs-ci typst-paper-ci ## Render the core docs surfaces used by root CI

qh-ci: ## Run the focused CPU-only Q_H training and distributed contracts
	@cd $(PKG_DIR) && $(QH_CI_PYTHON) -m ruff format --check $(QH_CI_RUFF_PATHS)
	@cd $(PKG_DIR) && $(QH_CI_PYTHON) -m ruff check $(QH_CI_RUFF_PATHS)
	@cd $(PKG_DIR) && $(QH_CI_PYTHON) -m pytest --import-mode=importlib $(PYTEST_ARGS) $(QH_CI_TESTS)

package-smoke: qh-ci ## Run CPU-only package lint and smoke tests for M1 contracts
	@cd $(PKG_DIR) && uv run --extra dev ruff format --check $(PACKAGE_SMOKE_RUFF_PATHS)
	@cd $(PKG_DIR) && uv run --extra dev ruff check $(PACKAGE_SMOKE_RUFF_PATHS)
	@cd $(PKG_DIR) && uv run --extra dev pytest --import-mode=importlib $(PYTEST_ARGS) $(PACKAGE_SMOKE_TESTS)

ci: agents-db-validate qmd-frontmatter-check check-agent-memory graphify-skill-upstream-self-test api-docs-self-test package-smoke docs-render-core ## Run the root CI contract

#  ═══════════════════════════════════════════════════════════════════════
#  ℹ️  Help
#  ═══════════════════════════════════════════════════════════════════════

help: ## Show this help message
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)               NBV Project - Makefile Commands             $(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
		@echo "$(YELLOW)Usage:$(NC) make <target>"
	@awk 'BEGIN {FS = ":.*?## "; section=""} \
		/^#  ═+$$/ {next} \
		/^#  [📦🔍🧪📚🔧🗺️]/ {if (section) print ""; section=$$0; gsub(/^#  /, "", section); print "$(YELLOW)" section "$(NC)"; next} \
		/^[a-zA-Z_-]+:.*?## / {printf "  $(BLUE)%-18s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════════════$(NC)"
	@echo ""
