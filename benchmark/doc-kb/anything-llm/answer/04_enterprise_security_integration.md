# 엔터프라이즈 보안 및 사내 융합 확장성

## 개요

AnythingLLM의 엔터프라이즈 보안 축은 현재 구현 기준으로 보면 `문서 단위 ACL`보다 `워크스페이스 단위 격리`, `전역 역할 기반 권한`, `임베드 공개 경로에 대한 서버 측 방어선`, `간단한 SSO 토큰 패스스루`에 더 가깝다. 즉 세밀한 문서별 권한 모델을 깊게 구현했다기보다 업무 공간을 먼저 분리하고 그 위에 관리자 기능과 외부 삽입 채널을 얹는 방식이다.

따라서 이 제품을 벤치마킹할 때는 "모든 리소스를 문서 단위로 직접 보호한다"는 관점보다 "워크스페이스를 보안 경계로 삼고 외부 진입점은 별도 설정과 미들웨어로 좁힌다"는 설계 선택으로 읽는 편이 정확하다.

처음 보는 사람이 이 문서에서 먼저 이해해야 할 전제는 아래와 같다.

- AnythingLLM의 핵심 보안 경계는 문서 단위 ACL보다 워크스페이스 단위 격리에 가까움
- 권한 모델은 전역 사용자 역할과 워크스페이스 멤버십 조합으로 구성됨
- 외부 노출 위험이 큰 임베드 경로는 일반 앱 인증과 분리된 별도 설정 엔터티와 미들웨어로 통제함
- `Simple SSO`는 완성형 OIDC 또는 SAML 계층이 아니라 기존 포털과 빠르게 붙기 위한 토큰 교환 브리지에 가까움
- 따라서 이 문서는 "엔터프라이즈 보안을 얼마나 세밀하게 완성했는가"보다 "어떤 경계를 먼저 세우고 무엇을 후순위로 미뤘는가"를 읽는 문서로 보는 편이 맞음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| workspace 격리 | 채팅, 문서, 설정, 이력을 워크스페이스 단위로 나눠 접근 제어하는 구조 |
| 전역 역할 | `admin`, `manager`, `default` 같은 사용자 전체 역할 |
| `workspace_users` | 사용자와 워크스페이스 소속 관계를 저장하는 조인 테이블 |
| 임베드 설정 | 외부 페이지에 붙는 챗봇의 공개 설정과 제한 조건을 담는 `embed_configs` 엔터티 |
| `canRespond` | 임베드 요청에 대해 origin, 세션, quota, chat mode 등을 검사하는 미들웨어 |
| Simple SSO | 외부 포털이 발급한 임시 토큰을 AnythingLLM 세션 JWT로 바꾸는 로그인 브리지 |
| 일회성 임시 토큰 | 짧은 만료 시간을 가진 `TemporaryAuthToken` 기반 로그인 토큰 |

처음 읽을 때는 아래 흐름으로 이해하면 된다.

1. 사용자는 전역 역할을 가지고 있으며 멀티유저 모드에서는 워크스페이스 멤버십도 함께 검사됨
2. 워크스페이스 접근 시 서버가 슬러그와 사용자 소속 관계를 검증함
3. 임베드 챗봇은 별도 `embed_config`를 통해 공개 UUID, 허용 origin, override 허용 범위를 가짐
4. 임베드 런타임 요청은 서버 미들웨어가 origin, 세션, quota를 확인한 뒤에만 처리함
5. 사내 포털 연동이 필요하면 `Simple SSO`가 임시 토큰을 세션 JWT로 교환함

예를 들어 사내 포털이 직원용 챗봇 링크를 제공하는 경우 흐름은 아래처럼 볼 수 있다.

```text
사내 포털에서 사용자 식별 완료
-> 임시 로그인 토큰 발급
-> /sso/simple?token=...
-> 세션 JWT 교환
-> 워크스페이스 멤버십 검증
-> 허용된 워크스페이스 또는 임베드 경로만 접근
```

즉 이 문서의 핵심 질문은 "세밀한 엔터프라이즈 권한 모델을 모두 갖췄는가"보다 "워크스페이스, 임베드, SSO 브리지라는 현실적인 경계들을 어떻게 조합했는가"다.

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 워크스페이스 단위 격리와 역할 기반 접근 제어

### 채택 기술 구조

