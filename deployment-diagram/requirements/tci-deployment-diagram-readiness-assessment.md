# TCI Deployment Diagram 작성 가능 여부 판단

## 목적

이 문서는 현재 [TCI Current System Architecture Briefing](/Users/seokhyunbae_1/Desktop/기획_스프린트/TCI/deployment-diagram/tci-current-system-architecture-briefing.md)을 기준으로, 지금 당장 TCI의 아키텍처 설명용 Deployment Diagram을 그릴 수 있는 상태인지 판단하고, 부족하다면 무엇이 더 필요하며 그 정보를 어떻게 수집해야 하는지 정리한 문서다.

이 문서는 팀장님 피드백을 반영해 아래 전제를 기준으로 판단한다.

- 초점은 `우리가 정의한 서비스가 어디서 제공되는가`
- 표현 수준은 `Node`와 `Artifact`
- `Execution Environment`는 이번 범위에서 제외
- 통신 경로는 프로토콜이 아니라 더 추상화된 통신 단계로 표현
- 외부 시스템은 필요 시 개별 서비스보다 역할군 단위로 묶어 표현
- `Knowledge Base`는 메인 그림에서 단일 Node를 기본값으로 고려
- 상위 경계는 `public / internal / external` 3영역을 기본값으로 고려
- 운영 배치도보다 아키텍처 설명용 그림을 우선

## 한 줄 결론

지금 상태는 **아키텍처 설명용 Deployment Diagram 초안 작성이 가능하다**.

다만 이 판단은 아래 범위를 전제로 한다.

- 서비스 제공 위치 중심
- Node와 Artifact 중심
- 실행 환경 생략
- 통신 단계 추상화

반대로 아래 수준의 Deployment Diagram은 아직 어렵다.

- 실행 환경까지 포함한 정밀 UML Deployment Diagram
- 운영 환경 차이와 인스턴스 수를 포함한 운영 배치도
- 프로토콜, 인프라, 비동기 런타임까지 닫힌 배포 구조도

즉, 지금 문서만으로도 `어떤 서비스가 어떤 제공 노드에 놓이고, 외부와 어떤 성격으로 연결되는가`는 그릴 수 있다. 하지만 `그 서비스가 정확히 어떤 런타임과 인프라 위에서 어떻게 실행되는가`까지는 아직 충분히 정리돼 있지 않다.

## 왜 지금은 더 그리기 쉬워졌는가

기존 판단에서는 Deployment Diagram에 필요한 실행 환경, 런타임, 프로토콜, 인프라 세부사항이 많이 비어 있어서 준비도가 낮다고 봤다.

하지만 이번 범위는 그보다 더 추상화되어 있다.

- `어디서 실행되는가`보다 `어디서 제공되는가`에 초점
- `Kubernetes`, `VM`, `서버리스` 같은 실행 환경은 제외
- `HTTPS`, `WebSocket`, `gRPC` 같은 프로토콜은 숨김
- 외부 시스템은 필요 시 역할군으로 묶고, `Knowledge Base`도 메인 그림에서는 단일 Node로 두는 쪽을 기본값으로 둔다
- 대신 서비스 제공 노드, 외부 시스템 경계, Artifact, 통신 목적만 표현

이렇게 범위를 조정하면 현재 C4 문서에서 이미 확보된 정보의 활용도가 높아진다.

현재 브리핑 문서는 아래 정보를 충분히 제공한다.

- 주요 사용자
- 주요 외부 시스템
- 주요 컨테이너
- 컨테이너 책임
- 상위 데이터 흐름
- Knowledge Base 중심 구조
- 상류 파이프라인과 하류 소비 계층의 구분

따라서 지금은 `정교한 배포 사실`은 부족하지만, `서비스 제공 구조`를 설명하는 수준의 Deployment Diagram은 그릴 수 있다.

## 지금 당장 그릴 수 있는 것

현재 자료만으로도 아래 수준의 그림은 만들 수 있다.

- 사용자가 `Web Application`을 통해 TCI에 진입한다는 사실
- `Data Collection`, `Data Processing`, `Knowledge Base`, `Analysis Engine`, `Interactive Assistant`, `Workflow & Integration`, `Operations Manager`가 주요 제공 서비스라는 사실
- 외부 시스템을 `개발 자산 소스`, `협업/관리 시스템`, `외부 자동화 채널`, `AI 소비 채널` 같은 역할군으로 묶어 표현할 수 있다는 사실
- `Knowledge Base`가 중앙 허브라는 사실
- 어떤 서비스가 상류 수집/처리 계층인지, 어떤 서비스가 분석/설명/실행 계층인지 구분할 수 있다는 사실

