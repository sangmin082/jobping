import SwiftUI

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Group {
            if model.onboardingDone {
                MainTabView()
            } else {
                OnboardingView()
            }
        }
        .task { await model.loadCompanies() }
    }
}

struct MainTabView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        TabView {
            JobListView()
                .tabItem { Label("공고", systemImage: "list.bullet.rectangle") }
            BookmarksView()
                .tabItem { Label("저장", systemImage: "bookmark") }
            SettingsView()
                .tabItem { Label("설정", systemImage: "gearshape") }
        }
    }
}
