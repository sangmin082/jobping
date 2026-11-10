# App Store 제출물

App Store Connect ▸ 앱 ▸ 잡핑 에 그대로 붙여넣는 값들. 글자 수 제한은 App Store Connect 기준이다.
`[직접]` 표시는 본인만 정할 수 있는 값이다.

---

## 1. 앱 정보 (앱 정보 탭)

| 항목 | 값 |
|---|---|
| 이름 (30자) | **잡핑 - 대기업 경력 채용 알림** |
| 부제 (30자) | **관심 회사 새 공고, 가장 먼저** |
| 기본 카테고리 | 비즈니스 |
| 보조 카테고리 | 생산성 |
| 연령 등급 | 4+ (아래 4절) |
| 콘텐츠 권한 | 아래 6절 — **본인 판단 필요** |

이름 "잡핑"만으로는 이미 쓰이는 이름일 수 있다. 등록이 막히면 `잡핑: 경력 채용 알림`으로 바꾼다.

## 2. 가격 및 사용 가능 여부

- 가격: **무료**
- 사용 가능 국가: **대한민국만** (공고·화면이 전부 한국어)

## 3. 버전 정보 (1.0 제출 화면)

### 프로모션 텍스트 (170자, 심사 없이 언제든 바꿀 수 있음)

```
삼성·SK·LG·네이버·토스 등 100여 개 회사의 채용 페이지를 30분마다 확인해서, 새 경력 공고가 뜨면 바로 알려드려요. 완전 무료, 가입 없음.
```

### 설명 (4000자)

```
관심 있는 회사에 새 경력 공고가 올라오면, 가장 먼저 알려드려요.

잡핑은 대기업과 IT 기업의 공식 채용 페이지를 30분마다 확인해서, 내가 고른 회사에 새 경력 공고가 뜨면 푸시 알림으로 알려주는 앱이에요. 채용 사이트를 매일 들어가 보지 않아도 돼요.

■ 이렇게 써요
1. 소식을 받고 싶은 회사를 골라요. 계열사 단위로 고를 수 있어요. (예: 삼성전자 DS부문, SK하이닉스, 토스뱅크)
2. 관심 직무 키워드를 넣어요. 선택이에요 — 비워두면 고른 회사의 새 경력 공고를 전부 알려드려요.
3. 끝. 새 공고가 뜨면 알림이 와요.

■ 이런 점이 달라요
· 회사 공식 채용 페이지에서 직접 가져와요. 원문도 항상 그 페이지에서 열려요.
· 계열사별로 지금 올라와 있는 공고 수를 보여줘요.
· 키워드는 띄어쓰기·대소문자를 가리지 않고, 영어/한국어 동의어(인프라 ↔ infra)도 같이 찾아요.
· 밤 11시부터 아침 8시까지는 알림을 모아뒀다가 아침에 한 번에 보내요.
· 한 번에 공고가 많이 뜨면 알림을 하나로 묶어요.
· 마음에 드는 공고는 저장해두고 다시 볼 수 있어요.

■ 완전 무료, 가입 없음, 광고 없음
이름·이메일·전화번호를 받지 않아요. 로그인도 없어요.

■ 지금 지원하는 회사 (계속 늘어나요)
삼성 계열사, SK 계열사, LG 계열사, 현대자동차, 기아, 네이버, 카카오, 라인, 우아한형제들, 토스, 쿠팡, 당근, 야놀자, 테슬라 코리아

※ 잡핑은 각 기업과 무관한 비공식 앱이에요. 공고 정보는 각 회사의 공식 채용 페이지에 공개된 내용이며, 지원은 해당 페이지에서 해주세요.
```

### 키워드 (100자, 쉼표로 구분, 띄어쓰기 없이)

```
채용알림,경력직,이직,채용공고,대기업,공채,수시채용,경력채용,구직,취업,개발자,엔지니어,잡알림,채용정보,신규공고,커리어,채용소식,경력공고
```

회사 이름(삼성·네이버…)은 키워드에 넣지 않는다. 남의 상표를 검색 키워드로 쓰면
심사 지침 2.3.7 위반으로 거절될 수 있다. 설명문에 지원 회사로 적는 건 사실 서술이라 괜찮다.

### 기타

| 항목 | 값 |
|---|---|
| 지원 URL | `https://github.com/sangmin082/jobping/issues` |
| 마케팅 URL | (비워둔다) |
| 저작권 | `2026 [직접: 본인 이름]` |
| 버전 | **1.0.0** — 제출 전에 `ios/project.yml` 의 `MARKETING_VERSION` 을 1.0.0 으로 올린다 (지금 0.1.0) |

## 4. 연령 등급 설문

전부 **없음 / 아니요**. 결과 **4+**.

- 사용자 생성 콘텐츠, 메시지·채팅: 아니요
- 웹 무제한 접근: **아니요** — 공고 원문을 Safari 뷰로 열지만 주소창이 없어 사용자가 임의의 사이트로 갈 수 없다
- 도박, 폭력, 성적 콘텐츠 등: 없음
- 광고: 없음

