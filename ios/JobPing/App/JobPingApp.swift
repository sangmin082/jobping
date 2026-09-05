import SwiftUI
import UserNotifications

@main
struct JobPingApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(model)
                .onAppear { appDelegate.model = model }
        }
    }
}

/// 푸시 등록과 알림 탭 처리. SwiftUI 만으로는 APNs 토큰 콜백을 받을 수 없어 delegate 가 필요하다.
final class AppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    var model: AppModel?

    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        // 이미 허용된 상태면 매 실행마다 토큰을 다시 받아 서버와 맞춘다. 토큰은 바뀔 수 있다.
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            if settings.authorizationStatus == .authorized {
                DispatchQueue.main.async { application.registerForRemoteNotifications() }
            }
        }
        return true
    }

    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let hex = deviceToken.map { String(format: "%02x", $0) }.joined()
        Task { @MainActor in model?.didReceiveDeviceToken(hex) }
    }

    func application(_ application: UIApplication,
                     didFailToRegisterForRemoteNotificationsWithError error: Error) {
        Task { @MainActor in model?.lastError = "푸시 등록 실패: \(error.localizedDescription)" }
    }

    // 앱이 켜져 있을 때도 배너를 보여준다.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                willPresent notification: UNNotification) async -> UNNotificationPresentationOptions {
        [.banner, .sound, .list]
    }

    // 알림을 탭하면 해당 공고로 간다. 서버가 payload 에 job_id 를 넣어 보낸다.
    func userNotificationCenter(_ center: UNUserNotificationCenter,
                                didReceive response: UNNotificationResponse) async {
        let info = response.notification.request.content.userInfo
        if let jobId = info["job_id"] as? String {
            await MainActor.run { model?.pendingJobId = jobId }
        }
    }
}

enum PushPermission {
    /// 온보딩 마지막에, 왜 필요한지 설명한 뒤에 부른다. 첫 화면에서 바로 물으면 거부율이 크게 오른다.
    @MainActor
    static func request() async -> Bool {
        let center = UNUserNotificationCenter.current()
        let granted = (try? await center.requestAuthorization(options: [.alert, .sound, .badge])) ?? false
        if granted {
            UIApplication.shared.registerForRemoteNotifications()
        }
        return granted
    }
}
