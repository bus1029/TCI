# 결론

Agent 개발에서는 Feature를 기존처럼 “개발자별 모듈 소유권” 기준으로 잡으면 병목이 커진다. Agent는 좁은 코드 수정은 빠르지만, 넓은 맥락 추론, 숨은 의존성 판단, 장기 상태 기억, 충돌 해결, 애매한 완료 기준에서 쉽게 느려진다. 따라서 Feature는 모듈 단위가 아니라 “하나의 사용자 가치 또는 운영 가치가 끝까지 검증되는 완결 기능 단위”로 잡아야 한다.

TCI 최종 기능 리스트 기준으로는 “코드 저장소 연동”, “티켓 시스템 연동”, “기술 스택 분석”, “영향 분석”, “대화형 질의 응답” 같은 큰 기능명을 그대로 개발 단위로 쓰면 너무 크다. 이들은 Epic 또는 Capability로 두고, 실제 Agent가 작업할 Feature는 입력, 처리, 저장, API 또는 UI, 검증 증거가 한 단위 안에 들어오도록 쪼갠다.

# 기본 원칙

## Feature는 완결 기능 단위로 잡는다

전통적인 개발에서는 백엔드, 프론트엔드, DB, 배치, 인프라처럼 가로로 나눠도 사람이 계속 회의와 기억으로 연결할 수 있었다. Agent 개발에서는 이 방식이 컨텍스트 누락과 통합 대기 시간을 만든다.

Feature는 가능한 한 다음 흐름을 한 단위에서 검증할 수 있게 잡는다.

```text
입력 이벤트 또는 사용자 행동
→ 도메인 판단
→ 저장 또는 분석 결과 생성
→ 조회 API 또는 화면 노출
→ 테스트와 증거
```

예를 들어 “코드 저장소 연동”은 하나의 Feature가 아니라 다음처럼 나눈다.

- GitHub 저장소 연결 생성
- GitLab Self-Managed 저장소 연결 생성
- 연결 후보 조회와 선택
- Webhook Push 이벤트 수신
- 저장소 기준 코드 스냅샷 생성
- 스냅샷 상세 조회
- 멀티 레포지토리 목록과 상태 표시

각 Feature는 독립적으로 테스트할 수 있어야 하고, 다음 Feature가 그 결과를 믿고 이어받을 수 있어야 한다.

## Agent 작업 단위는 작고 끝이 보여야 한다

Agent에게 좋은 작업 단위는 “2시간에서 1일 안에 구현, 리뷰, 검증, 문서 갱신까지 끝낼 수 있는 완결 기능 단위”다. 기능 자체가 크면 Epic은 유지하되 Agent Task로 내려가기 전에 반드시 더 작게 자른다.

좋은 작업 단위의 조건은 다음과 같다.

- 변경할 파일 범위 예측 가능
- 입력과 출력 계약이 명확
- 실패 조건과 에러 응답이 명확
- 검증용 예제 데이터와 기대 결과를 만들 수 있음
- 완료 증거를 문서에 남길 수 있음
- 다른 Agent의 쓰기 범위와 겹치지 않음

일반적인 나쁜 작업 단위는 다음과 같다.

- “영향 분석 기능 구현”
- “지식 모델 전체 개발”
- “자연어 질의 응답 백엔드 만들기”
- “데이터 수집 모듈 리팩터링”
- “문서 시스템 연동 전반”

좋은 작업 단위는 입력과 출력이 분명한 형태다.

- “PR Diff 입력을 받아 변경 파일 목록을 정규화해 저장”
- “변경 파일 기준 직접 호출 관계 영향 대상 조회 API 추가”
- “비즈니스 규칙 추출 결과를 규칙 카탈로그 테이블에 저장”
- “질의 응답 결과에 코드 위치 근거를 포함해 반환”
- “Confluence 문서 메타데이터를 수집하고 저장”

## Feature마다 계약을 먼저 고정한다

Agent 생산성은 구현 속도보다 재작업을 얼마나 줄이느냐에 더 크게 좌우된다. 따라서 SpecKit에서 Feature를 시작할 때는 먼저 계약을 고정한다.

계약은 다음 중 하나 이상이어야 한다.

- API 요청과 응답
- DB 상태 변화
- 이벤트 payload
- 파일 또는 스냅샷 manifest
- UI 상태와 사용자 행동
- CLI 명령 입력과 출력
- 분석 결과 JSON schema
- 운영자가 확인할 수 있는 evidence 항목

