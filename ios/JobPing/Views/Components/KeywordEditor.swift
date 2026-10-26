import SwiftUI

/// 키워드 입력. 선택 사항이다 — 비우면 고른 회사의 새 공고를 전부 받는다.
/// 순서는 알림에 어떤 키워드로 걸렸는지 보여줄 때만 쓴다(먼저 걸린 것).
struct KeywordEditor: View {
    @Binding var keywords: [String]
    @State private var draft = ""

    private let suggestions = ["DevOps", "SRE", "백엔드", "iOS", "데이터 엔지니어링", "머신러닝", "반도체", "보안", "인프라", "PM"]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 24) {
                input

                if !keywords.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        SectionLabel("내 키워드", trailing: "\(keywords.count)")
                        FlowLayout(spacing: 8) {
                            ForEach(keywords, id: \.self) { k in
                                RemovableChip(title: k) { keywords.removeAll { $0 == k } }
                            }
                        }
                    }
                }

                let rest = suggestions.filter { s in !keywords.contains { $0.caseInsensitiveCompare(s) == .orderedSame } }
                if !rest.isEmpty {
                    VStack(alignment: .leading, spacing: 10) {
                        SectionLabel("많이 찾는 키워드")
                        FlowLayout(spacing: 8) {
                            ForEach(rest, id: \.self) { s in
                                Button { keywords.append(s) } label: {
                                    HStack(spacing: 4) {
                                        Image(systemName: "plus").font(.caption.weight(.bold))
                                        Text(s)
                                    }
                                    .font(.subheadline.weight(.medium))
                                    .foregroundStyle(.primary)
                                    .padding(.horizontal, 12)
                                    .padding(.vertical, 8)
                                    .overlay(Capsule().strokeBorder(Theme.line, lineWidth: 1))
                                    .contentShape(Capsule())
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }

                Text("띄어쓰기·대소문자는 상관없어요. 영어/한국어 동의어(인프라 ↔ infra)도 같이 찾아요. 공고 제목과 세부 직무에서 찾아요.")
                    .font(.footnote)
                    .foregroundStyle(Theme.muted)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Theme.bg)
    }

    private var input: some View {
        HStack(spacing: 8) {
            TextField("예: DevOps, 반도체, 데이터 엔지니어", text: $draft)
                .submitLabel(.done)
                .onSubmit(add)
                .autocorrectionDisabled()
                .textInputAutocapitalization(.never)
            Button(action: add) {
                Image(systemName: "plus")
                    .font(.body.weight(.bold))
                    .foregroundStyle(Theme.onAccent)
                    .frame(width: 36, height: 36)
                    .background(Theme.accent, in: Circle())
            }
            .buttonStyle(.plain)
            .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
            .opacity(draft.trimmingCharacters(in: .whitespaces).isEmpty ? 0.35 : 1)
        }
        .padding(.leading, 16)
        .padding(.trailing, 6)
        .frame(height: 52)
        .background(Theme.card, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.line, lineWidth: 1))
    }

    private func add() {
        let k = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !k.isEmpty, !keywords.contains(where: { $0.caseInsensitiveCompare(k) == .orderedSame }) else { draft = ""; return }
        keywords.append(k)
        draft = ""
    }
}

/// 내 키워드 칩. × 로 지운다.
private struct RemovableChip: View {
    let title: String
    let remove: () -> Void

    var body: some View {
        HStack(spacing: 6) {
            Text(title).lineLimit(1)
            Button(action: remove) {
                Image(systemName: "xmark").font(.caption2.weight(.bold))
            }
            .buttonStyle(.plain)
            .accessibilityLabel("\(title) 지우기")
        }
        .font(.subheadline.weight(.semibold))
        .foregroundStyle(Theme.onAccent)
        .padding(.leading, 14)
        .padding(.trailing, 10)
        .padding(.vertical, 9)
        .background(Theme.accent, in: Capsule())
    }
}
