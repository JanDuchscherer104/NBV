# Ralplan critic review 1

- Reviewer role: critic
- Verdict: REVISE
- Date: 2026-07-13

Required revisions:

1. Replace Mac full-discovery acceptance with explicit CPU/Mojo suites because upstream modules force CUDA.
2. Treat speed ratios as optimization targets; use parity/no-regression plus a bounded plateau to avoid deadlock.
3. Name the exact real-data fixture, checkpoint, acquisition command, and external-block state.

Disposition: all three requirements incorporated into the PRD and test plan before re-review.
