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
                    .font(.jp(16, .semibold, relativeTo: .body))
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
                .font(.jp(28, .bold, relativeTo: .title))
                .tracking(-0.5)
                .lineSpacing(2)
                .fixedSize(horizontal: false, vertical: true)
            Text(subtitle)
                .font(.jp(14, relativeTo: .subheadline))
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
        VStack(alignment: .leading, spacing: 0) {
            Spacer()
            AppIconView(size: 72)
                .overlay(RoundedRectangle(cornerRadius: 72 * 0.2237, style: .continuous)
                    .strokeBorder(.white.opacity(0.15), lineWidth: 1))
                .shadow(color: .black.opacity(0.35), radius: 18, y: 10)
            (Text("관심 회사에\n새 경력 공고가 뜨면,\n") + Text("가장 먼저.").foregroundStyle(Theme.mint))
                .font(.jp(34, .bold, relativeTo: .largeTitle))
                .tracking(-0.6)
                .lineSpacing(4)
                .foregroundStyle(.white)
                .padding(.top, 28)
            Text("삼성·SK·LG·네이버·토스 등 100여 개 회사의 채용 페이지를 30분마다 확인해서 알려드려요.")
                .font(.jp(16, relativeTo: .body))
                .lineSpacing(3)
                .foregroundStyle(.white.opacity(0.68))
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 16)
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
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 24)
        .padding(.bottom, 12)
        // 배경은 레이아웃 크기에 안 들어가게 background 로 깐다. ZStack 에 넣으면 큰 장식이
        // 화면 폭을 키워서 글자가 왼쪽으로 밀려 잘린다.
        .background {
            ZStack(alignment: .topTrailing) {
                LinearGradient(colors: [Theme.navyDeep, Theme.navy], startPoint: .topLeading, endPoint: .bottomTrailing)
                BrandMark()
                    .frame(width: 520, height: 520)
                    .opacity(0.07)
                    .offset(x: 170, y: -40)
            }
            .ignoresSafeArea()
            .allowsHitTesting(false)
        }
        .environment(\.colorScheme, .dark)
    }

    private func pill(_ text: String) -> some View {
        HStack(spacing: 5) {
            Image(systemName: "checkmark").font(.jp(11, .heavy, relativeTo: .caption2)).foregroundStyle(Theme.mint)
            Text(text).font(.jp(13, .semibold, relativeTo: .footnote)).foregroundStyle(.white.opacity(0.85))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 7)
        .background(.white.opacity(0.08), in: Capsule())
    }
}

/// 잠금화면 미리보기. 고른 회사로 만든 알림이 시계 아래 떠 있다 — "이렇게 온다"를 바로 보여준다.
private struct NotificationPreview: View {
    let company: String
    let title: String

    var body: some View {
        VStack(spacing: 0) {
            Text(RelTime.today())
                .font(.jp(15, .semibold, relativeTo: .subheadline))
                .foregroundStyle(.white.opacity(0.75))
            Text("9:41")
                .font(.jp(64, .bold, relativeTo: .largeTitle))
                .tracking(-1)
                .foregroundStyle(.white)
            VStack(spacing: 8) {
                banner(company: company, title: title, time: "지금")
                banner(company: "네이버", title: "백엔드 개발자 (검색 플랫폼)", time: "28분 전")
                    .opacity(0.8)
            }
            .padding(.top, 20)
        }
        .padding(.top, 24)
        .padding(.bottom, 14)
        .padding(.horizontal, 12)
        .frame(maxWidth: .infinity)
        .background(
            LinearGradient(colors: [Theme.navyDeep, Theme.navy], startPoint: .top, endPoint: .bottom),
            in: RoundedRectangle(cornerRadius: 30, style: .continuous)
        )
    }

    /// 잠금화면 알림 모양. 앱의 다크/라이트와 상관없이 밝은 반투명 카드다.
    private func banner(company: String, title: String, time: String) -> some View {
        HStack(alignment: .center, spacing: 10) {
            AppIconView(size: 36)
            VStack(alignment: .leading, spacing: 1) {
                HStack {
                    Text(company).font(.jp(14, .semibold, relativeTo: .subheadline)).lineLimit(1)
                    Spacer()
                    Text(time).font(.jp(12, relativeTo: .caption)).foregroundStyle(Color.black.opacity(0.45))
                }
                Text(title).font(.jp(14, relativeTo: .subheadline)).lineLimit(1)
            }
            .foregroundStyle(Color.black.opacity(0.88))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 11)
        .background(Color.white.opacity(0.9), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}
