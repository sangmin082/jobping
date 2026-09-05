import Foundation

/// 서버의 `GET /v1/companies` 항목. 사용자가 구독하는 단위는 그룹이 아니라 계열사다.
struct Company: Codable, Identifiable, Hashable {
    let key: String
    let displayName: String
    let source: String
    let group: String
    let lastSuccessAt: String?
    let lastFetched: Int?

    var id: String { key }

    enum CodingKeys: String, CodingKey {
        case key, source, group
        case displayName = "display_name"
        case lastSuccessAt = "last_success_at"
        case lastFetched = "last_fetched"
    }
}

/// 회사 선택 화면의 섹션 단위(삼성/SK/LG…). 튜플 대신 구조체인 이유는 ForEach 의 id 키패스 때문이다.
struct CompanyGroup: Identifiable, Hashable {
    let group: String
    let companies: [Company]
    var id: String { group }
}

struct FreeTier: Codable, Hashable {
    let maxKeywords: Int
    let maxCompanies: Int

    enum CodingKeys: String, CodingKey {
        case maxKeywords = "max_keywords"
        case maxCompanies = "max_companies"
    }
}

struct CompaniesResponse: Codable {
    let companies: [Company]
    let freeTier: FreeTier

    enum CodingKeys: String, CodingKey {
        case companies
        case freeTier = "free_tier"
    }
}

/// 서버의 공고. 본문은 없다 — 원문은 항상 회사 사이트에서 연다.
struct Job: Codable, Identifiable, Hashable {
    let company: String
    let jobId: String
    let title: String
    let url: String
    let postedAt: String?
    let firstSeenAt: String
    let location: String?
    let department: String?
    let employmentType: String?
    let roles: [String]?

    var id: String { "\(company)#\(jobId)" }

    enum CodingKeys: String, CodingKey {
        case company, title, url, location, department, roles
        case jobId = "job_id"
        case postedAt = "posted_at"
        case firstSeenAt = "first_seen_at"
        case employmentType = "employment_type"
    }

    var firstSeenDate: Date? { ISO8601.parse(firstSeenAt) }
    var postedDate: Date? { postedAt.flatMap(ISO8601.parse) }
}

struct JobsResponse: Codable {
    let jobs: [Job]
    let nextSince: String?

    enum CodingKeys: String, CodingKey {
        case jobs
        case nextSince = "next_since"
    }
}

struct DeviceRegistration: Codable {
    var installId: String
    var deviceToken: String?
    var keywords: [String]
    var companies: [String]
    var pushEnabled: Bool
    var appVersion: String

    enum CodingKeys: String, CodingKey {
        case keywords, companies
        case installId = "install_id"
        case deviceToken = "device_token"
        case pushEnabled = "push_enabled"
        case appVersion = "app_version"
    }
}

struct DeviceResponse: Codable {
    let installId: String
    let tier: String
    let pushRegistered: Bool

    enum CodingKeys: String, CodingKey {
        case tier
        case installId = "install_id"
        case pushRegistered = "push_registered"
    }
}

/// 서버가 소수점 초를 붙일 때도, 안 붙일 때도 있어 두 형식을 다 받는다.
enum ISO8601 {
    private static let withFraction: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return f
    }()
    private static let plain: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime]
        return f
    }()

    static func parse(_ s: String) -> Date? {
        withFraction.date(from: s) ?? plain.date(from: s)
    }
}
