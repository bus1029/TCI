# 구현 참조 가이드

## 목적

이 문서는 `pilot-git-repo-connection` 실행 루트 안에서 `001-git-repo-connection` 기능을 구현하는 에이전트가 바로 일을 시작할 수 있도록 만든 기준서다. 이 파일을 먼저 읽고, 여기서 지정한 원문 문서를 함께 열어 구현한다.

이 문서의 경로 표기는 모두 `pilot-git-repo-connection/` 실행 루트를 기준으로 해석한다. 따라서 canonical spec 문서는 `../specs/001-git-repo-connection/` 아래에 있고, `AGENTS.md`는 상위 저장소 루트의 `../AGENTS.md`를 뜻한다.

## 기준 문서 우선순위

문서가 충돌하면 아래 순서를 따른다.

1. `../specs/001-git-repo-connection/spec.md`
2. `../specs/001-git-repo-connection/plan.md`
3. `../specs/001-git-repo-connection/tasks.md`
4. `../specs/001-git-repo-connection/data-model.md`
5. `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
6. `../specs/001-git-repo-connection/research.md`
7. `../specs/001-git-repo-connection/quickstart.md`
8. `../AGENTS.md`

## 문서별 역할

- `../specs/001-git-repo-connection/spec.md`
  - 기능 범위
  - 사용자 스토리
  - 기능 요구사항
  - 성공 기준
- `../specs/001-git-repo-connection/plan.md`
  - 구현 전략
  - 구조
  - 사용자 스토리별 슬라이스
- `../specs/001-git-repo-connection/tasks.md`
  - 실제 작업 순서
  - 선행 관계
  - 테스트 우선 순서
- `../specs/001-git-repo-connection/data-model.md`
  - 엔티티
  - 필드
  - 상태 전이
  - 관계
- `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
  - API 경로
  - 요청과 응답 필드
  - 오류 코드
  - webhook 계약
- `../specs/001-git-repo-connection/research.md`
  - 설계 이유
  - 운영 규칙
  - 필터 우선순위
  - dedupe 규칙
- `../specs/001-git-repo-connection/quickstart.md`
  - 수동 검증 시나리오
  - 회귀 검증 흐름
- `../AGENTS.md`
  - 상위 기술 스택
  - 프로젝트 전반 구조 참고

## 구현 시작 전 필수 읽기 순서

1. `../specs/001-git-repo-connection/spec.md`
2. `../specs/001-git-repo-connection/plan.md`
3. `../specs/001-git-repo-connection/tasks.md`
4. `../specs/001-git-repo-connection/data-model.md`
5. `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
6. `../specs/001-git-repo-connection/research.md`
7. `../specs/001-git-repo-connection/quickstart.md`
8. `../AGENTS.md`

## 작업 종류별 참조 문서 묶음

### 공통 시작

- `../specs/001-git-repo-connection/spec.md`
- `../specs/001-git-repo-connection/plan.md`
- `../specs/001-git-repo-connection/tasks.md`

### 영속 계층과 마이그레이션

- `../specs/001-git-repo-connection/tasks.md`
- `../specs/001-git-repo-connection/plan.md`
- `../specs/001-git-repo-connection/data-model.md`
- `../specs/001-git-repo-connection/research.md`

### API 스키마와 라우트

- `../specs/001-git-repo-connection/tasks.md`
- `../specs/001-git-repo-connection/spec.md`
- `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
- `../specs/001-git-repo-connection/data-model.md`

### Git, snapshot, webhook 처리

- `../specs/001-git-repo-connection/tasks.md`
- `../specs/001-git-repo-connection/plan.md`
- `../specs/001-git-repo-connection/research.md`
- `../specs/001-git-repo-connection/data-model.md`
- `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`

### 운영 화면과 조회 모델