즉, 아래 질문에는 현재 문서만으로도 꽤 직접적으로 답할 수 있다.

- 사용자는 어디로 들어오는가
- 어떤 서비스가 사용자에게 직접 제공되는가
- 어떤 서비스가 내부 제공 계층에 속하는가
- 어떤 서비스가 외부 시스템과 연동하는가
- 어떤 노드가 데이터 허브 역할을 하는가

이 수준이라면 `서비스 제공 위치를 설명하는 아키텍처용 Deployment Diagram`은 충분히 시작할 수 있다.

## 지금 당장 그리기 어려운 것

이 섹션은 현재 기준의 대표 예시다. 완전한 누락 목록으로 읽으면 안 된다.

아래 질문에는 현재 브리핑만으로 답하기 어렵다.

- 여러 컨테이너를 각각 독립 Node로 그릴지, 일부를 하나의 서비스 제공 Node로 묶을지
- `Knowledge Base`를 하나의 Node로 그릴지, `Graph / Vector / Object / Search`로 나눌지
- `Workflow & Integration`을 하나의 제공 Node로 볼지, 운영 제어와 분리할지
- `Operations Manager`를 별도 제공 Node로 둘지, 관리 경로 수준으로만 둘지
- `IDE Plugin`과 `AI Agent`가 정확히 어느 접점으로 붙는지
- 업로드, 관리 기능, 외부 webhook이 같은 진입점인지 분리되는지
- 어떤 Artifact를 서비스별로 나눌지, 어떤 Artifact를 묶을지

즉, 이번 범위에서는 실행 환경보다 `서비스 제공 단위의 경계`와 `Node 분해 수준`이 더 중요한 미확정 요소다.

## 현재 상태 판정

현재 TCI는 아래 판정이 가장 정확하다.

### 1. C4 기준 아키텍처 이해도

- 충분함

### 2. 서비스 제공 위치 설명 준비도

- 가능

### 3. Node + Artifact 중심 Deployment Diagram 작성 준비도

- 부분적으로 가능

### 4. 실행 환경 포함 Deployment Diagram 작성 준비도

- 아직 부족

### 5. 운영 배치 설명 준비도

- 부족

## 이번 범위에서 확정된 표현 원칙

이번 Deployment Diagram은 아래 원칙을 먼저 고정해야 한다.

### 1. 다이어그램의 목표

- 서비스가 어디서 제공되는지 설명
- 외부 시스템과 내부 서비스 경계 설명
- Knowledge Base 중심 구조 설명
- 사용자 진입 경로와 내부 서비스 흐름 설명

### 2. 다이어그램에 포함할 것

- 사용자와 외부 시스템
- 서비스 제공 Node
- 각 Node에서 제공되는 Artifact
- Node 간 추상화된 통신 단계
- `public / internal / external` 같은 상위 경계

### 3. 다이어그램에서 의도적으로 생략할 것

- 컨테이너 런타임
- VM, Kubernetes, 서버리스 여부
- 세부 프로토콜
- 포트 번호
- 인스턴스 수
- 오토스케일링, 장애 조치 같은 운영 상세

### 4. 통신 경로 표기 원칙

이번 문서에서는 프로토콜 대신 아래처럼 통신의 목적과 성격을 적는 편이 맞다.

- 사용자 접근
- 내부 처리
- 지식 접근
- 외부 연동
- 운영 제어

필요하면 세부 단계로 아래를 하위 용어로 쪼갤 수 있다.

- 사용자 접근
  - 대화형 세션
  - 알림 전달
- 내부 처리
  - 분석 요청
  - 분석 결과 소비
  - 컨텍스트 제공
- 지식 접근
  - 지식 조회
  - 지식 적재

즉, 메인 그림에서는 `사용자 접근 / 내부 처리 / 지식 접근 / 외부 연동 / 운영 제어` 정도로 두고, 필요할 때만 더 세분화하는 방식이다.

## 부족한 정보 목록

이번 범위에서 Deployment Diagram을 더 설득력 있게 만들려면 아래 정보가 추가로 필요하다.

