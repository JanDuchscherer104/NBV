# LRZ AI Systems Cheatsheet

Use placeholders in documentation and scripts. Do not commit usernames, project IDs, DSS paths, NGC tokens, or host-local values.

## SSH Setup

```bash
ssh-keygen -t ed25519 -C "<LRZ_USER>@ai" -f ~/.ssh/id_ed25519_lrz_ai
ssh-copy-id -i ~/.ssh/id_ed25519_lrz_ai.pub <LRZ_USER>@login.ai.lrz.de
```

```sshconfig
Host lrz-ai
  HostName login.ai.lrz.de
  User <LRZ_USER>
  IdentityFile ~/.ssh/id_ed25519_lrz_ai
  ForwardAgent yes
```

## Login Node Setup

```bash
mkdir -p ~/src
cd ~/src
git clone <ARIA_NBV_GIT_URL> ARIA-NBV
cd ARIA-NBV
dssusrinfo all
export ARIA_DSS=/dss/.../aria-nbv
.agents/skills/lrz-ai-systems/scripts/lrz-dss-init.sh "$ARIA_DSS"
```

## Resource Checks

Run Slurm queries as one-shot inspections. Do not put them in polling loops.

```bash
.agents/skills/lrz-ai-systems/scripts/lrz-probe.sh
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh summary
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh gpu
.agents/skills/lrz-ai-systems/scripts/lrz-resources.sh mine
```

Read `slurm-partitions.md` before choosing final partitions and
`slurm-job-patterns.md` before writing batch directives.

## GPU Smoke Test

```bash
salloc -p lrz-v100x2 --gres=gpu:1 --time=00:10:00
srun --pty bash
nvidia-smi
exit
exit
```

## Container Smoke Test

```bash
salloc -p lrz-v100x2 --gres=gpu:1 --time=00:30:00
export ARIA_DSS=/dss/.../aria-nbv
export LRZ_CONTAINER_IMAGE='nvcr.io#nvidia/pytorch:24.10-py3'
.agents/skills/lrz-ai-systems/scripts/lrz-container-shell.sh
cd aria_nbv
python -m pip install -U uv
uv sync --all-extras
uv run python -c 'import torch; print(torch.cuda.is_available())'
exit
exit
```

## Job Control

```bash
squeue -u "$USER" -o "%.18i %.20P %.30j %.8T %.10M %.6D %R"
scancel <JOB_ID>
scancel --me
```

For failed or pending jobs, collect evidence with `troubleshooting-slurm.md`
before changing resources or scripts.
