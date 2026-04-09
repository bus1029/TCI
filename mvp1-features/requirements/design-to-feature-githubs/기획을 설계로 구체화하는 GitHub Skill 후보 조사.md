# 기획을 설계로 구체화하는 GitHub Skill 후보 조사

## 목적

이 문서는 추상적인 기능 기획을 개발 전 설계 단계로 구체화하기 위한 Skill, 워크플로우, 템플릿 기반 GitHub 프로젝트 후보를 조사한 결과를 정리한다.

조사 목적은 다음과 같다.

- 기능 리스트 수준의 기획을 설계 입력 수준으로 끌어올릴 수 있는가
- PRD, Tech Spec, Architecture, Task Breakdown 등 중간 산출물을 체계적으로 만들 수 있는가
- 현재 TCI 문서 체계와 결합해 재사용 가능한가

## 조사 기준

다음 기준으로 후보를 추렸다.

- GitHub에서 공개적으로 확인 가능한 저장소인가
- 단순 프롬프트 모음이 아니라 재사용 가능한 Skill, 워크플로우, 템플릿, 명령 체계를 갖고 있는가
- `아이디어/기능 설명 → 요구사항 정제 → 설계 산출물` 흐름이 명시돼 있는가
- 구현 단계 이전의 문서화와 구조화에 실제로 도움이 되는가

## 요약

직접 적용 가능성이 가장 높은 후보는 다음과 같다.

- `github/spec-kit`
- `bmad-code-org/BMAD-METHOD`
- `xmm/codex-bmad-skills`
- `aj-geddes/claude-code-bmad-skills`
- `phuryn/pm-skills`
- `deanpeters/Product-Manager-Skills`

보조 후보로는 다음이 있다.

- `automazeio/ccpm`
- `gsd-build/get-shit-done`
- `hesreallyhim/awesome-claude-code`

## 후보 상세

### 1. github/spec-kit

