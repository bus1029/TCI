# 2. Local-first 저장 구조와 동기화 분석

## 개요

Basic Memory의 local-first 설계는 "파일을 쓰기 편하게 보관한다" 수준이 아니라, 파일 시스템을 원본 저장소로 유지하면서도 검색과 그래프 기능을 잃지 않게 만드는 운영 구조에 가깝다. 핵심은 Markdown 파일과 데이터베이스를 경쟁 관계로 두지 않고, 파일은 source of truth, DB는 재구축 가능한 인덱스로 분리한 점이다.

처음 보는 사람이 이 문서를 읽을 때 먼저 잡아야 할 제품 정의는 아래와 같다.

- Basic Memory는 Markdown 파일을 원본 지식 저장소로 두고, 그 내용을 데이터베이스 기반 검색 인덱스와 지식 그래프로 동기화한 뒤, AI와 사람이 함께 읽고 쓰게 만드는 local-first 지식 베이스 제품임

이 문서에서 먼저 알아야 할 전제는 아래와 같다.

- 사용자가 직접 수정하는 Markdown 파일이 진실 원본임
- 데이터베이스는 검색, 링크 해석, 상태 비교를 빠르게 하기 위한 인덱스임
- sync 계층은 "파일을 DB에 맞추는 것"이 아니라 "DB를 파일 상태에 맞추는 것"을 목표로 함
- local-first의 핵심은 저장 위치보다 파일 소유권과 복구 가능성을 유지하는 운영 구조에 있음

핵심 용어는 아래 뜻으로 보면 된다.

| 용어 | 뜻 |
| --- | --- |
| Project | 하나의 지식 베이스 단위. 고유한 루트 디렉터리와 sync 상태를 가짐 |
| Entity | Markdown 파일 하나에 대응하는 DB 엔티티이자 지식 그래프 노드 |
| WatchService | 파일 변경 이벤트를 감시하고 묶어서 sync 계층에 넘기는 런타임 |
| SyncService | 파일과 DB 상태를 비교하고 변경 사항을 반영하는 핵심 동기화 계층 |
| checksum | 파일 내용이 실제로 바뀌었는지 판정하기 위한 해시 값 |
| watermark | 마지막 스캔 기준점을 저장해 다음 sync 전략을 정하는 메타데이터 |
| `doctor` | 파일, DB, 검색 인덱스 루프가 실제로 건강한지 확인하는 운영 검증 명령 |

예를 들어 사용자가 에디터에서 Markdown 파일 하나를 직접 수정하면 대략 아래 흐름이 일어난다.

1. `WatchService`가 변경 이벤트를 감지함
2. `SyncService`가 파일 상태를 다시 읽고 checksum과 메타데이터를 비교함
3. 바뀐 내용이 있으면 `Entity`, relation, search index를 다시 갱신함
4. 마지막에 scan watermark를 업데이트해 다음 증분 sync 기준점으로 삼음

즉 이 문서의 주제는 "파일 기반 지식 시스템에서 검색 가능한 상태를 어떻게 계속 맞춰두는가"에 가깝다.

벤치마킹할 지점은 네 가지다.

- 파일 원본과 DB 인덱스의 역할을 명확히 분리하는 방식
- watcher, checksum, watermark를 조합해 증분 sync를 구성하는 방식
- 직접 수정, 이동, 삭제가 발생해도 인덱스와 그래프를 복구하는 방식
- `doctor`를 개발 명령이 아니라 운영 검증 루프로 포함하는 방식

# 시스템 핵심 동작 방식 및 사용 기술

## 1. 파일 원본과 DB 인덱스의 일관성을 유지하는 구조

### 채택 기술 구조

- 기본 원칙
    - Basic Memory는 처음부터 파일과 DB의 책임을 다르게 둠
    - `docs/NOTE-FORMAT.md`는 파일이 source of truth라고 명시함
    - 실제 런타임은 이 전제를 `SyncService`에 녹여, 사용자가 Markdown 파일을 직접 수정하면 시스템이 그 결과를 DB와 검색 인덱스로 반영함
