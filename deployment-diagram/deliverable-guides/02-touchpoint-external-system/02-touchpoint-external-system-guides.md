# 사용자 진입 / 외부 시스템 표 가이드

## 목적

사용자 진입, 업로드, 외부 시스템, 외부 채널 접점을 한 묶음의 표 문서로 정리하는 방법을 설명한다.

## 이 문서에서 별도 메모로 두지 않는 항목

- `사용자에게 보이는 Node 메모`
- `업로드 접점 정리 메모`
- `업로드 / IDE Plugin / AI Agent 접점 메모`
- `외부 시스템 역할군 기준 메모`

위 항목들은 각각 별도 문서로 만들기보다 아래 표의 컬럼이나 표 상단의 `기준` 섹션에 흡수하는 편이 더 효율적이다.

## 1. 사용자 진입 경로 표

### 이 산출물이 하는 일

사람 액터가 어떤 경로로 어떤 Node에 처음 진입하는지 정리한다. AI Coding Agent 같은 비인간 소비자 채널은 외부 시스템 접속 지점에서 별도로 다룬다.

### 권장 흡수 항목

- `사용자에게 보이는 Node 메모`
- `업로드 접점 정리 메모`

### 예시 형태

```md
| 액터 | 진입 채널 | 최초 진입 Node | 이후 연결 | 비고 |
|---|---|---|---|---|
| Developer | 웹 브라우저 | Web Application Node | Interactive Assistant | 기본 경로 |
| Developer | IDE Plugin | IDE Plugin Node | Web Application Node | public client 경유 |
| 사용자의 업로드 | 업로드 UI | Web Application Node | Data Collection & Processing Node | ZIP / PDF |
```

## 2. 외부 시스템 역할군 표

### 이 산출물이 하는 일

각 외부 시스템이 어떤 역할군에 속하는지 정리한다.

### 예시 형태

```md
## 역할군 기준
- 1차 초안은 개별 시스템으로 정리
- 가독성이 떨어질 때만 역할군 묶음 검토

| 외부 시스템 | 역할군 | 표현 방식 | 이유 |
|---|---|---|---|
| Code Repository | 개발 자산 소스 | 개별 유지 | 핵심 연동 |
| Ticket System | 협업 관리 시스템 | 역할군 후보 | 유사 계열 |
```

## 3. 외부 시스템별 접속 지점 표

### 이 산출물이 하는 일

각 외부 시스템이 어느 내부 Node와 연결되는지 정리한다.

### 예시 형태

```md
| 외부 시스템 | 연결 주체 Node | 방향 | 프로토콜 | 비고 |
|---|---|---|---|---|
| Code Repository | Data Collection & Processing Node | Outbound | Git Protocol | 코드 수집 |
| Policy Engine | Workflow & Integration Node | Outbound | REST | 정책 검증 |
| AI Coding Agent | Workflow & Integration Node | Bidirectional | MCP / REST | 컨텍스트 제공과 요청 수신 |
```

## 4. 외부 채널 접점 표

### 이 산출물이 하는 일

시스템 단위가 아니라 채널 단위로 접점을 묶어서 본다.

### 예시 형태

```md
| 외부 채널 | 연결 Node | 대표 예시 | 프로토콜 | 비고 |
|---|---|---|---|---|
| 코드 수집 채널 | Data Collection & Processing Node | Code Repository | Git Protocol | 입력 중심 |
| AI 소비 채널 | Workflow & Integration Node | AI Coding Agent | MCP, REST | 컨텍스트 전달 |
```

## 완료 기준

- 사용자 진입과 외부 시스템 접점이 한 묶음 안에서 이어진다
- 메모형 판단은 표의 컬럼 또는 기준 섹션에 흡수된다
