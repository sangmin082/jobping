import SwiftUI

// MARK: - 버튼

/// 화면 하단의 큰 버튼. 색은 기본이 accent, 온보딩 첫 화면처럼 남색 배경 위에선 민트를 넘긴다.
struct PrimaryButtonStyle: ButtonStyle {
    var fill: Color = Theme.accent
    var text: Color = Theme.onAccent

    func makeBody(configuration: Configuration) -> some View {
        Body(configuration: configuration, fill: fill, text: text)
    }

    private struct Body: View {
        let configuration: Configuration
        let fill: Color
        let text: Color
        @Environment(\.isEnabled) private var enabled

        var body: some View {
            configuration.label
                .font(.body.weight(.semibold))
                .frame(maxWidth: .infinity, minHeight: 54)
                .foregroundStyle(enabled ? text : Theme.muted)
                .background(enabled ? fill : Theme.chip,
                            in: RoundedRectangle(cornerRadius: 16, style: .continuous))
                .scaleEffect(configuration.isPressed ? 0.98 : 1)
                .opacity(configuration.isPressed ? 0.88 : 1)
                .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
        }
    }
}

/// 글자만 있는 보조 버튼 ("나중에").
struct QuietButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.subheadline.weight(.semibold))
            .foregroundStyle(Theme.muted)
            .frame(maxWidth: .infinity, minHeight: 44)
            .opacity(configuration.isPressed ? 0.5 : 1)
    }
}

// MARK: - 카드·행

extension View {
    /// 흰(다크: 남색) 카드. 그림자 대신 얇은 테두리 — 리스트가 길어도 지저분하지 않다.
    func card(padding: CGFloat = 16, radius: CGFloat = Theme.radius) -> some View {
        self.padding(padding)
            .background(Theme.card, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: radius, style: .continuous)
                .strokeBorder(Theme.line, lineWidth: 1))
    }

    /// List 안에서 기본 배경·구분선을 지우고 카드만 남긴다.
    func plainRow(_ insets: EdgeInsets = EdgeInsets(top: 0, leading: 16, bottom: 0, trailing: 16)) -> some View {
        self.listRowInsets(insets)
            .listRowSeparator(.hidden)
            .listRowBackground(Color.clear)
    }
}

/// 섹션 제목. 작고 진하게 — 큰 제목과 카드 사이의 리듬을 만든다.
struct SectionLabel: View {
    let title: String
    var trailing: String?

    init(_ title: String, trailing: String? = nil) {
        self.title = title
        self.trailing = trailing
    }

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(title)
                .font(.subheadline.weight(.bold))
                .foregroundStyle(.primary)
            if let trailing {
                Text(trailing)
                    .font(.subheadline.weight(.semibold))
                    .foregroundStyle(Theme.muted)
                    .monospacedDigit()
            }
            Spacer()
        }
    }
}

/// 화면 맨 위 큰 제목. 내비게이션 바 대신 쓴다 — 기본 큰 제목보다 위아래 여백을 우리가 정한다.
struct ScreenHeader: View {
    let eyebrow: String?
    let title: String
    let subtitle: String?
    var loading = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                if let eyebrow {
                    Text(eyebrow)
                        .font(.footnote.weight(.semibold))
                        .foregroundStyle(Theme.muted)
                }
                Spacer()
                if loading { ProgressView().controlSize(.small) }
            }
            Text(title)
                .font(.system(size: 32, weight: .bold))
                .foregroundStyle(.primary)
            if let subtitle {
                Text(subtitle)
                    .font(.subheadline)
                    .foregroundStyle(Theme.muted)
                    .padding(.top, 2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.top, 12)
        .padding(.bottom, 8)
    }
}

/// 빈 화면. 회색 큰 아이콘 대신 작은 원 안의 아이콘 + 한 줄 설명.
struct EmptyState: View {
    let icon: String
    let title: String
    let message: String

    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: icon)
                .font(.title2.weight(.semibold))
                .foregroundStyle(Theme.accent)
                .frame(width: 64, height: 64)
                .background(Theme.chip, in: Circle())
            Text(title)
                .font(.headline)
            Text(message)
                .font(.subheadline)
                .foregroundStyle(Theme.muted)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 56)
        .padding(.horizontal, 24)
    }
}

// MARK: - 회사·태그

/// 회사 그룹 모노그램 타일 (삼성 = 파란 SAMSUNG, SK = 빨간 SK …).
struct CompanyBadge: View {
    let group: String
    var size: CGFloat = 40

    var body: some View {
        let s = GroupStyle.of(group)
        Text(s.label)
            .font(.system(size: size * 0.3, weight: .heavy))
            .minimumScaleFactor(0.4)
            .lineLimit(1)
            .padding(.horizontal, size * 0.1)
            .foregroundStyle(s.text)
            .frame(width: size, height: size)
            .background(s.color, in: RoundedRectangle(cornerRadius: size * 0.28, style: .continuous))
            .accessibilityHidden(true)
    }
}

/// 공고 카드의 작은 회색 태그 (근무지, 직무).
struct JobTag: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.caption.weight(.medium))
            .foregroundStyle(Theme.muted)
            .lineLimit(1)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(Theme.chip, in: RoundedRectangle(cornerRadius: 6, style: .continuous))
    }
}

/// 24시간 안에 처음 본 공고 표시.
struct NewBadge: View {
    var body: some View {
        Text("NEW")
            .font(.system(size: 10, weight: .heavy))
            .tracking(0.5)
            .foregroundStyle(Theme.fresh)
            .padding(.horizontal, 5)
            .padding(.vertical, 2)
            .overlay(Capsule().strokeBorder(Theme.fresh, lineWidth: 1.2))
    }
}

