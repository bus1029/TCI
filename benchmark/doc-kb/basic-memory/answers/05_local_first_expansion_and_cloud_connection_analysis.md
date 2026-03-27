# 5. 로컬 우선 확장과 클라우드 연결 분석

## 개요

Basic Memory의 클라우드 기능은 local-first 철학을 뒤집는 별도 제품이 아니라, 로컬 지식 인프라 위에 얹히는 선택적 확장 계층에 가깝다. 핵심은 "전체 앱을 클라우드 모드로 전환"하는 방식이 아니라, 프로젝트 단위로 라우팅과 동기화를 나눠 갖는 구조다. 이 점 때문에 Basic Memory는 범용 SaaS 노트 앱보다 "로컬 우선 지식 인프라에 클라우드 경로를 덧붙인 시스템"으로 읽힌다.

처음 보는 사람이 이 문서를 읽을 때 먼저 잡아야 할 제품 정의는 아래와 같다.

- Basic Memory는 Markdown 파일을 원본 지식 저장소로 두고, 기본적으로는 로컬에서 동작하지만, 필요할 때 프로젝트 단위로 클라우드 경로와 동기화를 붙일 수 있게 만든 local-first 지식 베이스 제품임

이 문서에서 먼저 알아야 할 전제는 아래와 같다.

- 이 제품의 기본값은 local-first이며 cloud는 opt-in 확장임
- cloud 기능은 앱 전체를 다른 제품으로 바꾸는 것이 아니라, 같은 도구 호출을 유지한 채 transport와 sync 경로를 선택적으로 바꾸는 방식임
- project마다 local mode와 cloud mode를 따로 가질 수 있으며, routing 정책과 로컬 working copy 존재 여부는 별개로 다뤄짐
- backup과 restore도 모두 제품이 자동 책임지는 것이 아니라, cloud 경로와 local 경로에서 책임 경계가 다르게 설계돼 있음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| ProjectMode | 특정 프로젝트가 local로 라우팅될지 cloud로 라우팅될지 결정하는 모드 |
| ProjectEntry | 프로젝트별 경로, mode, workspace, sync 상태를 담는 설정 단위 |
| routing | 같은 도구 호출을 local ASGI로 보낼지 cloud HTTP로 보낼지 결정하는 과정 |
| transport | 실제 요청을 전달하는 통신 경로. local ASGI 또는 remote HTTP가 여기에 해당함 |
| workspace | cloud 쪽에서 프로젝트가 속한 논리적 작업 공간 단위 |
| local_sync_path | cloud 프로젝트의 로컬 작업 복제본 경로 |
| snapshot | cloud 경로의 특정 시점 상태를 저장하고 나중에 복구하기 위한 백업 단위 |

예를 들어 사용자가 두 개의 프로젝트를 갖고 있고, 하나는 개인 노트로 로컬에만 두고, 다른 하나는 팀 협업용으로 cloud mode에 두는 경우 대략 아래처럼 동작한다.

1. MCP tool이나 CLI는 같은 명령 형태를 유지함
2. client 계층이 프로젝트 설정을 보고 local ASGI 또는 cloud HTTP transport를 선택함
3. cloud mode 프로젝트라도 `local_sync_path`가 있으면 로컬 working copy와 bisync를 함께 운영할 수 있음
4. cloud 경로의 백업은 snapshot과 restore로 다루고, 로컬 경로의 파일과 SQLite/config 백업은 운영자 책임으로 남음

즉 이 문서의 주제는 "클라우드를 붙였는가" 자체보다 "local-first 구조를 깨지 않고 cloud 경로를 어떻게 선택적으로 얹는가"에 가깝다.

이번 섹션에서 벤치마킹할 지점은 네 가지다.

- 왜 local-first 제품이면서 프로젝트별 local/cloud routing을 공존시키는가
- 어떻게 동일한 도구 호출을 유지한 채 transport만 local/cloud로 바꾸는가
- 폐쇄망 또는 온프레미스 운영을 하려면 어떤 구성과 제약을 이해해야 하는가
- snapshot, backup, restore에서 제품 책임과 운영자 책임을 어디서 나누는가

# 시스템 핵심 동작 방식 및 사용 기술

## 1. local-first 제품이면서도 프로젝트별 local/cloud routing을 공존시키는 이유

### 채택 기술 구조

- 기본 철학
  - Basic Memory는 전역 `cloud_mode`로 앱 전체를 전환하는 구조를 버리고, 프로젝트별 `ProjectMode`를 중심으로 라우팅을 결정함
  - `docs/SPEC-PER-PROJECT-ROUTING.md`는 이를 명시적으로 "project-aware routing" 계약으로 정의함
  - README도 cloud가 optional이며 local-first workflow는 계속 유지된다고 설명함