- 사용자 전역 역할은 `users.role`에 저장되며 값은 `admin`, `manager`, `default`로 단순화돼 있음
- 사용자와 워크스페이스 연결은 `workspace_users` 조인 테이블로 관리됨
- 멀티유저 모드에서는 워크스페이스 진입 시 `validWorkspaceSlug`가 `Workspace.getWithUser()`를 호출해 소속 여부를 함께 검증함
- 일반 사용자는 자신이 연결된 워크스페이스만 조회할 수 있고 `admin`, `manager`는 이 멤버십 필터를 우회함
- 라우트 단 역할 검사는 `strictMultiUserRoleValid`, `flexUserRoleValid`로 나뉘며 멀티유저 전용 경로와 단일 사용자 겸용 경로를 다르게 다룸
- 현재 코드 기준 핵심 보안 경계는 문서별 ACL이 아니라 워크스페이스 단위 분리임

### 코드 근거 예시

- `server/prisma/schema.prisma`
  - `users.role`, `workspace_users`, `workspaces`가 기본 권한 모델과 격리 경계를 정의함
- `server/utils/middleware/multiUserProtected.js`
  - 역할 기반 접근 제어 미들웨어를 제공함
- `server/utils/middleware/validWorkspace.js`
  - 워크스페이스 슬러그 진입 시 사용자-워크스페이스 관계를 검증함
- `server/models/workspace.js`
  - `Workspace.getWithUser()`, `Workspace.whereWithUser()`가 실제 멤버십 필터를 구현함
- `server/models/workspaceUsers.js`
  - 워크스페이스 사용자 관계 생성과 삭제를 담당함

### 제품 적용 포인트

- 문서별 권한부터 시작하지 말고 사용자와 업무 공간 사이의 조인 구조를 먼저 고정하는 편이 구현 복잡도를 낮춤
- 채팅, 업로드, 설정 수정처럼 대부분의 민감 경로는 같은 `workspace access check`를 재사용하도록 미들웨어로 올리는 편이 안전함
- 역할은 우선 전역 역할로 단순하게 두고 정말 필요할 때만 워크스페이스별 역할로 확장하는 것이 운영에 유리함

### 해석과 시사점

- AnythingLLM은 보안 모델을 비교적 단순하게 유지하면서도 멀티유저 환경에서 데이터 섞임을 막기 위한 최소한의 격리 구조를 갖추고 있음
- 워크스페이스를 단위로 접근 제어를 묶으면 채팅 이력, 설정, 문서 연결, 임베드 대상을 한 경계 안에서 다룰 수 있어 일관성이 높음
- 반대로 이 구조는 질문 문서에서 기대한 문서 단위 보안과는 다름
- 특정 부서 안에서도 문서마다 권한이 갈라져야 하는 조직이라면 AnythingLLM의 현재 구현을 그대로 복제하기보다 워크스페이스 격리 위에 문서별 ACL 레이어를 추가하는 방향으로 해석해야 함

## 2. 임베드 위젯의 공개 진입점과 서버 측 방어선

### 채택 기술 구조

- 임베드 기능은 별도 설정 엔터티인 `embed_configs`를 중심으로 동작함
- 관리자는 임베드 설정을 생성하고 워크스페이스와 연결한 뒤 공개용 `uuid`를 가진 임베드 엔드포인트를 외부 페이지에서 사용함
- 임베드 런타임 진입점은 `/embed/:embedId/stream-chat`이며 `validEmbedConfig`, `setConnectionMeta`, `canRespond` 미들웨어를 거침
- `canRespond`는 임베드 활성화 여부, 허용 origin, UUID 형식의 `sessionId`, 유효한 `chat_mode`, 일일 채팅 수, 세션별 채팅 수를 검사함
- 임베드 설정은 `allow_model_override`, `allow_temperature_override`, `allow_prompt_override`로 오버라이드 허용 범위를 제한함
- `message_limit`는 과금 한도라기보다 임베드 대화에서 과거 몇 개의 메시지를 문맥으로 재주입할지 정하는 히스토리 윈도우 역할을 함
- 위젯 자체는 별도 프런트엔드 번들로 관리되며 실제 배포 산출물은 `frontend/public/embed` 아래의 정적 파일로 제공됨
- 관리용 REST와 개발자용 API surface는 분리돼 있으며 `/v1/embed/*` 계열은 `validApiKey`로 보호됨