### 1. 다이어그램 범위와 Node 분해 수준

반드시 확정되어야 하는 질문

- 대표 환경 하나만 그릴 것인가
- 우리 시스템 내부만 그릴 것인가
- 외부 시스템도 함께 그릴 것인가
- 각 C2 컨테이너를 개별 Node로 볼 것인가
- 일부 컨테이너를 하나의 서비스 제공 Node로 묶을 것인가

이게 정해져야 그림이 C2 복사본이 되지 않고, 반대로 과도하게 잘게 쪼개지지도 않는다.

### 2. 각 서비스의 제공 위치

반드시 확정되어야 하는 질문

- `Web Application`은 어떤 제공 Node에서 노출되는가
- `Data Collection`은 어떤 내부 제공 Node에 속하는가
- `Data Processing`은 어떤 내부 처리 Node에 속하는가
- `Analysis Engine`은 어떤 분석 제공 Node에 속하는가
- `Interactive Assistant`는 별도 제공 Node인가
- `Workflow & Integration`은 실행 서비스 Node인가
- `Operations Manager`는 별도 운영 Node인가

예시 답변 형태

- `Web Application`: 사용자용 진입 Node
- `Interactive Assistant`: 대화형 설명 서비스 Node
- `Analysis Engine`: 분석 서비스 Node
- `Workflow & Integration`: 자동화 및 외부 연동 Node

### 3. Artifact 경계

반드시 확정되어야 하는 질문

- 각 컨테이너가 하나의 Artifact인가
- 여러 컨테이너가 하나의 서비스 Artifact로 묶이는가
- 메인 그림에서는 역할 중심 Artifact 이름만 둘 것인가
- 구체 배포 패키지 이름은 보조 표로만 둘 것인가

예시 답변 형태

- `User Access Artifact`
- `Analysis Service Artifact`
- `Knowledge Service Artifact`
- `Automation Service Artifact`
- `Operations Artifact`

### 4. Knowledge Base 표현 수준

현재 브리핑에서 가장 큰 미확정 지점 중 하나다.

논리적으로는 `Knowledge Base`가 하나의 컨테이너지만, 이번 그림에서는 아래 중 무엇이 맞는지 정해야 한다.

- 메인 그림에서는 하나의 중앙 지식 저장 Node로 표현
- 필요하면 상세 그림에서만 `Graph / Vector / Object / Search`를 분리
- 또는 단일 Node 안에 역할 중심 Artifact만 보조적으로 구분

즉, 기본값은 `단일 Knowledge Base Node`이고, 상세 표현이 꼭 필요할 때만 분해하는 쪽이 메인 그림 복잡도를 줄이기 쉽다.

### 5. 외부 채널의 실제 접점

TCI는 `IDE Plugin`, `AI Agent`, `Upload`, `ChatOps`, `MCP` 같은 다양한 입력/출력 채널이 있다.

반드시 확정되어야 하는 질문

- `IDE Plugin`은 사용자 로컬 IDE에서 어떤 TCI Node로 붙는가
- `AI Agent`는 `Web Application`을 통하는가, 별도 제공 Node를 쓰는가
- 업로드는 항상 `Web Application`을 통해 들어오는가
- 외부 webhook은 `Data Collection`에 붙는가, `Workflow & Integration`에 붙는가
- 운영 경로는 사용자 경로와 분리되는가

이 정보가 있어야 외부 노드를 개별 서비스로 그릴지, `외부 자동화 채널`, `AI 소비 채널` 같은 역할군으로 묶을지 정할 수 있다.

### 6. 상위 경계와 소유 구분

반드시 확정되어야 하는 질문

- 어떤 Node가 우리 시스템 제공 범위인가
- 어떤 Node가 외부 SaaS인가
- 어떤 Node가 public에 노출되는가
- 어떤 Node가 internal only인가
- admin 성격의 Node를 별도 경계로 둘 것인가

메인 그림에서는 `public / internal / external`을 기본값으로 두고, `Knowledge Base`나 `Operations Manager`를 별도로 강조해야 할 때만 `data` 또는 `admin`을 추가하는 쪽이 더 단순하다.

### 7. 추상 통신 단계 분류

반드시 확정되어야 하는 질문

- 어떤 연결을 `사용자 접근`으로 볼 것인가
- 어떤 연결을 `내부 처리`로 볼 것인가
- 어떤 연결을 `지식 접근`으로 볼 것인가
- 어떤 연결을 `외부 연동`으로 볼 것인가
- 어떤 연결을 `운영 제어`로 볼 것인가

