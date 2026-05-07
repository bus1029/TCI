# 결론

공통 Agent Harness의 목적은 Agent와 모델을 하나로 통일하는 것이 아니다. 각자가 다른 Agent를 쓰더라도 같은 작업 단위, 같은 산출물 형식, 같은 검증 기준, 같은 보안 경계를 통과하게 만드는 것이다.

Agent 시대의 병목은 코드 작성 속도보다 리뷰, 검증, 컨텍스트 전달, 충돌 해결, 민감 정보 노출에서 자주 생긴다. Harness는 이 병목을 사람이 매번 판단하지 않도록 자동 검사와 명확한 중단 기준으로 바꿔야 한다.

# Harness가 맡아야 할 일

Harness는 다음 네 가지를 팀 공통 규칙으로 고정한다.

- 작업 단위와 이름
- 실행 환경과 허용 명령
- 테스트와 evidence 형식
- 보안과 민감 정보 처리 기준

Agent 선택 자유는 실행 도구의 자유여야 한다. 산출물 형식, 검증 기준, 보안 경계까지 자유롭게 두면 통합 비용이 다시 사람에게 돌아온다.

# 기본 원칙

## Agent는 바꿔도 산출물은 같아야 한다

팀원이 Codex, Claude Code, Copilot coding agent, Cursor, 사내 Agent를 섞어 쓰더라도 Harness가 받는 산출물은 같아야 한다.

- SpecKit artifact 위치와 이름
- feature ID와 branch 이름
- task status 형식
- acceptance와 테스트 연결 방식
- evidence 파일 형식
- handoff 형식
- reviewer finding 형식

Agent별 출력 차이는 Harness 밖에서만 허용한다. Harness 안으로 들어오는 순간에는 팀 표준 형식으로 정규화한다.

## 자동 실패 조건을 먼저 정한다

Harness가 단순히 “확인해야 할 항목”을 나열하면 결국 사람이 다시 판단한다. 실무에서 병목을 줄이려면 자동 실패 조건이 필요하다.

Harness는 다음 누락을 실패로 처리한다.

- feature ID와 branch, spec, task, evidence, handoff 이름 불일치
- 완료된 task의 evidence 누락
- acceptance 항목과 테스트 또는 evidence 연결 누락
- 민감 정보 처리 확인 누락
- 미해결 reviewer finding이 남은 상태의 완료 시도

## 자동화와 사람 판단을 구분한다

Harness는 모든 판단을 자동화하려고 하면 안 된다. 자동화할 수 있는 것은 빠르게 막고, 품질 판단이 필요한 것은 reviewer가 보도록 분리한다.

| 구분 | Harness 처리 기준 |
| --- | --- |
| 자동 실패 | 이름 불일치, evidence 누락, 필수 검증 명령 누락, 미해결 HIGH finding |
| 자동 경고 | 쓰기 범위 밖 변경, 공동 수정 영역 변경, 예상보다 넓은 diff |
| 사람 리뷰 | 테스트 검증력, 남은 리스크의 타당성, 변경 의도의 명확성 |
| 사람 승인 | 위험 작업 Gate, 외부 provider 쓰기 작업, 되돌리기 어려운 작업 |

## 위험한 작업은 별도 Gate를 통과한다

모든 작업을 같은 절차로 다루면 속도가 느려진다. 반대로 위험한 작업을 일반 작업처럼 다루면 사고가 난다.

별도 Gate가 필요한 작업은 다음과 같다.

- 인증, 권한, 세션, 토큰 처리 변경
- 데이터 삭제, migration, 되돌리기 어려운 작업
- 외부 webhook, 외부 provider 연동 변경
- 민감 정보 저장, 출력, 로그, evidence 처리 변경

이 작업들은 reviewer checklist만으로 끝내지 않는다. Harness가 사전 검사 단계에서 위험 작업으로 표시하고, 필요한 검증과 승인 조건을 요구해야 한다.

# 작업 격리 규칙

## 기준 단위

작업은 모듈이 아니라 완결 기능 단위 또는 기반 단위 기준으로 격리한다.

권장 이름은 다음 형식을 따른다.

```text
NNN-capability-unit-name
```

예시는 다음과 같다.

- `010-repository-snapshot-manifest`
- `011-local-upload-snapshot`
- `020-stack-detection-maven`
- `031-impact-direct-dependency-api`

브랜치, worktree, cloud agent task, subagent 작업은 모두 같은 feature ID를 공유해야 한다. 도구마다 작업 컨테이너가 달라도 Harness가 추적하는 단위는 하나여야 한다.

