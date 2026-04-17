# Research: 코드 저장소 연동 설계 결정

## Research Focus

이번 문서는 구현 가이드보다 설계 입력 문서 품질을 높이는 데 초점을 둔다. `spec.md`의 Clarifications와 Edge Cases를 그대로 남겨두지 않고, plan 단계에서 필요한 운영 규칙과 경계 조건을 명시적 결정으로 고정한다. 구현 기준은 단일 Python codebase를 전제로 한 FastAPI API, Celery worker, SQLAlchemy/Alembic persistence, Jinja2/HTMX 운영 UI 조합이다.

## 결정 1: GitHub Cloud만 공식 지원하되, 저장소 본문 수집은 Git transport 중심으로 처리한다

**Decision**: v1은 GitHub Cloud 저장소만 공식 지원한다. 연결 검증과 스냅샷 수집은 Python 서비스가 `git ls-remote`, `git fetch`, `git archive` 또는 동등한 Git transport 흐름을 subprocess로 호출해 처리하고, 실시간 이벤트는 GitHub webhook 계약을 따른다.

**Rationale**:
- `FR-001a`가 GitHub Cloud만 공식 지원 대상으로 제한한다.
- SSH/HTTPS 읽기 전용 연결과 branch/tag 선택은 Git transport가 가장 직접적이다.
- GitHub webhook은 `X-GitHub-Delivery`, `X-GitHub-Event`, `X-Hub-Signature-256` 헤더를 제공하므로 이벤트 무결성과 dedupe 기준을 명확히 둘 수 있다.
- 저장소 내용 수집은 provider API보다 Git transport가 snapshot 재현성에 유리하다.
- GitPython 같은 라이브러리 추상화보다 Git CLI subprocess 호출이 mirror 관리와 `git archive` 사용 범위를 명확히 통제하기 쉽다.

**Alternatives considered**:
- GitHub REST/GraphQL API 우선 수집: PR 메타데이터는 편하지만 Git tree 전체 스냅샷과 SSH 연결 요구를 자연스럽게 만족하지 못한다.
- GitPython 중심 구현: 일부 작업은 단순하지만 mirror/fetch/archive 전체 흐름을 CLI만큼 예측 가능하게 다루기 어렵다.
- 다중 provider 동시 지원: 장기적으로 타당하지만 현재 spec 범위를 넘어간다.

## 결정 2: 저장소 연결 1건은 기본 ref 1개만 가진다

**Decision**: 영속 설정은 연결당 기본 분석 ref 1개(branch 또는 tag)만 허용한다. Pull Request source branch는 저장소 연결 설정을 늘리지 않고, 이벤트 payload에서 파생되는 예외 타깃으로만 취급한다.

**Rationale**:
- Clarification에서 이미 연결 1건당 기본 ref 1개만 유지하기로 확정했다.
- 운영자가 어떤 ref가 상시 기준인지 명확히 이해할 수 있다.
- `FR-015`와 충돌 없이 PR 최신화만 예외 처리할 수 있다.

**Alternatives considered**:
- 연결 1건당 여러 ref 영속 관리: 멀티 target 설계로 확장성은 좋지만 승인된 spec을 넘어간다.
- PR별 가상 연결 생성: 이벤트 추적은 단순하지만 운영 모델이 복잡해진다.

## 결정 3: 연결 메타데이터와 비밀정보는 분리 저장하고, 시크릿 회전은 revision 모델로 관리한다

**Decision**: `RepositoryConnection`에는 비밀값 자체를 두지 않고, 읽기 전용 저장소 자격 증명과 webhook secret은 각각 revision 레코드로 분리 저장한다. webhook secret 회전 시 현재 revision과 직전 revision을 24시간 grace window 동안만 허용하고, 어떤 revision이 검증에 사용됐는지는 이벤트 기록과 운영 상태 조회에 남긴다.

