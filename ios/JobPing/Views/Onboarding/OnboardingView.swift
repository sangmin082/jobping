import SwiftUI

/// 회사 선택 → 키워드(선택) → 푸시 허용. 푸시는 마지막이다 — 이유를 본 뒤에 물어야 허용률이 높다.
/// 전면 무료라 회사·키워드 개수 제한이 없다.
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
                   hint: model.selectedCompanies.isEmpty ? "알림 받을 회사를 하나 이상 골라주세요" : nil) {
                step = 1
            }
        }
    }

    private var keywordsStep: some View {
        @Bindable var model = model
        return VStack {
            KeywordEditor(keywords: $model.keywords)
            // 키워드는 선택이다. 비우면 고른 회사의 새 경력 공고를 전부 받는다.
            footer(enabled: true,
                   title: model.keywords.isEmpty ? "건너뛰기" : "다음",
                   hint: model.keywords.isEmpty ? "비워두면 고른 회사의 새 경력 공고를 전부 알려드려요" : nil) {
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
            Text("회사 채용 페이지를 30분마다 확인해서, 새 경력 공고가 올라오면 알림을 보냅니다. 키워드를 넣었다면 맞는 공고만 보내요. 밤 11시부터 아침 8시까지는 모아뒀다가 아침에 한 번에 드려요.")
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

    private func footer(enabled: Bool, title: String = "다음", hint: String?,
                        action: @escaping () -> Void) -> some View {
        VStack(spacing: 8) {
            if let hint {
                Text(hint).font(.footnote).foregroundStyle(.secondary)
            }
            Button(action: action) {
                Text(title).frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!enabled)
        }
        .padding()
    }
}
