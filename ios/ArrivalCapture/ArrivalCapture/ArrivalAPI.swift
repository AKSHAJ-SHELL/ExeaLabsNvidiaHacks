import Foundation

/// Client for the Arrival web server (`python -m arrival serve --host 0.0.0.0`).
/// `POST /jobs` takes a multipart form with the file in field `scan` and answers 202
/// `{"status", "id", "status_url"}`; `GET /jobs/<id>` returns the job's status.json.
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

    static func upload(fileURL: URL, filename: String, server: String) async throws -> QueuedJob {
        let boundary = "ArrivalBoundary-\(UUID().uuidString)"
        var req = request(try baseURL(server).appendingPathComponent("jobs"), timeout: 120)
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        let body = multipartBody(file: try Data(contentsOf: fileURL), filename: filename, boundary: boundary)
        let (data, response) = try await URLSession.shared.upload(for: req, from: body)
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

    static func multipartBody(file: Data, filename: String, boundary: String) -> Data {
        var d = Data()
        d.append(Data("--\(boundary)\r\n".utf8))
        d.append(Data("Content-Disposition: form-data; name=\"scan\"; filename=\"\(filename)\"\r\n".utf8))
        d.append(Data("Content-Type: application/json\r\n\r\n".utf8))
        d.append(file)
        d.append(Data("\r\n--\(boundary)--\r\n".utf8))
        return d
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
