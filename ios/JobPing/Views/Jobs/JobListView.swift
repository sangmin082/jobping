import SwiftUI

/// 구독한 계열사들의 최신 공고. 서버가 first_seen_at 내림차순으로 준다.
/// 날짜별(오늘/어제/이번 주/이전)로 끊어 보여준다 — "언제 떴나"가 이 앱의 핵심 정보다.
struct JobListView: View {
    @Environment(AppModel.self) private var model
    @State private var openURL: URL?
    @State private var filter: String?      // 키워드 칩 필터

    var body: some View {
        NavigationStack {
            List {
                ScreenHeader(eyebrow: RelTime.today(), title: "새 공고", subtitle: summary, loading: model.isLoading)
                    .plainRow()
                if !model.keywords.isEmpty {
                    keywordChips
                        .plainRow(EdgeInsets(top: 4, leading: 0, bottom: 4, trailing: 0))
                }
                if filtered.isEmpty && !model.isLoading {
                    emptyState.plainRow()
                } else {
                    ForEach(sections) { section in
                        SectionLabel(section.title, trailing: "\(section.jobs.count)")
                            .plainRow(EdgeInsets(top: 18, leading: 20, bottom: 6, trailing: 20))
                        ForEach(section.jobs) { job in
                            JobCard(job: job)
                                .contentShape(Rectangle())
                                .onTapGesture { openURL = URL(string: job.url) }
                                .plainRow(EdgeInsets(top: 5, leading: 16, bottom: 5, trailing: 16))
                                .swipeActions(edge: .leading) {
                                    Button {
                                        model.bookmarks.toggle(job)
                                    } label: {
                                        Label(model.bookmarks.contains(job) ? "저장 해제" : "저장",
                                              systemImage: model.bookmarks.contains(job) ? "bookmark.slash" : "bookmark")
                                    }
                                    .tint(Theme.navy)
                                }
                                .swipeActions(edge: .trailing) {
                                    ShareLink(item: URL(string: job.url) ?? URL(string: "https://jobping.app")!) {
                                        Label("공유", systemImage: "square.and.arrow.up")
                                    }
                                    .tint(.gray)
                                }
                        }
                    }
                    Color.clear.frame(height: 12).plainRow()
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(Theme.bg)
            .toolbar(.hidden, for: .navigationBar)
            .refreshable { await model.refreshJobs() }
            .task { await model.refreshJobs() }
            .sheet(item: $openURL) { url in
                SafariView(url: url).ignoresSafeArea()
            }
            .onChange(of: model.pendingJobId) { _, jobId in
                // 푸시를 탭해서 들어온 경우 해당 공고를 바로 연다.
                guard let jobId, let job = model.jobs.first(where: { $0.jobId == jobId }) else { return }
                openURL = URL(string: job.url)
                model.pendingJobId = nil
            }
        }
    }

    private var summary: String {
        let today = model.jobs.filter { ($0.firstSeenDate.map { Calendar.current.isDateInToday($0) }) ?? false }.count
        let base = "회사 \(model.selectedCompanies.count)곳"
        return today > 0 ? "\(base) · 오늘 새 공고 \(today)건" : base
    }

    @ViewBuilder
    private var emptyState: some View {
        if let err = model.lastError, model.jobs.isEmpty {
            EmptyState(icon: "wifi.exclamationmark", title: "공고를 불러오지 못했어요", message: err)
        } else if model.selectedCompanies.isEmpty {
            EmptyState(icon: "building.2", title: "고른 회사가 없어요",
                       message: "설정에서 관심 회사를 고르면 새 공고가 여기 모여요")
        } else if filter != nil {
            EmptyState(icon: "line.3.horizontal.decrease", title: "이 키워드로 걸린 공고가 없어요",
                       message: "다른 키워드를 눌러보거나 '전체'로 돌아가세요")
        } else {
            EmptyState(icon: "clock", title: "아직 새 공고가 없어요",
                       message: "30분마다 확인하고 있어요. 새 공고가 뜨면 알림으로 알려드릴게요")
        }
    }

    private var filtered: [Job] {
        guard let filter else { return model.jobs }
        let needle = normalize(filter)
        return model.jobs.filter { job in
            let hay = normalize(([job.title, job.department ?? ""] + (job.roles ?? [])).joined(separator: " "))
            return hay.contains(needle)
        }
    }

    private struct DaySection: Identifiable {
        let title: String
        let jobs: [Job]
        var id: String { title }
    }

    private var sections: [DaySection] {
        let cal = Calendar.current
        var buckets: [(String, [Job])] = [("오늘", []), ("어제", []), ("이번 주", []), ("이전", [])]
        for job in filtered {
            guard let d = job.firstSeenDate else { buckets[3].1.append(job); continue }
            if cal.isDateInToday(d) { buckets[0].1.append(job) }
            else if cal.isDateInYesterday(d) { buckets[1].1.append(job) }
            else if Date.now.timeIntervalSince(d) < 7 * 86_400 { buckets[2].1.append(job) }
            else { buckets[3].1.append(job) }
        }
        return buckets.filter { !$0.1.isEmpty }.map { DaySection(title: $0.0, jobs: $0.1) }
    }

    private func normalize(_ s: String) -> String {
        s.lowercased().filter { !$0.isWhitespace && $0 != "-" && $0 != "_" && $0 != "." }
    }

    private var keywordChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                SelectChip(title: "전체", isOn: filter == nil) { filter = nil }
                ForEach(model.keywords, id: \.self) { k in
                    SelectChip(title: k, isOn: filter == k) { filter = (filter == k) ? nil : k }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 2)
        }
    }
}

