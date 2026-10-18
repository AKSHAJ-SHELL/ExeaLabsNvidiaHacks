import SwiftUI

@main
struct ArrivalCaptureApp: App {
    @StateObject private var store = ScanStore()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(store)
        }
    }
}
