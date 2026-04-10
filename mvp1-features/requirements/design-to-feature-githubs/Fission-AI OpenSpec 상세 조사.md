# Fission-AI/OpenSpec 상세 조사

- 조사 대상: `Fission-AI/OpenSpec`
- 조사 목적: TCI의 기능 기획을 설계 입력 수준의 문서와 지속 가능한 변경 관리 흐름으로 끌어올릴 수 있는지 검증
- 조사 시점: 2026-04-09 (KST)
- 조사 기준: 공식 저장소, 공식 사이트, 공식 문서, 공식 변경 로그 중심

## 1. 한줄 결론

`Fission-AI/OpenSpec`은 TCI가 원하는 `기획 → 변경 제안 → 요구사항 델타 → 설계 → 작업 분해` 흐름을 가볍게 운영하기에 매우 강한 후보다. 특히 기존 코드베이스 위에서 기능 변경 의도를 명세와 함께 남기는 데 강하다. 다만 기본 워크플로우는 `github/spec-kit`보다 더 가볍고 유연한 대신, `clarify`, `research`, `data-model`, `contracts`처럼 설계 착수 전 검토 항목을 강하게 강제하지는 않는다. 따라서 TCI에 바로 맞추기보다는 custom schema를 전제로 도입하는 편이 맞다