계약이 없는 Feature는 Agent마다 해석이 달라지고, 통합 시점에 충돌이 난다.

## 병렬화는 코드 영역이 아니라 쓰기 범위로 한다

Agent 시대의 병렬 개발은 “사람 A는 백엔드, 사람 B는 프론트엔드”보다 “Agent 1은 수집 계약, Agent 2는 분석 read model, Agent 3은 UI 조회 화면”처럼 쓰기 범위를 분리하는 편이 낫다. 같은 파일을 여러 Agent가 고치면 속도 이점보다 충돌 해결 비용이 커진다.

병렬화 기준은 다음 순서로 잡는다.

- 서로 다른 bounded context
- 서로 다른 데이터 출처 adapter
- 서로 다른 read model 또는 projection
- 서로 다른 화면 또는 operator flow
- 서로 다른 검증용 예제 데이터

공통 domain model, migration, core service, shared schema 변경이 있으면 병렬 작업 전에 별도 기반 단위로 먼저 끝낸다.

# 권장 Feature 계층

TCI 기능 리스트는 기본적으로 다음 4단계로 관리하는 것이 적합하다.

```text
Product Theme
→ Capability
   ├─ 기반 단위
   │  → Agent Task
   └─ Agent 완결 기능 단위
      → Agent Task
```

기반 단위는 Capability 아래에서 Agent 완결 기능 단위와 같은 레벨에 둔다. 다만 사용자 흐름을 직접 끝내는 단위가 아니라, 여러 완결 기능 단위가 의존하는 공통 기반을 먼저 만드는 예외 경로다.

## Product Theme

제품 관점의 큰 축이다. 최종 기능 리스트의 2단계 제목이 여기에 가깝다.

- 데이터 수집
- 시스템 구조 분석
- 구조 시각화 및 진단
- 데이터 흐름 및 로직 분석
- 지식 자산화
- 영향도 분석
- 자연어 질의
- 워크플로우 자동화
- 외부 연동

Product Theme는 브랜치나 Agent 작업 단위로 쓰지 않는다. 로드맵, 우선순위, 제품 설명 단위로만 쓴다.

## Capability

사용자가 인식할 수 있는 기능 묶음이다. 최종 기능 리스트의 3단계 또는 4단계 기능명이 여기에 해당한다.

예시는 다음과 같다.

- 코드 저장소 연동
- 데이터소스 스냅샷 관리
- 변경 영향 분석
- 대화형 질의 응답

Capability는 하나의 SpecKit feature가 될 수도 있지만, TCI처럼 기능이 큰 제품에서는 대부분 너무 크다. Capability는 여러 Agent 완결 기능 단위를 묶는 부모로 쓰는 편이 안전하다.

## 기반 단위

기반 단위는 사용자 흐름을 직접 완성하지는 않지만, 여러 완결 기능 단위가 공유하는 기반 계약을 먼저 고정하는 작업이다. 완결 기능 단위 원칙의 예외이므로 남용하면 안 된다.

기반 단위로 둘 수 있는 작업은 다음과 같다.

- 공통 source kind 모델
- 스냅샷 manifest 공통 계약
- 코드 속성 그래프 node와 edge 저장 계약
- 공통 민감 정보 처리 정책

기반 단위는 후속 Feature가 바로 사용할 계약, 검증용 예제 데이터, migration, 문서 증거를 남겨야 한다. 단순한 추상화나 미래 확장을 위한 설계 작업은 기반 단위로 잡지 않는다.

## Agent 완결 기능 단위

Agent가 실제로 구현하고 검증할 수 있는 단위다. 하나의 완결 흐름을 만든다.

예시는 다음과 같다.

- GitHub 저장소 연결 생성과 연결 상태 조회
- 코드 스냅샷 manifest 생성과 상세 조회
- Maven 프로젝트의 기술 스택 감지 결과 저장
- 질의 응답 결과에 근거 코드 위치 포함

Agent 완결 기능 단위는 하나의 브랜치와 하나의 SpecKit task 묶음으로 관리하기 좋다.

## Agent Task

완결 기능 단위 안에서 Agent가 수행하는 구체 작업이다. TDD와 리뷰 루프를 돌릴 수 있어야 한다.

예시는 다음과 같다.

- 실패 테스트 추가
- migration 추가
- domain service 구현
- API contract test 추가