- 동기화 기본 흐름
    - 일관성은 "저장 즉시 끝"이 아니라 `scan -> classify -> apply -> reindex -> watermark update` 흐름으로 유지됨
    - `Entity`는 `file_path`, `checksum`, `mtime`, `size`를 저장해 파일 상태의 기준점을 가짐
    - `Project`는 `last_scan_timestamp`, `last_file_count`를 저장해 다음 스캔 전략을 결정함
    - `SyncService.scan()`은 파일 시스템과 DB를 비교해 `new`, `modified`, `deleted`, `moves`를 계산함
    - `SyncService.sync()`는 move를 먼저, delete를 다음, new/modified를 마지막에 반영함
    - 반영이 끝나면 relation resolution과 검색 인덱싱을 다시 수행하고, 마지막에 scan watermark를 갱신함
- 설계 해석
    - DB를 "권위 있는 저장소"로 쓰지 않음
    - 상태 비교의 기준은 항상 파일 시스템이고, DB는 그 상태를 빠르게 질의하기 위한 파생 계층임
    - sync도 DB를 파일에 맞추는 방향으로만 설계돼 있음
- 운영 포인트
    - move를 먼저 처리해야 이후 delete/new 분류가 꼬이지 않음
    - relation resolution은 실제 변경이 있을 때만 수행해 비용을 줄임
    - 워터마크는 sync 종료 시점이 아니라 시작 시점을 기록해, sync 도중 생긴 파일이 다음 번에 누락되지 않게 함

### 코드 근거 예시

- `docs/NOTE-FORMAT.md`
    - 파일이 source of truth라고 명시함
- `src/basic_memory/models/knowledge.py`
    - `Entity`가 `checksum`, `mtime`, `size`, `file_path`를 함께 저장함
- `src/basic_memory/models/project.py`
    - `Project`가 `last_scan_timestamp`, `last_file_count`를 저장함
- `src/basic_memory/sync/sync_service.py`
    - `scan()`이 파일과 DB 차이를 `new`, `modified`, `deleted`, `moves`로 계산함
    - `sync()`가 move -> delete -> new/modified 순으로 반영함
    - 성공 후 relation resolution, 검색 인덱싱, watermark 갱신까지 마무리함
- `src/basic_memory/schemas/sync_report.py`
    - sync 결과를 `SyncReportResponse`로 노출해 상태 확인과 진단에 재사용함

### 제품 적용 포인트

- 파일 기반 제품이라면 DB를 원본으로 만들지 말고 재생성 가능한 인덱스로 두는 편이 운영 원칙이 선명함
- 일관성은 "이벤트가 오면 바로 반영"보다 `scan 결과를 명시적 diff로 만든 뒤 적용`하는 구조가 디버깅에 유리함
- 엔티티 테이블에는 최소한 `checksum`, `mtime`, `size`를 같이 저장해야 증분 동기화가 현실적으로 동작함
- 프로젝트 단위 워터마크를 두면 전체 시스템이 아니라 지식 베이스 단위로 증분 전략을 최적화할 수 있음

### 해석과 시사점

- Basic Memory의 강점은 local-first를 감성적 구호가 아니라 운영 가능한 상태 머신으로 구현한 점에 있음
- 파일과 DB의 역할을 분리했기 때문에 사용자는 파일 소유권을 유지하고, 시스템은 검색 성능을 확보함
- 반대로 이 구조는 DB 단독 복구보다 파일 시스템 상태 복구가 더 중요하다는 전제를 함께 받아들여야 함

## 2. watcher, checksum, watermark를 묶어 증분 sync를 만드는 방식

### 채택 기술 구조

