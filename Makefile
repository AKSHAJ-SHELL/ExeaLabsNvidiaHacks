# Laptop shortcuts. Everything is offline; nothing here needs a GPU or an API key.
PY ?= python
OUT ?= out

.PHONY: install test sim validate demo serve clean site check-site

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

# Static demo site: no build step. Open http://localhost:8765
site:
	$(PY) -m http.server 8765 --directory site

# Resolves every asset path the site references, against a running `make site` (or by file path with --offline)
check-site:
	$(PY) scripts/check_site.py
