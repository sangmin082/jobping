import SwiftUI

/// 회사 선택 → 키워드 → 푸시 허용. 푸시는 마지막이다 — 이유를 본 뒤에 물어야 허용률이 높다.
struct OnboardingView: View {
    @Environment(AppModel.self) private var model
    @State private var step = 0

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                ProgressView(value: Double(step + 1), total: 3)
                    .padding(.horizontal)
                switch step {
                case 0: companiesStep
                case 1: keywordsStep
                default: pushStep
                }
            }
            .navigationTitle(["관심 회사", "키워드", "알림"][step])
            .navigationBarTitleDisplayMode(.large)
        }
    }

    private var companiesStep: some View {
        @Bindable var model = model
        return VStack {
            if model.companies.isEmpty {
                ContentUnavailableView("회사 목록을 불러오는 중", systemImage: "building.2",
                                       description: Text(model.lastError ?? "잠시만요"))
            } else {
                CompanyPicker(selected: $model.selectedCompanies)
            }
            footer(enabled: !model.selectedCompanies.isEmpty,
                   hint: model.isPro ? nil : "무료는 \(model.freeTier.maxCompanies)곳까지 알림이 갑니다") {
                step = 1
            }
        }
    }

    private var keywordsStep: some View {
        @Bindable var model = model
        return VStack {
            KeywordEditor(keywords: $model.keywords)
            footer(enabled: !model.keywords.isEmpty,
                   hint: model.isPro ? nil : "무료는 첫 \(model.freeTier.maxKeywords)개 키워드만 알림이 갑니다") {
                step = 2
            }
        }
    }

    private var pushStep: some View {
        VStack(spacing: 24) {
            Spacer()
            Image(systemName: "bell.badge")
                .font(.system(size: 64))
                .foregroundStyle(.tint)
            Text("새 공고가 뜨면 바로 알려드릴게요")
                .font(.title2.bold())
            Text("회사 채용 페이지를 30분마다 확인해서, 고른 키워드에 맞는 경력 공고가 올라오면 알림을 보냅니다. 밤 11시부터 아침 8시까지는 모아뒀다가 아침에 한 번에 드려요.")
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 32)
            Spacer()
            Button {
                Task {
                    let granted = await PushPermission.request()
                    model.pushEnabled = granted
                    finish()
                }
            } label: {
                Text("알림 허용하기").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .padding(.horizontal)
            Button("나중에") {
                model.pushEnabled = false
                finish()
            }
            .padding(.bottom)
        }
    }

    private func finish() {
        model.onboardingDone = true
        Task {
            await model.syncDevice()
            await model.refreshJobs()
        }
    }

    private func footer(enabled: Bool, hint: String?, action: @escaping () -> Void) -> some View {
        VStack(spacing: 8) {
            if let hint {
                Text(hint).font(.footnote).foregroundStyle(.secondary)
            }
            Button(action: action) {
                Text("다음").frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!enabled)
        }
        .padding()
    }
}