- 핵심 구성
    - 증분 sync의 핵심은 watcher 하나가 아니라 세 계층의 조합임
    - `WatchService`는 파일 이벤트를 받음
    - `SyncService`는 변경을 실제 엔티티 갱신으로 변환함
    - `Project` watermark는 다음 스캔을 full scan으로 할지 incremental scan으로 할지 결정함
- watcher 역할
    - `WatchService`는 `watchfiles.awatch`로 변경을 수집함
    - debounce와 필터링을 먼저 적용함
    - 숨김 파일, `.tmp` 파일, gitignore 대상은 초기에 걸러냄
    - 프로젝트별로 변경을 묶고, 추가·삭제·수정으로 분류함
    - added + deleted 조합에서 checksum이 같은 경우 move로 승격함
- scan 전략
    - `SyncService.scan()`은 watcher 이벤트에만 의존하지 않음
    - 프로젝트의 `last_file_count`와 `last_scan_timestamp`를 보고 다음 전략을 선택함
    - 첫 sync면 full scan
    - 파일 수가 줄었으면 deletion 탐지를 위해 full scan
    - 삭제가 없고 watermark가 있으면 incremental scan
    - 사용자가 `force_full=True`를 주면 강제로 full scan
- incremental 판정 방식
    - 먼저 파일 수를 빠르게 셈
    - 수정 가능성이 있는 파일만 추려 mtime과 size를 비교함
    - 실제 checksum이 다를 때만 modified로 분류함
    - 즉 `mtime/size`는 싸게 거르고, `checksum`은 최종 확인에만 씀
- 구조적 의미
    - 대량 노트에서 전체 재색인을 피하면서도 삭제와 rename 같은 까다로운 케이스를 놓치지 않게 함
    - watcher는 빠른 반영을 담당함
    - watermark 기반 scan은 watcher가 놓칠 수 있는 상태 복구를 담당함
    - 둘은 대체 관계가 아니라 보완 관계임
- lifecycle 관리
    - watch lifecycle은 `SyncCoordinator`와 `initialize_file_sync()`가 감쌈
    - 시작 시 각 프로젝트에 대해 background sync를 먼저 걸고, 그 다음 watch loop를 실행함
    - 테스트 환경에서는 watcher를 아예 켜지 않음
    - 런타임 편의성과 테스트 안정성을 별도 계층에서 조절함

### 코드 근거 예시

- `src/basic_memory/sync/watch_service.py`
    - `awatch()` 기반 감시
    - debounce, hidden file, `.tmp`, gitignore 필터 적용
    - added/deleted checksum 비교로 move 감지
    - 프로젝트 목록을 주기적으로 다시 읽어 watch cycle을 재시작함
- `src/basic_memory/sync/sync_service.py`
    - `_quick_count_files()`로 파일 수를 빠르게 계산함
    - `_scan_directory_modified_since()`로 watermark 이후 변경 파일만 추림
    - mtime/size 비교 후 checksum으로 실제 수정 여부를 확정함
    - 삭제는 file count 감소 시 full scan으로 탐지함
- `src/basic_memory/models/project.py`
    - scan watermark 저장 필드 보유
- `src/basic_memory/sync/coordinator.py`
    - sync/watch lifecycle을 중앙에서 시작하고 중지함
- `src/basic_memory/services/initialization.py`
    - background sync 후 watch service를 올림
    - 테스트 환경에서는 file sync 초기화를 건너뜀

### 제품 적용 포인트

- watcher만 믿지 말고 주기적 또는 요청 기반 상태 스캔을 함께 둬야 운영이 안정적임
- 증분 sync는 `mtime/size로 1차 판별`, `checksum으로 확정`의 2단계가 비용 대비 효율이 좋음
- 삭제 탐지는 수정 탐지와 다르게 다뤄야 하므로 file count 같은 별도 신호가 필요함
- watch service와 sync service를 분리하면 이벤트 수집과 상태 반영의 실패 범위를 나눌 수 있음
- 테스트 환경에서 watcher를 끄는 정책은 비동기 teardown 불안정성을 줄이는 데 효과적임

