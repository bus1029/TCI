# Deployment Diagram 가이드

## 한 줄 요약

Deployment Diagram은 소프트웨어 아티팩트가 어떤 배포 대상에 올라가고, 그 대상들이 어떤 통신 경로로 연결되는지 보여주는 UML 구조 다이어그램이다.

쉽게 말하면 코드의 내부 구조를 설명하는 그림이 아니라, 시스템이 실제로 어디에서 실행되고 어떻게 연결되는지를 설명하는 그림이다.

## 먼저 감으로 이해하기

예를 들어 웹 서비스를 운영한다고 가정해보자.

```text
사용자 브라우저
  -> 로드밸런서
  -> 웹 서버 또는 CDN
  -> 애플리케이션 실행 환경
  -> 데이터베이스
  -> 캐시
```

이 구조를 Deployment Diagram으로 그리면 다음 질문에 답하기 쉬워진다.

- 사용자는 어떤 진입점을 통해 서비스에 들어오는가
- 어떤 애플리케이션이 어떤 실행 환경에서 동작하는가
- 데이터베이스와 캐시는 어디에 붙어 있는가
- 이 구조가 단일 노드인지, 여러 노드인지
- 외부 시스템과 내부 시스템의 경계가 어디인지

중요한 점은 이 그림이 단순 서버 목록이 아니라는 것이다. 핵심은 "무엇이 어디에 배포되고, 무엇과 무엇이 연결되는가"다.

## Deployment Diagram이 무엇인가

OMG의 UML 2.5.1은 UML을 시스템 산출물을 시각화하고 명세하고 문서화하기 위한 표준 언어로 정의한다. Deployment Diagram은 그중 배포 구조와 실행 구조를 다루는 구조 다이어그램이다. [1]

IBM 설명에 따르면 Deployment Diagram은 시스템의 물리 아키텍처를 모델링한다. 소프트웨어와 하드웨어의 관계, 처리의 물리적 분산, 각 노드에 저장되거나 실행되는 아티팩트를 표현하는 데 사용된다. 보통 구현 단계에서 많이 쓰이지만, 배포 구조를 설계하는 단계에서도 충분히 사용할 수 있다. [2]

UML-Diagrams 정리에 따르면 Deployment Diagram의 핵심은 "소프트웨어 아티팩트를 배포 대상에 할당하는 것"이다. 여기서 배포 대상은 보통 노드이며, 노드는 하드웨어 장치일 수도 있고 소프트웨어 실행 환경일 수도 있다. [3][4]

즉, Deployment Diagram은 아래 두 가지를 함께 보여주는 그림이라고 이해하면 된다.

- 소프트웨어가 어떤 배포 단위로 존재하는가
- 그 배포 단위가 어떤 인프라 또는 실행 환경 위에 놓이는가

## UML 기준 핵심 개념

이 문서를 제대로 이해하려면 아래 개념을 분리해서 봐야 한다.

### 1. Node

Node는 배포 대상이다. UML 기준으로는 계산 자원을 제공하는 요소를 뜻한다. [2][4]

Node는 크게 두 부류로 나뉜다.

- Device
- Execution Environment

### 2. Device

Device는 물리적 계산 자원이다.

예시

- 물리 서버
- PC
- 모바일 기기
- IoT 장치
- 프린터
- 센서

실무에서는 VM이나 클라우드 인스턴스를 Device처럼 다루는 경우가 많지만, UML 설명에서는 보통 물리 또는 계산 자원을 대표하는 노드로 이해하면 된다.

### 3. Execution Environment

Execution Environment는 소프트웨어가 실제 실행되는 환경을 뜻하는 노드다. [2][4]

예시

- 운영체제
- JVM
- 애플리케이션 서버
- DBMS
- 브라우저 런타임
- 컨테이너 런타임

중요한 점은 "서버"와 "실행 환경"이 같은 것이 아니라는 점이다.

예를 들어 다음처럼 계층적으로 표현할 수 있다.

- `Physical Server`
  - `Linux`
    - `Docker`
      - `Spring Boot App`

UML에서는 이런 식으로 노드를 중첩해서 표현할 수 있다. [4]

### 4. Artifact

