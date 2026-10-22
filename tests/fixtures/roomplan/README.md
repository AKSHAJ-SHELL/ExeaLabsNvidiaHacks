# Real RoomPlan exports (test fixtures)

Public Apple RoomPlan `CapturedRoom` JSON exports found on GitHub (`gh search code polygonCorners`),
copied verbatim for normalizer tests. Both look like real phone captures (non-round transforms,
floor below the ARKit origin, mixed confidences). Neither contains kitchen fixtures.

| file | source repo | path in repo |
| --- | --- | --- |
| `amal.json` | amal884/FormModuleBimProject | `src/jsonFiles/sortie.json` |
| `shopyseek.json` | sow-coding/shopyseek-web | `public/objects.json` |

## Licence check (P2, 2026-10-21)

Neither source repository has a licence: the GitHub API reports no licence for either repo, and neither has a
`LICENSE` file (checked with `gh api repos/<owner>/<repo>`).

| file | source repo | licence | last push |
| --- | --- | --- | --- |
| `amal.json` | amal884/FormModuleBimProject | none | 2024-03-07 |
| `shopyseek.json` | sow-coding/shopyseek-web | none | 2025-12-24 |

With no licence, the authors keep all rights, so these files have no grant that lets this repository redistribute
them. They are kept only until our own consented captures (P2, `docs/SCANNING.md`) can replace them. These files use
them: `tests/test_intake.py`, `tests/test_non_kitchen.py`, `tests/test_roomplan_coverage.py`, `tests/test_summary.py`,
`tests/test_web.py`, `arrival/eval/summary.py` and `scripts/render_rooms.py`. The office scan (`amal.json`) is the only
non-kitchen room the sim runs end to end, so a replacement needs a room with a table and chairs. `shopyseek.json`
needs a desk whose only free side is blocked by its chair.
