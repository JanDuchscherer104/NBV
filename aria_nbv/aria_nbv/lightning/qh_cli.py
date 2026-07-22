"""Installed ``nbv-train-qh`` CLI for :class:`QhExperimentConfig`.

The command parses one strict TOML experiment and optionally overrides only
the full-state Lightning checkpoint. This module provides argument parsing and
delegation only; :class:`QhExperimentConfig` owns admission and loop dispatch.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .qh_experiment import QhExperimentConfig


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nbv-train-qh",
        description="Train the target-conditioned finite-horizon Q_H scorer.",
    )
    parser.add_argument("--config-path", type=Path, required=True, help="Strict Q_H experiment TOML.")
    parser.add_argument("--ckpt-path", type=Path, default=None, help="Full-state Lightning checkpoint.")
    return parser


def main(argv: list[str] | None = None) -> None:
    """Parse one strict TOML config and run the Q_H experiment."""

    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    config = QhExperimentConfig.from_toml(args.config_path.expanduser().resolve())
    if args.ckpt_path is not None:
        config.ckpt_path = args.ckpt_path
    config.setup_target_and_run()


if __name__ == "__main__":
    main()


__all__ = ["main"]