Artifact는 개발 또는 배포 과정에서 생기는 물리적 산출물이다. Deployment Diagram에서는 보통 실제 배포되는 단위를 의미한다. [2][3][4]

대표 예시

- `app.jar`
- `frontend.zip`
- `nginx.conf`
- `schema.sql`
- `docker image`
- `terraform module`

문서, 테스트 보고서, 설계 산출물도 넓은 의미의 artifact일 수는 있다. 하지만 Deployment Diagram 학습에서는 "실제로 배포 대상에 올라가는 단위" 위주로 이해하는 편이 더 정확하다.

### 5. Deployment 관계

Deployment 관계는 어떤 Artifact가 어떤 Node에 배포되는지를 나타낸다. [2][4][5]

예시

- `payment-service.jar` 가 `App Server` 에 배포됨
- `frontend build` 가 `Web Server` 에 배포됨
- `etl-batch.py` 가 `Batch Runtime` 에 배포됨

UML 2.x에서는 컴포넌트를 직접 노드에 배포하는 것보다, Artifact를 Node에 배포하는 방식으로 이해하는 것이 맞다. [3][4]

### 6. Manifestation 관계

이 개념이 입문 문서에서 자주 빠진다.

UML 2.x에서는 보통 다음 흐름으로 이해한다. [3][5]

- Component는 논리적 구성 요소
- Artifact는 그 구성 요소의 실제 구현 또는 배포 산출물
- Node는 그 산출물이 올라가는 배포 대상

즉, 관계를 단순화하면 아래와 같다.

```text
Component
  <- manifest -
Artifact
  - deploy ->
Node
```

예를 들어 `Payment Service` 라는 컴포넌트가 있고, 그 구현 산출물이 `payment-service.jar` 라면, Deployment Diagram에서는 주로 `payment-service.jar` 가 어느 노드에 배포되는지를 본다.

### 7. Communication Path

Communication Path는 배포 대상 사이의 통신 경로다. UML에서는 배포 대상 간 association의 한 형태로 본다. [2][4][5]

대표 예시

- HTTPS
- TCP/IP
- gRPC
- AMQP
- 내부 전용망
- 물리 네트워크 링크

주의할 점은 Communication Path가 항상 상세 프로토콜 수준일 필요는 없다는 것이다. 어떤 다이어그램은 `Private Network` 정도로만 적고, 어떤 다이어그램은 `HTTPS:443` 처럼 더 구체적으로 적는다. 다이어그램의 목적에 맞춰 추상화 수준을 정하면 된다.

### 8. Deployment Specification

실무에서는 자주 빠지지만 UML에는 Deployment Specification도 있다. 이는 특정 아티팩트가 노드에 어떻게 배포되는지 정의하는 설정 정보를 의미한다. IBM은 XML 문서나 텍스트 설정 파일 같은 예를 든다. [2]

예시

- `application-prod.yml`
- `server.xml`
- `deployment.yaml`

복잡한 시스템에서는 실행 바이너리와 설정 파일을 구분해서 표현하면 도움이 된다.

## Deployment Diagram에서 특히 중요한 두 가지 구분

### 1. 논리 구조와 물리 배치 구조의 구분

Component Diagram은 시스템의 논리적 구성과 의존성을 설명하는 데 강하다.

- 어떤 컴포넌트가 존재하는가
- 어떤 인터페이스를 제공하는가
- 어떤 컴포넌트가 어떤 컴포넌트에 의존하는가

Deployment Diagram은 물리적 또는 실행 환경상의 배치를 설명하는 데 강하다.

- 어떤 Artifact가 어떤 Node에 배포되는가
- 어떤 실행 환경이 어떤 장비 위에 있는가
- 어떤 노드끼리 통신하는가

둘은 대체 관계가 아니라 보완 관계다.

### 2. Specification-level과 Instance-level의 구분

UML-Diagrams는 Deployment Diagram을 크게 두 레벨로 나눠 설명한다. [3]

#### Specification-level

타입 수준의 배포 구조를 보여준다.

예시

- `Application Server`
- `Database Server`
- `Redis Cache`

설계 문서나 표준 아키텍처 설명에 적합하다.

#### Instance-level

실제 인스턴스 수준의 배포 구조를 보여준다.

예시

- `app-prod-01`
- `app-prod-02`
- `db-primary-01`
- `redis-cluster-a`