/// 켜고 끄는 칩. 회사·키워드 필터에 쓴다.
struct SelectChip: View {
    let title: String
    let isOn: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 5) {
                if isOn {
                    Image(systemName: "checkmark").font(.caption.weight(.bold))
                }
                Text(title).lineLimit(1)
            }
            .font(.subheadline.weight(isOn ? .semibold : .medium))
            .foregroundStyle(isOn ? Theme.onAccent : Color.primary)
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(isOn ? Theme.accent : Theme.card, in: Capsule())
            .overlay(Capsule().strokeBorder(isOn ? Color.clear : Theme.line, lineWidth: 1))
            .contentShape(Capsule())
        }
        .buttonStyle(.plain)
        .animation(.easeOut(duration: 0.12), value: isOn)
    }
}

/// 둥근 검색창. `.searchable` 은 내비게이션 바가 있어야 해서 직접 만든다.
struct SearchField: View {
    @Binding var text: String
    let prompt: String

    var body: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass").foregroundStyle(Theme.muted)
            TextField(prompt, text: $text)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
            if !text.isEmpty {
                Button { text = "" } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(Theme.muted)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(.horizontal, 14)
        .frame(height: 46)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Theme.line, lineWidth: 1))
    }
}

// MARK: - 브랜드

/// 앱 아이콘의 서류가방 + 핑. 1024 격자 좌표는 ios/design/make_icon.py 와 같다.
/// 핑 둘레·이음선은 지워서(destinationOut) 뒤 배경이 비치게 한다.
struct BrandMark: View {
    var body: some View {
        Canvas { ctx, size in
            let k = min(size.width, size.height) / 1024
            func r(_ x: CGFloat, _ y: CGFloat, _ w: CGFloat, _ h: CGFloat) -> CGRect {
                CGRect(x: x * k, y: y * k, width: w * k, height: h * k)
            }
            let dot = CGPoint(x: 738 * k, y: 366 * k)

            ctx.drawLayer { layer in
                layer.stroke(Path(roundedRect: r(378, 328, 216, 140), cornerRadius: 44 * k, style: .continuous),
                             with: .color(.white), lineWidth: 44 * k)
                layer.fill(Path(roundedRect: r(216, 432, 540, 370), cornerRadius: 78 * k, style: .continuous),
                           with: .color(.white))
                layer.blendMode = .destinationOut
                layer.fill(Path(ellipseIn: CGRect(x: dot.x - 108 * k, y: dot.y - 108 * k, width: 216 * k, height: 216 * k)),
                           with: .color(.black))
                layer.fill(Path(r(216, 588, 540, 20)), with: .color(.black))
                layer.fill(Path(roundedRect: r(429, 553, 114, 90), cornerRadius: 28 * k, style: .continuous),
                           with: .color(.black))
            }
            ctx.fill(Path(roundedRect: r(447, 571, 78, 54), cornerRadius: 14 * k, style: .continuous),
                     with: .color(.white))
            for (radius, opacity): (CGFloat, Double) in [(148, 0.95), (204, 0.5)] {
                var arc = Path()
                arc.addArc(center: dot, radius: radius * k, startAngle: .degrees(-80), endAngle: .degrees(8),
                           clockwise: false)
                ctx.stroke(arc, with: .color(Theme.mint.opacity(opacity)),
                           style: StrokeStyle(lineWidth: 28 * k, lineCap: .round))
            }
            ctx.fill(Path(ellipseIn: CGRect(x: dot.x - 82 * k, y: dot.y - 82 * k, width: 164 * k, height: 164 * k)),
                     with: .color(Theme.mint))
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityHidden(true)
    }
}

/// 앱 아이콘과 같은 모양 (남색 타일 + 마크).
struct AppIconView: View {
    var size: CGFloat = 64

    var body: some View {
        BrandMark()
            .frame(width: size, height: size)
            .background(
                LinearGradient(colors: [Theme.navyDeep, Theme.navy], startPoint: .topLeading, endPoint: .bottomTrailing)
            )
            .clipShape(RoundedRectangle(cornerRadius: size * 0.2237, style: .continuous))
    }
}

// MARK: - 배치

/// 칩을 줄바꿈해 배치한다.
struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        var x: CGFloat = 0, y: CGFloat = 0, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > width, x > 0 { x = 0; y += rowH + spacing; rowH = 0 }
            x += s.width + spacing
            rowH = max(rowH, s.height)
        }
        return CGSize(width: width, height: y + rowH)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, rowH: CGFloat = 0
        for v in subviews {
            let s = v.sizeThatFits(.unspecified)
            if x + s.width > bounds.maxX, x > bounds.minX { x = bounds.minX; y += rowH + spacing; rowH = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(s))
            x += s.width + spacing
            rowH = max(rowH, s.height)
        }
    }
}

/// 화면 하단에 붙는 버튼 영역. 위 콘텐츠와 겹치는 부분은 배경색으로 페이드.
struct BottomBar<Content: View>: View {
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 4) { content }
            .padding(.horizontal, 20)
            .padding(.top, 12)
            .padding(.bottom, 8)
            .background(Theme.bg)
            .overlay(alignment: .top) {
                LinearGradient(colors: [Theme.bg.opacity(0), Theme.bg], startPoint: .top, endPoint: .bottom)
                    .frame(height: 24)
                    .offset(y: -24)
                    .allowsHitTesting(false)
            }
    }
}
