# 통신 표 가이드

## 목적

통신 경로와 연결 표기 방식을 한 문서 안에서 같이 관리하는 방법을 설명한다.

## 이 문서에서 별도 메모로 두지 않는 항목

- `기본 통신 표기 기준 초안`

이 항목은 별도 문서로 분리하지 않고, `Node 간 연결 표` 상단의 `표기 기준` 섹션으로 흡수하는 편이 더 효율적이다.

## 표기 원칙

- 외부 시스템과의 연결은 프로토콜 중심으로 표기
- `Knowledge Base`와의 연결은 접근 방식 중심으로 표기
- 같은 성격의 연결은 같은 이름으로 유지

## 1. Node 간 연결 표

### 이 산출물이 하는 일

최종 그림의 모든 선과 연결 표기 규칙을 한 문서에서 같이 관리한다.

### 예시 형태

```md
## 표기 기준
- HTTPS
- IDE UI
- Plugin API
- WebSocket
- REST
- WebHook / REST
- Git Protocol
- MCP
- Knowledge Read
- Knowledge R/W
- Knowledge Write

## 규칙
- 포트 번호는 쓰지 않는다
- 외부 연동은 프로토콜 이름을 우선 사용한다
- `Knowledge Base` 연결은 접근 방식 이름을 사용한다
- 같은 연결은 같은 이름으로 표기한다

| 출발 Node | 도착 Node | 방향 | 표기 | 목적 | 비고 |
|---|---|---|---|---|---|
| User | Web Application Node | Outbound | HTTPS | 사용자 접근 | 브라우저 경유 |
| Developer | IDE Plugin Node | Outbound | IDE UI | 로컬 IDE 진입 | public client |
| IDE Plugin Node | Web Application Node | Outbound | Plugin API | 업로드 · 컨텍스트 조회 | public client → gateway |
| Web Application Node | Interactive Assistant Node | Outbound | WebSocket | 대화 세션 | 실시간 |
| Interactive Assistant Node | Knowledge Base Node | Bidirectional | Knowledge R/W | 지식 조회 · 적재 | `Knowledge Base` 접근 |
```

## 완료 기준

- 표기 기준과 연결 표가 같은 문서 안에 있다
- 최종 그림의 모든 선이 표에 있다
