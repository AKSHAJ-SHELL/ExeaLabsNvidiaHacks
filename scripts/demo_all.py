"""One-command demo (DEM-4): scan -> twin -> MuJoCo sim -> GR00T dataset -> validate -> eval -> contact sheet.

    python scripts/demo_all.py --quick            # 2 episodes, 1 person, 64 px (about a minute, under 1.5 GB)
    python scripts/demo_all.py --full --serve     # 8 episodes, 2 people, 128 px, then the local page
    python scripts/demo_all.py --quick --room hero_kitchen --out out/demo

Runs the existing functions in-process, prints PASS/FAIL and wall time per stage, and writes
<out>/demo_summary.md and <out>/demo_summary.json. Exits 1 if any stage fails.
The dataset is a scripted expert in simulation; no policy was trained and no cost was measured.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

HONEST_LABEL = "Scripted expert in simulation, no policy trained."
FAMILIES = ["counter_to_sink", "open_drawer"]  # the README's sim defaults
SIZES = {"quick": {"episodes": 2, "people": 1, "res": 64}, "full": {"episodes": 8, "people": 2, "res": 128}}
EVAL_EPISODES = 2  # per family
UNMEASURED = ["nebius_token_factory_usd", "nebius_gpu_job_usd", "cosmos_restyle_usd", "finetune_usd",
              "teleop_comparison_usd_per_demo"]


class StageFailed(Exception):
    pass


def _stage(stages: list[dict], name: str, fn, log=print):
    """Run one stage, record wall time and PASS/FAIL, and raise StageFailed on failure."""
    t0 = time.perf_counter()
    err = None
    try:
        detail = fn()
    except (Exception, SystemExit) as e:  # run_demo reports a missing room with SystemExit(message)
        detail = None
        err = " ".join(str(e.code if isinstance(e, SystemExit) else e).split()) or type(e).__name__
    row = {"stage": name, "status": "FAIL" if err else "PASS", "seconds": round(time.perf_counter() - t0, 2),
           "detail": err or (detail if isinstance(detail, str) else None)}
    stages.append(row)
    log(f"[demo_all] {row['status']} {name} ({row['seconds']:.1f}s)" + (f": {err}" if err else ""))
    if err:
        raise StageFailed(f"{name}: {err}")
    return detail


def _render_layout(twin: dict, room: str, out: Path) -> str:
    import render_rooms  # scripts/render_rooms.py

    path = out / "renders" / f"{room}_top.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    render_rooms.render(room, twin, 100.0).save(path)
    return str(path)


def _markdown(s: dict) -> str:
    ds = s["dataset"]
    lines = [f"# Arrival demo summary: {s['room']}", "", f"**{HONEST_LABEL}**", "",
             f"Mode: {s['mode']}. Overall: **{s['overall']}**. Wall time {s['seconds']} s.", "",
             "| Stage | Status | Seconds |", "|---|---|---|"]
    lines += [f"| {r['stage']} | {r['status']} | {r['seconds']} |" for r in s["stages"]]
    lines += ["", "## Dataset", ""]
    if ds:
        lines += [f"- Path: `{ds['path']}`", f"- Episodes: {ds['episodes']}, frames: {ds['frames']}",
                  f"- arrival_physically_valid: {str(ds['physically_valid']).lower()}",
                  f"- joints_are_placeholder: {str(ds['joints_are_placeholder']).lower()}",
                  f"- Demos per hour (this laptop): {ds['demos_per_hour']}"]
    else:
        lines.append("- not produced")
    lines += ["", "## Closed-loop eval (scripted expert)", ""]
    if s["per_family"]:
        lines += ["| Family | Successes | Episodes |", "|---|---|---|"]
        lines += [f"| {k} | {v['successes']} | {v['episodes']} |" for k, v in s["per_family"].items()]
    else:
        lines.append("- not run")
    lines += ["", "## Cost (not measured)", ""] + [f"- {k}: null" for k in s["cost"]]
    if s["error"]:
        lines += ["", "## Error", "", s["error"]]
    return "\n".join(lines) + "\n"


def run(room: str, mode: str, out: Path, scans: str = "scans", log=print) -> tuple[dict, int]:
    from arrival.cli import run_demo

    size = SIZES[mode]
    t_all = time.perf_counter()
    stages: list[dict] = []
    s = {"room": room, "mode": mode, "size": size, "honest_label": HONEST_LABEL, "stages": stages,
         "dataset": None, "per_family": {}, "successes": 0, "cost": {k: None for k in UNMEASURED},
         "artifacts": {}, "error": None}
    quiet = lambda *_: None  # noqa: E731
    try:
        # scan normalize + compile; the 1-episode placeholder dataset it also writes is not the demo dataset
        res = _stage(stages, "scan normalize + compile",
                     lambda: run_demo(room, 1, "none", out, scans, log=quiet), log)
        twin = json.loads((res["twin_dir"] / "twin.json").read_text())
        s["artifacts"]["layout"] = _stage(stages, "twin layout png", lambda: _render_layout(twin, room, out), log)

        from arrival.sim.collect import collect

        sim = _stage(stages, "sim dataset", lambda: collect(
            twin, FAMILIES, size["episodes"], out, people=size["people"], res=size["res"], save_preview=True,
            log=quiet), log)
        ds_dir = Path(sim["dataset"])
        info = json.loads((ds_dir / "meta" / "info.json").read_text())
        emb = json.loads((ds_dir / "meta" / "embodiment.json").read_text())  # the placeholder flag lives here
        rep = sim["report_data"]
        s["dataset"] = {"path": str(ds_dir), "episodes": info["total_episodes"], "frames": info["total_frames"],
                        "physically_valid": info.get("arrival_physically_valid"),
                        "joints_are_placeholder": emb.get("joints_are_placeholder"),
                        "demos_per_hour": rep["demos_per_hour"], "attempts": rep["attempts"]}
        s["successes"] = rep["successes"]

        def check():
            from arrival.export.validate import validate

            errs = validate(ds_dir)
            if errs:
                raise StageFailed("; ".join(errs[:3]))
            return f"{info['total_episodes']} episodes valid"

        _stage(stages, "validate", check, log)

        def ev():
            from arrival.eval.harness import evaluate

            r = evaluate(twin, FAMILIES, EVAL_EPISODES, "scripted", people=size["people"], res=size["res"],
                         out_dir=out, log=quiet)
            s["per_family"] = {k: {"successes": v["successes"], "episodes": v["episodes"]}
                               for k, v in r["families"].items()}
            if not s["per_family"]:
                raise StageFailed("no eval episodes ran")
            return f"{r['totals']['successes']}/{r['totals']['episodes']}"

        _stage(stages, "closed-loop eval", ev, log)

        def sheet():
            p = out / "previews" / f"{room}_sim_contact.png"
            if not p.is_file():
                raise StageFailed(f"missing {p}")
            return str(p)

        s["artifacts"]["contact_sheet"] = _stage(stages, "contact sheet", sheet, log)
    except StageFailed as e:
        s["error"] = str(e)
    s["overall"] = "FAIL" if s["error"] else "PASS"
    s["seconds"] = round(time.perf_counter() - t_all, 2)
    s["physically_valid"] = bool(s["dataset"] and s["dataset"]["physically_valid"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "demo_summary.json").write_text(json.dumps(s, indent=2))
    (out / "demo_summary.md").write_text(_markdown(s))
    return s, 1 if s["error"] else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--quick", action="store_true", help="2 episodes, 1 person, 64 px (default)")
    g.add_argument("--full", action="store_true", help="8 episodes, 2 people, 128 px")
    ap.add_argument("--room", default="hero_kitchen")
    ap.add_argument("--out", default="out")
    ap.add_argument("--scans", default="scans")
    ap.add_argument("--serve", action="store_true", help="start the local page when every stage passed")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args(argv)
    out = Path(a.out)
    s, code = run(a.room, "full" if a.full else "quick", out, a.scans)
    if code:
        print(f"demo_all: FAIL {s['error']}", file=sys.stderr)
        return code
    print((out / "demo_summary.md").read_text())
    print(f"summary: {out / 'demo_summary.md'}")
    if a.serve:
        from arrival.cli import resolve_scans
        from arrival.web.app import serve

        serve(port=a.port, out_dir=out, scans_dir=resolve_scans(a.scans))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
