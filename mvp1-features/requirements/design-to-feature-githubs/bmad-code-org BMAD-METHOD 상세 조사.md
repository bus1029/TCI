# bmad-code-org/BMAD-METHOD 상세 조사

- 조사 대상: `bmad-code-org/BMAD-METHOD`
- 조사 목적: TCI의 기능 기획을 설계 입력 수준의 문서와 실행 흐름으로 끌어올릴 수 있는지 검증
- 조사 시점: 2026-04-09 (KST)
- 조사 기준: 공식 저장소, 공식 문서, 공식 릴리스 페이지 중심

## 1. 한줄 결론

`bmad-code-org/BMAD-METHOD`는 단일 명세 템플릿 도구라기보다, 분석부터 기획, 아키텍처, 구현 분해, 개발 운영까지 이어지는 AI 에이전트 기반 개발 프레임워크에 가깝다. TCI 관점에서는 `아이디어/기획 → PRD → architecture → epic/story → 구현 준비도 판단` 흐름을 한 체계 안에서 다룰 수 있다는 점이 강점이다. 다만 범위와 방법론이 넓고 무거워서, "기획을 설계 입력 문서로 정제"만이 목표라면 과할 수 있다

출처: [README](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/README.md), [Docs Index](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/index.md), [Workflow Map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md)

참고: 아래 문서의 적합성 판단과 도입 권고는 upstream 문서의 직접 진술이 아니라 TCI 관점의 해석을 포함한다

## 2. 왜 TCI에 맞는가

### 2.1 상위 기획부터 설계와 실행 분해까지 이어진다

BMAD-METHOD의 기본 흐름은 크게 아래로 정리할 수 있다

- Analysis
- Planning
- Solutioning
- Implementation

TCI 관점에서 중요한 점은 이 흐름이 단순 명세 작성에 머물지 않고, 문제 정의와 브리프, PRD, 아키텍처, 구현 단위 분해까지 연결된다는 점이다. 즉, 기능 문서를 설계 입력으로 바꾸는 것뿐 아니라 그 이후 운영 리듬까지 한 프레임 안에서 다룰 수 있다

출처: [Workflow Map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md), [Getting Started](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/tutorials/getting-started.md)

### 2.2 architecture 이후 epic/story 구조가 분명하다

BMAD-METHOD는 Planning 이후에 바로 구현으로 가지 않고, Solutioning 단계에서 아래를 별도 산출물로 둔다

- `architecture.md`
- epic/story 파일
- implementation readiness 판단

특히 architecture 이후 epic/story를 만들고, 구현 준비도를 `PASS`, `CONCERNS`, `FAIL`로 나누는 구조는 TCI의 "설계가 먼저 닫히고, 그 뒤에 실행 단위로 내린다"는 목적과 잘 맞는다

출처: [Workflow Map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md), [Getting Started](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/tutorials/getting-started.md), [CHANGELOG](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/CHANGELOG.md)

### 2.3 `bmad-help`가 오케스트레이션 역할을 한다

이 프레임워크에서 중요한 진입점은 개별 명령보다 `bmad-help`다. 공식 문서는 이를 현재 프로젝트 상태를 보고 다음 단계와 선택지를 추천하는 가이드로 설명한다

TCI 입장에서는 워크플로우가 넓고 복잡하더라도, 사용자가 매번 전체 구조를 외울 필요 없이 현재 단계 기준으로 다음 행동을 추천받을 수 있다는 점이 장점이다

출처: [README](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/README.md), [Getting Started](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/tutorials/getting-started.md), [Commands/Skills Reference](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/commands.md)

## 3. TCI 기준 장점

- 단순 기능 명세보다 상위 기획 맥락까지 포괄한다
- PRD 이후 architecture와 epic/story를 분리해 설계 우선 구조를 강하게 만든다
- implementation readiness gate가 있어 설계 착수 판단과 연결하기 쉽다
- `bmad-help` 중심의 라우팅으로 넓은 프레임워크의 사용성을 보완한다
- 설치형 skill 구조와 모듈 체계 덕분에 장기적으로 확장성이 높다

출처: [README](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/README.md), [Workflow Map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md), [Commands/Skills Reference](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/commands.md), [Modules Reference](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/modules.md)

## 4. TCI 기준 리스크와 한계

- 범위가 넓어 "설계 입력 문서화"만을 목표로 할 때는 과할 수 있다
- 설치형 skill 및 agent 런타임을 전제로 해 진입 비용이 높다
- 기본 산출물 구조가 현재 TCI 문서 체계와 다르다
- 공식 문서와 최신 main 변화 사이에 시차가 있어 운영 판단을 보수적으로 해야 한다

