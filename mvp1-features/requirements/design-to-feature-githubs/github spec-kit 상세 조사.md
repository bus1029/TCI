# github/spec-kit 상세 조사

- 조사 대상: `github/spec-kit`
- 조사 목적: TCI의 기능 기획을 설계 입력 수준의 문서로 끌어올릴 수 있는지 검증
- 조사 시점: 2026-04-09 (KST)
- 조사 기준: 공식 저장소, 공식 문서, 공식 릴리스 페이지 중심

## 1. 한줄 결론

`github/spec-kit`은 TCI가 원하는 `기획 → 명세 → 기술 계획 → 작업 분해` 흐름에 가장 잘 맞는 후보다. 다만 기본 산출물은 개발 실행 중심이므로, TCI에 맞게 쓰려면 preset 또는 프로젝트 로컬 템플릿 오버라이드가 사실상 필요하다

출처: [README](https://github.com/github/spec-kit/blob/main/README.md), [Quick Start Guide](https://github.com/github/spec-kit/blob/main/docs/quickstart.md), [Presets README](https://github.com/github/spec-kit/blob/main/presets/README.md)

참고: 아래의 적합성 판단과 도입 권고는 upstream 문서의 직접 진술이 아니라 TCI 관점의 해석을 포함한다

## 2. 왜 TCI에 맞는가

### 2.1 워크플로우가 명확하다

Spec Kit의 기본 흐름은 `constitution → specify → clarify → plan → tasks → implement`다. 이 구조는 TCI가 원하는 문서 흐름과 거의 그대로 맞닿아 있다

- `specify`: 기능 설명을 요구사항 명세로 정리
- `clarify`: 빠진 질문과 모호한 범위를 정제
- `plan`: 기술 설계와 검증 자료 생성
- `tasks`: 실행 가능한 작업 단위로 분해

TCI 관점에서 중요한 점은 기획 문서를 바로 코드로 넘기지 않고, 명세와 계획 단계를 중간에 강제한다는 점이다

출처: [README](https://github.com/github/spec-kit/blob/main/README.md), [Quick Start Guide](https://github.com/github/spec-kit/blob/main/docs/quickstart.md), [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)

### 2.2 산출물 구조가 설계 입력에 가깝다

핵심 산출물은 아래와 같다

- `spec.md`
- `plan.md`
- `research.md`
- `data-model.md`
- `quickstart.md`
- `contracts/`
- `tasks.md`

이 구조는 단순 기능 목록보다 설계 착수에 훨씬 유리하다. 특히 `spec.md`는 사용자 스토리, 수용 시나리오, 성공 기준, 가정까지 담게 하고, `plan` 단계는 데이터 모델과 계약 명세를 분리해 남긴다

TCI 관점에서 보면 "기획 문서"와 "개발 착수 문서" 사이의 빈 구간을 메우는 기본 뼈대가 이미 있다

출처: [spec-template](https://github.com/github/spec-kit/blob/main/templates/spec-template.md), [plan-template](https://github.com/github/spec-kit/blob/main/templates/plan-template.md), [tasks-template](https://github.com/github/spec-kit/blob/main/templates/tasks-template.md)

### 2.3 clarify 단계가 특히 유용하다

공식 문서는 `clarify`를 계획 수립 전 권장되는 정제 단계로 둔다. 이 단계는 모호한 요구사항을 질문 기반으로 메우고, 이후 재작업 비용을 줄이는 역할을 한다

TCI에서는 이 단계가 특히 중요하다. 현재도 "설계 착수 가능 여부"를 판단해야 하는데, `clarify`는 다음 질문을 구조적으로 드러내는 데 적합하다

- 범위가 닫혔는가
- 수용 기준이 충분한가
- 기술 계획으로 넘어가도 되는가
- 아직 결정되지 않은 핵심 항목은 무엇인가

출처: [Quick Start Guide](https://github.com/github/spec-kit/blob/main/docs/quickstart.md), [README](https://github.com/github/spec-kit/blob/main/README.md)

## 3. TCI 기준 장점

- 기능 리스트를 요구사항 명세로 전환하기 쉽다
- 설계 전에 빠진 질문을 드러내는 절차가 내장돼 있다
- 설계 이후 `tasks`까지 이어져 backlog나 issue로 연결하기 좋다
- preset과 override 구조 덕분에 fork 없이 조직 맞춤화가 가능하다

출처: [README](https://github.com/github/spec-kit/blob/main/README.md), [Presets README](https://github.com/github/spec-kit/blob/main/presets/README.md), [tasks-template](https://github.com/github/spec-kit/blob/main/templates/tasks-template.md)

## 4. TCI 기준 리스크와 한계

- 기본 산출물은 PM 문서보다 개발 실행 문서에 더 가깝다
- 현재 TCI 문서 구조와 기본 디렉터리 구조가 다르다
- 프로젝트가 아직 빠르게 변하고 있어 버전 고정과 업그레이드 정책이 필요하다
- 커뮤니티 extension과 preset은 별도 신뢰 검증이 필요하다

조금 더 구체적으로 보면 아래와 같다

- 문서 언어와 항목 구성은 TCI 문맥에 맞게 조정해야 한다
- 기본 구조는 `.specify/`와 `specs/###-feature-name/` 중심이라 현재 `mvp1-features/requirements` 체계와 매핑 정책이 필요하다
- 도입 시 `main` 추적보다 태그 고정 설치가 안전하다
- 외부 extension은 공식 보증 대상이 아니므로 초기에는 코어 워크플로우와 내부 preset 중심이 적절하다

출처: [README](https://github.com/github/spec-kit/blob/main/README.md), [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md), [Release v0.5.1](https://github.com/github/spec-kit/releases/tag/v0.5.1), [Presets README](https://github.com/github/spec-kit/blob/main/presets/README.md)

## 5. 권장 도입 방식

### 권장 원칙

- `implement`는 당분간 쓰지 않는다
- 초도 도입은 `specify → clarify → plan → tasks`까지만 사용한다
- 기본 템플릿을 그대로 쓰지 말고 TCI용 preset 또는 project-local override를 만든다
- 외부 extension 도입은 나중으로 미룬다

### TCI 문서 체계와의 매핑

| TCI 목적 | Spec Kit 대응 | 비고 |
| --- | --- | --- |
| 기능 설명 정리 | `specify` | 기능을 사용자 스토리와 요구사항으로 변환 |
| 설계 착수 가능 여부 판단 | `clarify` | 현재 판단 기준 문서와 가장 잘 맞음 |
| 기술 설계 입력 작성 | `plan` | `plan.md`, `research.md`, `contracts/` 활용 |
| 데이터/연동 구조 정의 | `data-model.md`, `contracts/` | 외부 시스템 연동 기능에 유리 |
| 실행 단위 분해 | `tasks` | 후속 issue/backlog 변환 기반 |

출처: [Quick Start Guide](https://github.com/github/spec-kit/blob/main/docs/quickstart.md), [spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)

### 파일럿 권장 범위

처음부터 전면 도입하기보다 설계 난도가 있고 시스템 경계가 분명한 기능 하나에 붙여보는 편이 맞다

- 코드 저장소 연동
- 티켓 시스템 연동
- 문서-코드 추적
- 문서와 코드 간 불일치 분석

권장 절차는 아래와 같다

1. 파일럿 기능 하나 선택
2. TCI constitution 초안 작성
3. `specify`로 목적, 사용자 가치, 범위 명세화
4. `clarify`로 누락 질문 정리
5. `plan`으로 기술 경계, 데이터 모델, 계약, 검증 시나리오 작성
6. `tasks`에서 멈추고 결과를 TCI 문서 체계에 편입

## 6. 최종 판단

현재 목적이 "기획을 설계로 구체화"하는 것이라면, `github/spec-kit`은 여전히 가장 유력한 단일 후보로 볼 수 있다. 이유는 세 가지다

- 요구사항 정제와 설계 문서화 사이의 중간 산출물이 분명하다
- `clarify`가 있어 설계 착수 전 질문을 구조적으로 수집할 수 있다
- preset과 override 구조 덕분에 TCI 맞춤형 문서 체계로 변형하기 쉽다

정리하면 결론은 아래와 같다

- 도입 가치 높음
- 템플릿 현지화 전제
- 초기에는 코어 워크플로우만 제한적으로 도입

## 7. 참고 링크

- 저장소: https://github.com/github/spec-kit
- README: https://github.com/github/spec-kit/blob/main/README.md
- Spec-Driven Development 설명: https://github.com/github/spec-kit/blob/main/spec-driven.md
- Quick Start Guide: https://github.com/github/spec-kit/blob/main/docs/quickstart.md
- Installation Guide: https://github.com/github/spec-kit/blob/main/docs/installation.md
- Presets README: https://github.com/github/spec-kit/blob/main/presets/README.md
- `spec-template`: https://github.com/github/spec-kit/blob/main/templates/spec-template.md
- `plan-template`: https://github.com/github/spec-kit/blob/main/templates/plan-template.md
- `tasks-template`: https://github.com/github/spec-kit/blob/main/templates/tasks-template.md
- 최신 릴리스 `v0.5.1`: https://github.com/github/spec-kit/releases/tag/v0.5.1
- `pyproject.toml`: https://github.com/github/spec-kit/blob/main/pyproject.toml
