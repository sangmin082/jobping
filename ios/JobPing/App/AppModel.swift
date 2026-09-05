import Foundation
import SwiftUI

/// 앱의 단일 상태. 구독 설정은 로컬에 저장하고 서버에 동기화한다.
/// 서버가 원본인 건 공고 목록뿐이다 — 설정은 서버가 죽어도 앱이 알고 있어야 한다.
@Observable
@MainActor
final class AppModel {
    // 구독 설정 (로컬 저장)
    var selectedCompanies: [String] { didSet { persist() } }
    var keywords: [String] { didSet { persist() } }
    var pushEnabled: Bool { didSet { persist() } }
    var onboardingDone: Bool { didSet { persist() } }

    // 서버에서 받은 것
    var companies: [Company] = []
    var freeTier = FreeTier(maxKeywords: 1, maxCompanies: 3)
    var jobs: [Job] = []
    var tier: String = "free"

    // 상태
    var isLoading = false
    var lastError: String?
    var deviceToken: String?
    var pendingJobId: String?   // 푸시를 탭해서 열린 경우

    let api: APIClient?
    let bookmarks = Bookmarks()

    private let defaults = UserDefaults.standard

    init(api: APIClient? = APIClient()) {
        self.api = api
        selectedCompanies = defaults.stringArray(forKey: "companies") ?? []
        keywords = defaults.stringArray(forKey: "keywords") ?? []
        pushEnabled = defaults.object(forKey: "pushEnabled") as? Bool ?? true
        onboardingDone = defaults.bool(forKey: "onboardingDone")
        if let data = defaults.data(forKey: "jobs.cache"),
           let cached = try? JSONDecoder().decode([Job].self, from: data) {
            jobs = cached
        }
        if let data = defaults.data(forKey: "companies.cache"),
           let cached = try? JSONDecoder().decode([Company].self, from: data) {
            companies = cached
        }
    }

    private func persist() {
        defaults.set(selectedCompanies, forKey: "companies")
        defaults.set(keywords, forKey: "keywords")
        defaults.set(pushEnabled, forKey: "pushEnabled")
        defaults.set(onboardingDone, forKey: "onboardingDone")
    }

    var isPro: Bool { tier == "pro" }

    /// 무료 티어는 서버도 자르지만, 앱이 먼저 보여줘야 사용자가 왜 안 오는지 안다.
    var effectiveKeywords: [String] { isPro ? keywords : Array(keywords.prefix(freeTier.maxKeywords)) }
    var effectiveCompanies: [String] { isPro ? selectedCompanies : Array(selectedCompanies.prefix(freeTier.maxCompanies)) }

    var companiesByGroup: [CompanyGroup] {
        let grouped = Dictionary(grouping: companies, by: \.group)
        return grouped.keys.sorted().map { CompanyGroup(group: $0, companies: grouped[$0] ?? []) }
    }

    func company(for key: String) -> Company? { companies.first { $0.key == key } }

    // MARK: - 서버 동기화

    func loadCompanies() async {
        guard let api else { lastError = APIError.badURL.localizedDescription; return }
        do {
            let resp = try await api.companies()
            companies = resp.companies
            freeTier = resp.freeTier
            if let data = try? JSONEncoder().encode(companies) {
                defaults.set(data, forKey: "companies.cache")
            }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshJobs() async {
        guard let api else { lastError = APIError.badURL.localizedDescription; return }
        guard !effectiveCompanies.isEmpty else { jobs = []; return }
        isLoading = true
        defer { isLoading = false }
        do {
            let resp = try await api.jobs(companies: effectiveCompanies)
            jobs = resp.jobs
            lastError = nil
            if let data = try? JSONEncoder().encode(jobs) {
                defaults.set(data, forKey: "jobs.cache")
            }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func syncDevice() async {
        guard let api else { return }
        let reg = DeviceRegistration(
            installId: InstallID.current,
            deviceToken: deviceToken,
            keywords: keywords,
            companies: selectedCompanies,
            pushEnabled: pushEnabled,
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        )
        do {
            let resp = try await api.register(reg)
            tier = resp.tier
        } catch {
            lastError = error.localizedDescription
        }
    }

    func didReceiveDeviceToken(_ token: String) {
        deviceToken = token
        Task { await syncDevice() }
    }
}