## 공동 수정 영역

Agent 병렬화에서 실제 충돌은 일반 파일보다 공동 수정 영역에서 자주 난다. 공동 수정 영역은 한 시점에 하나의 작업만 수정한다.

공동 수정 영역은 다음을 포함한다.

- migration
- 공통 schema
- lockfile
- 공통 예제 데이터와 기대 결과
- generated file
- SpecKit template
- `AGENTS.md`와 Harness 설정

공동 수정 영역을 수정해야 하는 작업은 Plan에 이유와 순서를 적는다. 여러 완결 기능 단위가 같은 공동 수정 영역을 요구하면 먼저 기반 단위로 분리한다.

## 쓰기 범위

각 작업은 쓰기 범위를 명시한다.

예시는 다음과 같다.

- `src/tci/domain/services/create_local_upload_snapshot.py`
- `src/tci/infrastructure/persistence/local_upload_repository.py`
- `tests/unit/local_uploads/`
- `specs/NNN-local-upload-snapshot/`

Agent는 명시된 쓰기 범위 밖의 파일을 수정하기 전에 이유를 남겨야 한다. Harness는 범위 밖 변경을 발견하면 PR 본문이나 evidence에 설명이 있는지 확인한다.

# 실행 환경 규칙

Agent가 자기 환경에서 build, test, validate를 실행할 수 있어야 결과 품질이 올라간다. Harness는 실행 환경을 개인 기억이나 Agent 추론에 맡기지 않는다.

각 작업에는 다음 실행 기준이 있어야 한다.

- 기본 cwd
- 필수 환경 변수 이름
- 실행 가능한 build, lint, typecheck, test 명령
- 네트워크 접근 허용 범위
- DB, Redis, 외부 provider 대체 방식
- 실패 시 남길 로그 범위

값 자체가 민감한 환경 변수는 기록하지 않는다. Harness는 존재 여부와 key 이름만 확인한다.

# 컨텍스트 규칙

## 컨텍스트 번들

Agent에게 전체 저장소와 전체 대화를 넘기지 않는다. 작업마다 필요한 컨텍스트 번들을 만든다.

컨텍스트 번들은 다음을 포함한다.

- 목표와 범위 밖 항목
- 관련 spec, plan, tasks
- 읽어야 할 대표 파일
- 수정 가능한 쓰기 범위
- 검증 명령
- 참고해야 할 기존 패턴
- 남은 리스크와 금지 작업

컨텍스트 번들은 짧고 현재 상태 중심이어야 한다. 오래된 대화 요약이나 과한 규칙 묶음은 Agent 성능을 떨어뜨린다.

## 새 세션 기준

다음 상황에서는 새 세션을 연다.

- 다른 완결 기능 단위로 이동
- Agent가 같은 실패를 반복
- 구현과 검증이 끝남
- 대화가 길어져 현재 파일 상태와 이전 결정이 섞임

새 세션에는 전체 대화 대신 현재 목표, 변경 파일, 검증 명령, 남은 리스크, 참고해야 할 artifact만 넘긴다.

# 민감 정보 처리 기준

Harness는 민감 정보가 context, log, evidence, MCP 입력, PR 본문에 들어가지 않게 막아야 한다.

민감 정보는 다음을 포함한다.

- `.env` 값
- access token, refresh token, API key
- cookie, session token, Authorization header
- private key, deploy key, webhook secret
- credential이 포함된 URL
- raw provider response에 섞인 인증 정보

Harness는 값이 아니라 존재 여부와 key 이름만 확인한다. 실패 로그나 provider 응답을 남겨야 할 때는 민감 값을 제거한 일부만 evidence에 남긴다.

# Evidence 규칙

Feature는 merge 가능한 코드가 아니라 재현 가능한 증거까지 포함해야 끝난다.

Evidence에는 다음을 남긴다.

- 실행 명령
- cwd
- 대상 commit 또는 diff 기준
- 실행 시각
- 테스트 데이터
- 검증 방식: 자동 검증 또는 운영자 확인
- 통과 또는 실패 결과
- 실패 로그의 민감 정보 제거 일부
- 남은 리스크와 다음 조치

TCI처럼 외부 연동, 코드 스냅샷, 분석 결과, Agent 컨텍스트를 다루는 제품은 evidence 없이 완료 처리하면 다음 Agent가 잘못된 전제를 이어받기 쉽다.

# 테스트 규칙

Agent가 만든 테스트는 양보다 검증력으로 판단한다. 테스트 파일이 늘어났다는 사실만으로 품질이 올라갔다고 보지 않는다.

