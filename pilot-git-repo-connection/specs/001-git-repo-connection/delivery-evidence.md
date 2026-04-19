# Delivery Evidence

## 목적

이 문서는 `001-git-repo-connection` 구현이 어떤 검증 근거로 완료되었는지 기록한다. 각 사용자 스토리의 검증 결과와 `FR-014`, `SC-001`부터 `SC-005`까지의 근거를 한곳에서 추적할 수 있어야 한다.

## 문서 사용 규칙

- 구현 중간에는 섹션과 기대 근거만 먼저 준비
- 실제 검증이 끝난 뒤 실행 로그, 테스트 결과, 수동 검증 링크를 채움
- 스토리별 완료 판단과 전체 릴리스 판단을 분리해서 기록

## 사용자 스토리 검증

### User Story 1

- 상태: 미검증
- 범위
  - 저장소 연결 생성
  - 기본 ref 검증
  - 초기 스냅샷 생성
  - traceability 기본 조회
- 근거
  - TODO

### User Story 2

- 상태: 미검증
- 범위
  - 범위 규칙 저장
  - `empty_result_risk` 경고
  - `NO_INCLUDED_FILES` 실패 처리
  - scope rule version 추적
- 근거
  - TODO

### User Story 3

- 상태: 미검증
- 범위
  - GitHub webhook 수신
  - Push/PR 최신화
  - dedupe와 stale head 처리
  - secret rotation grace
  - event timeline 조회
- 근거
  - TODO

## FR-014 추적성 근거

- 계획 입력 -> 연결 설정
  - TODO
- 연결 설정 -> scope rule version
  - TODO
- trigger event -> sync run
  - TODO
- sync run -> code snapshot
  - TODO
- code snapshot -> snapshot manifest
  - TODO

## 성공 기준 검증

### SC-001

- 목표: 저장소 연결부터 첫 스냅샷 완료 확인까지 10분 이내
- 근거: TODO

### SC-002

- 목표: 유효한 Push/PR 이벤트의 95% 이상이 1분 이내 상태 반영
- 근거: TODO

### SC-003

- 목표: 모든 스냅샷의 저장소, ref, 규칙, 수집 시점 추적 가능
- 근거: TODO

### SC-004

- 목표: 규칙과 실제 스냅샷 결과의 일치율 100%
- 근거: TODO

### SC-005

- 목표: webhook secret 회전 grace 기간 동안 유효 이벤트 중단 없이 처리
- 근거: TODO

## 테스트 증거 인덱스

- Unit
  - TODO
- Integration
  - TODO
- Contract
  - TODO
- End-to-End
  - TODO

## 변경 이력

- 2026-04-17: Phase 1 스캐폴드 초안 생성