### 코드 근거 예시

- `server/prisma/schema.prisma`
  - `embed_configs`, `embed_chats`가 임베드 설정과 대화 저장 구조를 정의함
- `server/models/embedConfig.js`
  - 허용 필드 검증과 `allowlist_domains` 파싱을 담당함
- `server/utils/middleware/embedMiddleware.js`
  - origin allowlist, 세션 검증, quota 검사를 수행함
- `server/endpoints/embed/index.js`
  - 공개 임베드 채팅 스트림과 세션별 히스토리 조회, 리셋 경로를 제공함
- `server/utils/chats/embed.js`
  - 워크스페이스 문맥 재사용, override 적용, `message_limit` 기반 히스토리 절단을 처리함
- `server/endpoints/embedManagement.js`
  - 관리자 UI용 임베드 생성, 수정, 삭제를 제공함
- `server/endpoints/api/embed/index.js`
- `server/utils/middleware/validApiKey.js`
  - API Key 기반 개발자 API를 구성함
- `frontend/public/embed/anythingllm-chat-widget.min.js`
  - 배포용 위젯 번들이고 `embed/`가 위젯 소스 앱임

### 제품 적용 포인트

- 사내 포털 삽입형 챗봇은 일반 앱 인증 흐름과 분리된 별도 설정 엔터티로 관리하는 편이 운영에 유리함
- 외부 삽입 채널은 스크립트 배포보다 공개 런타임 엔드포인트, 서버 측 origin 검증, 세션 단위 quota 조합으로 설계하는 편이 재사용성이 높음
- 프롬프트, 모델, temperature 같은 고위험 옵션은 요청마다 자유롭게 받지 말고 설정 플래그로 명시적 허용 여부를 두는 편이 안전함

### 해석과 시사점

- AnythingLLM의 임베드 구조는 헤드리스 위젯을 여러 내부 시스템에 붙일 수 있게 하되 공개 진입점은 별도 가드레일로 좁힌다는 방향으로 읽을 수 있음
- 워크스페이스 문맥을 그대로 재사용하면서도 외부 페이지 전용 quota와 allowlist를 별도로 갖는 점이 실무적으로 유용함
- 다만 이 구조는 전통적인 의미의 CORS 기반 보호와는 결이 조금 다름
- 실제 스트리밍 응답은 `Access-Control-Allow-Origin: *`를 설정하고 있고 보안 판단의 핵심은 브라우저 CORS 자체보다 `canRespond` 내부의 origin allowlist와 설정 검증에 실려 있음
- 즉 보안 통신은 헤더 한 줄보다 애플리케이션 레벨 검증에 더 의존함

## 3. Simple SSO 기반 사내 인증 연동

### 채택 기술 구조

- 현재 구현은 범용 OIDC, SAML 통합 프레임워크라기보다 `Simple SSO`라는 토큰 패스스루 방식에 가깝다
- `SIMPLE_SSO_ENABLED`가 켜진 멀티유저 환경에서만 임시 인증 토큰 발급과 검증이 가능함
- 관리 API는 `/v1/users/:id/issue-auth-token` 경로에서 단일 사용자를 위한 일회성 임시 토큰을 발급함
- 사용자는 `/sso/simple?token=...` 형태의 프런트 경로로 유입되고 프런트는 서버의 `/request-token/sso/simple`을 호출해 실제 세션 JWT를 교환함
- `SIMPLE_SSO_NO_LOGIN`이 함께 설정되면 자격 증명 로그인 경로를 막아 사내 포털에서만 진입시키는 구성이 가능함
- `SIMPLE_SSO_NO_LOGIN_REDIRECT`가 유효하면 로그인 차단 시 별도 리다이렉트 URL을 제공할 수 있음

### 코드 근거 예시

- `server/utils/middleware/simpleSSOEnabled.js`
  - Simple SSO 활성화 여부, 멀티유저 모드 전제, 로그인 비활성화 미들웨어를 담당함
- `server/models/temporaryAuthToken.js`
  - 임시 토큰 발급, 만료 검증, 일회성 소모 후 삭제를 구현함
- `server/endpoints/api/userManagement/index.js`
  - `/v1/users/:id/issue-auth-token` 발급 API를 제공함