/// 공고 카드. 회사 타일 → 회사·시간 → 제목 → 태그 순서로 눈이 내려간다.
struct JobCard: View {
    @Environment(AppModel.self) private var model
    let job: Job

    var body: some View {
        let company = model.company(for: job.company)
        HStack(alignment: .top, spacing: 12) {
            CompanyBadge(group: company?.group ?? job.company, size: 42)
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 6) {
                    Text(company?.displayName ?? job.company)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.muted)
                        .lineLimit(1)
                    if isNew { NewBadge() }
                    Spacer(minLength: 4)
                    if model.bookmarks.contains(job) {
                        Image(systemName: "bookmark.fill")
                            .font(.caption2)
                            .foregroundStyle(Theme.accent)
                    }
                    if let d = job.firstSeenDate {
                        Text(RelTime.string(d))
                            .font(.caption)
                            .foregroundStyle(Theme.muted)
                            .monospacedDigit()
                    }
                }
                Text(job.title)
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.primary)
                    .lineLimit(2)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                if !tags.isEmpty {
                    FlowLayout(spacing: 6) {
                        ForEach(tags, id: \.self) { JobTag(text: $0) }
                    }
                    .padding(.top, 2)
                }
            }
        }
        .card(padding: 14)
    }

    private var isNew: Bool {
        guard let d = job.firstSeenDate else { return false }
        return Date.now.timeIntervalSince(d) < 86_400
    }

    /// 근무지, 고용 형태, 직무 앞 두 개. 너무 긴 건 자른다 — 태그가 제목보다 눈에 띄면 안 된다.
    private var tags: [String] {
        var out: [String] = []
        for t in [job.location, job.employmentType].compactMap({ $0 }) + (job.roles ?? []).prefix(2) {
            let t = t.trimmingCharacters(in: .whitespaces)
            guard !t.isEmpty, !out.contains(t) else { continue }
            out.append(t.count > 16 ? String(t.prefix(15)) + "…" : t)
            if out.count == 3 { break }
        }
        return out
    }
}

extension URL: Identifiable {
    public var id: String { absoluteString }
}