운영 환경, 스테이징 환경, DR 환경 차이를 설명할 때 유용하다.

입문자가 자주 놓치는 부분인데, "배포 다이어그램"이 꼭 추상적인 구조만 뜻하는 것은 아니다. 실제 서버 이름, 실제 배포 환경, 실제 인스턴스 수를 넣은 운영 다이어그램도 가능하다.

## 다른 다이어그램과 무엇이 다른가

### Component Diagram과의 차이

가장 단순하게 정리하면 다음과 같다.

- Component Diagram: 무엇이 어떻게 구성되는가
- Deployment Diagram: 그것이 어디에 어떻게 배치되는가

실무에서는 보통 다음 식으로 연결된다.

- Component Diagram에서 `Payment Service`, `Order Service` 를 정의
- Deployment Diagram에서 각 서비스의 산출물이 어떤 실행 환경과 노드에 올라가는지 표현

### Sequence Diagram과의 차이

Sequence Diagram은 시간이 흐르면서 메시지가 어떤 순서로 오가는지 보여준다.

Deployment Diagram은 그 메시지를 주고받는 주체가 어떤 실행 환경과 어떤 노드에 배치되어 있는지 보여준다.

즉

- Sequence Diagram: 언제, 어떤 순서로 상호작용하는가
- Deployment Diagram: 어디에서 실행되고, 어떤 경로로 연결되는가

### 일반 인프라 그림과의 차이

실무에서는 많은 그림이 사실상 Deployment Diagram처럼 쓰이지만, UML 관점에서는 아무 인프라 박스 그림이나 Deployment Diagram은 아니다.

Deployment Diagram이라고 부르려면 최소한 아래 질문에는 답해야 한다.

- 어떤 Node가 있는가
- 어떤 Artifact가 어디에 배포되는가
- 어떤 통신 경로가 있는가

서버 박스와 화살표만 있고 배포 단위가 없다면, 그것은 인프라 개요도나 네트워크 개념도에 더 가깝다.

## 현업에서 어떻게 쓰는가

Deployment Diagram은 실무에서 다음 목적에 특히 유용하다.

### 1. 아키텍처 설명

- 웹 서버, 앱 서버, DB, 캐시, 메시지 브로커의 위치 설명
- 외부 연동 시스템과 내부 시스템의 경계 설명
- SaaS, 온프레미스, 하이브리드 환경 구조 설명

### 2. 인프라와 개발 조직의 공통 언어

- 개발자는 서비스 단위로 말하는 경우가 많음
- 인프라 팀은 서버, 네트워크, 런타임 단위로 말하는 경우가 많음

Deployment Diagram은 이 둘을 연결해준다.

### 3. 운영 환경 비교

- 개발 환경
- 스테이징 환경
- 운영 환경
- DR 환경

이 환경들이 어떻게 다른지 한눈에 보여주기 좋다.

### 4. 배포 계획 보조

Visual Paradigm은 배포 계획 체크리스트에서 설치 실패 지점, 롤백, 백업, 데이터 전환, 운영 지원 준비 같은 항목을 함께 검토하라고 제안한다. [6]

다만 이것은 Deployment Diagram 자체가 그런 내용을 모두 표현한다는 뜻은 아니다. 더 정확히는 Deployment Diagram이 그런 운영 문서와 함께 쓰일 때 유용하다는 뜻이다.

### 5. 온보딩과 운영 이해

Lucidchart와 C4 Model 모두 배포 구조 그림이 기술 조직 내외의 이해관계자에게 시스템 실행 위치를 설명하는 데 유용하다고 본다. [7][8]

신규 입사자에게 특히 도움이 되는 질문은 아래 두 가지다.

- 서비스가 논리적으로 어떻게 나뉘는가
- 그 서비스가 실제 어디서 실행되는가

Deployment Diagram은 두 번째 질문에 직접 답한다.

## 특히 유용한 상황

- 웹 서버, 앱 서버, DB 서버가 분리된 서비스
- MSA 또는 분산 시스템
- 쿠버네티스, 컨테이너, VM이 섞인 환경
- 외부 장비나 센서가 붙는 시스템
- 고객사 온프레미스와 SaaS가 섞인 하이브리드 환경
- 운영, 스테이징, DR 환경을 함께 설명해야 하는 경우
- 이중화, 점진 배포, 버전 공존 구조를 설명해야 하는 경우

