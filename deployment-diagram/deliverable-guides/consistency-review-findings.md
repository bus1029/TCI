# Deployment Diagram 산출물 일관성 점검 메모

## 목적

`deliverable-guides` 하위 문서가 최신 기준인 drawio 원본과 exported image에 맞는지 점검한 결과를 남긴다.

검토 기준:
- [tci-deployment-diagram.drawio](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio)
- [tci-deployment-diagram.drawio.png](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-deployment-diagram.drawio.png)

검토 대상:
- [00-index.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/00-index.md)
- [01-node-boundary-service-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/01-node-boundary-service/01-node-boundary-service-output-1.md)
- [02-touchpoint-external-system-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/02-touchpoint-external-system/02-touchpoint-external-system-output-1.md)
- [03-artifact-knowledge-base-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/03-artifact-knowledge-base/03-artifact-knowledge-base-output-1.md)
- [04-communication-output-1.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/04-communication/04-communication-output-1.md)
- [05-final-diagram-kb-runtime-draft-explanation.md](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/deliverable-guides/05-final-diagram/05-final-diagram-kb-runtime-draft-explanation.md)

## 한눈에 보는 결론

- 최신 기준은 drawio와 exported image다.
- 이번 정리로 `deliverable-guides` 문서는 drawio 기준과 맞게 갱신됐다.
- 핵심 반영 사항은 `Data Collection & Processing` 단일 노드, `Knowledge Base` 내부 4계층, 정확한 연결 라벨(`Knowledge R/W`, `Knowledge Read`, `Knowledge Write`, `WebHook / REST`)이다.

## 이번에 확인하고 반영한 포인트

### 1. top-level Node 수와 내부 서비스 구성이 최신 drawio와 맞는다

상태: 정렬됨

정리:
- 최신 drawio의 top-level Node는 총 15개다.
- TCI 직접 통제 범위는 `Web Application`, `IDE Plugin`, `Interactive Assistant`, `Analysis Engine`, `Workflow & Integration`, `Data Collection & Processing`, `Knowledge Base` 7개다.
- 기존 문서에 남아 있던 `Data Collection` / `Data Processing` 분리 서술은 `Data Collection & Processing` 단일 Node 기준으로 정리했다.

### 2. `Knowledge Base` 내부 구조는 4계층 기준으로 맞는다

상태: 정렬됨

정리:
- `Knowledge Base`는 메인 그림에서 단일 top-level Node다.
- 내부 상세는 `Object Storage Runtime Environment`, `Vector DB Runtime Environment`, `Graph DB Runtime Environment`, `RDB Runtime Environment` 4계층이다.
- 대응 artifact는 `Object Artifact`, `Vector Artifact`, `Graph Artifact`, `Metadata Artifact`다.

### 3. 통신선 이름과 방향이 drawio와 맞는다

상태: 정렬됨

정리:
- 업로드 경로는 `Web Application -> Data Collection & Processing`이다.
- `Workflow & Integration`의 `Knowledge Read`는 drawio 화살표 방향에 맞춰 `Workflow & Integration <- Knowledge Base`로 문서화했다.
- CI/CD 연동 라벨은 drawio의 실제 표기인 `WebHook / REST`로 맞췄다.

### 4. 설명 문서의 기준 파일을 drawio로 고정했다

상태: 정렬됨

정리:
- `05-final-diagram-kb-runtime-draft-explanation.md`는 이제 drawio 원본과 exported image를 기준 문서로 본다.
- `tci-deployment-diagram-kb-runtime-draft.puml`은 초안 기록으로만 남고, 최신 기준 문서로는 사용하지 않는다.

## 메모

- 가이드 문서 예시는 여전히 추상적일 수 있지만, 현재 직접 입력 산출물과 최신 다이어그램 사이의 구조적 충돌은 정리됐다.
- 이후 변경이 생기면 drawio를 먼저 갱신하고, `deliverable-guides`는 그 결과를 따라가는 방식으로 유지한다.