- 설정 단위
  - `BasicMemoryConfig`는 프로젝트마다 `ProjectEntry`를 두고, 각 entry에 `path`, `mode`, `workspace_id`, `local_sync_path`, `bisync_initialized`, `last_sync`를 저장함
  - `project.mode`가 프로젝트 단위 라우팅의 유일한 config signal임
  - `cloud_api_key`는 계정 단위 인증 정보이고, 실제 라우팅 대상은 프로젝트별 mode가 결정함
- 라우팅 계약
  - 우선순위는 factory injection -> explicit override -> project mode -> default local 순서임
  - `bm cloud login/logout/status`는 인증 상태만 바꾸고 라우팅 기본값은 바꾸지 않음
  - `bm project set-cloud`는 특정 프로젝트만 cloud mode로 바꾸고, `bm project set-local`은 다시 local로 되돌림
- 왜 이렇게 나누는가
  - 모든 프로젝트를 한 번에 SaaS로 옮기지 않고, 필요한 프로젝트만 단계적으로 클라우드에 붙일 수 있게 함
  - 개인 비공개 노트는 로컬에 두고, 협업이나 다기기 접근이 필요한 프로젝트만 클라우드로 보낼 수 있게 함
  - local-first 기본값을 깨지 않으면서도 상업적 클라우드 기능을 얹을 수 있게 함
- sync 계층과의 연결
  - cloud-only 프로젝트는 로컬 watcher와 background sync에서 자동 제외됨
  - 다만 cloud 프로젝트라도 `local_sync_path`가 있는 bisync 복제본이면 로컬 watch 대상에 남음
  - 즉 라우팅 mode와 로컬 파일 존재 여부를 분리해, "cloud route + local working copy" 조합을 허용함

### 코드 근거 예시

- `docs/SPEC-PER-PROJECT-ROUTING.md`
  - global cloud toggle을 없애고 project-aware routing을 계약으로 명시함
  - 명시적 flag와 project mode의 우선순위를 정의함
- `README.md`
  - cloud는 optional이며 local-first workflow가 계속 유지된다고 설명함
  - per-project cloud routing을 주요 기능으로 소개함
- `src/basic_memory/config.py`
  - `ProjectMode`, `ProjectEntry`, `cloud_api_key`, `default_workspace`를 정의함
  - `get_project_mode()`가 프로젝트별 routing mode를 반환함
- `src/basic_memory/cli/commands/project.py`
  - `set-cloud`, `set-local` 명령으로 프로젝트별 mode 전환을 제공함
- `src/basic_memory/services/initialization.py`
  - cloud-only 프로젝트를 로컬 sync 대상에서 제외함
- `src/basic_memory/sync/watch_service.py`
  - cloud-mode 프로젝트 중 local bisync copy가 없는 항목은 watch cycle에서 건너뜀

### 제품 적용 포인트

- local-first 제품에 SaaS 기능을 붙일 때는 전역 모드 전환보다 프로젝트별 routing이 현실적임
- 인증 정보와 라우팅 대상은 분리해야 함
- 프로젝트별 mode와 local working copy 유무를 분리하면 "클라우드 경유 + 로컬 작업 디렉터리" 조합을 만들 수 있음
- sync 계층도 routing 계층과 같은 기준을 써야 운영 정책이 일관됨

### 해석과 시사점

- Basic Memory의 확장 전략은 "클라우드 전환"보다 "클라우드 선택"에 가깝다
- 이 구조 덕분에 로컬 우선 철학을 유지하면서도 유료 클라우드 기능을 점진적으로 도입할 수 있다
- 반대로 mode, workspace, local_sync_path를 함께 이해해야 하므로 설정 모델은 다소 복잡해진다

## 2. 동일한 도구 호출을 유지한 채 routing만 바꾸는 클라이언트 추상화

### 채택 기술 구조

- 핵심 원칙
  - MCP tool이나 CLI 명령은 "무엇을 할지"만 알고, "어느 transport로 갈지"는 client layer가 결정함
  - 이 덕분에 동일한 tool call을 유지한 채 local ASGI와 cloud HTTP proxy를 교체할 수 있음
- transport 추상화
  - `get_client()`는 local이면 in-process `ASGITransport`, cloud면 `cloud_host/proxy` 기반 `AsyncClient`를 만듦
  - cloud route에서는 Bearer token으로 `cloud_api_key` 또는 OAuth 토큰을 사용함
  - workspace가 지정되면 `X-Workspace-ID` 헤더까지 함께 붙임