Task는 너무 작아도 overhead가 커진다. 하지만 Task가 여러 도메인 결정을 동시에 요구하면 Agent가 길을 잃기 쉽다.

# SpecKit 기반 개발 흐름

## 0단계 작업 규모 판단

모든 작업에 같은 수준의 SpecKit 절차를 적용하지 않는다. Agent 개발의 생산성은 절차를 많이 만드는 데서 나오지 않고, 작업의 위험도와 불확실성에 맞는 최소 절차를 고르는 데서 나온다.

작업 규모는 다음처럼 나눈다.

- 즉시 실행 작업
  - 오탈자, 문구 수정, 단일 테스트 수정, 단순 로그 추가
  - issue 수준의 명확한 지시와 검증 명령만으로 처리
- 계획 작업
  - 여러 파일 변경, 낯선 코드 영역, 기존 패턴 확인이 필요한 작업
  - 읽기 전용 탐색과 간단한 plan을 먼저 작성한 뒤 구현
- Spec 작업
  - 신규 Capability, 데이터 모델 변경, 보안 경계, 외부 계약, 여러 팀이 의존하는 기능
  - SpecKit의 spec, plan, tasks 흐름을 적용
- 탐색 작업
  - 구현보다 조사, 구조 파악, 리스크 확인이 목적인 작업
  - 코드 변경 없이 조사 결과와 추천 경로만 남김

한 문장으로 diff를 설명할 수 있는 작업은 큰 spec 절차 없이 처리할 수 있다. 반대로 도메인 판단, 데이터 계약, 권한, 보안, 여러 시스템 간 영향이 들어가면 Spec 작업으로 승격한다.

## 1단계 기능 접수

기능 요청이 들어오면 먼저 Product Theme와 Capability를 확인한다. 그다음 Agent 완결 기능 단위로 줄일 수 있는지 판단한다.

기능 접수에서 답해야 할 질문은 다음과 같다.

- 이 요청은 즉시 실행 작업, 계획 작업, Spec 작업, 탐색 작업 중 무엇인가
- 이 Feature가 다루는 사용자 또는 운영자 행동은 무엇인가
- 입력과 출력은 무엇인가
- 어떤 데이터 계약을 새로 만들거나 바꾸는가
- 어떤 기존 Feature를 깨뜨릴 수 있는가
- 어떤 예제 데이터와 기대 결과로 검증할 수 있는가
- 어떤 파일과 모듈을 주로 수정할 것인가
- 병렬 작업과 충돌할 공통 파일은 무엇인가

좋은 issue는 좋은 Agent prompt이기도 하다. 기능 접수 문서는 Agent가 바로 작업에 들어갈 수 있도록 배경, 목표, 범위 밖 항목, 검증 명령, 주의할 기존 패턴을 포함해야 한다. 모호한 issue는 사람이 읽어도 대화로 보완할 수 있지만, Agent에게는 잘못된 구현을 빠르게 만들게 하는 입력이 된다.

## 2단계 Spec 작성

Spec은 Agent가 해석할 수 있을 만큼 구체적이어야 한다. 모호한 문장은 사람에게는 쉬워 보여도 Agent에게는 재작업 원인이 된다.

Spec에는 최소한 다음을 포함한다.

- 사용자 시나리오
- 성공 기준
- 실패 기준
- 권한과 보안 조건
- 민감 정보 처리 기준
- 기존 기능 호환성 조건
- 수용 테스트 관점
- 범위 밖 항목

## 3단계 Plan 작성

Plan은 구현 설계보다 작업 경계에 더 집중해야 한다. Agent 병목을 줄이려면 “무엇을 만들지”만큼 “어디를 건드리지 않을지”가 중요하다.

Plan에는 최소한 다음을 포함한다.

- 데이터 모델 변경
- API 또는 이벤트 계약
- 쓰기 범위
- 읽기 전용 참고 범위
- migration 전략
- worker 또는 queue 영향
- UI 영향
- 기존 회귀 테스트 범위
- 운영 evidence 방식

## 4단계 Task 분해

Task는 TDD와 리뷰 루프가 가능한 순서로 둔다.

권장 순서는 다음과 같다.

- 계약 테스트 또는 실패 테스트
- 데이터 모델과 migration
- domain service
- persistence
- API 또는 worker entrypoint
- UI 또는 operator flow
- regression test
- 문서와 evidence
- handoff

공통 기반 Task는 병렬화하지 않는다. 공통 기반이 끝난 뒤 adapter, UI, report, 검증용 예제 데이터를 병렬화한다.