- `server/endpoints/system.js`
  - `/request-token/sso/simple` 교환 엔드포인트를 제공함
- `server/models/systemSettings.js`
  - `SIMPLE_SSO_NO_LOGIN_REDIRECT`를 해석함
- `frontend/src/pages/Login/SSO/simple.jsx`
  - 토큰을 세션 JWT로 교환한 뒤 로컬 인증 상태를 저장함

### 제품 적용 포인트

- 기존 포털이 이미 사용자 식별을 끝낸 상태라면 복잡한 IdP 통합 전에 일회성 로그인 토큰 전달 패턴만으로도 초기 연동을 빠르게 열 수 있음
- 다만 이 패턴은 발급 API 보호가 중요하므로 별도 API Key 또는 관리자 전용 경로와 함께 묶어야 함
- 로그인 UI를 아예 차단하는 옵션은 공공망이나 폐쇄망처럼 진입 경로를 강제해야 하는 환경에서 유용함

### 해석과 시사점

- AnythingLLM의 SSO 구현은 대기업 표준 연합 인증을 내장했다기보다 기존 사내 포털과 빠르게 접합하기 위한 얇은 브리지에 가까움
- 외부 시스템이 사용자를 식별하고 AnythingLLM은 짧은 수명의 임시 토큰을 세션으로 교환하는 역할만 수행함
- 이 방식은 구현 비용이 낮고 폐쇄망 포털 통합에 적합함
- 반면 정교한 IdP 정책 연동이나 표준 프로토콜 호환성을 바로 제공하지는 않음
- 따라서 벤치마킹할 때는 완성형 SSO 제품보다 포털 중심 로그인 위임 패턴으로 해석하는 편이 적절함

## 4. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 질문 문서의 기대와 달리 현재 보안 경계는 문서 단위가 아니라 워크스페이스 단위임
- 역할은 전역 사용자 역할이며 워크스페이스별 세부 역할 모델은 아님
- `admin`, `manager`는 워크스페이스 멤버십 필터를 우회하므로 운영 정책이 역할 설계에 크게 의존함
- 임베드 스트리밍 경로는 origin allowlist와 quota를 검사하지만 히스토리 조회와 리셋 경로는 `validEmbedConfig`만 거치므로 방어선이 완전히 같지는 않음
- 임베드 응답은 `Access-Control-Allow-Origin: *`를 반환하므로 보안 판단을 브라우저 CORS 헤더 하나에 기대면 안 됨
- `TemporaryAuthToken.expiry`는 구현상 `1000 * 60 * 6`으로 6분인데 주석은 1시간이라고 적혀 있어 코드와 설명이 어긋나 있음
- Simple SSO는 강한 표준 연합 인증 계층이 아니라 환경변수 기반 토큰 패스스루이므로 대규모 엔터프라이즈 정책을 그대로 대체하지는 못함

### 제품 해석

- 우리 제품에 이 패턴을 도입한다면 1차 목표는 문서별 권한 완성보다 `workspace silo + 공통 접근 미들웨어 + 외부 임베드 전용 설정`을 먼저 안정화하는 것이 맞음
- 이 수준만 갖춰도 내부 데이터 혼선과 외부 삽입 경로 오남용을 상당 부분 줄일 수 있음
- 그다음 단계에서만 문서별 ACL, 워크스페이스별 역할, 표준 OIDC 또는 SAML, 서명 기반 임베드 토큰 같은 엔터프라이즈 기능을 얹는 편이 설계와 운영 양쪽에서 더 현실적임

## 적용 인사이트

- 보안 경계는 문서가 아니라 업무 공간 단위로 먼저 세우고 대부분의 기능이 그 경계를 재사용하게 만드는 편이 구현 효율이 높음
- 임베드 기능은 일반 웹앱 인증과 섞지 말고 별도 설정 모델과 전용 미들웨어로 분리하는 편이 안전함
- 외부 포털 연동은 처음부터 무거운 표준 SSO로 가지 않아도 되며 짧은 수명의 일회성 로그인 토큰 브리지로 초기 통합 속도를 높일 수 있음
- 다만 세밀한 문서 권한, 표준 연합 인증, 위젯별 강한 서명 검증이 필요한 조직이라면 AnythingLLM의 현재 구조를 출발점으로 보고 추가 계층을 설계해야 함
