import SwiftUI

struct SettingsView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        @Bindable var model = model
        NavigationStack {
            Form {
                Section("구독") {
                    NavigationLink {
                        CompanyPicker(selected: $model.selectedCompanies)
                            .navigationTitle("관심 회사")
                            .onDisappear { Task { await model.syncDevice(); await model.refreshJobs() } }
                    } label: {
                        LabeledContent("관심 회사", value: "\(model.selectedCompanies.count)곳")
                    }
                    NavigationLink {
                        KeywordEditor(keywords: $model.keywords)
                            .navigationTitle("키워드")
                            .onDisappear { Task { await model.syncDevice() } }
                    } label: {
                        LabeledContent("키워드", value: model.keywords.isEmpty ? "없음" : model.keywords.prefix(3).joined(separator: ", "))
                    }
                }

                Section {
                    Toggle("새 공고 알림", isOn: $model.pushEnabled)
                        .onChange(of: model.pushEnabled) { _, on in
                            Task {
                                if on { _ = await PushPermission.request() }
                                await model.syncDevice()
                            }
                        }
                } footer: {
                    Text("밤 11시~아침 8시엔 모아뒀다가 아침에 한 번에 보내드려요. 한 번에 5건이 넘으면 묶어서 알려요.")
                }

                Section("이용 등급") {
                    LabeledContent("현재", value: model.isPro ? "Pro" : "무료")
                    if !model.isPro {
                        Text("무료: 키워드 \(model.freeTier.maxKeywords)개 · 회사 \(model.freeTier.maxCompanies)곳까지 알림. 그 이상은 등록은 되지만 알림이 가지 않아요.")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }

                Section("정보") {
                    LabeledContent("버전", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "-")
                    Text("잡핑은 각 기업과 무관한 비공식 앱입니다. 공고 정보는 각 회사의 공식 채용 페이지에서 가져오며, 원문은 해당 페이지에서 확인하세요.")
                        .font(.footnote).foregroundStyle(.secondary)
                    Link("개인정보 처리방침", destination: URL(string: "https://github.com/sangmin082/jobping/blob/main/docs/PRIVACY.md")!)
                }

                if let err = model.lastError {
                    Section("최근 오류") {
                        Text(err).font(.footnote).foregroundStyle(.red)
                    }
                }
            }
            .navigationTitle("설정")
        }
    }
}
