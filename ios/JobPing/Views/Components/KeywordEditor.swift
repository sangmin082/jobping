import SwiftUI

/// 키워드 입력. 순서가 곧 우선순위다 — 무료 티어는 첫 N개만 알림이 간다.
struct KeywordEditor: View {
    @Binding var keywords: [String]
    @State private var draft = ""
    @FocusState private var focused: Bool

    private let suggestions = ["DevOps", "SRE", "백엔드", "iOS", "데이터 엔지니어링", "머신러닝", "반도체", "보안", "인프라", "PM"]

    var body: some View {
        List {
            Section {
                HStack {
                    TextField("예: DevOps, 반도체, 데이터 엔지니어", text: $draft)
                        .focused($focused)
                        .submitLabel(.done)
                        .onSubmit(add)
                        .autocorrectionDisabled()
                    Button("추가", action: add).disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
                }
            } footer: {
                Text("띄어쓰기·대소문자는 상관없어요. 영어/한국어 동의어(인프라 ↔ infra)도 같이 찾습니다. 공고 제목과 세부 직무에서 찾아요.")
            }

            if !keywords.isEmpty {
                Section("내 키워드 (위쪽이 우선)") {
                    ForEach(keywords, id: \.self) { k in
                        Text(k)
                    }
                    .onDelete { keywords.remove(atOffsets: $0) }
                    .onMove { keywords.move(fromOffsets: $0, toOffset: $1) }
                }
            }

            Section("자주 쓰는 키워드") {
                FlowLayout(spacing: 8) {
                    ForEach(suggestions.filter { !keywords.contains($0) }, id: \.self) { s in
                        Button(s) { keywords.append(s) }
                            .buttonStyle(.bordered)
                            .controlSize(.small)
                    }
                }
            }
        }
        .toolbar { EditButton() }
        .onAppear { focused = keywords.isEmpty }
    }

    private func add() {
        let k = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !k.isEmpty, !keywords.contains(where: { $0.caseInsensitiveCompare(k) == .orderedSame }) else { draft = ""; return }
        keywords.append(k)
        draft = ""
    }
}

/// 칩을 줄바꿈해 배치한다. iOS 16+ Layout 프로토콜.
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