- project-aware bootstrap
  - `get_project_client()`는 먼저 config에서 프로젝트 이름과 mode를 읽고, 그 정보로 올바른 client를 만든 다음 API에서 프로젝트를 검증함
  - 즉 "어떤 project인지 알아야 routing을 고를 수 있고, routing이 맞아야 project를 검증할 수 있다"는 bootstrap 문제를 별도 helper로 흡수함
- 명시적 override
  - `--local`, `--cloud` flag는 `BASIC_MEMORY_FORCE_LOCAL`, `BASIC_MEMORY_FORCE_CLOUD`, `BASIC_MEMORY_EXPLICIT_ROUTING` 환경 변수로 전달됨
  - explicit routing이 있으면 project mode보다 flag가 우선함
- workspace resolution
  - cloud routing 시 workspace는 explicit argument -> per-project workspace_id -> global default_workspace -> context cache -> auto-select 순서로 결정됨
  - local project에 workspace를 주면 fail fast로 막음
- 결과적 효과
  - tool 코드는 `get_project_client()`만 쓰면 됨
  - typed client와 API path는 그대로 유지됨
  - local/cloud 차이는 transport와 auth에서만 흡수됨

### 코드 근거 예시

- `src/basic_memory/mcp/async_client.py`
  - `get_client()`가 explicit routing, project mode, default local 순으로 transport를 선택함
  - local은 `ASGITransport`, cloud는 `cloud_host/proxy` HTTP client를 사용함
- `src/basic_memory/mcp/project_context.py`
  - `get_project_client()`가 프로젝트 해석, workspace resolution, client creation, project validation을 한 번에 처리함
  - explicit `--local/--cloud`와 project mode 우선순위를 코드로 구현함
- `docs/SPEC-PER-PROJECT-ROUTING.md`
  - routing contract와 env var override를 문서화함
- `src/basic_memory/cli/commands/project.py`
  - `--local`, `--cloud`, `--workspace` 플래그 기반의 명시적 타깃 선택을 지원함
- `src/basic_memory/cli/commands/cloud/core_commands.py`
  - login/logout은 인증만 관리하고 routing 기본값은 건드리지 않는다고 명시함

### 제품 적용 포인트

- transport 차이를 tool 내부 분기로 넣지 말고 client factory나 context helper에서 흡수하는 편이 좋음
- local/cloud 전환은 API contract를 바꾸지 말고 auth와 base URL만 바꾸는 구조가 재사용성이 높음
- workspace, tenant, project를 함께 써야 한다면 bootstrap 문제를 별도 helper로 분리해야 함
- 명시적 route flag는 디버깅과 운영 지원에서 매우 유용함

### 해석과 시사점

- Basic Memory의 강점은 cloud 기능 자체보다 "도구 호출 계약을 유지한 채 실행 경로만 바꾸는 방식"에 있다
- 이 구조 덕분에 MCP, CLI, cloud app이 같은 도메인 계층을 공유하면서도 배포 토폴로지가 달라도 동작시킬 수 있다
- 반대로 client/context 계층을 이해하지 못하면 local/cloud 문제를 디버깅하기가 쉽지 않다

## 3. 폐쇄망 또는 온프레미스 환경에서 외부 전송 없이 운영하려면 무엇을 이해해야 하는가

### 채택 기술 구조

- 가능한 기본 구성
  - Basic Memory의 기본 저장 구조는 로컬 파일 + 로컬 SQLite DB임
  - README는 cloud가 optional이라고 명시함
  - cloud routing을 켜지 않으면 기본 transport는 local ASGI임
- 검색과 임베딩
  - semantic search 기본 provider는 `fastembed`이며, 이는 로컬 ONNX 기반 임베딩 provider임
  - 따라서 OpenAI embedding provider를 쓰지 않으면 의미 검색도 로컬에서 처리 가능함
- 강제 로컬 운영
  - `BASIC_MEMORY_FORCE_LOCAL=true`를 쓰면 명시적으로 local transport를 강제할 수 있음
  - 프로젝트를 모두 `local` mode로 두면 MCP와 CLI도 로컬 경로만 사용함
  - cloud API key, OAuth 토큰, `set-cloud`, `bisync`, `sync-setup`을 사용하지 않으면 클라우드 경로가 열리지 않음
- 배포 형태
  - `docs/Docker.md`는 `/app/data`에 지식 디렉터리, `/app/.basic-memory`에 config와 SQLite DB를 volume mount하는 Docker 운영 방식을 설명함
  - 즉 온프레미스 환경에서는 파일 디렉터리와 app state 디렉터리를 로컬 볼륨으로 유지하는 방식이 기본임
