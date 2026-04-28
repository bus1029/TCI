# 목적

이 문서는 GitHub 및 GitLab 연동 기능을 개발하면서 Agent, SpecKit, Codex CLI, RTK 같은 외부 도구를 어떻게 활용했는지 팀에 공유하기 위한 문서다. 단순한 사용 후기가 아니라, 요구사항을 스펙으로 정리하고, 그 스펙을 기준으로 구현과 리뷰를 반복하고, 테스트 결과와 판단 근거를 남기는 개발 흐름을 다시 따라 할 수 있게 정리한다.

# 전체 흐름

이번 개발은 기획 문장을 바로 구현하지 않고, 문서로 먼저 정리한 뒤 작은 개발 사이클로 나누어 진행했다.

큰 흐름은 다음과 같다.

1. 개발 환경 준비
   - SpecKit, ECC, Codex CLI, RTK, Caveman, `AGENTS.md` 역할 정리
2. SpecKit으로 SDD 산출물 작성
   - 기획 문서를 `spec.md`, `plan.md`, `tasks.md` 등으로 구체화
3. 산출물 교차 검토
   - 새 세션에서 `$speckit-analyze`를 실행해 문서 간 빠진 부분과 충돌 확인
4. ECC와 Codex CLI로 개발 계획 작성
   - `$plan`으로 `tasks.md` 또는 `next-session-handoff.md`를 읽고 한 번의 개발 사이클 계획 수립
5. TDD로 구현
   - `$tdd`를 사용해 실패 테스트, 최소 구현, 재검증 순서로 진행
6. 에이전트 리뷰와 수정 반복
   - 변경 성격에 맞는 reviewer를 선택해 리뷰하고, 지적 사항은 다시 테스트로 고정한 뒤 수정
7. 통합 검증과 산출물 갱신
   - 내부 레이어가 함께 맞물리는 흐름을 확인하고 `delivery-evidence.md`, `tasks.md`, `quickstart.md` 등에 반영
8. 다음 세션 인수인계와 커밋
   - `$handoff`로 `next-session-handoff.md`를 갱신하고, `$git-commit`으로 현재 diff에 맞는 커밋 메시지 작성

# 환경 설정

## SpecKit

SpecKit은 요구사항을 바로 구현으로 넘기지 않고, 스펙과 계획 문서로 한 번 정리한 뒤 개발에 들어가게 도와주는 도구다. 이번 GitHub 및 GitLab 연동 개발에서는 기능 범위, 기술 설계, 작업 순서, 검증 기준을 문서로 남기는 데 사용했다.

주요 산출물은 다음과 같다.

- `spec.md`
  - 사용자가 원하는 기능, 범위, 비범위, 요구사항, 성공 기준을 정리
- `plan.md`
  - 스펙을 실제 코드에 어떻게 반영할지 기술 설계와 검증 전략을 정리
- `tasks.md`
  - 구현할 일을 테스트, 기반 작업, 사용자 시나리오 단위로 쪼개 실행 순서를 정리
- `research.md`
  - 설계 판단에 필요한 조사 내용과 선택 이유를 정리
- `data-model.md`
  - 주요 데이터, 상태, 관계, 제약 조건을 정리
- `contracts/`
  - API나 외부 연동 계약을 OpenAPI 같은 형태로 정리
- `quickstart.md`
  - 기능을 실제로 실행하고 확인하는 최소 절차를 정리
- `delivery-evidence.md`
  - 구현 후 어떤 테스트와 리뷰를 통과했는지 판단 근거를 정리

정리하면 SpecKit은 "무엇을 만들지"와 "어떻게 검증할지"를 먼저 고정하고, 이후 ECC와 Codex CLI를 사용해 그 문서를 기준으로 구현하게 만드는 역할을 했다.

## ECC 관련 에이전트와 스킬

ECC(Everything-Claude-Code)는 원래 Claude Code를 중심으로 만들어진 agent 설정 모음이다. 이번 GitHub 및 GitLab 연동 개발에서는 원본을 그대로 쓰지 않고, Codex CLI에서 사용할 수 있도록 조정한 버전을 사용했다.

