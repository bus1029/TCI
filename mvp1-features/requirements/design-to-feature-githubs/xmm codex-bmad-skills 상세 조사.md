# xmm/codex-bmad-skills 상세 조사

- 조사 대상: `xmm/codex-bmad-skills`
- 조사 목적: TCI의 기능 기획을 PRD, Tech Spec, Architecture, Sprint/Story 수준까지 구조화할 수 있는지 검증
- 조사 시점: 2026-04-09 (KST)
- 조사 기준: 공식 GitHub 저장소, 공식 README, 공식 docs, 공개 릴리스/커밋 정보 중심

## 1. 한줄 결론

`xmm/codex-bmad-skills`는 Codex 환경에서 BMAD 방법론을 직접 실행하는 데 초점을 둔 워크플로우 패키지다. PRD, Tech Spec, Architecture, Gate Check, Story 흐름이 명시적이고 상태 파일 기반 운영도 분명하다. 다만 저장소 규모와 공개 검증도는 아직 작아서, TCI의 단일 기본선보다 Codex 특화 실험 후보로 보는 편이 맞다

출처: [README](https://github.com/xmm/codex-bmad-skills/blob/main/README.md), [Codex Workflows](https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-workflows.md), [Codex Skills](https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-skills.md)

참고: 아래 문서의 적합성 판단과 도입 권고는 upstream 문서의 직접 진술이 아니라 TCI 관점의 해석을 포함한다

## 2. 왜 TCI에 맞는가

### 2.1 문서 흐름이 직접적이다

이 프로젝트의 핵심 강점은 문서 단계 이름이 매우 명확하다는 점이다

- `product-brief`
- `prd`
- `tech-spec`
- `architecture`
- `gate-check`
- `sprint-plan`
- `create-story`

TCI 관점에서는 "기획을 설계로 구체화하고, 설계 착수 가능 여부를 판단한 뒤, 실행 단위로 내린다"는 흐름이 문서 이름만으로도 바로 읽힌다

출처: [README](https://github.com/xmm/codex-bmad-skills/blob/main/README.md), [Codex Workflows](https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-workflows.md)

### 2.2 Gate Check가 특히 유용하다

이 프로젝트는 `architecture` 다음에 `gate-check`를 둔다. 이는 구현 전 설계 검토를 별도 산출물로 남긴다는 뜻이다

공식 기준상 gate-check는 다음을 평가한다

- 요구사항 커버리지
- 아키텍처 품질
- blocker / major / minor 이슈 분류
- `PASS`, `CONDITIONAL PASS`, `FAIL` 판단

TCI에서 중요하게 보는 "설계 착수 판단 기준"과 가장 직접적으로 맞물리는 계층이다

출처: [bmad-architect SKILL](https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-architect/SKILL.md), [README](https://github.com/xmm/codex-bmad-skills/blob/main/README.md)

### 2.3 상태 파일 기반 운영이 가능하다

이 저장소는 대화 맥락이 아니라 파일을 상태의 소스 오브 트루스로 둔다. 핵심 파일은 아래와 같다

- `bmad/project.yaml`
- `bmad/workflow-status.yaml`
- `bmad/sprint-status.yaml`

즉, 프로젝트가 지금 어느 단계에 있는지, 어떤 문서가 생성됐는지, 다음에 무엇을 해야 하는지를 저장소 내부 상태로 남길 수 있다. 장기 작업이나 세션 전환이 잦은 운영에는 분명한 장점이다

출처: [Configuration](https://github.com/xmm/codex-bmad-skills/blob/main/docs/configuration.md), [bmad-orchestrator SKILL](https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-orchestrator/SKILL.md)

## 3. TCI 기준 장점

- Codex 전용으로 설계돼 현재 작업 환경과의 밀착도가 높다
- PRD, Architecture, Gate Check, Story 흐름이 명시적이다
- 상태 기반 워크플로우라 장기 프로젝트 운영에 유리하다
- 프로젝트 레벨에 따라 산출물 깊이를 다르게 가져갈 수 있다
- 한국어 문서 운영과 기술 토큰 병행에 유리한 language guard가 있다

출처: [README](https://github.com/xmm/codex-bmad-skills/blob/main/README.md), [Codex Workflows](https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-workflows.md), [bmad-product-manager SKILL](https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-product-manager/SKILL.md), [bmad-architect SKILL](https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-architect/SKILL.md)

## 4. TCI 기준 리스크와 한계

- 저장소 규모와 공개 검증도가 아직 작다
- `yq`와 설치 스크립트 등 운영 의존성이 분명하다
- BMAD 역할 구조와 레벨 체계를 이해해야 제대로 사용할 수 있다
- 문서와 구현 디테일이 아직 완전히 다듬어진 상태는 아니다

조금 더 구체적으로 보면 아래와 같다

- 공개 지표만 보면 실험 단계에 가까워 `spec-kit`보다 보수적으로 평가해야 한다
- YAML 상태 관리를 전제로 해 팀 환경에 따라 onboarding 비용이 생길 수 있다
- 직관적인 `spec → plan → tasks` 흐름보다 방법론 학습 비용이 더 있다
- 일부 문서 품질 이슈가 보여 운영 성숙도는 과대평가하지 않는 편이 안전하다

출처: [Repository Page](https://github.com/xmm/codex-bmad-skills), [Configuration](https://github.com/xmm/codex-bmad-skills/blob/main/docs/configuration.md), [Getting Started](https://github.com/xmm/codex-bmad-skills/blob/main/docs/getting-started.md), [Release v1.3.3](https://github.com/xmm/codex-bmad-skills/releases/tag/v1.3.3)

## 5. 권장 도입 방식

### 권장 사용 구간

TCI에서는 이 저장소를 "단일 표준 프레임워크"보다 "Codex 친화적인 BMAD 설계 파이프라인"으로 보는 편이 맞다

추천 흐름은 아래와 같다

1. `bmad:init`
2. `bmad:product-brief`
3. `bmad:prd` 또는 `bmad:tech-spec`
4. `bmad:architecture`
5. `bmad:gate-check`
6. 필요 시 `bmad:sprint-plan` 또는 `bmad:create-story`

즉, 구현 자동화보다 설계 문서화와 readiness gate를 세우는 용도로 먼저 쓰는 것이 가장 현실적이다

### TCI 문서 목적과의 매핑

| TCI 목적 | BMAD 대응 | 비고 |
| --- | --- | --- |
| 기능 기획의 문제 정의 | `product-brief` | 상위 PM 문맥 정리에 유리 |
| 요구사항 문서화 | `prd` / `tech-spec` | 범위 크기에 따라 선택 가능 |
| 설계 문서화 | `architecture` | 구성요소, 인터페이스, NFR 매핑 |
| 설계 착수 판단 | `gate-check` | pass / conditional pass / fail 구조 |
| 실행 단위 분해 | `sprint-plan` / `create-story` | story 기반 delivery 연결 |

출처: [README](https://github.com/xmm/codex-bmad-skills/blob/main/README.md), [Codex Workflows](https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-workflows.md)

### 현실적인 포지션

TCI에서는 이 프로젝트를 단독 채택하기보다 아래처럼 두는 편이 자연스럽다

- `spec-kit`: 더 넓게 검증된 기본선
- `codex-bmad-skills`: Codex 환경에서 PRD, Architecture, Gate Check를 더 명시적으로 운영하는 고도화 옵션

즉, 초기에는 기본선 교체보다 병행 실험 후보로 두는 전략이 적절하다

## 6. 최종 판단

`xmm/codex-bmad-skills`는 "기획 → PRD/Tech Spec → Architecture → Gate → Story" 흐름이 매우 선명하고, Codex 적합성도 높다. 그래서 TCI의 장기적 설계 운영 프레임으로는 충분히 매력적이다

하지만 현재 시점에서 단일 1순위 도입 후보로 바로 올리기에는 근거가 아직 약하다. 이유는 세 가지다

- 저장소 성숙도가 낮다
- 공개 생태계와 사례가 작다
- 설치와 운영 의존성이 분명하다

정리하면 결론은 아래와 같다

- 잠재력 높음
- 파일럿 검증 전제
- 초기에는 `spec-kit`의 대체재보다 Codex 특화 보완재로 보는 편이 맞다

## 7. 참고 링크

- 저장소: https://github.com/xmm/codex-bmad-skills
- README: https://github.com/xmm/codex-bmad-skills/blob/main/README.md
- Getting Started: https://github.com/xmm/codex-bmad-skills/blob/main/docs/getting-started.md
- Configuration: https://github.com/xmm/codex-bmad-skills/blob/main/docs/configuration.md
- Codex Workflows: https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-workflows.md
- Codex Skills: https://github.com/xmm/codex-bmad-skills/blob/main/docs/codex-skills.md
- `bmad-orchestrator` skill: https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-orchestrator/SKILL.md
- `bmad-product-manager` skill: https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-product-manager/SKILL.md
- `bmad-architect` skill: https://github.com/xmm/codex-bmad-skills/blob/main/skills/bmad-architect/SKILL.md
- CHANGELOG: https://github.com/xmm/codex-bmad-skills/blob/main/CHANGELOG.md
- 최신 릴리스 `v1.3.3`: https://github.com/xmm/codex-bmad-skills/releases/tag/v1.3.3
