"""Write docs/CONTRIBUTORS.md: who worked on what, from GitHub's pull request authors and the git history.

    python scripts/render_contributors.py

Needs the `gh` CLI (logged in) for the pull request list. Work that came in through a fork branch with no pull
request is listed under its own heading with the commit author git recorded. Commits keep their original author
through every merge, so `git shortlog -sn` and GitHub's contributor graph agree with this page.
"""
from __future__ import annotations

import json
import subprocess
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FORK_WORK = [  # (title, GitHub login, branch it came from)
    ("Synchronized ego, wrist and exocentric capture, side-by-side preview, optional three-camera GR00T config",
     "rishith-c", "rishith-c/ExeaLabsNvidiaHacks:feat/ego-exocentric-capture"),
]


def run(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=True).stdout


def main() -> int:
    prs = json.loads(run("gh", "pr", "list", "--state", "all", "--limit", "500", "--json",
                         "number,title,author,state,mergedAt"))
    by_author: dict[str, list[dict]] = defaultdict(list)
    for p in prs:
        by_author[p["author"]["login"]].append(p)
    out = ["# Contributors", "",
           "Who worked on what. Pull request authors come from GitHub; the commit counts are `git shortlog -sn` on this "
           "branch. Merges keep each commit's original author, so the git history credits the same people. Regenerate "
           "with `python scripts/render_contributors.py`.", "",
           "Work on this repository's laptop pass was done by the repo owner with Claude Code agents. Those commits end with "
           "a `Co-Authored-By: Claude` line.", "", "## Commits by author", "", "```",
           run("git", "shortlog", "-sn", "HEAD").rstrip(), "```", ""]
    out += ["## From forks, with no pull request", ""]
    for title, login, src in FORK_WORK:
        out.append(f"- **@{login}**: {title} (`{src}`)")
    out.append("")
    out += ["## Pull requests by author", ""]
    for login in sorted(by_author, key=lambda a: -len(by_author[a])):
        items = sorted(by_author[login], key=lambda p: p["number"])
        out += [f"### @{login} ({len(items)})", ""]
        out += [f"- #{p['number']} {p['title']} ({p['state'].lower()})" for p in items]
        out.append("")
    (REPO / "docs" / "CONTRIBUTORS.md").write_text("\n".join(out), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