기준으로 삼은 프로젝트:

- GitHub: [bus1029/everything-claude-code](https://github.com/bus1029/everything-claude-code)

이번 개발에서 사용한 방식은 다음과 같다.

- ECC의 agent와 skill 구조를 Codex CLI의 skill, sub-agent, `AGENTS.md` 방식에 맞게 조정
- reviewer, language reviewer, security reviewer, database reviewer, test analyzer 같은 역할을 개발 단계별 검토에 활용
- 기능 구현은 로컬에서 직접 진행하고, reviewer 계열 agent는 변경 사항 검토와 빠진 테스트 확인에 사용
- 리뷰 지적 사항은 바로 수정하지 않고 먼저 실패 테스트나 focused test로 고정한 뒤 수정

## Codex CLI 설정

Codex CLI 설정은 사용자 홈의 `~/.codex/config.toml`을 기준으로 관리했다. 이 파일은 모델, 권한 정책, MCP 서버, agent, plugin, 신뢰할 프로젝트 경로를 한 곳에서 정리하는 전역 설정이다. 여기서는 이번 개발에 실제로 영향을 준 설정만 정리한다.

기본 실행 설정은 다음과 같다.

- 기본 모델은 `gpt-5.5`
- 기본 reasoning effort는 `high`
- 기본 승인 정책은 `on-request`
- 기본 sandbox는 `workspace-write`
- web search는 `live`
- `AGENTS.md` 지침과 MCP 활용 원칙을 persistent instruction으로 추가

권한 프로필은 작업 성격에 따라 바꿔 쓸 수 있게 나눴다.

- `strict`
  - `read-only` sandbox
  - cached web search
  - 코드 읽기, 검토, 조사 중심 작업에 사용
- `yolo`
  - `workspace-write` sandbox
  - live web search
  - 승인 없이 빠르게 로컬 파일을 수정해야 할 때 사용
- `yololo`
  - `danger-full-access` sandbox
  - live web search
  - 로컬 전체 접근이 필요한 파일럿 작업에만 제한적으로 사용

자주 쓴 MCP 서버는 다음과 같다.

- Notion
  - 회의록, 문서, workspace 자료 조회와 정리에 사용
- Sequential Thinking
  - 복잡한 문제를 단계별로 쪼개 볼 때 사용
- Context7
  - 라이브러리와 프레임워크 문서를 최신 기준으로 확인할 때 사용
- Exa
  - 웹 검색과 외부 자료 확인에 사용
- GitHub
  - GitHub repository, PR, issue, code search 조회에 사용
  - GitHub token은 설정 파일에 직접 넣지 않고 `gh auth token`을 런타임에 읽는 방식

agent 기능은 명시적으로 켜 두고, 최대 동시 작업 수와 깊이를 제한했다.

- `multi_agent=true`
- `max_threads=6`
- `max_depth=1`

`max_depth=1`은 메인 Codex 세션이 직접 부르는 1단계 agent까지만 허용한다는 뜻이다. agent가 다시 다른 agent를 부르는 중첩 위임을 막아, 책임 범위와 토큰 사용량을 관리하기 쉽게 했다.

이번 개발에서 자주 쓴 agent는 다음과 같다.

- `reviewer`
  - 일반적인 코드 리뷰 agent
- `planner`
  - 구현 계획을 쪼개는 agent
- `python-reviewer`
  - Python 코드 리뷰 agent
- `security-reviewer`
  - 보안 관점 리뷰 agent
- `database-reviewer`
  - PostgreSQL과 migration 리뷰 agent
- `pr-test-analyzer`
  - 변경 사항에 대한 테스트 부족 여부를 보는 agent
- `tdd-guide`
  - 테스트 먼저 작성하는 흐름을 점검하는 agent

그 밖의 agent와 plugin은 필요할 때만 사용했다. Notion과 Caveman plugin은 전역에서 켜 두었다.

- `notion@openai-curated`
- `caveman@caveman-repo`

## RTK

RTK는 CLI 명령 결과를 agent에게 전달하기 전에 줄여 주는 도구다. 이번 개발에서는 `git status`, `git diff`, `rg`, `pytest`, `ruff`처럼 출력이 길어지기 쉬운 명령을 실행할 때 토큰 사용량을 줄이기 위해 사용했다.

공식 GitHub 기준으로 RTK는 `60-90%` 수준의 토큰 절감을 목표로 하는 Rust 기반 CLI proxy다. 동작 방식은 간단하다.

- Codex가 shell 명령을 실행할 때 `rtk`를 앞에 붙임
- RTK가 실제 명령을 대신 실행
- 명령 결과에서 반복되거나 덜 중요한 부분을 줄임
- 실패 원인, 변경 파일, 요약 통계처럼 판단에 필요한 정보는 남김
- 줄어든 결과만 Codex context로 들어가 토큰 사용량이 감소

Codex 작업 중 shell 명령을 실행할 때는 `rtk git status`, `rtk rg`, `rtk pytest -q`처럼 직접 `rtk`를 붙여 실행했다. 원본 출력이 꼭 필요한 경우에는 RTK를 우회하거나 passthrough를 사용한다.

## Caveman

Caveman은 agent의 답변을 짧고 직접적인 형태로 줄여 출력 토큰을 아끼는 skill/plugin이다. 공식 GitHub 기준으로 Claude Code와 Codex plugin을 지원하며, 설명은 줄이되 기술적인 내용은 유지하는 것을 목표로 한다.

동작 방식은 다음과 같다.

- agent 답변에서 인사, 완곡한 표현, 반복 설명 같은 군더더기를 제거
- 핵심 판단, 변경 내용, 다음 행동만 짧게 유지
- 코드, 명령어, 파일 경로, 오류 메시지 같은 기술 정보는 그대로 유지
- 필요한 경우 `lite`, `full`, `ultra`처럼 압축 강도를 조절
- Codex에서는 `$caveman` 형태로 켜고, 일반 모드로 돌아가고 싶을 때는 중지 명령어를 내림

팀 문서 작성, 설계 설명, 사용자와의 의사결정이 필요한 순간에는 자연스러운 문장을 우선했고, 긴 진행 상황 보고나 단순 반복 응답을 줄이고 싶을 때만 토큰 절약용으로 활용했다.

## AGENTS.md

`AGENTS.md`는 Codex가 작업할 때 항상 참고하는 운영 규칙이다. 이번 개발에서는 전역 파일인 `~/.codex/AGENTS.md`와 프로젝트 안의 `AGENTS.md`를 함께 사용했다.

- 전역 `~/.codex/AGENTS.md`
  - 모든 Codex 작업에 공통으로 적용할 기본 규칙
- 프로젝트 `AGENTS.md`
  - 특정 저장소에서만 적용할 기술 스택, 테스트, 작업 방식 규칙

규칙이 여러 곳에 있을 때는 현재 작업 위치에 가까운 `AGENTS.md`가 더 구체적인 기준이 된다.

### 전역 AGENTS.md

전역 `AGENTS.md`에서 이번 개발에 직접 영향을 준 내용은 다음과 같다.

- shell 명령은 가능하면 `rtk`로 실행
- 원본 출력이 필요한 보안 스캔, diff, 감사성 확인은 `rtk proxy` 또는 원본 출력 사용
- 코드 변경 전 로컬 코드베이스를 먼저 읽고 기존 패턴을 따름
- 사용자 변경사항은 되돌리지 않음
- 검색은 `rg`, `rg --files` 우선 사용
- 수동 파일 수정은 `apply_patch` 사용
- 변경 범위는 요청한 동작에 필요한 곳으로 제한
- skill은 사용자가 이름을 말했거나 작업 성격이 맞을 때만 사용
- sub-agent는 사용자가 명시적으로 요청했을 때만 사용
- agent를 사용할 때는 역할과 파일 범위를 좁게 지정
- 비밀값, 토큰, private key, `.env` 값은 응답이나 MCP, agent에 넘기지 않음
- 코드 변경 후에는 위험도에 맞게 좁은 테스트부터 넓은 회귀 테스트까지 실행
- commit, push, release는 사용자가 명시적으로 요청했을 때만 수행
- destructive git 명령은 명확한 요청 없이는 실행하지 않음

구현은 직접 코드와 테스트를 보고 진행하고, reviewer agent는 검토와 빠진 테스트를 찾는 용도로 제한했다. 보안상 민감한 정보는 항상 redaction하거나 존재 여부만 확인했다.

### 프로젝트 AGENTS.md

현재 TCI 프로젝트의 `AGENTS.md`에는 `forrestchang/andrej-karpathy-skills`에서 제공하는 `CLAUDE.md` 내용을 참고해 가져온 원칙도 포함되어 있다.

- GitHub: [forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)

이 `CLAUDE.md`는 LLM 코딩에서 자주 생기는 문제를 줄이는 데 초점을 둔다. agent가 모호한 요구를 확인하지 않고 가정하거나, 필요 이상으로 복잡한 코드를 만들거나, 요청과 상관없는 코드를 건드리거나, 성공 기준 없이 구현을 밀어붙이는 일을 막기 위한 지침이다.

프로젝트에 반영한 원칙은 네 가지다.

- Think Before Coding
  - 모르면 추측하지 않고 가정을 드러내거나 질문
  - 여러 해석이 가능하면 조용히 하나를 고르지 않고 선택지를 제시
- Simplicity First
  - 요청받은 문제를 푸는 최소 코드 우선
  - 필요 없는 추상화, 확장성, 설정 옵션을 만들지 않음
- Surgical Changes
  - 요청한 범위에 필요한 파일과 라인만 수정
  - 인접 코드, 주석, 포맷을 이유 없이 정리하지 않음
- Goal-Driven Execution
  - 성공 기준과 검증 방법을 먼저 세움
  - 버그 수정이나 기능 추가는 테스트로 재현하고 통과시키는 흐름으로 진행

# SpecKit을 사용한 SDD 개발 방식

SpecKit은 기획 문장을 바로 코드로 넘기지 않고, 구현 전에 요구사항과 설계 판단을 문서로 고정하는 방식으로 사용했다. GitHub 연동은 신규 기능을 정의하는 흐름이었고, GitLab 연동은 기존 GitHub 구현과의 호환성을 제약으로 둔 확장 흐름이었다.

## 입력 정리

처음에는 기존 기획 문서(Confluence)의 기능 설명을 SpecKit 입력으로 정리했다. 단순히 기능 이름만 넘기지 않고, 기능 설명, 상세 기능, 반드시 고려해야 할 제약을 함께 적었다.

GitHub 코드 저장소 연동에서는 다음 내용을 입력으로 삼았다.

- Git 기반 형상 관리 시스템과 연동
- 코드베이스와 변경 이력 수집
- 분석 가능한 코드 스냅샷 생성
- SSH/HTTPS 저장소 연결
- 브랜치/태그 선택
- 포함/제외 경로와 파일 타입 설정
- Commit, Push, PR 이벤트 감지
- Webhook 기반 실시간 이벤트 수신

GitLab 연동에서는 같은 입력에 기존 구현과의 관계를 추가했다.

- 기존 GitHub Cloud 연동 기능 존재
- On-premise GitLab 연동 추가
- 기존 GitHub Cloud 코드와 기능 흐름을 깨지 않아야 함
- PR 대신 MR 이벤트를 기준으로 처리

## 스펙 작성

`$speckit-specify`로 `spec.md`를 작성했다. 이 문서에는 구현 방법보다 사용자가 기대하는 결과를 먼저 고정했다.

`spec.md`에서 정리한 내용은 다음과 같다.

- 기능 배경과 목적
- 사용자 시나리오
- 기능 요구사항
- 주요 데이터와 상태
- 성공 기준
- 가정과 비범위

GitHub 연동에서는 코드 저장소 연동 자체의 기준선을 세웠다. GitLab 연동에서는 그 기준선을 다시 사용하되, provider가 늘어나도 기존 GitHub 흐름이 유지되어야 한다는 조건을 명확히 넣었다.

## 모호한 부분 정리

`$speckit-clarify`로 설계 전에 반드시 정해야 할 질문을 드러냈다. 이 단계는 agent가 모호한 부분을 조용히 가정하지 않게 만드는 역할을 했다.

확정한 질문의 예시는 다음과 같다.

- credential을 사용자 개인 기준으로 둘지, 연결 단위 공유 credential로 둘지
- 읽기 전용 credential만 허용할지
- 기본 수집 제외 정책을 GitHub와 GitLab에 동일하게 둘지
- Commit 이벤트를 독립 snapshot trigger로 볼지, 기록 전용으로 볼지
- Merge Request 이벤트 중 어떤 action만 snapshot trigger로 볼지
- 공식 connection status와 webhook health를 분리할지
- GitLab instance URL을 사용자가 직접 입력할지, remote URL에서 파생할지

질문에 답한 뒤에는 답변을 대화에만 남기지 않고 `spec.md`에 반영했다. 이 과정을 거쳐 스펙이 구현 전 기준선이 되었다.

## 계획 작성

`$speckit-plan`으로 `plan.md`를 작성했다. 이 단계에서는 `spec.md`를 실제 코드에 어떻게 반영할지 기술 설계로 바꿨다.

`plan.md`에서 정리한 내용은 다음과 같다.

- 기술 스택과 실행 환경
- 데이터 모델 변경 방향
- API와 webhook 계약
- provider별 adapter 구조
- GitHub와 GitLab 공통 흐름
- credential 처리와 보안 제약
- snapshot과 scope rule 처리 방식
- 테스트와 검증 전략

GitLab 연동 계획에서는 "기존 GitHub Cloud 연동 기능 관련 코드와의 호환성"을 명시적인 제약으로 넣었다.

## 작업 분해

`$speckit-tasks`로 `tasks.md`를 작성했다. 이 문서는 개발자가 바로 backlog나 issue로 옮길 수 있을 정도의 작업 단위를 만드는 데 사용했다.

작업 분해 기준은 다음과 같다.

- 공통 기반 작업을 먼저 배치
- 사용자 가치 기준으로 US1, US2, US3 분리
- 각 사용자 story마다 테스트 작업과 구현 작업을 함께 작성
- 한 작업이 너무 커지지 않도록 파일 경로와 책임 범위를 명시
- 모든 작업이 끝났을 때 `spec.md` 요구사항을 충족해야 함
- GitHub 회귀 테스트를 별도 작업으로 유지

## 산출물 교차 검토

`$speckit-analyze`로 `spec.md`, `plan.md`, `tasks.md`를 교차 검토했다. 이 단계는 기존 작성 흐름과 섞이지 않게 새로운 세션에서 시작했다. 그래야 앞선 대화 맥락에 끌려가지 않고, 실제 파일만 기준으로 문서끼리 서로 맞지 않는 부분을 볼 수 있었다.

중점적으로 본 항목은 다음과 같다.

- `spec.md` 요구사항이 `tasks.md`에 빠지지 않았는지
- 비범위 항목이 `tasks.md`에 들어가지 않았는지
- `plan.md`의 기술 설계가 `spec.md` 요구사항을 설명하는지
- 테스트가 사용자 story와 성공 기준을 충족하는지
- GitHub 호환성 같은 제약이 작업 단위까지 내려왔는지

문제가 나오면 바로 구현하지 않고 `analyze -> clarify -> plan -> tasks` 순서로 다시 보정했다. 그다음 다시 새로운 세션을 열어 `$speckit-analyze`를 실행하고 같은 방식으로 루프를 반복했다.

## 개발 단계로 넘기기

SpecKit 산출물은 ECC와 Codex CLI 개발의 입력이 되었다. 구현을 시작하기 전에 agent에게 어떤 문서를 어떤 순서로 읽어야 하는지 먼저 정했다.

기본 순서는 다음과 같다.

1. `spec.md`
2. `plan.md`
3. `tasks.md`
4. `data-model.md`
5. `contracts/`
6. `quickstart.md`
7. `delivery-evidence.md`

이 순서를 둔 이유는 간단하다. 먼저 "무엇을 만족해야 하는지"를 보고, 그다음 "어떻게 만들지"를 본 뒤, 마지막으로 "어떤 순서로 구현하고 어떻게 검증할지"를 보기 위해서다.

# 작성된 스펙 문서를 기반으로 한 ECC 개발 방식

ECC와 Codex CLI는 SpecKit 산출물을 기준으로 실제 구현을 진행하는 단계에서 사용했다. 핵심은 `plan -> tdd -> review -> fix -> handoff -> evidence -> commit` 흐름을 유지하는 것이다.

## 처음 개발하는 경우

처음 기능 개발을 시작할 때는 `tasks.md`를 기준으로 계획을 다시 세웠다. 여기서 `$plan`은 `tasks.md` 전체를 한 번에 개발하겠다는 뜻이 아니다. 전체 task 목록 중에서 한 번의 개발 사이클로 끝낼 수 있는 범위를 고르고, 현재 코드 상태와 테스트 상태를 반영해 이번 세션에서 실제로 어디까지 할지 정하는 단계다.

기본 흐름은 다음과 같다.

1. `$plan`으로 개발 계획 작성
2. `$tdd`로 개발 진행
3. reviewer 계열 agent로 리뷰
4. 리뷰 지적 사항 수정
5. 더 이상 수정 사항이 없을 때까지 개발과 리뷰 반복
6. `$handoff`로 다음 세션 인수인계 작성
7. `tasks.md`, `delivery-evidence.md`, `plan.md`, `quickstart.md` 등 산출물 갱신
8. `$git-commit`으로 현재 개발 상태에 맞는 커밋 메시지 작성

이때 `$plan`은 `tasks.md`를 context로 받아 이번 개발 사이클의 실행 계획을 만든다. 구현 전에 목표, 비목표, 제약, 위험, 검증 방법을 다시 정리하고, 사용자 승인을 받은 뒤에만 실제 코드 수정으로 넘어간다.

## TDD 구현

`$tdd`는 계획된 작업을 `RED -> GREEN -> REFACTOR` 흐름으로 진행하는 데 사용했다. 새 기능, 버그 수정, 회귀 방지 작업 모두 먼저 테스트로 동작을 고정한 뒤 최소 코드로 통과시키는 방식을 유지했다.

진행 방식은 다음과 같다.

1. 요구사항과 성공 기준을 짧게 고정
2. 테스트 케이스와 edge case 분해
3. 영향을 받는 파일과 함수 확인
4. 실패 테스트 추가
5. 테스트를 실행해 의도한 이유로 실패하는지 확인
6. 최소 수정으로 통과
7. 같은 테스트와 주변 테스트 재실행
8. 필요할 때만 리팩터링
9. 리팩터링 후 다시 검증

## 에이전트 리뷰

구현 후에는 reviewer 계열 agent를 사용해 변경 사항을 다시 봤다. 모든 reviewer를 항상 돌린 것은 아니다. 메인 agent가 개발한 내용의 언어, 변경 범위, 위험 지점에 맞춰 필요한 reviewer만 골라 실행했다.

`$tdd` 스킬도 같은 기준을 갖고 있다. 먼저 범용 `reviewer`로 리스크를 확인하고, Python 변경이면 `python-reviewer`, DB schema나 query 영향이 크면 `database-reviewer`, 인증이나 secret 처리처럼 보안 민감 변경이면 `security-reviewer`를 추가하는 방식이다.

주로 사용한 역할은 다음과 같다.

- `reviewer`
  - 기능 회귀, 동작 오류, 빠진 테스트 확인
- `python-reviewer`
  - Python 코드 품질, 예외 처리, resource cleanup 확인
- `security-reviewer`
  - secret 처리, 입력 검증, trust boundary, 인증 흐름 확인
- `database-reviewer`
  - PostgreSQL schema, migration, constraint, downgrade 위험 확인
- `pr-test-analyzer`
  - 변경된 동작을 테스트가 충분히 덮는지 확인

비밀값이나 credential 원문은 agent에게 넘기지 않았다.

## 수정 루프

리뷰 지적 사항은 바로 코드만 고치지 않았다. 가능하면 먼저 실패 테스트나 focused test로 문제를 고정한 뒤 수정했다.

반복 흐름은 다음과 같다.

1. reviewer finding 확인
2. 실제 문제인지 코드와 테스트로 재확인
3. 재현 테스트 또는 focused test 추가
4. RED 확인
5. 최소 수정
6. GREEN 확인
7. 같은 reviewer 또는 관련 reviewer로 재검토

이 루프를 통해 `수정했다고 생각한 상태`가 아니라 `테스트와 reviewer가 다시 확인한 상태`를 기준으로 다음 단계로 넘어갔다.

## 통합 검증

여기서 말하는 통합 검증은 실제 GitHub나 GitLab 서버까지 모두 붙이는 end-to-end 테스트를 뜻하지 않는다. TDD로 기능을 만든 뒤, API route, domain service 처럼 여러 내부 레이어가 함께 맞물려 동작하는지 확인하는 단계다.

검증은 좁은 focused test에서 시작해, 변경한 흐름과 인접한 회귀 범위로 넓혔다. 실제 테스트 범위는 변경 내용에 따라 달라졌지만, 주로 아래 흐름을 확인했다.

- 저장소 연결 생성과 초기 snapshot 생성
- scope rule 저장과 filtered snapshot 생성
- GitHub webhook refresh와 secret rotation
- GitLab push/MR webhook 처리
- GitHub와 GitLab provider 공존과 데이터 섞임 방지

검증 결과는 마지막 응답에만 남기지 않고 `delivery-evidence.md` 같은 산출물에도 반영했다.

## 다음 세션에서 이어 개발하는 경우

다음 세션에서 이어 개발할 때는 `tasks.md`보다 `next-session-handoff.md`를 먼저 읽었다. 이전 세션의 마지막 상태, 닫힌 결정, 남은 위험, 바로 다음 액션을 빠르게 복구하기 위해서다.

처음 개발할 때와 대부분의 흐름은 같다. 달라지는 점은 시작 context다.

- `$plan`에는 `next-session-handoff.md`를 먼저 넘김
- 에이전트가 필요할 때만 `spec.md`, `plan.md`, `tasks.md`, `delivery-evidence.md`를 추가 확인
- `$tdd`, reviewer 리뷰, 수정 루프는 동일하게 유지
- 세션 끝에는 `$handoff`로 다음 시작점을 다시 갱신
- 산출물과 검증 결과를 업데이트하고, 필요한 경우 `$git-commit` 사용

이 방식은 긴 기능 개발에서 특히 중요했다. 다음 세션이 오래된 대화 로그를 다시 읽지 않아도, 현재 상태와 다음 행동을 빠르게 잡을 수 있었다.

## handoff 스킬

`$handoff`는 다음 Codex 세션이 작업을 이어받을 수 있게 인수인계 문서를 작성하거나 갱신하는 skill이다. 이번 개발에서는 `next-session-handoff.md`를 만들고 관리하는 데 사용했다.

handoff 문서는 대화 기록이 아니라 다음 세션을 위한 작업 브리핑이다. 그래서 긴 설명보다 현재 상태, 바뀐 파일, 테스트 결과, 닫힌 결정, 다음 액션을 짧게 남기는 것이 중요하다.

기본 섹션은 다음과 같다.

- 짧은 요약
- 현재 상태
- 이번 세션에서 바뀐 것
- 다음 에이전트가 먼저 봐야 할 파일
- 꼭 유지해야 할 기준
- 다시 논의하지 말아야 할 결정
- 이번 세션에서 얻은 중요한 메모
- 테스트와 검증 상태
- 다음 세션의 시작 순서
- 마지막 액션과 바로 다음 액션

기존 handoff 문서가 있으면 그대로 덧붙이지 않고, 오래된 내용은 지우거나 교체했다. 다음 세션의 첫 10분에 필요한 사실만 남기는 것이 기준이다.

## 산출물 갱신과 커밋

구현이 끝나면 코드만 맞추지 않고 관련 산출물도 함께 갱신했다.

주로 갱신한 문서는 다음과 같다.

- `tasks.md`
  - 완료된 task 상태 반영
- `delivery-evidence.md`
  - 테스트, 리뷰, 수동 검증 결과 반영
- `plan.md`
  - 구현 중 확정된 기술 결정 반영
- `quickstart.md`
  - 실제 실행 방법과 운영 확인 절차 반영
- `next-session-handoff.md`
  - 다음 세션 시작 기준 반영

마지막에는 `$git-commit`으로 현재 diff에 맞는 커밋 메시지를 작성했다. 이 skill은 staged diff를 먼저 보고, 없으면 working tree diff를 본다. 커밋 메시지는 지정한 경로 안의 변경만 기준으로 작성하고, 한국어 conventional commit 형식을 사용한다.

# 정리 및 결론

이번 개발에서 가장 효과가 있었던 점은 기획, 설계, 구현, 리뷰, 검증을 한 번에 섞지 않았다는 것이다. SpecKit으로 먼저 요구사항과 계획을 문서로 고정했고, ECC와 Codex CLI는 그 문서를 기준으로 작은 개발 사이클을 반복하는 데 사용했다.

팀에서 같은 방식을 적용할 때는 아래 기준을 지키는 것이 좋다.

- SpecKit은 구현 도구가 아니라 개발 전 기준선을 만드는 도구로 사용
- `$plan`은 전체 task를 한 번에 처리하는 계획이 아니라 한 개발 사이클의 계획으로 사용
- `$tdd`는 테스트 작성, RED 확인, 최소 구현, GREEN 확인 순서를 유지
- reviewer agent는 항상 전부 돌리지 않고 변경 성격에 맞게 선택
- 긴 작업은 `$handoff`로 다음 세션 시작점을 남김
- 테스트 결과와 판단 근거는 `delivery-evidence.md` 같은 문서에 남김

결론적으로 이 방식은 개발 판단을 문서와 테스트로 남기기 위한 작업 방식에 가깝다. 복잡한 기능일수록 agent에게 모든 걸 맡기기보다, 사람이 범위와 기준을 잡고 agent를 계획, 구현 보조, 리뷰, 정리에 나누어 쓰는 방식이 더 안정적이었다.

# 참고 문서

<!-- 관련 스펙, 매뉴얼, 설정 파일, 개발 산출물 링크를 정리한다. -->

- [SpecKit 공식 설치 문서](https://github.github.com/spec-kit/installation.html)
- [SpecKit GitHub 릴리스](https://github.com/github/spec-kit/releases)
- [RTK 공식 GitHub](https://github.com/rtk-ai/rtk)
- [Caveman 공식 GitHub](https://github.com/juliusbrussee/caveman)
- [andrej-karpathy-skills GitHub](https://github.com/forrestchang/andrej-karpathy-skills)
- `specs/001-git-repo-connection/spec.md`
- `specs/001-git-repo-connection/plan.md`
- `specs/001-git-repo-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/spec.md`
- `specs/002-gitlab-onprem-connection/plan.md`
- `specs/002-gitlab-onprem-connection/tasks.md`
- `specs/002-gitlab-onprem-connection/delivery-evidence.md`
- `specs/002-gitlab-onprem-connection/next-session-handoff.md`