- `../specs/001-git-repo-connection/tasks.md`
- `../specs/001-git-repo-connection/spec.md`
- `../specs/001-git-repo-connection/data-model.md`
- `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
- `../specs/001-git-repo-connection/quickstart.md`

### 테스트와 검증

- `../specs/001-git-repo-connection/tasks.md`
- `../specs/001-git-repo-connection/spec.md`
- `../specs/001-git-repo-connection/contracts/repository-ingestion.openapi.yaml`
- `../specs/001-git-repo-connection/quickstart.md`

## 권장 개발 순서

반드시 `tasks.md`의 Phase 순서를 따른다.

1. `Phase 1`
   - 패키지 골격
   - 테스트 골격
   - 설정 파일
   - 검증 문서 틀
2. `Phase 2`
   - 공통 엔티티
   - 마이그레이션
   - Git mirror
   - snapshot 저장 기반
   - traceability 기반
3. `US1`
   - 저장소 연결
   - 기본 ref 검증
   - 초기 snapshot
4. `US2`
   - 범위 규칙
   - 경고와 실패 처리
   - scope rule version 추적
5. `US3`
   - GitHub webhook
   - dedupe
   - stale head 처리
   - secret rotation grace
6. `Polish`
   - 회귀 검증
   - quickstart 검증
   - `delivery-evidence.md` 정리

## 기본 작업 방식

1. 현재 작업의 선행 조건을 `../specs/001-git-repo-connection/tasks.md`에서 확인
2. 작업 종류에 맞는 문서 묶음을 함께 열기
3. 테스트를 먼저 작성하거나 기대 계약을 먼저 고정
4. 최소 구현으로 테스트를 통과시킴
5. 상태값, 필드명, 오류 코드를 문서와 다시 대조
6. `../specs/001-git-repo-connection/quickstart.md` 기준으로 수동 또는 통합 검증 가능성을 점검
7. 완료 시 `delivery-evidence.md`에 근거를 기록

## 구현 중 자주 확인할 규칙

- 저장소 연결 1건은 기본 ref 1개만 유지
- GitHub Cloud만 v1 공식 지원
- SSH와 HTTPS 모두 읽기 전용 credential만 허용
- canonical connection 상태는 `active`, `reauth_required`, `ref_missing`만 사용
- webhook 이상은 health projection으로 분리 노출
- 바이너리와 `5 MiB` 초과 파일은 v1에서 항상 제외
- Push와 PR만 snapshot 갱신 트리거
- Commit은 기록만 하고 snapshot 갱신은 시작하지 않음
- PR snapshot은 source branch 최신 HEAD 기준
- PR action은 `opened`, `reopened`, `synchronize`, `ready_for_review`만 갱신 대상
- dedupe는 delivery ID와 target HEAD SHA 두 단계로 처리
- traceability는 런타임 조회 가능 상태여야 함

## 시작 체크리스트

- [ ] `../specs/001-git-repo-connection/spec.md` 확인
- [ ] `../specs/001-git-repo-connection/plan.md` 확인
- [ ] `../specs/001-git-repo-connection/tasks.md`에서 현재 작업 번호 확인
- [ ] 작업 종류에 맞는 문서 묶음 열기
- [ ] 필드명과 상태값을 `../specs/001-git-repo-connection/data-model.md`, 계약 파일과 일치시키기
- [ ] 운영 규칙이 헷갈리면 `../specs/001-git-repo-connection/research.md`에서 먼저 확인
- [ ] 완료 기준을 `../specs/001-git-repo-connection/quickstart.md`로 역산

## 한 줄 요약

이 기능은 `../specs/001-git-repo-connection/spec.md -> ../specs/001-git-repo-connection/plan.md -> ../specs/001-git-repo-connection/tasks.md`로 범위와 순서를 고정하고, 구현 시에는 `../specs/001-git-repo-connection/data-model.md`, 계약 파일, `../specs/001-git-repo-connection/research.md`, `../specs/001-git-repo-connection/quickstart.md`를 항상 함께 보면서 `Phase 1 -> Phase 2 -> US1 -> US2 -> US3 -> Polish` 순서로 진행한다.