### 해석과 시사점

- Basic Memory는 "실시간 반영"보다 "운영 가능한 반영"을 택했다
- 특히 watcher, watermark, checksum을 한 세트로 묶은 점이 대규모 파일 기반 제품에 실용적이다
- 반대로 이 구조는 파일 시스템의 mtime 정밀도와 rename semantics에 일정 부분 의존하므로, 플랫폼별 차이를 테스트로 보완해야 한다

## 3. 직접 수정, 이동, 삭제가 발생해도 정합성을 복구하는 흐름

### 채택 기술 구조

- 기본 전제
    - Basic Memory는 사용자가 앱 내부 UI 대신 에디터와 파일 탐색기에서 직접 작업하는 상황을 기본 전제로 둠
    - 그래서 복구 흐름도 "예외 케이스"가 아니라 주요 경로에 포함돼 있음
- 직접 수정 복구
    - `WatchService.handle_changes()`가 수정 이벤트를 `sync_file()`로 보냄
    - Markdown 파일이면 parser가 다시 frontmatter와 본문을 읽음
    - `upsert_entity_from_markdown()`이 엔티티, observation, relation을 다시 정리함
    - 이후 최종 checksum을 다시 계산하고 검색 인덱스를 갱신함
    - sync 중 파일이 사라지면 `FileNotFoundError`를 deletion으로 간주해 정리함
- 삭제 복구
    - `handle_delete()`가 DB 엔티티를 지움
    - cascade로 observation과 relation을 제거함
    - 엔티티와 파생 observation/relation permalink에 대응하는 검색 row까지 정리함
    - 즉 파일 삭제를 단순 row delete가 아니라 그래프와 검색 인덱스 정리까지 포함한 삭제로 봄
- 이동 복구
    - watcher 레벨에서는 added + deleted의 checksum 일치로 move를 감지함
    - scan 레벨에서도 "새 파일의 checksum과 같은 기존 엔티티가 있고 원본 경로는 더 이상 없을 때" move로 해석함
    - `handle_move()`는 `file_path`를 새 경로로 갱신함
    - 설정이 켜져 있으면 frontmatter의 permalink도 새 경로 기준으로 다시 쓰고 checksum을 재계산함
    - 이후 search index를 다시 생성함
- 구조적 의미
    - "복구"를 느슨한 fallback으로 두지 않음
    - 삭제는 검색 정리까지 포함함
    - 이동은 path conflict와 swap 시나리오까지 포함함
    - markdown 갱신은 frontmatter 보정과 relation resolution까지 포함함
    - 사람이 파일 시스템에서 직접 작업하는 제품이라면 이 정도 복구 경로가 핵심 기능에 가까움
- 실패 제어
    - sync는 실패 파일을 무한 재시도하지 않음
    - `SyncService`는 파일별 연속 실패 횟수와 마지막 checksum을 기억함
    - 같은 파일이 같은 상태로 계속 실패하면 circuit breaker처럼 잠시 건너뜀
    - 파일 내용이 바뀌면 checksum 차이로 실패 기록을 지우고 다시 시도함
    - 운영 안정성 측면에서 중요한 장치임

### 코드 근거 예시

- `src/basic_memory/sync/watch_service.py`
    - deleted event가 실제로 남아 있는 파일이면 atomic write로 보고 modification으로 처리함
    - add + delete + checksum 일치 조합으로 move를 감지함
- `src/basic_memory/sync/sync_service.py`
    - `sync_file()`가 markdown와 일반 파일 경로를 분리 처리함
    - `sync_markdown_file()`가 parse -> upsert -> final checksum update 흐름을 수행함
    - `handle_delete()`가 DB cascade 삭제와 search cleanup을 함께 수행함
    - `handle_move()`가 path conflict 점검, permalink/frontmatter 갱신, search reindex를 수행함
    - 반복 실패 파일은 checksum 기반 circuit breaker로 일시 제외함
