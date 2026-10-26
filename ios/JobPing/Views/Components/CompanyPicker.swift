import SwiftUI

/// 회사 고르기. 계열사가 여럿인 그룹(삼성/SK/LG…)은 카드 하나에 칩으로, 한 곳뿐인
/// 회사(카카오/토스…)는 2열 타일로 보여준다. 구독 단위는 계열사다.
struct CompanyPicker: View {
    @Environment(AppModel.self) private var model
    @Binding var selected: [String]
    @State private var search = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                SearchField(text: $search, prompt: "회사 이름으로 찾기")
                    .padding(.bottom, 4)
                if model.companies.isEmpty {
                    EmptyState(icon: "building.2", title: "회사 목록을 불러오는 중",
                               message: model.lastError ?? "잠시만요")
                } else if groups.isEmpty && singles.isEmpty {
                    EmptyState(icon: "magnifyingglass", title: "'\(search)' 회사가 없어요",
                               message: "지금은 대기업·IT 기업 100여 곳을 지원해요")
                }
                ForEach(groups) { group in
                    GroupCard(group: group, selected: $selected)
                }
                if !singles.isEmpty {
                    SectionLabel("IT·플랫폼 외")
                        .padding(.top, 8)
                    LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)],
                              spacing: 10) {
                        ForEach(singles) { company in
                            CompanyTile(company: company, isOn: selected.contains(company.key)) {
                                toggle(company.key)
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
        .scrollDismissesKeyboard(.immediately)
        .background(Theme.bg)
    }

    /// 계열사가 둘 이상인 그룹. 계열사 많은 순.
    private var groups: [CompanyGroup] {
        filtered.filter { $0.companies.count > 1 }
            .sorted { ($0.companies.count, $1.group) > ($1.companies.count, $0.group) }
    }

    /// 한 곳뿐인 회사들. 이름순.
    private var singles: [Company] {
        filtered.filter { $0.companies.count == 1 }
            .flatMap(\.companies)
            .sorted { $0.displayName < $1.displayName }
    }

    private var filtered: [CompanyGroup] {
        guard !search.isEmpty else { return model.companiesByGroup }
        return model.companiesByGroup.compactMap { g in
            let hits = g.group.localizedCaseInsensitiveContains(search)
                ? g.companies
                : g.companies.filter { $0.displayName.localizedCaseInsensitiveContains(search) }
            return hits.isEmpty ? nil : CompanyGroup(group: g.group, companies: hits)
        }
    }

    private func toggle(_ key: String) {
        if let i = selected.firstIndex(of: key) {
            selected.remove(at: i)
        } else {
            selected.append(key)
        }
    }
}

/// 그룹 카드: 머리(타일·이름·전체 선택) + 계열사 칩.
private struct GroupCard: View {
    let group: CompanyGroup
    @Binding var selected: [String]

    var body: some View {
        let keys = group.companies.map(\.key)
        let count = keys.filter { selected.contains($0) }.count
        let all = count == keys.count
        VStack(alignment: .leading, spacing: 14) {
            HStack(spacing: 10) {
                CompanyBadge(group: group.group, size: 34)
                VStack(alignment: .leading, spacing: 1) {
                    Text(group.group).font(.jp(17, .semibold, relativeTo: .headline))
                    Text(count == 0 ? summary : "\(keys.count)곳 중 \(count)곳 선택")
                        .font(.jp(12, relativeTo: .caption))
                        .foregroundStyle(count == 0 ? Theme.muted : Theme.accent)
                        .monospacedDigit()
                }
                Spacer()
                Button(all ? "전체 해제" : "전체 선택") {
                    if all {
                        selected.removeAll { keys.contains($0) }
                    } else {
                        selected += keys.filter { !selected.contains($0) }
                    }
                }
                .font(.jp(13, .semibold, relativeTo: .footnote))
                .foregroundStyle(Theme.accent)
                .buttonStyle(.plain)
            }
            FlowLayout(spacing: 8) {
                ForEach(group.companies) { c in
                    SelectChip(title: c.displayName, detail: c.lastFetched.map(String.init),
                               isOn: selected.contains(c.key)) {
                        if let i = selected.firstIndex(of: c.key) { selected.remove(at: i) } else { selected.append(c.key) }
                    }
                }
            }
        }
        .card()
    }

    /// "계열사 6곳 · 공고 128건". 공고 수는 계열사별 현재 경력 공고의 합이다.
    private var summary: String {
        let counts = group.companies.compactMap(\.lastFetched)
        let base = "계열사 \(group.companies.count)곳"
        return counts.isEmpty ? base : "\(base) · 공고 \(counts.reduce(0, +))건"
    }
}

/// 한 곳뿐인 회사 타일.
private struct CompanyTile: View {
    let company: Company
    let isOn: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                CompanyBadge(group: company.group, size: 34)
                VStack(alignment: .leading, spacing: 1) {
                    Text(company.displayName)
                        .font(.jp(14, .semibold, relativeTo: .subheadline))
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.8)
                    if let n = company.lastFetched {
                        Text(n == 0 ? "지금 공고 없음" : "공고 \(n)건")
                            .font(.jp(12, relativeTo: .caption))
                            .foregroundStyle(Theme.muted)
                            .monospacedDigit()
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: isOn ? "checkmark.circle.fill" : "circle")
                    .font(.jp(19, relativeTo: .title3))
                    .foregroundStyle(isOn ? Theme.accent : Theme.line)
            }
            .padding(12)
            .background(Theme.card, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                .strokeBorder(isOn ? Theme.accent : Theme.line, lineWidth: isOn ? 1.5 : 1))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .animation(.easeOut(duration: 0.12), value: isOn)
    }
}
