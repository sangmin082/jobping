import Foundation

/// 저장한 공고. 서버에 두지 않는다 — 개인 데이터를 서버에 안 모으는 게 이 앱의 설계다.
@Observable
final class Bookmarks {
    private(set) var jobs: [Job] = []
    private let key = "bookmarks.v1"

    init() { load() }

    func contains(_ job: Job) -> Bool { jobs.contains { $0.id == job.id } }

    func toggle(_ job: Job) {
        if let i = jobs.firstIndex(where: { $0.id == job.id }) {
            jobs.remove(at: i)
        } else {
            jobs.insert(job, at: 0)
        }
        save()
    }

    #if DEBUG
    /// 스크린샷용 데모 모드(DemoMode.swift)가 저장 목록을 정해진 상태로 맞출 때 쓴다.
    func replace(with jobs: [Job]) {
        self.jobs = jobs
        save()
    }
    #endif

    private func load() {
        guard let data = UserDefaults.standard.data(forKey: key),
              let decoded = try? JSONDecoder().decode([Job].self, from: data) else { return }
        jobs = decoded
    }

    private func save() {
        if let data = try? JSONEncoder().encode(jobs) {
            UserDefaults.standard.set(data, forKey: key)
        }
    }
}
