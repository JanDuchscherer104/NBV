# Research Sandbox

## Inputs

- Local Codex session roots for 2026-08-17 through 2026-08-31.
- `scripts/codex_transcript_extract.py` as the repository-owned extraction and
  conservative lexical-review surface.
- The live `.agents/references/human_owner_intent.md` and its two-week Git
  history.
- Current repository guidance for intent capture and transcript trust.

## Allowed work

- Read local session JSONL.
- Generate temporary extracted JSONL outside the repository.
- Record aggregate counts, content hashes, session identifiers, paraphrased
  evidence, and source locators in the report.
- Edit only the canonical intent owner plus public-safe research/provenance
  artifacts required by the repository workflow.

## Exclusions

- Raw or full transcript publication.
- Promotion based only on assistant repetition, historical memory, or lexical
  classifier labels.
- Task-specific implementation choices, scientific claims, backlog work,
  credentials, private unrelated sessions, or machine-specific instructions.
- Automatic promotion without independent semantic review.