핵심 테스트는 acceptance 항목 또는 task ID와 연결한다. 테스트 이름, 주석, evidence 중 하나에서 어떤 사용자 가치나 운영 리스크를 검증하는지 추적 가능해야 한다.

테스트 작성 기준은 다음과 같다.

- 핵심 도메인 판단은 domain service 테스트로 검증
- 외부 시스템 경계는 adapter 예제 데이터 또는 contract test로 검증
- persistence와 queue 경계는 integration test로 검증
- mock은 외부 네트워크, 시간, 난수, 비싼 API 비용을 끊을 때 우선 사용

과도한 mock은 실패 가능성을 숨긴다. reviewer는 테스트가 실제 상호작용을 검증하는지, 구현 세부사항만 따라가는지 확인해야 한다.

# 리뷰 규칙

Agent 도입 후 병목은 코드 작성에서 리뷰, 검증, 시스템 이해로 이동한다. 팀은 구현 속도보다 검토 가능성을 먼저 설계해야 한다.

PR은 하나의 완결 기능 단위 또는 기반 단위만 포함한다. PR 본문에는 다음을 포함한다.

- 변경 의도
- 관련 spec, task, acceptance 링크
- 주요 변경 파일
- 실행한 검증 명령
- 남은 리스크
- reviewer가 집중해서 볼 파일

reviewer finding은 severity, 소유자, 처리 결과, 재검증 명령을 남긴다. HIGH 이상 finding은 같은 PR에서 수정과 재검증 evidence가 끝나기 전까지 완료 처리하지 않는다.

# CI와 PR Gate 규칙

Harness 결과는 문서에만 남기지 않고 CI와 PR Gate에 연결해야 한다. 사람이 문서를 읽어야만 발견되는 규칙은 반복될수록 지켜지지 않는다.

PR에서 required check로 둘 항목은 다음과 같다.

- artifact 이름과 위치 검사
- feature ID와 task/evidence 연결 검사
- build, lint, typecheck, test 실행
- 민감 정보 처리 기준 검사
- secret scan
- dependency audit
- reviewer finding 처리 상태 검사

branch protection은 이 required check가 통과되기 전 merge를 막아야 한다. dependency audit은 package manifest나 lockfile이 바뀐 경우 필수로 실행한다.

# 실패 복구 규칙

Agent가 같은 실패를 반복하면 더 많은 프롬프트를 붙이지 않는다. 실패 원인을 분류하고 작업을 멈출 기준을 둔다.

중단 기준은 다음과 같다.

- 같은 테스트 실패 2회 반복
- 같은 reviewer finding 재발
- 쓰기 범위 밖 변경 반복
- 민감 정보 처리 위반

중단 후에는 새 세션에서 목표, 실패 원인, 변경 파일, 검증 명령만 넘긴다. 실패한 긴 대화 전체를 이어 붙이지 않는다.

# 최소 구축 순서

처음부터 모든 Gate를 자동화하려 하면 Harness 자체가 큰 프로젝트가 된다. 최소 구축 순서는 다음이 현실적이다.

1. artifact 이름과 위치 검사
2. feature ID와 branch/task/evidence 연결 검사
3. 검증 명령과 evidence 형식 검사
4. CI required check 연결
5. 민감 정보 처리 기준 검사
6. secret scan과 dependency audit 연결
7. reviewer finding 처리 상태 검사
8. 공동 수정 영역 충돌 검사
9. branch protection 연결

이 순서로 만들면 팀은 먼저 산출물 형식을 통일하고, 이후 보안과 병렬화 병목을 점진적으로 줄일 수 있다.

# 참고 자료

- [Anthropic Claude Code best practices](https://code.claude.com/docs/en/best-practices)
- [GitHub Copilot task best practices](https://docs.github.com/en/enterprise-cloud@latest/copilot/tutorials/cloud-agent/get-the-best-results)
- [OpenAI Codex docs](https://developers.openai.com/codex/cloud)
- [OpenAI Codex agent internet access](https://developers.openai.com/codex/cloud/internet-access)
- [VS Code AI best practices](https://code.visualstudio.com/docs/copilot/best-practices)
- [Google secure AI agents](https://research.google/pubs/an-introduction-to-googles-approach-for-secure-ai-agents/)
- [OWASP LLM06 Excessive Agency](https://genai.owasp.org/llmrisk/llm062025-excessive-agency/)
- [OWASP Prompt Injection Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/LLM_Prompt_Injection_Prevention_Cheat_Sheet.html)
- [Spec-driven development paper](https://openreview.net/pdf?id=bw5mNj75h9)