- 저장소: [github/spec-kit](https://github.com/github/spec-kit)
- 성격: Spec-Driven Development 툴킷
- 핵심 흐름
  - `constitution`
  - `specify`
  - `clarify`
  - `plan`
  - `tasks`
  - `implement`
- 강점
  - 기능 아이디어를 바로 코드로 넘기지 않고 먼저 명세로 구조화함
  - `clarify` 단계가 있어 모호한 요구사항을 설계 전 질문으로 보강할 수 있음
  - `spec.md`, `plan.md`, `tasks.md` 구조가 명확함
  - 확장과 preset 체계가 있어 조직 맞춤형 템플릿으로 발전시키기 좋음
- TCI 관점 평가
  - 현재의 `기능 리스트`를 `설계 가능한 요구사항`으로 올리는 데 가장 직접적
  - `코드 저장소 연동` 같은 항목을 spec과 plan으로 확장하는 데 적합
- 적합도
  - 매우 높음

### 2. bmad-code-org/BMAD-METHOD

- 저장소: [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
- 성격: Agile AI Driven Development 프레임워크 원본
- 핵심 흐름
  - 분석
  - 계획
  - 아키텍처
  - 구현
- 강점
  - 프로젝트 규모에 따라 planning depth를 조절하는 구조가 있음
  - PM, Architect, UX 등 역할 기반 구분이 분명함
  - 요구사항과 아키텍처를 단계적으로 분리함
- TCI 관점 평가
  - 기능 항목을 곧바로 설계하지 않고, 중간 산출물로 정제하는 프레임이 좋음
  - 다만 원본은 범위가 넓어 그대로 도입하면 다소 무거울 수 있음
- 적합도
  - 높음

### 3. xmm/codex-bmad-skills

- 저장소: [xmm/codex-bmad-skills](https://github.com/xmm/codex-bmad-skills)
- 성격: Codex용 BMAD 구현체
- 핵심 흐름
  - `bmad:product-brief`
  - `bmad:research`
  - `bmad:brainstorm`
  - `bmad:prd`
  - `bmad:tech-spec`
  - `bmad:architecture`
  - `bmad:sprint-plan`
- 강점
  - 현재 작업 환경과 가까운 Codex 중심 구조
  - Product Brief, PRD, Tech Spec, Architecture가 나뉘어 있음
  - 의도 기반 워크플로우와 YAML 상태 관리가 있음
- TCI 관점 평가
  - TCI 기능 하나를 뽑아 설계 문서로 변환하는 실험용 후보로 좋음
  - `기능 리스트 → product brief/PRD/tech spec` 흐름을 Codex에 맞춰 적용하기 쉬움
- 적합도
  - 매우 높음

### 4. aj-geddes/claude-code-bmad-skills

- 저장소: [aj-geddes/claude-code-bmad-skills](https://github.com/aj-geddes/claude-code-bmad-skills)
- 성격: Claude Code용 BMAD 구현체
- 핵심 흐름
  - `/product-brief`
  - `/prd`
  - `/tech-spec`
  - `/architecture`
  - `/solutioning-gate-check`
  - `/create-ux-design`
- 강점
  - 요구사항과 아키텍처 사이의 게이트가 분명함
  - PRD와 Architecture를 분리해서 다룸
  - UX와 설계를 병행할 수 있는 구조가 있음
- TCI 관점 평가
  - 설계 착수 가능 여부를 판단하는 게이트 개념이 현재 문서와 잘 맞음
  - Claude 중심이지만 개념 참고용으로 유용함
- 적합도
  - 높음

### 5. phuryn/pm-skills

- 저장소: [phuryn/pm-skills](https://github.com/phuryn/pm-skills)
- 성격: PM 스킬 마켓플레이스
- 핵심 영역
  - discovery
  - strategy
  - PRD
  - backlog
  - stories
  - metrics
  - market research
- 강점
  - `create-prd`, `prioritize-features`, `opportunity-solution-tree`, `test-scenarios` 등 기획 정제용 스킬이 풍부함
  - 추상적인 기능을 문제 정의, 가설, 우선순위, 사용자 스토리로 전개하기 좋음
- TCI 관점 평가
  - 구현 직전 설계보다 그 이전의 PM 정제 단계에 강함
  - 현재 `기능 설계 착수 판단 기준` 문서의 상위 단계 프레임워크로 활용 가능
- 적합도
  - 높음

### 6. deanpeters/Product-Manager-Skills

- 저장소: [deanpeters/Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills)
- 성격: PM 프레임워크 기반 Skill 라이브러리
- 핵심 영역
  - `prd-development`
  - `roadmap-planning`
  - `problem-statement`
  - `user-story`
  - `user-story-mapping`
  - `epic-breakdown-advisor`
- 강점
  - 기능을 문장 수준에서 설계 가능한 단위로 쪼개는 데 좋음
  - 교육적 설명이 많아 팀 내부 공통 기준 문서화에 유리함
- TCI 관점 평가
  - 기능 항목을 `문제 정의 → PRD → 스토리`로 풀어내는 데 적합
  - TCI 요구사항 문서를 더 세밀하게 구조화할 때 참고 가치가 높음
- 적합도
  - 높음

### 7. automazeio/ccpm

- 저장소: [automazeio/ccpm](https://github.com/automazeio/ccpm)
- 성격: PRD 기반 프로젝트 관리 Skill
- 핵심 흐름
  - PRD 생성
  - Epic 변환
  - Task 분해
  - GitHub 이슈 동기화
  - 병렬 실행
- 강점
  - PRD에서 Epic과 Task로 이어지는 추적성이 강함
  - 작업 단위 구조화에 특화돼 있음
- TCI 관점 평가
  - 설계 문서 생성보다는 설계 이후 구조화와 실행 연결에 강함
  - 기능을 backlog와 issue 수준으로 분해할 때 유용
- 적합도
  - 중간 이상

### 8. gsd-build/get-shit-done

- 저장소: [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)
- 성격: 경량 spec-driven development 시스템
- 핵심 흐름
  - `new-project`
  - `discuss-phase`
  - `plan-phase`
  - `execute-phase`
  - `verify-work`
- 강점
  - discuss 단계에서 회색지대를 질문으로 메워줌
  - planning 문서와 실행 문서를 분리함
  - context engineering에 강함
- TCI 관점 평가
  - 기능별 논의와 설계 보강에는 적합
  - 다만 전체 시스템이 넓어서 특정 기능 요구사항 문서화만 보면 다소 무거움
- 적합도
  - 중간 이상

### 9. hesreallyhim/awesome-claude-code

- 저장소: [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
- 성격: Claude Code 관련 리소스 인덱스
- 강점
  - planning, PRD, workflow, project management 계열 저장소를 더 찾기 좋음
  - 직접 사용보다는 추가 탐색 출발점으로 가치가 큼
- TCI 관점 평가
  - 바로 도입할 프레임워크는 아니지만 후보군 확장용으로 유용
- 적합도
  - 탐색용

## 추천 우선순위

현재 TCI 문서 상태와 목표를 기준으로 우선순위를 정리하면 다음과 같다.

### 1순위

- `github/spec-kit`
- `xmm/codex-bmad-skills`

이유

- 기능 설명을 `명세 → 계획 → 작업`으로 끌어올리는 경로가 가장 직접적
- 현재처럼 기능 카탈로그만 있는 상태를 다루기 좋음
- Codex 환경과 연계성이 높음

### 2순위

- `bmad-code-org/BMAD-METHOD`
- `aj-geddes/claude-code-bmad-skills`

이유

- 분석, PRD, 아키텍처, 구현 게이트가 잘 분리돼 있음
- 설계 전 단계의 질문과 산출물 구분이 분명함

### 3순위

- `phuryn/pm-skills`
- `deanpeters/Product-Manager-Skills`

이유

- 기능을 더 나은 요구사항으로 정제하는 PM 프레임워크가 풍부함
- 설계 자체보다는 설계 이전 기획 정제 단계 강화에 적합

## TCI에 바로 적용하는 방법

### 적용안 1

`기능 리스트 → Spec Kit 방식`

- 기능 항목 선택
- 기능 목적과 사용자 가치 정리
- 명확하지 않은 부분을 clarify 질문으로 보강
- `spec.md` 수준 요구사항 작성
- `plan.md` 수준 기술 설계 입력 작성

적합한 대상

- `코드 저장소 연동`
- `티켓 시스템 연동`
- `문서-코드 추적`
- `문서와 코드 간 불일치 분석`

### 적용안 2

`기능 리스트 → BMAD 방식`

- product brief 작성
- PRD 또는 tech spec 작성
- architecture 문서 작성
- gate check로 누락 확인

적합한 대상

- 설계 복잡도가 높은 연동 기능
- 비기능 요구사항과 운영 정책이 중요한 기능

### 적용안 3

`기능 리스트 → PM Skill 방식`

- problem statement 작성
- user story 또는 job story로 분해
- PRD 작성
- test scenario와 acceptance 기준 작성

적합한 대상

- 사용자 가치와 업무 흐름이 중요한 기능
- PM, 기획, 개발 간 공통 언어가 필요한 기능

## TCI 기준 추천 사용 전략

가장 현실적인 전략은 단일 프레임워크만 쓰는 방식보다 조합 방식이다.

- 1단계: `phuryn/pm-skills` 또는 `deanpeters/Product-Manager-Skills`로 기능 정의 보강
- 2단계: `github/spec-kit` 또는 `xmm/codex-bmad-skills`로 설계 입력 문서화
- 3단계: 필요 시 `ccpm`으로 Epic, Task, Issue 수준까지 분해

즉, 다음 구조가 적절하다.

- PM 정제
- 설계 문서화
- 실행 단위 분해

## 결론

이번 목적에 가장 잘 맞는 단일 후보는 `github/spec-kit`이다.

현재 환경과의 궁합까지 고려한 실행 후보는 `xmm/codex-bmad-skills`다.

기획의 질을 먼저 끌어올리려면 `phuryn/pm-skills`와 `deanpeters/Product-Manager-Skills`가 유용하다.

따라서 TCI에서는 다음 순서가 가장 적절하다.

1. 기능 하나 선택
2. PM 프레임워크로 문제와 범위를 정제
3. Spec 또는 Tech Spec 형식으로 설계 입력 문서 작성
4. 필요하면 Epic과 Task로 분해

## 참고 링크

- [github/spec-kit](https://github.com/github/spec-kit)
- [bmad-code-org/BMAD-METHOD](https://github.com/bmad-code-org/BMAD-METHOD)
- [xmm/codex-bmad-skills](https://github.com/xmm/codex-bmad-skills)
- [aj-geddes/claude-code-bmad-skills](https://github.com/aj-geddes/claude-code-bmad-skills)
- [phuryn/pm-skills](https://github.com/phuryn/pm-skills)
- [deanpeters/Product-Manager-Skills](https://github.com/deanpeters/Product-Manager-Skills)
- [automazeio/ccpm](https://github.com/automazeio/ccpm)
- [gsd-build/get-shit-done](https://github.com/gsd-build/get-shit-done)
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code)
