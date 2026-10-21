import Foundation

/// Client for the Arrival web server (`python -m arrival serve --host 0.0.0.0`).
/// `POST /jobs` takes a multipart form with the file in field `scan` (and optionally a CAP-2a frames zip in
/// `frames`) and answers 202 `{"status", "id", "status_url"}`; `GET /jobs/<id>` returns the job's status.json.
enum ArrivalAPI {
    struct QueuedJob: Decodable {
        let id: String
        let status: String
    }

    struct JobStatus: Decodable {
        let id: String
        let status: String
        let stage: String?
        let error: String?
        let attempts: Int?
        let successes: Int?
    }

    enum APIError: LocalizedError {
        case badServerURL(String)
        case http(Int, String)

        var errorDescription: String? {
            switch self {
            case .badServerURL(let s):
                return "Not a server URL: \"\(s)\". Use the one `python -m arrival serve --host 0.0.0.0` prints, like http://192.168.1.20:8000"
            case .http(let code, let body):
                return "Server answered \(code): \(body)"
            }
        }
    }

    static func baseURL(_ server: String) throws -> URL {
        var s = server.trimmingCharacters(in: .whitespacesAndNewlines)
        if !s.contains("://") { s = "http://" + s }
        while s.hasSuffix("/") { s.removeLast() }
        guard let url = URL(string: s), url.host != nil else { throw APIError.badServerURL(server) }
        return url
    }

    static func ping(server: String) async throws {
        let (data, response) = try await URLSession.shared.data(for: request(try baseURL(server)))
        try check(response, data, expect: 200)
    }

    /// Uploads the scan, and the frames zip when given. The body is written to a temporary file and streamed
    /// from there, so a large frames bundle is never held in memory.
    static func upload(fileURL: URL, filename: String, framesZip: URL? = nil, server: String) async throws -> QueuedJob {
        let boundary = "ArrivalBoundary-\(UUID().uuidString)"
        var req = request(try baseURL(server).appendingPathComponent("jobs"), timeout: framesZip == nil ? 120 : 600)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        var parts = [Part(field: "scan", filename: filename, contentType: "application/json", file: fileURL)]
        if let framesZip {
            parts.append(Part(field: "frames", filename: "frames.zip", contentType: "application/zip", file: framesZip))
        }
        let body = FileManager.default.temporaryDirectory.appendingPathComponent("upload_\(UUID().uuidString).bin")
        defer { try? FileManager.default.removeItem(at: body) }
        try writeMultipart(parts, boundary: boundary, to: body)
        let (data, response) = try await URLSession.shared.upload(for: req, fromFile: body)
        try check(response, data, expect: 202)
        return try JSONDecoder().decode(QueuedJob.self, from: data)
    }

    static func status(jobID: String, server: String) async throws -> JobStatus {
        let url = try baseURL(server).appendingPathComponent("jobs").appendingPathComponent(jobID)
        let (data, response) = try await URLSession.shared.data(for: request(url))
        try check(response, data, expect: 200)
        return try JSONDecoder().decode(JobStatus.self, from: data)
    }

    static func downloadURL(jobID: String, server: String) -> URL? {
        try? baseURL(server).appendingPathComponent("jobs").appendingPathComponent(jobID).appendingPathComponent("download")
    }

    struct Part {
        let field: String
        let filename: String
        let contentType: String
        let file: URL
    }

    static func writeMultipart(_ parts: [Part], boundary: String, to output: URL) throws {
        FileManager.default.createFile(atPath: output.path, contents: nil)
        let out = try FileHandle(forWritingTo: output)
        defer { try? out.close() }
        for part in parts {
            try out.write(contentsOf: Data(("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(part.field)\"; "
                + "filename=\"\(part.filename)\"\r\nContent-Type: \(part.contentType)\r\n\r\n").utf8))
            let input = try FileHandle(forReadingFrom: part.file)
            defer { try? input.close() }
            while let chunk = try input.read(upToCount: 1 << 20), !chunk.isEmpty {
                try out.write(contentsOf: chunk)
            }
            try out.write(contentsOf: Data("\r\n".utf8))
        }
        try out.write(contentsOf: Data("--\(boundary)--\r\n".utf8))
    }

    private static func request(_ url: URL, timeout: TimeInterval = 15) -> URLRequest {
        var req = URLRequest(url: url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: timeout)
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        return req
    }

    private static func check(_ response: URLResponse, _ data: Data, expect: Int) throws {
        let code = (response as? HTTPURLResponse)?.statusCode ?? -1
        guard code == expect else {
            throw APIError.http(code, String(decoding: data.prefix(300), as: UTF8.self))
        }
    }
}