**Rationale**:
- `FR-001b`, `FR-016`, `FR-017`은 연결 단위 비밀정보 저장과 secret 상태 추적을 요구한다.
- 회전 직후 GitHub webhook 설정 반영 지연이 있을 수 있으므로 짧은 중첩 허용 구간이 운영상 안전하다.
- revision 분리는 누가 언제 무엇을 바꿨는지 감사 추적을 남기기 쉽다.
- Python 애플리케이션 계층에서 credential과 webhook secret을 같은 암호화 추상화로 다뤄도 수명 주기와 UI 상태는 분리해야 한다.

**Alternatives considered**:
- 연결 레코드에 단일 비밀값만 저장: 단순하지만 회전 이력과 grace handling이 불가능하다.
- grace 없이 즉시 교체: 보안은 단순하지만 운영 전환 실패율이 높아진다.

## 결정 4: mirror cache는 연결 단위 로컬 bare mirror를 사용한다

**Decision**: 연결마다 `.runtime/git-mirrors/{connectionId}.git` 경로에 bare mirror를 유지한다. 연결 검증은 `git ls-remote`로 시작하고, 초기 수집과 이벤트 최신화는 해당 mirror에 `git fetch --prune`를 적용한 뒤 스냅샷 export를 수행한다.

**Rationale**:
- AGENTS의 활성 기술 스택에 `.runtime/git-mirrors`가 이미 기준 저장소로 정의되어 있다.
- branch/tag 이동, 재검증, 이벤트성 PR source ref 추적을 재클론 없이 수행할 수 있다.
- webhook burst 상황에서 네트워크 비용과 지연 시간을 줄인다.
- Celery worker가 stateless하게 재기동되더라도 로컬 bare mirror를 재사용해 작업 시간을 일정하게 유지할 수 있다.

**Alternatives considered**:
- 스냅샷마다 fresh clone: 초기 구현은 쉽지만 비용이 크고 이벤트 폭주에 약하다.
- 영구 worktree 유지: 단일 ref에는 편하지만 PR source branch 처리와 정리 비용이 커진다.

## 결정 5: Code Snapshot은 메타데이터와 파일 아카이브를 분리한 완전 스냅샷으로 저장한다

**Decision**: 성공한 각 수집은 완전 스냅샷 1건을 생성한다. 스냅샷 메타데이터, manifest, 파일별 해시는 PostgreSQL에 저장하고, 실제 파일 본문은 `.runtime/code-snapshots/{snapshotId}` 아래 content-addressed archive로 저장한다.

**Rationale**:
- `FR-005a`는 필터 적용 후 전체 파일 집합을 완전한 스냅샷으로 보존하라고 요구한다.
- 파일 본문을 DB에 직접 저장하면 대형 저장소에서 테이블 팽창과 백업 부담이 과도해진다.
- 메타데이터와 파일 본문을 분리하면 manifest 비교, 감사 추적, 재분석 입력 고정이 쉬워진다.
- Python 애플리케이션에서 archive 생성과 manifest 기록을 분리하면 실패 지점을 `SNAPSHOT_WRITE_FAILED`와 메타데이터 롤백으로 명확히 나눌 수 있다.

**Alternatives considered**:
- commit SHA와 path만 저장: 재현성은 있으나 원격 저장소 상태 변화나 credential 만료 시 재분석 보장이 깨진다.
- 모든 파일 본문을 PostgreSQL에 저장: 구현은 단순하지만 운영 비용이 높다.

## 결정 6: 범위 규칙 평가는 고정 순서와 하드 가드레일을 가진다

**Decision**:
1. 시스템 하드 제외 경로를 먼저 적용한다: `.git/**`, `node_modules/**`, `dist/**`, `build/**`, `.next/**`, `coverage/**`, `target/**`, `vendor/**`.
2. 사용자 include path를 적용한다. 비어 있으면 전체 트리를 후보로 본다.
3. 사용자 exclude path를 적용한다.
4. 파일 타입 허용/차단 규칙을 적용한다.
5. 최종적으로 텍스트 판정과 크기 제한을 적용한다. 기본 최대 포함 크기는 5 MiB이며, 바이너리 또는 비텍스트 판정 파일은 사용자가 예외 규칙을 주더라도 v1에서는 수집하지 않는다.

