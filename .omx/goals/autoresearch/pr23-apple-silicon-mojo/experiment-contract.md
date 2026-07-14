# Measured experiment contract

- Device: Apple M5 Max, arm64, macOS 26.4.1.
- Toolchain: Python 3.11, PyTorch 2.4.1, Mojo 1.0.0b2.
- Mutable surface: the fork-owned PyTorch3D Mojo dispatch and kernels only.
- Correctness gates: 20/20 Mojo parity/safety tests and 9/9 relevant upstream CPU cases; direct unsafe binding inputs must be rejected.
- Primary metric: CPU parity (exact indices and contract-specific floating tolerances). A correctness failure rejects the candidate.
- Secondary metrics: median wall runtime and necessary non-test implementation LOC.
- Runtime gate: keep a candidate only when a measured workload improves meaningfully and no representative workload regresses by more than 3%.
- LOC gate: prefer deletion; reject unmeasured complexity. Tests and research artifacts are excluded from implementation LOC.
- Timing protocol: warm up before timing, use interleaved rounds, and repeat in three fresh processes for optimization candidates.
- Inputs: deterministic synthetic tensors with fixed seeds. No synthetic input is represented as official ASE data.