## 5단계 구현과 리뷰 루프

구현은 한 번에 끝내는 방식이 아니라 짧은 루프로 운영한다.

```text
RED: 실패 테스트 또는 명시된 acceptance gap 생성
GREEN: 최소 구현
REVIEW: 코드 리뷰, 보안 리뷰, 타입 또는 테스트 리뷰
FIX: findings 수정
EVIDENCE: 실행 결과와 남은 리스크 기록
HANDOFF: 다음 Agent가 이어받을 현재 상태 기록
```

Agent가 달라도 이 루프와 산출물 형식은 같아야 한다. 그래야 모델 선택이 달라도 팀 전체의 개발 방식은 흔들리지 않는다.

# Feature 크기 판단 기준

## 적절한 Feature

다음 조건을 대부분 만족하면 적절한 크기다.

- 한 문장으로 사용자 가치 설명 가능
- 핵심 acceptance test 3개에서 8개
- 주요 쓰기 파일 10개 이하 예상
- migration 1개 이하
- 외부 시스템 adapter 1개 이하
- UI 화면 1개 또는 API group 1개 이하
- 회귀 테스트 범위가 명확
- 실패 시 rollback 또는 재시도 기준 명확

기반 단위는 예외적으로 사용자 흐름을 직접 완성하지 않을 수 있다. 대신 후속 Feature가 의존할 계약과 회귀 테스트가 명확해야 하고, 한 번에 하나의 공통 기반만 바꿔야 한다.

## 너무 큰 Feature

다음 신호가 있으면 더 쪼갠다.

- “전체”, “전반”, “통합”, “고도화” 같은 단어가 제목에 들어감
- 분석, 저장, UI, 리포트, 자동화를 한 번에 포함
- 여러 외부 시스템을 동시에 연결
- 여러 데이터 모델의 소유권을 동시에 바꿈
- 기대 결과가 포함된 검증용 예제 데이터를 만들기 어려움
- 구현 전 질문이 5개 이상 남음
- 한 Agent가 repo 전체를 계속 읽어야 함

## 너무 작은 Feature

다음 신호가 있으면 인접 Task와 합친다.

- 사용자 또는 운영자 가치가 전혀 드러나지 않음
- 테스트 없이 타입 하나만 추가
- migration만 있고 읽고 쓰는 경로가 없음
- API field만 추가하고 실제 사용 경로가 없음
- 문서 한 줄 수정이 별도 브랜치가 됨

# 병목을 줄이는 팀 규칙

## 공통 Harness 규칙

팀이 Agent와 모델을 자유롭게 선택하더라도 Harness는 다음을 강제해야 한다.

- SpecKit artifact 위치와 이름
- 완결 기능 단위 명명 규칙
- task status 형식
- acceptance test 형식
- evidence 기록 방식
- 민감 정보 처리 규칙
- handoff 형식
- reviewer loop 기준
- commit scope 기준

Agent 선택 자유는 실행 도구의 자유여야 한다. 산출물 형식까지 자유롭게 두면 통합 비용이 다시 사람에게 돌아온다.

## 브랜치 규칙

브랜치는 모듈이 아니라 완결 기능 단위 또는 기반 단위 기준으로 딴다.

권장 형식은 다음과 같다.

```text
NNN-capability-unit-name
```

예시는 다음과 같다.

- `010-repository-snapshot-manifest`
- `011-local-upload-snapshot`
- `020-stack-detection-maven`
- `031-impact-direct-dependency-api`

브랜치가 여러 Capability를 포함하면 크기가 큰 것이다. 반대로 한 Capability 안의 여러 완결 기능 단위는 순서와 의존성을 SpecKit tasks에서 관리한다. 기반 단위 브랜치는 후속 Feature가 의존하는 공통 계약 하나만 포함한다.

## 소유권 규칙

각 완결 기능 단위는 쓰기 소유권을 명시한다.

예시는 다음과 같다.

- `src/tci/domain/services/create_local_upload_snapshot.py`
- `src/tci/infrastructure/persistence/local_upload_repository.py`
- `tests/unit/local_uploads/`
- `specs/NNN-local-upload-snapshot/`

공유 파일을 수정해야 한다면 Plan에 이유를 적고, 같은 시점의 다른 Agent 작업과 겹치지 않게 한다.

## Evidence 규칙

