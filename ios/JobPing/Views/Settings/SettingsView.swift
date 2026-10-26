import SwiftUI

struct SettingsView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    ScreenHeader(eyebrow: nil, title: "설정", subtitle: nil)

                    VStack(alignment: .leading, spacing: 10) {
                        SectionLabel("알림 조건")
                        VStack(spacing: 0) {
                            NavigationLink {
                                CompanyPicker(selected: $model.selectedCompanies)
                                    .navigationTitle("관심 회사")
                                    .navigationBarTitleDisplayMode(.inline)
                                    .onDisappear { Task { await model.syncDevice(); await model.refreshJobs() } }
                            } label: {
                                SettingRow(icon: "building.2.fill", tint: Theme.navy, title: "관심 회사",
                                           value: "\(model.selectedCompanies.count)곳")
                            }
                            Divider().padding(.leading, 56)
                            NavigationLink {
                                KeywordEditor(keywords: $model.keywords)
                                    .navigationTitle("키워드")
                                    .navigationBarTitleDisplayMode(.inline)
                                    .onDisappear { Task { await model.syncDevice() } }
                            } label: {
                                SettingRow(icon: "number", tint: Color(hex: 0x0A9E6A), title: "키워드",
                                           value: model.keywords.isEmpty ? "전체 공고" : model.keywords.prefix(2).joined(separator: ", ")
                                               + (model.keywords.count > 2 ? " 외 \(model.keywords.count - 2)" : ""))
                            }
                        }
                        .buttonStyle(.plain)
                        .card(padding: 0)
                        if !model.selectedCompanies.isEmpty {
                            companyStrip
                        }
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        SectionLabel("알림")
                        HStack(spacing: 14) {
                            IconTile(icon: "bell.fill", tint: Color(hex: 0xE5484D))
                            Toggle("새 공고 알림", isOn: $model.pushEnabled)
                                .font(.body.weight(.medium))
                                .tint(Theme.accent)
                                .onChange(of: model.pushEnabled) { _, on in
                                    Task {
                                        if on { _ = await PushPermission.request() }
                                        await model.syncDevice()
                                    }
                                }
                        }
                        .padding(.vertical, 12)
                        .padding(.horizontal, 14)
                        .card(padding: 0)
                        Text("밤 11시~아침 8시엔 모아뒀다가 아침에 한 번에 보내요. 한 번에 5건이 넘으면 묶어서 알려요.")
                            .font(.footnote)
                            .foregroundStyle(Theme.muted)
                            .padding(.horizontal, 4)
                    }

                    VStack(alignment: .leading, spacing: 10) {
                        SectionLabel("정보")
                        VStack(spacing: 0) {
                            Link(destination: URL(string: "https://github.com/sangmin082/jobping/blob/main/docs/PRIVACY.md")!) {
                                SettingRow(icon: "hand.raised.fill", tint: Color(hex: 0x6B7280), title: "개인정보 처리방침",
                                           value: nil, external: true)
                            }
                            Divider().padding(.leading, 56)
                            SettingRow(icon: "info.circle.fill", tint: Color(hex: 0x6B7280), title: "버전",
                                       value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "-",
                                       chevron: false)
                        }
                        .buttonStyle(.plain)
                        .card(padding: 0)
                        Text("잡핑은 각 기업과 무관한 비공식 앱이에요. 공고는 각 회사의 공식 채용 페이지에서 가져오고, 원문은 해당 페이지에서 확인해주세요. 잡핑은 무료예요.")
                            .font(.footnote)
                            .foregroundStyle(Theme.muted)
                            .padding(.horizontal, 4)
                    }

                    if let err = model.lastError {
                        Text(err)
                            .font(.footnote)
                            .foregroundStyle(Color(hex: 0xE5484D))
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .card(padding: 14)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Theme.bg)
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    /// 고른 회사 타일 줄. 몇 곳인지 숫자보다 빨리 읽힌다.
    private var companyStrip: some View {
        let picked = model.selectedCompanies.compactMap { model.company(for: $0) }
        let groups = picked.reduce(into: [String]()) { if !$0.contains($1.group) { $0.append($1.group) } }
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: -6) {
                ForEach(groups.prefix(8), id: \.self) { g in
                    CompanyBadge(group: g, size: 30)
                        .overlay(RoundedRectangle(cornerRadius: 30 * 0.28, style: .continuous)
                            .strokeBorder(Theme.bg, lineWidth: 2))
                }
                if groups.count > 8 {
                    Text("+\(groups.count - 8)")
                        .font(.caption.weight(.bold))
                        .foregroundStyle(Theme.muted)
                        .padding(.leading, 12)
                }
            }
            .padding(.horizontal, 4)
        }
    }
}

private struct IconTile: View {
    let icon: String
    let tint: Color

    var body: some View {
        Image(systemName: icon)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(.white)
            .frame(width: 28, height: 28)
            .background(tint, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }
}

private struct SettingRow: View {
    let icon: String
    let tint: Color
    let title: String
    let value: String?
    var chevron = true
    var external = false

    var body: some View {
        HStack(spacing: 14) {
            IconTile(icon: icon, tint: tint)
            Text(title)
                .font(.body.weight(.medium))
                .foregroundStyle(.primary)
            Spacer(minLength: 8)
            if let value {
                Text(value)
                    .font(.subheadline)
                    .foregroundStyle(Theme.muted)
                    .lineLimit(1)
            }
            if chevron {
                Image(systemName: external ? "arrow.up.right" : "chevron.right")
                    .font(.footnote.weight(.semibold))
                    .foregroundStyle(Theme.muted.opacity(0.7))
            }
        }
        .padding(.vertical, 13)
        .padding(.horizontal, 14)
        .contentShape(Rectangle())
    }
}
