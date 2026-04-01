# Deployment Diagram 산출물 가이드 인덱스

## 왜 묶었는가

산출물 이름과 문서 수를 1:1로 맞추면 파일 수만 많아지고, 내용이 짧은 산출물은 오히려 찾기 불편해진다.

그래서 이 디렉터리는 아래 원칙으로 재구성했다.

- 의미가 가까운 산출물끼리 하나의 가이드 문서로 묶음
- 각 가이드 문서 안에서 산출물별 섹션으로 분리
- 인덱스는 `산출물 이름 -> 가이드 문서 + 섹션` 기준으로 제공

## 묶음 구조

- `01-node-boundary-service-guides.md`
  - Node 선정
  - 서비스 Node 매핑
  - 서비스 제공 위치
  - 상위 경계
  - 우리 시스템 / 외부 서비스 구분
- `02-touchpoint-external-system-guides.md`
  - 사용자 진입
  - 외부 시스템 역할군
  - 외부 시스템별 접속 지점
  - 외부 채널 접점
- `03-artifact-knowledge-base-guides.md`
  - Artifact 이름 및 Node 매핑
  - Knowledge Base 표현 결정표
- `04-communication-guides.md`
  - Node 간 연결 표
- `05-final-diagram-guide.md`
  - 최종 Deployment Diagram 초안

## 산출물별 이동표

| 산출물 | 가이드 위치 |
|---|---|
| `포함할 Node / 제외할 Node 목록` | `01-node-boundary-service-guides.md` / `포함할 Node / 제외할 Node 목록` |
| `서비스 Node 매핑 초안` | `01-node-boundary-service-guides.md` / `서비스 Node 매핑 초안` |
| `서비스별 제공 위치 표` | `01-node-boundary-service-guides.md` / `서비스별 제공 위치 표` |
| `상위 경계 초안` | `01-node-boundary-service-guides.md` / `상위 경계 초안` |
| `우리 시스템 / 외부 서비스 구분표` | `01-node-boundary-service-guides.md` / `우리 시스템 / 외부 서비스 구분표` |
| `사용자 진입 경로 표` | `02-touchpoint-external-system-guides.md` / `사용자 진입 경로 표` |
| `외부 시스템 역할군 표` | `02-touchpoint-external-system-guides.md` / `외부 시스템 역할군 표` |
| `외부 시스템별 접속 지점 표` | `02-touchpoint-external-system-guides.md` / `외부 시스템별 접속 지점 표` |
| `외부 채널 접점 표` | `02-touchpoint-external-system-guides.md` / `외부 채널 접점 표` |
| `Artifact 이름 및 Node 매핑표` | `03-artifact-knowledge-base-guides.md` / `Artifact 이름 및 Node 매핑표` |
| `Knowledge Base 표현 결정표` | `03-artifact-knowledge-base-guides.md` / `Knowledge Base 표현 결정표` |
| `Node 간 연결 표` | `04-communication-guides.md` / `Node 간 연결 표` |
| `최종 Deployment Diagram 초안` | `05-final-diagram-guide.md` / `최종 Deployment Diagram 초안` |

## 공통 작성 원칙

- 대표 환경은 1개만 다룸
- C1 외부 시스템은 전체 포함
- C2 컨테이너는 모두 Node로 매핑
- Knowledge Base는 단일 Node + 내부 Artifact 구분
- 상위 경계는 `public / private / external / data`
- 통신 경로는 프로토콜 형태로 표기
- 산출물마다 추상화 수준을 섞지 않는다