IBM은 임베디드, 클라이언트/서버, 분산 시스템에서 Deployment Diagram이 효과적이라고 설명한다. [2]

## 굳이 안 그려도 되는 상황

- 로컬 단일 프로세스 수준의 작은 프로그램
- 배포 위치보다 도메인 모델이 더 중요한 초기 개념 설계 단계
- 인프라 구조가 사실상 없는 간단한 스크립트성 작업

다만 작은 시스템이라도 외부 의존성이 많거나, 운영 환경이 자주 바뀌거나, 보안 경계가 중요하면 Deployment Diagram이 다시 유용해질 수 있다.

## 읽는 법

Deployment Diagram을 볼 때는 아래 순서로 읽으면 된다.

1. 어떤 Node가 있는지 본다
2. Node가 Device인지 Execution Environment인지 구분한다
3. 각 Node에 어떤 Artifact가 배포되는지 본다
4. Artifact가 어떤 Component를 구현하는지 필요하면 연결해서 본다
5. Node 사이의 Communication Path를 본다
6. 환경 경계와 외부 연동 지점을 본다
7. 마지막으로 운영 리스크를 해석한다

여기서 중요한 점은, Deployment Diagram만 보고 성능 병목이나 단일 장애 지점을 단정하지는 말아야 한다는 것이다. 이 그림은 그런 리스크를 "발견하기 쉽게 만드는 지도"에 가깝다.

예를 들어 다음은 Deployment Diagram만으로는 확정할 수 없다.

- 실제 복제 수
- 실제 트래픽
- 자동 장애 조치 여부
- 방화벽 규칙의 세부 내용
- 용량 한계와 성능 수치

따라서 Deployment Diagram은 운영 판단의 출발점이지, 모든 운영 사실의 완전한 대체물은 아니다.

## 그릴 때의 실무 팁

### 1. 먼저 목적을 정한다

다이어그램마다 목적이 달라야 한다.

- 아키텍처 설명용
- 운영 환경 설명용
- 보안 경계 설명용
- 배포 절차 보조용

목적이 불명확하면 과도하게 복잡해지기 쉽다.

### 2. Node와 Artifact를 섞어 쓰지 않는다

다음은 서로 다른 개념이다.

- 서버
- 운영체제
- 컨테이너 런타임
- 애플리케이션 바이너리
- 설정 파일

이것들을 모두 같은 레벨의 박스로 그리면 그림이 흐려진다.

### 3. 추상화 수준을 맞춘다

한 그림 안에서 아래 정보가 뒤섞이면 읽기 어려워진다.

- 추상적 역할 이름
- 실제 호스트명
- 프로토콜 세부값
- 운영 절차 설명

설계용 그림은 역할 중심으로, 운영용 그림은 인스턴스 중심으로 나누는 편이 좋다.

### 4. 클라우드 아이콘을 써도 되지만 UML 개념은 유지한다

AWS, Azure, Kubernetes 아이콘을 쓰는 것은 실무에서 흔하다. 다만 아이콘을 쓰더라도 아래 개념은 유지하는 편이 좋다.

- 이것이 Node인지
- Artifact가 무엇인지
- 어떤 경로로 연결되는지

아이콘이 많아져도 UML 의미가 흐려지면 학습과 소통 모두 어려워진다.

### 5. 너무 많은 정보를 한 장에 담지 않는다

보통은 아래 세 가지 중 하나를 우선순위로 정하면 읽기 쉬워진다.

- 실행 위치
- 네트워크 경계
- 운영 환경 차이

## 자주 하는 오해

### 오해 1

"Deployment Diagram은 서버 박스만 그리면 된다"

아니다. 서버만 있으면 인프라 개요도일 수는 있어도 UML Deployment Diagram으로는 부족할 수 있다. 최소한 배포 대상, 배포 산출물, 통신 경로를 구분해서 표현해야 한다.

### 오해 2

"컴포넌트가 서버에 바로 배포된다"

UML 2.x 관점에서는 보통 Artifact가 Node에 배포되고, Artifact가 Component를 구현하거나 포함하는 관계로 이해하는 것이 더 정확하다. [3][5]