**Rationale**:
- `FR-006`, `FR-007`, `FR-013`과 User Story 2의 기대치를 충족하려면 우선순위가 문서로 고정되어야 한다.
- 생성 산출물과 대용량 파일은 분석 가치보다 비용이 크다.
- 사용자가 include를 주더라도 바이너리/초대형 파일을 허용하면 파일럿 운영 안정성이 낮아진다.
- Python 필터 엔진은 glob/extension/text sniffing을 분리 구현할 수 있으므로, 평가 순서를 문서로 먼저 고정하는 편이 유지보수에 유리하다.

**Alternatives considered**:
- 사용자 규칙만 전적으로 신뢰: 유연하지만 운영 비용과 실패 가능성이 높다.
- MIME 기반 정밀 판별만 사용: 정확도는 높지만 v1에 과한 구현 복잡도를 만든다.

## 결정 7: 웹훅은 FastAPI raw body HMAC 검증 후 비동기 처리한다

**Decision**: GitHub webhook 엔드포인트는 FastAPI에서 raw request body를 확보한 뒤 `X-Hub-Signature-256` HMAC SHA-256 검증을 수행한다. 검증 성공 시 이벤트 레코드를 영속화하고 Celery queue에 enqueue한 뒤 `202 Accepted`를 반환한다.

**Rationale**:
- GitHub 공식 문서는 webhook delivery 검증에 `X-Hub-Signature-256` 사용을 권장한다.
- GitHub 공식 문서는 webhook 소비자가 빠르게 응답하고 비동기 후처리를 하도록 권장한다.
- FastAPI/Starlette는 request body를 직접 읽는 패턴을 제공하므로, 서명 계산을 원문 기준으로 일관되게 수행할 수 있다.
- Celery는 Redis 기반 비동기 작업과 재시도 정책을 분리해 API 응답 경로를 짧게 유지하기 쉽다.

**Alternatives considered**:
- 파싱된 JSON body 기준 서명 검증: 직렬화 차이로 검증 실패 가능성이 있다.
- 동기식 전체 처리 후 응답: 재시도와 타임아웃 위험이 커진다.
- RQ/Dramatiq 채택: 단순성은 장점이지만 현재 요구된 재시도/상태 분리 모델에서는 Celery의 운영 패턴이 더 익숙하다.

## 결정 8: 이벤트 기록과 스냅샷 트리거 규칙을 분리한다

**Decision**:
- `commit_comment`, `create`, `delete` 등 ref 이동을 직접 나타내지 않는 이벤트는 v1 수집 대상이 아니다.
- Push 이벤트는 기본 ref와 일치하는 ref에 대해서만 스냅샷 갱신 후보가 된다.
- Pull Request 이벤트는 `opened`, `reopened`, `synchronize`, `ready_for_review` 액션에서만 스냅샷 갱신 후보가 된다.
- Commit 이벤트 개념은 GitHub webhook의 별도 이벤트로 처리하지 않고, Push/PR payload에서 commit 메타데이터를 기록용으로 추출해 `RepositoryEvent`에 남긴다.

**Rationale**:
- 승인된 spec은 Commit, Push, PR의 세 가지 도메인 이벤트를 구분하지만 GitHub 실제 delivery 모델은 Push/PR 중심이다.
- Commit을 독립적 snapshot trigger로 사용하지 않겠다는 Clarification을 구현 가능한 webhook 계약으로 번역해야 한다.
- PR `closed` 또는 `converted_to_draft`는 상태 기록은 필요하지만 새 스냅샷 생성 가치는 낮다.

**Alternatives considered**:
- 모든 PR action에서 스냅샷 생성: 잡 폭증과 노이즈가 크다.
- Push payload의 모든 commit을 개별 snapshot 대상으로 처리: spec과 상충한다.

## 결정 9: dedupe는 delivery ID와 target HEAD SHA 두 층으로 처리한다

