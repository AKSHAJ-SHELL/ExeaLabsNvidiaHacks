"""python -m arrival demo | validate | serve"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

EXIT_OK, EXIT_INVALID, EXIT_USAGE = 0, 1, 2
MAX_DEFAULT_VIDEO_EPISODES = 16


def run_demo(room: str = "hero_kitchen", episodes: int = 4, videos: str = "all",
             out_dir: str | Path = "out", scans_dir: str | Path = "scans",
             from_roomplan: bool = False, seed: int = 0, log=print) -> dict:
    """scan -> twin -> tasks -> scripted retarget -> oracle -> sim_texture -> LeRobot v2 -> report."""
    from arrival.eval.report import build_report, write_report
    from arrival.export.lerobot import LeRobotWriter
    from arrival.generate.scripted import generate
    from arrival.render.sim_texture import room_center_x
    from arrival.scan import bundle as scan_bundle
    from arrival.scan import roomplan
    from arrival.tasks.propose import propose, write_tasks
    from arrival.twin.compile import compile_twin, write_twin

    out_dir, scans_dir = Path(out_dir), Path(scans_dir)
    if from_roomplan:
        bundle = roomplan.load(scans_dir / room / "roomplan.json", room)
        # RoomPlan does not capture small objects; borrow the authored object placements if present.
        authored = scans_dir / room / "scan.json"
        if authored.is_file():
            bundle["objects"] = scan_bundle.load(authored)["objects"]
    else:
        bundle = scan_bundle.load_room(room, scans_dir)
    twin = compile_twin(bundle)
    twin_dir = out_dir / "twins" / room
    write_twin(twin, twin_dir)
    tasks = propose(twin)
    write_tasks(tasks, twin_dir)
    if not tasks["tasks"]:
        raise SystemExit(f"no tasks could be proposed for {room}")
    log(f"[arrival] {room}: {len(twin['fixtures'])} fixtures, {len(tasks['tasks'])} task variations")

    t0 = time.perf_counter()
    dataset_dir = out_dir / "datasets" / room
    writer = LeRobotWriter(dataset_dir, room, videos, room_center_x=room_center_x(twin))
    attempts = 0
    for att in generate(tasks["tasks"], twin, episodes, seed=seed):
        attempts += 1
        if att["success"]:  # oracle: drop misses
            ep = writer.add(att)
            if ep and ep % 100 == 0:
                log(f"[arrival]   {ep} episodes ({attempts} attempts)")
    info = writer.finish(attempts)
    seconds = time.perf_counter() - t0
    report = build_report(room, attempts, info["total_episodes"], seconds, sorted(writer.families))
    report_path = write_report(report, out_dir / "reports")
    return {"dataset": dataset_dir, "report": report_path, "info": info, "report_data": report,
            "twin_dir": twin_dir}


def cmd_demo(a) -> int:
    if a.episodes < 1:
        print("--episodes must be >= 1", file=sys.stderr)
        return EXIT_USAGE
    videos = a.videos
    if videos is None:
        if a.episodes > MAX_DEFAULT_VIDEO_EPISODES:
            print(f"--episodes {a.episodes} > {MAX_DEFAULT_VIDEO_EPISODES}: pass --videos sparse "
                  f"(or --videos all / none) explicitly.", file=sys.stderr)
            return EXIT_USAGE
        videos = "all"
    res = run_demo(a.room, a.episodes, videos, a.out, a.scans, from_roomplan=a.from_roomplan)
    r = res["report_data"]
    print(f"dataset: {res['dataset']}")
    print(f"report:  {res['report']}")
    print(f"{r['successes']} episodes / {r['attempts']} attempts ({r['dropped']} dropped) in "
          f"{r['seconds']:.1f}s, {res['info']['total_videos']} videos, families={r['tasks']}")
    print("NOTE: scripted placeholder motion; walkin_physically_valid=false. Do not fine-tune on it.")
    return EXIT_OK


def cmd_validate(a) -> int:
    from arrival.export.validate import validate

    errors = validate(a.dataset_dir)
    if errors:
        for e in errors:
            print(f"INVALID: {e}", file=sys.stderr)
        return EXIT_INVALID
    info = json.loads((Path(a.dataset_dir) / "meta" / "info.json").read_text())
    print(f"OK: {a.dataset_dir} — {info['total_episodes']} episodes, {info['total_frames']} frames, "
          f"{info['total_tasks']} tasks, video_policy={info['walkin_video_policy']}, "
          f"physically_valid={info['walkin_physically_valid']}")
    return EXIT_OK


def cmd_serve(a) -> int:
    from arrival.web.app import serve

    serve(port=a.port, out_dir=Path(a.out), scans_dir=Path(a.scans))
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="arrival", description="WALK·IN Arrival: room scan -> GR00T LeRobot v2 dataset")
    sub = p.add_subparsers(dest="cmd")
    d = sub.add_parser("demo", help="compile the room and write the dataset")
    d.add_argument("--episodes", type=int, default=4)
    d.add_argument("--videos", choices=["all", "sparse", "none"], default=None)
    d.add_argument("--room", default="hero_kitchen")
    d.add_argument("--from-roomplan", action="store_true", help="normalize scans/<room>/roomplan.json instead of scan.json")
    d.add_argument("--out", default="out")
    d.add_argument("--scans", default="scans")
    d.set_defaults(fn=cmd_demo)
    v = sub.add_parser("validate", help="structurally check a LeRobot v2 dataset")
    v.add_argument("dataset_dir")
    v.set_defaults(fn=cmd_validate)
    s = sub.add_parser("serve", help="local page on 127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.add_argument("--out", default="out")
    s.add_argument("--scans", default="scans")
    s.set_defaults(fn=cmd_serve)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        a = parser.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code else EXIT_OK
    if not a.cmd:
        parser.print_usage(sys.stderr)
        return EXIT_USAGE
    return a.fn(a)
