# Scanning rooms for Arrival

This is the field protocol for CAP-3 scans. It produces a RoomPlan JSON export, two reference photos, and three independent tape measurements so the twin can be checked against the room. The capture app in CAP-1 is still planned; use a RoomPlan exporter that writes the `CapturedRoom` JSON and USDZ until it exists. The authored `hero_kitchen` sample is not a measured room.

## Before entering the room

1. Get permission from the owner or occupant to scan the room and to store the resulting geometry and reference photos in this public repository. Explain that the room layout may reveal private details. If permission does not include public release, keep the files out of `scans/`.
2. Pick a short, lowercase room ID with underscores, such as `kitchen_galley_01`. Do not put an address, person's name, or other identifying detail in the ID or filenames.
3. Record the device model, iOS version, date, room type, lighting, and clutter level in `notes.md`. Include whether the room has glass, mirrors, reflective appliances, or occluded fixtures.
4. Choose three features to measure **with a tape measure**: counter length, counter height from finished floor, and sink width. Record the endpoints or surfaces used for each measurement. Record meters to the nearest centimeter. If the room has no sink or counter, record three other fixed dimensions and name them clearly; this room cannot be used for the kitchen accuracy gate.

## Capture pass

1. Turn on the room lights and keep them steady. Open curtains if it improves visibility without creating strong glare. Avoid direct reflections in mirrors, windows, and glossy appliance doors where possible.
2. Start near a doorway and make one continuous pass around the perimeter at a steady walking pace. Keep the device pointed at the wall-floor junction and furniture faces so corners and fixture edges are seen from more than one angle. Pause briefly at the sink, stove, fridge, doors, and any island.
3. Keep people and pets out of the scan. Move loose objects only if the owner permits it; record anything moved in `notes.md`. Do not treat a temporarily cleared room as a furnished-room scan.
4. Check the preview before leaving. Verify that the wall loop closes, the floor is present, major fixtures are represented, and there are no obvious duplicate or floating objects. If a wall or key fixture is missing, take another full pass and keep only the better export.
5. Take two reference photos from different corners showing the overall layout and major fixtures. Avoid faces, screens, documents, photographs, addresses, and other personal information. Retake or crop a photo if any such detail is visible.

## Export and file layout

Keep the raw export and the measurements together:

```text
scans/<room_id>/
  roomplan.json       # CapturedRoom JSON, as exported
  room.usdz           # optional; do not commit large files without review
  notes.md
  reference_1.jpg
  reference_2.jpg
```

The JSON must be the RoomPlan `CapturedRoom` data, including transforms and dimensions in meters. Do not manually edit fixture positions to make the accuracy test pass. If the exporter produces another schema, keep the original privately and document the conversion before adding `roomplan.json`. The two photos are reference views, not the four-photo fallback input.

Use this `notes.md` template:

```markdown
# <room_id>

- Room type / layout: kitchen / galley
- Device / iOS: <model> / <version>
- Capture date: YYYY-MM-DD
- Lighting / clutter: <description>
- Reflective or occluded surfaces: <description>
- Scan issues or objects moved: <description>
- Permission for public geometry and photos: yes; obtained from <role, not name>

| Feature | Tape measurement (m) | Endpoints or surfaces measured | RoomPlan fixture ID |
|---|---:|---|---|
| Counter length | | | |
| Counter height | | finished floor to worktop | |
| Sink width | | outside rim to outside rim | |
```

Use fixture IDs from the JSON in the last column. If a feature is not recognized by RoomPlan, write `missing`; do not substitute a guessed dimension. Keep the signed consent record outside this public repo.

## Review before committing

1. Open the JSON and confirm it contains `walls` and `objects`. Make sure the device exported the whole room rather than a partial pass.
2. Remove location metadata from the photos. Inspect the visible pixels and the notes for personal information. Do not commit raw RGB-D frames until their privacy and storage format is defined under CAP-2.
3. Normalize and compile the scan locally, then run the regression suite:

   ```bash
   python scripts/render_rooms.py scans/<room_id>
   python -m pytest -q tests/test_scans.py
   ```

   For a kitchen with recognized fixtures, also run `python -m arrival demo --room <room_id> --from-roomplan --episodes 4`. A non-kitchen room or a kitchen without a recognized counter may yield no tasks. Record that coverage gap; do not invent objects in the scan.
4. Inspect the top-down PNG under `out/renders/`. Compare each of the three tape measurements with the corresponding twin dimension. Record the absolute error in centimeters in `notes.md`. The TWN-1 accuracy gate is **5 cm per measurement**; if an error exceeds it, keep the raw scan, mark the failure, and re-scan or fix the normalizer. Never silently change the tape value.
5. Add the scan and `notes.md` to a focused PR. Include the reference photos only after the privacy check. State whether the scan passed the geometry and 5 cm checks.

The automated scan regression suite checks structure and geometry. It does not establish metric accuracy; only the independent tape measurements can do that.