### 오해 3

"Deployment Diagram은 운영 문서이므로 설계 단계에서는 필요 없다"

그렇지 않다. 구현 전에 배포 구조를 미리 검토하면 네트워크 경계, 실행 환경, 외부 의존성을 조기에 드러낼 수 있다.

### 오해 4

"이 다이어그램만 보면 병목과 SPOF를 바로 알 수 있다"

정확히는 후보 지점을 찾기 쉬워질 뿐이다. 실제 판단에는 복제 수, 트래픽, 장애 조치, 모니터링 정보가 추가로 필요하다.

## 현대 시스템에서는 무엇을 같이 보면 좋은가

현대 클라우드 환경에서는 UML Deployment Diagram만으로는 부족할 때가 많다.

특히 다음이 중요하면 C4 Model의 Deployment Diagram도 같이 보는 것이 좋다. [8]

- 환경별 배포 구조
- 컨테이너 인스턴스 수
- 로드밸런서, DNS, 방화벽 같은 인프라 노드
- 소프트웨어 시스템과 인프라 노드의 관계

즉

- UML Deployment Diagram은 표준 개념을 배우는 데 적합
- C4 Deployment Diagram은 현대 소프트웨어 시스템을 설명하는 데 실용적

학습 순서로는 UML 개념을 먼저 이해하고, 이후 C4 스타일로 확장하는 방법을 권장한다.

## 결론

Deployment Diagram은 "우리 시스템이 실제 어디에서 실행되고, 무엇이 어디에 배포되며, 어떤 경로로 연결되는가"를 설명하는 그림이다.

정확히 이해하려면 아래 네 가지를 꼭 기억하면 된다.

- Node는 Device와 Execution Environment로 나뉨
- Artifact가 Node에 배포됨
- Artifact는 필요하면 Component를 구현함
- Deployment Diagram은 논리 구조가 아니라 배치 구조와 실행 구조를 설명함

입문자가 이 정도만 확실히 잡아도, 서버 박스 그림과 UML Deployment Diagram의 차이를 분명하게 이해할 수 있다.

## 참고 자료

이 문서를 정리할 때 아래 자료를 참고했다.

1. OMG, *About the Unified Modeling Language Specification Version 2.5.1*  
   https://www.omg.org/spec/UML/2.5.1/About-UML  
   사용 이유: UML 2.5.1이 공식 표준이라는 점 확인

2. IBM, *Deployment diagrams*  
   https://www.ibm.com/docs/en/dmrt/9.5.0?topic=diagrams-deployment  
   사용 이유: 물리 아키텍처, node, device, execution environment, artifact, deployment specification 설명 확인

3. UML-Diagrams.org, *Deployment Diagrams Overview*  
   https://www.uml-diagrams.org/deployment-diagrams-overview.html  
   사용 이유: specification-level / instance-level 구분, UML 1.x와 UML 2.x 차이 확인

4. UML-Diagrams.org, *UML Deployment Diagrams*  
   https://www.uml-diagrams.org/deployment-diagrams.html  
   사용 이유: node, communication path, manifestation, deployment 관계의 UML 해석 확인

5. IBM, *Specifying the deployment of artifacts within nodes*  
   https://www.ibm.com/docs/en/rational-soft-arch/9.7.0?topic=diagrams-specifying-deployment-artifacts-within-nodes  
   사용 이유: artifact를 node에 deploy하는 관계 설명 확인

6. Visual Paradigm, *What is Deployment Diagram?*  
   https://www.visual-paradigm.com/guide/uml-unified-modeling-language/what-is-deployment-diagram/  
   사용 이유: 배포 계획 체크리스트와 실무 질문 정리

7. Lucidchart, *How to Draw a Deployment Diagram in UML*  
   https://www.lucidchart.com/pages/how-to-draw-a-deployment-diagram-in-uml  
   사용 이유: 입문자 관점의 작성 흐름과 실무 공유 맥락 보강

8. C4 Model, *Deployment diagram*  
   https://c4model.com/diagrams/deployment  
   사용 이유: 현대 클라우드 환경에서 UML 배포 다이어그램을 실무적으로 확장해 이해하는 보조 자료