출처: [README](https://github.com/Fission-AI/OpenSpec/blob/main/README.md), [OpenSpec 공식 사이트](https://openspec.dev/), [Getting Started](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md), [Concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md), [Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md)

참고: 아래 문서의 적합성 판단과 도입 권고는 upstream 문서의 직접 진술이 아니라 TCI 관점의 해석을 포함한다

## 2. 왜 TCI에 맞는가

### 2.1 기본 흐름이 "기획 후 설계 입력 정리"에 잘 맞는다

OpenSpec의 기본 quick path는 `propose → apply → archive`이고, 확장 워크플로우에서는 `new → continue 또는 ff → apply → verify → archive`로 운영된다. 핵심은 구현 전에 `proposal.md`, delta spec, `design.md`, `tasks.md`를 먼저 만든다는 점이다

TCI 관점에서 보면 이 구조는 "기능 아이디어를 바로 코드로 넘기지 않고, 변경 의도와 요구사항, 기술 접근, 작업 분해를 먼저 정리한다"는 목적과 잘 맞는다

출처: [README](https://github.com/Fission-AI/OpenSpec/blob/main/README.md), [Getting Started](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md), [OPSX Workflow](https://github.com/Fission-AI/OpenSpec/blob/main/docs/opsx.md)

### 2.2 brownfield-first와 delta spec 개념이 TCI에 특히 유용하다

OpenSpec은 기존 시스템의 현재 동작을 `openspec/specs/`에 두고, 변경 사항은 `openspec/changes/<change>/specs/` 안의 delta spec으로 관리한다. delta spec은 `ADDED`, `MODIFIED`, `REMOVED` 요구사항 섹션으로 바뀌는 지점만 표현한다

TCI 입장에서는 이 점이 중요하다. TCI가 다룰 기능 중 상당수는 "새 시스템 백지 설계"보다 기존 도구 연동, 기존 기능 수정, 기존 문서-코드 관계 보강에 가깝다. OpenSpec의 델타 중심 구조는 이런 변경형 작업을 문서화하기에 적합하다

출처: [OpenSpec 공식 사이트](https://openspec.dev/), [Getting Started](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md), [Concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md)

### 2.3 산출물 묶음이 작지만 실전적이다

OpenSpec change 폴더는 기본적으로 아래 묶음을 만든다

- `proposal.md`
- `design.md`
- `tasks.md`
- `specs/` 아래 delta spec

이 조합은 `spec-kit`보다 작지만, 실제 기능 변경을 리뷰하고 구현 착수 여부를 판단하는 데 필요한 최소 세트를 갖춘다. 특히 proposal과 spec delta를 분리해 두는 방식은 "왜 바꾸는지"와 "무엇이 바뀌는지"를 분리해 읽게 해준다

출처: [README](https://github.com/Fission-AI/OpenSpec/blob/main/README.md), [Getting Started](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md), [Concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md)

### 2.4 TCI 맞춤형으로 바꾸기 쉽다

공식 문서는 OpenSpec의 주요 강점 중 하나로 project config와 custom schema를 제시한다. `openspec/config.yaml`로 프로젝트 컨텍스트와 artifact별 규칙을 주입할 수 있고, `openspec/schemas/` 아래에서 workflow와 template 자체를 fork해서 바꿀 수 있다

TCI 입장에서는 이 점이 매우 실용적이다. 기본 OpenSpec이 부족한 `research`, `readiness-check`, `review`, `data-model` 같은 산출물을 schema 수준에서 추가할 수 있기 때문이다

출처: [Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md), [Concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md), [OPSX Workflow](https://github.com/Fission-AI/OpenSpec/blob/main/docs/opsx.md)

## 3. TCI 기준 장점

- 기존 코드베이스 변경을 문서화하는 brownfield-first 접근이 분명하다
- spec을 저장소 안의 source of truth로 유지해 문맥이 채팅 세션에만 남지 않는다
- `proposal`, delta spec, `design`, `tasks`로 기능 변경 리뷰에 필요한 최소 묶음이 잘 잡혀 있다
- `openspec init`과 Node 기반 설치 구조 덕분에 도입 장벽이 낮다
- 공식 사이트가 `No API Keys`, `No MCP`, 다중 도구 지원을 내세워 운영 제약이 적다
- Codex를 포함한 여러 코딩 에이전트 환경을 공식 지원한다
- project config와 custom schema로 TCI 전용 산출물 구조를 설계하기 쉽다
- changelog와 최근 커밋 기준으로 프로젝트 활동성이 높다

출처: [OpenSpec 공식 사이트](https://openspec.dev/), [README](https://github.com/Fission-AI/OpenSpec/blob/main/README.md), [Supported Tools](https://github.com/Fission-AI/OpenSpec/blob/main/docs/supported-tools.md), [Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md), [CHANGELOG](https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md), [최근 커밋 예시 2026-04-09](https://github.com/Fission-AI/OpenSpec/commit/7fd5417ed01b7b035782561c14ef731117fddaff)

## 4. TCI 기준 리스크와 한계

- 기본 워크플로우만 보면 설계 착수 전 정제 강도가 `github/spec-kit`보다 약하다
- `clarify`, `research.md`, `data-model.md`, `contracts/` 같은 구조가 기본 제공되지 않는다
- "fluid not rigid" 철학은 장점이지만, 반대로 보면 품질 게이트를 팀이 직접 설계해야 한다
- delta spec 중심 구조는 변경 관리에는 좋지만, 상위 문제 정의나 긴 기술 설계 패키지에는 추가 템플릿이 필요하다
- 공식 문서가 빠르게 진화하고 있어 버전 고정과 schema 관리 정책이 필요하다

조금 더 구체적으로 보면 아래와 같다

- TCI가 원하는 "설계 착수 가능 여부 판단"은 OpenSpec 기본 명령 자체보다 template와 review 규칙으로 보완해야 한다
- 기본 artifact 세트는 작아서, API 계약이나 데이터 모델 정리가 중요한 기능에는 문서 공백이 생길 수 있다
- 유연한 구조는 숙련된 팀에는 좋지만, 초기에 운영 원칙이 없으면 artifact 품질 편차가 커질 수 있다
- 현재 공식 package 버전은 `1.2.0`이고, 메인 브랜치 커밋도 2026-04-09까지 활발히 이어지고 있어, upstream 추종 시 변경 관리가 필요하다

출처: [README](https://github.com/Fission-AI/OpenSpec/blob/main/README.md), [Concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md), [Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md), [CHANGELOG 1.2.0](https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md), [package.json](https://github.com/Fission-AI/OpenSpec/blob/main/package.json), [최근 커밋 예시 2026-04-09](https://github.com/Fission-AI/OpenSpec/commit/7fd5417ed01b7b035782561c14ef731117fddaff)

## 5. 권장 도입 방식

### 권장 원칙

- OpenSpec 기본 구조를 그대로 쓰지 말고 TCI 전용 schema를 만든다
- 초도 도입은 `apply`보다 `proposal/specs/design/tasks` 품질 검증에 집중한다
- 초기에는 `explore` 또는 `propose`를 사용하되, 구현 자동화는 후순위로 둔다
- 설계 착수 판단을 위해 `review` 또는 `readiness-check` artifact를 추가하는 편이 좋다
- upstream main을 그대로 추적하기보다 버전 고정 후 주기적으로 업데이트 검토하는 편이 안전하다

### TCI 문서 체계와의 매핑

| TCI 목적 | OpenSpec 대응 | 비고 |
| --- | --- | --- |
| 기능 의도와 범위 정리 | `proposal.md` | why, scope, approach 정리 |
| 변경 요구사항 명세화 | delta spec | `ADDED`, `MODIFIED`, `REMOVED` 요구사항 구조 |
| 기술 설계 입력 작성 | `design.md` | 기술 접근과 의사결정 정리 |
| 실행 단위 분해 | `tasks.md` | 체크리스트 기반 구현 단위 분해 |
| 설계 착수 가능 여부 판단 | custom artifact 추가 권장 | 기본 제공보다 `review.md` 또는 `readiness-check.md`가 더 적합 |
| 기존 시스템 기준선 유지 | `openspec/specs/` | 현재 시스템 동작의 source of truth |

출처: [Getting Started](https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md), [Concepts](https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md), [Customization](https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md)

### 파일럿 권장 범위

OpenSpec은 아래 같은 기능에 먼저 붙여보는 편이 좋다

- 기존 기능 변경이 많은 연동 기능
- 설계보다 변경 영향 추적이 중요한 기능
- 문서-코드 간 의도 차이를 줄여야 하는 기능
- TCI 안에서 반복적으로 사양 변경이 생기는 기능

예시:

- GitHub 연동 동작 보강
- 티켓 시스템 상태 동기화 규칙 변경
- 문서-코드 불일치 탐지 규칙 추가
- 기존 워크플로우에 설계 검증 단계를 삽입하는 기능

권장 절차는 아래와 같다

1. `openspec init` 후 TCI 프로젝트 컨텍스트를 `openspec/config.yaml`에 반영
2. `spec-driven` schema를 fork해서 `tci-design-input` 같은 커스텀 schema 생성
3. 필요 시 `research`, `review`, `data-model` artifact 추가
4. 파일럿 기능 하나를 `proposal → delta spec → design → tasks`로 작성
5. `apply`는 보류하고 결과를 TCI의 설계 착수 판단 문서와 함께 검토
6. 품질이 만족스러우면 이후에만 `verify`와 `archive`를 운영 흐름에 편입

## 6. 최종 판단

`Fission-AI/OpenSpec`은 "가볍지만 지속 가능한 spec-driven 변경 관리 레이어"로 보면 매우 강한 후보다. 특히 아래 세 가지가 TCI에 잘 맞는다

- 기존 코드베이스 변경을 delta spec으로 다루는 구조가 분명하다
- proposal, spec, design, tasks를 한 change 폴더에 묶어 리뷰하기 쉽다
- custom schema로 TCI 전용 산출물 체계로 바꾸기 쉽다

반면 기본 형태 그대로는 `github/spec-kit`만큼 설계 전 정제 강도가 높지 않다. 따라서 결론은 아래와 같다

- 도입 가치 높음
- 기본형 그대로보다 TCI 맞춤 schema 전제
- lightweight 운영 레이어로는 매우 적합
- 깊은 설계 패키지 생성은 추가 artifact 설계가 필요

## 7. 참고 링크

- 저장소: https://github.com/Fission-AI/OpenSpec
- 공식 사이트: https://openspec.dev/
- README: https://github.com/Fission-AI/OpenSpec/blob/main/README.md
- Getting Started: https://github.com/Fission-AI/OpenSpec/blob/main/docs/getting-started.md
- OPSX Workflow: https://github.com/Fission-AI/OpenSpec/blob/main/docs/opsx.md
- Concepts: https://github.com/Fission-AI/OpenSpec/blob/main/docs/concepts.md
- Customization: https://github.com/Fission-AI/OpenSpec/blob/main/docs/customization.md
- Supported Tools: https://github.com/Fission-AI/OpenSpec/blob/main/docs/supported-tools.md
- Installation: https://github.com/Fission-AI/OpenSpec/blob/main/docs/installation.md
- Workflows: https://github.com/Fission-AI/OpenSpec/blob/main/docs/workflows.md
- CHANGELOG: https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md
- 최신 공개 버전 `1.2.0`: https://github.com/Fission-AI/OpenSpec/blob/main/CHANGELOG.md
- `package.json`: https://github.com/Fission-AI/OpenSpec/blob/main/package.json
- 최근 커밋 예시 2026-04-09: https://github.com/Fission-AI/OpenSpec/commit/7fd5417ed01b7b035782561c14ef731117fddaff
