import RoomPlan
import SwiftUI

/// Hosts Apple's `RoomCaptureView`: live coaching while scanning, then the processed 3D model.
final class RoomCaptureController: UIViewController, RoomCaptureViewDelegate {
    var onResult: ((CapturedRoom) -> Void)?
    var onError: ((Error) -> Void)?
    /// Set before the view appears: record a CAP-2 RGB-D frame bundle for this room alongside RoomPlan.
    var framesRoomID: String?

    private lazy var captureView = RoomCaptureView(frame: .zero)
    private var running = false
    private(set) var recorder: FrameRecorder?
    /// The finished frame bundle folder (in tmp) once scanning stops, if any frame was kept.
    private(set) var framesURL: URL?
    private(set) var framesError: String?

    override func viewDidLoad() {
        super.viewDidLoad()
        captureView.frame = view.bounds
        captureView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        captureView.delegate = self
        view.addSubview(captureView)
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        guard !running else { return }
        running = true
        captureView.captureSession.run(configuration: RoomCaptureSession.Configuration())
        if let framesRoomID {
            do {
                recorder = try FrameRecorder(session: captureView.captureSession.arSession, roomID: framesRoomID)
                recorder?.start()
            } catch {
                framesError = "Frame recording could not start: \(error.localizedDescription)"
            }
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        stop()
    }

    /// Ends scanning; RoomPlan then processes the scan and calls `captureView(didPresent:error:)`.
    func stop() {
        guard running else { return }
        running = false
        captureView.captureSession.stop()
        if let recorder {
            framesURL = recorder.finish()
            if framesURL == nil {
                framesError = recorder.noDepthCount > 0 && recorder.keptCount == 0
                    ? "No RGB-D frames: this session delivered no LiDAR depth."
                    : recorder.lastError.map { "No RGB-D frames: \($0.localizedDescription)" }
            }
            self.recorder = nil
        }
    }

    /// Deletes a recorded frame bundle that will not be saved (the scan was cancelled).
    func discardFrames() {
        recorder?.discard()
        recorder = nil
        if let framesURL { try? FileManager.default.removeItem(at: framesURL) }
        framesURL = nil
    }

    func captureView(shouldPresent roomDataForProcessing: CapturedRoomData, error: Error?) -> Bool {
        true
    }

    func captureView(didPresent processedResult: CapturedRoom, error: Error?) {
        if let error {
            onError?(error)
        } else {
            onResult?(processedResult)
        }
    }
}

private struct RoomCaptureRepresentable: UIViewControllerRepresentable {
    let controller: RoomCaptureController
    let framesRoomID: String?

    func makeUIViewController(context: Context) -> RoomCaptureController {
        controller.framesRoomID = framesRoomID  // before viewDidAppear starts the session and the recorder
        return controller
    }
    func updateUIViewController(_ uiViewController: RoomCaptureController, context: Context) {}
}

struct CaptureScreen: View {
    let roomName: String
    var recordFrames = false

    @EnvironmentObject private var store: ScanStore
    @Environment(\.dismiss) private var dismiss
    @State private var controller = RoomCaptureController()
    @State private var phase = Phase.scanning
    @State private var result: CapturedRoom?
    @State private var errorText: String?
    @State private var saved = false

    enum Phase { case scanning, processing, review }

    var body: some View {
        NavigationStack {
            RoomCaptureRepresentable(controller: controller, framesRoomID: recordFrames ? roomName : nil)
                .ignoresSafeArea()
                .overlay(alignment: .bottom) {
                    if recordFrames && phase == .scanning {
                        TimelineView(.periodic(from: .now, by: 1)) { _ in
                            Text("RGB-D frames: \(controller.recorder?.keptCount ?? 0)")
                                .font(.caption.monospacedDigit())
                                .padding(.horizontal, 10).padding(.vertical, 4)
                                .background(.thinMaterial, in: Capsule())
                                .padding(.bottom, 24)
                        }
                    }
                }
                .navigationTitle(roomName)
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") { dismiss() }
                    }
                    ToolbarItem(placement: .confirmationAction) {
                        switch phase {
                        case .scanning:
                            Button("Done") {
                                phase = .processing
                                controller.stop()
                            }
                        case .processing:
                            ProgressView()
                        case .review:
                            Button("Save") { save() }.bold()
                        }
                    }
                }
                .alert("Scan problem", isPresented: Binding(get: { errorText != nil }, set: { if !$0 { errorText = nil } })) {
                    Button("OK") { if result == nil { dismiss() } }
                } message: {
                    Text(errorText ?? "")
                }
        }
        .onDisappear {
            if !saved { controller.discardFrames() }
        }
        .onAppear {
            controller.onResult = { room in
                result = room
                phase = .review
            }
            controller.onError = { error in
                errorText = error.localizedDescription
            }
        }
    }

    private func save() {
        guard let result else { return }
        do {
            let (_, usdzError) = try store.save(result, roomName: roomName, frames: controller.framesURL,
                                                framesNote: recordFrames ? controller.framesError : nil)
            if let usdzError {
                print("USDZ export failed: \(usdzError)")
            }
            saved = true
            dismiss()
        } catch {
            errorText = "Could not save: \(error.localizedDescription)"
        }
    }
}
