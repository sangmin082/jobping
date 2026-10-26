import SwiftUI

/// 소개 → 회사 → 키워드(선택) → 푸시 허용. 푸시는 마지막이다 — 이유를 본 뒤에 물어야 허용률이 높다.
/// 전면 무료라 회사·키워드 개수 제한이 없다.
struct OnboardingView: View {
    @Environment(AppModel.self) private var model
    @State private var step: Int

    init(step: Int = 0) {
        _step = State(initialValue: step)
    }

    var body: some View {
        ZStack {
            if step == 0 {
                WelcomeStep { step = 1 }
                    .transition(.opacity)
            } else {
                VStack(spacing: 0) {
                    topBar
                    Group {
                        switch step {
                        case 1: companiesStep
                        case 2: keywordsStep
                        default: pushStep
                        }
                    }
                    .frame(maxHeight: .infinity)
                }
                .background(Theme.bg.ignoresSafeArea())
                .transition(.opacity)
            }
        }
        .animation(.easeInOut(duration: 0.25), value: step)
    }

    // MARK: - 단계

    private var companiesStep: some View {
        @Bindable var model = model
        return VStack(spacing: 0) {
            StepTitle(title: "어느 회사 소식을\n받아볼까요?", subtitle: "여러 곳 골라도 돼요. 나중에 설정에서 바꿀 수 있어요.")
            CompanyPicker(selected: $model.selectedCompanies)
            BottomBar {
                Button(model.selectedCompanies.isEmpty ? "회사를 골라주세요" : "\(model.selectedCompanies.count)곳 선택 · 다음") {
                    step = 2
                }
                .buttonStyle(PrimaryButtonStyle())
                .disabled(model.selectedCompanies.isEmpty)
            }
        }
    }

    private var keywordsStep: some View {
        @Bindable var model = model
        return VStack(spacing: 0) {
            StepTitle(title: "관심 직무가 있나요?",
                      subtitle: "선택이에요. 비워두면 고른 회사의 새 경력 공고를 전부 알려드려요.")
            KeywordEditor(keywords: $model.keywords)
            BottomBar {
                // 키워드는 선택이다. 비우면 고른 회사의 새 경력 공고를 전부 받는다.
                Button(model.keywords.isEmpty ? "건너뛰고 전체 공고 받기" : "다음") { step = 3 }
                    .buttonStyle(PrimaryButtonStyle())
            }
        }
    }

    private var pushStep: some View {
        VStack(spacing: 0) {
            StepTitle(title: "새 공고가 뜨면\n바로 알려드릴게요",
                      subtitle: "30분마다 채용 페이지를 확인해요. 밤 11시~아침 8시엔 모아뒀다가 아침에 한 번에 보내요.")
            Spacer()
            NotificationPreview(company: previewCompany, title: previewTitle)
                .padding(.horizontal, 20)
            Spacer()
            BottomBar {
                Button("알림 받기") {
                    Task {
                        let granted = await PushPermission.request()
                        model.pushEnabled = granted
                        finish()
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                Button("나중에") {
                    model.pushEnabled = false
                    finish()
                }
                .buttonStyle(QuietButtonStyle())
            }
        }
    }

    /// 미리보기 알림은 고른 회사·키워드로 만든다 — "내 알림"처럼 보여야 허용한다.
    private var previewCompany: String {
        model.selectedCompanies.first.flatMap { model.company(for: $0)?.displayName } ?? "SK하이닉스"
    }

    private var previewTitle: String {
        if let k = model.keywords.first { return "\(k) 엔지니어 (경력)" }
        return "DevOps Engineer (경력)"
    }

    private var topBar: some View {
        HStack(spacing: 12) {
            Button {
                step -= 1
            } label: {
                Image(systemName: "chevron.left")
                    .font(.body.weight(.semibold))
                    .foregroundStyle(.primary)
                    .frame(width: 40, height: 40)
            }
            .buttonStyle(.plain)
            .accessibilityLabel("뒤로")
            HStack(spacing: 6) {
                ForEach(1...3, id: \.self) { i in
                    Capsule()
                        .fill(i <= step ? Theme.accent : Theme.line)
                        .frame(height: 4)
                }
            }
            Color.clear.frame(width: 40, height: 40)
        }
        .padding(.horizontal, 8)
    }

    private func finish() {
        model.onboardingDone = true
        Task {
            await model.syncDevice()
            await model.refreshJobs()
        }
    }
}

/// 각 단계 머리말.
private struct StepTitle: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.system(size: 28, weight: .bold))
                .fixedSize(horizontal: false, vertical: true)
            Text(subtitle)
                .font(.subheadline)
                .foregroundStyle(Theme.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 20)
        .padding(.top, 8)
        .padding(.bottom, 16)
    }
}

