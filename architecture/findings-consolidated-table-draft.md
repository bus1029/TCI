# TCI 아키텍처 C4 검토 비교표

이 문서는 각 리뷰 문서의 `핵심 findings`를 Notion 형식의 비교표로 다시 정리한 완성본이다.

정리 원칙:

- 섹션 기준은 `각 Diagram`
- 표 형식은 `논의 사항 / 조치 / 추천 / 결정`
- 각 행은 원문 `핵심 findings` 1개와 1:1로 대응
- 각 섹션의 `[#n]` 표기는 해당 리뷰 문서의 findings 번호와 동일

## 1. C1 Context Diagram

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] `IDE Plugin` 제거 결정과 실제 `puml` 충돌**<br>Notion 설명은 `IDE Plugin` 제거를 명시하지만 `puml`에는 `IDE Plugin`, `Developer -> IDE Plugin`, `TCI <-> IDE Plugin`이 남아 있다 | **옵션 A**: `puml`에서 `IDE Plugin`을 제거<br>**옵션 B**: Notion의 제거 결정을 철회하고 병렬 채널로 유지 | 옵션 A 추천. 현재 상위 메시지는 `AI Coding Agent` 중심이 더 일관적이다 | ___ |
| **[#2] 기능 문서의 `로컬 변경 코드 스냅샷 전송(플러그인)`과 C1 방향 불일치**<br>`whole-features.md`는 플러그인 기반 diff 캡처를 공식 기능으로 두지만 C1 설명은 이를 사실상 `AI Coding Agent`로 대체한다 | 기능 문서에서 플러그인을 `후순위` 또는 `대체 가능 채널`로 낮추거나, 반대로 C1에 다시 공식 채널로 복원 | 제품 기준선을 먼저 고정한 뒤 문서 전체를 한 방향으로 정리 추천 | ___ |
| **[#3] `Ticket` 관계의 `분석 코멘트 작성` 근거 약함**<br>문서에서는 티켓 메타데이터 수집과 연결은 보이지만 TCI가 Jira/Azure DevOps에 코멘트를 다시 쓴다는 요구는 약하다 | `분석 코멘트 작성`을 C1에서 제거하거나, 제품 문서에 outbound comment 기능을 명시적으로 추가 | 근거가 약하므로 우선 제거 추천 | ___ |
| **[#4] `Docs / Wiki` 양방향 발행 근거 보강 필요**<br>문서 초안 생성과 문서화 자동화는 보이지만 외부 위키 재발행이 확정 요구사항인지는 약하다 | 외부 위키 발행이 범위라면 PRD/기능 문서에 명시하고, 아니라면 C1의 양방향 표현을 약화 | 범위가 확정되기 전까지는 약한 표현으로 낮추는 방향 추천 | ___ |
| **[#5] `파일 업로드`가 C1에서 사실상 보이지 않음**<br>코드 ZIP, 매뉴얼, 규정 문서 업로드는 중요한 입력 축인데 현재 C1은 외부 시스템 중심으로만 보인다 | 사용자와 TCI 관계에 `문서/코드 업로드`를 추가하거나, 단순화 생략 의도를 note로 남김 | 업로드는 핵심 입력 경로이므로 관계에 직접 드러내는 방식 추천 | ___ |
| **[#6] `문서화/설명 산출물`과 `자연어 질의응답` 가치가 약하게 표현됨**<br>현재 설명은 구조/영향 분석에 치우쳐 있고, 포지셔닝 문서가 강조하는 설명 가능성과 문서화 가치가 약하다 | 시스템 설명과 사용자 관계에 `질의응답`, `근거 링크`, `리포트/문서 초안 생성`을 추가 | 권고 수용 추천 | ___ |

## 2. C2 Container Diagram

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] `Policy Engine` 외부 경계가 C2에서 사라짐**<br>기능 문서는 별도 `Policy Gate` 외부 시스템을 전제하지만 C2는 이를 `DevOps Pipeline` 쪽에 흡수해 경계를 흐린다 | **옵션 A**: `Policy Engine`을 외부 시스템으로 복원<br>**옵션 B**: 현재 모델을 유지하되 문서도 같은 기준으로 수정 | 옵션 A 추천. 정책 판단 시스템과 파이프라인 채널은 분리하는 편이 명확하다 | ___ |
| **[#2] `파일 업로드`가 외부 시스템처럼 표현됨**<br>`Data Collection -> Development Context`의 `REST / Upload`는 실제 사용자 업로드를 외부 시스템 호출처럼 보이게 만든다 | `사용자 -> Web Application -> Data Collection` 경로로 다시 표현하거나 `Development Context`의 `Upload`를 제거 | 업로드는 사용자 진입 흐름으로 재표현 추천 | ___ |
| **[#3] `Knowledge Base`에서 `Vector DB`가 빠져 Notion 설명과 불일치**<br>질의응답과 컨텍스트 검색을 생각하면 벡터 저장소가 핵심인데 `puml`에는 `Graph DB · Object Storage`만 보인다 | KB 구성을 `Graph + Vector + Object + Search` 기준으로 통일 | `Vector DB`를 C2에도 명시 추천 | ___ |
| **[#4] Notion의 `Workflow & Integration -> Web Application` 푸시 관계가 `puml`에서 누락**<br>실시간 알림 UX를 설명하면서도 실제 관계선은 빠져 있다 | `W&I -> WebApp` 또는 `W&I -> Notification Hub` 관계를 추가하거나, Notion 설명에서 제거 | 제품 UX에 실시간 알림이 중요하므로 관계 추가 추천 | ___ |
| **[#5] `IDE Plugin 제거` 방향이 C2와 기능 문서 사이에서 미정렬**<br>C2는 `AI Coding Agent`만 남겼지만 기능 문서는 여전히 플러그인 기반 입력을 포함한다 | 기능 문서의 플러그인 항목을 후순위로 낮추거나, 공식 범위라면 C2에도 채널을 복원 | 상위 기준에 맞춰 기능 문서를 정리하는 방향 추천 | ___ |

## 3. C3 Web Application

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] `파일 업로드`와 `연동 설정` 경로가 Web Application에서 드러나지 않음**<br>`UI Shell -> API Router`는 보이지만 업로드, 인증 정보 관리, 동기화 정책, 연동 상태 조회가 어디로 가는지 불명확하다 | `API Router` 설명에 `설정/업로드/API 프록시`를 포함하거나, 외부 참조에 `Data Collection` 또는 `Operations Manager`를 추가 | 업로드와 설정의 실제 백엔드 경로를 명시 추천 | ___ |
| **[#2] `Asset Server`가 존재하지만 실제 관계가 없음**<br>정적 자산 서빙 책임은 정의돼 있지만 브라우저나 `UI Shell`과의 관계선이 없다 | `사용자 -> Asset Server` 또는 `UI Shell -> Asset Server` 관계를 추가 | 단순 표현 누락이므로 관계 추가 추천 | ___ |
| **[#3] `Notification Hub`의 반환 경로가 명시되지 않음**<br>`UI Shell -> Notification Hub` 구독과 `Workflow -> Notification Hub` 푸시는 있지만 `Notification Hub -> UI Shell` 업데이트 흐름이 빠져 있다 | `Notification Hub -> UI Shell` `알림 상태/배지 업데이트` 관계를 추가 | 권고 수용 추천 | ___ |
| **[#4] `Auth Gateway`의 `RBAC 프론트 체크` 표현이 보안 경계를 오해하게 만들 수 있음**<br>프론트엔드 체크만 보이면 백엔드 권한 재검증이 없는 것처럼 읽힌다 | `프론트 체크`는 유지하되 `백엔드에서도 재검증`한다는 note 추가 | 경계 오해를 막기 위해 note 보강 추천 | ___ |
| **[#5] `API Router`의 대상이 `Workflow & Integration` 하나뿐인 점은 현재 타당하지만 장기 범위는 불명확**<br>향후 업로드, 연동 설정, 라이선스 관리까지 커지면 BFF 범위 정의가 필요하다 | `API Router`를 `W&I 전용 BFF`인지 `전체 백엔드 BFF`인지 정의하고 설명에 반영 | 지금 기준 정의를 짧게라도 문서화 추천 | ___ |

## 4. C3 Data Collection

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] `인증 정보 관리` 책임이 컴포넌트 수준에서 보이지 않음**<br>OAuth, API 토큰, SSH Key 등록·암호화 저장·삭제 기능이 문서에 있지만 이를 담당하는 컴포넌트가 없다 | `Credential Manager` 또는 `Connection Manager`를 추가하거나 외부 비밀관리 서비스 의존성을 명시 | 별도 책임으로 드러내는 방식 추천 | ___ |
| **[#2] `파일 업로드`가 `Document Collector` 설명에만 있고 실제 진입 경로가 없음**<br>현재 인바운드는 웹훅 위주라 사용자 직접 업로드가 사라져 보인다 | `Web Application -> Document Collector` 또는 `Web Application -> Collection Orchestrator` 경로를 추가 | 업로드 진입 경로를 명시 추천 | ___ |
| **[#3] `로컬 변경 코드 스냅샷 전송(플러그인)` 경로가 없음**<br>기능 문서가 플러그인 입력을 공식 범위로 둔다면 DC에도 입력 채널이 있어야 한다 | 제품 기준이 `AI Agent` 우선인지, 플러그인도 공식 범위인지 먼저 결정 후 다이어그램에 반영 | 상위 제품 기준 결정 선행 추천 | ___ |
| **[#4] `데이터 소스 스냅샷 관리` 책임이 누락되거나 경계가 불명확**<br>스냅샷 저장, 버전 이력, 특정 시점 재현, 스냅샷 비교 책임이 어느 컴포넌트에도 분명히 안 보인다 | `Snapshot Manager`를 추가하거나, 해당 책임이 `Knowledge Base`인지 명시 | 스냅샷 책임 위치를 먼저 고정 추천 | ___ |
| **[#5] `연동 상태 모니터링`과 `오류 로그` 관점이 약함**<br>기능 문서에는 연결 상태, 마지막 동기화 시각, 오류 로그가 있지만 C3 표현은 약하다 | `Collection Orchestrator` 설명에 `연동 상태/오류 기록`을 포함하거나 운영성 책임의 위치를 note로 명시 | 설명 보강 추천 | ___ |
| **[#6] `Development Context -> Webhook Receiver` 근거가 약함**<br>코드 수집은 웹훅이 분명하지만 티켓·문서 변경 이벤트 구독은 현재 문서 근거가 상대적으로 약하다 | 관계를 점선 또는 옵션으로 낮추거나, 제품 문서에 티켓/문서 이벤트 구독 요구를 추가 | 근거 확보 전까지는 옵션 처리 추천 | ___ |

## 5. C3 Data Processing

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] `문서/티켓`까지 `CPG Generator`로 들어가는 것처럼 읽힘**<br>현재 선형 파이프라인은 코드와 비코드 자산을 같은 처리 흐름으로 오해하게 만든다 | `Code Pipeline`과 `Context Artifact Pipeline`으로 분기하고 코드만 `CPG Generator`로 전달 | 파이프라인 분기 명시 추천 | ___ |
| **[#2] `KB Loader`의 책임과 실제 쓰기 경로가 충돌**<br>설명은 중앙 적재자인데 `Snapshot Builder`와 `Embedding Generator`가 직접 KB에 쓰는 관계도 있다 | **옵션 A**: `KB Loader`를 유일한 writer로 유지<br>**옵션 B**: `Graph Loader`로 축소하고 직접 쓰기 모델을 명시 | 먼저 적재 원칙을 결정하고 용어를 맞추는 방식 추천 | ___ |
| **[#3] `Snapshot Builder`의 범위가 제품 문서의 `데이터 소스 스냅샷 관리`보다 좁음**<br>현재 설명은 코드 스냅샷 중심이라 전체 데이터 소스 스냅샷 책임과 어긋난다 | `Snapshot Builder`를 `코드 스냅샷`으로 명시하거나, 상위 스냅샷 관리와 연결해 역할을 분리 | 이름과 책임 범위를 맞추는 쪽 추천 | ___ |
| **[#4] `Source Normalizer` 책임 설명이 과도함**<br>`언어별 파서 선택`은 `CPG Generator`의 프론트엔드 선택과 겹친다 | `Source Normalizer`는 입력 정규화·분류만 담당하고 실제 파서 선택은 `CPG Generator`로 일원화 | 책임 중복 제거 추천 | ___ |
| **[#5] `도메인 용어 사전`과 `외부 컨텍스트` 준비 책임이 거의 보이지 않음**<br>오류는 아니지만 향후 세분화 시 어디서 용어 후보 추출과 외부 컨텍스트 병합을 담당하는지 보강이 필요하다 | `Data Processing`을 전처리 범위로 한정한다는 note를 추가하거나, 향후 세부 컴포넌트 후보를 기록 | 현재는 note 보강 정도 추천 | ___ |

## 6. C3 Analysis Engine

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] Notion 설명의 `내부 컴포넌트 10개`와 실제 목록이 맞지 않음**<br>실제 `puml`에는 `KB Writer`를 포함해 11개가 보인다 | Notion 문서의 개수 표기를 실제와 맞추거나, `KB Writer`를 설명 구조에서 재배치 | 단순 불일치이므로 즉시 수정 추천 | ___ |
| **[#2] `Business Rule Extractor`가 무엇을 읽는지 관계가 빠져 있음**<br>LLM 호출은 보이지만 규칙 추출의 근거가 되는 구조·흐름 데이터 접근이 표현되지 않는다 | `Business Rule Extractor -> Knowledge Base` 또는 `Business Rule Extractor -> Data Flow Tracer` 관계를 추가 | 근거 데이터 접근을 명시 추천 | ___ |
| **[#3] `Data Flow Tracer`도 입력 관계가 없음**<br>실행 지시만 있을 뿐 실제 그래프 질의나 다른 분석기와의 연결이 부족하다 | `Data Flow Tracer -> KB` `Graph Query`를 추가하고 필요한 상호 의존을 명시 | 권고 수용 추천 | ___ |
| **[#4] `Tech Stack Detector`도 입력 자산이 보이지 않음**<br>빌드 파일, 설정 파일, 코드 구조 메타데이터를 읽어야 하지만 다이어그램에는 실행만 보인다 | `Tech Stack Detector -> KB` `Graph/Object Query` 또는 처리 산출물 조회 관계를 추가 | 입력 자산을 드러내는 방향 추천 | ___ |
| **[#5] `Impact Analyzer`의 diff 입력 경로가 불명확**<br>의존성·규칙 질의는 보이지만 diff 자체를 어디서 받는지 나타나지 않는다 | `Analysis Coordinator` note에 `diff reference` 입력을 명시하거나 `Impact Analyzer -> KB` 설명에 snapshot/diff 질의를 포함 | diff 입력 명시 추천 | ___ |
| **[#6] `비즈니스 규칙 검증/정합성 체크` 기능이 별도 책임으로 드러나지 않음**<br>규칙-코드 정합성, 충돌 규칙 탐지, dead rule 후보 탐지가 어느 컴포넌트 책임인지 불명확하다 | `Business Rule Extractor` 책임에 정합성 검사를 포함하거나 `Rule Validator`를 추가 | 우선 기존 컴포넌트 책임 보강 추천 | ___ |
| **[#7] `Structure Analyzer`에 너무 많은 책임이 몰려 있어 `구조 메타데이터 추출` 단계가 사라져 보임**<br>`whole-features.md`에서는 구조 분석이 `컴포넌트/레이어 추출` → `구조 메타데이터 추출` → `아키텍처 관계 분석`으로 나뉜다. 그런데 현재 다이어그램은 `Structure Analyzer` 하나가 `컴포넌트/레이어 식별`, `아키텍처 관계 추출`, `External Integration 분석`까지 함께 맡는 것처럼 보인다. 그 결과 어노테이션, 설정 파일, 의존성 메타데이터, DB 매핑, 엔티티 역할 분류 같은 중간 단계의 메타데이터를 누가 추출하는지가 보이지 않는다 | **옵션 A**: `Structure Analyzer` 설명에 `구조 메타데이터 추출`까지 포함한다고 명시<br>**옵션 B**: `Metadata Extractor`를 별도 컴포넌트로 분리<br>**옵션 C**: 메타데이터 추출 책임이 `Data Processing` 또는 `Knowledge Base` 쪽이라면 그 연결을 명시 | 옵션 A 추천. 우선 현재 컴포넌트 수를 크게 늘리지 않고도 책임 공백을 줄일 수 있다. 이후 메타데이터 활용 범위가 더 커지면 옵션 B로 분리하는 편이 자연스럽다 | ___ |

## 7. C3 Interactive Assistant

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] 사용자 액터가 `Interactive Assistant`에 직접 붙어 있어 `Web Application`이 단일 진입점이라는 기준과 충돌**<br>C2와 `Web Application` C3에서는 사용자가 먼저 `Web Application`에 접속하고, 그 안의 `WebSocket Proxy`가 `Interactive Assistant`로 세션을 중계하는 구조다. 즉 전체 기준은 `사용자 -> Web Application -> Interactive Assistant`다. 그런데 현재 `Interactive Assistant` 다이어그램만 보면 `Developer`, `Reviewer`, `PM/PO`가 `Session Manager`에 직접 붙어 있어 `사용자 -> Interactive Assistant`처럼 읽힌다. note에 `Web Application 경유`라고 적혀 있어도, 관계선 자체는 여전히 직접 연결이라서 웹앱이 아닌 IA에도 별도 사용자 진입점이 있는 것처럼 보인다 | **옵션 A**: 액터 직접 연결을 제거하고 `Web Application`을 외부 참조로 둠<br>**옵션 B**: 더 구체적으로 `WebSocket Proxy`를 외부 참조로 두고 `WebSocket Proxy -> Session Manager`로 수정<br>**옵션 C**: 현재 관계는 유지하되 note만 보강 | 옵션 B 추천. 실제 연결 경로를 가장 정확하게 드러내고 C2 및 `Web Application` C3와도 가장 잘 맞는다 | ___ |
| **[#2] `Context Assembler -> KB`가 `Graph Read`만으로는 부족**<br>실제 기능은 그래프, 벡터, 검색, 오브젝트를 결합한 컨텍스트 검색을 요구한다 | 관계를 `Hybrid Query` 또는 `Graph/Vector/Search/Object Read`로 확장 | `Hybrid Query` 표기 추천 | ___ |
| **[#3] `Gap Analyzer`의 책임 경계가 AE/W&I와 겹쳐 보임**<br>대화형 갭 분석과 배치형 리포트/자동화의 구분이 다이어그램만 보면 약하다 | `Gap Analyzer` 설명에 `대화형 갭 분석`을 명시하고 AE/WI와의 역할 구분 note를 추가 | 경계 설명 보강 추천 | ___ |
| **[#4] `Response Renderer`의 근거 링크 조립 경로가 보이지 않음**<br>근거 링크 제공은 핵심 기능이지만 링크 메타를 누가 전달하는지 드러나지 않는다 | `Context Assembler -> Response Renderer` 관계를 추가하거나, 핸들러 설명에 근거 링크 포함 결과 생성을 명시 | 렌더러 입력 경로 보강 추천 | ___ |
| **[#5] `Explainability Engine`은 설득력 있지만 최신 분석 트리거 경로가 없음**<br>KB에 필요한 분석 결과가 없을 때 어떻게 최신 설명을 보장하는지가 비어 있다 | `Explainability Engine`이 `Analysis Engine`을 직접 호출하지 않는다면, 부족 시 재분석 요청 흐름을 note로 설명 | 운영 흐름 note 추가 추천 | ___ |
| **[#6] `QA Handler`, `Session Manager`, `Response Renderer`가 각각 KB에 쓰는 구조로 저장 책임이 분산**<br>답변, 세션, 피드백 자산의 저장 모델이 한눈에 보이지 않는다 | IA 쪽 쓰기 책임을 정리하거나 KB 문서에서 저장 위치를 명확히 정의 | KB 저장 모델과 함께 다시 정렬 추천 | ___ |

## 8. C3 Knowledge Base

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] `Search Index`의 인덱싱 경로가 빠져 있음**<br>검색 질의는 보이지만 누가 인덱스를 생성·갱신하는지 없다 | `Index Builder` 또는 `Search Projector`를 추가하거나 `Query Facade`가 인덱싱도 맡는다고 명시 | 별도 인덱싱 책임을 두는 방식 추천 | ___ |
| **[#2] `단일 지식 모델`의 주요 자산 일부가 저장 구조 설명에 충분히 드러나지 않음**<br>도메인 용어, 외부 컨텍스트, 사용자 수동 컨텍스트, 교차 참조 구조가 암묵적이다 | `Graph Store` 설명에 주요 자산을 포함하거나 별도 note로 자산 목록을 명시 | 자산 목록을 명시하는 방식 추천 | ___ |
| **[#3] `Interactive Assistant`의 `답변·이력·피드백` 저장 위치가 명확하지 않음**<br>어느 스토어에 대화 이력, 문서화된 답변, Good/Bad 피드백이 저장되는지 불명확하다 | `Graph Store` 또는 별도 `Conversation Store` 성격을 명시 | 저장 모델을 KB 문서에서 명확히 정의 추천 | ___ |
| **[#4] `Retention Manager`가 `Search Index`를 정리하지 않음**<br>원본이 삭제돼도 검색 인덱스에 고아 데이터가 남을 수 있다 | `Retention Manager -> Search Index` 관계를 추가하거나 인덱스 재구축 정책을 note로 명시 | 정리 경로 추가 추천 | ___ |
| **[#5] `Schema Manager`가 Graph만 다루는 것은 타당하지만 Search/Vector 메타 스키마 설명이 부족**<br>검색 인덱스 매핑, 벡터 메타 필드 버전 관리 주체가 드러나지 않는다 | `Schema Manager` 범위를 넓히지 않더라도 운영 note로 각 메타 스키마 관리 주체를 설명 | 운영 설명 보강 추천 | ___ |

## 9. C3 Workflow & Integration

| 논의 사항 | 조치 | 추천 | 결정 |
| --- | --- | --- | --- |
| **[#1] 사용자 액터가 `Workflow & Integration`에 직접 붙어 있어 C2/WebApp 경계와 충돌**<br>현재는 note로만 보정하고 있어 실제 구조 기준선과 어긋난다 | 액터 직접 연결을 제거하고 `Web Application` 또는 `API Router`를 외부 참조로 추가 | 사용자 진입점을 `Web Application`으로 통일 추천 | ___ |
| **[#2] `Event Router`의 입력 정의와 실제 인바운드 관계가 맞지 않음**<br>설명은 `PR/Push/Merge/스케줄` 이벤트를 말하지만 실제 인바운드는 `DevOps Pipeline` 하나뿐이다 | `Scheduler` 또는 `Operations Manager`에서 오는 경로를 추가하고 Push/Merge 이벤트 원천도 명시 | 입력 원천을 분리해 표현 추천 | ___ |
| **[#3] `PR Automation Handler`가 PR 본문을 어디에 쓰는지 빠져 있음**<br>PR 본문 생성은 설명되지만 실제로 GitHub/GitLab PR API 등에 반영하는 write 경로가 없다 | `PR Automation Handler -> Code Hosting / DevOps Platform` write 관계를 추가 | 생성 결과의 write-back 경로 명시 추천 | ___ |
| **[#4] `Docs Studio Engine`도 생성 문서를 어디에 발행하는지 직접 관계가 없음**<br>문서 발행과 버전 관리가 기능에 있지만 실제 외부 시스템 반영 경로가 빠져 있다 | `Docs Studio Engine -> Collaboration Connector` 관계를 추가하거나 외부 발행 책임을 명시 | `Collaboration Connector` 경유 구조 추천 | ___ |
| **[#5] `Notification Dispatcher`가 Web Application으로 푸시하는 경로가 없음**<br>ChatOps와 Collaboration 발송만 보이고 WebApp 실시간 알림 경로가 없다 | `Notification Dispatcher -> Web Application` 또는 `Notification Hub` 관계를 추가 | 알림 흐름 완결을 위해 관계 추가 추천 | ___ |
| **[#6] `Event Router -> Report Generator`는 Notion 설명과 `puml`이 어긋남**<br>문서 설명에는 없는 아웃바운드가 `puml`에 추가돼 있다 | 실제 필요하다면 Notion 설명을 수정하고, 아니면 `puml`에서 관계를 제거 | 기준 문서를 먼저 고른 뒤 둘 중 하나로 정렬 추천 | ___ |
| **[#7] `MCP/API Gateway`의 KB 읽기 범위가 문서 대비 좁음**<br>컨텍스트 패키지, 팀 컨벤션, 유사 구현 탐지 등을 고려하면 `Graph Read`만으로는 부족하다 | `MCP/API Gateway -> KB`를 `Hybrid Query` 수준으로 확장 | KB 접근 표기를 `Hybrid Query`로 통일 추천 | ___ |
| **[#8] `Operations Manager`의 책임이 너무 넓고 실제 연결은 너무 적음**<br>분석 작업 모니터링, 사용자/권한, 시스템 설정, 라이선스 관리가 선언돼 있지만 실제 반영 관계는 제한적이다 | `Operations Manager` 책임을 더 좁히거나, 설정/권한/라이선스가 영향을 주는 대상 관계를 추가 | 우선 책임 설명을 줄이거나 관계를 보강하는 방식 추천 | ___ |
