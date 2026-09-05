import SwiftUI

/// 그룹(삼성/SK/LG…)별로 묶어 계열사를 고른다. 구독 단위는 계열사다.
struct CompanyPicker: View {
    @Environment(AppModel.self) private var model
    @Binding var selected: [String]
    @State private var search = ""

    var body: some View {
        List {
            ForEach(filteredGroups) { section in
                Section(section.group) {
                    ForEach(section.companies) { company in
                        Button {
                            toggle(company.key)
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(company.displayName).foregroundStyle(.primary)
                                    if let n = company.lastFetched {
                                        Text("현재 경력 공고 \(n)건")
                                            .font(.caption).foregroundStyle(.secondary)
                                    }
                                }
                                Spacer()
                                if selected.contains(company.key) {
                                    Image(systemName: "checkmark.circle.fill").foregroundStyle(.tint)
                                } else {
                                    Image(systemName: "circle").foregroundStyle(.quaternary)
                                }
                            }
                        }
                    }
                }
            }
        }
        .searchable(text: $search, prompt: "회사 검색")
        .overlay(alignment: .bottom) {
            if !selected.isEmpty {
                Text("\(selected.count)곳 선택")
                    .font(.footnote.weight(.semibold))
                    .padding(.horizontal, 14).padding(.vertical, 8)
                    .background(.thinMaterial, in: Capsule())
                    .padding(.bottom, 8)
            }
        }
    }

    private var filteredGroups: [CompanyGroup] {
        guard !search.isEmpty else { return model.companiesByGroup }
        return model.companiesByGroup.compactMap { g in
            let hits = g.companies.filter { $0.displayName.localizedCaseInsensitiveContains(search) || g.group.localizedCaseInsensitiveContains(search) }
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
