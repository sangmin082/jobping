import SwiftUI

struct RootView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        Group {
            if model.onboardingDone {
                MainTabView()
            } else {
                OnboardingView(step: model.initialOnboardingStep)
            }
        }
        .tint(Theme.accent)
        .task { await model.loadCompanies() }
    }
}

enum MainTab: Hashable {
    case jobs, saved, settings
}

struct MainTabView: View {
    @Environment(AppModel.self) private var model
    @State private var tab: MainTab = .jobs

    var body: some View {
        TabView(selection: $tab) {
            JobListView()
                .tabItem { Label("새 공고", systemImage: "briefcase") }
                .tag(MainTab.jobs)
            BookmarksView()
                .tabItem { Label("저장", systemImage: "bookmark") }
                .tag(MainTab.saved)
            SettingsView()
                .tabItem { Label("설정", systemImage: "slider.horizontal.3") }
                .tag(MainTab.settings)
        }
        .onAppear { tab = model.initialTab }
    }
}
