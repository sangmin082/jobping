#if DEBUG
import Foundation

/// CI 스크린샷용. `-demo <화면>` 인자로 실행하면 서버 없이 예시 데이터로 그 화면을 띄운다.
/// 디버그 빌드에만 들어간다 — TestFlight(Release)에는 없다.
///
/// 화면: welcome, companies, keywords, keywords-empty, push, jobs, empty, saved, settings
enum DemoMode {
    @MainActor
    static func model(arguments: [String] = ProcessInfo.processInfo.arguments) -> AppModel? {
        guard let i = arguments.firstIndex(of: "-demo"), i + 1 < arguments.count else { return nil }
        let m = AppModel(api: nil)
        m.isDemo = true
        m.companies = companies
        m.jobs = jobs()
        m.selectedCompanies = ["sk_hynix", "samsung_ds", "naver", "kakao", "toss_bank", "daangn"]
        m.keywords = ["DevOps", "백엔드", "반도체"]
        m.pushEnabled = true
        m.lastError = nil
        m.bookmarks.replace(with: [])
        m.onboardingDone = true

        switch arguments[i + 1] {
        case "welcome":
            m.onboardingDone = false
            m.initialOnboardingStep = 0
        case "companies":
            m.onboardingDone = false
            m.initialOnboardingStep = 1
            m.selectedCompanies = ["samsung_ds", "sk_hynix", "sk_telecom", "kakao", "toss_bank"]
        case "keywords":
            m.onboardingDone = false
            m.initialOnboardingStep = 2
        case "keywords-empty":
            m.onboardingDone = false
            m.initialOnboardingStep = 2
            m.keywords = []
        case "push":
            m.onboardingDone = false
            m.initialOnboardingStep = 3
        case "empty":
            m.jobs = []
        case "saved":
            m.initialTab = .saved
            m.bookmarks.replace(with: Array(m.jobs.prefix(3)))
        case "settings":
            m.initialTab = .settings
        default:
            break
        }
        return m
    }

    private static func company(_ key: String, _ name: String, _ group: String, _ n: Int) -> Company {
        Company(key: key, displayName: name, source: group, group: group, lastSuccessAt: nil, lastFetched: n)
    }

    static let companies: [Company] = [
        company("samsung_dx", "삼성전자 DX부문", "삼성", 42), company("samsung_ds", "삼성전자 DS부문", "삼성", 37),
        company("samsung_display", "삼성디스플레이", "삼성", 12), company("samsung_sdi", "삼성SDI", "삼성", 9),
        company("samsung_sds", "삼성SDS", "삼성", 15), company("samsung_biologics", "삼성바이오로직스", "삼성", 7),
        company("sk_hynix", "SK하이닉스", "SK", 88), company("sk_telecom", "SK텔레콤", "SK", 21),
        company("sk_innovation", "SK이노베이션", "SK", 14), company("sk_planet", "SK플래닛", "SK", 6),
        company("lg_electronics", "LG전자", "LG", 51), company("lg_energy", "LG에너지솔루션", "LG", 33),
        company("lg_cns", "LG CNS", "LG", 18),
        company("naver", "네이버", "네이버", 64), company("naver_cloud", "네이버클라우드", "네이버", 22),
        company("toss_bank", "토스뱅크", "토스", 19), company("toss_payments", "토스페이먼츠", "토스", 16),
        company("line_plus", "LINE Plus", "라인", 27), company("line_ipx", "IPX", "라인", 4),
        company("kakao", "카카오", "카카오", 45), company("coupang", "쿠팡", "쿠팡", 120),
        company("daangn", "당근", "당근", 31), company("yanolja", "야놀자", "야놀자", 17),
        company("woowahan", "우아한형제들", "우아한형제들", 29), company("hyundai", "현대자동차", "현대자동차", 56),
        company("kia", "기아", "기아", 38), company("tesla_kr", "테슬라 코리아", "테슬라 코리아", 8),
    ]

    static func jobs(now: Date = .now) -> [Job] {
        let iso = ISO8601DateFormatter()
        func job(_ company: String, _ id: String, _ title: String, minutesAgo: Double,
                 location: String? = nil, type: String? = nil, roles: [String]? = nil) -> Job {
            Job(company: company, jobId: id, title: title, url: "https://example.com/\(company)/\(id)",
                postedAt: nil, firstSeenAt: iso.string(from: now.addingTimeInterval(-minutesAgo * 60)),
                location: location, department: nil, employmentType: type, roles: roles)
        }
        return [
            job("sk_hynix", "1", "DevOps Engineer (경력)", minutesAgo: 12, location: "이천", type: "정규직", roles: ["Infra", "DevOps"]),
            job("naver", "2", "백엔드 개발자 - 검색 플랫폼", minutesAgo: 95, location: "성남", roles: ["Backend", "Java"]),
            job("samsung_ds", "3", "메모리사업부 반도체 공정기술 경력사원 채용", minutesAgo: 240, location: "화성", type: "정규직", roles: ["공정기술"]),
            job("toss_bank", "4", "Server Developer (Kotlin)", minutesAgo: 410, location: "서울", roles: ["Backend"]),
            job("kakao", "5", "클라우드 인프라 엔지니어 (경력 5년 이상)", minutesAgo: 60 * 27, location: "판교", type: "정규직", roles: ["Infra"]),
            job("daangn", "6", "Site Reliability Engineer", minutesAgo: 60 * 30, location: "서울", roles: ["SRE"]),
            job("sk_hynix", "7", "반도체 설계 검증 엔지니어", minutesAgo: 60 * 52, location: "분당", type: "정규직", roles: ["Design Verification"]),
            job("naver", "8", "Data Engineer, 광고 데이터 플랫폼", minutesAgo: 60 * 75, location: "성남", roles: ["Data"]),
            job("samsung_ds", "9", "DevOps 엔지니어 (S/W 인프라)", minutesAgo: 60 * 24 * 9, location: "화성", type: "정규직"),
        ]
    }
}
#endif