- 제약 사항
  - cloud snapshot, restore, rclone bisync는 모두 외부 cloud endpoint를 전제로 함
  - project를 cloud mode로 두면 HTTP proxy와 인증 토큰이 필요함
  - OpenAI embedding provider를 선택하면 외부 API 전송이 발생함
  - Postgres tenant config는 cloud deployment용이므로, 단순 로컬 독립 운영과는 성격이 다름

### 코드 근거 예시

- `README.md`
  - cloud는 optional이며 local-first workflow가 유지된다고 설명함
- `src/basic_memory/config.py`
  - 기본 database backend는 SQLite
  - 기본 embedding provider는 `fastembed`
  - `cloud_api_key`와 `ProjectMode`가 별도 필드로 존재함
- `src/basic_memory/repository/fastembed_provider.py`
  - FastEmbed를 local ONNX embedding provider로 정의함
- `src/basic_memory/mcp/async_client.py`
  - 기본 fallback transport가 local ASGI임
  - `BASIC_MEMORY_FORCE_LOCAL`을 지원함
- `docs/Docker.md`
  - 로컬 volume mount 기반 배포와 persistent config/DB 보관 방식을 설명함

### 제품 적용 포인트

- 오프라인 제품을 만들려면 저장, 검색, 임베딩까지 모두 로컬 경로가 있어야 함
- cloud optional을 말하려면 "기본 route가 local"이고 "cloud route는 opt-in"이어야 함
- 온프레미스 배포에서는 파일 디렉터리와 앱 상태 디렉터리를 분리해 persistent volume으로 관리하는 편이 안정적임
- 외부 전송이 발생하는 기능을 명확히 구분해 사용자에게 알려야 함

### 해석과 시사점

- Basic Memory는 로컬 단독 운영이 가능한 구조를 기본으로 두고, 클라우드는 선택적 증분 기능으로 얹는다
- 이 덕분에 폐쇄망, 민감 정보, 개인 지식 베이스 같은 시나리오에 잘 맞는다
- 다만 semantic provider 선택이나 project mode 설정 하나만 잘못해도 외부 경로가 열릴 수 있으므로 운영 가이드는 명확해야 한다

## 4. snapshot, backup, restore에서 제품 책임과 운영자 책임을 나누는 방식

### 채택 기술 구조

- 제품이 직접 책임지는 범위
  - cloud snapshot lifecycle은 제품이 CLI 명령으로 직접 제공함
  - `bm cloud snapshot create/list/show/browse/delete`로 스냅샷 관리 가능함
  - `bm cloud restore <path> --snapshot <id>`로 특정 파일이나 폴더를 이전 스냅샷에서 현재 bucket으로 복구 가능함
  - restore 전에는 browse를 통해 어떤 파일이 영향을 받는지 보여 주고, 기본적으로 사용자 확인을 받음
- sync 안정화 책임
  - cloud sync 경로에서는 `bisync_initialized`, `last_sync`, per-project bisync state를 제품이 관리함
  - `bm cloud bisync-reset`으로 손상된 bisync metadata를 지우고 baseline을 다시 만들 수 있게 함
  - `.bmignore`를 rclone filter로 변환해 sync 대상 제어도 제품이 지원함
- 운영자가 맡는 범위
  - 로컬 프로젝트 자체에 대한 snapshot/backup 시스템은 현재 제품 내에 없음
  - local-first 운영에서는 Markdown 파일 디렉터리와 `~/.basic-memory` 아래 config/SQLite DB를 운영자가 백업해야 함
  - Docker 운영 시에도 volume persistence와 백업은 운영자 책임임
  - one-way sync인지 bisync인지, `--resync`를 언제 쓸지, 로컬을 source of truth로 볼지 같은 정책도 운영자가 결정해야 함
- 책임 경계의 의미
  - cloud 쪽은 서비스가 snapshot과 restore를 제공함
  - local 쪽은 파일 소유권을 사용자에게 남겨 두는 대신, 제품은 sync/check/reset 같은 운영 보조 도구만 제공함
  - 즉 제품은 "로컬 파일을 대신 보관"하지 않고, "로컬 파일을 잘 다루도록 돕는 도구" 역할에 머묾

### 코드 근거 예시

- `src/basic_memory/cli/commands/cloud/snapshot.py`
  - snapshot create/list/show/browse/delete 명령을 제공함
