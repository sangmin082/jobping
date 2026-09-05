import SwiftUI

struct BookmarksView: View {
    @Environment(AppModel.self) private var model
    @State private var openURL: URL?

    var body: some View {
        NavigationStack {
            Group {
                if model.bookmarks.jobs.isEmpty {
                    ContentUnavailableView("저장한 공고가 없어요", systemImage: "bookmark",
                                           description: Text("공고를 왼쪽으로 밀어 저장할 수 있어요"))
                } else {
                    List(model.bookmarks.jobs) { job in
                        JobRow(job: job)
                            .contentShape(Rectangle())
                            .onTapGesture { openURL = URL(string: job.url) }
                            .swipeActions {
                                Button(role: .destructive) { model.bookmarks.toggle(job) } label: {
                                    Label("삭제", systemImage: "trash")
                                }
                            }
                    }
                    .listStyle(.plain)
                }
            }
            .navigationTitle("저장")
            .sheet(item: $openURL) { url in SafariView(url: url).ignoresSafeArea() }
        }
    }
}