조금 더 구체적으로 보면 아래와 같다

- 아이디어 탐색부터 구현 리뷰까지 포함해 초도 도입 범위를 좁히지 않으면 무거워진다
- Markdown 템플릿만 가져다 쓰는 방식보다 설치와 운영 이해가 더 필요하다
- `_bmad/`, `_bmad-output/`, `PRD.md`, `architecture.md`, epic/story 파일 구조를 그대로 받아들이기 어렵다
- 기능이 빠르게 진화해 도입 시 버전 고정과 매핑 전략이 필요하다

출처: [README](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/README.md), [Getting Started](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/tutorials/getting-started.md), [Commands/Skills Reference](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/commands.md), [Recent Commits](https://github.com/bmad-code-org/BMAD-METHOD/commits/main)

## 5. 권장 도입 방식

### 권장 원칙

- BMAD 전체를 한 번에 도입하지 않는다
- 초도 도입은 Analysis 일부 + Planning + Solutioning 일부만 본다
- `_bmad-output` 구조를 그대로 쓰기보다 TCI 문서 체계에 매핑하는 방식을 먼저 정한다
- Implementation phase 자동화는 나중으로 미룬다

### TCI 문서 체계와의 매핑

| TCI 목적 | BMAD 대응 | 비고 |
| --- | --- | --- |
| 아이디어/문제 정의 강화 | Analysis | brainstorming, research, product-brief, prfaq |
| 요구사항 문서화 | Planning | `PRD.md`, 필요 시 `ux-spec.md` |
| 기술 설계 입력 작성 | Solutioning | `architecture.md` |
| 실행 단위 분해 | create-epics-and-stories | epic/story 파일 생성 |
| 구현 준비도 검증 | implementation-readiness | `PASS` / `CONCERNS` / `FAIL` gate |

출처: [Workflow Map](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md), [Getting Started](https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/tutorials/getting-started.md)

### 파일럿 권장 범위

TCI에서는 아래 조건에 맞는 기능에 제한적으로 붙여보는 편이 좋다

- 기획 맥락과 사용자 가치 설명이 중요함
- 설계 난도가 있음
- architecture와 story breakdown의 분리가 유의미함
- 구현보다 문서 정합성이 먼저 중요함

예시:

- 문서-코드 추적 구조 설계
- GitHub, 티켓, 문서 연동 플로우
- 설계 산출물과 구현 상태 불일치 감지

권장 절차는 아래와 같다

1. 필요한 경우 Analysis에서 `product-brief` 또는 `prfaq`만 제한적으로 사용
2. `bmad-create-prd`로 요구사항 문서화
3. 필요 시 `bmad-create-ux-design` 추가
4. `bmad-create-architecture`로 기술 설계 입력 작성
5. `bmad-create-epics-and-stories`까지만 사용
6. Implementation phase 자동화는 하지 않고 TCI 문서 체계로 편입

## 6. 최종 판단

`bmad-code-org/BMAD-METHOD`는 "기획을 더 상위 맥락부터 다루고, 설계와 실행 분해까지 이어지는 전체 프레임워크"가 필요할 때 매우 강력한 후보다. 특히 아래 세 가지가 강점이다

- Analysis부터 시작하는 상위 기획 흐름이 있다
- architecture 이후 story breakdown이라는 설계 우선 구조가 명확하다
- `bmad-help`와 skill 기반 실행으로 실제 운영형 워크플로우를 제공한다

하지만 "기획 문서를 설계 입력 문서로만 바꾸고 싶다"는 좁은 목표에는 과할 수 있다

정리하면 결론은 아래와 같다

- 강력하지만 무겁다
- 설계 문서화만이 아니라 전체 프로세스 혁신을 원할 때 더 적합하다
- 초기에는 기본선보다 상위 확장 프레임워크 후보로 보는 편이 맞다

## 7. 참고 링크

- 저장소: https://github.com/bmad-code-org/BMAD-METHOD
- README: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/README.md
- Docs Index: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/index.md
- Getting Started: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/tutorials/getting-started.md
- Workflow Map: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/workflow-map.md
- Agents Reference: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/agents.md
- Skills Reference: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/commands.md
- Modules Reference: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/reference/modules.md
- Non-Interactive Installation: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/docs/how-to/non-interactive-installation.md
- CHANGELOG: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/CHANGELOG.md
- 최신 릴리스 `v6.2.2`: https://github.com/bmad-code-org/BMAD-METHOD/releases/tag/v6.2.2
- `package.json`: https://github.com/bmad-code-org/BMAD-METHOD/blob/main/package.json