- `src/basic_memory/services/file_service.py`
    - atomic write, async checksum, frontmatter update, file move를 제공함
    - rename과 frontmatter 갱신이 별도 서비스로 추상화돼 있음

### 제품 적용 포인트

- 파일 기반 제품은 직접 수정과 앱 내부 수정을 같은 1급 시나리오로 봐야 함
- 삭제 처리에는 DB row 삭제만 아니라 그래프 edge와 검색 row 정리까지 포함돼야 함
- rename은 `new + deleted`로만 처리하지 말고 checksum 비교로 move를 판정하는 편이 안전함
- atomic write를 쓰는 편집기 특성을 알아야 DELETE 이벤트를 오탐하지 않음
- 반복 실패 파일을 무한 재시도하지 않는 보호 장치를 두면 watch loop 전체가 불안정해지는 것을 막을 수 있음

### 해석과 시사점

- Basic Memory의 local-first가 강한 이유는 "사용자가 시스템 바깥에서 작업한다"는 현실을 정면으로 받아들였기 때문이다
- 이 설계 덕분에 파일 탐색기, Git, 외부 에디터를 써도 지식 그래프를 다시 맞춰 놓을 수 있다
- 반대로 checksum 기반 move 판별은 내용이 동시에 바뀐 rename에는 보수적으로 동작할 수 있으므로, 일부 케이스는 delete + new로 처리될 수 있다

## 4. `doctor`를 제품 안에 포함한 이유와 역할

### 채택 기술 구조

- 역할 정의
    - `doctor`는 단순 상태 출력 명령이 아니라 "파일 ↔ DB 루프가 실제로 건강한가"를 제품 수준에서 검증하는 시나리오 테스트임
    - 중요한 점은 이 검증이 테스트 코드 바깥이 아니라 사용 가능한 CLI 명령으로 제공된다는 점임
- 검증 시나리오
    - `run_doctor()`는 임시 프로젝트를 만든 뒤 네 단계를 실제 제품 경로로 검증함
    1. API를 통해 엔티티를 생성하고 파일이 실제로 생겼는지 확인
    2. 사용자가 파일을 직접 작성한 뒤 `force_full=True`, `run_in_background=False`로 sync를 실행
    3. 검색으로 수동 작성 노트가 인덱싱됐는지 확인
    4. 마지막으로 `status`를 호출해 파일과 DB 사이에 남은 차이가 없는지 확인
- 구조적 의미
    - `doctor`는 단위 기능이 아니라 `DB -> File`, `File -> DB`, `Search`, `Status clean`을 한 루프로 엮어 봄
    - 지식 베이스 제품의 실패는 대개 개별 함수보다 계층 간 연결에서 발생하기 때문에 이 방식이 중요함
- 실행 격리
    - `just doctor`는 임시 HOME과 임시 config 디렉터리를 사용함
    - `BASIC_MEMORY_ENV=test`를 설정한 뒤 로컬 라우팅으로만 실행함
    - 사용자의 실제 Basic Memory 설정을 건드리지 않으면서도 실제 CLI 경로를 검증함
- 품질 장치로서의 의미
    - 이 구조는 테스트와 운영 검증의 중간층으로 볼 수 있음
    - pytest가 세밀한 회귀를 잡는다면, `doctor`는 배포 환경이나 로컬 개발 환경에서 "이 제품의 핵심 약속이 아직 성립하는가"를 빠르게 확인함
    - local-first 제품에서는 파일, DB, 검색 인덱스가 함께 맞아야 하므로 이런 검증 루프가 특히 중요함

### 코드 근거 예시

- `src/basic_memory/cli/commands/doctor.py`
    - 임시 프로젝트 생성
    - API write 후 파일 생성 확인
    - 수동 Markdown 작성 후 foreground full sync 실행
    - 검색 확인 후 status clean 확인
- `src/basic_memory/api/v2/routers/project_router.py`
    - `sync`와 `status`가 같은 `SyncService` 결과를 API로 노출함
