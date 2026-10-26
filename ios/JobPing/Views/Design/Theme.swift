import SwiftUI
import UIKit

/// 잡핑의 색. 앱 아이콘(남색 + 민트 핑)에서 나왔다.
/// 라이트 모드는 남색이 주인공, 다크 모드는 민트가 주인공이다 — 민트는 흰 배경에서 글씨로 못 읽는다.
enum Theme {
    static let navyDeep = Color(hex: 0x111D47)
    static let navy = Color(hex: 0x26338A)
    static let mint = Color(hex: 0x3DF5A2)

    static let bg = Color(light: 0xF4F5F9, dark: 0x080D20)
    static let card = Color(light: 0xFFFFFF, dark: 0x121936)
    static let line = Color(light: 0xE3E6EF, dark: 0x222B52)
    static let chip = Color(light: 0xECEEF5, dark: 0x1A2247)
    static let muted = Color(light: 0x6B7280, dark: 0x8E97BA)

    /// 버튼·선택 표시. 라이트는 남색, 다크는 민트.
    static let accent = Color(light: 0x26338A, dark: 0x3DF5A2)
    /// accent 위에 올리는 글자색.
    static let onAccent = Color(light: 0xFFFFFF, dark: 0x0B1440)
    /// "새 공고" 표시. 흰 배경에서도 읽히는 진한 민트.
    static let fresh = Color(light: 0x0A9E6A, dark: 0x3DF5A2)

    static let radius: CGFloat = 18
}

/// 그룹별 모노그램 타일 색과 글자. 로고 대신 쓴다 — 로고는 상표라 앱에 못 넣는다.
struct GroupStyle {
    let label: String
    let color: Color
    let text: Color

    static func of(_ group: String) -> GroupStyle {
        if let s = known[group] { return s }
        // 모르는 그룹은 이름 해시로 팔레트에서 고른다. 실행마다 같은 색이 나와야 한다.
        let palette: [UInt32] = [0x3B4CCA, 0x0F8B8D, 0xC2410C, 0x7C3AED, 0xBE185D, 0x15803D]
        let h = group.unicodeScalars.reduce(UInt32(7)) { ($0 &* 31) &+ $1.value }
        return GroupStyle(label: String(group.prefix(1)), color: Color(hex: palette[Int(h % UInt32(palette.count))]), text: .white)
    }

    private static let known: [String: GroupStyle] = [
        "삼성": .init(label: "SAMSUNG", color: Color(hex: 0x1428A0), text: .white),
        "SK": .init(label: "SK", color: Color(hex: 0xEA002C), text: .white),
        "LG": .init(label: "LG", color: Color(hex: 0xA50034), text: .white),
        "네이버": .init(label: "N", color: Color(hex: 0x03C75A), text: .white),
        "카카오": .init(label: "kakao", color: Color(hex: 0xFEE500), text: Color(hex: 0x191919)),
        "라인": .init(label: "LINE", color: Color(hex: 0x06C755), text: .white),
        "토스": .init(label: "toss", color: Color(hex: 0x0064FF), text: .white),
        "쿠팡": .init(label: "쿠팡", color: Color(hex: 0x346AFF), text: .white),
        "당근": .init(label: "당근", color: Color(hex: 0xFF6F0F), text: .white),
        "야놀자": .init(label: "야놀자", color: Color(hex: 0xFF3478), text: .white),
        "우아한형제들": .init(label: "배민", color: Color(hex: 0x2AC1BC), text: .white),
        "현대자동차": .init(label: "HYUNDAI", color: Color(hex: 0x002C5F), text: .white),
        "기아": .init(label: "KIA", color: Color(hex: 0x05141F), text: .white),
        "테슬라 코리아": .init(label: "T", color: Color(hex: 0xCC0000), text: .white),
    ]
}

extension Color {
    init(hex: UInt32) {
        self.init(uiColor: UIColor(hex: hex))
    }

    /// 라이트/다크에 따라 바뀌는 색.
    init(light: UInt32, dark: UInt32) {
        self.init(uiColor: UIColor { $0.userInterfaceStyle == .dark ? UIColor(hex: dark) : UIColor(hex: light) })
    }
}

extension UIColor {
    convenience init(hex: UInt32) {
        self.init(red: CGFloat((hex >> 16) & 0xFF) / 255,
                  green: CGFloat((hex >> 8) & 0xFF) / 255,
                  blue: CGFloat(hex & 0xFF) / 255,
                  alpha: 1)
    }
}

/// "방금", "12분 전", "3시간 전", "2일 전", "10월 3일". 기기 언어와 상관없이 한국어로 쓴다.
enum RelTime {
    static func string(_ date: Date, now: Date = .now) -> String {
        let s = now.timeIntervalSince(date)
        switch s {
        case ..<60: return "방금"
        case ..<3600: return "\(Int(s / 60))분 전"
        case ..<86_400: return "\(Int(s / 3600))시간 전"
        case ..<(7 * 86_400): return "\(Int(s / 86_400))일 전"
        default: return day.string(from: date)
        }
    }

    static func today(_ now: Date = .now) -> String { weekday.string(from: now) }

    private static let day: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        f.dateFormat = "M월 d일"
        return f
    }()

    private static let weekday: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "ko_KR")
        f.dateFormat = "M월 d일 EEEE"
        return f
    }()
}

// MARK: - 글꼴

/// Pretendard. 시스템 한글(Apple SD 산돌고딕 Neo)보다 자간·굵기 단계가 고르게 잡혀 있어
/// 한국어 UI 에서 사실상 표준이다. SIL OFL 1.1 — 라이선스는 Resources/Fonts/Pretendard-OFL.txt.
extension Font {
    /// `relativeTo` 로 Dynamic Type(글자 크기 설정)을 따라간다.
    static func jp(_ size: CGFloat, _ weight: Font.Weight = .regular,
                   relativeTo style: Font.TextStyle = .body) -> Font {
        .custom(pretendard(weight), size: size, relativeTo: style)
    }

    private static func pretendard(_ weight: Font.Weight) -> String {
        switch weight {
        case .heavy, .black: "Pretendard-ExtraBold"
        case .bold: "Pretendard-Bold"
        case .semibold: "Pretendard-SemiBold"
        case .medium: "Pretendard-Medium"
        default: "Pretendard-Regular"
        }
    }
}
