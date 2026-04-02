# Artifact / Knowledge Base 표 가이드

## 목적

Artifact naming과 Knowledge Base 표현 방식을 한 묶음의 표 문서로 정리한다.

## 이 문서에서 별도 메모로 두지 않는 항목

- `Knowledge Base 표현 기본안 메모`

이 항목은 별도 문서로 분리하지 않고, `Knowledge Base 표현 결정표` 상단의 기본 원칙 섹션으로 흡수하는 편이 더 효율적이다.

## 1. Artifact 이름 및 Node 매핑표

### 이 산출물이 하는 일

그림에 표시할 Artifact 이름과, 그 Artifact를 어느 Node에 붙일지 한 번에 정한다.

### 예시 형태

```md
| Artifact 이름 | 담당 Node | 역할 | 표시 수준 | 비고 |
|---|---|---|---|---|
| User Access Artifact | Web Application Node | 사용자 진입 | 메인 그림 표시 | public |
| Graph Artifact | Knowledge Base Node | 지식 그래프 저장 | 내부 Artifact | data |
```

## 2. Knowledge Base 표현 결정표

### 이 산출물이 하는 일

Knowledge Base 내부 논리 요소별 표현 방식을 확정한다.

### 예시 형태

```md
## 기본 원칙
- 메인 그림에서는 Knowledge Base를 단일 Node로 유지
- 필요 시 내부에는 Runtime Environment를 중첩하고 Graph, Vector, Object Artifact를 구분
- Execution Environment는 top-level Node로 세지 않는다

| 논리 요소 | Runtime Environment | 표현 방식 | 메인 그림 표시 | 이유 |
|---|---|---|---|---|
| Graph Store | Graph DB Runtime | 내부 Artifact | 예 | 핵심 지식 모델 |
| Vector Store | Vector DB Runtime | 내부 Artifact | 예 | 임베딩 및 유사도 검색 |
| Object Store | Object Storage Runtime | 내부 Artifact | 예 | 원본 및 산출물 저장 |
| Query Facade | - | 메모로만 설명 | 아니오 | Node 수준 아님 |
```

## 완료 기준

- Artifact 이름과 Node 매핑, Knowledge Base 표현 방식이 서로 충돌하지 않는다
- Knowledge Base는 단일 Node + 내부 Artifact 원칙이 유지된다
