import RoomPlan
import SwiftUI

/// Hosts Apple's `RoomCaptureView`: live coaching while scanning, then the processed 3D model.
final class RoomCaptureController: UIViewController, RoomCaptureViewDelegate {
    var onResult: ((CapturedRoom) -> Void)?
    var onError: ((Error) -> Void)?

    private lazy var captureView = RoomCaptureView(frame: .zero)
    private var running = false

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

    func makeUIViewController(context: Context) -> RoomCaptureController { controller }
    func updateUIViewController(_ uiViewController: RoomCaptureController, context: Context) {}
}

struct CaptureScreen: View {
    let roomName: String

    @EnvironmentObject private var store: ScanStore
    @Environment(\.dismiss) private var dismiss
    @State private var controller = RoomCaptureController()
    @State private var phase = Phase.scanning
    @State private var result: CapturedRoom?
    @State private var errorText: String?

    enum Phase { case scanning, processing, review }

    var body: some View {
        NavigationStack {
            RoomCaptureRepresentable(controller: controller)
                .ignoresSafeArea()
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
            let (_, usdzError) = try store.save(result, roomName: roomName)
            if let usdzError {
                print("USDZ export failed: \(usdzError)")
            }
            dismiss()
        } catch {
            errorText = "Could not save: \(error.localizedDescription)"
        }
    }
}
