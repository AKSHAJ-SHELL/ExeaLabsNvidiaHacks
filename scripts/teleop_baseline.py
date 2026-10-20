"""Timed keyboard teleop in the twin, for the generated-vs-teleop cost comparison (L20, OPS-3).

    mjpython scripts/teleop_baseline.py --operator-usd-per-hour 40 --successes 20    # macOS (the viewer needs mjpython)
    python scripts/teleop_baseline.py --operator-usd-per-hour 40 --successes 20      # Linux, Windows

Writes out/teleop_baseline.json (read by `python -m arrival.eval.cost`), out/reports/<room>_teleop_attempts.jsonl,
and with --record out/datasets/<room>_teleop. Logic and key map: arrival/sim/teleop.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from arrival.sim.teleop import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