/// 첫 화면. 남색 전면 + 아이콘 + 한 문장.
private struct WelcomeStep: View {
    let next: () -> Void

    var body: some View {
        ZStack {
            LinearGradient(colors: [Theme.navyDeep, Theme.navy], startPoint: .topLeading, endPoint: .bottomTrailing)
                .ignoresSafeArea()
            // 아이콘의 핑 물결을 배경에 크게 깐다. 장식이라 아주 옅게.
            BrandMark()
                .frame(width: 560, height: 560)
                .opacity(0.06)
                .offset(x: 150, y: -250)
                .allowsHitTesting(false)

            VStack(alignment: .leading, spacing: 0) {
                Spacer()
                AppIconView(size: 76)
                    .overlay(RoundedRectangle(cornerRadius: 76 * 0.2237, style: .continuous)
                        .strokeBorder(.white.opacity(0.15), lineWidth: 1))
                    .shadow(color: .black.opacity(0.3), radius: 16, y: 8)
                Text("관심 회사에\n새 경력 공고가 뜨면,\n가장 먼저.")
                    .font(.system(size: 36, weight: .bold))
                    .foregroundStyle(.white)
                    .lineSpacing(2)
                    .padding(.top, 28)
                Text("삼성·SK·LG·네이버·토스 등 100여 개 회사의 채용 페이지를 30분마다 확인해서 알려드려요.")
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.7))
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.top, 14)
                Spacer()
                HStack(spacing: 8) {
                    pill("완전 무료")
                    pill("가입 없음")
                    pill("광고 없음")
                }
                Button("시작하기", action: next)
                    .buttonStyle(PrimaryButtonStyle(fill: Theme.mint, text: Theme.navyDeep))
                    .padding(.top, 20)
            }
            .padding(.horizontal, 24)
            .padding(.bottom, 12)
        }
        .environment(\.colorScheme, .dark)
    }

    private func pill(_ text: String) -> some View {
        HStack(spacing: 5) {
            Image(systemName: "checkmark").font(.caption2.weight(.heavy)).foregroundStyle(Theme.mint)
            Text(text).font(.footnote.weight(.semibold)).foregroundStyle(.white.opacity(0.85))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(.white.opacity(0.08), in: Capsule())
    }
}

/// 잠금화면 알림처럼 생긴 미리보기. 뒤에 한 장 더 겹쳐 "계속 온다"는 느낌을 준다.
private struct NotificationPreview: View {
    let company: String
    let title: String

    var body: some View {
        ZStack(alignment: .top) {
            banner(company: "네이버", title: "백엔드 개발자 (검색 플랫폼)", time: "28분 전")
                .scaleEffect(0.92)
                .offset(y: 22)
                .opacity(0.55)
            banner(company: company, title: title, time: "지금")
        }
        .padding(.bottom, 22)
    }

    private func banner(company: String, title: String, time: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            AppIconView(size: 40)
            VStack(alignment: .leading, spacing: 2) {
                HStack {
                    Text(company).font(.subheadline.weight(.semibold)).lineLimit(1)
                    Spacer()
                    Text(time).font(.caption).foregroundStyle(Theme.muted)
                }
                Text(title).font(.subheadline).lineLimit(2)
            }
        }
        .padding(14)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Theme.line, lineWidth: 1))
        .shadow(color: .black.opacity(0.08), radius: 20, y: 10)
    }
}