필요하면 아래 하위 용어는 보조 설명으로만 사용한다.

- `내부 처리`
  - `분석 요청`
  - `분석 결과 소비`
  - `컨텍스트 제공`
- `지식 접근`
  - `지식 조회`
  - `지식 적재`

이 분류가 정해져야 통신 경로가 프로토콜이 아니라 의미 수준에서 일관되게 보인다.

## 정보를 어떻게 수집해야 하는가

아래 순서로 수집하는 것이 가장 효율적이다.

### 1. C2 컨테이너를 서비스 제공 Node로 매핑

현재 C2에는 논리 컨테이너가 정리돼 있다. 먼저 각 컨테이너마다 아래 질문을 붙여야 한다.

- 이 컨테이너는 독립 Node로 그릴 가치가 있는가
- 다른 컨테이너와 하나의 서비스 제공 Node로 묶는 편이 더 자연스러운가
- 사용자가 직접 인지하는 서비스인가
- 내부 처리 계층인가
- 운영 전용 계층인가
- 저장소인가

수집 방법

- 현재 C2 컨테이너별로 표 작성
- 각 컨테이너에 대해 `표현 Node` 컬럼 추가
- 불명확한 항목은 아키텍처 결정 필요 항목으로 표시

### 2. 각 Node의 Artifact 정의

각 Node에 대해 아래 질문을 해야 한다.

- 이 Node에서 제공되는 소프트웨어 Artifact는 무엇인가
- Artifact를 서비스 단위로 표현할 것인가
- 여러 기능을 하나의 Artifact로 묶을 것인가
- 메인 그림에서는 역할 중심 이름만 쓸 것인가

수집 방법

- C2와 C3 책임 범위를 보고 Artifact 후보 작성
- 메인 그림은 역할 기반 Artifact명 사용
- 구체 패키지명은 필요하면 보조 표에만 기록

정리 표 예시

| Node | Artifact | 역할 | 비고 |
|---|---|---|---|
| User Access Node | `User Access Artifact` | 사용자 진입 | public |
| Analysis Service Node | `Analysis Service Artifact` | 구조·영향·규칙 분석 | internal |
| Knowledge Base Node | `Knowledge Service Artifact` | 중앙 지식 저장 | internal |

### 3. Knowledge Base를 표현 수준에 맞게 분해

이 단계는 꼭 필요하다.

수집해야 할 질문

- 이번 그림에서 KB를 하나의 Node로 그릴 것인가
- `Graph / Vector / Object / Search`를 분리해서 보여줄 것인가
- Query Facade를 저장소 일부로 볼 것인가, 별도 Artifact로 볼 것인가

수집 방법

- 아키텍처 설명용 한 장 그림이면 우선 `중앙 Knowledge Base Node`로 확정
- 저장소 성격을 꼭 강조해야 할 때만 내부 하위 Artifact 또는 서브 Node로 분해

### 4. 내부 연결을 통신 단계로 재정리

외부 연결뿐 아니라 내부 연결도 별도로 정리해야 한다.

수집해야 할 질문

- `Web Application -> Interactive Assistant`는 어떤 통신 단계인가
- `Web Application -> Workflow & Integration`은 어떤 통신 단계인가
- `Data Collection -> Data Processing`은 어떤 통신 단계인가
- `Data Processing -> Knowledge Base`는 어떤 통신 단계인가
- `Analysis Engine -> Knowledge Base`는 어떤 통신 단계인가

수집 방법

- C2와 C3를 함께 보면서 `출발 Node / 도착 Node / 통신 단계 / 비고` 표 작성
- 메인 그림 예시는 `사용자 접근`, `내부 처리`, `지식 접근`, `외부 연동`, `운영 제어`
- 세부 설명이 필요하면 하위 용어로 `대화형 세션`, `분석 요청`, `지식 조회`, `지식 적재`, `알림 전달` 등을 보조 표에만 기록

### 5. 외부 시스템 연결 방식 확인

외부 시스템 이름만으로는 부족하다.

수집해야 할 질문