**Decision**:
- `RepositoryEvent`는 provider delivery ID에 unique 제약을 둔다.
- queue enqueue key는 `connectionId + triggerType + targetKey + headSha`로 생성한다.
- target cursor는 `default_ref` 또는 `pr:{pullRequestNumber}` 단위로 최신 accepted `headSha`를 유지한다.
- 지연 도착 이벤트가 cursor보다 오래된 SHA를 가리키면 이력은 남기되 `stale_head_skipped`로 종료한다.

**Rationale**:
- `FR-011a`, `FR-011b`가 요구하는 중복 제거와 최신 SHA 우선 처리를 만족한다.
- GitHub는 redelivery를 지원하므로 delivery ID dedupe가 필요하다.
- 동일 SHA에 대한 중복 Push/PR 재전송까지 막으려면 target SHA 단위 dedupe가 추가로 필요하다.
- Celery job id만으로는 DB 상태와 독립적으로 정확한 dedupe 감사 추적을 남기기 어렵다.

**Alternatives considered**:
- delivery ID만 dedupe: 같은 SHA를 다른 delivery가 가리키면 중복 스냅샷이 생긴다.
- SHA만 dedupe: redelivery 감사 추적과 재시도 관찰성이 약해진다.

## 결정 10: 운영자 UI는 Jinja2 + HTMX 기반 서버 렌더링으로 단일 Python 서비스 안에 둔다

**Decision**: 운영자 화면은 별도 프런트엔드 런타임을 추가하지 않고 FastAPI 애플리케이션 내부의 Jinja2 템플릿과 HTMX 상호작용으로 구현한다. JSON API와 HTML route는 같은 도메인 서비스 계층을 공유한다.

**Rationale**:
- 사용자는 내부 운영자이며, UI 요구가 대규모 소비자용 인터랙션보다 상태 가시성과 운영 정확도에 가깝다.
- Python 기반 개발로 전환한다는 목표에 맞춰 백엔드와 UI를 단일 기술 스택으로 유지할 수 있다.
- HTML route와 JSON API가 같은 traceability projection을 재사용하면 뷰 모델 정합성이 좋아진다.
- 별도 Node/React 런타임을 유지하지 않아도 spec이 요구하는 connection detail, scope warnings, event timeline UI를 충분히 제공할 수 있다.

**Alternatives considered**:
- React/Next.js 프런트엔드 유지: 구현 선택지는 넓지만 Python-only 설계 목표와 어긋난다.
- 순수 JSON API만 제공: 운영자 경험 요구를 충족하기 어렵고 quickstart 검증 흐름도 약해진다.

## 결정 11: Edge Case는 운영 상태 코드와 거부 사유로 분리 노출한다

**Decision**:
- credential 만료/취소: 연결 상태를 `reauth_required`로 전환하고 이후 자동 수집을 중단한다.
- 기본 ref 삭제/이름 변경: 연결 상태를 `ref_missing`으로 전환하고 운영자에게 새 ref 선택을 요구한다.
- webhook secret 누락: 연결 상태를 `webhook_unconfigured`로 표기하고 delivery는 `secret_missing` 거부 사유로 기록한다.
- webhook secret 불일치: 연결 상태는 `active`를 유지하되 `webhookHealth.status = secret_mismatch_detected`로 노출하고 delivery는 `secret_mismatch` 거부 사유로 기록한다.
- 기타 서명 검증 실패: delivery는 `signature_invalid` 거부 사유로 기록하고 `webhookHealth.status = signature_invalid_recently`를 갱신한다.
- 범위 규칙 결과가 0개 파일: 저장 시 경고, 실행 시 `NO_INCLUDED_FILES` 실패로 종료한다.
- `FR-012` 운영 요약은 connection detail에 `lastSuccessfulSnapshotAt`, `lastFailedSyncAt`, `lastProcessedEvent`를 제공하고, 상세 이력은 event timeline 조회로 분리한다.

