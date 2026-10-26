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
    var jobs: [Job] = []

    // 상태
    var isLoading = false
    var lastError: String?
    var deviceToken: String?
    var pendingJobId: String?   // 푸시를 탭해서 열린 경우

    // 처음 띄울 화면. 평소엔 기본값이고, 스크린샷용 데모 모드(DemoMode.swift)만 바꾼다.
    var initialTab: MainTab = .jobs
    var initialOnboardingStep = 0
    /// 데모 모드면 서버와 통신하지 않는다 — 넣어둔 예시 데이터가 그대로 보여야 한다.
    var isDemo = false

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

    var companiesByGroup: [CompanyGroup] {
        let grouped = Dictionary(grouping: companies, by: \.group)
        return grouped.keys.sorted().map { CompanyGroup(group: $0, companies: grouped[$0] ?? []) }
    }

    func company(for key: String) -> Company? { companies.first { $0.key == key } }

    // MARK: - 서버 동기화

    func loadCompanies() async {
        guard !isDemo else { return }
        guard let api else { lastError = APIError.badURL.localizedDescription; return }
        do {
            let resp = try await api.companies()
            companies = resp.companies
            if let data = try? JSONEncoder().encode(companies) {
                defaults.set(data, forKey: "companies.cache")
            }
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshJobs() async {
        guard !isDemo else { return }
        guard let api else { lastError = APIError.badURL.localizedDescription; return }
        guard !selectedCompanies.isEmpty else { jobs = []; return }
        isLoading = true
        defer { isLoading = false }
        do {
            let resp = try await api.jobs(companies: selectedCompanies)
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
        guard !isDemo, let api else { return }
        let reg = DeviceRegistration(
            installId: InstallID.current,
            deviceToken: deviceToken,
            keywords: keywords,
            companies: selectedCompanies,
            pushEnabled: pushEnabled,
            appVersion: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        )
        do {
            _ = try await api.register(reg)
        } catch {
            lastError = error.localizedDescription
        }
    }

    func didReceiveDeviceToken(_ token: String) {
        deviceToken = token
        Task { await syncDevice() }
    }
}
