import SwiftUI

/// 구독한 계열사들의 최신 공고. 서버가 first_seen_at 내림차순으로 준다.
struct JobListView: View {
    @Environment(AppModel.self) private var model
    @State private var openURL: URL?
    @State private var filter: String?      // 키워드 칩 필터

    var body: some View {
        NavigationStack {
            Group {
                if model.jobs.isEmpty && !model.isLoading {
                    ContentUnavailableView(
                        model.effectiveCompanies.isEmpty ? "구독한 회사가 없어요" : "아직 공고가 없어요",
                        systemImage: "tray",
                        description: Text(model.lastError ?? "당겨서 새로고침")
                    )
                } else {
                    List(filtered) { job in
                        JobRow(job: job)
                            .contentShape(Rectangle())
                            .onTapGesture { openURL = URL(string: job.url) }
                            .swipeActions(edge: .leading) {
                                Button {
                                    model.bookmarks.toggle(job)
                                } label: {
                                    Label(model.bookmarks.contains(job) ? "저장 해제" : "저장",
                                          systemImage: model.bookmarks.contains(job) ? "bookmark.slash" : "bookmark")
                                }
                                .tint(.orange)
                            }
                            .swipeActions(edge: .trailing) {
                                ShareLink(item: URL(string: job.url) ?? URL(string: "https://jobping.app")!) {
                                    Label("공유", systemImage: "square.and.arrow.up")
                                }
                                .tint(.blue)
                            }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("공고")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    if model.isLoading { ProgressView() }
                }
            }
            .safeAreaInset(edge: .top) { keywordChips }
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

    private var filtered: [Job] {
        guard let filter else { return model.jobs }
        let needle = normalize(filter)
        return model.jobs.filter { job in
            let hay = normalize(([job.title, job.department ?? ""] + (job.roles ?? [])).joined(separator: " "))
            return hay.contains(needle)
        }
    }

    private func normalize(_ s: String) -> String {
        s.lowercased().filter { !$0.isWhitespace && $0 != "-" && $0 != "_" && $0 != "." }
    }

    @ViewBuilder
    private var keywordChips: some View {
        if !model.keywords.isEmpty {
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 8) {
                    chip("전체", selected: filter == nil) { filter = nil }
                    ForEach(model.keywords, id: \.self) { k in
                        chip(k, selected: filter == k) { filter = (filter == k) ? nil : k }
                    }
                }
                .padding(.horizontal).padding(.vertical, 6)
            }
            .background(.bar)
        }
    }

    private func chip(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.subheadline.weight(selected ? .semibold : .regular))
                .padding(.horizontal, 12).padding(.vertical, 6)
                .background(selected ? Color.accentColor.opacity(0.18) : Color.secondary.opacity(0.12), in: Capsule())
        }
        .buttonStyle(.plain)
    }
}

struct JobRow: View {
    @Environment(AppModel.self) private var model
    let job: Job

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack(alignment: .firstTextBaseline) {
                Text(model.company(for: job.company)?.displayName ?? job.company)
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.tint)
                Spacer()
                if let d = job.firstSeenDate {
                    Text(d, style: .relative).font(.caption2).foregroundStyle(.secondary)
                }
                if model.bookmarks.contains(job) {
                    Image(systemName: "bookmark.fill").font(.caption2).foregroundStyle(.orange)
                }
            }
            Text(job.title).font(.body)
            HStack(spacing: 6) {
                ForEach([job.location, job.employmentType].compactMap { $0 }, id: \.self) { t in
                    Text(t).font(.caption).foregroundStyle(.secondary)
                }
            }
            if let roles = job.roles, !roles.isEmpty {
                Text(roles.prefix(3).joined(separator: " · "))
                    .font(.caption2).foregroundStyle(.tertiary).lineLimit(1)
            }
        }
        .padding(.vertical, 4)
    }
}

extension URL: Identifiable {
    public var id: String { absoluteString }
}
