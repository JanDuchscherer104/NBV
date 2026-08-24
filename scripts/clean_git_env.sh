#!/usr/bin/env bash

# Run nested fixture commands without inheriting the caller's repository routing.
set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec python3 "$script_dir/git_env_contract.py" --exec "$@"
