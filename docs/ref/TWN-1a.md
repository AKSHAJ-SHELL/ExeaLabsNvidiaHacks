# TWN-1a: scan accuracy harness

`scans/<room>/measurements.json` holds tape measurements of a real room; `arrival.twin.accuracy` reads the matching dimensions off the compiled twin and reports the signed error (twin minus tape) and pass/fail at `tolerance_m` (default 0.05).

```json
{"counter_length_m": 3.25, "counter_height_m": 0.92, "sink_width_m": 0.6,
 "island_length_m": 1.2, "stove_width_m": 0.7, "fridge_width_m": 0.75, "dishwasher_width_m": 0.6,
 "tolerance_m": 0.05, "measured_by": "name", "date": "2026-10-19"}
```

The first three are required; the rest are optional extras (an extra the twin cannot supply fails). Unknown keys are an error, so a typo does not silently skip a check.

## What is measured

- **counter_length_m**: the longest contiguous counter run. Pieces are scanned `counter` fixtures that are not islands, not dining tables and not synthesized. A stove or dishwasher no taller than a counter (+5 cm) sits in the run, because a tape is run across the cooktop. Pieces join when their long axes are parallel, their centres are within 25 cm across the run and the gap along it is at most 5 cm. Length is the extent along the run.
- **L and U shapes**: pieces at another angle never join, so each leg is its own run and the longest leg is compared. Measure that leg on the tape, wall to wall or to the end of the cabinet, not around the corner. A second, separate counter is another run and counts only if it is longer.
- **counter_height_m**: top of the longest counter piece in that run.
- **sink_width_m**: the sink's extent along the counter front (`size[0]`); with several, the one over the longest run.
- **island_length_m**: long side of the longest island.

## Running it

```bash
python scripts/scan_accuracy.py                 # every scans/<room> with a measurements.json; exit 1 if any error > tolerance
pytest tests/test_lidar_accuracy.py             # real rooms (skipped until one exists) plus synthetic cases
```

Rooms without `measurements.json` are skipped, not failed. `tests/fixtures/measurements/hero_kitchen.json` is marked `"authored": true`: the hero kitchen is authored, not scanned, so its numbers are derived from `scan.json` and only exercise the harness. It lives under tests and never under `scans/`, so it cannot pass for accuracy evidence.
