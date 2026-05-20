# arXiv Source Trees

This directory stores extracted arXiv LaTeX source bundles for papers that directly shape the benchmark design in this repository.

## Included papers

- [EFM3D: A Benchmark for Measuring Progress Towards 3D Egocentric Foundation Models](https://arxiv.org/abs/2406.10224): Establishes a benchmark for 3D Egocentric Foundation Models using Project Aria data; introduces Egocentric Voxel Lifting (EVL) for 3D spatial reasoning. Local source tree: `arXiv-EFM3D/`.
- [GenNBV: Generalizable Next-Best-View Policy for Active 3D Reconstruction](https://arxiv.org/abs/2402.16174): Introduces an end-to-end generalizable Next-Best-View policy using Reinforcement Learning that operates across diverse, unseen geometries. Local source tree: `arXiv-GenNBV/`.
- [Project Aria: A New Tool for Egocentric Multi-Modal AI Research](https://arxiv.org/abs/2308.13561): Describes the Project Aria hardware and tools for multi-modal egocentric AI research. Local source tree: `arXiv-project-aria/`.
- [SceneScript: Reconstructing Scenes With An Autoregressive Structured Language Model](https://arxiv.org/abs/2403.13064): Represents 3D scenes as structured language commands using an autoregressive model; releases the Aria Synthetic Environments (ASE) dataset. Local source tree: `arXiv-scene-script/`.
- [VIN-NBV: A View Introspection Network for Next-Best-View Selection](https://arxiv.org/abs/2505.06219): Optimizes Next-Best-View selection for direct reconstruction quality using Relative Reconstruction Improvement (RRI) predictions. Local source tree: `arXiv-VIN-NBV/`.
- [Informative Object-centric Next Best View for Object-aware 3D Gaussian Splatting in Cluttered Scenes](https://arxiv.org/abs/2602.08266): Target-conditioned Next-Best-View policy focusing on specific object instances and handling occlusions in cluttered scenes. Local source tree: `arXiv-Instance-NBV/`.
- [PB-NBV: Efficient Projection-Based Next-Best-View Planning Framework for Reconstruction of Unknown Objects](https://arxiv.org/abs/2501.10663): Fast projection-based Next-Best-View planning framework that replaces expensive ray-casting with ellipsoid-based evaluation. Local source tree: `arXiv-PB-NBV/`.
- [Next Best View Selections for Semantic and Dynamic 3D Gaussian Splatting](https://arxiv.org/abs/2512.22771): Next-Best-View selection for dynamic and semantic 3D Gaussian Splatting using Fisher Information to quantify view informativeness. Local source tree: `arXiv-Dynamic-3DGS/`.
- [Hestia: Voxel-Face-Aware Hierarchical Next-Best-View Acquisition for Efficient 3D Reconstruction](https://arxiv.org/abs/2508.01014): Hierarchical Next-Best-View system using voxel-face visibility and a "close-greedy" strategy for efficient reconstruction. Local source tree: `arXiv-Hestia/`.
- [Offline Reinforcement Learning as One Big Sequence Modeling Problem](https://arxiv.org/abs/2106.02039): Frames reinforcement learning as a sequence modeling problem, using Transformers and beam search for trajectory planning. Local source tree: `arXiv-Trajectory-Transformer/`.
- [Playing Atari with Deep Reinforcement Learning](https://arxiv.org/abs/1312.5602): Introduces Deep Q-Networks with experience replay and minibatch Q-learning from high-dimensional observations. Local source tree: `arXiv-DQN/`.
- [Deep Reinforcement Learning with Double Q-learning](https://arxiv.org/abs/1509.06461): Mitigates overestimation bias in deep Q-learning by decoupling action selection from evaluation. Local source tree: `arXiv-Double-DQN/`.
- [Offline Reinforcement Learning with Implicit Q-Learning](https://arxiv.org/abs/2110.06169): Enables offline RL without querying out-of-distribution actions by using an expectile-based implicit value function. Local source tree: `arXiv-IQL/`.
- [Conservative Q-Learning for Offline Reinforcement Learning](https://arxiv.org/abs/2006.04779): Regularizes learned Q-functions to reduce overestimation under offline distribution shift. Local source tree: `arXiv-CQL/`.
- [Off-Policy Deep Reinforcement Learning without Exploration](https://arxiv.org/abs/1812.02900): Introduces batch-constrained Q-learning for fixed offline datasets. Local source tree: `arXiv-BCQ/`.
- [Decision Transformer: Reinforcement Learning via Sequence Modeling](https://arxiv.org/abs/2106.01345): Casts offline RL as return-conditioned sequence modeling with a Transformer. Local source tree: `arXiv-Decision-Transformer/`.
- [Reinforcement Learning with Deep Energy-Based Policies](https://arxiv.org/abs/1702.08165): Connects maximum entropy RL with energy-based models to learn expressive, multi-modal policies. Local source tree: `arXiv-Deep-Energy-Based-Policies/`.
- [Stochastic Beams and Where to Find Them: The Gumbel-Top-k Trick for Sampling Sequences Without Replacement](https://arxiv.org/abs/1903.06059): Introduces the Gumbel-Top-k trick for sampling sequences without replacement from autoregressive models. Local source tree: `arXiv-Gumbel-Top-k/`.
- [FisherRF: Active View Selection and Uncertainty Quantification for Radiance Fields using Fisher Information](https://arxiv.org/abs/2311.17874): Scores candidate views by expected Fisher information for radiance-field parameters; useful for ARIA-NBV uncertainty/support diagnostics, not as a replacement for target-RRI. Local source tree: `arXiv-FisherRF/`.
- [Next Best Sense: Guiding Vision and Touch with FisherRF for 3D Gaussian Splatting](https://arxiv.org/abs/2410.04680): Guides multi-modal active sensing (vision and touch) for 3D Gaussian Splatting using Fisher Information (FisherRF). Local source tree: `arXiv-Next-Best-Sense/`.
- [Finding Optimal Viewpoints for Monocular 3D Human Pose Estimation in Dynamic 3D Gaussian Splatting Space](https://doi.org/10.1109/AVSS65446.2025.11149906): Optimal viewpoint selection for monocular 3D human pose estimation in dynamic 3DGS spaces. (Reference only)

## Manifest and refresh workflow

The checked-in manifest for this directory lives at:

- `sources.jsonl`

Each JSONL row describes one paper and the local output names needed to fetch its arXiv e-print source tree and, optionally, its PDF. The current schema is:

- required: `arxiv_id`, `tex_dir`
- optional: `title`, `short_title`, `source_url`, `pdf_url`, `pdf_file`

Run the downloader from the repo root:

```bash
uv run python scripts/download_arxiv_tex_src.py docs/literature/sources.jsonl
uv run python scripts/download_arxiv_tex_src.py docs/literature/sources.jsonl --download-pdfs
```

By default the script writes extracted source trees into `docs/literature/tex-src/` and PDFs into `docs/literature/pdf/`. Use `--overwrite` to replace an existing extracted tree or PDF target.

## Why these sources are kept locally

- to inspect the exact paper contribution statements and method structure
- to recover figure, notation, and pipeline terminology directly from the source
- to anchor our wrapper and stage design to the paper, not only to the GitHub README
- to make future report writing and figure reuse easier

## Most useful files

### EFM3D
- `arXiv-EFM3D/main.tex`
- `arXiv-EFM3D/method.tex`
- `arXiv-EFM3D/dataset.tex`

### GenNBV
- `arXiv-GenNBV/main.tex`
- `arXiv-GenNBV/3-Method.tex`

### Project Aria
- `arXiv-project-aria/main.tex`
- `arXiv-project-aria/device.tex`
- `arXiv-project-aria/mps.tex`

### SceneScript
- `arXiv-scene-script/main.tex`
- `arXiv-scene-script/sections/structured_scene_language.tex`

### VIN-NBV
- `arXiv-VIN-NBV/main.tex`
- `arXiv-VIN-NBV/sec/3_methods.tex`

### Instance-NBV
- `arXiv-Instance-NBV/root.tex`
- `arXiv-Instance-NBV/ver3_rpm/3_method_ver3_rpm.tex`

### PB-NBV
- `arXiv-PB-NBV/jzz_2025_ral_resub.tex`
- `arXiv-PB-NBV/sections/method.tex`

### Dynamic 3DGS NBV
- `arXiv-Dynamic-3DGS/main.tex`
- `arXiv-Dynamic-3DGS/sec/method.tex`

### Hestia
- `arXiv-Hestia/main.tex`
- `arXiv-Hestia/sec/3_method.tex`

### Trajectory Transformer
- `arXiv-Trajectory-Transformer/ms.tex`
- `arXiv-Trajectory-Transformer/text/method.tex`

### DQN
- `arXiv-DQN/deepqnet.tex`
- `arXiv-DQN/intro.tex`
- `arXiv-DQN/background.tex`
- `arXiv-DQN/method.tex`
- `arXiv-DQN/experiments.tex`

### Double DQN
- `arXiv-Double-DQN/DoubleDQN_aaai2016_total.tex`

### IQL
- `arXiv-IQL/iclr2022_conference.tex`

### Deep Energy-Based Policies
- `arXiv-Deep-Energy-Based-Policies/icml2017-no-comments.tex`

### Gumbel-Top-k
- `arXiv-Gumbel-Top-k/main.tex`
- `arXiv-Gumbel-Top-k/full.tex`

### FisherRF
- `arXiv-FisherRF/main.tex`

### Next Best Sense
- `arXiv-Next-Best-Sense/ms.tex`

The repo-level lookup material for these papers lives in:

- `.agents/references/agent_reference.md`
