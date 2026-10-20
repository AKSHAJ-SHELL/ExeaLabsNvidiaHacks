# Laptop shortcuts. Everything is offline; nothing here needs a GPU or an API key.
PY ?= python
OUT ?= out

.PHONY: install test sim validate demo serve lint docs-check package-smoke clean

install:
	$(PY) -m pip install -e ".[dev,sim]"

test:
	$(PY) -m pytest -q -p no:cacheprovider

# Tiny physics sim (one person, 64 px frames); real runs use more episodes and --res 128.
sim:
	$(PY) -m arrival sim --episodes 2 --people 1 --res 64 --out $(OUT)

validate:
	$(PY) -m arrival validate $(OUT)/datasets/hero_kitchen_sim

# Offline end to end (about 20 s on a laptop, under 1 GB): scan, twin, sim dataset, validate, eval, contact
# sheet. Picks a working MuJoCo GL backend, refuses network access, ignores API keys, and writes
# $(OUT)/index.html. Exits 2 with one line if mujoco is missing; install it first with `make install`.
demo:
	$(PY) scripts/demo_all.py --quick --out $(OUT)

lint:
	$(PY) -m ruff check .

docs-check:
	$(PY) scripts/check_docs.py
	$(PY) scripts/check_links.py

# Build the sdist and wheel, install the wheel in a temp venv, run it from another directory.
package-smoke:
	$(PY) scripts/smoke_package.py

serve:
	$(PY) -m arrival serve --out $(OUT)

clean:
	rm -rf $(OUT)
