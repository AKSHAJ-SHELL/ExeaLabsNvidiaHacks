# Arrival Capture (iOS)

CAP-1. Scans a room with Apple RoomPlan, saves the `CapturedRoom` JSON and a USDZ model, shares them
(AirDrop, Files, Mail) and uploads the JSON to the Arrival server, which turns it into a twin and a sim
dataset.

Needs a LiDAR device (iPhone 12 Pro or newer Pro, iPad Pro 2020+) on iOS 17 or later, and a Mac with
Xcode 26.1+ (match or exceed your phone's iOS version). A free Apple ID is enough.

## Build and run on your phone

1. Open `ios/ArrivalCapture/ArrivalCapture.xcodeproj` in Xcode.
2. Xcode → Settings → Accounts: add your Apple ID.
3. Select the **ArrivalCapture** target → Signing & Capabilities → Team: pick your *(Personal Team)*.
   The bundle id is `dev.arrival.capture.t<your team id>`, so it is unique per person; nothing to edit.
   Xcode writes `DEVELOPMENT_TEAM = <id>;` into `project.pbxproj`; don't commit that line.
4. Plug in the phone, tap Trust, and turn on Settings → Privacy & Security → **Developer Mode** (reboots).
5. Pick the phone as the run destination and press Run (⌘R).
6. First launch only: on the phone, Settings → General → VPN & Device Management → trust your Apple ID.

With a free Apple ID the app expires after 7 days; press Run again to renew it.

## Use it

On a Mac on the **same Wi-Fi**:

```bash
python -m arrival serve --host 0.0.0.0     # prints "Capture app server URL: http://192.168.x.y:8000"
python -m arrival work                     # second terminal: processes uploads
```

On the phone:

1. Paste the printed URL into **Arrival server** and tap **Test connection**. iOS asks for Local Network
   access the first time; allow it and tap again.
2. Type a room name (`kitchen_a`; it is reduced to `[a-z0-9_]`) and tap **Scan room**. Follow the on-screen
   coaching, then **Done**, wait for the model, **Save**.
3. Open the scan: **Share / AirDrop** sends `roomplan.json` and `room.usdz`; **Upload to server** posts
   `roomplan.json` as `<room>.json` to `POST /jobs`. The screen polls `GET /jobs/<id>` and shows a
   **Download dataset.zip** link when the worker is done.

Scans live in the app's Documents folder (`scans/<room>_<unix time>/`), which the Files app shows under
*On My iPhone → Arrival Capture*.

To commit a scan for CAP-3, AirDrop `roomplan.json` to the Mac and put it at `scans/<room_id>/roomplan.json`;
`tests/test_scans.py` picks it up.

## Notes

- `NSAllowsArbitraryLoads` is on because the local server is plain `http://` on a LAN IP. Remove it once
  the server is hosted over HTTPS (DEM-1).
- The JSON is `JSONEncoder().encode(capturedRoom)`, the format `arrival/scan/roomplan.py` reads
  (`docs/04-contracts.md`). The upload request is mirrored byte for byte in
  `tests/test_web.py::test_capture_app_upload_reaches_worker`.
- Command-line compile check without signing:
  `xcodebuild -project ios/ArrivalCapture/ArrivalCapture.xcodeproj -target ArrivalCapture -sdk iphoneos CODE_SIGNING_ALLOWED=NO SYMROOT=ios/build build`