- `src/basic_memory/schemas/sync_report.py`
    - status와 sync가 같은 보고 형식을 사용함
- `README.md`
    - `just doctor`를 fast local workflow 옆에 별도 consistency check로 둠
- `justfile`
    - 임시 HOME, 임시 config, test env로 doctor를 격리 실행함

### 제품 적용 포인트

- local-first 제품이라면 health check는 HTTP ping보다 `file -> index -> search` 루프 검증이어야 함
- 운영 점검 명령은 테스트 더블이 아니라 실제 제품 진입점을 통해 실행하는 편이 가치가 큼
- doctor 성격의 명령은 사용자 설정을 오염시키지 않도록 격리 환경에서 실행해야 함
- `status clean`을 마지막 조건으로 두면 "동작했다"가 아니라 "남은 불일치가 없다"까지 확인할 수 있음

### 해석과 시사점

- Basic Memory는 sync를 백그라운드 구현 세부사항으로 숨기지 않고, 제품이 책임져야 할 건강 상태로 다룬다
- `doctor`를 CLI에 포함한 것은 파일 기반 지식 시스템의 핵심 리스크가 계층 간 정합성에 있다는 판단으로 읽힌다
- 우리 제품도 local-first 구조를 택한다면, smoke test와 별도로 `원본 저장소 ↔ 인덱스 ↔ 검색`을 한 번에 검증하는 doctor 루프가 필요하다

## 5. 한계와 트레이드오프

### 현재 구현 기준에서 주의할 점

- 증분 최적화는 워터마크와 파일 수 비교에 크게 의존하므로, 파일 시스템 메타데이터 신뢰도가 낮은 환경에서는 full scan 비중이 늘 수 있음
- move 판별은 checksum 기반이라 rename과 동시에 내용이 바뀌는 경우에는 delete + new로 해석될 수 있음
- watcher와 scan이 둘 다 필요하다는 점은 구조를 단순하게 만들기보다 운영 안정성을 우선한 선택임
- local-first 구조인 만큼 DB만 백업해서는 충분하지 않고, 파일 저장소를 중심으로 복구 전략을 세워야 함
- cloud-mode 프로젝트를 어떻게 local watch 대상에 포함할지까지 고려해야 하므로, 라우팅 정책이 sync 계층과 맞물림

### 제품 해석

- Basic Memory의 sync 설계는 "간단한 메모 앱"보다 "파일 기반 지식 인프라"에 더 가깝다
- 강점은 빠른 반응성보다 복구 가능성과 상태 진단 가능성을 함께 갖춘 점에 있다
- 따라서 벤치마킹의 핵심도 실시간 UX보다 `상태 비교 모델`, `복구 경로`, `검증 루프`에 맞추는 편이 맞다

# 적용 인사이트

우리 제품이 Basic Memory에서 가장 먼저 가져와야 할 것은 local-first를 파일 저장 방식이 아니라 운영 원칙으로 구현하는 태도다. 특히 `파일 원본 / DB 인덱스 분리`, `watcher + watermark + checksum 조합`, `이동·삭제 복구 경로`, `doctor 검증 루프`를 한 세트로 설계해야 한다.

- 파일 기반 지식 제품에서는 DB를 진실 원본으로 두지 말고 재생성 가능한 인덱스로 설계하는 편이 장기 운영에 유리함
- 증분 sync는 watcher 하나로 끝나지 않으며, watermark와 상태 스캔이 반드시 함께 가야 함
- 사용자가 앱 밖에서 직접 파일을 고칠 것을 기본 전제로 삼아야 복구 경로가 튼튼해짐
- sync health는 로그 몇 줄이 아니라 `status clean`까지 포함한 검증 루프로 관리해야 함
- local-first의 경쟁력은 저장 위치보다 "사용자 소유권을 유지하면서도 검색과 그래프를 잃지 않는 구조"에 있음