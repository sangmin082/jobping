import Foundation
import Security

/// 로그인이 없는 앱의 유일한 식별자. Keychain 에 두어 재설치·복원 후에도 유지된다.
/// APNs 토큰을 식별자로 쓰면 토큰이 바뀔 때 구독 정보(와 나중의 결제 권한)가 날아간다.
enum InstallID {
    private static let service = "app.jobping.install-id"
    private static let account = "install-id"

    static var current: String {
        if let existing = read() { return existing }
        let fresh = UUID().uuidString.lowercased()
        write(fresh)
        return fresh
    }

    private static func read() -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data, let s = String(data: data, encoding: .utf8) else { return nil }
        return s
    }

    private static func write(_ value: String) {
        let attrs: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: Data(value.utf8),
            // 기기 잠금 해제 후엔 백그라운드에서도 읽을 수 있어야 푸시 처리 때 쓸 수 있다.
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly,
        ]
        SecItemDelete(attrs as CFDictionary)
        SecItemAdd(attrs as CFDictionary, nil)
    }
}
