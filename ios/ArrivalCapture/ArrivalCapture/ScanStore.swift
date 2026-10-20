import Foundation
import RoomPlan

/// One saved capture: `Documents/scans/<id>/` holds `roomplan.json` (CapturedRoom via JSONEncoder,
/// the format `arrival/scan/roomplan.py` reads), `room.usdz` and this record as `scan_meta.json`.
struct Scan: Identifiable, Codable, Equatable {
    var id: String
    var roomName: String
    var created: Date
    var jobID: String?
    var jobStatus: String?
    var jobStage: String?
    var jobError: String?
    var uploadedTo: String?

    var isJobFinished: Bool { jobStatus == "done" || jobStatus == "failed" }
}

@MainActor
final class ScanStore: ObservableObject {
    @Published private(set) var scans: [Scan] = []
    let root: URL

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.outputFormatting = [.prettyPrinted, .sortedKeys]
        e.dateEncodingStrategy = .iso8601
        return e
    }()
    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    init() {
        root = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("scans", isDirectory: true)
        try? FileManager.default.createDirectory(at: root, withIntermediateDirectories: true)
        reload()
    }

    /// Same rule as the worker's `room_id_for`: lowercase, runs of anything outside [a-z0-9_] become "_".
    static func roomID(_ name: String) -> String {
        var out = ""
        var pendingUnderscore = false
        for ch in name.lowercased() {
            if ch.isASCII && (ch.isLetter || ch.isNumber || ch == "_") {
                if pendingUnderscore && !out.isEmpty { out.append("_") }
                pendingUnderscore = false
                out.append(ch)
            } else {
                pendingUnderscore = true
            }
        }
        return out.isEmpty ? "room" : out
    }

    func folder(_ scan: Scan) -> URL { root.appendingPathComponent(scan.id, isDirectory: true) }
    func jsonURL(_ scan: Scan) -> URL { folder(scan).appendingPathComponent("roomplan.json") }
    func usdzURL(_ scan: Scan) -> URL { folder(scan).appendingPathComponent("room.usdz") }

    /// Files that exist on disk for this scan, for the share sheet.
    func files(_ scan: Scan) -> [URL] {
        [jsonURL(scan), usdzURL(scan)].filter { FileManager.default.fileExists(atPath: $0.path) }
    }

    func reload() {
        let dirs = (try? FileManager.default.contentsOfDirectory(at: root, includingPropertiesForKeys: nil)) ?? []
        scans = dirs.compactMap { dir in
            guard let data = try? Data(contentsOf: dir.appendingPathComponent("scan_meta.json")) else { return nil }
            return try? Self.decoder.decode(Scan.self, from: data)
        }
        .sorted { $0.created > $1.created }
    }

    /// Writes the JSON first; a USDZ export failure is returned as a warning, not thrown, because the
    /// pipeline only needs the JSON.
    func save(_ room: CapturedRoom, roomName: String) throws -> (Scan, usdzError: Error?) {
        let name = Self.roomID(roomName)
        let stamp = Int(Date().timeIntervalSince1970)
        let scan = Scan(id: "\(name)_\(stamp)", roomName: name, created: Date())
        try FileManager.default.createDirectory(at: folder(scan), withIntermediateDirectories: true)
        try Self.encoder.encode(room).write(to: jsonURL(scan), options: .atomic)
        var usdzError: Error?
        do {
            try room.export(to: usdzURL(scan))
        } catch {
            usdzError = error
        }
        try write(scan)
        reload()
        return (scan, usdzError)
    }

    func update(_ scan: Scan) {
        try? write(scan)
        if let i = scans.firstIndex(where: { $0.id == scan.id }) {
            scans[i] = scan
        }
    }

    func delete(_ scan: Scan) {
        try? FileManager.default.removeItem(at: folder(scan))
        scans.removeAll { $0.id == scan.id }
    }

    private func write(_ scan: Scan) throws {
        try Self.encoder.encode(scan).write(to: folder(scan).appendingPathComponent("scan_meta.json"), options: .atomic)
    }
}