- 어떤 외부 시스템을 역할군으로 묶어 표현할 것인가
- `개발 자산 소스`는 어떤 서비스 Node와 연결되는가
- `협업/관리 시스템`은 어떤 서비스 Node와 연결되는가
- `AI 소비 채널`은 어떤 서비스 Node에서 컨텍스트를 받는가
- `외부 자동화 채널`은 어떤 서비스 Node가 담당하는가

수집 방법

- 브리핑 문서의 유입 채널 섹션 기반으로 연결 주체 표 작성
- 메인 그림은 역할군 단위 묶음을 기본값으로 검토
- 인증 방식, 트리거 방식은 이번 그림에서 필요하면 보조 표에만 기록

### 6. 상위 경계 결정

수집해야 할 질문

- `public`
- `internal`
- `data`
- `external`
- `admin`

위 다섯 경계를 모두 쓸 것인가, 아니면 더 단순화할 것인가

수집 방법

- 아키텍처 설명용 메인 그림은 우선 3영역으로 두는 안 검토
  - `public`
  - `internal`
  - `external`
- 데이터 중심성을 꼭 강조해야 할 때만 `data zone` 분리
- 운영 기능 분리를 꼭 강조해야 할 때만 `admin zone` 추가

## 추천 산출물

Deployment Diagram을 바로 그리기 전에 아래 자료를 먼저 만드는 것이 좋다.

### 1. 서비스 Node 매핑표

필수 컬럼

- C2 컨테이너
- 표현 Node
- 독립 표현 여부
- 사용자 노출 여부
- 내부 / 외부 / 운영 구분

### 2. Artifact 매핑표

필수 컬럼

- Node
- Artifact
- 역할
- 비고

### 3. Knowledge Base 표현 결정표

필수 컬럼

- 논리 요소
- 표현 방식
- 분리 여부
- 이유

### 4. 외부 연동 표

필수 컬럼

- 외부 시스템
- 외부 시스템 역할군
- 연결 주체 Node
- 통신 단계
- 비고

### 5. 내부 연결 표

필수 컬럼

- 출발 Node
- 도착 Node
- 통신 단계
- 비고

## 지금 기준 추천 판단

지금 바로 해야 할 일은 실행 환경까지 닫는 것이 아니라, 먼저 아래 세 단계를 닫는 것이다.

1. C2 컨테이너를 서비스 제공 Node로 매핑
2. 각 Node의 Artifact를 정리
3. Knowledge Base와 주요 연결을 어떤 추상화 수준으로 표현할지 결정

이 세 단계가 닫히면 아키텍처 설명용 Deployment Diagram은 무리 없이 그릴 수 있다.

## 바로 사용할 수 있는 수집 체크리스트

- [ ] 이번 그림의 범위가 아키텍처 설명용으로 고정돼 있다
- [ ] 실행 환경을 생략한다는 원칙이 합의돼 있다
- [ ] 각 C2 컨테이너를 어떤 Node로 표현할지 정해져 있다
- [ ] 각 Node의 Artifact 이름이 정해져 있다
- [ ] `Knowledge Base`를 하나의 Node로 그릴지 분해할지 정해져 있다
- [ ] 메인 그림에서 외부 시스템을 역할군으로 묶을지 정해져 있다
- [ ] 사용자 진입 Node가 정해져 있다
- [ ] 외부 시스템별 연결 주체 Node가 정해져 있다
- [ ] `IDE Plugin`, `AI Agent`, `Upload`의 접점이 정해져 있다
- [ ] `Operations Manager`를 별도 Node로 둘지 정해져 있다
- [ ] 통신 경로를 어떤 단계 용어로 표기할지 정해져 있다
- [ ] `public / internal / external` 경계가 정해져 있다
- [ ] 필요하면 `data zone`과 `admin zone` 추가 여부가 정해져 있다

## 최종 결론

현재 TCI는 C4 Diagram을 바탕으로 `서비스가 어디서 제공되는가`를 설명하는 Deployment Diagram 초안을 시작할 수 있다.

이번 범위에서는 아래 판단이 가장 정확하다.

- C4 기반 논리 아키텍처는 충분히 정리됨
- 서비스 제공 위치 중심 Deployment Diagram 초안은 가능
- Node + Artifact 중심의 추상화된 Deployment Diagram도 가능
- 실행 환경 중심 Deployment Diagram은 아직 추가 정보가 필요함

즉, 지금은 `그릴 수 있느냐`보다 `어떤 Node와 Artifact 수준으로 추상화할 것인가`가 더 중요한 단계다.
