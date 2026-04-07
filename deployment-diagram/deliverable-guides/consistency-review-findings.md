# Deployment Diagram 산출물 일관성 점검 메모

## 목적

`deliverable-guides` 하위 산출물들 사이에서 용어, 구조, 표현 원칙이 현재 기준과 맞는지 빠르게 확인하기 위한 점검 메모다.

검토 대상:
- [00-index.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/00-index.md)
- [01-node-boundary-service-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/01-node-boundary-service/01-node-boundary-service-output-1.md)
- [02-touchpoint-external-system-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/02-touchpoint-external-system/02-touchpoint-external-system-output-1.md)
- [03-artifact-knowledge-base-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/03-artifact-knowledge-base/03-artifact-knowledge-base-output-1.md)
- [04-communication-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/04-communication/04-communication-output-1.md)
- [05-final-diagram-guide.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/05-final-diagram-guide.md)

## 한눈에 보는 결론

- 현재 `output-1.md` 4개는 Notion 기준에 맞춰 주요 충돌이 해소된 상태다.
- 핵심 정렬 사항은 `IDE Plugin`의 public client 해석, `Web Application -> Data Collection` 업로드 경로, `Execution Environment`의 top-level Node 비카운트 원칙 반영, 외부 연동과 `Knowledge Base` 연결의 표기 원칙 분리다.
- 남은 차이는 주로 가이드 문서의 예시가 추상적이라는 점이며, 실제 산출물 기준에는 직접적인 충돌을 만들지 않는다.

## 현재 기준으로 확인된 정렬 상태

### 1. `IDE Plugin` 표현 축이 정리됨

상태: 정렬됨

설명:
- [01-node-boundary-service-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/01-node-boundary-service/01-node-boundary-service-output-1.md)는 `IDE Plugin`을 TCI 내부의 `public client node`로 둔다.
- [02-touchpoint-external-system-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/02-touchpoint-external-system/02-touchpoint-external-system-output-1.md)는 `Developer -> IDE Plugin -> Web Application` 경로로 정리한다.
- [04-communication-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/04-communication/04-communication-output-1.md)는 `Developer -> IDE Plugin (IDE UI)`와 `IDE Plugin -> Web Application (Plugin API)`를 분리해 같은 해석을 유지한다.

정리:
- `IDE Plugin`은 외부 시스템이 아니라 public 경계의 client node로 고정됐다.

### 2. 업로드 경로가 통신 표까지 닫힘

상태: 정렬됨

설명:
- [02-touchpoint-external-system-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/02-touchpoint-external-system/02-touchpoint-external-system-output-1.md)는 브라우저 업로드와 IDE Plugin 업로드가 모두 `Web Application -> Data Collection`로 수렴한다고 명시한다.
- [04-communication-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/04-communication/04-communication-output-1.md)는 `Web Application -> Data Collection` 선을 `HTTPS`와 `파일·문서 업로드 전달`로 반영한다.

정리:
- 사용자 진입 문서와 실제 연결 표 사이의 업로드 경로 누락이 해소됐다.

### 3. `Execution Environment` 처리 원칙이 공통 원칙에 반영됨

상태: 정렬됨

설명:
- [01-node-boundary-service-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/01-node-boundary-service/01-node-boundary-service-output-1.md)는 `Execution Environment`를 범위에 포함하되 `top-level Node 비카운트`로 둔다.
- [00-index.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/00-index.md)도 같은 원칙을 반영한다.

정리:
- `EE를 뺀다`와 `EE를 일부만 드러낸다` 사이의 혼선이 줄었다.

### 4. `Knowledge Base`는 단일 Node + 내부 4계층으로 정리됨

상태: 정렬됨

설명:
- [01-node-boundary-service-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/01-node-boundary-service/01-node-boundary-service-output-1.md)는 메인 경계에서 `Knowledge Base`를 단일 Top-level Node로 둔다.
- 현재 최종 다이어그램 설명 문서는 `Graph / Object / Vector / RDB` 4개 nested runtime을 기준으로 설명한다.
- `RDB Runtime Environment`에는 `Metadata Artifact`를 배치해 정형 메타데이터 계층을 드러낸다.

정리:
- 메인 그림 기준은 `Knowledge Base 단일 Node`로 유지한다.
- 내부 상세는 `Graph / Vector / Object / RDB` 4계층으로 본다.
- 인덱싱 관련 환경/아티팩트는 별도 Runtime/Artifact로 승격하지 않는다.

### 5. 통신선 이름은 대상별 표기 원칙으로 정리됨

상태: 정렬됨

설명:
- [04-communication-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/04-communication/04-communication-output-1.md)는 현재 사용 중인 표기(`HTTPS`, `WebSocket`, `Plugin API`, `Knowledge R/W`, `MCP / REST`)를 한 문서에 모아 관리한다.
- [02-touchpoint-external-system-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/02-touchpoint-external-system/02-touchpoint-external-system-output-1.md)의 접속 지점 표도 같은 이름을 사용한다.

정리:
- 외부 시스템 연결은 프로토콜 중심으로, `Knowledge Base` 연결은 접근 방식 중심으로 표기한다.
- "같은 연결은 같은 이름으로 표기" 원칙은 현재 기준에서 지켜지고 있다.

## 남아 있는 오픈 포인트

### 1. 가이드 문서는 추상 예시 위주라 현재 산출물의 최신 결정을 모두 담지는 않음

심각도: 낮음

설명:
- `01~04-*-guides.md`는 작성 방식 설명용이라 현재 산출물의 최신 결정을 모두 재진술하지는 않는다.
- 다만 실제 산출물 형식을 오도할 정도의 직접 충돌은 현재 크지 않다.

권장 정리:
- 이후 가이드 정비 시 `IDE Plugin은 public client node`, `Execution Environment는 top-level Node 비카운트` 정도만 예시에 반영하면 충분하다.

## 우선순위 제안

### 지금 상태로 바로 진행 가능한 것

1. `Node / 경계 / 서비스`
2. `사용자 진입 / 외부 시스템`
3. `통신 표`
4. `최종 Deployment Diagram 초안`

## 메모

- 현재 기준으로는 `output-1.md` 4개를 최종 다이어그램의 직접 입력 자료로 사용해도 된다.
- Knowledge Base 내부 상세는 `Graph / Vector / Object / RDB` 4계층 기준으로 맞춰졌다.
