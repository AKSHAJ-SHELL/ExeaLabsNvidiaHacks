#!/usr/bin/env bash
# GR00T N1.7 fine-tune smoke test (100 steps). Intended to run as a Nebius Job on a GPU host.
# NOTHING HERE HAS RUN ON A GPU. Lines marked UNVERIFIED are not confirmed against a working run.
#
#   HF_TOKEN=... DATASET_DIR=out/datasets/<name> scripts/run_finetune.sh
#
# Env: DATASET_DIR (required), HF_TOKEN (required, never printed), GR00T_DIR (default /opt/Isaac-GR00T),
#      OUTPUT_DIR (default out/finetune_smoke), MAX_STEPS (default 100), PY (default python).
set -euo pipefail

die() { echo "ERROR: $*" >&2; exit 1; }

DATASET_DIR="${DATASET_DIR:-}"
GR00T_DIR="${GR00T_DIR:-/opt/Isaac-GR00T}"
OUTPUT_DIR="${OUTPUT_DIR:-out/finetune_smoke}"
MAX_STEPS="${MAX_STEPS:-100}"
PY="${PY:-python}"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

[ -n "$DATASET_DIR" ] || die "DATASET_DIR is not set"
[ -d "$DATASET_DIR" ] || die "DATASET_DIR is not a directory: $DATASET_DIR"
[ -n "${HF_TOKEN:-}" ] || die "HF_TOKEN is not set (needed for the gated Cosmos-Reason2-2B backbone)"
[ -d "$GR00T_DIR" ] || die "GR00T_DIR not found: $GR00T_DIR"
command -v nvidia-smi >/dev/null 2>&1 || die "nvidia-smi not found: no GPU on this host"
nvidia-smi -L >/dev/null 2>&1 || die "nvidia-smi found no GPU"
export HF_TOKEN # UNVERIFIED: that huggingface_hub in the GR00T env reads HF_TOKEN from the environment

DATASET_DIR="$(cd "$DATASET_DIR" && pwd)"
mkdir -p "$OUTPUT_DIR"
OUTPUT_DIR="$(cd "$OUTPUT_DIR" && pwd)"

echo "1/3 dataset check"
"$PY" "$REPO_DIR/scripts/check_dataset_loader.py" "$DATASET_DIR" || die "dataset failed the loader check"

# Flags are from the Isaac-GR00T README single-GPU fine-tune example.
# UNVERIFIED: --global-batch-size 32 is the README example value; it may not fit with our two cameras.
CMD=(uv run python gr00t/experiment/launch_finetune.py
  --base-model-path nvidia/GR00T-N1.7-3B
  --dataset-path "$DATASET_DIR"
  --embodiment-tag NEW_EMBODIMENT
  --modality-config-path "$REPO_DIR/configs/gr00t/arrival_panda_config.py"
  --num-gpus 1
  --output-dir "$OUTPUT_DIR"
  --max-steps "$MAX_STEPS"
  --global-batch-size 32
  --dataloader-num-workers 4)

echo "2/3 fine-tune: $MAX_STEPS steps"
START="$(date +%s)"
(cd "$GR00T_DIR" && CUDA_VISIBLE_DEVICES=0 "${CMD[@]}") || die "fine-tune failed"
END="$(date +%s)"

# UNVERIFIED: that checkpoints land directly under --output-dir as checkpoint-<step>.
CKPT="$(find "$OUTPUT_DIR" -maxdepth 2 -type d -name 'checkpoint-*' | sort -V | tail -n 1)"
[ -n "$CKPT" ] || die "no checkpoint-* directory found under $OUTPUT_DIR"

echo "3/3 writing run record"
"$PY" - "$OUTPUT_DIR/finetune_run.json" "$CKPT" "$((END - START))" "$MAX_STEPS" "${CMD[*]}" <<'PYEOF'
import json, sys
out, ckpt, secs, steps, cmd = sys.argv[1:6]
with open(out, "w") as f:
    json.dump({"command": cmd, "duration_s": int(secs), "max_steps": int(steps),
               "checkpoint_path": ckpt}, f, indent=2)
PYEOF
echo "checkpoint: $CKPT"
echo "record: $OUTPUT_DIR/finetune_run.json"
