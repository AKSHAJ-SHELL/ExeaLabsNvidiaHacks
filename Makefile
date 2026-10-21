# Laptop shortcuts. Everything is offline; nothing here needs a GPU or an API key.
PY ?= python
OUT ?= out

.PHONY: install test sim validate demo serve clean train eval-policy serve-policy

install:
	$(PY) -m pip install -e ".[dev,sim]"

test:
	$(PY) -m pytest -q -p no:cacheprovider

# Tiny physics sim (one person, 64 px frames); real runs use more episodes and --res 128.
sim:
	$(PY) -m arrival sim --episodes 2 --people 1 --res 64 --out $(OUT)

validate:
	$(PY) -m arrival validate $(OUT)/datasets/hero_kitchen_sim

# scripts/demo_all.py is owned by DEM-4.
demo:
	$(PY) scripts/demo_all.py

serve:
	$(PY) -m arrival serve --out $(OUT)

clean:
	rm -rf $(OUT)

# GPU targets (G5). Never run on a GPU yet; see docs/BUILD-LOG.md. train needs HF_TOKEN in the environment.
DATASET ?= $(OUT)/datasets/hero_kitchen_sim
CKPT ?= $(OUT)/finetune_smoke/checkpoint-100
train:
	DATASET_DIR=$(DATASET) OUTPUT_DIR=$(OUT)/finetune_smoke bash scripts/run_finetune.sh

# Needs GR00T_POLICY_URL pointing at a running `make serve-policy`.
eval-policy:
	$(PY) -m arrival eval --policy vla --out $(OUT)

serve-policy:
	$(PY) -m arrival.policy_server.gr00t_shim --model-path $(CKPT) --port 8000 --modality-config-path configs/gr00t/arrival_panda_config.py
