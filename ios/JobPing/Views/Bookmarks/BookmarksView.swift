import SwiftUI

struct BookmarksView: View {
    @Environment(AppModel.self) private var model
    @State private var openURL: URL?

    var body: some View {
        NavigationStack {
            List {
                ScreenHeader(eyebrow: nil, title: "저장한 공고",
                             subtitle: model.bookmarks.jobs.isEmpty ? nil : "\(model.bookmarks.jobs.count)개")
                    .plainRow()
                if model.bookmarks.jobs.isEmpty {
                    EmptyState(icon: "bookmark", title: "저장한 공고가 없어요",
                               message: "공고를 오른쪽으로 밀면 여기에 저장돼요")
                        .plainRow()
                } else {
                    ForEach(model.bookmarks.jobs) { job in
                        JobCard(job: job)
                            .contentShape(Rectangle())
                            .onTapGesture { openURL = URL(string: job.url) }
                            .plainRow(EdgeInsets(top: 5, leading: 16, bottom: 5, trailing: 16))
                            .swipeActions {
                                Button(role: .destructive) { model.bookmarks.toggle(job) } label: {
                                    Label("삭제", systemImage: "trash")
                                }
                            }
                    }
                }
            }
            .listStyle(.plain)
            .scrollContentBackground(.hidden)
            .background(Theme.bg)
            .toolbar(.hidden, for: .navigationBar)
            .sheet(item: $openURL) { url in SafariView(url: url).ignoresSafeArea() }
        }
    }
}