- `src/basic_memory/cli/commands/cloud/restore.py`
  - snapshot 기반 file/folder restore를 제공함
  - overwrite 경고와 사전 확인 절차를 포함함
- `src/basic_memory/cli/commands/cloud/project_sync.py`
  - bisync 성공 후 `last_sync`, `bisync_initialized`를 config에 기록함
  - `bisync-reset`과 `sync-setup`을 제공함
- `src/basic_memory/cli/commands/cloud/rclone_commands.py`
  - 프로젝트별 bisync state 디렉터리와 rclone 기반 sync/check/bisync를 구현함
- `docs/cloud-cli.md`
  - per-project bisync state, `.bmignore`, delete safety limit, restore 전제와 운영 흐름을 설명함
- `docs/Docker.md`
  - config와 SQLite DB를 persistent volume으로 보관하는 운영 방식을 설명함

### 제품 적용 포인트

- local-first 제품은 "백업을 전부 제품이 책임질 것인가"보다 "어디까지 제품이 자동화하고 어디부터 운영자가 관리하는가"를 명확히 나눠야 함
- cloud backup 기능이 있다면 snapshot browse, preview, confirmation, selective restore까지 한 세트로 제공하는 편이 좋음
- 로컬 경로에서는 snapshot 자체보다 sync check, state reset, ignore filter 같은 운영 보조 장치가 더 현실적일 수 있음
- 파일 저장소와 인덱스 저장소가 분리돼 있으면 둘 다 복구 대상이라는 점을 문서에 명확히 써야 함

### 해석과 시사점

- Basic Memory는 cloud backup/restore는 제품 기능으로 제공하지만, local backup은 사용자 소유권 영역으로 남겨 둔다
- 이 경계는 local-first 철학과 잘 맞는다
- 반대로 사용자가 "local도 제품이 자동 백업해 주겠지"라고 기대하면 실제 책임 범위와 어긋날 수 있으므로 문서와 UX에서 더 명확히 안내할 필요가 있다

## 5. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 프로젝트별 routing은 강력하지만, mode, workspace, local_sync_path를 모두 이해해야 해서 개념 부하가 있다
- 일부 문서 예시는 현재 통합 `ProjectEntry` 구조보다 예전 config shape를 보여 주는 구간이 있어, 코드 기준 해석이 더 중요하다
- local-only 운영은 강하지만, cloud sync와 snapshot 복구는 외부 서비스 가용성과 인증 상태에 의존한다
- snapshot과 restore는 cloud path 기준으로 제공되며, local 프로젝트 전용 시점 복구 기능은 현재 제품 안에 없다
- 온프레미스 운영이 가능해도 Docker volume, SQLite/config persistence, embedding provider 선택 같은 운영 세부를 직접 챙겨야 한다

### 제품 해석

- Basic Memory의 클라우드 전략은 "앱 전체를 SaaS화"하는 방식보다 "로컬 지식 인프라에 프로젝트 단위 cloud path를 추가"하는 방식에 가깝다
- 이 제품의 강점은 local-first를 포기하지 않고도 인증, sync, snapshot 같은 상업 기능을 붙였다는 점에 있다
- 따라서 벤치마킹 초점도 클라우드 기능 수보다 `프로젝트별 routing`, `transport 추상화`, `오프라인 기본값`, `백업 책임 경계`에 두는 편이 맞다

# 적용 인사이트

우리 제품이 Basic Memory에서 가장 먼저 벤치마킹해야 할 것은 local-first와 cloud를 양자택일로 보지 않고, 프로젝트 단위로 조합 가능한 운영 모델로 설계하는 관점이다. 구체적으로는 `per-project routing`, `same API different transport`, `local-only 기본 경로`, `cloud snapshot과 local backup의 책임 분리`를 한 세트로 가져가는 것이 핵심이다.

- cloud 기능을 붙이더라도 기본 라우팅과 기본 저장은 local에 두는 편이 local-first 정체성을 지키기 쉽다
- tool contract를 유지한 채 transport만 교체하면 local, cloud, on-prem 배포를 같은 제품 구조 안에서 흡수할 수 있다
- 폐쇄망 운영을 지원하려면 로컬 저장, 로컬 검색, 로컬 임베딩, 로컬 배포 경로가 모두 준비돼 있어야 한다
- snapshot과 restore는 cloud 쪽에서 제품 기능으로 제공하고, local 쪽은 파일/DB 백업 책임을 운영자에게 두는 식의 경계가 실무적으로 명확하다
- 이 제품의 차별점은 클라우드 기능의 화려함보다 "로컬 소유권을 유지한 채 선택적으로 클라우드 경로를 여는 방식"에 있다