Feature는 merge 가능한 코드가 아니라 재현 가능한 증거까지 포함해야 끝난다.

Evidence에는 다음을 남긴다.

- 실행한 테스트 명령
- 통과 또는 실패 결과
- 실패 시 원인과 다음 조치
- operator rehearsal 필요 여부
- 민감 정보 처리 확인
- 남은 리스크
- 다음 Feature가 의존해도 되는 계약

TCI처럼 외부 연동, 코드 스냅샷, 분석 결과, Agent 컨텍스트를 다루는 제품은 evidence 없이 완료 처리하면 다음 Agent가 잘못된 전제를 이어받기 쉽다.

## 테스트 품질 규칙

Agent가 만든 테스트는 양보다 검증력으로 판단한다. 테스트 파일이 늘어났다는 사실만으로 품질이 올라갔다고 보지 않는다.

테스트 작성 기준은 다음과 같다.

- 핵심 도메인 판단은 실제 domain service 테스트로 검증
- 외부 시스템 경계는 contract test 또는 adapter 예제 데이터로 검증
- persistence와 queue 경계는 integration test로 최소 1개 이상 검증
- mock은 외부 네트워크, 시간, 난수, 비싼 API 비용을 끊을 때만 우선 사용
- 구현 세부사항을 그대로 따라가는 mock은 피함
- 테스트가 실패할 때 어떤 사용자 가치나 운영 리스크를 막는지 설명 가능해야 함

Agent는 통과하기 쉬운 테스트를 만들 수 있다. 그래서 reviewer는 테스트가 실제 상호작용을 검증하는지, 과도한 mock으로 실패 가능성을 숨기지 않는지 확인해야 한다.

## 리뷰 병목 규칙

Agent 도입 후 병목은 코드 작성에서 리뷰, 검증, 시스템 이해로 이동한다. 팀은 구현 속도보다 검토 가능성을 먼저 설계해야 한다.

리뷰 병목을 줄이는 기준은 다음과 같다.

- PR은 하나의 완결 기능 단위 또는 기반 단위만 포함
- PR 본문에 변경 의도, 검증 명령, 남은 리스크, 관련 spec/task 링크 포함
- 리뷰어가 봐야 할 파일과 보지 않아도 되는 파일 구분
- 대량 기계 변경은 생성 규칙과 샘플 검토 범위 명시
- 보안, 권한, 데이터 삭제, 인증 정보, 외부 webhook은 별도 reviewer checklist 적용

리뷰가 느린 이유가 코드 양인지, 계약 불명확성인지, 테스트 신뢰 부족인지 구분한다. 원인을 구분하지 않으면 Agent 병렬화가 오히려 검토 대기열만 늘린다.

# 운영 결론

Agent 시대의 생산성은 Agent를 많이 쓰는 데서 나오지 않는다. Feature를 Agent가 실패하기 어려운 모양으로 자르고, 같은 Harness 위에서 같은 증거를 남기게 할 때 나온다.

TCI에서는 최종 기능 리스트의 큰 기능명을 바로 브랜치로 만들지 말고, Product Theme와 Capability로 보관한다. 실제 개발은 Agent 완결 기능 단위로 진행한다. 각 단위는 계약, 쓰기 범위, 테스트, evidence, handoff가 갖춰져야 완료다. 이 기준을 지키면 Agent와 모델 선택은 각자 달라도 팀 전체 개발 방식은 일관되게 유지된다.

# 부록 TCI 기능 리스트 기준 분해안

이 부록은 위 방법론을 TCI 최종 기능 리스트에 적용한 예시다. 실제 개발 순서는 제품 우선순위, 선행 계약, 팀 가용성에 따라 조정한다.