## 5. 앱 개인정보 보호 (App Privacy 탭)

개인정보 처리방침 URL:
`https://github.com/sangmin082/jobping/blob/main/docs/PRIVACY.md`

**데이터를 수집합니까?** → 예

| 데이터 유형 | 무엇 | 용도 | 사용자와 연결 | 추적 |
|---|---|---|---|---|
| 식별자 ▸ **기기 ID** | 앱이 만든 무작위 설치 ID, 푸시 알림 토큰 | 앱 기능 | 아니요 | 아니요 |
| 사용자 콘텐츠 ▸ **기타 사용자 콘텐츠** | 고른 회사·키워드 | 앱 기능 | 아니요 | 아니요 |

- "사용자와 연결 = 아니요" 근거: 계정이 없고, 이름·이메일·전화번호 등 실제 신원과 이어지는 정보를 받지 않는다.
- 추적 없음: 광고 식별자(IDFA) 미사용, 제3자 SDK 없음(분석·광고·크래시 수집 모두 없음).
- 저장한 공고(북마크)는 기기에만 있어서 수집에 해당하지 않는다.

## 6. 콘텐츠 권한 — 본인 판단 필요

App Store Connect가 "제3자 콘텐츠를 표시하거나 접근합니까?"를 묻는다. 잡핑은 회사 채용 페이지의
**공고 제목·근무지·직무명·링크**를 보여준다(본문은 저장하지 않고 원문은 회사 페이지에서 연다).

- 정직한 답은 **예(제3자 콘텐츠 있음)**.
- 이어서 "필요한 권리를 모두 갖고 있습니까"를 묻는데, 공개된 공고의 제목과 링크만 쓰는 구조라
  일반적으로는 문제가 적지만 **법적 판단은 본인 몫**이다. 불안하면 출시 전에 확인받는다.
- 심사에서 이 부분을 물으면 7절 심사 메모의 설명으로 답한다.

## 7. 앱 심사 정보

| 항목 | 값 |
|---|---|
| 로그인 필요 | 아니요 (데모 계정 불필요) |
| 연락처 (이름·전화·이메일) | [직접] — 심사팀만 본다 |

### 심사 메모 (영어로 — 심사관 대부분이 영어를 쓴다)

```
JobPing is a free job-alert app for Korea. It checks the official career pages of large Korean companies every 30 minutes and sends a push notification when a new experienced-hire posting appears at a company the user picked.

How to review:
1. Launch the app and tap "시작하기" (Start).
2. Pick one or more companies (e.g. SK하이닉스, 쿠팡). Each shows how many postings are open now.
3. Keywords are optional; tap "건너뛰고 전체 공고 받기" (Skip) to receive every new posting at those companies.
4. Allow notifications. The "새 공고" (New postings) tab lists current postings; tapping one opens the company's own career page.

No account or sign-in is needed. The app collects no name, email or phone number; it stores a random install ID, the push token and the chosen companies/keywords so the server can match postings.

Content: JobPing is unofficial and not affiliated with the companies. It shows only the title, location, role and link of postings that the companies publish publicly, and always opens the original page for details. It does not copy posting bodies.

Push notifications depend on new postings appearing, which can take hours. Coupang and Toss post most often if you want to see one sooner.
```

## 8. 스크린샷

- **필수: 6.9인치 iPhone** (1320×2868 또는 1290×2796). 지금 CI가 찍는 6.3인치(1206×2622)로는 제출이 안 된다.
- CI의 build 잡이 Pro Max 시뮬레이터로 스토어용 세트(`store-*.png`)를 따로 찍는다 — 아티팩트 `screenshots`.
- 올리는 순서 (최대 10장, 처음 3장이 검색 결과에 보인다):
  1. `store-welcome` — 첫인상
  2. `store-jobs` — 실제로 보는 화면
  3. `store-push` — 알림이 이렇게 온다
  4. `store-companies` — 계열사별 공고 수
  5. `store-keywords` — 키워드는 선택
- 스크린샷의 회사·공고는 데모 데이터다. 실제 존재하는 회사명이지만 공고 내용은 예시라는 점을
  심사에서 문제 삼으면 실제 공고 화면으로 바꾼다.

## 9. 제출 전 체크리스트

- [ ] `MARKETING_VERSION` 1.0.0 으로 올리고 TestFlight 빌드 새로 만들기
- [ ] 삼성전자 공고 출처 해결 (지금 0건 — 설명문이 삼성을 앞세운다)
- [ ] 지인 베타에서 실제 공고 알림 수신 확인
- [ ] 개인정보 처리방침 URL 이 로그인 없이 열리는지 확인 (저장소가 공개라 지금은 열린다)
- [ ] 콘텐츠 권한(6절) 본인 판단
- [ ] 연락처·저작권 입력