**Rationale**:
- User Story 2, `FR-012`, `FR-013`, `FR-017`, Edge Cases가 모두 운영자 가시성을 요구한다.
- connection detail에 요약과 상세 이력을 함께 넣기보다, 요약은 즉시 판단용으로 두고 상세는 timeline으로 분리해야 응답 크기와 운영자 인지 부하를 함께 줄일 수 있다.
- 상태 코드를 문서에서 먼저 고정해야 UI/백엔드/worker 로그가 같은 언어를 쓴다.

**Alternatives considered**:
- 모든 실패를 generic error로 통합: 구현은 쉽지만 운영자가 재설정 절차를 알기 어렵다.
- UI에서만 메시지 변환: API와 worker 감사 추적이 불일치할 수 있다.

## 결정 12: FR-014는 문서 링크가 아니라 런타임 조회 가능한 traceability chain으로 닫는다

**Decision**: planning input은 별도 reference 레코드로 보관하고, `RepositoryConnection`은 해당 planning input reference를 가리킨다. `CollectionScopeRuleVersion`, `RepositorySyncRun`, `RepositoryEvent`, `CodeSnapshot`은 이미 가진 FK와 version 필드를 통해 "어떤 계획 입력에서 나온 연결 설정이 어떤 이벤트와 어떤 스냅샷으로 이어졌는지"를 API 응답에서 역추적 가능하게 노출한다.

**Rationale**:
- `FR-014`는 계획 입력, 저장소 연결 설정, 이벤트 기록, 코드 스냅샷 사이의 추적 관계를 유지해야 한다고 요구한다.
- delivery evidence 문서만으로는 운영 중 발생한 snapshot이 어떤 planning input과 설정 버전을 기준으로 생성됐는지 즉시 확인하기 어렵다.
- 별도 traceability entity를 추가하면 connection detail, event list, snapshot detail에서 같은 provenance vocabulary를 재사용할 수 있다.

**Alternatives considered**:
- delivery evidence 문서만으로 추적: 구현은 단순하지만 런타임 역추적이 안 된다.
- 모든 엔티티에 문서 링크 문자열을 중복 저장: 조회는 쉬우나 정합성과 수정 비용이 나빠진다.

## Clarification Closure

아래 항목은 spec의 clarify/edge case를 plan 단계에서 추가 구체화한 결과다.

| 주제 | 구체화 결과 |
|------|-------------|
| 기본 ref 삭제/변경 | 다음 검증 또는 수집 시 `ref_missing`으로 전환하고 새 ref 선택 전까지 snapshot job 차단 |
| credential 회전 | 새 revision 활성화, 직전 revision 24시간 grace, 이후 자동 폐기 |
| webhook secret 회전 | current + previous revision 허용, grace 종료 후 previous reject |
| secret mismatch 상태 표현 | 연결은 `active` 유지, `webhookHealth.status = secret_mismatch_detected`, event rejection reason은 `secret_mismatch` |
| 빈 수집 결과 | 저장 시 warning, 실행 시 hard fail(`NO_INCLUDED_FILES`) |
| 바이너리/대용량 예외 | v1에서는 사용자 예외 규칙이 있어도 수집 불가, 후속 범위로 남김 |
| FR-012 요약 책임 | connection detail은 최근 성공/실패 시각과 마지막 처리 이벤트 요약 제공, 상세 이력은 event timeline 조회가 담당 |
| PR force push | 같은 PR 번호 cursor의 최신 `headSha`만 반영, 이전 SHA job은 stale 처리 |
| Commit 이벤트 의미 | GitHub 개별 webhook 타입이 아니라 Push/PR payload에서 분리 기록되는 도메인 이벤트로 정의 |

## Sources Used

- GitHub Docs, Validating webhook deliveries: https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- GitHub Docs, Best practices for using webhooks: https://docs.github.com/en/webhooks/using-webhooks/best-practices-for-using-webhooks
- FastAPI Docs, Using the Request Directly: https://fastapi.tiangolo.com/advanced/using-request-directly/
- Celery Docs, Retrying Tasks: https://docs.celeryq.dev/en/stable/userguide/tasks.html#retrying
- Alembic Docs, Tutorial: https://alembic.sqlalchemy.org/en/latest/tutorial.html