| 단계 | 우선 Capability | 기반 계약 | 개발 후보 |
| --- | --- | --- | --- |
| 1. 데이터 수집 기반 | 코드 저장소 연동, 파일 업로드 관리, 데이터소스 스냅샷 관리, 인증 정보 관리 등 | Source kind 공통 모델, Snapshot manifest 공통 계약, 인증 정보 처리 기준, 데이터소스 상태 enum과 오류 코드 | Repository Connection 생성과 검증, Repository Snapshot 조회, Local Upload ZIP Snapshot, 인증 정보 등록/삭제/민감 정보 처리 |
| 2. 구조 분석 기반 | 기술 스택 분석, 컴포넌트 구조 분석, 코드 메타데이터 생성, 아키텍처 관계 분석 등 | 기술 스택 감지 결과 schema, 컴포넌트 식별 결과 schema, 호출 관계 edge schema | Maven/Gradle/npm/Python adapter, signature 추출 read model, 레이어 분류, 호출 관계 edge 생성 |
| 3. 지식 모델과 영향 분석 | 코드 속성 그래프, 도메인 용어 사전, 지식 모델, 객체/변경/테스트/리스크 분석 | CPG node/edge 저장 계약, 영향 경로 조회 응답 schema, 정확도 평가용 예제 데이터 형식 | symbol 직접 의존 조회, object 역방향 영향 조회, PR Diff 정규화, 영향 API 목록 |
| 4. 자연어 질의와 문서 자동화 | 컨텍스트 검색, 답변 근거, 대화형 질의, AI 컨텍스트 번들, 문서 자동화 등 | 답변 근거 schema, 컨텍스트 번들 schema, 권한 필터 기준 | 질의 범위 선택, context retrieval, 답변 근거 링크, PR Diff 요약 |
| 5. 외부 Agent Harness와 거버넌스 | AI 에이전트 컨텍스트 제공, Policy Gate, CI 연동, 분석 자동화, 답변 평가 | `AGENTS.md` 운영 규칙, SpecKit 템플릿, acceptance/evidence/handoff/reviewer/민감 정보 처리 형식, command runner, Agent 컨텍스트 번들 schema | MCP context bundle, 유사 구현 위치 탐색, Policy Gate 리포트, CI 분석 job |

데이터 수집은 모든 분석의 입력이므로 먼저 안정화한다. 티켓 시스템과 문서 시스템도 한 번에 전체 연동하지 말고, 메타데이터 수집과 본문 수집을 나눠야 한다.

구조 분석은 대표 stack 하나를 end-to-end로 검증한 뒤 adapter를 늘린다. 처음부터 모든 언어와 framework를 일반화하려 하면 parser, graph model, UI가 동시에 흔들린다.

자연어 질의와 문서 자동화는 “좋은 답변”보다 “근거 있는 답변”을 먼저 검증한다. 답변 품질 평가는 검색 가능한 컨텍스트, 근거 링크, 권한 필터가 안정된 뒤 붙인다.

# 부록 Agent 운영 참고

Agent와 모델 선택은 개인에게 맡길 수 있지만, 선택 결과는 팀이 학습할 수 있어야 한다. 팀은 작업 유형별로 잘 맞는 도구를 경험 기반으로 갱신한다.

- 문서 정리와 요약
- 단순 버그 수정
- 신규 기능 구현
- 보안 리뷰

실패한 Agent 선택도 기록한다. 어떤 Agent가 실패했는지가 아니라 어떤 작업 조건에서 실패했는지가 다음 분해 기준을 개선한다.

새 세션을 여는 기준은 다음과 같다.

- 다른 기능이나 다른 완결 기능 단위로 이동
- Agent가 같은 실수를 반복
- 현재 작업의 구현과 검증이 끝남
- 대화가 길어져 이전 결정과 현재 파일 상태가 섞임

새 세션에는 전체 대화를 넘기지 않는다. 대신 현재 목표, 변경 파일, 검증 명령, 남은 리스크, 참고해야 할 spec/task/handoff만 넘긴다.

# 참고 자료

- [Anthropic Claude Code best practices](https://code.claude.com/docs/en/best-practices)
- [GitHub Copilot task best practices](https://docs.github.com/en/enterprise-cloud%40latest/copilot/tutorials/cloud-agent/get-the-best-results)
- [Cursor agent best practices](https://cursor.com/blog/agent-best-practices)
- [OpenAI Codex usage guide](https://openai.com/business/guides-and-resources/how-openai-uses-codex/)
- [GitHub Spec Kit integrations](https://github.com/github/spec-kit/blob/main/docs/reference/integrations.md)
- [Microsoft Spec Kit guide](https://developer.microsoft.com/blog/spec-driven-development-spec-kit)
- [Thoughtworks AI and software delivery](https://www.thoughtworks.com/insights/looking-glass/looking-glass-2026/AI-and-software-delivery)
- [Shopify AI-first engineering summary](https://www.bvp.com/assets/uploads/2026/04/Shopifys-strategy-for-AI-first-engineering-1.pdf)
- [AI coding agent task-stratified study](https://arxiv.org/abs/2602.08915)
- [Agent-generated test and mocking study](https://arxiv.org/abs/2602.00409)
