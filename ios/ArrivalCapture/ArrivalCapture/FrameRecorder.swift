import ARKit
import CoreImage
import Foundation

/// CAP-2: records RGB, LiDAR depth, confidence and camera poses while RoomPlan scans, into a CAP-2a bundle
/// (`FrameBundleWriter`). It reads `RoomCaptureSession.arSession.currentFrame` on a timer instead of becoming the
/// session's delegate, so RoomPlan keeps its own ARKit session untouched. A frame is kept when tracking is normal,
/// depth is present and the camera has moved or turned enough since the last kept frame; encoding runs on a
/// background queue and a sample is skipped while the previous one is still being written.
///
/// Not field-tested: whether RoomPlan's session delivers `sceneDepth` on every device has not been checked on a
/// phone. If it does not, `smoothedSceneDepth` is tried, and with neither the recorder keeps nothing and says so.
final class FrameRecorder {
    struct Settings {
        var interval: TimeInterval = 0.5   // seconds between samples
        var minMove: Float = 0.15          // metres since the last kept frame ...
        var minTurn: Float = 15 * .pi / 180  // ... or radians of view-direction change
        var maxFrames = 300                // about 100 MB of JPEG + depth at 1920x1440
        var jpegQuality: CGFloat = 0.8
    }

    let directory: URL
    private let settings: Settings
    private let session: ARSession
    private let writer: FrameBundleWriter
    private let queue = DispatchQueue(label: "arrival.frame-recorder", qos: .utility)
    private let context = CIContext()
    private var timer: Timer?
    private var busy = false
    private var lastPose: simd_float4x4?
    private(set) var keptCount = 0          // read on the main thread
    private(set) var noDepthCount = 0
    private(set) var lastError: Error?

    init(session: ARSession, roomID: String, settings: Settings = Settings()) throws {
        self.session = session
        self.settings = settings
        directory = FileManager.default.temporaryDirectory.appendingPathComponent("frames_\(UUID().uuidString)", isDirectory: true)
        writer = try FrameBundleWriter(root: directory, roomID: roomID)
    }

    func start() {
        guard timer == nil else { return }
        timer = Timer.scheduledTimer(withTimeInterval: settings.interval, repeats: true) { [weak self] _ in self?.sample() }
    }

    /// Stops sampling, waits for the frame being written and writes the manifest. Returns the bundle folder, or
    /// nil when nothing was kept (the folder is then removed).
    func finish() -> URL? {
        timer?.invalidate()
        timer = nil
        return queue.sync {
            do {
                try writer.finish()
                return directory
            } catch {
                lastError = error
                try? FileManager.default.removeItem(at: directory)
                return nil
            }
        }
    }

    /// Stops and deletes everything recorded (the scan was cancelled).
    func discard() {
        timer?.invalidate()
        timer = nil
        queue.sync { try? FileManager.default.removeItem(at: directory) }
    }

    private func sample() {
        guard !busy, keptCount < settings.maxFrames, let frame = session.currentFrame,
              case .normal = frame.camera.trackingState else { return }
        guard let depth = frame.sceneDepth ?? frame.smoothedSceneDepth else {
            noDepthCount += 1
            return
        }
        let pose = frame.camera.transform
        if let last = lastPose, !movedEnough(from: last, to: pose) { return }

        // Copy what is needed out of the ARFrame now: holding frames stalls ARKit's buffer pool.
        let (depthValues, dw, dh) = Self.floats(depth.depthMap)
        let confidence = depth.confidenceMap.map { Self.bytes($0) }
        let rgb = CIImage(cvPixelBuffer: frame.capturedImage)
        let res = frame.camera.imageResolution
        let k = frame.camera.intrinsics  // column-major: [0][0] fx, [1][1] fy, [2][0] cx, [2][1] cy
        let intrinsics = FrameBundleWriter.Intrinsics(fx: Double(k[0][0]), fy: Double(k[1][1]),
                                                      cx: Double(k[2][0]), cy: Double(k[2][1]))
        let rowMajor = (0..<16).map { Double(pose[$0 % 4][$0 / 4]) }
        let timestamp = frame.timestamp
        lastPose = pose
        busy = true
        queue.async { [weak self] in
            guard let self else { return }
            var kept = false
            var failure: Error?
            do {
                guard let jpeg = self.context.jpegRepresentation(
                    of: rgb, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!,
                    options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: self.settings.jpegQuality])
                else { throw FrameBundleWriter.BundleError.encode("RGB JPEG") }
                kept = try self.writer.add(timestamp: timestamp, rgbJPEG: jpeg, rgbWidth: Int(res.width), rgbHeight: Int(res.height),
                                           depth: depthValues, depthWidth: dw, depthHeight: dh, confidence: confidence?.0,
                                           intrinsics: intrinsics, cameraToWorld: rowMajor)
            } catch {
                failure = error
            }
            DispatchQueue.main.async {
                if kept { self.keptCount += 1 }
                if let failure { self.lastError = failure }
                self.busy = false
            }
        }
    }

    private func movedEnough(from a: simd_float4x4, to b: simd_float4x4) -> Bool {
        let move = simd_distance(simd_make_float3(a.columns.3), simd_make_float3(b.columns.3))
        let fa = -simd_make_float3(a.columns.2), fb = -simd_make_float3(b.columns.2)  // the camera looks down -z
        let turn = acos(max(-1, min(1, simd_dot(simd_normalize(fa), simd_normalize(fb)))))
        return move >= settings.minMove || turn >= settings.minTurn
    }

    /// A DepthFloat32 pixel buffer as row-major metres.
    private static func floats(_ buffer: CVPixelBuffer) -> ([Float], Int, Int) {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let w = CVPixelBufferGetWidth(buffer), h = CVPixelBufferGetHeight(buffer)
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return ([], w, h) }
        var out = [Float](repeating: 0, count: w * h)
        for y in 0..<h {
            let row = base.advanced(by: y * stride).assumingMemoryBound(to: Float32.self)
            for x in 0..<w { out[y * w + x] = row[x] }
        }
        return (out, w, h)
    }

    /// A OneComponent8 pixel buffer (ARConfidenceLevel per pixel) as row-major bytes.
    private static func bytes(_ buffer: CVPixelBuffer) -> ([UInt8], Int, Int) {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let w = CVPixelBufferGetWidth(buffer), h = CVPixelBufferGetHeight(buffer)
        let stride = CVPixelBufferGetBytesPerRow(buffer)
        guard let base = CVPixelBufferGetBaseAddress(buffer) else { return ([], w, h) }
        var out = [UInt8](repeating: 0, count: w * h)
        for y in 0..<h {
            let row = base.advanced(by: y * stride).assumingMemoryBound(to: UInt8.self)
            for x in 0..<w { out[y * w + x] = row[x] }
        }
        return (out, w, h)
    }
}
